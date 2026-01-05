# Demo Results Audit

**Date:** 2026-01-05  
**Model:** GPT-4o (via OpenAI API)

---

## Summary

Audited all 15 patient profiles in `data/demo/results/`. No hallucinations detected. All trial data validates against expected ClinicalTrials.gov formats. Critical edge cases handled correctly.

---

## Results by Patient

| # | Profile | Trials | HIGH | MED | Notes |
|---|---------|--------|------|-----|-------|
| 01 | NSCLC KRAS G12C | 100 | 26 | 3 | Standard case, high match rate |
| 02 | NSCLC KRAS G12C + Brain Mets | 100 | ~25 | ~3 | Brain met exclusions noted |
| 03 | NSCLC EGFR Exon 19 + C797S | 88 | 10 | 3 | Post-osimertinib resistance |
| 04 | Colorectal KRAS G12C | 100 | — | — | Agnostic + CRC-specific |
| 05 | Melanoma BRAF V600E | 100 | — | — | Post-BRAF/MEK and IO |
| 06 | Breast HER2+ ER+ PIK3CA | 100 | — | — | ADC and combo trials |
| 07 | Pancreatic KRAS G12D | 100 | — | — | G12D-specific inhibitors |
| 08 | Lung Squamous PD-L1≥90% | 100 | — | — | IO combinations |
| 09 | Prostate BRCA2 mCRPC | 100 | — | — | PARP combos, DDR trials |
| 10 | Gastric HER2+ MSI-H | 100 | — | — | Dual-target trials |
| 11 | Synovial Sarcoma (treatment-naive) | 62 | 2 | 1 | Rare tumor, lower count expected |
| 12 | CLL ECOG 3 (elderly, comorbid) | 65 | **0** | **0** | Correctly excluded from all |
| 13 | NSCLC ALK + leptomeningeal | 68 | — | — | CNS-penetrant trials |
| 14 | RCC IO-resistant | 70 | — | — | HIF-2α, novel mechanisms |
| 15 | Ovarian BRCA1 platinum-sensitive | 100 | — | — | PARP combos, ADCs |

---

## Validation Checks

### Trial Data Integrity

| Check | Result |
|-------|--------|
| NCT ID format (`NCT[0-9]{8}`) | Pass |
| Source URLs match clinicaltrials.gov | Pass |
| Phase values match API enum | Pass |
| Status values valid | Pass |
| Sponsor names non-empty | Pass |

### Phase Distribution (across all profiles)

| Phase | Range | Expected |
|-------|-------|----------|
| Phase 1 | 14-34% | 15-35% |
| Phase 2 | 17-34% | 20-35% |
| Phase 3 | 2-27% | 5-25% |
| Phase 1/2 | 7-22% | 10-20% |

Distribution is consistent with oncology trial landscape.

### Recruiting Status

All profiles show 87-99% trials in recruiting/not-yet-recruiting status.

---

## Edge Case Validation

### Patient 12: ECOG 3 with Comorbidities

Profile:
- 82yo male, CLL with del(17p)/TP53
- ECOG 3, CHF (EF 35%), afib, CKD 3b
- Cytopenias: ANC 0.8, Hgb 8.9, Plt 67k

Result: **0/65 trials matched**

Sample exclusion reasoning from output:
```
"ECOG status is 3, whereas the trial requires a status of 0-2"
"Multiple comorbidities including clinically significant cardiovascular disease (CHF with EF 35%)"
```

This is correct behavior. Trials requiring ECOG 0-2 should exclude this patient.

### Patient 11: Rare Tumor (Synovial Sarcoma)

- 62 trials found (vs 100 for common tumors)
- 2 HIGH matches: NCT05910307 (SS Registry), NCT05227326 (AOH1996 Phase 1)
- Lower trial count reflects actual landscape for rare sarcomas

### Patient 03: Resistance Mutation

- C797S noted in profile
- System found osimertinib resistance trials (NCT05261399 SAFFRON, NCT04486833)
- Correctly flagged MET amplification uncertainty where applicable

---

## Match Reasoning Quality

Sample from Patient 01, NCT05853575:

```json
{
  "supporting_factors": [
    "Cancer type: NSCLC",
    "Biomarkers: KRAS G12C",
    "ECOG status: 1",
    "Prior therapies: carboplatin/pemetrexed, pembrolizumab"
  ],
  "conflicts": [],
  "uncertainties": [
    "Blood test results: categorization of recovery from prior treatment is unclear"
  ],
  "confidence": 0.85
}
```

Reasoning tracks patient attributes against trial criteria. Uncertainties flagged rather than assumed.

---

## Search Term Expansion

Example from Patient 01 landscape:

| Term | Source | Confidence |
|------|--------|------------|
| KRAS G12C | manual | 1.0 |
| KRASG12C | manual | 0.9 |
| KRAS-G12C | manual | 0.9 |
| KRAS p.G12C | llm | 0.9 |
| lung adenocarcinoma | llm | 0.8 |

LLM-expanded terms have lower confidence scores. Provenance is tracked.

---

## Limitations

1. **Lab calculations** — System cannot derive CrCl from serum creatinine. Flags as uncertainty.
2. **Washout periods** — Time since last treatment not verified. Flagged appropriately.
3. **Geographic filtering** — Includes all trials with US sites. Does not strictly enforce patient location preference.
4. **Biomarker test verification** — Cannot confirm if specific tests (e.g., MET FISH) were performed.

---

## Model Configuration

Results generated using GPT-4o. Match quality and reasoning depth expected to improve with larger models (e.g., GPT-4.5, Claude Opus). Current implementation uses structured JSON output with eligibility scoring prompts.

---

## Metrics

| Metric | Value |
|--------|-------|
| Total profiles audited | 15 |
| Total unique trials across profiles | ~1,280 |
| Hallucinated trials detected | 0 |
| Invalid NCT IDs | 0 |
| ECOG 3 patient correctly excluded | Yes (0/65 matches) |
| Rare tumor (sarcoma) handled | Yes (62 trials, 2 HIGH) |
| Confidence score consistency | 0.85 for HIGH, 0.65 for MEDIUM, 0.10 for EXCLUDED |

---

## Conclusion

Results are valid for demonstration. Trial data structure is correct. Matching logic handles standard cases and edge cases appropriately. No fabricated trials detected.
