--sqlite
-- ============================================================
-- 03_data_quality_checks.sql
--
-- Standard QC pass over the raw claims table before analysis: referential integrity, 
-- code validity, duplicate detection, and value-range sanity checks.
-- Run BEFORE 01/02 in a real pipeline, on every data refresh.
-- ============================================================

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

-- Q2. Orphan claims (patient_id with no matching patient record)
SELECT claim_id, patient_id, service_date, claim_type, billed_amount
FROM claims
WHERE patient_id NOT IN (SELECT patient_id FROM patients)
LIMIT 20;

-- Q3. Invalid / unmapped diagnosis codes, with frequency
SELECT diagnosis_code, COUNT(*) AS n_records
FROM claims
WHERE diagnosis_code NOT IN (SELECT diagnosis_code FROM diagnosis_reference)
GROUP BY diagnosis_code
ORDER BY n_records DESC;

-- Q4. Claims with service_date before the enrollment date (flags coverage-window error or miskeyed dates)
SELECT cl.claim_id, cl.patient_id, cl.service_date, pt.enrollment_date
FROM claims cl
JOIN patients pt ON pt.patient_id = cl.patient_id
WHERE cl.service_date < pt.enrollment_date
LIMIT 20;

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