# Claims Data SQL Pipeline: T2D Cohort Identification, Utilization & Data Quality

A reproducible SQL analysis pipeline built on synthetic administrative health claims data, 
modeled on the structure of Canadian physician/hospital billing data (e.g. OHIP/CIHI-style);
demonstrates cohort identification, utilization/cost analysis, and data quality control

## Why this project

This project pulls a defined patient cohort out of messy administrative data, quantifies how
much healthcare that cohort uses and what it costs, catches data quality problems before they 
contaminate an analysis, and  builds a pipeline end-to-end against a messy dataset.

## Project structure

```
claims_sql_pipeline/
├── generate_synthetic_data.py     # builds data/claims_data.db from scratch
├── data/
│   └── claims_data.db             # SQLite database (generated)
└── queries/
    ├── 00_create_views.sql        # cohort definition (view)
    ├── 01_cohort_identification.sql
    ├── 02_utilization_metrics.sql
    └── 03_data_quality_checks.sql
├── run_pipeline.py                # applies views, runs queries, writes report
           # generates pipeline_results.md
├── pipeline_results.md 
```

## How to run it

```bash
python -m pip install pandas tabulate --break-system-packages   # if not installed
python generate_synthetic_data.py   # builds data/claims_data.db
python run_pipeline.py > pipeline_results.md    # applies views + runs queries -> pipeline_results.md
```

Re-running `generate_synthetic_data.py` reseeds the same synthetic dataset so that results are reproducible.

## Data model

| Table                 | Grain                | Key fields |
|------------------------|-----------------------|------------|
| `patients`             | one row per patient   | `patient_id`, `birth_year`, `sex`, `region`, `enrollment_date`, `disenrollment_date` |
| `providers`             | one row per provider  | `provider_id`, `specialty`, `region` |
| `diagnosis_reference`   | one row per dx code   | `diagnosis_code` (ICD-10-CA-style), `description`, `chronic_flag` |
| `claims`                | one row per claim     | `claim_id`, `patient_id`, `provider_id`, `service_date`, `claim_type` (physician / hospital_inpatient / emergency / pharmacy), `diagnosis_code`, `service_code`, `billed_amount`, `paid_amount` |

Synthetic data: 8,000 patients, 150 providers, ~89,000 claims across a
2021–2025 study window, with chronic-disease prevalence (diabetes,
hypertension, etc.) weighted by synthetic patient age.

**Deliberately injected data issues**: orphaned patient IDs, invalid/unmapped diagnosis codes, 
duplicate claims, non-positive billed amounts, paid amounts exceeding billed amounts,
and future-dated services.

## 1. Cohort identification (`00_create_views.sql`, `01_cohort_identification.sql`)

Defines a Type 2 diabetes (T2D) cohort using a validated-style case-finding
algorithm modeled on the logic behind administrative-data algorithms such as
the Ontario Diabetes Database (ODD):

> A patient is classified as having T2D if they have **≥2 physician claims**
> with a T2D diagnosis (E11), 30–730 days apart, **or ≥1 hospitalization**
> with a T2D diagnosis.

This two-claim / one-hospitalization pattern avoids false positives from a single miscoded or rule-out visit.

**Result:** 954 of 8,000 patients (11.9%) met the cohort definition —
consistent with real-world T2D prevalence in an adult population. 27% of
the cohort was identified via hospitalization, underscoring why relying on
hospital data alone would undercount the true cohort.

## 2. Utilization & cost metrics (`02_utilization_metrics.sql`)

Compares the T2D cohort against the rest of the population — the standard "burden of illness" comparison.

| Metric | T2D cohort | Non-cohort |
|---|---|---|
| Avg. claims / patient-year | 4.18 | 2.61 |
| Avg. paid $ / patient-year | $3,102 | $1,867 |
| % with ≥1 ED visit | 79.1% | 63.7% |
| % with ≥1 hospitalization | 57.5% | 40.6% |

Within the cohort, hospital inpatient care drives 68% of paid spend despite
being a small share of claim volume — anchors the "cost offset" argument 
(an intervention that reduces hospitalizations has an outsized effect 
on total cost, even if it doesn't reduce the number of claims overall).

## 3. Data quality checks (`03_data_quality_checks.sql`)

Referential integrity, code validity, duplicate detection, and value-range sanity checks.

| Issue | Records flagged |
|---|---|
| Orphan patient IDs | 262 |
| Invalid/unmapped diagnosis codes | 350 |
| Non-positive billed amounts | 175 |
| Paid amount exceeds billed amount | 529 |
| Future-dated services | 131 |
| Exact duplicate claims | 525 |
| **Overall clean rate** | **98.77%** |

In a real pipeline, this check would run on every data refresh, *before*
the cohort/utilization queries — records failing these checks should be
quarantined and excluded (as done in `02_utilization_metrics.sql`, which
filters out non-positive billed amounts).

## Full results

See [`pipeline_results.md`](pipeline_results.md) for every query alongside
its output.

## Notes on scope and limitations

- This is a single-condition (T2D) cohort algorithm; a production version would need 
    clinical validation against a gold-standard (e.g., chart review) before supporting a 
    real HTA submission.
- Costs are synthetic and not calibrated to real Canadian billing schedules
  (e.g., OHIP fee codes) — they're randomly generated within ranges by claim type.
- A production pipeline would also check things like provider-level outlier billing patterns.