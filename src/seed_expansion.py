"""Seed expansion: convert a molecular target into search terms."""

from src.schemas import SearchTerm, Provenance


def generate_variant_notations(target: str) -> list[str]:
    """Generate common notation variants for a molecular target.
    
    For targets like 'KRAS G12C', generates variations in spacing/punctuation
    that researchers might use in trial registrations.
    
    Args:
        target: The molecular target (e.g., "KRAS G12C", "BRAF V600E")
        
    Returns:
        List of notation variants including the original
    """
    variants = [target]
    parts = target.split()
    
    if len(parts) == 2:
        gene, mutation = parts
        # Common notation variants for gene+mutation targets
        variants.extend([
            f"{gene}{mutation}",       # KRASG12C
            f"{gene}-{mutation}",      # KRAS-G12C
        ])
    elif len(parts) == 1:
        # Single gene name - add common prefixes/suffixes
        gene = parts[0]
        # Some genes have common alternate capitalizations
        if gene.isupper():
            variants.append(gene.capitalize())  # EGFR -> Egfr
    
    return variants


def expand_seed(target: str) -> list[SearchTerm]:
    """Expand a molecular target into a list of search terms.
    
    Generates notation variants programmatically (e.g., "KRAS G12C" -> 
    "KRASG12C", "KRAS-G12C") to catch different registration styles.
    
    Note: I initially intended to expand to associated drug names using OpenTargets,
    but removed it. ClinicalTrials.gov trials for drugs like sotorasib already mention 
    "KRAS G12C" in their conditions/eligibility, so searching for the 
    target directly finds relevant drug trials. Adding drug names as 
    search terms would add complexity, increase noise and unrelated trials, and introduce API dependencies without 
    meaningfully improving coverage.
    
    Args:
        target: The molecular target (e.g., "KRAS G12C")
        
    Returns:
        List of SearchTerms with provenance tracking
    """
    terms: list[SearchTerm] = []
    seen: set[str] = set()
    
    for variant in generate_variant_notations(target):
        if variant.lower() not in seen:
            seen.add(variant.lower())
            terms.append(SearchTerm(
                term=variant,
                provenance=Provenance.MANUAL,
                confidence=1.0
            ))
    
    return terms
