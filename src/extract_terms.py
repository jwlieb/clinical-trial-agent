"""Extract search terms from patient profile using LLM."""

import json
import os

from rich.console import Console

from src.schemas import PatientProfile, SearchTerm, Provenance
from src.seed_expansion import generate_variant_notations

console = Console()

DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")
MAX_LLM_TOKENS = 800  # Increased for 70B model
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")  # "openai" or "groq"

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


TERM_EXTRACTION_PROMPT = """You are extracting clinical trial search terms from a patient profile.

## Patient Profile
- Cancer type: {cancer_type}
- Biomarkers/mutations: {biomarkers}
- Description: {description}

## Task
Extract search terms that would find relevant clinical trials for this patient.

## Critical Rules
- ONLY include biomarkers that are EXPLICITLY listed in the patient profile above
- Do NOT suggest related or similar biomarkers (e.g., if patient has KRAS G12C, do NOT add BRAF V600E, EGFR, or other mutations)
- Do NOT invent or assume biomarkers not explicitly stated in the profile
- Primary terms should combine the exact biomarker with cancer type
- Include common abbreviations for cancer type (e.g., NSCLC for non-small cell lung cancer)

## Response Format
Return a JSON object:
{{
    "primary_terms": ["biomarker + cancer type combinations from profile only"],
    "cancer_terms": ["cancer type and common synonyms/abbreviations"],
    "biomarker_terms": ["exact biomarker variations from profile only"],
    "reasoning": "brief explanation of term choices"
}}

## Examples of CORRECT behavior:
- Patient has "KRAS G12C" → biomarker_terms: ["KRAS G12C", "KRAS-G12C", "KRAS p.G12C"]
- Patient has "NSCLC" → cancer_terms: ["NSCLC", "non-small cell lung cancer", "lung adenocarcinoma"]

## Examples of INCORRECT behavior (DO NOT DO THIS):
- Patient has "KRAS G12C" → DO NOT add "BRAF V600E", "EGFR", "ALK", or any other mutations
- Patient has lung cancer → DO NOT add breast cancer, colorectal cancer, or other cancer types

Maximum 3 primary terms, 3 cancer terms, 3 biomarker terms.
"""


def extract_terms_with_llm(patient: PatientProfile) -> dict:
    """Use LLM to extract search terms from patient profile.
    
    Args:
        patient: The patient profile
        
    Returns:
        Dictionary with extracted terms
    """
    if not LLM_AVAILABLE:
        console.print("[yellow]LLM client not available, using fallback term extraction[/yellow]")
        return _fallback_extraction(patient)
    
    api_key = os.environ.get("GROQ_API_KEY" if LLM_PROVIDER == "groq" else "OPENAI_API_KEY")
    if not api_key:
        console.print(f"[yellow]{'GROQ_API_KEY' if LLM_PROVIDER == 'groq' else 'OPENAI_API_KEY'} not set, using fallback[/yellow]")
        return _fallback_extraction(patient)
    
    client = LLM_CLIENT(api_key=api_key)
    
    prompt = TERM_EXTRACTION_PROMPT.format(
        cancer_type=patient.cancer_type or "Not specified",
        biomarkers=", ".join(patient.biomarkers) if patient.biomarkers else "Not specified",
        description=patient.description
    )
    
    try:
        # OpenAI uses max_completion_tokens, Groq uses max_tokens
        token_param = "max_completion_tokens" if LLM_PROVIDER == "openai" else "max_tokens"
        
        # Build params - some models don't support temperature
        params = {
            "model": DEFAULT_LLM_MODEL,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that extracts clinical trial search terms. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            token_param: MAX_LLM_TOKENS,
        }
        # OpenAI-specific settings
        if LLM_PROVIDER == "openai":
            params["response_format"] = {"type": "json_object"}
        else:
            params["temperature"] = 0
        
        response = client.chat.completions.create(**params)
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM returned empty response")
        
        # Handle potential markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        content = content.strip()
        if not content:
            raise ValueError("LLM returned empty content after parsing")
        
        result = json.loads(content)
        # Validate expected keys exist with defaults
        return {
            "primary_terms": result.get("primary_terms", []),
            "cancer_terms": result.get("cancer_terms", []),
            "biomarker_terms": result.get("biomarker_terms", []),
            "reasoning": result.get("reasoning", ""),
        }
        
    except Exception as e:
        console.print(f"[yellow]LLM extraction failed: {e}, using fallback[/yellow]")
        return _fallback_extraction(patient)


def _fallback_extraction(patient: PatientProfile) -> dict:
    """Fallback term extraction when LLM is not available.
    
    Args:
        patient: The patient profile
        
    Returns:
        Dictionary with extracted terms from structured fields
    """
    primary_terms = []
    cancer_terms = []
    biomarker_terms = []
    
    # Add cancer type if available
    if patient.cancer_type:
        cancer_terms.append(patient.cancer_type)
    
    # Add biomarkers
    for biomarker in patient.biomarkers:
        biomarker_terms.append(biomarker)
        
        # Create primary term combining biomarker + cancer type
        if patient.cancer_type:
            primary_terms.append(f"{biomarker} {patient.cancer_type}")
    
    return {
        "primary_terms": primary_terms[:3],
        "cancer_terms": cancer_terms[:3],
        "biomarker_terms": biomarker_terms[:3],
        "reasoning": "Fallback extraction from structured fields"
    }


def extract_search_terms(patient: PatientProfile) -> list[SearchTerm]:
    """Extract search terms from a patient profile.
    
    Combines LLM-based extraction with programmatic variant generation.
    
    Args:
        patient: The patient profile
        
    Returns:
        List of SearchTerms with provenance tracking
    """
    terms: list[SearchTerm] = []
    seen: set[str] = set()
    
    def add_term(term: str, provenance: Provenance, confidence: float = 1.0) -> None:
        """Add a term if not already seen."""
        term = term.strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            terms.append(SearchTerm(
                term=term,
                provenance=provenance,
                confidence=confidence
            ))
    
    # First add structured fields directly
    for biomarker in patient.biomarkers:
        add_term(biomarker, Provenance.MANUAL, confidence=1.0)
        # Generate variants for biomarkers
        for variant in generate_variant_notations(biomarker):
            add_term(variant, Provenance.MANUAL, confidence=0.95)
    
    if patient.cancer_type:
        add_term(patient.cancer_type, Provenance.MANUAL, confidence=1.0)
    
    # Combine biomarker + cancer type for targeted searches
    for biomarker in patient.biomarkers:
        if patient.cancer_type:
            add_term(f"{biomarker} {patient.cancer_type}", Provenance.MANUAL, confidence=1.0)
    
    # Then use LLM to extract additional terms
    extraction = extract_terms_with_llm(patient)
    
    for term in extraction.get("primary_terms", []):
        add_term(term, Provenance.LLM, confidence=0.9)
        # Generate variants for primary terms
        for variant in generate_variant_notations(term):
            add_term(variant, Provenance.LLM, confidence=0.85)
    
    # Cancer terms don't get variants - names are standardized (e.g., "NSCLC", "lung cancer")
    for term in extraction.get("cancer_terms", []):
        add_term(term, Provenance.LLM, confidence=0.85)
    
    for term in extraction.get("biomarker_terms", []):
        add_term(term, Provenance.LLM, confidence=0.9)
        # Generate variants for biomarker terms
        for variant in generate_variant_notations(term):
            add_term(variant, Provenance.LLM, confidence=0.85)
    
    if "reasoning" in extraction:
        console.print(f"  [dim]Term extraction: {extraction['reasoning']}[/dim]")
    
    return terms

