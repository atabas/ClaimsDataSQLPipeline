-- sqlite
-- ============================================================
-- 00_create_views.sql
--
-- Defines a reusable cohort view: patients meeting a Type 2 diabetes (T2D) case-finding algorithm,
-- modeled on logic by administrative-data algorithms such as the Ontario Diabetes Database (ODD):
--
--   A patient is classified as having T2D if they have:
--     (a) >= 2 physician claims with a T2D diagnosis (E11),
--         at least 30 days but no more than 730 days apart, OR
--     (b) >= 1 hospitalization with a T2D diagnosis (E11)
--
-- This two-claim / one-hospitalization pattern is to avoid classifying a 
-- single miscoded or rule-out visit as a true chronic-disease case.
-- ============================================================

DROP VIEW IF EXISTS t2d_physician_claim_pairs;
DROP VIEW IF EXISTS t2d_cohort;

CREATE VIEW t2d_physician_claim_pairs AS
WITH t2d_physician_claims AS (
    SELECT patient_id, service_date
    FROM claims
    WHERE diagnosis_code = 'E11'
      AND claim_type = 'physician'
),
ordered AS (
    SELECT
        patient_id,
        service_date,
        LAG(service_date) OVER (
            PARTITION BY patient_id ORDER BY service_date
        ) AS prev_service_date
    FROM t2d_physician_claims
)
SELECT DISTINCT patient_id
FROM ordered
WHERE prev_service_date IS NOT NULL
  AND julianday(service_date) - julianday(prev_service_date) BETWEEN 30 AND 730;

CREATE VIEW t2d_cohort AS
SELECT patient_id FROM t2d_physician_claim_pairs
UNION
SELECT DISTINCT patient_id
FROM claims
WHERE diagnosis_code = 'E11'
  AND claim_type = 'hospital_inpatient';