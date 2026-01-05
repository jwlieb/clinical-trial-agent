# Patient-Trial Matching Agent

An AI-assisted system that helps match patients with relevant clinical trials based on their clinical profile, biomarkers, and eligibility criteria.

## Overview

This agent takes a patient profile (biomarkers, cancer type, treatment history, ECOG status, etc.) and:

1. **Extracts** search terms from the patient profile using LLM + programmatic expansion
2. **Discovers** relevant clinical trials from ClinicalTrials.gov (recruiting only)
3. **Normalizes** trial data into a structured schema with eligibility criteria
4. **Fast Filters** trials using deterministic rules (age, sex, location, phase preference)
5. **LLM Scores** candidate trials against detailed eligibility criteria
6. **Exports** results as ranked match reports (JSON, Markdown) with explanations

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PATIENT PROFILE                                   │
│  --biomarker "KRAS G12C" --cancer-type "NSCLC" --age 65 --ecog 1           │
│  --description "Failed carboplatin/pemetrexed and pembrolizumab..."        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TERM EXTRACTION                                      │
│              LLM + programmatic variant generation                          │
│   "KRAS G12C" → ["KRAS G12C", "KRASG12C", "KRAS-G12C", "KRAS G12C NSCLC"]  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TRIAL DISCOVERY                                      │
│                    ClinicalTrials.gov API                                   │
│          Recruiting-only filter • Location filter • Deduplicate            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      NORMALIZE & VALIDATE                                    │
│         Extract eligibility criteria • Parse age ranges                     │
│              Store raw responses for auditability                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     TWO-STAGE MATCHING                                       │
│                                                                              │
│   ┌──────────────────────┐     ┌──────────────────────────────────────┐    │
│   │  STAGE 1: Fast Filter │     │  STAGE 2: LLM Eligibility Scoring   │    │
│   │  • Age range check    │────▶│  • Prior treatment analysis         │    │
│   │  • Sex requirement    │     │  • Brain met policy evaluation      │    │
│   │  • Location match     │     │  • ECOG requirement check           │    │
│   │  • Phase preference   │     │  • Detailed eligibility parsing     │    │
│   │  • Relevance score    │     │  • Confidence scoring               │    │
│   └──────────────────────┘     └──────────────────────────────────────┘    │
│          │                              │                                   │
│          ▼                              ▼                                   │
│      EXCLUDED                    HIGH / MEDIUM / LOW                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            OUTPUTS                                           │
│  patient_matches.json  │  patient_matches.md  │  trials.json  │  trials.csv│
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
export GROQ_API_KEY="your-groq-api-key"
# OR
export OPENAI_API_KEY="your-openai-api-key"
export LLM_PROVIDER="openai"  # default is "groq"
```

## Usage

```bash
# Match trials for a specific patient profile
python run_agent.py \
  --age 65 --sex male \
  --cancer-type "NSCLC" \
  --biomarker "KRAS G12C" \
  --ecog 1 \
  --description "Failed carboplatin/pemetrexed and pembrolizumab, stable brain mets"

# Using a JSON profile file
python run_agent.py --profile patient.json

# With location preference (filters to trials in specific countries)
python run_agent.py \
  --biomarker "KRAS G12C" \
  --cancer-type "NSCLC" \
  --location "United States" \
  --description "65yo male with KRAS G12C NSCLC, ECOG 1"

