"""Trial discovery: search ClinicalTrials.gov for relevant trials."""

import time

import requests
from rich.console import Console

from src.schemas import SearchTerm

console = Console()

CLINICALTRIALS_API = "https://clinicaltrials.gov/api/v2/studies"


def search_clinicaltrials(
    query: str,
    max_results: int = 50
) -> list[str]:
    """Search ClinicalTrials.gov for trials matching a query.
    
    Args:
        query: Search term
        max_results: Maximum number of results to return
        
    Returns:
        List of NCT IDs
    """
    nct_ids: list[str] = []
    page_size = min(max_results, 100)  # API max is 100 per page
    
    params = {
        "query.term": query,
        "pageSize": page_size,
        "format": "json",
        "fields": "NCTId",
    }
    
    try:
        response = requests.get(
            CLINICALTRIALS_API,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        studies = data.get("studies", [])
        for study in studies:
            protocol = study.get("protocolSection", {})
            id_module = protocol.get("identificationModule", {})
            nct_id = id_module.get("nctId")
            if nct_id:
                nct_ids.append(nct_id)
                
    except requests.RequestException as e:
        console.print(f"  [yellow]ClinicalTrials.gov API error for '{query}': {e}[/yellow]")
    except (KeyError, TypeError) as e:
        console.print(f"  [yellow]Parsing error for '{query}': {e}[/yellow]")
    
    return nct_ids


def discover_trials(
    search_terms: list[SearchTerm],
    max_results: int = 100
) -> list[str]:
    """Discover trials for all search terms.
    
    Args:
        search_terms: List of search terms with provenance
        max_results: Maximum total trials to return
        
    Returns:
        Deduplicated list of NCT IDs
    """
    all_nct_ids: set[str] = set()
    term_to_trials: dict[str, list[str]] = {}
    
    for term in search_terms:
        
        nct_ids = search_clinicaltrials(term.term, max_results=50)
        term_to_trials[term.term] = nct_ids
        
        new_ids = set(nct_ids) - all_nct_ids
        if new_ids:
            console.print(f"  [dim]'{term.term}' → {len(nct_ids)} results ({len(new_ids)} new)[/dim]")
        
        all_nct_ids.update(nct_ids)
        
        # Early exit if we have enough
        if len(all_nct_ids) >= max_results:
            break
    
    # Return as sorted list for reproducibility
    result = sorted(list(all_nct_ids))[:max_results]
    return result

