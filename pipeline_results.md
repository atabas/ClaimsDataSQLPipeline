
## queries/01_cohort_identification.sql

**Q1. Cohort size and share of the enrolled population**

```sql
-- Q1. Cohort size and share of the enrolled population
SELECT
    (SELECT COUNT(*) FROM t2d_cohort)                    AS t2d_cohort_size,
    (SELECT COUNT(*) FROM patients)                       AS total_patients,
    ROUND(100.0 * (SELECT COUNT(*) FROM t2d_cohort)
          / (SELECT COUNT(*) FROM patients), 2)           AS pct_of_population;
```

|   t2d_cohort_size |   total_patients |   pct_of_population |
|------------------:|-----------------:|--------------------:|
|               954 |             8000 |               11.93 | 

**Q2. Cohort identification pathway: hospitalization-only, physician-pair-only, or both**

```sql
-- Q2. Cohort identification pathway: hospitalization-only, physician-pair-only, or both
WITH hosp AS (
    SELECT DISTINCT patient_id FROM claims
    WHERE diagnosis_code = 'E11' AND claim_type = 'hospital_inpatient'
),
phys_pair AS (
    SELECT patient_id FROM t2d_physician_claim_pairs
)
SELECT
    CASE
        WHEN h.patient_id IS NOT NULL AND p.patient_id IS NOT NULL THEN 'both'
        WHEN h.patient_id IS NOT NULL THEN 'hospitalization_only'
        WHEN p.patient_id IS NOT NULL THEN 'physician_pair_only'
    END AS identification_pathway,
    COUNT(*) AS n_patients
FROM t2d_cohort c
LEFT JOIN hosp h ON h.patient_id = c.patient_id
LEFT JOIN phys_pair p ON p.patient_id = c.patient_id
GROUP BY identification_pathway;
```

| identification_pathway   |   n_patients |
|:-------------------------|-------------:|
| both                     |          260 |
| hospitalization_only     |           31 |
| physician_pair_only      |          663 | 

**Q3. Cohort demographic breakdown: sex and 10-year age band (age computed as of study end, 2025-12-31)**

```sql
-- Q3. Cohort demographic breakdown: sex and 10-year age band (age computed as of study end, 2025-12-31)
SELECT
    pt.sex,
    CASE
        WHEN (2025 - pt.birth_year) < 45 THEN 'under_45'
        WHEN (2025 - pt.birth_year) < 65 THEN '45_64'
        ELSE '65_plus'
    END AS age_band,
    COUNT(*) AS n_patients
FROM patients pt
JOIN t2d_cohort c ON c.patient_id = pt.patient_id
GROUP BY pt.sex, age_band
ORDER BY age_band, pt.sex;
```

| sex   | age_band   |   n_patients |
|:------|:-----------|-------------:|
| F     | 45_64      |          123 |
| M     | 45_64      |          122 |
| F     | 65_plus    |          258 |
| M     | 65_plus    |          252 |
| F     | under_45   |           96 |
| M     | under_45   |          103 | 

**Q4. Cohort distribution by region (regional access/resourcing view)**

```sql
-- Q4. Cohort distribution by region (regional access/resourcing view)
SELECT
    pt.region,
    COUNT(*) AS n_cohort_patients
FROM patients pt
JOIN t2d_cohort c ON c.patient_id = pt.patient_id
GROUP BY pt.region
ORDER BY n_cohort_patients DESC;
```

| region      |   n_cohort_patients |
|:------------|--------------------:|
| Mississauga |                 169 |
| Waterloo    |                 166 |
| London      |                 166 |
| Ottawa      |                 156 |
| Toronto     |                 149 |
| Hamilton    |                 148 | 


## queries/02_utilization_metrics.sql

**Q1. Annualized claims and cost per patient: cohort vs. non-cohort**

