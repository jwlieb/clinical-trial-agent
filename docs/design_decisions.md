# Design Decisions & Tradeoffs

---

## 1. The Pivot: Target Discovery → Patient Matching

**Original approach:** Input a molecular target (e.g., "KRAS G12C"), output a landscape of all trials targeting it.

**New approach:** Input a patient profile, output ranked trial recommendations with eligibility assessments.

### Why I pivoted

The original system took ~3 hours to build and worked. It answered: "What trials exist for KRAS G12C?" But I realized this question isn't that useful in practice.

The harder, more valuable question is: "Which of these trials might my patient actually qualify for?"

| Aspect | Target Discovery | Patient Matching |
|--------|------------------|------------------|
| Input | Molecular target | Full patient profile |
| Output | Trial landscape | Ranked recommendations |
| Value | Research overview | Actionable for clinicians |
| LLM use | Search term expansion | Eligibility interpretation |
| Time to build | ~3 hours | ~6 hours additional |

**Use cases for each:**
- Target discovery: Competitive intelligence, research landscape reports, drug development planning
- Patient matching: Clinical decision support, patient navigation, trial enrollment

I chose patient matching because it's the harder problem and demonstrates more interesting LLM application — interpreting complex eligibility criteria against a patient's clinical history.

**Tradeoffs:**
- More complex system
- Slower (LLM calls per candidate trial)
- Dependent on LLM quality for eligibility interpretation

---

## 2. Two-Stage Matching

**Stage 1: Fast Filter** — deterministic checks on structured fields:
- Age range
- Sex requirement
- Location match
- Phase preference
- Relevance score (keyword overlap)
- Recruiting status

**Stage 2: LLM Scoring** — for trials that pass Stage 1:
- Prior treatment analysis
- Brain metastases policy
- ECOG interpretation
- Detailed eligibility parsing

**Why two stages:**
- Fast filter is instant and free — eliminates 60-80% of trials
- LLM scoring is expensive — only run on viable candidates
- Each stage has clear failure modes and is testable independently

---

## 3. LLM Choice

Used Groq (Llama 3.3 70B) because it's free and fast. OpenAI is configurable via environment variable for comparison. This is a prototype — cost optimization wasn't the goal, but free API access made iteration faster.

---

## 4. Prompt Calibration

**Problem:** Initial prompts produced overly conservative results. Age 65 was flagged as "above typical range." Prior platinum chemotherapy was marked as a conflict even when trials required it.

**Fix:** Added explicit misconception corrections:

```
## Misconceptions to Avoid
- Age 65 is NOT "above typical age range" - most oncology trials accept adults 18+
- Prior standard-of-care treatments are typically REQUIRED for later-line trials
- Do NOT assume facts not explicitly stated in the patient profile
```

Added confidence calibration guide to produce consistent scores across trials.

---

## 5. Traceability & Verified Data

Every piece of data in the system is traceable to its source:

| Data Type | Source | Verification |
|-----------|--------|--------------|
| Trial metadata | ClinicalTrials.gov API | NCT ID links directly to source |
| Eligibility criteria | ClinicalTrials.gov raw text | Stored verbatim, no modification |
| Search terms | Tracked as "manual" or "llm" | Provenance recorded with confidence |
| Match assessments | LLM with full reasoning | Supporting factors, conflicts, uncertainties explicit |
| Raw API responses | Saved to `data/raw/` | Full audit trail |

**Why this matters:**
- Clinical decisions require trust in data
- LLM assessments can be wrong — explicit reasoning enables human review
- Provenance enables debugging when results look wrong

---

## 6. Why I Removed OpenTargets

Original system used OpenTargets to expand molecular targets into associated drug names.

Removed because:
1. Redundant — trials for target-specific drugs already mention the target in eligibility
2. Noise — drug name searches return trials for other indications
3. Complexity — extra API, extra failure modes, marginal benefit

Simpler approach: search for target + variants, let ClinicalTrials.gov indexing handle drug-target relationships.

---

## 7. Recruiting-Only Filter

For patient matching, only return trials with status:
- Recruiting
- Not yet recruiting
- Enrolling by invitation

Patients want trials they can enroll in. Completed/terminated trials are historical data.

---

## 8. Rate Limiting

Groq has aggressive rate limits. Implemented:
- 1 second minimum between requests
- Exponential backoff on 429 errors
- Thread-safe locking for parallel scoring
- `--no-parallel` flag for debugging

---

## 9. Relevance Pre-Filter

Before LLM scoring, calculate keyword-based relevance:
- Biomarker in trial title/conditions: +0.5
- Cancer type match: +0.3
- Threshold: 0.2 minimum to proceed

Saves LLM calls on clearly irrelevant trials (e.g., colorectal cancer trial for NSCLC patient).

