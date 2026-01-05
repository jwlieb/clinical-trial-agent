"""Two-stage patient-trial matching."""

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.schemas import (
    PatientProfile,
    Trial,
    FilterResult,
    MatchResult,
    MatchLikelihood,
)

console = Console()

# Configuration
DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.1-70b-versatile")
MAX_LLM_TOKENS = 1200  # Increased for 70B model
MAX_PARALLEL_LLM_CALLS = 2  # Reduced to avoid rate limits
LLM_TIMEOUT_SECONDS = 30.0
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")  # "openai" or "groq"

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 2.0  # seconds

# Rate limiting configuration
MIN_REQUEST_INTERVAL = 1.0  # Minimum seconds between LLM calls
_last_request_time = 0.0
_rate_limit_lock = __import__('threading').Lock()


def _rate_limited_llm_call(client, **kwargs):
    """Make an LLM call with rate limiting and retry logic."""
    global _last_request_time

    for attempt in range(MAX_RETRIES):
        # Rate limiting
        with _rate_limit_lock:
            elapsed = time.time() - _last_request_time
            if elapsed < MIN_REQUEST_INTERVAL:
                time.sleep(MIN_REQUEST_INTERVAL - elapsed)
            _last_request_time = time.time()

        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            error_str = str(e).lower()
            if "429" in str(e) or "rate_limit" in error_str or "rate limit" in error_str:
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    console.print(f"  [yellow]Rate limited, retrying in {delay:.1f}s...[/yellow]")
                    time.sleep(delay)
                else:
                    raise
            else:
                raise

# Recruiting statuses that indicate trial is open for enrollment
RECRUITING_STATUSES = {
    "Recruiting",
    "Not yet recruiting",
    "Enrolling by invitation",
}

# Try to import LLM clients
LLM_CLIENT = None
try:
    if LLM_PROVIDER == "groq":
        from groq import Groq
        LLM_CLIENT = Groq
    else:
        from openai import OpenAI
        LLM_CLIENT = OpenAI
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


ELIGIBILITY_SCORING_PROMPT = """You are evaluating whether a patient is likely eligible for a clinical trial.

## Patient Profile
{patient_description}

## Trial Eligibility Criteria
{eligibility_text}

## Task
Evaluate each key criterion and determine overall match likelihood.

Respond with a JSON object:
{{
    "match_likelihood": "HIGH" | "MEDIUM" | "LOW" | "EXCLUDED",
    "supporting_factors": ["reasons patient likely qualifies"],
    "conflicts": ["reasons patient may not qualify"],
    "uncertainties": ["criteria that are unclear or need verification"],
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation of assessment"
}}

## Scoring Guidelines
- HIGH: Patient clearly meets the stated criteria based on available information
- MEDIUM: Patient likely qualifies but some criteria are unclear or need verification
- LOW: Patient may qualify but there are significant uncertainties
- EXCLUDED: Patient clearly fails one or more hard exclusion criteria

## Rules
- Be conservative — flag uncertainties rather than assuming
- If a criterion isn't mentioned in the patient profile, mark it as uncertain, not a conflict
- Prior treatments: Check if patient's prior treatments are allowed or excluded
- Brain metastases: Pay close attention to brain met policies (often nuanced)
- ECOG status: Match patient's ECOG against trial requirements
"""


def parse_age(age_str: str | None) -> int | None:
    """Parse age string like '18 Years' into integer.
    
    Args:
        age_str: Age string from API (e.g., '18 Years', '75 Years')
        
    Returns:
        Age as integer or None if unparseable
    """
    if not age_str:
        return None
    match = re.search(r'(\d+)', age_str)
    return int(match.group(1)) if match else None


def fast_filter(patient: PatientProfile, trial: Trial) -> FilterResult:
    """Stage 1: Fast deterministic filter using structured fields.
    
    Checks obvious exclusion criteria that don't require LLM interpretation.
    
    Args:
        patient: The patient profile
        trial: The trial to check
        
    Returns:
        FilterResult indicating if trial passed or reason for exclusion
    """
    # Guard against missing eligibility data
    if not trial.eligibility:
        return FilterResult(passed=True)  # Pass to LLM stage for assessment
    
    eligibility = trial.eligibility
    
    # 1. Status filter - only recruiting trials
    if trial.status not in RECRUITING_STATUSES:
        return FilterResult(
            passed=False,
            excluded_reason=f"Trial status '{trial.status}' is not actively recruiting"
        )
    
    # 2. Sex filter
    if patient.sex and eligibility.sex:
        trial_sex = eligibility.sex.upper()
        patient_sex = patient.sex.lower()
        
        if trial_sex != "ALL":
            if patient_sex == "male" and trial_sex == "FEMALE":
                return FilterResult(
                    passed=False,
                    excluded_reason="Trial requires female patients"
                )
            if patient_sex == "female" and trial_sex == "MALE":
                return FilterResult(
                    passed=False,
                    excluded_reason="Trial requires male patients"
                )
    
    # 3. Age filter
    if patient.age is not None:
        min_age = parse_age(eligibility.minimum_age)
        max_age = parse_age(eligibility.maximum_age)
        
        if min_age is not None and patient.age < min_age:
            return FilterResult(
                passed=False,
                excluded_reason=f"Patient age {patient.age} is below minimum age {min_age}"
            )
        if max_age is not None and patient.age > max_age:
            return FilterResult(
                passed=False,
                excluded_reason=f"Patient age {patient.age} is above maximum age {max_age}"
            )
    
    # 4. Phase preference filter (if specified)
    if patient.phase_preference and trial.phase:
        if trial.phase not in patient.phase_preference:
            return FilterResult(
                passed=False,
                excluded_reason=f"Trial phase '{trial.phase}' not in patient preference: {patient.phase_preference}"
            )
    
    # 5. Location preference filter (if specified)
    if patient.location_preference and trial.locations:
        # Check if any preferred location is in trial locations
        preferred_set = {loc.lower() for loc in patient.location_preference}
        trial_set = {loc.lower() for loc in trial.locations}
        if not preferred_set & trial_set:
            return FilterResult(
                passed=False,
                excluded_reason=f"Trial locations {trial.locations} don't match preference: {patient.location_preference}"
            )
    
    # Passed all filters
    return FilterResult(passed=True)


