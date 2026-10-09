"""
Synthetic administrative health claims data.
 
Generates a SQLite database (claims_data.db) that mimics the structure of Canadian 
physician/hospital billing claims data (e.g. OHIP/CIHI-style), including realistic patient 
enrollment patterns, provider billing, and deliberately injected data quality issues
"""

import random
import sqlite3
from datetime import date, timedelta

random.seed(42)
DB_PATH = "data/claims_data.db"
N_PATIENTS = 8000
N_PROVIDERS = 150
STUDY_START = date(2021, 1, 1)
STUDY_END = date(2025, 12, 31)

REGIONS = ["Toronto", "Ottawa", "Mississauga", "Waterloo", "Hamilton", "London"]
SPECIALTIES = [
    "Family Medicine", "Endocrinology", "Internal Medicine",
    "Cardiology", "Emergency Medicine", "General Surgery", "Nephrology",
]
# ICD-10-CA-style diagnosis codes with a chronic-disease flag.
DIAGNOSIS_REF = [
    ("E11", "Type 2 diabetes mellitus", 1),
    ("E10", "Type 1 diabetes mellitus", 1),
    ("I10", "Essential (primary) hypertension", 1),
    ("I25", "Chronic ischemic heart disease", 1),
    ("J45", "Asthma", 1),
    ("N18", "Chronic kidney disease", 1),
    ("J06", "Acute upper respiratory infection", 0),
    ("M54", "Dorsalgia (back pain)", 0),
    ("R51", "Headache", 0),
    ("S93", "Ankle sprain", 0),
    ("Z00", "General health examination", 0),
    ("K21", "Gastro-esophageal reflux disease", 0),
]
CLAIM_TYPES = ["physician", "hospital_inpatient", "emergency", "pharmacy"]
CLAIM_TYPE_WEIGHTS = [0.70, 0.05, 0.10, 0.15]
SERVICE_CODES = {
    "physician": ["A001", "A007", "A888", "K005", "K030"],
    "hospital_inpatient": ["H101", "H102", "H150"],
    "emergency": ["ED01", "ED02"],
    "pharmacy": ["RX01", "RX02", "RX03"],
}

def random_date(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))
 
def build_reference_tables(cur):
    cur.execute("""
        CREATE TABLE diagnosis_reference (
            diagnosis_code TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            chronic_flag INTEGER NOT NULL
        )
    """)
    cur.executemany(
        "INSERT INTO diagnosis_reference VALUES (?, ?, ?)", DIAGNOSIS_REF
    )
 
    cur.execute("""
        CREATE TABLE providers (
            provider_id INTEGER PRIMARY KEY,
            specialty TEXT NOT NULL,
            region TEXT NOT NULL
        )
    """)
    providers = [
        (pid, random.choice(SPECIALTIES), random.choice(REGIONS))
        for pid in range(1, N_PROVIDERS + 1)
    ]
    cur.executemany("INSERT INTO providers VALUES (?, ?, ?)", providers)

def build_patients(cur):
    cur.execute("""
        CREATE TABLE patients (
            patient_id INTEGER PRIMARY KEY,
            birth_year INTEGER NOT NULL,
            sex TEXT NOT NULL,
            region TEXT NOT NULL,
            enrollment_date TEXT NOT NULL,
            disenrollment_date TEXT
        )
    """)
    rows = []
    for pid in range(1, N_PATIENTS + 1):
        birth_year = random.randint(1935, 2015)
        sex = random.choice(["F", "M"])
        region = random.choice(REGIONS)
        enrollment = random_date(STUDY_START, STUDY_START + timedelta(days=365))
        # ~8% disenroll partway through (moved away, plan change, etc.)
        disenroll = None
        if random.random() < 0.08:
            disenroll = random_date(enrollment + timedelta(days=180), STUDY_END)
            disenroll = disenroll.isoformat()
        rows.append((pid, birth_year, sex, region, enrollment.isoformat(), disenroll))
    cur.executemany("INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?)", rows)
    return rows

def assign_chronic_conditions(patient_rows):
    """Assign each patient a small set of chronic conditions they'll generate
    recurring claims for, at roughly realistic prevalence."""
    chronic_codes = [c for c, _, flag in DIAGNOSIS_REF if flag == 1]
    assignments = {}
    for pid, birth_year, *_ in patient_rows:
        age = 2023 - birth_year
        conditions = []
        # Diabetes prevalence rises with age; ~11% baseline, higher if older
        diabetes_p = 0.06 if age < 45 else (0.14 if age < 65 else 0.22)
        if random.random() < diabetes_p:
            conditions.append("E11")
        if random.random() < 0.20 + (0.15 if age > 60 else 0):
            conditions.append("I10")
        if random.random() < 0.05 and age > 50:
            conditions.append("I25")
        if random.random() < 0.07:
            conditions.append("J45")
        if random.random() < 0.03 and age > 55:
            conditions.append("N18")
        assignments[pid] = conditions
    return assignments

