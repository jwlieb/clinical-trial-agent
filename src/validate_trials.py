"""Validate normalized trial data."""

import re

from rich.console import Console

from src.schemas import Trial

console = Console()

# NCT ID pattern
NCT_PATTERN = re.compile(r"^NCT\d{8}$")

# Threshold for flagging trials with empty critical fields
CRITICAL_FIELD_THRESHOLD = 2


def validate_nct_id(nct_id: str) -> tuple[bool, str | None]:
    """Validate NCT ID format.
    
    Args:
        nct_id: The NCT ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not nct_id:
        return (False, "NCT ID is empty")
    if not NCT_PATTERN.match(nct_id):
        return (False, f"NCT ID '{nct_id}' does not match pattern NCT########")
    return (True, None)


def validate_dates(trial: Trial) -> tuple[bool, str | None]:
    """Validate date ordering.
    
    Args:
        trial: The trial to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if trial.start_date and trial.completion_date:
        if trial.start_date > trial.completion_date:
            return (False, f"Start date {trial.start_date} is after completion date {trial.completion_date}")
    return (True, None)


def validate_critical_fields(trial: Trial) -> list[str]:
    """Check for empty critical fields.
    
    Args:
        trial: The trial to validate
        
    Returns:
        List of warning messages for empty fields
    """
    warnings = []
    
    if not trial.title:
        warnings.append("Title is empty")
    if not trial.conditions:
        warnings.append("No conditions specified")
    if not trial.interventions:
        warnings.append("No interventions specified")
    if not trial.sponsor or trial.sponsor == "Unknown":
        warnings.append("Sponsor is unknown")
    
    return warnings


def validate_single_trial(trial: Trial) -> Trial:
    """Validate a single trial and set confidence flags.
    
    Args:
        trial: The trial to validate
        
    Returns:
        Trial with updated confidence flags
    """
    review_reasons = []
    
    valid, error = validate_nct_id(trial.nct_id)
    if not valid:
        review_reasons.append(error)
    
    valid, error = validate_dates(trial)
    if not valid:
        review_reasons.append(error)
    
    warnings = validate_critical_fields(trial)
    # Only flag if enough critical fields are empty
    if len(warnings) >= CRITICAL_FIELD_THRESHOLD:
        review_reasons.extend(warnings)
    
    if review_reasons:
        trial.confidence_flags.needs_review = True
        trial.confidence_flags.review_reasons = review_reasons
    
    return trial


def validate_trials(trials: list[Trial]) -> list[Trial]:
    """Validate all trials.
    
    Args:
        trials: List of trials to validate
        
    Returns:
        List of validated trials with confidence flags set
    """
    validated = []
    
    for trial in trials:
        validated_trial = validate_single_trial(trial)
        validated.append(validated_trial)
    
    flagged = sum(1 for t in validated if t.confidence_flags.needs_review)
    if flagged > 0:
        console.print(f"  [dim]{flagged} trials flagged for review[/dim]")
    
    return validated
