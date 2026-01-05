# Demo Patient Profiles

This directory contains realistic patient profiles for testing and demonstrating the clinical trial matching tool.

## Usage

Run the tool with any profile:

```bash
python run_agent.py --profile data/demo/patient_profiles/01_nsclc_kras_g12c_standard.json
```

Or with additional options:

```bash
python run_agent.py --profile data/demo/patient_profiles/01_nsclc_kras_g12c_standard.json --max-trials 50
```

## Patient Profiles Overview

### Standard Cases (Common Scenarios)

| File | Cancer Type | Key Biomarker | Clinical Scenario |
|------|-------------|---------------|-------------------|
| `01_nsclc_kras_g12c_standard.json` | NSCLC | KRAS G12C | Standard 2nd-line, no brain mets, ECOG 1 |
| `02_nsclc_kras_g12c_brain_mets.json` | NSCLC | KRAS G12C + STK11 | Treated stable brain mets, PD-L1 negative |
| `03_nsclc_egfr_exon19.json` | NSCLC | EGFR exon 19 del + C797S | Post-osimertinib resistance |
| `04_colorectal_kras_g12c.json` | Colorectal | KRAS G12C | 3rd-line, liver-dominant disease |
| `05_melanoma_braf_v600e.json` | Melanoma | BRAF V600E | Post-BRAF/MEK and IO, excellent PS |

### Specialized Biomarker Cases

| File | Cancer Type | Key Biomarker | Clinical Scenario |
|------|-------------|---------------|-------------------|
| `06_breast_her2_positive.json` | Breast | HER2+, ER+, PIK3CA | Progressing on T-DM1 |
| `07_pancreatic_kras_g12d.json` | Pancreatic | KRAS G12D | Post-FOLFIRINOX/gem-nab, seeking G12D trials |
| `09_prostate_brca2.json` | Prostate | BRCA2 germline | mCRPC post-olaparib |
| `10_gastric_her2_msi_high.json` | Gastric | HER2+, MSI-High | Dual-target opportunity, Lynch syndrome |

### Immunotherapy Focus

| File | Cancer Type | Key Biomarker | Clinical Scenario |
|------|-------------|---------------|-------------------|
| `08_lung_squamous_pd_l1_high.json` | Squamous Lung | PD-L1 ≥90% | Post-pembrolizumab progression |

### Edge Cases (Testing Boundaries)

| File | Cancer Type | Key Biomarker | Clinical Scenario |
|------|-------------|---------------|-------------------|
| `11_young_sarcoma_treatment_naive.json` | Synovial Sarcoma | SS18-SSX fusion | Treatment-naive, young patient |
| `12_elderly_cll_poor_performance.json` | CLL | TP53 del, IGHV unmut | ECOG 3, multiple comorbidities |
| `13_nsclc_alk_cns_disease.json` | NSCLC | ALK | Active brain mets, leptomeningeal |
| `14_renal_cell_io_resistant.json` | RCC | VHL loss | Exhausted IO/TKI options |
| `15_ovarian_brca1_platinum_sensitive.json` | Ovarian | BRCA1 germline | Platinum-sensitive recurrence |

## Profile Details

### 01 - NSCLC KRAS G12C Standard
**Scenario**: Most common KRAS G12C trial candidate
- 65M, ECOG 1, post-chemo/IO
- No brain mets, good labs
- **Expected**: High match rate for KRAS G12C NSCLC trials

### 02 - NSCLC KRAS G12C with Brain Mets
**Scenario**: Tests brain met eligibility criteria parsing
- 58F, ECOG 1, STK11 co-mutation
- Stable treated brain mets (off steroids)
- **Expected**: Some trials excluded for brain mets policy

### 03 - NSCLC EGFR with Resistance Mutation
**Scenario**: Post-TKI resistance, seeking next-gen agents
- 52F, Asian, never smoker
- EGFR exon 19 del + C797S resistance
- **Expected**: Matches to C797S-specific or novel EGFR trials

### 04 - Colorectal KRAS G12C
**Scenario**: Different tumor type with same mutation
- 61M, MSS, 3rd-line
- **Expected**: Should match KRAS G12C agnostic trials + CRC-specific

### 05 - Melanoma BRAF V600E
**Scenario**: Heavily pretreated melanoma
- 45F, post-BRAF/MEK and IO
- **Expected**: Novel combination trials, BRAF-specific agents

### 06 - Breast HER2+ with PIK3CA
**Scenario**: Dual-target opportunity
- 48F, premenopausal, HER2+/ER+
- PIK3CA H1047R co-mutation
- **Expected**: HER2 ADCs, PIK3CA combinations

### 07 - Pancreatic KRAS G12D
**Scenario**: Emerging G12D-specific trials
- 67M, ECOG 1, post-standard chemotherapy
- **Expected**: G12D-specific inhibitors, pan-KRAS trials

### 08 - Squamous Lung PD-L1 High
**Scenario**: IO-responsive tumor progressing on pembrolizumab
- 71M, no drivers, PD-L1 ≥90%
- **Expected**: IO combinations, novel checkpoint targets

### 09 - Prostate BRCA2
**Scenario**: DNA repair deficiency in prostate cancer
- 72M, mCRPC, post-PARP inhibitor
- **Expected**: PARP combinations, ATR/CHK inhibitors

### 10 - Gastric HER2+ MSI-High
**Scenario**: Dual biomarker opportunity
- 55M, ECOG 2, declining performance
- Lynch syndrome carrier
- **Expected**: HER2 trials + IO trials (MSI-H)

### 11 - Sarcoma Treatment-Naive (Edge Case)
**Scenario**: Tests first-line trial matching
- 28F, excellent PS, no prior treatment
- Rare tumor type with fusion
- **Expected**: Sarcoma-specific trials, fusion-targeted agents

### 12 - Elderly CLL Poor Performance (Edge Case)
**Scenario**: Tests ECOG and age filtering
- 82M, ECOG 3, multiple comorbidities
- High-risk cytogenetics
- **Expected**: Many trials excluded for ECOG/comorbidities

### 13 - NSCLC ALK CNS Disease (Edge Case)
**Scenario**: Tests active brain met handling
- 42M, leptomeningeal disease
- **Expected**: CNS-penetrant ALK inhibitor trials

### 14 - Renal Cell IO-Resistant (Edge Case)
**Scenario**: Exhausted standard options
- 59F, post-IO and multiple TKIs
- **Expected**: Novel mechanisms (HIF-2α, etc.)

### 15 - Ovarian BRCA1 Platinum-Sensitive (Edge Case)
**Scenario**: Recurrent with favorable biology
- 54F, platinum-sensitive recurrence
- **Expected**: PARP combos, ADCs, platinum re-challenge trials

## Testing Matrix

The profiles cover these key dimensions:

| Dimension | Values Covered |
|-----------|----------------|
| Age Range | 28-82 years |
| Sex | Male, Female |
| ECOG Status | 0, 1, 2, 3 |
| Brain Mets | None, Stable, Active |
| Treatment Status | Naive, 1-2 prior, 3+ prior |
| Tumor Types | 12 different malignancies |
| Biomarkers | KRAS, EGFR, ALK, HER2, BRAF, BRCA1/2, MSI, etc. |

## Notes

- All profiles are fictional but clinically realistic
- Labs and clinical details are included to test eligibility parsing
- Profiles intentionally include various edge cases for robustness testing
- Some profiles should have few/no matches (e.g., #12) to test empty result handling