```sql
-- Q1. Annualized claims and cost per patient: cohort vs. non-cohort
WITH patient_years AS (
    SELECT
        pt.patient_id,
        CASE WHEN c.patient_id IS NOT NULL THEN 'T2D_cohort' ELSE 'non_cohort' END AS grp,
        ROUND(
            (julianday(COALESCE(pt.disenrollment_date, '2025-12-31'))
             - julianday(pt.enrollment_date)) / 365.25
        , 2) AS years_enrolled
    FROM patients pt
    LEFT JOIN t2d_cohort c ON c.patient_id = pt.patient_id
),
claim_totals AS (
    SELECT patient_id, COUNT(*) AS n_claims, SUM(paid_amount) AS total_paid
    FROM claims
    WHERE billed_amount > 0          -- exclude known-bad records; see 03_data_quality_checks.sql
    GROUP BY patient_id
)
SELECT
    py.grp,
    COUNT(*) AS n_patients,
    ROUND(AVG(COALESCE(ct.n_claims, 0) / NULLIF(py.years_enrolled, 0)), 2) AS avg_claims_per_patient_year,
    ROUND(AVG(COALESCE(ct.total_paid, 0) / NULLIF(py.years_enrolled, 0)), 2) AS avg_paid_per_patient_year
FROM patient_years py
LEFT JOIN claim_totals ct ON ct.patient_id = py.patient_id
WHERE py.years_enrolled > 0
GROUP BY py.grp;
```

| grp        |   n_patients |   avg_claims_per_patient_year |   avg_paid_per_patient_year |
|:-----------|-------------:|------------------------------:|----------------------------:|
| T2D_cohort |          954 |                          4.18 |                     3101.68 |
| non_cohort |         7046 |                          2.61 |                     1867.33 | 

**Q2. Emergency and hospitalization rates: cohort vs. non-cohort (patients with >=1 claim of that type / total patients in group)**

```sql
-- Q2. Emergency and hospitalization rates: cohort vs. non-cohort (patients with >=1 claim of that type / total patients in group)
WITH grouped AS (
    SELECT
        pt.patient_id,
        CASE WHEN c.patient_id IS NOT NULL THEN 'T2D_cohort' ELSE 'non_cohort' END AS grp
    FROM patients pt
    LEFT JOIN t2d_cohort c ON c.patient_id = pt.patient_id
)
SELECT
    g.grp,
    COUNT(DISTINCT g.patient_id) AS n_patients,
    COUNT(DISTINCT CASE WHEN cl.claim_type = 'emergency' THEN g.patient_id END) AS n_with_ed_visit,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN cl.claim_type = 'emergency' THEN g.patient_id END)
          / COUNT(DISTINCT g.patient_id), 1) AS pct_with_ed_visit,
    COUNT(DISTINCT CASE WHEN cl.claim_type = 'hospital_inpatient' THEN g.patient_id END) AS n_with_hospitalization,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN cl.claim_type = 'hospital_inpatient' THEN g.patient_id END)
          / COUNT(DISTINCT g.patient_id), 1) AS pct_with_hospitalization
FROM grouped g
LEFT JOIN claims cl ON cl.patient_id = g.patient_id AND cl.billed_amount > 0
GROUP BY g.grp;
```

| grp        |   n_patients |   n_with_ed_visit |   pct_with_ed_visit |   n_with_hospitalization |   pct_with_hospitalization |
|:-----------|-------------:|------------------:|--------------------:|-------------------------:|---------------------------:|
| T2D_cohort |          954 |               755 |                79.1 |                      549 |                       57.5 |
| non_cohort |         7046 |              4485 |                63.7 |                     2864 |                       40.6 | 

**Q3. Year-over-year total paid claims cost, cohort vs. non-cohort (trend view)**

```sql
-- Q3. Year-over-year total paid claims cost, cohort vs. non-cohort (trend view)
WITH grouped AS (
    SELECT
        pt.patient_id,
        CASE WHEN c.patient_id IS NOT NULL THEN 'T2D_cohort' ELSE 'non_cohort' END AS grp
    FROM patients pt
    LEFT JOIN t2d_cohort c ON c.patient_id = pt.patient_id
)
SELECT
    substr(cl.service_date, 1, 4) AS service_year,
    g.grp,
    COUNT(*) AS n_claims,
    ROUND(SUM(cl.paid_amount), 2) AS total_paid
FROM claims cl
JOIN grouped g ON g.patient_id = cl.patient_id
WHERE cl.billed_amount > 0
  AND cl.service_date BETWEEN '2021-01-01' AND '2025-12-31'
GROUP BY service_year, g.grp
ORDER BY service_year, g.grp;
```