---

## 10. Output Formats

| Output | Purpose |
|--------|---------|
| patient_matches.md | Human review — readable, shareable |
| patient_matches.json | Programmatic access — all fields, scores |
| trials.json | Full trial data with eligibility text |
| trials.csv | Spreadsheet analysis |
| landscape.md | Target-level summary |

---

## 11. Data Source: ClinicalTrials.gov Only

| Source | Decision |
|--------|----------|
| ClinicalTrials.gov | ✓ Canonical US trials, structured API, eligibility text |
| EU Clinical Trials Register | ✗ Different API/schema, time constraint |
| Company pipelines | ✗ Scraping complexity |

ClinicalTrials.gov has the best structured eligibility criteria. EU registry would be valuable but different enough to require significant additional work.

---

## 12. Technology Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Python 3.11+ | Best LLM/data ecosystem |
| Pydantic | Type-safe schemas, JSON serialization |
| requests | Simple HTTP, no async needed at prototype scale |
| Click | Better CLI than argparse for complex options |
| Rich | Progress bars, formatted terminal output |

---

## 13. Non-Goals

| Feature | Why scoped out |
|---------|----------------|
| EU Clinical Trials | Different API, time constraint |
| Multi-pass agent loop | Unpredictable, harder to debug |
| Web UI | CLI sufficient for prototype |
| Real-time updates | Prototype, not production |
| Direct enrollment | Out of scope |

---

## 14. What I Learned

1. **Two-stage filtering works** — fast filter reduces LLM calls by 60-80%
2. **LLM prompts need guardrails** — explicit misconception corrections improved results significantly
3. **Provenance tracking is essential** — when results look wrong, you need to trace back to source
4. **Patient-centric framing is more actionable** — ranked recommendations beat raw landscape data

---

## Alignment with Project Requirements

Per the project brief:

| Requirement | How addressed |
|-------------|---------------|
| **Discover trials from seed input** | ✓ Patient profile → search terms → ClinicalTrials.gov API |
| **Collect/structure trial details** | ✓ NCT ID, indication, interventions, sponsor, status, eligibility |
| **Molecular targets** | ✓ Biomarkers from patient profile drive search |
| **AI tools used thoughtfully** | ✓ LLM for term extraction + eligibility scoring, not for data retrieval |
| **Explain design choices** | ✓ This document |
| **Working prototype** | ✓ End-to-end pipeline, tested on KRAS G12C NSCLC patient |
| **Non-trivial examples** | ✓ 20+ trials evaluated, 12 medium/high matches |

**Where AI adds value vs. where it doesn't:**
- **Term extraction**: LLM helps with synonyms (NSCLC ↔ "non-small cell lung cancer"), but programmatic variant generation handles notation (KRAS G12C → KRASG12C)
- **Eligibility scoring**: LLM interprets nuanced criteria that would be extremely hard to parse programmatically
- **Data retrieval**: No LLM — ClinicalTrials.gov API is structured and reliable
- **Validation**: No LLM — deterministic checks on schema, date ordering, NCT ID format

**Scope choice:** Deep on one use case (KRAS G12C NSCLC patient matching) rather than broad/shallow coverage of many targets. This let me iterate on the matching logic and prompt calibration.

---

## 15. Iterative Fixes

Initial testing revealed issues. Each was diagnosed, fixed, and verified:

| Issue | Root Cause | Fix | Impact |
|-------|------------|-----|--------|
| 30% rate limit failures | Groq TPM limits, parallel calls | Retry with backoff, reduce workers to 2, add inter-request delay | 0% failures |
| BRAF terms for KRAS patient | LLM hallucinating related biomarkers | Prompt: "ONLY include biomarkers EXPLICITLY listed" | Clean search terms |
| Colorectal trials for NSCLC | No cancer type pre-filter | Relevance score filter (biomarker + cancer type in title/conditions) | Wrong-indication trials excluded |
| All confidence scores = 0.60 | No calibration guidance | Added confidence calibration scale (0.0-1.0 with examples) | Range: 0.05-0.80 |
| Age 65 "above typical range" | LLM misconception | Prompt: "Age 65 is NOT above typical" | Accurate age assessment |
| Location assumption | LLM assumed "Canadian resident" | Prompt: "NEVER assume location; treat as uncertainty" | No hallucinated facts |
| Arbitrary trial order | Only sorted by likelihood | Multi-factor sort: confidence → indication-match → phase | Clinically relevant order |
| Missing info unclear | Uncertainties scattered | Aggregate uncertainties → "Information That Would Improve Matches" section | Actionable guidance |

**Result:** 0 HIGH matches → 1 HIGH, 6 UNKNOWN → 0, colorectal/vascular trials correctly excluded.
