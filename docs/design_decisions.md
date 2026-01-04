# Design Decisions & Tradeoffs

---

## 1. Seed Type Selection

**Decision:** Molecular target (parameterized) — accepts any target as input (e.g., "KRAS G12C", "EGFR", "PD-1").

| Seed Type | Pros | Cons |
|-----------|------|------|
| Disease/Indication | Intuitive, broad coverage | Simple keyword search, less reasoning required |
| Drug name | Direct mapping to trials | Trivial lookup |
| Company/Sponsor | Business-relevant | Just a filter |
| **Molecular target** ✓ | Forces multi-step reasoning (target → drugs → trials) | More complex, requires external data source |

**Why molecular target:**
- "KRAS G12C" doesn't appear verbatim in trials — system must know sotorasib and adagrasib are KRAS G12C inhibitors
- Shows competitive landscape across multiple drugs
- Validates OpenTargets integration

**Tradeoffs:** More complex than disease search. Requires OpenTargets API. May miss trials that don't specify target.

---

## 2. Data Sources

**Decision:** ClinicalTrials.gov (primary) + OpenTargets (expansion)

| Source | Decision |
|--------|----------|
| ClinicalTrials.gov | ✓ Primary — canonical US trials, structured API, NCT IDs |
| OpenTargets | ✓ Expansion — curated drug-target mappings, GraphQL API |
| EU Clinical Trials Register | ✗ Different API, scoped out |
| PubMed | ✗ Nice-to-have enrichment |
| Company pipeline pages | ✗ Scraping complexity |

**Tradeoffs:** Missing non-US trials. OpenTargets curation may lag newest drugs.

---

## 3. LLM Usage: Single-Pass Gap Review

**Decision:** LLM reviews results once after discovery, assessing coverage gaps.

| Approach | Pros | Cons |
|----------|------|------|
| No LLM | Simpler, deterministic | No intelligence in gap detection |
| **Single-pass review** ✓ | Demonstrates AI value, predictable | May miss some gaps |
| Multi-pass agent | More thorough | Complex, time-consuming, harder to debug |
| Full ReAct agent | Most impressive | Unpredictable, scope creep |

**Prompt template:**
```
You are reviewing clinical trial search results for {target} inhibitors.

Search terms used: {terms}
Trials found: {count}
Phase distribution: {phases}
Drugs mentioned: {drugs}
Sponsors: {sponsors}

Based on your knowledge of this therapeutic area, are there obvious gaps?

Respond with:
1. Coverage assessment (Good/Gaps Detected)
2. If gaps: suggested additional search terms (max 3)
3. Brief reasoning
```

**Tradeoffs:** May miss subtle gaps. Relies on LLM training data currency. Not fully autonomous (by design).

---

## 4. Accuracy vs. Coverage

**Decision:** Prioritize accuracy. Target 50-100 trials with high accuracy over 500+ uncertain.

- Every field links to source — quantity without provenance is useless
- If field can't be extracted confidently: `null` with `needs_review: true`
- Invalid data flagged, not silently accepted

**Validation:**

| Check | Implementation |
|-------|----------------|
| Phase enum | Must match known phases or null |
| Status enum | Must match known statuses |
| NCT ID format | Regex: `NCT\d{8}` |
| Date ordering | start_date <= completion_date |
| Empty critical fields | Flagged for review |

**Tradeoffs:** Lower trial count. Some valid trials flagged unnecessarily.

---

## 5. Schema Design

**Decision:** Structured schema with provenance tracking.

Every trial record includes:
- Normalized fields (phase, status, etc.)
- Source citations for each field
- Confidence flags for uncertain data

| Field | Decision | Rationale |
|-------|----------|-----------|
| `molecular_targets` | Nullable list | Not always extractable |
| `sources` | Per-field provenance | Enables auditing |
| `confidence_flags.needs_review` | Boolean | Explicit uncertainty signal |
| `summary` | LLM-generated from structured fields | Grounded, not invented |

**Tradeoffs:** More complex than flat CSV. More storage for provenance.

---

## 6. Interface: CLI Only

**Decision:** Command-line interface, no web UI.

| Interface | Pros | Cons |
|-----------|------|------|
| **CLI only** ✓ | Fast to build, scriptable | Less impressive demo |
| Jupyter notebook | Interactive | Harder to run as pipeline |
| Streamlit | Impressive demo | 2-3 hours additional |

Focus on core intelligence, not presentation. Outputs (JSON, CSV, Markdown) viewable anywhere.

---

## 7. Non-Goals

Scoped out to stay within time budget:

| Feature | Reason |
|---------|--------|
| PubMed enrichment | Nice-to-have |
| EU Clinical Trials Register | Different API |
| Multi-seed-type support | Different expansion strategies per type |
| Real-time updates | Prototype, not production |
| Fully autonomous agent loop | Unpredictable, debugging time |
| Web UI | Time better spent on core logic |

---

## 8. Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Best ecosystem for APIs, LLMs, data |
| Schema validation | Pydantic | Type-safe, good errors |
| HTTP client | requests | Simple, reliable |
| LLM | OpenAI API (GPT-4) | Best reasoning |
| CLI | argparse or click | Standard |
| Output formatting | rich | Nice terminal output |

**Why not:**
- LangChain — overkill for single-pass LLM use
- Async — not needed at prototype scale
- SQLite — JSON files sufficient
- TypeScript — Python has better data science ecosystem

---

## 9. Future Extensions

| Extension | Value | Effort |
|-----------|-------|--------|
| EU Clinical Trials Register | Non-US trial coverage | Medium |
| Multi-pass LLM agent | Better gap detection | Medium |
| Streamlit UI | Better demo | Low-Medium |
| PubMed enrichment | Linked publications | Low |
| Multiple seed types | Disease, drug, company inputs | High |
| Incremental updates | Track status changes over time | High |
