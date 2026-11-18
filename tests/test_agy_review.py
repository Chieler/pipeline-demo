import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from trackb.agy_review import review_batch, process_pending, effective_observations, fingerprint, seed_benchmark_cache, review_status
from trackb.db import connect, initialize, import_dataset, daily_symptoms

DATA = Path(__file__).resolve().parents[1] / "data/synthetic"


def test_batch_review_is_grounded_text_only_and_does_not_invoke_a_shell():
    report = {"report_id": "one", "raw_text": "My ears are ringing.", "submitted_at": "2026-10-17T08:30:00", "questionnaire_json": '{"private_questionnaire": 8}'}
    payload = {"reports": [{"report_id": "one", "observations": [{"symptom": "tinnitus", "presence": "present", "evidence_quote": "ears are ringing"}]}]}
    response = subprocess.CompletedProcess([], 0, json.dumps({"status": "SUCCESS", "response": json.dumps(payload)}), "")
    with patch("trackb.agy_review.shutil.which", return_value="/bin/agy"), patch("trackb.agy_review.subprocess.run", return_value=response) as run:
        result = review_batch([report], {"one": []})
        assert result["one"]["status"] == "reviewed"
        assert "private_questionnaire" not in run.call_args.args[0][2]
        assert run.call_args.kwargs["shell"] is False
    payload["reports"][0]["observations"][0]["evidence_quote"] = "not in the report"
    response.stdout = json.dumps({"status": "SUCCESS", "response": json.dumps(payload)})
    with patch("trackb.agy_review.shutil.which", return_value="/bin/agy"), patch("trackb.agy_review.subprocess.run", return_value=response):
        assert review_batch([report], {"one": []})["one"]["status"] == "invalid"


def test_missing_cli_or_timeout_preserves_local_pipeline():
    report = {"report_id": "one", "raw_text": "Fine.", "submitted_at": "2026-10-17"}
    with patch("trackb.agy_review.shutil.which", return_value=None):
        assert review_batch([report], {"one": []})["one"]["status"] == "unavailable"
    with patch("trackb.agy_review.shutil.which", return_value="/bin/agy"), patch("trackb.agy_review.subprocess.run", side_effect=subprocess.TimeoutExpired("agy", 600)):
        assert review_batch([report], {"one": []})["one"]["status"] == "unavailable"


def test_automatic_review_changes_presence_but_preserves_numeric_analytics(tmp_path):
    conn = connect(tmp_path / "review.sqlite")
    initialize(conn)
    import_dataset(conn, DATA)
    report_id = "CHK-SYN-PT-103-D11"
    original = conn.execute("SELECT * FROM symptom_observations").fetchall()
    before = [(r['date'], r['episode_count'], r['count_excluded']) for r in daily_symptoms(conn, "SYN-PT-103") if r['symptom'] == 'vomiting']
    calls = []
    def fake_review(reports, local):
        calls.append(len(reports))
        result = {}
        for report in reports:
            rows = [{"symptom": row['symptom'], "presence": row['presence'], "evidence_quote": row['evidence']}
                    for row in local[report['report_id']] if row['source'] == 'text']
            if report['report_id'] == report_id:
                rows = [row for row in rows if row['symptom'] != 'vomiting']
                rows.append({"symptom": "tinnitus", "presence": "present", "evidence_quote": "ringing"})
            result[report['report_id']] = {"status": "reviewed", "observations": rows,
                "source_fingerprint": fingerprint(report, local[report['report_id']])}
        return result
    process_pending(conn, reviewer=fake_review, seed_cache=False)
    assert sum(calls) == 78
    assert any(row['symptom'] == 'tinnitus' and row['presence'] == 'present' for row in daily_symptoms(conn, 'SYN-PT-103'))
    assert any(row.get('review_origin') == 'agy' for row in effective_observations(conn, report_id=report_id))
    assert not any(row['source'] == 'text' and row['symptom'] == 'vomiting' for row in effective_observations(conn, report_id=report_id))
    assert conn.execute("SELECT * FROM symptom_observations").fetchall() == original
    assert [(r['date'], r['episode_count'], r['count_excluded']) for r in daily_symptoms(conn, 'SYN-PT-103') if r['symptom'] == 'vomiting'] == before
    calls.clear()
    process_pending(conn, reviewer=fake_review, seed_cache=False)
    assert calls == []
    conn.execute("UPDATE reports SET raw_text=raw_text || ' Changed.' WHERE report_id=?", (report_id,))
    conn.commit()
    process_pending(conn, reviewer=fake_review, seed_cache=False)
    assert calls == [1]
    conn.close()


def test_saved_benchmark_review_is_reused_without_calling_a_model(tmp_path):
    conn = connect(tmp_path / 'cache.sqlite')
    initialize(conn)
    import_dataset(conn, DATA)
    seed_benchmark_cache(conn)
    assert review_status(conn) == {'total': 78, 'reviewed': 26, 'pending': 52, 'failed': 0}
    assert any(row['symptom'] == 'tinnitus' for row in effective_observations(conn, patient_id='SYN-PT-103'))
    conn.close()


def test_existing_database_migration_preserves_reports(tmp_path):
    conn = connect(tmp_path / "old.sqlite")
    schema = (Path(__file__).resolve().parents[1] / "trackb/schema.sql").read_text()
    conn.executescript(schema.replace(", symptom_review_json TEXT NOT NULL DEFAULT '{\"status\":\"not_run\"}'", ""))
    conn.execute("INSERT INTO patients VALUES ('one','Patient',50,'2026-10-01','2026-10-28')")
    conn.execute("INSERT INTO reports VALUES ('report','one','2026-10-17','2026-10-17','Original message','{}','1',0,'[]','{}')")
    conn.commit()
    initialize(conn)
    initialize(conn)
    assert conn.execute("SELECT raw_text FROM reports").fetchone()[0] == 'Original message'
    conn.close()


def test_new_symptoms_use_local_date_rules_not_model_dates():
    from trackb.parser import resolve_review_date
    assert resolve_review_date('Yesterday my ears were ringing. Today is better.', 'ears were ringing', '2026-10-17') == '2026-10-16'
    assert resolve_review_date('Yesterday and today my ears were ringing.', 'ears were ringing', '2026-10-17') is None
    assert resolve_review_date('My ears have been ringing since Monday.', 'ringing', '2026-10-17') is None
