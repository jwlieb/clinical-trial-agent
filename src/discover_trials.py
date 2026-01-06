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
    patient_age: int | None = None,
    patient_sex: str | None = None,
) -> list[dict[str, Any]]:
    """Search ClinicalTrials.gov for trials matching a query.
    
    Args:
        query: Search term
        max_results: Maximum number of results to return
        recruiting_only: If True, only return recruiting trials
        locations: List of countries to filter by (e.g., ["United States", "Canada"])
        patient_age: Patient age in years (for age bucket filtering)
        patient_sex: Patient sex ("male" or "female") for sex filtering
        
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
    
    # Build aggregation filters for demographic filtering
    agg_filters = []
    
    # Sex filter
    if patient_sex:
        sex_code = "f" if patient_sex.lower() == "female" else "m"
        agg_filters.append(f"sex:{sex_code}")
    
    # Age bucket filter (API uses coarse buckets, not exact ages)
    if patient_age is not None:
        if patient_age < 18:
            agg_filters.append("ages:child")
        elif patient_age >= 65:
            agg_filters.append("ages:older")
        else:
            agg_filters.append("ages:adult")
    
    # Add aggregation filters to params if any were built
    if agg_filters:
        params["aggFilters"] = ",".join(agg_filters)
    
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
    patient_age: int | None = None,
    patient_sex: str | None = None,
) -> list[dict[str, Any]]:
    """Discover trials for all search terms.
    
    Args:
        search_terms: List of search terms with provenance
        max_results: Maximum total trials to return
        recruiting_only: If True, only return recruiting trials
        locations: List of countries to filter by
        patient_age: Patient age in years (for age bucket filtering at API level)
        patient_sex: Patient sex ("male" or "female") for sex filtering at API level
        
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
    if patient_age is not None:
        age_bucket = "child" if patient_age < 18 else ("older" if patient_age >= 65 else "adult")
        console.print(f"  [dim]Filtering: age bucket = {age_bucket} (patient age {patient_age})[/dim]")
    if patient_sex:
        console.print(f"  [dim]Filtering: sex = {patient_sex}[/dim]")
    
    for term in search_terms:
        
        trials = search_clinicaltrials(
            term.term,
            max_results=50,
            recruiting_only=recruiting_only,
            locations=locations,
            patient_age=patient_age,
            patient_sex=patient_sex,
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

