"""SQLite storage and descriptive summaries of documented observations."""
import json
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from .parser import parse_report


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def initialize(conn):
    conn.executescript(Path(__file__).with_name('schema.sql').read_text())


def import_dataset(conn, data_dir):
    path = Path(data_dir)
    def read(name):
        return json.loads((path / name).read_text())
    patients, slots, reports, meds = (read(name) for name in ('patients.json', 'schedule_slots.json', 'check_ins.json', 'medication_events.json'))
    dates = defaultdict(list)
    for slot in slots:
        dates[slot['patient_id']].append(slot['scheduled_date'])
    with conn:
        for p in patients:
            days = dates[p['patient_id']]
            conn.execute('INSERT OR IGNORE INTO patients VALUES (?,?,?,?,?)', (p['patient_id'], p['pseudonym'], p['age'], min(days), max(days)))
        for report in reports:
            report_id = report['checkin_id']
            if conn.execute('SELECT 1 FROM reports WHERE report_id=?', (report_id,)).fetchone():
                continue
            rows = parse_report(report)
            issues = [issue for row in rows for issue in row['issues_json']]
            conn.execute('INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?,?)', (report_id, report['patient_id'], report['submission_timestamp'], report['submission_timestamp'][:10], report['free_text_report'], json.dumps(report['questionnaire_responses']), '1', bool(issues), json.dumps(issues), json.dumps({'status': 'not_run'})))
            for i, row in enumerate(rows):
                conn.execute('INSERT INTO symptom_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (f'{report_id}:{i}', report_id, row['source'], row['symptom'], row['original_phrase'], row['presence'], row['severity_value'], row['severity_scale'], row['severity_text'], row['episode_count'], row['observed_date'], row['timing_text'], row['medication_mentioned'], row['evidence'], json.dumps(row['issues_json']), row['is_full_day'], row['count_eligible']))
        for m in meds:
            if m['status'] in ('started', 'discontinued'):
                conn.execute('INSERT OR IGNORE INTO medication_events VALUES (?,?,?,?,?,?,?,?)', (m['med_event_id'], m['patient_id'], None, m['drug_name'], m.get('dose'), m['date'], 'start' if m['status'] == 'started' else 'stop', 'structured_fixture'))
        _mark_source_conflicts(conn)
    return {'patients': len(patients), 'reports': len(reports), 'schedule_slots': len(slots), 'medication_events': sum(m['status'] in ('started', 'discontinued') for m in meds)}


def _mark_source_conflicts(conn):
    observations = conn.execute('SELECT o.*, r.patient_id FROM symptom_observations o JOIN reports r USING(report_id) WHERE o.observed_date IS NOT NULL').fetchall()
    groups = defaultdict(list)
    for row in observations:
        groups[(row['patient_id'], row['observed_date'], row['symptom'])].append(row)
    for rows in groups.values():
        questionnaires = [r for r in rows if r['source'] == 'questionnaire']
        texts = [r for r in rows if r['source'] == 'text']
        for q in questionnaires:
            for t in texts:
                presence_conflict = (q['presence'] == 'absent' and t['presence'] == 'present') or (q['presence'] == 'present' and t['presence'] == 'absent' and t['is_full_day'])
                count_conflict = q['episode_count'] is not None and t['episode_count'] is not None and (t['episode_count'] > q['episode_count'] or (t['is_full_day'] and t['episode_count'] != q['episode_count']))
                if not (presence_conflict or count_conflict):
                    continue
                for row in (q, t):
                    issues = json.loads(row['issues_json'])
                    if 'source_conflict' not in issues:
                        issues.append('source_conflict')
                        conn.execute('UPDATE symptom_observations SET issues_json=? WHERE observation_id=?', (json.dumps(issues), row['observation_id']))
                    report = conn.execute('SELECT issues_json FROM reports WHERE report_id=?', (row['report_id'],)).fetchone()
                    report_issues = json.loads(report['issues_json'])
                    if 'source_conflict' not in report_issues:
                        report_issues.append('source_conflict')
                    conn.execute('UPDATE reports SET review_needed=1, issues_json=? WHERE report_id=?', (json.dumps(report_issues), row['report_id']))


def daily_symptoms(conn, patient_id):
    patient = conn.execute('SELECT * FROM patients WHERE patient_id=?', (patient_id,)).fetchone()
    if not patient:
        return []
    reports = conn.execute('SELECT report_date FROM reports WHERE patient_id=?', (patient_id,)).fetchall()
    reported = {r['report_date'] for r in reports}
    observations = conn.execute('SELECT o.* FROM symptom_observations o JOIN reports r USING(report_id) WHERE r.patient_id=?', (patient_id,)).fetchall()
    grouped = defaultdict(list)
    for obs in observations:
        if obs['observed_date']:
            grouped[(obs['observed_date'], obs['symptom'])].append(obs)
    symptoms = sorted({o['symptom'] for o in observations})
    start, end = date.fromisoformat(patient['start_date']), date.fromisoformat(patient['end_date'])
    result = []
    for offset in range((end - start).days + 1):
        day = (start + timedelta(days=offset)).isoformat()
        for symptom in symptoms:
            obs = grouped[(day, symptom)]
            q = [o for o in obs if o['source'] == 'questionnaire']
            texts = [o for o in obs if o['source'] == 'text']
            present = 'present' if any(o['presence'] == 'present' for o in obs) else ('uncertain' if any(o['presence'] == 'uncertain' for o in obs) else ('absent' if obs else None))
            if any(qr['presence'] == 'absent' and tr['presence'] == 'present' or qr['presence'] == 'present' and tr['presence'] == 'absent' and tr['is_full_day'] for qr in q for tr in texts):
                present = 'conflict'
            claims = {(o['report_id'], o['evidence'], o['episode_count'], o['is_full_day'], o['count_eligible']) for o in texts if o['episode_count'] is not None}
            qcounts = [o['episode_count'] for o in q if o['episode_count'] is not None]
            count, excluded = None, False
            if qcounts:
                count = qcounts[0]
                excluded = len(set(qcounts)) > 1 or any(not eligible or n > count or (full and n != count) for _, _, n, full, eligible in claims)
            elif len(claims) == 1:
                _, _, count, _, eligible = next(iter(claims))
                excluded = not eligible
            elif len(claims) > 1:
                excluded = True
            elif symptom == 'vomiting' and present == 'present' and not qcounts:
                excluded = True
            if symptom == 'vomiting' and present == 'conflict':
                excluded = True
            if excluded:
                count = None
            result.append(dict(date=day, symptom=symptom, presence=present, episode_count=count, count_excluded=excluded, reported=day in reported, source='questionnaire+text' if q and texts else ('questionnaire' if q else ('text' if texts else None))))
    return result


def weekly_symptoms(conn, patient_id):
    daily = daily_symptoms(conn, patient_id)
    if not daily:
        return []
    start = date.fromisoformat(daily[0]['date'])
    grouped = defaultdict(list)
    for row in daily:
        week = (date.fromisoformat(row['date']) - start).days // 7 + 1
        grouped[(week, row['symptom'])].append(row)
    return [dict(week=week, symptom=symptom, present_days=sum(r['presence'] == 'present' for r in rows), documented_episodes=sum(r['episode_count'] for r in rows if r['episode_count'] is not None), counted_days=sum(r['episode_count'] is not None for r in rows), excluded_count_days=sum(r['count_excluded'] for r in rows), reported_days=sum(r['reported'] for r in rows), scheduled_days=len(rows)) for (week, symptom), rows in sorted(grouped.items())]


def medication_comparison(conn, patient_id):
    # A regimen switch has both a stop and a start on the same date.
    anchor = conn.execute("SELECT effective_date FROM medication_events WHERE patient_id=? GROUP BY effective_date HAVING COUNT(DISTINCT event_type)=2 ORDER BY effective_date LIMIT 1", (patient_id,)).fetchone()
    if not anchor:
        return []
    day = date.fromisoformat(anchor['effective_date'])
    daily = daily_symptoms(conn, patient_id)
    result = []
    for period, start, end in [('before', day - timedelta(days=7), day - timedelta(days=1)), ('after', day + timedelta(days=1), day + timedelta(days=7))]:
        grouped = defaultdict(list)
        for row in daily:
            if start.isoformat() <= row['date'] <= end.isoformat():
                grouped[row['symptom']].append(row)
        for symptom, rows in sorted(grouped.items()):
            result.append(dict(period=period, start_date=start.isoformat(), end_date=end.isoformat(), symptom=symptom, present_days=sum(r['presence'] == 'present' for r in rows), documented_episodes=sum(r['episode_count'] for r in rows if r['episode_count'] is not None), reported_days=sum(r['reported'] for r in rows), scheduled_days=len(rows)))
    return result