|   service_year | grp        |   n_claims |   total_paid |
|---------------:|:-----------|-----------:|-------------:|
|           2021 | T2D_cohort |       1907 |  1.54881e+06 |
|           2021 | non_cohort |       8608 |  6.11813e+06 |
|           2022 | T2D_cohort |       3707 |  2.58205e+06 |
|           2022 | non_cohort |      17528 |  1.30239e+07 |
|           2023 | T2D_cohort |       3467 |  2.459e+06   |
|           2023 | non_cohort |      16174 |  1.11527e+07 |
|           2024 | T2D_cohort |       3377 |  2.46108e+06 |
|           2024 | non_cohort |      15530 |  1.16132e+07 |
|           2025 | T2D_cohort |       3293 |  2.28355e+06 |
|           2025 | non_cohort |      14987 |  1.05076e+07 | 

**Q4. Cost mix by claim type within the T2D cohort (where is the spend actually going?)**

```sql
-- Q4. Cost mix by claim type within the T2D cohort (where is the spend actually going?)
SELECT
    cl.claim_type,
    COUNT(*) AS n_claims,
    ROUND(SUM(cl.paid_amount), 2) AS total_paid,
    ROUND(100.0 * SUM(cl.paid_amount) / (
        SELECT SUM(paid_amount) FROM claims
        WHERE billed_amount > 0
          AND patient_id IN (SELECT patient_id FROM t2d_cohort)
    ), 1) AS pct_of_cohort_spend
FROM claims cl
WHERE cl.billed_amount > 0
  AND cl.patient_id IN (SELECT patient_id FROM t2d_cohort)
GROUP BY cl.claim_type
ORDER BY total_paid DESC;
```

| claim_type         |   n_claims |       total_paid |   pct_of_cohort_spend |
|:-------------------|-----------:|-----------------:|----------------------:|
| hospital_inpatient |        811 |      7.72179e+06 |                  68.1 |
| emergency          |       1571 |      1.79878e+06 |                  15.9 |
| physician          |      10992 |      1.2969e+06  |                  11.4 |
| pharmacy           |       2383 | 518341           |                   4.6 | 


## queries/03_data_quality_checks.sql

**Q1. Summary scorecard: count of each issue type**

```sql
-- Q1. Summary scorecard: count of each issue type
SELECT 'orphan_patient_id' AS issue, COUNT(*) AS n_records
FROM claims
WHERE patient_id NOT IN (SELECT patient_id FROM patients)

UNION ALL

SELECT 'invalid_diagnosis_code', COUNT(*)
FROM claims
WHERE diagnosis_code NOT IN (SELECT diagnosis_code FROM diagnosis_reference)

UNION ALL

SELECT 'non_positive_billed_amount', COUNT(*)
FROM claims
WHERE billed_amount <= 0

UNION ALL

SELECT 'paid_exceeds_billed', COUNT(*)
FROM claims
WHERE paid_amount > billed_amount

UNION ALL

SELECT 'future_dated_service', COUNT(*)
FROM claims
WHERE service_date > '2025-12-31'

UNION ALL

SELECT 'exact_duplicate_claim', COUNT(*)
FROM (
    SELECT patient_id, provider_id, service_date, claim_type,
           diagnosis_code, service_code, billed_amount, paid_amount,
           COUNT(*) AS n
    FROM claims
    GROUP BY patient_id, provider_id, service_date, claim_type,
             diagnosis_code, service_code, billed_amount, paid_amount
    HAVING COUNT(*) > 1
);
```

| issue                      |   n_records |
|:---------------------------|------------:|
| orphan_patient_id          |         262 |
| invalid_diagnosis_code     |         350 |
| non_positive_billed_amount |         175 |
| paid_exceeds_billed        |         529 |
| future_dated_service       |         131 |
| exact_duplicate_claim      |         525 | 

**Q2. Orphan claims (patient_id with no matching patient record)**

```sql
-- Q2. Orphan claims (patient_id with no matching patient record)
SELECT claim_id, patient_id, service_date, claim_type, billed_amount
FROM claims
WHERE patient_id NOT IN (SELECT patient_id FROM patients)
LIMIT 20;
```