def score_eligibility_with_llm(
    patient: PatientProfile,
    trial: Trial
) -> dict:
    """Stage 2: Score patient eligibility using LLM.
    
    Sends patient description and trial eligibility criteria to LLM
    for nuanced assessment.
    
    Args:
        patient: The patient profile
        trial: The trial to score
        
    Returns:
        Dictionary with match assessment
    """
    if not LLM_AVAILABLE:
        return {
            "match_likelihood": "UNKNOWN",
            "supporting_factors": [],
            "conflicts": [],
            "uncertainties": ["LLM not available for eligibility assessment"],
            "confidence": 0.0,
            "reasoning": "LLM library not installed"
        }
    
    api_key_var = "GROQ_API_KEY" if LLM_PROVIDER == "groq" else "OPENAI_API_KEY"
    api_key = os.environ.get(api_key_var)
    if not api_key:
        return {
            "match_likelihood": "UNKNOWN",
            "supporting_factors": [],
            "conflicts": [],
            "uncertainties": ["LLM API key not configured"],
            "confidence": 0.0,
            "reasoning": f"{api_key_var} environment variable not set"
        }
    
    eligibility_text = trial.eligibility.raw_text
    if not eligibility_text:
        return {
            "match_likelihood": "UNKNOWN",
            "supporting_factors": [],
            "conflicts": [],
            "uncertainties": ["No eligibility criteria text available"],
            "confidence": 0.0,
            "reasoning": "Trial has no eligibility criteria text"
        }
    
    # Build patient description
    patient_parts = []
    if patient.age:
        patient_parts.append(f"Age: {patient.age}")
    if patient.sex:
        patient_parts.append(f"Sex: {patient.sex}")
    if patient.cancer_type:
        patient_parts.append(f"Cancer type: {patient.cancer_type}")
    if patient.biomarkers:
        patient_parts.append(f"Biomarkers: {', '.join(patient.biomarkers)}")
    patient_parts.append(f"Clinical details: {patient.description}")
    
    patient_description = "\n".join(patient_parts)
    
    prompt = ELIGIBILITY_SCORING_PROMPT.format(
        patient_description=patient_description,
        eligibility_text=eligibility_text
    )
    
    try:
        client = LLM_CLIENT(api_key=api_key, timeout=LLM_TIMEOUT_SECONDS)
        response = _rate_limited_llm_call(
            client,
            model=DEFAULT_LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a clinical trial eligibility analyst. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=MAX_LLM_TOKENS,
        )
        
        content = response.choices[0].message.content
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        result = json.loads(content.strip())
        
        # Validate and normalize response structure
        validated_result = {
            "match_likelihood": result.get("match_likelihood", "UNKNOWN"),
            "supporting_factors": result.get("supporting_factors") if isinstance(result.get("supporting_factors"), list) else [],
            "conflicts": result.get("conflicts") if isinstance(result.get("conflicts"), list) else [],
            "uncertainties": result.get("uncertainties") if isinstance(result.get("uncertainties"), list) else [],
            "confidence": float(result.get("confidence", 0.0)) if isinstance(result.get("confidence"), (int, float)) else 0.0,
            "reasoning": str(result.get("reasoning", "")) if result.get("reasoning") else "",
        }
        return validated_result
        
    except json.JSONDecodeError as e:
        return {
            "match_likelihood": "UNKNOWN",
            "supporting_factors": [],
            "conflicts": [],
            "uncertainties": [f"Failed to parse LLM response as JSON: {str(e)}"],
            "confidence": 0.0,
            "reasoning": "LLM returned invalid JSON"
        }
    except Exception as e:
        return {
            "match_likelihood": "UNKNOWN",
            "supporting_factors": [],
            "conflicts": [],
            "uncertainties": [f"LLM scoring failed: {str(e)}"],
            "confidence": 0.0,
            "reasoning": f"Error during LLM scoring: {str(e)}"
        }


