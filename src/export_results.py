"""Export trial results in various formats."""

import csv
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from src.schemas import Trial, SearchTerm

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
                    "molecular_targets": "; ".join(trial.molecular_targets),
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
