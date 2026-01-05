"""Extract search terms from patient profile using LLM."""

import json
import os

from rich.console import Console

from src.schemas import PatientProfile, SearchTerm, Provenance
from src.seed_expansion import generate_variant_notations

console = Console()

DEFAULT_LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
MAX_LLM_TOKENS = 500

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


TERM_EXTRACTION_PROMPT = """You are extracting clinical trial search terms from a patient profile.

## Patient Profile
- Cancer type: {cancer_type}
- Biomarkers/mutations: {biomarkers}
- Description: {description}

## Task
Extract search terms that would find relevant clinical trials for this patient.

Focus on:
1. The specific cancer type and its common abbreviations
2. Biomarkers/mutations (these are critical for targeted therapy trials)
3. Any specific drugs or drug classes mentioned in prior treatments (to find trials that allow/exclude them)

## Response Format
Return a JSON object:
{{
    "primary_terms": ["most important terms - usually biomarker + cancer type combinations"],
    "cancer_terms": ["cancer type and common synonyms/abbreviations"],
    "biomarker_terms": ["biomarker/mutation variations"],
    "reasoning": "brief explanation of term choices"
}}

Rules:
- Primary terms should be specific combinations like "KRAS G12C NSCLC"
- Include common abbreviations (e.g., NSCLC for non-small cell lung cancer)
- For biomarkers, include the exact notation (e.g., "KRAS G12C", "BRAF V600E")
- Don't include overly generic terms like "cancer" or "clinical trial"
- Maximum 3 primary terms, 3 cancer terms, 3 biomarker terms
"""


def extract_terms_with_llm(patient: PatientProfile) -> dict:
    """Use LLM to extract search terms from patient profile.
    
    Args:
        patient: The patient profile
        
    Returns:
        Dictionary with extracted terms
    """
    if not OPENAI_AVAILABLE:
        console.print("[yellow]OpenAI not available, using fallback term extraction[/yellow]")
        return _fallback_extraction(patient)
    
    client = OpenAI()
    
    prompt = TERM_EXTRACTION_PROMPT.format(
        cancer_type=patient.cancer_type or "Not specified",
        biomarkers=", ".join(patient.biomarkers) if patient.biomarkers else "Not specified",
        description=patient.description
    )
    
    try:
        response = client.chat.completions.create(
            model=DEFAULT_LLM_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=MAX_LLM_TOKENS,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
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

