"""LLM-based gap review for trial coverage."""

import json
import os
from collections import Counter

from rich.console import Console

from src.schemas import (
    Trial, 
    SearchTerm, 
    GapReviewResult, 
    Provenance
)
from src.discover_trials import discover_trials, get_nct_id
from src.normalize_trials import normalize_trials
from src.validate_trials import validate_trials

console = Console()

# Configuration constants
DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
MAX_SUGGESTED_TERMS = 3
MAX_SAMPLE_TITLES = 10
MAX_TOP_ITEMS = 10
MAX_LLM_TOKENS = 500
LLM_SUGGESTED_CONFIDENCE = 0.7
ADDITIONAL_TRIALS_MAX_RESULTS = 50
REASONING_TRUNCATE_LENGTH = 100

# Check if OpenAI is available
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


GAP_REVIEW_PROMPT = """You are reviewing clinical trial search results for {target} inhibitors/modulators.

## Search Context
Search terms used: {terms}
Total trials found: {count}

## Results Summary
Phase distribution:
{phases}

Drugs/interventions mentioned (top 10):
{drugs}

Sponsors (top 10):
{sponsors}

## Sample Trial Titles
{sample_titles}

## Your Task
Based on your knowledge of this therapeutic area, assess whether there are obvious coverage gaps.

Consider:
1. Are there known drugs for this target that are missing?
2. Are there major pharmaceutical companies that should be running trials but aren't represented?
3. Is the phase distribution unusual (e.g., all early phase, no late phase)?
4. Are there known drug code names or aliases that might find additional trials?

## Response Format
Respond with a JSON object:
{{
    "coverage_assessment": "Good" or "Gaps Detected",
    "suggested_terms": ["term1", "term2"],  // Max 3 terms, empty if coverage is good
    "reasoning": "Brief explanation"
}}

Only suggest terms that are likely to find NEW trials not already captured.
"""


def build_summary(
    trials: list[Trial],
    search_terms: list[SearchTerm]
) -> dict:
    """Build a summary of trial results for LLM review.
    
    Args:
        trials: List of normalized trials
        search_terms: Search terms used
        
    Returns:
        Summary dict
    """
    # Phase distribution (handle None and empty strings)
    phases = Counter(t.phase if t.phase else "Unknown" for t in trials)
    phase_str = "\n".join(f"  - {phase}: {count}" for phase, count in phases.most_common())
    
    # Drug/intervention frequency
    all_interventions = []
    for t in trials:
        all_interventions.extend(t.interventions)
    drug_counts = Counter(all_interventions)
    drugs_str = "\n".join(f"  - {drug}: {count}" for drug, count in drug_counts.most_common(MAX_TOP_ITEMS))
    
    # Sponsor frequency
    sponsors = Counter(t.sponsor for t in trials)
    sponsors_str = "\n".join(f"  - {sponsor}: {count}" for sponsor, count in sponsors.most_common(MAX_TOP_ITEMS))
    
    # Sample titles
    sample_titles = [t.title for t in trials[:MAX_SAMPLE_TITLES]]
    titles_str = "\n".join(f"  - {title[:100]}..." if len(title) > 100 else f"  - {title}" for title in sample_titles)
    
    # Terms used
    terms_str = ", ".join(t.term for t in search_terms)
    
    return {
        "count": len(trials),
        "phases": phase_str,
        "drugs": drugs_str,
        "sponsors": sponsors_str,
        "sample_titles": titles_str,
        "terms": terms_str,
    }


