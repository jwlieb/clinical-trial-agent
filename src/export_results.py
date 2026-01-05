"""Export trial results in various formats."""

import csv
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from src.schemas import Trial, SearchTerm, PatientProfile, MatchResult

console = Console()


def trial_to_dict(trial: Trial) -> dict[str, Any]:
    """Convert a Trial to a JSON-serializable dict.
    
    Args:
        trial: The trial to convert
        
    Returns:
        Dict representation
    """
    return {
        "nct_id": trial.nct_id,
        "title": trial.title,
        "phase": trial.phase,
        "status": trial.status,
        "study_type": trial.study_type,
        "conditions": trial.conditions,
        "interventions": trial.interventions,
        "molecular_targets": trial.molecular_targets,
        "sponsor": trial.sponsor,
        "collaborators": trial.collaborators,
        "enrollment_count": trial.enrollment_count,
        "start_date": trial.start_date.isoformat() if trial.start_date else None,
        "completion_date": trial.completion_date.isoformat() if trial.completion_date else None,
        "locations": trial.locations,
        "summary": trial.summary,
        "source_url": trial.source_url,
        "eligibility": {
            "raw_text": trial.eligibility.raw_text,
            "minimum_age": trial.eligibility.minimum_age,
            "maximum_age": trial.eligibility.maximum_age,
            "sex": trial.eligibility.sex,
            "accepts_healthy_volunteers": trial.eligibility.accepts_healthy_volunteers,
        },
        "confidence_flags": {
            "needs_review": trial.confidence_flags.needs_review,
            "review_reasons": trial.confidence_flags.review_reasons
        }
    }


def export_json(trials: list[Trial], output_path: Path) -> None:
    """Export trials to JSON format.
    
    Args:
        trials: List of trials to export
        output_path: Path to output JSON file
        
    Raises:
        IOError: If the file cannot be written
    """
    data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "trial_count": len(trials),
            "flagged_for_review": sum(1 for t in trials if t.confidence_flags.needs_review)
        },
        "trials": [trial_to_dict(t) for t in trials]
    }
    
    try:
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        console.print(f"  [dim]Wrote {output_path}[/dim]")
    except IOError as e:
        console.print(f"  [red]Error writing {output_path}: {e}[/red]")
        raise


def export_csv(trials: list[Trial], output_path: Path) -> None:
    """Export trials to CSV format (flat view).
    
    Args:
        trials: List of trials to export
        output_path: Path to output CSV file
        
    Raises:
        IOError: If the file cannot be written
    """
    fieldnames = [
        "nct_id",
        "title", 
        "phase",
        "status",
        "study_type",
        "conditions",
        "interventions",
        "molecular_targets",
        "sponsor",
        "collaborators",
        "enrollment_count",
        "start_date",
        "completion_date",
        "locations",
        "needs_review",
        "source_url"
    ]
    
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for trial in trials:
                writer.writerow({
                    "nct_id": trial.nct_id,
                    "title": trial.title,
                    "phase": trial.phase or "",
                    "status": trial.status,
                    "study_type": trial.study_type or "",
                    "conditions": "; ".join(trial.conditions),
                    "interventions": "; ".join(trial.interventions),
                    "molecular_targets": "; ".join(trial.molecular_targets) if trial.molecular_targets else "",
                    "sponsor": trial.sponsor,
                    "collaborators": "; ".join(trial.collaborators),
                    "enrollment_count": trial.enrollment_count if trial.enrollment_count else "",
                    "start_date": trial.start_date.isoformat() if trial.start_date else "",
                    "completion_date": trial.completion_date.isoformat() if trial.completion_date else "",
                    "locations": "; ".join(trial.locations),
                    "needs_review": "Yes" if trial.confidence_flags.needs_review else "No",
                    "source_url": trial.source_url
                })
        console.print(f"  [dim]Wrote {output_path}[/dim]")
    except IOError as e:
        console.print(f"  [red]Error writing {output_path}: {e}[/red]")
        raise