# Debugging mode (sequential LLM calls)
python run_agent.py --profile patient.json --no-parallel
```

### Patient Profile Options

| Option | Description |
|--------|-------------|
| `--profile` | Path to JSON file with patient profile |
| `--age` | Patient age in years |
| `--sex` | Patient sex: male or female |
| `--cancer-type` | Cancer type (e.g., "NSCLC", "colorectal cancer") |
| `--biomarker` | Biomarker/mutation (can specify multiple times) |
| `--description` | Free-text patient description (required) |
| `--ecog` | ECOG performance status (0-5) |
| `--pd-l1` | PD-L1 expression level |
| `--prior-therapy` | Prior therapy (can specify multiple times) |
| `--brain-mets` | Brain metastases: none, stable, or active |
| `--co-mutation` | Co-mutation (can specify multiple times) |
| `--phase` | Preferred trial phases (can specify multiple) |
| `--location` | Preferred trial locations/countries |
| `--country` | Patient country for location matching |

## Output Files

| File | Description |
|------|-------------|
| `patient_matches.md` | Human-readable match report with HIGH/MEDIUM/LOW rankings |
| `patient_matches.json` | Machine-readable match results with confidence scores |
| `trials.json` | Full structured trial data with eligibility criteria |
| `trials.csv` | Flat view for spreadsheet analysis |
| `landscape.md` | Summary of trial landscape (phase distribution, sponsors) |
| `data/raw/*.json` | Raw API responses for auditability |

## Match Report Format

Each matched trial includes:
- **Match Likelihood**: HIGH, MEDIUM, LOW, or EXCLUDED
- **Confidence Score**: 0-100% confidence in the assessment
- **Supporting Factors**: Criteria the patient clearly meets
- **Conflicts**: Criteria the patient may fail
- **Uncertainties**: Criteria that need verification

```markdown
## 🟢 HIGH Likelihood (3 trials)

### NCT05067283
**Phase 1 Study of MK-1084 in KRAS G12C Solid Tumors**

- **Sponsor**: Merck Sharp & Dohme LLC
- **Phase**: Phase 1
- **Confidence**: 85%

✓ Supporting Factors:
- Patient has confirmed KRAS G12C mutation
- ECOG 1 meets trial requirement of ECOG 0-1
- Prior platinum-based chemotherapy is allowed

✗ Potential Conflicts:
- None identified

? Uncertainties:
- Stable brain metastases may require verification
```

## Trial Schema

```python
Trial:
  nct_id: str                      # e.g., "NCT04303780"
  title: str                       # Official trial title
  phase: str | None                # "Phase 1", "Phase 2", etc.
  status: str                      # "Recruiting", "Not yet recruiting"
  conditions: list[str]            # Target diseases/indications
  interventions: list[str]         # Drugs/treatments being tested
  sponsor: str                     # Lead sponsor organization
  locations: list[str]             # Study site countries
  eligibility:
    raw_text: str                  # Full eligibility criteria text
    minimum_age: str               # e.g., "18 Years"
    maximum_age: str               # e.g., "75 Years"
    sex: str                       # ALL, MALE, FEMALE
  confidence_flags:
    needs_review: bool             # Flag for uncertain data
```

## Patient Profile Schema

```python
PatientProfile:
  age: int | None                  # Patient age in years
  sex: str | None                  # "male" or "female"
  cancer_type: str | None          # e.g., "NSCLC"
  biomarkers: list[str]            # e.g., ["KRAS G12C"]
  description: str                 # Free-text clinical history (required)
  ecog_status: int | None          # 0-5
  pd_l1_status: str | None         # PD-L1 expression
  prior_therapies: list[str]       # Prior treatment regimens
  brain_mets_status: str | None    # "none", "stable", "active"
  co_mutations: list[str]          # e.g., ["STK11", "KEAP1"]
  phase_preference: list[str]      # Preferred trial phases
  location_preference: list[str]   # Preferred locations/countries
```

## Repository Structure

```
clinical-trial-tool/
├── README.md
├── requirements.txt
├── run_agent.py                    # CLI entry point
├── src/
│   ├── schemas.py                  # Pydantic models (Trial, PatientProfile, MatchResult)
│   ├── extract_terms.py            # LLM-based search term extraction
│   ├── seed_expansion.py           # Notation variant generation
│   ├── discover_trials.py          # ClinicalTrials.gov search & retrieval
│   ├── normalize_trials.py         # Schema normalization
│   ├── validate_trials.py          # Data validation rules
│   ├── match_patient.py            # Two-stage patient-trial matching
│   ├── review_coverage.py          # LLM gap review (legacy)
│   └── export_results.py           # Output generation
├── data/
│   ├── raw/                        # Raw API responses
│   └── processed/                  # Intermediate data
├── outputs/
│   └── kras_g12c/                  # Example output directory
│       ├── patient_matches.md
│       ├── patient_matches.json
│       ├── trials.json
│       ├── trials.csv
│       └── landscape.md
├── docs/
│   └── design_decisions.md         # Tradeoffs and rationale
└── report/
    └── presentation_outline.md
```

## Key Features

- **Patient-centric**: Input is a patient profile, not just a molecular target
- **Two-stage matching**: Fast deterministic filter + nuanced LLM scoring
- **Recruiting-only**: Only returns trials currently enrolling patients
- **Location filtering**: Filter trials by country/region
- **Explained decisions**: Every match includes supporting factors, conflicts, and uncertainties
- **Provenance tracking**: Search terms tracked by source (manual, LLM-extracted)
- **Parallel scoring**: Concurrent LLM calls with rate limiting for throughput
- **Auditable**: Raw data snapshots preserved

## Limitations

- **ClinicalTrials.gov only**: No EU registry, company pipelines, etc.
- **LLM confidence**: Eligibility assessment depends on LLM quality
- **Eligibility criteria parsing**: Free-text criteria can be ambiguous
- **No real-time verification**: Results should be verified with trial coordinators
- **CLI only**: No web interface

See [docs/design_decisions.md](docs/design_decisions.md) for detailed rationale on these tradeoffs.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | (required) | Groq API key for LLM inference |
| `OPENAI_API_KEY` | (optional) | OpenAI API key (if using OpenAI) |
| `LLM_PROVIDER` | `groq` | LLM provider: "groq" or "openai" |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | LLM model to use |

## License

MIT License - see LICENSE file for details.
