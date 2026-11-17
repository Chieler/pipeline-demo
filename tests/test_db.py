from pathlib import Path
from trackb import db


def test_import_idempotent_and_calendar_queries():
    conn = db.connect(':memory:')
    db.initialize(conn)
    db.import_dataset(conn, Path('data/synthetic'))
    first = conn.execute('select count(*) from symptom_observations').fetchone()[0]
    db.import_dataset(conn, Path('data/synthetic'))
    assert conn.execute('select count(*) from symptom_observations').fetchone()[0] == first
    assert conn.execute('select count(*) from reports').fetchone()[0] == 78
    assert conn.execute('select count(*) from medication_events').fetchone()[0] == 3
    assert len(conn.execute("select name from sqlite_master where type='table'").fetchall()) == 4
    daily = db.daily_symptoms(conn, 'SYN-PT-101')
    retrospective = next(r for r in daily if r['date'] == '2026-10-16' and r['symptom'] == 'vomiting')
    assert retrospective['reported'] is False and retrospective['episode_count'] == 2
    assert db.weekly_symptoms(conn, 'SYN-PT-101')
    comparisons = db.medication_comparison(conn, 'SYN-PT-102')
    assert {r['period'] for r in comparisons} == {'before', 'after'}
    assert db.medication_comparison(conn, 'SYN-PT-101') == []


def test_daily_count_reconciliation():
    conn = db.connect(':memory:')
    db.initialize(conn)
    db.import_dataset(conn, Path('data/synthetic'))
    report = conn.execute("select report_id, report_date from reports where patient_id='SYN-PT-101' limit 1").fetchone()
    conn.execute("delete from symptom_observations where report_id=? and symptom='vomiting'", (report['report_id'],))
    def add(ident, source, count, full):
        conn.execute("insert into symptom_observations (observation_id,report_id,source,symptom,presence,episode_count,observed_date,evidence,issues_json,is_full_day) values (?,?,?,'vomiting','present',?,?,?,'[]',?)", (ident, report['report_id'], source, count, report['report_date'], ident, full))
    def daily():
        return next(r for r in db.daily_symptoms(conn, 'SYN-PT-101') if r['date'] == report['report_date'] and r['symptom'] == 'vomiting')
    add('questionnaire', 'questionnaire', 3, 1)
    add('text', 'text', 2, 0)
    assert daily()['episode_count'] == 3 and not daily()['count_excluded']
    conn.execute("update symptom_observations set is_full_day=1 where observation_id='text'")
    assert daily()['episode_count'] is None and daily()['count_excluded']
    conn.execute("update symptom_observations set is_full_day=0,episode_count=4 where observation_id='text'")
    assert daily()['episode_count'] is None and daily()['count_excluded']
    conn.execute("delete from symptom_observations where observation_id='questionnaire'")
    assert daily()['episode_count'] == 4 and not daily()['count_excluded']
    add('second', 'text', 2, 0)
    assert daily()['episode_count'] is None and daily()['count_excluded']


def test_import_marks_presence_and_count_source_conflicts():
    import json
    conn = db.connect(':memory:')
    db.initialize(conn)
    db.import_dataset(conn, Path('data/synthetic'))
    report = conn.execute("select * from reports where report_id='CHK-SYN-PT-101-D21'").fetchone()
    assert report['review_needed']
    assert 'source_conflict' in json.loads(report['issues_json'])
    rows = conn.execute("select * from symptom_observations where report_id=? and symptom='nausea'", (report['report_id'],)).fetchall()
    assert {r['source'] for r in rows} == {'text', 'questionnaire'}
    assert any('source_conflict' in json.loads(r['issues_json']) for r in rows)
    assert next(r for r in db.daily_symptoms(conn, 'SYN-PT-101') if r['date'] == report['report_date'] and r['symptom'] == 'nausea')['presence'] == 'conflict'


def test_vague_vomiting_without_questionnaire_is_excluded():
    conn = db.connect(':memory:')
    db.initialize(conn)
    db.import_dataset(conn, Path('data/synthetic'))
    report = conn.execute("select report_id, report_date from reports where patient_id='SYN-PT-101' limit 1").fetchone()
    conn.execute("delete from symptom_observations where report_id=? and symptom='vomiting'", (report['report_id'],))
    conn.execute("insert into symptom_observations (observation_id,report_id,source,symptom,presence,observed_date,evidence,issues_json) values ('vague',?,'text','vomiting','present',?,'vomited a few times','[]')", (report['report_id'], report['report_date']))
    row = next(r for r in db.daily_symptoms(conn, 'SYN-PT-101') if r['date'] == report['report_date'] and r['symptom'] == 'vomiting')
    assert row['episode_count'] is None and row['count_excluded']


def test_count_conflict_is_persisted(tmp_path):
    import json
    import shutil
    for name in ('patients.json', 'schedule_slots.json', 'check_ins.json', 'medication_events.json'):
        shutil.copy(Path('data/synthetic') / name, tmp_path / name)
    path = tmp_path / 'check_ins.json'
    reports = json.loads(path.read_text())
    reports[0]['free_text_report'] = 'Vomited four times today.'
    reports[0]['questionnaire_responses']['reported_vomiting_episodes'] = 2
    path.write_text(json.dumps(reports))
    conn = db.connect(':memory:')
    db.initialize(conn)
    db.import_dataset(conn, tmp_path)
    report = conn.execute('select * from reports where report_id=?', (reports[0]['checkin_id'],)).fetchone()
    assert report['review_needed'] and 'source_conflict' in json.loads(report['issues_json'])
    rows = conn.execute("select issues_json from symptom_observations where report_id=? and symptom='vomiting'", (report['report_id'],)).fetchall()
    assert all('source_conflict' in json.loads(row['issues_json']) for row in rows)
    reports[0]['free_text_report'] = 'Vomited a few times today.'
    reports[0]['questionnaire_responses']['reported_vomiting_episodes'] = 0
    path.write_text(json.dumps(reports))
    other = db.connect(':memory:')
    db.initialize(other)
    db.import_dataset(other, tmp_path)
    daily = next(r for r in db.daily_symptoms(other, reports[0]['patient_id']) if r['date'] == reports[0]['submission_timestamp'][:10] and r['symptom'] == 'vomiting')
    assert daily['presence'] == 'conflict' and daily['count_excluded'] and daily['episode_count'] is None


def test_daywide_absence_conflicts_with_positive_questionnaire(tmp_path):
    import json
    import shutil
    for name in ('patients.json', 'schedule_slots.json', 'check_ins.json', 'medication_events.json'):
        shutil.copy(Path('data/synthetic') / name, tmp_path / name)
    path = tmp_path / 'check_ins.json'
    reports = json.loads(path.read_text())
    reports[0]['free_text_report'] = 'No vomiting today.'
    reports[0]['questionnaire_responses']['reported_vomiting_episodes'] = 2
    path.write_text(json.dumps(reports))
    conn = db.connect(':memory:')
    db.initialize(conn)
    db.import_dataset(conn, tmp_path)
    report = conn.execute('select * from reports where report_id=?', (reports[0]['checkin_id'],)).fetchone()
    assert 'source_conflict' in json.loads(report['issues_json'])
    daily = next(r for r in db.daily_symptoms(conn, reports[0]['patient_id']) if r['date'] == report['report_date'] and r['symptom'] == 'vomiting')
    assert daily['presence'] == 'conflict' and daily['count_excluded']