def generate_landscape_report(
    trials: list[Trial],
    search_terms: list[SearchTerm],
    target: str
) -> str:
    """Generate a markdown landscape report.
    
    Args:
        trials: List of trials
        search_terms: Search terms used
        target: The molecular target
        
    Returns:
        Markdown string
    """
    lines = []
    trial_count = len(trials)
    
    # Header
    lines.append(f"# Clinical Trial Landscape: {target}")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Trials**: {trial_count}")
    lines.append(f"- **Flagged for Review**: {sum(1 for t in trials if t.confidence_flags.needs_review)}")
    lines.append(f"- **Search Terms Used**: {len(search_terms)}")
    lines.append("")
    
    # Handle empty trials case
    if trial_count == 0:
        lines.append("*No trials found matching the search criteria.*")
        lines.append("")
        
        # Still show search term provenance even with no trials
        lines.append("## Search Term Provenance")
        lines.append("")
        lines.append("| Term | Source | Confidence |")
        lines.append("|------|--------|------------|")
        for term in search_terms:
            lines.append(f"| {term.term} | {term.provenance.value} | {term.confidence:.1f} |")
        lines.append("")
        
        return "\n".join(lines)
    
    # Phase distribution
    lines.append("## Phase Distribution")
    lines.append("")
    lines.append("| Phase | Count | Distribution |")
    lines.append("|-------|-------|--------------|")
    phases = Counter(t.phase or "Unknown" for t in trials)
    for phase, count in sorted(phases.items(), key=lambda x: x[1], reverse=True):
        pct = count / trial_count * 100
        bar = "█" * int(pct / 5)
        lines.append(f"| {phase} | {count} | {bar} {pct:.1f}% |")
    lines.append("")
    
    # Status distribution
    lines.append("## Status Distribution")
    lines.append("")
    statuses = Counter(t.status for t in trials)
    for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True):
        pct = count / trial_count * 100
        lines.append(f"- **{status}**: {count} ({pct:.1f}%)")
    lines.append("")
    
    # Top sponsors
    lines.append("## Top Sponsors")
    lines.append("")
    sponsors = Counter(t.sponsor for t in trials)
    lines.append("| Sponsor | Trial Count |")
    lines.append("|---------|-------------|")
    for sponsor, count in sponsors.most_common(15):
        lines.append(f"| {sponsor[:50]} | {count} |")
    lines.append("")
    
    # Drug/Intervention frequency
    lines.append("## Interventions")
    lines.append("")
    all_interventions = []
    for t in trials:
        all_interventions.extend(t.interventions)
    drug_counts = Counter(all_interventions)
    lines.append("| Intervention | Occurrences |")
    lines.append("|--------------|-------------|")
    for drug, count in drug_counts.most_common(20):
        lines.append(f"| {drug[:50]} | {count} |")
    lines.append("")
    
    # Geographic distribution
    lines.append("## Geographic Distribution")
    lines.append("")
    all_locations = []
    for t in trials:
        all_locations.extend(t.locations)
    location_counts = Counter(all_locations)
    lines.append("| Country | Trial Count |")
    lines.append("|---------|-------------|")
    for location, count in location_counts.most_common(15):
        lines.append(f"| {location} | {count} |")
    lines.append("")
    
    # Search term provenance
    lines.append("## Search Term Provenance")
    lines.append("")
    lines.append("| Term | Source | Confidence |")
    lines.append("|------|--------|------------|")
    for term in search_terms:
        lines.append(f"| {term.term} | {term.provenance.value} | {term.confidence:.1f} |")
    lines.append("")
    
    # Trials flagged for review
    flagged = [t for t in trials if t.confidence_flags.needs_review]
    if flagged:
        lines.append("## Trials Flagged for Review")
        lines.append("")
        lines.append("| NCT ID | Title | Reasons |")
        lines.append("|--------|-------|---------|")
        for t in flagged[:20]:  # Limit to 20
            reasons = "; ".join(t.confidence_flags.review_reasons)
            title_short = t.title[:40] + "..." if len(t.title) > 40 else t.title
            lines.append(f"| [{t.nct_id}]({t.source_url}) | {title_short} | {reasons} |")
        lines.append("")
    
    # All trials list
    lines.append("## All Trials")
    lines.append("")
    lines.append("| NCT ID | Phase | Status | Sponsor | Title |")
    lines.append("|--------|-------|--------|---------|-------|")
    for t in sorted(trials, key=lambda x: x.start_date or date.min, reverse=True)[:50]:
        title_short = t.title[:35] + "..." if len(t.title) > 35 else t.title
        sponsor_short = t.sponsor[:20] + "..." if len(t.sponsor) > 20 else t.sponsor
        lines.append(f"| [{t.nct_id}]({t.source_url}) | {t.phase or 'N/A'} | {t.status} | {sponsor_short} | {title_short} |")
    
    if len(trials) > 50:
        lines.append("")
        lines.append(f"*... and {len(trials) - 50} more trials (see trials.csv for full list)*")
    
    lines.append("")
    
    return "\n".join(lines)


