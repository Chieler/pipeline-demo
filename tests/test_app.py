from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
import json

from trackb.agy_review import fingerprint
from trackb.db import connect, initialize, import_dataset


@pytest.mark.parametrize("patient_id", ["SYN-PT-101", "SYN-PT-102", "SYN-PT-103"])
def test_dashboard_runs_for_each_patient(tmp_path, monkeypatch, patient_id):
    monkeypatch.setenv("TRACKB_DB_PATH", str(tmp_path / "demo.sqlite"))
    monkeypatch.delenv("VERIFIER_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=40).run()
    assert not app.exception
    app.selectbox(key="patient").set_value(patient_id).run()
    assert not app.exception
    assert len(app.get("plotly_chart")) >= 2
    assert any(metric.label == "Check-ins submitted" and metric.value == "26 / 28" for metric in app.metric)
    assert len(app.dataframe) >= 1
    date_selector = app.selectbox(key=f"checkin_date_{patient_id}")
    assert len(date_selector.options) == 28
    assert sum("Not checked in" in option for option in date_selector.options) == 2
    assert any(metric.label == "Nausea severity" for metric in app.metric)
    missed_date = {"SYN-PT-101": "2026-10-16", "SYN-PT-102": "2026-10-11", "SYN-PT-103": "2026-10-19"}[patient_id]
    date_selector.set_value(missed_date).run()
    assert not app.exception
    assert any("Not checked in" in notice.value for notice in app.info)
    assert not any(metric.label == "Nausea severity" for metric in app.metric)


def test_saved_review_feeds_dashboard_without_approval_buttons(tmp_path, monkeypatch):
    db = tmp_path / "review.sqlite"
    monkeypatch.setenv("TRACKB_DB_PATH", str(db))
    conn = connect(db)
    initialize(conn)
    import_dataset(conn, Path(__file__).resolve().parents[1] / "data/synthetic")
    report_id = "CHK-SYN-PT-103-D11"
    report = dict(conn.execute("SELECT * FROM reports WHERE report_id=?", (report_id,)).fetchone())
    rows = [dict(row) for row in conn.execute("SELECT * FROM symptom_observations WHERE report_id=?", (report_id,))]
    review = {"status": "reviewed", "observations": [{"symptom": "tinnitus", "presence": "present", "evidence_quote": "ringing"}],
              "source_fingerprint": fingerprint(report, rows)}
    conn.execute("UPDATE reports SET symptom_review_json=? WHERE report_id=?", (json.dumps(review), report_id))
    conn.commit()
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=40).run()
    app.selectbox(key="patient").set_value("SYN-PT-103").run()
    app.selectbox(key="checkin_date_SYN-PT-103").set_value(report["report_date"]).run()
    assert not app.exception
    assert not any(button.label in {"Review symptoms", "Add confirmed symptoms", "Undo symptom additions"} for button in app.button)
    assert any("Reviewed patient text" in frame.value["Source"].tolist()
               for frame in app.dataframe if "Source" in frame.value.columns)
    conn.close()
