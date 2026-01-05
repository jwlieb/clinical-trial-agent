#!/usr/bin/env python3
"""CLI entry point for the Patient-Trial Matching Agent."""

import json
import re
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.schemas import PatientProfile
from src.extract_terms import extract_search_terms
from src.discover_trials import discover_trials
from src.normalize_trials import normalize_trials
from src.validate_trials import validate_trials
from src.match_patient import match_trials
from src.export_results import export_results, export_match_report

console = Console()


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename/directory name.
    
    Args:
        name: The string to sanitize
        
    Returns:
        Filesystem-safe string
    """
    sanitized = re.sub(r'[^\w\-]', '_', name.lower())
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_')


def validate_options(max_trials: int) -> None:
    """Validate CLI options.
    
    Args:
        max_trials: Maximum number of trials
        
    Raises:
        click.BadParameter: If validation fails
    """
    if max_trials <= 0:
        raise click.BadParameter("--max-trials must be a positive integer")


def build_patient_profile(
    profile_file: str | None,
    age: int | None,
    sex: str | None,
    cancer_type: str | None,
    biomarkers: tuple[str, ...],
    description: str | None,
    phase_preference: tuple[str, ...] | None,
    location_preference: tuple[str, ...] | None,
) -> PatientProfile:
    """Build PatientProfile from CLI options or JSON file.
    
    Args:
        profile_file: Path to JSON profile file (optional)
        age: Patient age
        sex: Patient sex
        cancer_type: Cancer type
        biomarkers: List of biomarkers
        description: Free-text description
        phase_preference: Preferred trial phases
        location_preference: Preferred locations
        
    Returns:
        PatientProfile object
        
    Raises:
        click.BadParameter: If required fields are missing
    """
    if profile_file:
        # Load from JSON file
        try:
            with open(profile_file, "r") as f:
                data = json.load(f)
            return PatientProfile(**data)
        except Exception as e:
            raise click.BadParameter(f"Failed to load profile from {profile_file}: {e}")
    
    # Build from CLI options
    if not description:
        raise click.BadParameter(
            "Either --profile or --description is required. "
            "Provide a free-text description of the patient's clinical history."
        )
    
    return PatientProfile(
        age=age,
        sex=sex,
        cancer_type=cancer_type,
        biomarkers=list(biomarkers) if biomarkers else [],
        description=description,
        phase_preference=list(phase_preference) if phase_preference else None,
        location_preference=list(location_preference) if location_preference else None,
    )


@click.command()
@click.option(
    "--profile",
    "profile_file",
    type=click.Path(exists=True),
    help="Path to JSON file containing patient profile"
)
@click.option(
    "--age",
    type=int,
    help="Patient age in years"
)
@click.option(
    "--sex",
    type=click.Choice(["male", "female"], case_sensitive=False),
    help="Patient sex"
)
@click.option(
    "--cancer-type",
    help="Cancer type (e.g., 'NSCLC', 'colorectal cancer')"
)
@click.option(
    "--biomarker", "--biomarkers",
    "biomarkers",
    multiple=True,
    help="Biomarker/mutation (can be specified multiple times, e.g., --biomarker 'KRAS G12C')"
)
@click.option(
    "--description",
    help="Free-text patient description (prior treatments, ECOG, comorbidities, etc.)"
)
@click.option(
    "--phase",
    "phase_preference",
    multiple=True,
    help="Preferred trial phases (can be specified multiple times)"
)
@click.option(
    "--location",
    "location_preference",
    multiple=True,
    help="Preferred trial locations/countries (can be specified multiple times)"
)
@click.option(
    "--output",
    default="outputs/",
    type=click.Path(),
    help="Output directory for results"
)
@click.option(
    "--max-trials",
    default=100,
    type=int,
    help="Maximum number of trials to fetch"
)
@click.option(
    "--no-parallel",
    is_flag=True,
    help="Disable parallel LLM scoring (useful for debugging)"
)
def main(
    profile_file: str | None,
    age: int | None,
    sex: str | None,
    cancer_type: str | None,
    biomarkers: tuple[str, ...],
    description: str | None,
    phase_preference: tuple[str, ...],
    location_preference: tuple[str, ...],
    output: str,
    max_trials: int,
    no_parallel: bool,
):
    """Patient-Trial Matching Agent.
    
    Finds and ranks clinical trials for a patient based on their profile.
    
    \b
    Examples:
      # Using CLI options:
      python run_agent.py \\
        --age 65 --sex male \\
        --cancer-type "NSCLC" \\
        --biomarker "KRAS G12C" \\
        --description "Failed carboplatin/pemetrexed and pembrolizumab, stable brain mets, ECOG 1"
    
      # Using a JSON profile:
      python run_agent.py --profile patient.json
    """
    # Validate options
    validate_options(max_trials)
    
    # Build patient profile
    try:
        patient = build_patient_profile(
            profile_file=profile_file,
            age=age,
            sex=sex,
            cancer_type=cancer_type,
            biomarkers=biomarkers,
            description=description,
            phase_preference=phase_preference,
            location_preference=location_preference,
        )
    except click.BadParameter as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    
    # Display patient profile
    profile_summary = []
    if patient.age:
        profile_summary.append(f"Age: {patient.age}")
    if patient.sex:
        profile_summary.append(f"Sex: {patient.sex}")
    if patient.cancer_type:
        profile_summary.append(f"Cancer: {patient.cancer_type}")
    if patient.biomarkers:
        profile_summary.append(f"Biomarkers: {', '.join(patient.biomarkers)}")
    
    console.print(Panel.fit(
        f"[bold blue]Patient-Trial Matching Agent[/bold blue]\n"
        f"{chr(10).join(profile_summary) if profile_summary else 'Profile from description'}\n"
        f"[dim]{patient.description[:100]}{'...' if len(patient.description) > 100 else ''}[/dim]",
        border_style="blue"
    ))
    
    # Create output directory
    # Use biomarker or cancer type for folder name
    folder_name = sanitize_filename(
        patient.biomarkers[0] if patient.biomarkers 
        else patient.cancer_type if patient.cancer_type 
        else "patient_search"
    )
    output_dir = Path(output) / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    data_dir = Path("data")
    (data_dir / "raw").mkdir(parents=True, exist_ok=True)
    (data_dir / "processed").mkdir(parents=True, exist_ok=True)
    
    try:
        # Step 1: Extract search terms from patient profile
        console.print("\n[bold]Step 1: Extracting search terms from patient profile...[/bold]")
        search_terms = extract_search_terms(patient)
        console.print(f"  Generated [green]{len(search_terms)}[/green] search terms:")
        for term in search_terms[:5]:
            console.print(f"    [dim]• {term.term} ({term.provenance.value})[/dim]")
        if len(search_terms) > 5:
            console.print(f"    [dim]... and {len(search_terms) - 5} more[/dim]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 2: Trial Discovery
            task = progress.add_task("[cyan]Discovering trials...", total=None)
            raw_trials = discover_trials(search_terms, max_results=max_trials)
            progress.stop_task(task)
            progress.update(task, description="[green]✓ Discovered trials")
            console.print(f"  Discovered [green]{len(raw_trials)}[/green] unique trials")
            
            # Save raw data for auditability
            raw_file = data_dir / "raw" / f"trials_raw_{folder_name}.json"
            with open(raw_file, "w") as f:
                json.dump(raw_trials, f, indent=2)
            console.print(f"  [dim]Saved raw data to {raw_file}[/dim]")
            
            # Step 3: Normalize
            task = progress.add_task("[cyan]Normalizing trial data...", total=None)
            normalized_trials = normalize_trials(raw_trials)
            progress.stop_task(task)
            progress.update(task, description="[green]✓ Normalized trial data")
            
            # Step 4: Validate
            task = progress.add_task("[cyan]Validating trials...", total=None)
            validated_trials = validate_trials(normalized_trials)
            progress.stop_task(task)
            progress.update(task, description="[green]✓ Validated trials")
            flagged = sum(1 for t in validated_trials if t.confidence_flags.needs_review)
            if flagged:
                console.print(f"  [yellow]{flagged}[/yellow] trials flagged for review")
        
        # Step 5: Match trials against patient (two-stage)
        console.print("\n[bold]Step 5: Matching trials to patient...[/bold]")
        match_results = match_trials(
            patient=patient,
            trials=validated_trials,
            parallel=not no_parallel
        )
        
        # Step 6: Export Results
        console.print("\n[bold]Step 6: Exporting results...[/bold]")
        
        # Export trial data (JSON, CSV)
        export_results(validated_trials, search_terms, folder_name, output_dir)
        
        # Export patient match report
        export_match_report(patient, match_results, search_terms, output_dir)
        
        console.print(f"  [dim]Results saved to {output_dir}[/dim]")
        
        # Final summary
        high_count = sum(1 for r in match_results if r.match_likelihood.value == "HIGH")
        medium_count = sum(1 for r in match_results if r.match_likelihood.value == "MEDIUM")
        
        console.print(Panel.fit(
            f"[bold green]Complete![/bold green]\n"
            f"Total trials found: [cyan]{len(validated_trials)}[/cyan]\n"
            f"[green]HIGH[/green] likelihood matches: [bold]{high_count}[/bold]\n"
            f"[yellow]MEDIUM[/yellow] likelihood matches: [bold]{medium_count}[/bold]\n"
            f"Outputs saved to: [blue]{output_dir}[/blue]",
            border_style="green"
        ))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(Panel.fit(
            f"[bold red]Error[/bold red]\n{e}",
            border_style="red"
        ))
        raise SystemExit(1) from e


if __name__ == "__main__":
    main()
