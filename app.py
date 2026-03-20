# app.py
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from database import init_db, load_csv_data, get_db
from sentiment import analyze_sms

app = Flask(__name__)

with app.app_context():
    init_db()
    load_csv_data()

@app.route('/')
def index(): return render_template('dashboard.html')

@app.route('/doctor')
def doctor(): return render_template('doctor.html')

@app.route('/api/patients')
def get_patients():
    conn = get_db(); c = conn.cursor()
    c.execute('''SELECT p.*, s.message AS last_sms, s.final_label AS last_label,
                 s.lexicon_score, s.timestamp AS last_sms_time
                 FROM patients p
                 LEFT JOIN sms_logs s ON s.id=(
                     SELECT id FROM sms_logs WHERE patient_id=p.patient_id
                     ORDER BY timestamp DESC LIMIT 1)
                 ORDER BY s.timestamp IS NULL ASC, s.timestamp DESC,
                 CASE p.status
                     WHEN 'EMERGENCY' THEN 1
                     WHEN 'CONCERNING' THEN 2
                     ELSE 3 END, p.risk_score DESC''')
    rows = c.fetchall(); conn.close()
    return jsonify([{**dict(r),
        'last_sms': r['last_sms'] or 'No SMS yet',
        'last_label': r['last_label'] or 'NORMAL',
        'lexicon_score': r['lexicon_score'] or 0} for r in rows])

@app.route('/api/patients/<patient_id>')
def get_patient(patient_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM patients WHERE patient_id=?', (patient_id,))
    row = c.fetchone(); conn.close()
    return jsonify(dict(row)) if row else (jsonify({'error':'Not found'}), 404)

@app.route('/api/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    pid  = data.get('patient_id', 'PT-1')
    msg  = data.get('message', '').strip()
    if not msg: return jsonify({'error': 'Empty message'}), 400

    result = analyze_sms(msg)
    conn = get_db(); c = conn.cursor()

    c.execute('''INSERT INTO sms_logs
        (patient_id, message, final_label, lexicon_score, nb_label, nb_confidence, agreement)
        VALUES (?,?,?,?,?,?,?)''',
        (pid, msg, result['final_label'],
         result['lexicon']['score'],
         result['naive_bayes']['label'],
         result['naive_bayes']['confidence'],
         1 if result['agreement'] else 0))

    risk = calc_risk(result, pid, c)
    c.execute('UPDATE patients SET status=?, risk_score=? WHERE patient_id=?',
              (result['final_label'], risk, pid))

    if result['final_label'] in ['EMERGENCY', 'CONCERNING']:
        action = 'Ambulance dispatched' if result['final_label'] == 'EMERGENCY' else 'Nurse notified'
        c.execute('INSERT INTO alerts (patient_id, alert_type, message, action_taken) VALUES (?,?,?,?)',
                  (pid, result['final_label'], msg, action))

    conn.commit(); conn.close()
    return jsonify({'success': True, 'patient_id': pid, 'message': msg,
                    'final_label': result['final_label'],
                    'agreement': result['agreement'],
                    'lexicon': result['lexicon'],
                    'naive_bayes': result['naive_bayes'],
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

def calc_risk(result, pid, cursor):
    cursor.execute('SELECT * FROM patients WHERE patient_id=?', (pid,))
    p = cursor.fetchone()
    if not p: return 50
    risk = {'EMERGENCY': 40, 'CONCERNING': 25, 'NORMAL': 5}.get(result['final_label'], 5)
    bp   = p['bp_systolic'] or 120
    risk += 25 if bp > 160 else 18 if bp > 145 else 10 if bp > 130 else 3
    chol = p['cholesterol'] or 200
    risk += 20 if chol > 260 else 14 if chol > 240 else 8 if chol > 200 else 2
    hr   = p['heart_rate'] or 75
    risk += 15 if hr > 100 else 10 if hr > 90 else 5 if hr > 80 else 2
    return min(risk, 99)

@app.route('/api/sms/<patient_id>')
def get_sms(patient_id):
    conn = get_db(); c = conn.cursor()
    c.execute('SELECT * FROM sms_logs WHERE patient_id=? ORDER BY timestamp DESC LIMIT 20', (patient_id,))
    rows = c.fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/alerts')
def get_alerts():
    conn = get_db(); c = conn.cursor()
    c.execute('''SELECT a.*, p.name FROM alerts a
                 JOIN patients p ON a.patient_id=p.patient_id
                 WHERE a.resolved=0 ORDER BY a.timestamp DESC''')
    rows = c.fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stats')
def get_stats():
    conn = get_db(); c = conn.cursor()
    stats = {}
    for key, q in [
        ('emergency',    "SELECT COUNT(*) FROM patients WHERE status='EMERGENCY'"),
        ('concerning',   "SELECT COUNT(*) FROM patients WHERE status='CONCERNING'"),
        ('normal',       "SELECT COUNT(*) FROM patients WHERE status='NORMAL'"),
        ('total',        "SELECT COUNT(*) FROM patients"),
        ('active_alerts',"SELECT COUNT(*) FROM alerts WHERE resolved=0"),
        ('sms_today',    "SELECT COUNT(*) FROM sms_logs WHERE date(timestamp)=date('now')")]:
        c.execute(q); stats[key] = c.fetchone()[0]
    conn.close()
    return jsonify(stats)

# ── DOCTOR REPLY — save and fetch ──

@app.route('/api/doctor-reply', methods=['POST'])
def save_doctor_reply():
    """Doctor sends a reply message to a patient"""
    data = request.get_json()
    pid  = data.get('patient_id', '').strip()
    note = data.get('note', '').strip()
    if not pid or not note:
        return jsonify({'error': 'Missing patient_id or note'}), 400

    conn = get_db(); c = conn.cursor()
    c.execute('INSERT INTO doctor_notes (patient_id, note) VALUES (?,?)', (pid, note))
    conn.commit(); conn.close()
    return jsonify({'success': True,
                    'patient_id': pid,
                    'note': note,
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

@app.route('/api/doctor-reply/<patient_id>')
def get_doctor_replies(patient_id):
    """Patient fetches all doctor replies for their ID"""
    conn = get_db(); c = conn.cursor()
    c.execute('''SELECT * FROM doctor_notes
                 WHERE patient_id=?
                 ORDER BY timestamp DESC LIMIT 20''', (patient_id,))
    rows = c.fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/notes', methods=['POST'])
def add_note():
    data = request.get_json()
    conn = get_db(); c = conn.cursor()
    c.execute('INSERT INTO doctor_notes (patient_id, note) VALUES (?,?)',
              (data.get('patient_id'), data.get('note')))
    conn.commit(); conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    print('\n' + '='*45)
    print('  CardioSense Backend Starting...')
    print('='*45)
    print('  Patient Dashboard -> http://127.0.0.1:5000')
    print('  Doctor Panel      -> http://127.0.0.1:5000/doctor')
    print('='*45 + '\n')
    app.run(debug=True, port=5000)
