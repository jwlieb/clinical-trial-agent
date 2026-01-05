"""Seed expansion: convert a molecular target into search terms."""

import requests
from rich.console import Console

from src.schemas import SearchTerm, Provenance

console = Console()

OPENTARGETS_ENDPOINT = "https://api.platform.opentargets.org/api/v4/graphql"


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


def get_opentargets_drugs(target: str) -> list[SearchTerm]:
    """Query OpenTargets for drugs associated with a target.
    
    Args:
        target: The molecular target name (e.g., "KRAS")
        
    Returns:
        List of SearchTerms with drug names and synonyms
    """
    # Extract the gene name from targets like "KRAS G12C"
    gene_name = target.split()[0].upper()
    
    # GraphQL query to get associated drugs
    query = """
    query DrugsByTarget($ensemblId: String!) {
        target(ensemblId: $ensemblId) {
            id
            approvedSymbol
            knownDrugs {
                rows {
                    drug {
                        id
                        name
                        synonyms
                        drugType
                        mechanismsOfAction {
                            rows {
                                mechanismOfAction
                            }
                        }
                    }
                    phase
                }
            }
        }
    }
    """
    
    # First, we need to get the Ensembl ID for the gene
    search_query = """
    query SearchTarget($queryString: String!) {
        search(queryString: $queryString, entityNames: ["target"], page: {size: 5, index: 0}) {
            hits {
                id
                name
                entity
            }
        }
    }
    """
    
    terms: list[SearchTerm] = []
    
    try:
        # Search for the target to get Ensembl ID
        response = requests.post(
            OPENTARGETS_ENDPOINT,
            json={"query": search_query, "variables": {"queryString": gene_name}},
            timeout=30
        )
        response.raise_for_status()
        search_data = response.json()
        
        hits = search_data.get("data", {}).get("search", {}).get("hits", [])
        if not hits:
            console.print(f"  [yellow]No OpenTargets results for {gene_name}[/yellow]")
            return terms
        
        # Get the first matching target
        ensembl_id = hits[0]["id"]
        
        # Now query for drugs
        response = requests.post(
            OPENTARGETS_ENDPOINT,
            json={"query": query, "variables": {"ensemblId": ensembl_id}},
            timeout=30
        )
        response.raise_for_status()
        drug_data = response.json()
        
        target_data = drug_data.get("data", {}).get("target", {})
        if not target_data:
            return terms
        
        known_drugs = target_data.get("knownDrugs", {}).get("rows", [])
        
        seen_names: set[str] = set()
        for row in known_drugs:
            drug = row.get("drug", {})
            drug_name = drug.get("name", "")
            
            if drug_name and drug_name.lower() not in seen_names:
                seen_names.add(drug_name.lower())
                terms.append(SearchTerm(
                    term=drug_name,
                    provenance=Provenance.OPENTARGETS,
                    confidence=0.9
                ))
            
            # Add synonyms
            for synonym in drug.get("synonyms", [])[:3]:  # Limit synonyms
                if synonym and synonym.lower() not in seen_names:
                    seen_names.add(synonym.lower())
                    terms.append(SearchTerm(
                        term=synonym,
                        provenance=Provenance.OPENTARGETS,
                        confidence=0.7
                    ))
        
        console.print(f"  [dim]OpenTargets returned {len(terms)} drug terms[/dim]")
        
    except requests.RequestException as e:
        console.print(f"  [yellow]OpenTargets API error: {e}[/yellow]")
    except (KeyError, TypeError) as e:
        console.print(f"  [yellow]OpenTargets parsing error: {e}[/yellow]")
    
    return terms


def expand_seed(target: str) -> list[SearchTerm]:
    """Expand a molecular target into a list of search terms.
    
    Generates search terms from:
    1. Programmatic notation variants (e.g., "KRAS G12C" -> "KRASG12C", "KRAS-G12C")
    2. OpenTargets drug associations (dynamically fetched)
    
    Args:
        target: The molecular target (e.g., "KRAS G12C")
        
    Returns:
        List of SearchTerms with provenance tracking
    """
    terms: list[SearchTerm] = []
    seen: set[str] = set()
    
    # Add programmatic notation variants
    for variant in generate_variant_notations(target):
        if variant.lower() not in seen:
            seen.add(variant.lower())
            terms.append(SearchTerm(
                term=variant,
                provenance=Provenance.MANUAL,
                confidence=1.0
            ))
    
    # Query OpenTargets for associated drugs
    opentargets_terms = get_opentargets_drugs(target)
    for ot_term in opentargets_terms:
        if ot_term.term.lower() not in seen:
            seen.add(ot_term.term.lower())
            terms.append(ot_term)
    
    return terms

