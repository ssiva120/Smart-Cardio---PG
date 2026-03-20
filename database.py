# database.py
import sqlite3, os, csv
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'cardiosense.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        age INTEGER,
        gender TEXT,
        heart_rate INTEGER,
        bp_systolic INTEGER,
        bp_diastolic INTEGER,
        cholesterol INTEGER,
        risk_score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'NORMAL',
        doctor_feedback TEXT,
        sentiment TEXT,
        alert_level TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sms_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        message TEXT NOT NULL,
        final_label TEXT NOT NULL,
        lexicon_score REAL,
        nb_label TEXT,
        nb_confidence REAL,
        agreement INTEGER DEFAULT 1,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        acknowledged INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        alert_type TEXT NOT NULL,
        message TEXT,
        action_taken TEXT,
        resolved INTEGER DEFAULT 0,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS doctor_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        doctor_id TEXT DEFAULT 'DOC-01',
        note TEXT NOT NULL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()
    print("Database tables created!")

def load_csv_data():
    csv_path = os.path.join(BASE_DIR, 'cardio.csv')
    if not os.path.exists(csv_path):
        print("cardio.csv not found - no data loaded")
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM patients")
    if c.fetchone()[0] > 0:
        conn.close()
        return

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))

        loaded = 0
        for i, row in enumerate(rows):
            pid = str(row.get('Patient_ID', 'PT-' + str(i+1))).strip()
            name = 'Patient ' + pid
            gender = str(row.get('Gender', 'Unknown')).strip()
            if gender not in ['Male', 'Female']:
                gender = 'Unknown'

            sentiment   = str(row.get('Sentiment', 'NORMAL')).strip().upper()
            alert_level = str(row.get('Alert_Level', '')).strip()
            feedback    = str(row.get('Doctor_Feedback', '')).strip()

            if 'CALL DOCTOR' in alert_level.upper() or 'EMERGENCY' in alert_level.upper():
                status = 'EMERGENCY'
            elif 'NURSE' in alert_level.upper() or 'CONCERNING' in sentiment:
                status = 'CONCERNING'
            else:
                status = 'NORMAL'

            try:
                bp   = int(float(row.get('BP_Systolic', 120)))
                hr   = int(float(row.get('Heart_Rate', 75)))
                chol = int(float(row.get('Cholesterol_Level', 200)))
                bd   = int(float(row.get('BP_Diastolic', 80)))
                age  = int(float(row.get('Age', 0)))
                risk = 0
                risk += 25 if bp   > 160 else 18 if bp   > 145 else 10 if bp   > 130 else 3
                risk += 15 if hr   > 100 else 10 if hr   > 90  else 5  if hr   > 80  else 2
                risk += 20 if chol > 260 else 14 if chol > 240 else 8  if chol > 200 else 2
                if status == 'EMERGENCY':    risk = min(risk + 40, 99)
                elif status == 'CONCERNING': risk = min(risk + 20, 99)
            except:
                bp, hr, chol, bd, age, risk = 120, 75, 200, 80, 0, 30

            try:
                c.execute('''INSERT OR IGNORE INTO patients
                    (patient_id, name, age, gender, heart_rate,
                     bp_systolic, bp_diastolic, cholesterol,
                     risk_score, status, doctor_feedback, sentiment, alert_level)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (pid, name, age, gender, hr, bp, bd,
                     chol, risk, status, feedback, sentiment, alert_level))

                
                if status in ['EMERGENCY', 'CONCERNING']:
                    action = 'Ambulance dispatched' if status == 'EMERGENCY' else 'Nurse notified'
                    c.execute('''INSERT INTO alerts (patient_id, alert_type, message, action_taken)
                        VALUES (?,?,?,?)''',
                        (pid, status, feedback or alert_level, action))

                loaded += 1
            except Exception as e:
                print('Row ' + str(i+1) + ' skipped: ' + str(e))

        conn.commit()
        print('Loaded ' + str(loaded) + ' patients from cardio.csv')

    except Exception as e:
        print('CSV load error: ' + str(e))
    finally:
        conn.close()