|   claim_id |   patient_id | service_date   | claim_type         |   billed_amount |
|-----------:|-------------:|:---------------|:-------------------|----------------:|
|      88054 |         8095 | 2025-08-02     | pharmacy           |          293.68 |
|      88055 |         8188 | 2021-09-11     | emergency          |          174.97 |
|      88056 |         8363 | 2021-07-01     | pharmacy           |           43.62 |
|      88057 |         8124 | 2025-11-04     | hospital_inpatient |          297    |
|      88058 |         8259 | 2022-08-24     | hospital_inpatient |          110.61 |
|      88059 |         8058 | 2025-11-22     | physician          |           82.23 |
|      88060 |         8140 | 2022-04-07     | emergency          |           66.09 |
|      88061 |         8131 | 2024-03-08     | hospital_inpatient |          160.16 |
|      88062 |         8149 | 2024-02-03     | hospital_inpatient |           68.92 |
|      88063 |         8338 | 2024-06-12     | emergency          |           62.45 |
|      88064 |         8214 | 2025-10-16     | emergency          |          201.79 |
|      88065 |         8180 | 2024-07-31     | pharmacy           |           91.17 |
|      88066 |         8434 | 2024-05-01     | hospital_inpatient |          110.78 |
|      88067 |         8362 | 2023-09-20     | emergency          |           83.89 |
|      88068 |         8273 | 2025-03-25     | physician          |          204.59 |
|      88069 |         8484 | 2021-04-28     | pharmacy           |           86.92 |
|      88070 |         8320 | 2022-08-24     | emergency          |          239.72 |
|      88071 |         8448 | 2023-08-07     | emergency          |          152.35 |
|      88072 |         8380 | 2025-05-05     | emergency          |          109.31 |
|      88073 |         8346 | 2025-05-08     | hospital_inpatient |           89.38 | 

**Q3. Invalid / unmapped diagnosis codes, with frequency**

```sql
-- Q3. Invalid / unmapped diagnosis codes, with frequency
SELECT diagnosis_code, COUNT(*) AS n_records
FROM claims
WHERE diagnosis_code NOT IN (SELECT diagnosis_code FROM diagnosis_reference)
GROUP BY diagnosis_code
ORDER BY n_records DESC;
```

| diagnosis_code   |   n_records |
|:-----------------|------------:|
|                  |          96 |
| 9999             |          93 |
| XX99             |          81 |
| E119             |          80 | 

**Q4. Claims with service_date before the enrollment date (flags coverage-window error or miskeyed dates)**

```sql
-- Q4. Claims with service_date before the enrollment date (flags coverage-window error or miskeyed dates)
SELECT cl.claim_id, cl.patient_id, cl.service_date, pt.enrollment_date
FROM claims cl
JOIN patients pt ON pt.patient_id = cl.patient_id
WHERE cl.service_date < pt.enrollment_date
LIMIT 20;
```

|   claim_id |   patient_id | service_date   | enrollment_date   |
|-----------:|-------------:|:---------------|:------------------|
|      88320 |         2713 | 2021-02-21     | 2021-07-31        |
|      88330 |         6031 | 2021-05-07     | 2021-08-16        |
|      88356 |         5559 | 2021-04-04     | 2021-09-09        |
|      88358 |          949 | 2021-02-20     | 2021-02-24        |
|      88361 |         3018 | 2021-05-03     | 2021-09-08        |
|      88364 |         1240 | 2021-06-14     | 2021-11-25        |
|      88377 |         6094 | 2021-08-21     | 2021-12-27        |
|      88379 |         2863 | 2021-01-14     | 2021-07-15        |
|      88381 |         1456 | 2021-04-12     | 2021-05-16        |
|      88387 |         7436 | 2021-02-11     | 2021-03-07        |
|      88388 |          209 | 2021-04-28     | 2021-05-21        |
|      88390 |         4071 | 2021-05-08     | 2021-12-11        |
|      88391 |          623 | 2021-04-02     | 2021-08-20        |
|      88394 |         2103 | 2021-10-16     | 2021-12-31        |
|      88397 |          131 | 2021-06-12     | 2021-08-12        |
|      88407 |         3447 | 2021-11-01     | 2021-11-17        |
|      88415 |         7650 | 2021-03-22     | 2021-10-17        |
|      88423 |         3548 | 2021-01-07     | 2021-03-29        |
|      88435 |         2663 | 2021-03-24     | 2021-10-27        |
|      88447 |         3453 | 2021-08-10     | 2021-09-28        | 

**Q5. Exact duplicate claims (same patient/provider/date/code/amounts appearing more than once)**