def build_claims(cur, patient_rows, chronic_map):
    cur.execute("""
        CREATE TABLE claims (
            claim_id INTEGER PRIMARY KEY,
            patient_id INTEGER,
            provider_id INTEGER,
            service_date TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            diagnosis_code TEXT,
            service_code TEXT,
            billed_amount REAL,
            paid_amount REAL
        )
    """)
 
    acute_codes = [c for c, _, flag in DIAGNOSIS_REF if flag == 0]
    claim_id = 1
    rows = []
 
    for pid, birth_year, sex, region, enrollment_s, disenroll_s in patient_rows:
        enrollment = date.fromisoformat(enrollment_s)
        window_end = date.fromisoformat(disenroll_s) if disenroll_s else STUDY_END
        if window_end <= enrollment:
            continue
 
        conditions = chronic_map[pid]
        # Baseline number of routine visits over the whole study window
        n_baseline_visits = random.randint(2, 10)
        # Chronic-disease patients generate extra recurring claims per condition
        n_chronic_visits = sum(random.randint(3, 9) for _ in conditions)
        # Occasional acute/one-off visits
        n_acute_visits = random.randint(0, 4)
 
        total_visits = n_baseline_visits + n_chronic_visits + n_acute_visits
 
        for _ in range(total_visits):
            svc_date = random_date(enrollment, window_end)
            if conditions and random.random() < 0.55:
                dx = random.choice(conditions)
            else:
                dx = random.choice(acute_codes + ["Z00"])
 
            ctype = random.choices(CLAIM_TYPES, weights=CLAIM_TYPE_WEIGHTS)[0]
            scode = random.choice(SERVICE_CODES[ctype])
 
            if ctype == "hospital_inpatient":
                billed = round(random.uniform(3000, 18000), 2)
            elif ctype == "emergency":
                billed = round(random.uniform(300, 2200), 2)
            elif ctype == "pharmacy":
                billed = round(random.uniform(15, 450), 2)
            else:
                billed = round(random.uniform(35, 220), 2)
 
            paid = round(billed * random.uniform(0.85, 1.0), 2)
 
            rows.append((
                claim_id, pid, random.randint(1, N_PROVIDERS),
                svc_date.isoformat(), ctype, dx, scode, billed, paid,
            ))
            claim_id += 1
 
    # ---- Inject deliberate data quality issues -----------------------
    n_clean = len(rows)
 
    # 1. Duplicate claims (~0.6%): same details, new claim_id
    dup_sample = random.sample(rows, k=int(n_clean * 0.006))
    for r in dup_sample:
        rows.append((claim_id, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]))
        claim_id += 1
 
    # 2. Orphan claims (~0.3%): patient_id that doesn't exist in patients table
    for _ in range(int(n_clean * 0.003)):
        fake_pid = N_PATIENTS + random.randint(1, 500)
        svc_date = random_date(STUDY_START, STUDY_END)
        ctype = random.choice(CLAIM_TYPES)
        rows.append((
            claim_id, fake_pid, random.randint(1, N_PROVIDERS),
            svc_date.isoformat(), ctype, random.choice(acute_codes),
            random.choice(SERVICE_CODES[ctype]), round(random.uniform(30, 300), 2),
            round(random.uniform(30, 300), 2),
        ))
        claim_id += 1
 
    # 3. Invalid diagnosis codes not present in diagnosis_reference (~0.4%)
    invalid_codes = ["E119", "XX99", "9999", ""]
    for _ in range(int(n_clean * 0.004)):
        pid = random.randint(1, N_PATIENTS)
        svc_date = random_date(STUDY_START, STUDY_END)
        ctype = random.choice(CLAIM_TYPES)
        rows.append((
            claim_id, pid, random.randint(1, N_PROVIDERS), svc_date.isoformat(),
            ctype, random.choice(invalid_codes), random.choice(SERVICE_CODES[ctype]),
            round(random.uniform(30, 300), 2), round(random.uniform(30, 300), 2),
        ))
        claim_id += 1
 
    # 4. Negative or zero billed amounts (~0.2%)
    for _ in range(int(n_clean * 0.002)):
        pid = random.randint(1, N_PATIENTS)
        svc_date = random_date(STUDY_START, STUDY_END)
        ctype = random.choice(CLAIM_TYPES)
        bad_amount = random.choice([0, -round(random.uniform(10, 200), 2)])
        rows.append((
            claim_id, pid, random.randint(1, N_PROVIDERS), svc_date.isoformat(),
            ctype, random.choice(acute_codes), random.choice(SERVICE_CODES[ctype]),
            bad_amount, bad_amount,
        ))
        claim_id += 1
 
    # 5. Future-dated services (data entry errors) (~0.15%)
    for _ in range(int(n_clean * 0.0015)):
        pid = random.randint(1, N_PATIENTS)
        future_date = STUDY_END + timedelta(days=random.randint(30, 400))
        ctype = random.choice(CLAIM_TYPES)
        rows.append((
            claim_id, pid, random.randint(1, N_PROVIDERS), future_date.isoformat(),
            ctype, random.choice(acute_codes), random.choice(SERVICE_CODES[ctype]),
            round(random.uniform(30, 300), 2), round(random.uniform(30, 300), 2),
        ))
        claim_id += 1
 
    # 6. paid_amount exceeding billed_amount (~0.2%)
    for _ in range(int(n_clean * 0.002)):
        pid = random.randint(1, N_PATIENTS)
        svc_date = random_date(STUDY_START, STUDY_END)
        ctype = random.choice(CLAIM_TYPES)
        billed = round(random.uniform(30, 300), 2)
        paid = round(billed * random.uniform(1.1, 1.5), 2)
        rows.append((
            claim_id, pid, random.randint(1, N_PROVIDERS), svc_date.isoformat(),
            ctype, random.choice(acute_codes), random.choice(SERVICE_CODES[ctype]),
            billed, paid,
        ))
        claim_id += 1
 
    random.shuffle(rows)
    cur.executemany(
        "INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
    )
    return len(rows)
 
 
def main():
    import os
    os.makedirs("data", exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
 
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
 
    build_reference_tables(cur)
    patient_rows = build_patients(cur)
    chronic_map = assign_chronic_conditions(patient_rows)
    n_claims = build_claims(cur, patient_rows, chronic_map)
 
    conn.commit()
    conn.close()
 
    print(f"Generated {N_PATIENTS} patients, {N_PROVIDERS} providers, "
          f"{n_claims} claims -> {DB_PATH}")
 
 
if __name__ == "__main__":
    main()
 