def export_landscape(
    trials: list[Trial],
    search_terms: list[SearchTerm],
    target: str,
    output_path: Path
) -> None:
    """Export landscape markdown report.
    
    Args:
        trials: List of trials
        search_terms: Search terms used
        target: The molecular target
        output_path: Path to output markdown file
        
    Raises:
        IOError: If the file cannot be written
    """
    report = generate_landscape_report(trials, search_terms, target)
    
    try:
        with open(output_path, "w") as f:
            f.write(report)
        console.print(f"  [dim]Wrote {output_path}[/dim]")
    except IOError as e:
        console.print(f"  [red]Error writing {output_path}: {e}[/red]")
        raise


def export_results(
    trials: list[Trial],
    search_terms: list[SearchTerm],
    target: str,
    output_dir: Path
) -> None:
    """Export all result formats.
    
    Args:
        trials: List of trials
        search_terms: Search terms used
        target: The molecular target
        output_dir: Output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Export JSON
    export_json(trials, output_dir / "trials.json")
    
    # Export CSV
    export_csv(trials, output_dir / "trials.csv")
    
    # Export landscape report
    export_landscape(trials, search_terms, target, output_dir / "landscape.md")


def generate_match_report(
    patient: PatientProfile,
    results: list[MatchResult],
    search_terms: list[SearchTerm],
) -> str:
    """Generate a markdown patient-trial match report.
    
    Args:
        patient: The patient profile
        results: List of match results
        search_terms: Search terms used
        
    Returns:
        Markdown string
    """
    lines = []
    
    # Header
    lines.append("# Patient-Trial Match Report")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append("")
    
    # Patient Profile
    lines.append("## Patient Profile")
    lines.append("")
    if patient.age:
        lines.append(f"- **Age**: {patient.age}")
    if patient.sex:
        lines.append(f"- **Sex**: {patient.sex.capitalize()}")
    if patient.cancer_type:
        lines.append(f"- **Cancer Type**: {patient.cancer_type}")
    if patient.biomarkers:
        lines.append(f"- **Biomarkers**: {', '.join(patient.biomarkers)}")
    lines.append("")
    lines.append("**Clinical Description**:")
    lines.append(f"> {patient.description}")
    lines.append("")
    
    if patient.phase_preference:
        lines.append(f"- **Phase Preference**: {', '.join(patient.phase_preference)}")
    if patient.location_preference:
        lines.append(f"- **Location Preference**: {', '.join(patient.location_preference)}")
    lines.append("")
    
    # Search Summary
    lines.append("## Search Summary")
    lines.append("")
    lines.append(f"- **Search terms used**: {len(search_terms)}")
    lines.append(f"- **Total trials evaluated**: {len(results)}")
    
    stage_counts = {"fast_filter": 0, "llm_scored": 0}
    for r in results:
        stage_counts[r.filter_stage] = stage_counts.get(r.filter_stage, 0) + 1
    
    lines.append(f"- **Excluded by fast filter**: {stage_counts.get('fast_filter', 0)}")
    lines.append(f"- **LLM scored**: {stage_counts.get('llm_scored', 0)}")
    lines.append("")
    
    # Results by likelihood
    for likelihood in ["HIGH", "MEDIUM", "LOW"]:
        likelihood_results = [r for r in results if r.match_likelihood.value == likelihood]
        if likelihood_results:
            emoji = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🟠"}.get(likelihood, "")
            lines.append(f"## {emoji} {likelihood} Likelihood ({len(likelihood_results)} trials)")
            lines.append("")
            
            for r in likelihood_results:
                lines.append(f"### [{r.nct_id}](https://clinicaltrials.gov/study/{r.nct_id})")
                lines.append("")
                lines.append(f"**{r.title}**")
                lines.append("")
                lines.append(f"- **Sponsor**: {r.sponsor}")
                lines.append(f"- **Phase**: {r.phase or 'N/A'}")
                lines.append(f"- **Status**: {r.status}")
                lines.append(f"- **Confidence**: {r.confidence:.0%}")
                lines.append("")
                
                if r.supporting_factors:
                    lines.append("**✓ Supporting Factors:**")
                    for factor in r.supporting_factors:
                        lines.append(f"- {factor}")
                    lines.append("")
                
                if r.conflicts:
                    lines.append("**✗ Potential Conflicts:**")
                    for conflict in r.conflicts:
                        lines.append(f"- {conflict}")
                    lines.append("")
                
                if r.uncertainties:
                    lines.append("**? Uncertainties:**")
                    for uncertainty in r.uncertainties:
                        lines.append(f"- {uncertainty}")
                    lines.append("")
                
                if r.reasoning:
                    lines.append("**Assessment:**")
                    lines.append(f"> {r.reasoning}")
                    lines.append("")
                
                lines.append("---")
                lines.append("")
    
    # Excluded trials summary
    excluded_results = [r for r in results if r.match_likelihood.value == "EXCLUDED"]
    if excluded_results:
        lines.append(f"## Excluded ({len(excluded_results)} trials)")
        lines.append("")
        
        # Group by exclusion reason
        fast_filter_excluded = [r for r in excluded_results if r.filter_stage == "fast_filter"]
        llm_excluded = [r for r in excluded_results if r.filter_stage == "llm_scored"]
        
        if fast_filter_excluded:
            lines.append("### Excluded by Fast Filter")
            lines.append("")
            lines.append("| NCT ID | Reason |")
            lines.append("|--------|--------|")
            for r in fast_filter_excluded[:20]:
                lines.append(f"| [{r.nct_id}](https://clinicaltrials.gov/study/{r.nct_id}) | {r.excluded_reason or 'N/A'} |")
            if len(fast_filter_excluded) > 20:
                lines.append(f"| ... | *and {len(fast_filter_excluded) - 20} more* |")
            lines.append("")
        
        if llm_excluded:
            lines.append("### Excluded by Eligibility Assessment")
            lines.append("")
            lines.append("| NCT ID | Sponsor | Reason |")
            lines.append("|--------|---------|--------|")
            for r in llm_excluded[:20]:
                reason = r.conflicts[0] if r.conflicts else r.reasoning[:50] if r.reasoning else "N/A"
                lines.append(f"| [{r.nct_id}](https://clinicaltrials.gov/study/{r.nct_id}) | {r.sponsor[:20]} | {reason} |")
            if len(llm_excluded) > 20:
                lines.append(f"| ... | ... | *and {len(llm_excluded) - 20} more* |")
            lines.append("")
    
    # Search terms used
    lines.append("## Search Terms Used")
    lines.append("")
    lines.append("| Term | Source | Confidence |")
    lines.append("|------|--------|------------|")
    for term in search_terms:
        lines.append(f"| {term.term} | {term.provenance.value} | {term.confidence:.1f} |")
    lines.append("")
    
    # Key Missing Information section
    missing_info = _identify_missing_patient_info(patient, results)
    if missing_info:
        lines.append("## Information That Would Improve Matches")
        lines.append("")
        lines.append("The following patient data was not provided but would help refine eligibility assessment:")
        lines.append("")
        for item in missing_info:
            lines.append(f"- {item}")
        lines.append("")
    
    return "\n".join(lines)


def _identify_missing_patient_info(
    patient: PatientProfile,
    results: list[MatchResult]
) -> list[str]:
    """Identify key patient information that would improve matching.
    
    Analyzes uncertainties across all results to find commonly mentioned
    missing data points.
    
    Args:
        patient: The patient profile
        results: List of match results
        
    Returns:
        List of missing information descriptions
    """
    missing = []
    
    # Collect all uncertainties from scored trials
    all_uncertainties = []
    for r in results:
        if r.filter_stage == "llm_scored":
            all_uncertainties.extend(r.uncertainties)
    
    uncertainty_text = " ".join(all_uncertainties).lower()
    
    # Check what patient data is missing and frequently mentioned
    if not patient.pd_l1_status:
        # Check if PD-L1 is mentioned in uncertainties
        if "pd-l1" in uncertainty_text or "pdl1" in uncertainty_text or "pd l1" in uncertainty_text:
            missing.append("**PD-L1 expression status** - required by several trials for cohort assignment")
    
    if not patient.co_mutations:
        if "stk11" in uncertainty_text or "keap1" in uncertainty_text or "co-mutation" in uncertainty_text:
            missing.append("**Co-mutation status** (STK11, KEAP1) - affects eligibility for some KRAS G12C trials")
    
    if not patient.country:
        if "resident" in uncertainty_text or "canadian" in uncertainty_text or "location" in uncertainty_text:
            missing.append("**Patient country/location** - some trials have geographic requirements")
    
    if "organ function" in uncertainty_text or "hematologic" in uncertainty_text or "laboratory" in uncertainty_text:
        missing.append("**Organ function labs** (hematology, liver, renal) - required by all interventional trials")
    
    if "measurable disease" in uncertainty_text or "recist" in uncertainty_text:
        missing.append("**Measurable disease status** (per RECIST 1.1) - required for most therapeutic trials")
    
    if not patient.prior_therapies:
        if "prior treatment" in uncertainty_text or "prior therapy" in uncertainty_text:
            missing.append("**Detailed prior therapy list** - helps determine line of therapy eligibility")
    
    if "life expectancy" in uncertainty_text:
        missing.append("**Life expectancy estimate** - many trials require ≥3 months")
    
    if "qtc" in uncertainty_text or "cardiac" in uncertainty_text or "ecg" in uncertainty_text:
        missing.append("**Cardiac status/QTc interval** - relevant for trials with cardiotoxicity risk")
    
    return missing


def export_match_report(
    patient: PatientProfile,
    results: list[MatchResult],
    search_terms: list[SearchTerm],
    output_dir: Path
) -> None:
    """Export patient-trial match report.
    
    Args:
        patient: The patient profile
        results: List of match results
        search_terms: Search terms used
        output_dir: Output directory
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate and write markdown report
    report = generate_match_report(patient, results, search_terms)
    report_path = output_dir / "patient_matches.md"
    
    try:
        with open(report_path, "w") as f:
            f.write(report)
        console.print(f"  [dim]Wrote {report_path}[/dim]")
    except IOError as e:
        console.print(f"  [red]Error writing {report_path}: {e}[/red]")
        raise
    
    # Also export match results as JSON
    results_data = {
        "metadata": {
            "export_date": datetime.now().isoformat(),
            "patient_profile": {
                "age": patient.age,
                "sex": patient.sex,
                "cancer_type": patient.cancer_type,
                "biomarkers": patient.biomarkers,
                "description": patient.description,
            },
            "total_trials": len(results),
            "high_likelihood": sum(1 for r in results if r.match_likelihood.value == "HIGH"),
            "medium_likelihood": sum(1 for r in results if r.match_likelihood.value == "MEDIUM"),
        },
        "results": [
            {
                "nct_id": r.nct_id,
                "title": r.title,
                "sponsor": r.sponsor,
                "phase": r.phase,
                "status": r.status,
                "match_likelihood": r.match_likelihood.value,
                "filter_stage": r.filter_stage,
                "supporting_factors": r.supporting_factors,
                "conflicts": r.conflicts,
                "uncertainties": r.uncertainties,
                "confidence": r.confidence,
                "reasoning": r.reasoning,
                "excluded_reason": r.excluded_reason,
            }
            for r in results
        ]
    }
    
    json_path = output_dir / "patient_matches.json"
    try:
        with open(json_path, "w") as f:
            json.dump(results_data, f, indent=2)
        console.print(f"  [dim]Wrote {json_path}[/dim]")
    except IOError as e:
        console.print(f"  [red]Error writing {json_path}: {e}[/red]")
        raise