```sql
-- Q5. Exact duplicate claims (same patient/provider/date/code/amounts appearing more than once)
SELECT patient_id, provider_id, service_date, claim_type,
       diagnosis_code, service_code, billed_amount, paid_amount,
       COUNT(*) AS n_occurrences
FROM claims
GROUP BY patient_id, provider_id, service_date, claim_type,
         diagnosis_code, service_code, billed_amount, paid_amount
HAVING COUNT(*) > 1
ORDER BY n_occurrences DESC
LIMIT 20;
```

|   patient_id |   provider_id | service_date   | claim_type         | diagnosis_code   | service_code   |   billed_amount |   paid_amount |   n_occurrences |
|-------------:|--------------:|:---------------|:-------------------|:-----------------|:---------------|----------------:|--------------:|----------------:|
|            3 |           116 | 2025-12-12     | physician          | M54              | A001           |          113.33 |        102.2  |               2 |
|           32 |            87 | 2021-08-10     | pharmacy           | S93              | RX02           |          300.77 |        288.71 |               2 |
|           42 |            90 | 2024-08-22     | pharmacy           | I10              | RX02           |           89.75 |         84.89 |               2 |
|           51 |            32 | 2024-01-10     | physician          | I10              | K030           |           81.61 |         78.21 |               2 |
|           54 |           150 | 2024-08-08     | emergency          | M54              | ED01           |          450.55 |        428.59 |               2 |
|           81 |           137 | 2024-05-09     | physician          | I25              | A007           |          193.03 |        175    |               2 |
|          102 |           108 | 2023-04-12     | physician          | J45              | A007           |          115.56 |        101.04 |               2 |
|          102 |           144 | 2023-05-27     | pharmacy           | J06              | RX03           |          444.58 |        382.87 |               2 |
|          109 |           143 | 2024-06-22     | physician          | I10              | K030           |           62.07 |         56.54 |               2 |
|          136 |           145 | 2022-08-25     | physician          | K21              | A888           |          215.36 |        205.49 |               2 |
|          143 |            44 | 2024-04-16     | physician          | Z00              | A888           |           91.62 |         80.95 |               2 |
|          162 |            34 | 2023-04-15     | physician          | Z00              | A001           |           69.94 |         65.41 |               2 |
|          199 |           111 | 2022-11-29     | pharmacy           | S93              | RX03           |          261.82 |        231.61 |               2 |
|          209 |           124 | 2025-01-01     | physician          | M54              | A001           |          106.17 |         99.69 |               2 |
|          226 |           136 | 2022-01-30     | physician          | J06              | A007           |           66.03 |         60.88 |               2 |
|          255 |            33 | 2025-04-17     | physician          | K21              | A001           |           67.24 |         64.44 |               2 |
|          256 |           133 | 2021-05-04     | emergency          | R51              | ED01           |         1295.56 |       1239.08 |               2 |
|          260 |            17 | 2025-06-12     | pharmacy           | R51              | RX03           |          333.61 |        303.86 |               2 |
|          267 |           117 | 2025-08-12     | hospital_inpatient | R51              | H101           |        12298.4  |      11325.8  |               2 |
|          268 |             7 | 2021-12-01     | pharmacy           | Z00              | RX03           |          437.45 |        416.1  |               2 | 

**Q6. Overall data quality rate (share of claims passing every check)**

```sql
-- Q6. Overall data quality rate (share of claims passing every check)
WITH flagged AS (
    SELECT claim_id
    FROM claims
    WHERE patient_id NOT IN (SELECT patient_id FROM patients)
       OR diagnosis_code NOT IN (SELECT diagnosis_code FROM diagnosis_reference)
       OR billed_amount <= 0
       OR paid_amount > billed_amount
       OR service_date > '2025-12-31'
)
SELECT
    (SELECT COUNT(*) FROM claims) AS total_claims,
    (SELECT COUNT(*) FROM flagged) AS flagged_claims,
    ROUND(100.0 * (1 - (SELECT COUNT(*) FROM flagged) * 1.0
          / (SELECT COUNT(*) FROM claims)), 2) AS pct_clean;
```

|   total_claims |   flagged_claims |   pct_clean |
|---------------:|-----------------:|------------:|
|          89146 |             1093 |       98.77 | 

