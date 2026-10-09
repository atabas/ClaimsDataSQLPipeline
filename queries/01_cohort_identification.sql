--sqlite
-- ============================================================
-- 01_cohort_identification.sql
-- Requires 00_create_views.sql to run first.
--
-- Applies the t2d_cohort view (see 00_create_views.sql) and profiles the resulting cohort:
-- size, share of the population, and basic demographic breakdown; this is a first-pass output 
-- sanity check before using a cohort in a downstream study.
-- ============================================================

-- Q1. Cohort size and share of the enrolled population
SELECT
    (SELECT COUNT(*) FROM t2d_cohort)                    AS t2d_cohort_size,
    (SELECT COUNT(*) FROM patients)                       AS total_patients,
    ROUND(100.0 * (SELECT COUNT(*) FROM t2d_cohort)
          / (SELECT COUNT(*) FROM patients), 2)           AS pct_of_population;

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

-- Q4. Cohort distribution by region (regional access/resourcing view)
SELECT
    pt.region,
    COUNT(*) AS n_cohort_patients
FROM patients pt
JOIN t2d_cohort c ON c.patient_id = pt.patient_id
GROUP BY pt.region
ORDER BY n_cohort_patients DESC;