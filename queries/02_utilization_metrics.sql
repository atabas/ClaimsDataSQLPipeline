--sqlite
-- ============================================================
-- 02_utilization_metrics.sql
-- Requires 00_create_views.sql to have been run first.
--
-- Compares healthcare utilization and cost between the T2D
-- cohort and the rest of the population - "burden of illness" comparison
-- ============================================================

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