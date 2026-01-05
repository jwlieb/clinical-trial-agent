"""Trial discovery: search ClinicalTrials.gov for relevant trials."""

import time
from typing import Any

import requests
from rich.console import Console

from src.schemas import SearchTerm

console = Console()

CLINICALTRIALS_API = "https://clinicaltrials.gov/api/v2/studies"

# Recruiting statuses to filter for patient matching
RECRUITING_STATUSES = [
    "RECRUITING",
    "NOT_YET_RECRUITING",
    "ENROLLING_BY_INVITATION",
]


def search_clinicaltrials(
    query: str,
    max_results: int = 50,
    recruiting_only: bool = False,
    locations: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Search ClinicalTrials.gov for trials matching a query.
    
    Args:
        query: Search term
        max_results: Maximum number of results to return
        recruiting_only: If True, only return recruiting trials
        locations: List of countries to filter by (e.g., ["United States", "Canada"])
        
    Returns:
        List of full trial records
    """
    trials: list[dict[str, Any]] = []
    page_size = min(max_results, 100)  # API max is 100 per page
    
    params = {
        "query.term": query,
        "pageSize": page_size,
        "format": "json",
    }
    
    # Add recruiting status filter
    if recruiting_only:
        params["filter.overallStatus"] = ",".join(RECRUITING_STATUSES)
    
    # Add location filter (country-level)
    if locations:
        # ClinicalTrials.gov uses query.locn for location search
        # Format: "SEARCH[Location](country1 OR country2)"
        location_query = " OR ".join(locations)
        params["query.locn"] = location_query
    
    try:
        response = requests.get(
            CLINICALTRIALS_API,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        studies = data.get("studies", [])
        trials.extend(studies)
                
    except requests.RequestException as e:
        console.print(f"  [yellow]ClinicalTrials.gov API error for '{query}': {e}[/yellow]")
    except (KeyError, TypeError) as e:
        console.print(f"  [yellow]Parsing error for '{query}': {e}[/yellow]")
    
    return trials


def get_nct_id(trial: dict[str, Any]) -> str | None:
    """Extract NCT ID from a trial record."""
    try:
        protocol = trial.get("protocolSection", {})
        id_module = protocol.get("identificationModule", {})
        return id_module.get("nctId")
    except (KeyError, TypeError):
        return None


def discover_trials(
    search_terms: list[SearchTerm],
    max_results: int = 100,
    recruiting_only: bool = False,
    locations: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Discover trials for all search terms.
    
    Args:
        search_terms: List of search terms with provenance
        max_results: Maximum total trials to return
        recruiting_only: If True, only return recruiting trials
        locations: List of countries to filter by
        
    Returns:
        Deduplicated list of full trial records
    """
    all_trials: dict[str, dict[str, Any]] = {}  # NCT ID -> trial record
    term_to_trials: dict[str, list[str]] = {}
    
    # Log filters if applied
    if recruiting_only:
        console.print(f"  [dim]Filtering: recruiting trials only[/dim]")
    if locations:
        console.print(f"  [dim]Filtering: locations = {', '.join(locations)}[/dim]")
    
    for term in search_terms:
        
        trials = search_clinicaltrials(
            term.term,
            max_results=50,
            recruiting_only=recruiting_only,
            locations=locations,
        )
        
        # Track NCT IDs for this term
        nct_ids = []
        new_count = 0
        
        for trial in trials:
            nct_id = get_nct_id(trial)
            if nct_id:
                nct_ids.append(nct_id)
                if nct_id not in all_trials:
                    all_trials[nct_id] = trial
                    new_count += 1
        
        term_to_trials[term.term] = nct_ids
        
        if nct_ids:
            console.print(f"  [dim]'{term.term}' → {len(nct_ids)} results ({new_count} new)[/dim]")
        
        # Early exit if we have enough
        if len(all_trials) >= max_results:
            break
    
    # Return as list, sorted by NCT ID for reproducibility
    result = list(all_trials.values())
    result.sort(key=lambda t: get_nct_id(t) or "")
    return result[:max_results]