def _score_single_trial(patient: PatientProfile, trial: Trial) -> MatchResult:
    """Score a single trial that passed fast filter.
    
    Args:
        patient: The patient profile
        trial: The trial to score
        
    Returns:
        MatchResult with LLM assessment
    """
    score = score_eligibility_with_llm(patient, trial)
    
    # Map string likelihood to enum
    likelihood_str = score.get("match_likelihood", "UNKNOWN").upper()
    try:
        likelihood = MatchLikelihood(likelihood_str)
    except ValueError:
        likelihood = MatchLikelihood.UNKNOWN
    
    return MatchResult(
        nct_id=trial.nct_id,
        title=trial.title,
        sponsor=trial.sponsor,
        phase=trial.phase,
        status=trial.status,
        match_likelihood=likelihood,
        filter_stage="llm_scored",
        supporting_factors=score.get("supporting_factors", []),
        conflicts=score.get("conflicts", []),
        uncertainties=score.get("uncertainties", []),
        confidence=score.get("confidence", 0.0),
        reasoning=score.get("reasoning", ""),
    )


def match_trials(
    patient: PatientProfile,
    trials: list[Trial],
    parallel: bool = True
) -> list[MatchResult]:
    """Match a patient against a list of trials using two-stage filtering.
    
    Stage 1: Fast deterministic filter on structured fields
    Stage 2: LLM-based eligibility scoring on candidates
    
    Args:
        patient: The patient profile
        trials: List of trials to match against
        parallel: Whether to run LLM scoring in parallel
        
    Returns:
        List of MatchResults sorted by likelihood (HIGH first)
    """
    results: list[MatchResult] = []
    candidates: list[Trial] = []
    
    # Stage 1: Fast filter
    console.print("\n[bold]Stage 1: Fast Filter[/bold]")
    for trial in trials:
        filter_result = fast_filter(patient, trial)
        
        if filter_result.passed:
            candidates.append(trial)
        else:
            # Add excluded trial to results
            results.append(MatchResult(
                nct_id=trial.nct_id,
                title=trial.title,
                sponsor=trial.sponsor,
                phase=trial.phase,
                status=trial.status,
                match_likelihood=MatchLikelihood.EXCLUDED,
                filter_stage="fast_filter",
                excluded_reason=filter_result.excluded_reason,
            ))
    
    console.print(f"  {len(trials)} trials evaluated")
    console.print(f"  {len(trials) - len(candidates)} excluded by fast filter")
    console.print(f"  {len(candidates)} candidates for LLM scoring")
    
    if not candidates:
        return results
    
    # Stage 2: LLM scoring
    console.print("\n[bold]Stage 2: LLM Eligibility Scoring[/bold]")
    
    if parallel and len(candidates) > 1:
        # Parallel LLM scoring
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Scoring {len(candidates)} trials...",
                total=len(candidates)
            )
            
            with ThreadPoolExecutor(max_workers=MAX_PARALLEL_LLM_CALLS) as executor:
                futures = {
                    executor.submit(_score_single_trial, patient, trial): trial
                    for trial in candidates
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        trial = futures[future]
                        console.print(f"  [yellow]Error scoring {trial.nct_id}: {e}[/yellow]")
                        results.append(MatchResult(
                            nct_id=trial.nct_id,
                            title=trial.title,
                            sponsor=trial.sponsor,
                            phase=trial.phase,
                            status=trial.status,
                            match_likelihood=MatchLikelihood.UNKNOWN,
                            filter_stage="llm_scored",
                            reasoning=f"Scoring error: {str(e)}",
                        ))
                    progress.advance(task)
    else:
        # Sequential LLM scoring
        for trial in candidates:
            result = _score_single_trial(patient, trial)
            results.append(result)
            console.print(f"  [dim]{trial.nct_id}: {result.match_likelihood.value}[/dim]")
    
    # Sort by likelihood (HIGH > MEDIUM > LOW > EXCLUDED > UNKNOWN)
    likelihood_order = {
        MatchLikelihood.HIGH: 0,
        MatchLikelihood.MEDIUM: 1,
        MatchLikelihood.LOW: 2,
        MatchLikelihood.EXCLUDED: 3,
        MatchLikelihood.UNKNOWN: 4,
    }
    
    results.sort(key=lambda r: (
        likelihood_order.get(r.match_likelihood, 5),
        -r.confidence  # Higher confidence first within same likelihood
    ))
    
    # Summary
    counts = {}
    for r in results:
        counts[r.match_likelihood.value] = counts.get(r.match_likelihood.value, 0) + 1
    
    console.print("\n[bold]Matching Summary:[/bold]")
    for likelihood in ["HIGH", "MEDIUM", "LOW", "EXCLUDED", "UNKNOWN"]:
        if likelihood in counts:
            console.print(f"  {likelihood}: {counts[likelihood]}")
    
    return results