def call_llm_for_review(
    target: str,
    summary: dict
) -> GapReviewResult | None:
    """Call LLM to review coverage.
    
    Args:
        target: The molecular target
        summary: Summary dict from build_summary
        
    Returns:
        GapReviewResult or None if LLM unavailable
    """
    if not OPENAI_AVAILABLE:
        console.print("  [yellow]OpenAI not installed, skipping LLM review[/yellow]")
        return GapReviewResult(
            coverage_assessment="Unknown",
            suggested_terms=[],
            reasoning="OpenAI library not installed"
        )
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        console.print("  [yellow]OPENAI_API_KEY not set, skipping LLM review[/yellow]")
        return GapReviewResult(
            coverage_assessment="Unknown",
            suggested_terms=[],
            reasoning="OPENAI_API_KEY environment variable not set"
        )
    
    prompt = GAP_REVIEW_PROMPT.format(
        target=target,
        terms=summary["terms"],
        count=summary["count"],
        phases=summary["phases"],
        drugs=summary["drugs"],
        sponsors=summary["sponsors"],
        sample_titles=summary["sample_titles"],
    )
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=DEFAULT_LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a clinical trial research analyst. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=MAX_LLM_TOKENS,
        )
        
        content = response.choices[0].message.content
        
        # Check for empty response
        if content is None:
            raise ValueError("LLM returned empty content")
        
        # Parse JSON response
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        result_data = json.loads(content.strip())
        
        return GapReviewResult(
            coverage_assessment=result_data.get("coverage_assessment", "Unknown"),
            suggested_terms=result_data.get("suggested_terms", [])[:MAX_SUGGESTED_TERMS],
            reasoning=result_data.get("reasoning", "")
        )
        
    except Exception as e:
        console.print(f"  [yellow]LLM review failed: {e}[/yellow]")
        return GapReviewResult(
            coverage_assessment="Error",
            suggested_terms=[],
            reasoning=f"LLM call failed: {str(e)}"
        )


def fetch_additional_trials(
    suggested_terms: list[str],
    existing_nct_ids: set[str]
) -> list[Trial]:
    """Fetch additional trials based on LLM suggestions.
    
    Args:
        suggested_terms: Terms suggested by LLM
        existing_nct_ids: NCT IDs already fetched
        
    Returns:
        List of new trials
    """
    if not suggested_terms:
        return []
    
    console.print(f"  [dim]Searching for: {', '.join(suggested_terms)}[/dim]")
    
    # Create SearchTerm objects
    new_terms = [
        SearchTerm(term=term, provenance=Provenance.LLM, confidence=LLM_SUGGESTED_CONFIDENCE)
        for term in suggested_terms
    ]
    
    # Discover new trials (now returns full records)
    raw_trials = discover_trials(new_terms, max_results=ADDITIONAL_TRIALS_MAX_RESULTS)
    
    # Filter out existing trials by NCT ID
    truly_new_trials = [
        trial for trial in raw_trials
        if get_nct_id(trial) not in existing_nct_ids
    ]
    
    if not truly_new_trials:
        console.print("  [dim]No new trials found from suggested terms[/dim]")
        return []
    
    console.print(f"  [dim]Found {len(truly_new_trials)} new trials[/dim]")
    
    # Normalize and validate
    normalized = normalize_trials(truly_new_trials)
    validated = validate_trials(normalized)
    
    return validated


def review_coverage(
    target: str,
    search_terms: list[SearchTerm],
    trials: list[Trial]
) -> tuple[GapReviewResult, list[Trial]]:
    """Review trial coverage and optionally fetch additional trials.
    
    Args:
        target: The molecular target
        search_terms: Search terms used
        trials: Current trial list
        
    Returns:
        Tuple of (GapReviewResult, additional_trials)
    """
    # Build summary
    summary = build_summary(trials, search_terms)
    
    # Call LLM
    result = call_llm_for_review(target, summary)
    
    if result is None:
        return (GapReviewResult(
            coverage_assessment="Skipped",
            suggested_terms=[],
            reasoning="LLM review was skipped"
        ), [])
    
    console.print(f"  [dim]LLM assessment: {result.coverage_assessment}[/dim]")
    if result.reasoning:
        reasoning_display = result.reasoning
        if len(reasoning_display) > REASONING_TRUNCATE_LENGTH:
            reasoning_display = reasoning_display[:REASONING_TRUNCATE_LENGTH] + "..."
        console.print(f"  [dim]Reasoning: {reasoning_display}[/dim]")
    
    # If gaps detected, fetch additional trials
    additional_trials = []
    if result.coverage_assessment == "Gaps Detected" and result.suggested_terms:
        console.print(f"  [cyan]LLM suggested terms: {', '.join(result.suggested_terms)}[/cyan]")
        existing_ids = {t.nct_id for t in trials}
        additional_trials = fetch_additional_trials(result.suggested_terms, existing_ids)
    
    return (result, additional_trials)

