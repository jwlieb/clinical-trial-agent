#!/usr/bin/env python3
"""CLI entry point for the Clinical Trial Intelligence Agent."""

import json
import re
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.seed_expansion import expand_seed
from src.discover_trials import discover_trials
from src.normalize_trials import normalize_trials
from src.validate_trials import validate_trials
from src.review_coverage import review_coverage
from src.export_results import export_results

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


@click.command()
@click.option(
    "--target",
    required=True,
    help="Molecular target to search for (e.g., 'KRAS G12C', 'EGFR')"
)
@click.option(
    "--output",
    default="outputs/",
    type=click.Path(),
    help="Output directory for results"
)
@click.option(
    "--no-review",
    is_flag=True,
    help="Skip LLM gap review step"
)
@click.option(
    "--max-trials",
    default=100,
    type=int,
    help="Maximum number of trials to fetch"
)
def main(target: str, output: str, no_review: bool, max_trials: int):
    """Clinical Trial Intelligence Agent.
    
    Discovers and collects clinical trial information for a molecular target.
    """
    # Validate options
    validate_options(max_trials)
    
    console.print(Panel.fit(
        f"[bold blue]Clinical Trial Intelligence Agent[/bold blue]\n"
        f"Target: [green]{target}[/green]",
        border_style="blue"
    ))
    
    # Create target-specific output directory
    target_slug = sanitize_filename(target)
    output_dir = Path(output) / target_slug
    output_dir.mkdir(parents=True, exist_ok=True)
    
    data_dir = Path("data")
    (data_dir / "raw").mkdir(parents=True, exist_ok=True)
    (data_dir / "processed").mkdir(parents=True, exist_ok=True)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Step 1: Seed Expansion
            task = progress.add_task("[cyan]Expanding seed terms...", total=None)
            search_terms = expand_seed(target)
            progress.stop_task(task)
            progress.update(task, description="[green]✓ Expanded seed terms")
            console.print(f"  Found [green]{len(search_terms)}[/green] search terms")
            
            # Step 2: Trial Discovery (returns full records)
            task = progress.add_task("[cyan]Discovering trials...", total=None)
            raw_trials = discover_trials(search_terms, max_results=max_trials)
            progress.stop_task(task)
            progress.update(task, description="[green]✓ Discovered trials")
            console.print(f"  Discovered [green]{len(raw_trials)}[/green] unique trials")
            
            # Save raw data for auditability (target-specific filename)
            raw_file = data_dir / "raw" / f"trials_raw_{target_slug}.json"
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
            console.print(f"  Validated trials, [yellow]{flagged}[/yellow] flagged for review")
            
            # Step 5: LLM Gap Review (optional)
            if not no_review:
                task = progress.add_task("[cyan]Reviewing coverage with LLM...", total=None)
                gap_result, additional_trials = review_coverage(
                    target, search_terms, validated_trials
                )
                progress.stop_task(task)
                progress.update(task, description="[green]✓ Reviewed coverage")
                
                if additional_trials:
                    console.print(f"  LLM suggested new terms, found [green]{len(additional_trials)}[/green] additional trials")
                    validated_trials.extend(additional_trials)
                else:
                    console.print(f"  Coverage assessment: [green]{gap_result.coverage_assessment}[/green]")
            
            # Step 6: Export Results
            task = progress.add_task("[cyan]Exporting results...", total=None)
            export_results(validated_trials, search_terms, target, output_dir)
            progress.stop_task(task)
            progress.update(task, description="[green]✓ Exported results")
        
        console.print(Panel.fit(
            f"[bold green]Complete![/bold green]\n"
            f"Total trials: [cyan]{len(validated_trials)}[/cyan]\n"
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
