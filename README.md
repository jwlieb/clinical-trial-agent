# Clinical Trial Intelligence Agent

An AI-assisted system that automatically discovers, collects, and organizes detailed information about clinical trials starting from a molecular target input.

## Overview

This agent takes a molecular target (e.g., "KRAS G12C", "EGFR", "PD-1") and:

1. **Expands** the seed into notation variants (e.g., "KRAS G12C" → "KRASG12C", "KRAS-G12C")
2. **Discovers** relevant clinical trials from ClinicalTrials.gov
3. **Normalizes** trial data into a structured, auditable schema
4. **Reviews** coverage using an LLM to identify gaps and suggest additional search terms
5. **Exports** results in multiple formats (JSON, CSV, Markdown summary)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SEED INPUT                                      │
│                         --target "KRAS G12C"                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SEED EXPANSION                                     │
│                                                                              │
│              Generate notation variants programmatically                     │
│           "KRAS G12C" → ["KRAS G12C", "KRASG12C", "KRAS-G12C"]              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TRIAL DISCOVERY                                      │
│                    ClinicalTrials.gov API                                   │
│              Query each term → collect NCT IDs → deduplicate                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FETCH & NORMALIZE                                       │
│         Retrieve full trial records → normalize to schema                   │
│              Store raw responses for auditability                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LLM GAP REVIEW                                         │
│     Analyze results → identify coverage gaps → suggest new terms            │
│                                                                              │
│   ┌──────────────┐         ┌──────────────────────────────────────┐        │
│   │ Gaps Found?  │───Yes──▶│ Run additional discovery round       │        │
│   └──────────────┘         └──────────────────────────────────────┘        │
│          │ No                                                               │
│          ▼                                                                  │
│   [Finalize Dataset]                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            OUTPUTS                                           │
│    trials.json    │    trials.csv    │    landscape.md                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd clinical-trial-tool

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export OPENAI_API_KEY="your-api-key"
```

## Usage

```bash
# Basic usage with KRAS G12C (demo target)
python run_agent.py --target "KRAS G12C" --output outputs/

# Other molecular targets
python run_agent.py --target "EGFR" --output outputs/
python run_agent.py --target "BRAF V600E" --output outputs/

# Skip LLM gap review (faster, but may miss coverage gaps)
python run_agent.py --target "KRAS G12C" --no-review --output outputs/
```

## Output Files

| File | Description |
|------|-------------|
| `outputs/trials.json` | Full structured trial data with provenance tracking |
| `outputs/trials.csv` | Flat view for spreadsheet analysis |
| `outputs/landscape.md` | Human-readable summary with phase distribution, sponsor breakdown |
| `data/raw/*.json` | Raw API responses for auditability |

## Trial Schema

Each trial is normalized to the following structure:

```python
Trial:
  nct_id: str                      # e.g., "NCT04303780"
  title: str                       # Official trial title
  phase: str | None                # "Phase 1", "Phase 2", etc.
  status: str                      # "Recruiting", "Completed", etc.
  conditions: list[str]            # Target diseases/indications
  interventions: list[str]         # Drugs/treatments being tested
  molecular_targets: list[str]     # Inferred targets (if available)
  sponsor: str                     # Lead sponsor organization
  start_date: date | None
  completion_date: date | None
  locations: list[str]             # Study sites
  summary: str                     # Brief description
  sources: list[Source]            # Provenance for each field
  confidence_flags:
    needs_review: bool             # Flag for uncertain data
```

## Repository Structure

```
clinical-trial-tool/
├── README.md
├── requirements.txt
├── run_agent.py                    # CLI entry point
├── src/
│   ├── seed_expansion.py           # Notation variant generation
│   ├── discover_trials.py          # ClinicalTrials.gov search & retrieval
│   ├── normalize_trials.py         # Schema normalization
│   ├── validate_trials.py          # Data validation rules
│   ├── review_coverage.py          # LLM gap review
│   ├── export_results.py           # Output generation
│   └── schemas.py                  # Pydantic models
├── data/
│   ├── raw/                        # Raw API responses
│   └── processed/                  # Intermediate data
├── outputs/
│   ├── trials.json
│   ├── trials.csv
│   └── landscape.md
├── docs/
│   └── design_decisions.md         # Tradeoffs and rationale
└── report/
    └── slides.pdf                  # Final presentation
```

## Data Sources

| Source | Purpose | Usage |
|--------|---------|-------|
| **ClinicalTrials.gov** | Trial discovery and structured data | Primary source for all trial information |

## Key Features

- **Parameterized input**: Works with any molecular target, not hardcoded
- **Provenance tracking**: Every field links back to its source
- **Auditable**: Raw data snapshots preserved
- **Intelligent gap detection**: LLM reviews results and suggests missing terms
- **Conservative defaults**: Unknown values marked as `null`, not guessed

## Limitations

- Molecular targets only (not diseases, companies, or drugs as seed types)
- Single-pass LLM review (not a full autonomous agent loop)
- ClinicalTrials.gov focus (no EU registry, company pipelines, etc.)
- CLI only (no web interface)

See [docs/design_decisions.md](docs/design_decisions.md) for detailed rationale on these tradeoffs.

## License

MIT License - see LICENSE file for details.
