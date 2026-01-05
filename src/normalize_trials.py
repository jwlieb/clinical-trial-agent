"""Normalize raw trial data into structured schema."""

import os
from datetime import date
from typing import Any, NamedTuple

from dateutil.parser import parse as parse_date
from rich.console import Console

from src.schemas import Trial, TrialPhase, TrialStatus, StudyType, EligibilityInfo

# Constants
DEFAULT_SPONSOR = "Unknown"
DEFAULT_NCT_ID = "UNKNOWN"
CLINICALTRIALS_BASE_URL = os.environ.get(
    "CLINICALTRIALS_BASE_URL",
    "https://clinicaltrials.gov/study/"
)

# Default console for module-level use (can be overridden in function calls)
_default_console = Console()


class NormalizationError(NamedTuple):
    """Structured error for trial normalization failures."""
    nct_id: str
    error: str


def _parse_bool(value: Any) -> bool | None:
    """Parse a boolean value that may be bool or string.
    
    Args:
        value: Boolean value or string representation
        
    Returns:
        Parsed boolean or None if not parseable
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return None


def parse_date_safe(date_str: str | None) -> date | None:
    """Safely parse a date string.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        Parsed date or None
    """
    if not date_str:
        return None
    try:
        parsed = parse_date(date_str, fuzzy=True)
        return parsed.date()
    except (ValueError, TypeError):
        return None


def extract_phase(
    phases_list: list[str] | None,
    console: Console | None = None
) -> str | None:
    """Extract and normalize the trial phase.
    
    Args:
        phases_list: List of phase strings from API (e.g., ["PHASE1", "PHASE2"])
        console: Optional console for logging (uses default if not provided)
        
    Returns:
        Normalized phase string or None
    """
    if not phases_list:
        return None
    
    # Map each phase to its canonical value (with defensive str conversion)
    mapped_phases = [
        phase_enum.value
        for phase in phases_list
        if (phase_enum := TrialPhase.from_api(str(phase))) is not None
    ]
    
    if not mapped_phases:
        return None
    
    if len(mapped_phases) == 1:
        return mapped_phases[0]
    
    # Check for known combinations
    phase_set = set(mapped_phases)
    if phase_set == {TrialPhase.PHASE_1.value, TrialPhase.PHASE_2.value}:
        return TrialPhase.PHASE_1_2.value
    if phase_set == {TrialPhase.PHASE_2.value, TrialPhase.PHASE_3.value}:
        return TrialPhase.PHASE_2_3.value
    
    # Fallback: join with slash (log unusual combinations)
    log = console or _default_console
    log.print(f"  [dim]Unusual phase combination: {mapped_phases}[/dim]")
    return "/".join(mapped_phases)


def extract_status(status_module: dict | None) -> str:
    """Extract the overall status from the status module.
    
    Args:
        status_module: Status module from API
        
    Returns:
        Status string
    """
    if not status_module:
        return TrialStatus.UNKNOWN.value
    
    overall_status = status_module.get("overallStatus", "")
    status_enum = TrialStatus.from_api(overall_status)
    
    if status_enum:
        return status_enum.value
    
    # Return original if not recognized (preserves unexpected values)
    return overall_status if overall_status else TrialStatus.UNKNOWN.value


def extract_study_type(design_module: dict | None) -> str | None:
    """Extract the study type from the design module.
    
    Args:
        design_module: Design module from API
        
    Returns:
        Study type string or None
    """
    if not design_module:
        return None
    
    study_type = design_module.get("studyType", "")
    study_type_enum = StudyType.from_api(study_type)
    
    if study_type_enum:
        return study_type_enum.value
    
    return study_type if study_type else None


def extract_enrollment(design_module: dict | None) -> int | None:
    """Extract enrollment count from the design module.
    
    Args:
        design_module: Design module from API
        
    Returns:
        Enrollment count or None
    """
    if not design_module:
        return None
    
    enrollment_info = design_module.get("enrollmentInfo", {})
    count = enrollment_info.get("count")
    
    return count if isinstance(count, int) else None


def extract_interventions(arms_module: dict | None) -> list[str]:
    """Extract intervention names from the arms/interventions module.
    
    Args:
        arms_module: ArmsInterventionsModule from API
        
    Returns:
        List of intervention names
    """
    if not arms_module:
        return []
    
    interventions = arms_module.get("interventions", [])
    return [intervention.get("name", "") for intervention in interventions if intervention.get("name")]


def extract_conditions(conditions_module: dict | None) -> list[str]:
    """Extract condition names from the conditions module.
    
    Args:
        conditions_module: ConditionsModule from API
        
    Returns:
        List of condition names
    """
    if not conditions_module:
        return []
    
    return conditions_module.get("conditions", [])


def extract_locations(locations_module: dict | None) -> list[str]:
    """Extract unique countries from locations.
    
    Args:
        locations_module: LocationsModule from API
        
    Returns:
        List of unique country names
    """
    if not locations_module:
        return []
    
    locations = locations_module.get("locations", [])
    countries = {loc.get("country", "") for loc in locations if loc.get("country")}
    
    return sorted(countries)


def extract_sponsor(sponsor_module: dict | None) -> tuple[str, list[str]]:
    """Extract lead sponsor and collaborators.
    
    Args:
        sponsor_module: SponsorCollaboratorsModule from API
        
    Returns:
        Tuple of (lead_sponsor, collaborators_list)
    """
    if not sponsor_module:
        return (DEFAULT_SPONSOR, [])
    
    lead = sponsor_module.get("leadSponsor", {}).get("name", DEFAULT_SPONSOR)
    collaborators = [
        collab.get("name", "")
        for collab in sponsor_module.get("collaborators", [])
        if collab.get("name")
    ]
    
    return (lead, collaborators)


def extract_eligibility(eligibility_module: dict | None) -> EligibilityInfo:
    """Extract eligibility information from the eligibility module.
    
    Args:
        eligibility_module: EligibilityModule from API
        
    Returns:
        EligibilityInfo object with raw text and structured fields
    """
    if not eligibility_module:
        return EligibilityInfo()
    
    return EligibilityInfo(
        raw_text=eligibility_module.get("eligibilityCriteria"),
        minimum_age=eligibility_module.get("minimumAge"),
        maximum_age=eligibility_module.get("maximumAge"),
        sex=eligibility_module.get("sex"),
        accepts_healthy_volunteers=_parse_bool(eligibility_module.get("healthyVolunteers"))
    )


def normalize_single_trial(raw_trial: dict[str, Any]) -> Trial:
    """Normalize a single raw trial record.
    
    Args:
        raw_trial: Raw trial data from API
        
    Returns:
        Normalized Trial object
    """
    protocol = raw_trial.get("protocolSection", {})
    
    # Extract modules
    id_module = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    design_module = protocol.get("designModule", {})
    conditions_module = protocol.get("conditionsModule", {})
    arms_module = protocol.get("armsInterventionsModule", {})
    sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
    contacts_module = protocol.get("contactsLocationsModule", {})
    desc_module = protocol.get("descriptionModule", {})
    eligibility_module = protocol.get("eligibilityModule", {})
    
    # Extract NCT ID
    nct_id = id_module.get("nctId", DEFAULT_NCT_ID)
    
    # Extract sponsor info
    sponsor, collaborators = extract_sponsor(sponsor_module)
    
    # Extract dates
    start_date_info = status_module.get("startDateStruct", {})
    completion_date_info = status_module.get("completionDateStruct", {})
    
    # Build trial object (confidence_flags uses default_factory)
    trial = Trial(
        nct_id=nct_id,
        title=id_module.get("officialTitle", id_module.get("briefTitle", "")),
        phase=extract_phase(design_module.get("phases", [])),
        status=extract_status(status_module),
        study_type=extract_study_type(design_module),
        conditions=extract_conditions(conditions_module),
        interventions=extract_interventions(arms_module),
        molecular_targets=None,
        sponsor=sponsor,
        collaborators=collaborators,
        enrollment_count=extract_enrollment(design_module),
        start_date=parse_date_safe(start_date_info.get("date")),
        completion_date=parse_date_safe(completion_date_info.get("date")),
        locations=extract_locations(contacts_module),
        summary=desc_module.get("briefSummary", ""),
        source_url=f"{CLINICALTRIALS_BASE_URL}{nct_id}",
        eligibility=extract_eligibility(eligibility_module),
    )
    
    return trial


def normalize_trials(
    raw_trials: list[dict[str, Any]],
    console: Console | None = None
) -> list[Trial]:
    """Normalize all raw trial records.
    
    Args:
        raw_trials: List of raw trial data from API
        console: Optional console for logging (uses default if not provided)
        
    Returns:
        List of normalized Trial objects
    """
    log = console or _default_console
    trials = []
    errors: list[NormalizationError] = []
    
    for raw in raw_trials:
        try:
            trial = normalize_single_trial(raw)
            trials.append(trial)
        except Exception as e:
            nct_id = raw.get("protocolSection", {}).get("identificationModule", {}).get("nctId", DEFAULT_NCT_ID)
            errors.append(NormalizationError(nct_id=nct_id, error=str(e)))
    
    # Log errors at the end (batch reporting)
    for err in errors:
        log.print(f"  [yellow]Failed to normalize {err.nct_id}: {err.error}[/yellow]")
    
    return trials
