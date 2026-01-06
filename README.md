# Patient-Trial Matching Agent

An AI-assisted system that matches cancer patients with relevant clinical trials based on their clinical profile, biomarkers, and eligibility criteria.

## Overview

Clinical trial matching is hard. ClinicalTrials.gov can answer "what trials exist for KRAS G12C?" but the harder question is "which of these trials might my patient actually qualify for?" That requires interpreting free-text eligibility criteria against a patient's full clinical history—prior treatments, performance status, comorbidities, brain metastases policies, and more.

This prototype automates that interpretation using a multi-stage approach: fast deterministic filtering on structured fields, then LLM-based scoring of eligibility criteria for candidates that pass.

**For the full project rationale and design philosophy, see [docs/project_summary.md](docs/project_summary.md).**

## How It Works

Starting from a patient profile, the system:

1. **Extracts search terms** from biomarkers and cancer type (LLM + programmatic expansion)
2. **Discovers trials** from ClinicalTrials.gov (recruiting only, with demographic pre-filtering)
3. **Fast filters** using deterministic rules (age, sex, location, relevance score)
4. **LLM scores** candidates against raw eligibility text
5. **Exports** ranked matches with supporting factors, conflicts, and uncertainties

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
│                        TWO-STAGE MATCHING                                    │
│                                                                              │
│   ┌───────────────────────┐     ┌───────────────────────────────────────┐  │
│   │  STAGE 1: Fast Filter  │     │  STAGE 2: LLM Eligibility Scoring    │  │
│   │  • Age/sex/location    │────▶│  • Treatment line analysis           │  │
│   │  • Relevance score     │     │  • Brain mets policy                 │  │
│   │  • Recruiting status   │     │  • ECOG/comorbidity check            │  │
│   └───────────────────────┘     └───────────────────────────────────────┘  │
│          │                               │                                  │
│          ▼                               ▼                                  │
│      EXCLUDED                     HIGH / MEDIUM / LOW                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OUTPUTS                                         │
│   patient_matches.md  │  patient_matches.json  │  trials.json  │  trials.csv│
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone and set up
git clone <repository-url>
cd clinical-trial-tool
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure LLM provider (choose one)
export GROQ_API_KEY="your-groq-api-key"      # Free, fast (default)
# OR
export OPENAI_API_KEY="your-openai-api-key"
export LLM_PROVIDER="openai"

# Run a match
python run_agent.py \
  --age 65 --sex male \
  --cancer-type "NSCLC" \
  --biomarker "KRAS G12C" \
  --ecog 1 \
  --description "Stage IV adenocarcinoma, failed carboplatin/pemetrexed and pembrolizumab"
```

## Usage Examples

```bash
# From a JSON patient profile
python run_agent.py --profile data/demo/patient_profiles/01_nsclc_kras_g12c_standard.json

# With location filtering
python run_agent.py \
  --biomarker "KRAS G12C" \
  --cancer-type "NSCLC" \
  --location "United States" \
  --description "65yo male with KRAS G12C NSCLC, ECOG 1"

# Debug mode (sequential LLM calls, verbose output)
python run_agent.py --profile patient.json --no-parallel
```

### CLI Options

| Option | Description |
|--------|-------------|
| `--profile` | Path to JSON patient profile |
| `--age` | Patient age in years |
| `--sex` | `male` or `female` |
| `--cancer-type` | Cancer type (e.g., "NSCLC", "colorectal cancer") |
| `--biomarker` | Biomarker/mutation (repeatable) |
| `--description` | Free-text clinical history (**required**) |
| `--ecog` | ECOG performance status (0-5) |
| `--pd-l1` | PD-L1 expression level |
| `--prior-therapy` | Prior therapy (repeatable) |
| `--brain-mets` | `none`, `stable`, or `active` |
| `--co-mutation` | Co-mutation (repeatable) |
| `--phase` | Preferred trial phases (repeatable) |
| `--location` | Preferred countries (repeatable) |

## Output Files

| File | Purpose |
|------|---------|
| `patient_matches.md` | Human-readable ranked report |
| `patient_matches.json` | Machine-readable results with confidence scores |
| `trials.json` | Full trial data with raw eligibility text |
| `trials.csv` | Spreadsheet-friendly flat export |
| `landscape.md` | Trial landscape summary (phases, sponsors) |
| `data/raw/*.json` | Raw API responses for audit |

### Example Match Output

```markdown
## 🟢 HIGH Likelihood

### NCT06881784
**RASolve 301: Phase 3 Study of RMC-6236 vs Docetaxel in RAS-Mutant NSCLC**

- **Sponsor**: Revolution Medicines, Inc.
- **Phase**: Phase 3
- **Confidence**: 95%

✓ Supporting Factors:
- ECOG 1 meets requirement
- Prior platinum + anti-PD-1 therapy (required for this trial)
- Documented KRAS G12C mutation

✗ Conflicts: None

? Uncertainties: None
```

## Validation

The system was validated on 15 patient profiles spanning 12 tumor types:

- **Standard cases**: KRAS G12C, EGFR, ALK, BRAF, HER2, BRCA1/2
- **Edge cases**: ECOG 3 with comorbidities, rare sarcoma, active CNS disease
- **Results**: ~1,349 unique trials evaluated, zero hallucinated NCT IDs
- **Negative control**: Elderly CLL patient (ECOG 3, CHF, CKD) correctly matched 0/64 trials

See `data/demo/` for example patient profiles and results.

## Repository Structure

```
clinical-trial-tool/
├── README.md
├── requirements.txt
├── run_agent.py                 # CLI entry point
├── src/
│   ├── schemas.py               # Pydantic models
│   ├── extract_terms.py         # Search term extraction
│   ├── seed_expansion.py        # Notation variant generation
│   ├── discover_trials.py       # ClinicalTrials.gov API
│   ├── normalize_trials.py      # Schema normalization
│   ├── validate_trials.py       # Data validation
│   ├── match_patient.py         # Two-stage matching
│   └── export_results.py        # Output generation
├── data/
│   ├── demo/                    # Example patient profiles & results
│   └── raw/                     # Raw API responses
├── outputs/                     # Generated match reports
├── tests/                       # Unit tests
└── docs/
    ├── project_summary.md       # Project rationale and overview
    └── design_decisions.md      # Technical tradeoffs
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Two-stage filtering** | Fast filter eliminates 30-45% of trials before expensive LLM scoring |
| **ClinicalTrials.gov only** | Best structured eligibility text; EU registry deferred due to schema differences |
| **Raw text preserved** | Eligibility criteria stored verbatim for auditability |
| **Explicit uncertainties** | LLM surfaces what it doesn't know instead of guessing |

For the full design rationale, see [docs/design_decisions.md](docs/design_decisions.md).

## Limitations

- **ClinicalTrials.gov only** — EU Clinical Trials Register not yet supported
- **LLM-dependent** — Eligibility scoring quality depends on the underlying model
- **Snapshot data** — Results reflect trials at query time; no update monitoring
- **CLI only** — No web interface
- **Advisory only** — Results should be verified with trial coordinators

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Groq API key (required if using Groq) |
| `OPENAI_API_KEY` | — | OpenAI API key (required if using OpenAI) |
| `LLM_PROVIDER` | `groq` | `"groq"` or `"openai"` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model identifier |

## Documentation

- **[Project Summary](docs/project_summary.md)** — Goals, approach, validation, and lessons learned
- **[Design Decisions](docs/design_decisions.md)** — Technical tradeoffs and rationale

## License

MIT License — see [LICENSE](LICENSE) for details.
