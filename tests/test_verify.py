import json
from unittest.mock import patch
from urllib.error import HTTPError

from trackb.verify import VerifierConfig, verify_report


REPORT = {
    "raw_text": "Threw up twice after dinner.",
    "questionnaire_json": {"reported_vomiting_episodes": 2},
}
OBSERVATIONS = [{"symptom": "vomiting", "presence": "present", "episode_count": 2}]
CONFIG = VerifierConfig(api_key="test-secret", model="test-model")


class Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"choices": [{"message": {"content": json.dumps(self.value)}}]}).encode()


def test_missing_key_never_calls_network():
    with patch.dict("os.environ", {}, clear=True), patch("trackb.verify.urlopen") as call:
        assert verify_report(REPORT, OBSERVATIONS)["status"] == "not_run"
        call.assert_not_called()


def test_verifier_sends_source_and_preserves_observations():
    original = json.dumps(OBSERVATIONS)
    with patch("trackb.verify.urlopen", return_value=Response({"agrees": True, "issues": []})) as call:
        result = verify_report(REPORT, OBSERVATIONS, config=CONFIG)
    assert result["status"] == "agreed"
    assert json.dumps(OBSERVATIONS) == original
    request = call.call_args.args[0]
    payload = json.loads(request.data)
    assert "Threw up twice after dinner." in payload["messages"][1]["content"]
    assert "questionnaire" in payload["messages"][1]["content"]
    assert "test-secret" not in json.dumps(result)


def test_grounded_disagreement_is_advisory():
    issue = {"symptom": "vomiting", "description": "Check count", "evidence_quote": "twice"}
    with patch("trackb.verify.urlopen", return_value=Response({"agrees": False, "issues": [issue]})):
        result = verify_report(REPORT, OBSERVATIONS, config=CONFIG)
    assert result["status"] == "disagreements"
    assert result["issues"] == [issue]
    assert OBSERVATIONS[0]["episode_count"] == 2


def test_unsupported_evidence_is_not_accepted():
    issue = {"symptom": "syncope", "description": "Missed symptom", "evidence_quote": "passed out"}
    with patch("trackb.verify.urlopen", return_value=Response({"agrees": False, "issues": [issue]})):
        result = verify_report(REPORT, OBSERVATIONS, config=CONFIG)
    assert result["status"] == "invalid"


def test_api_error_leaves_local_result_usable_and_redacts_secret():
    error = HTTPError("https://example.test", 401, "test-secret rejected", {}, None)
    with patch("trackb.verify.urlopen", side_effect=error):
        result = verify_report(REPORT, OBSERVATIONS, config=CONFIG)
    assert result["status"] == "unavailable"
    assert "test-secret" not in json.dumps(result)
    assert OBSERVATIONS[0]["episode_count"] == 2


def test_invalid_envelope_cannot_claim_agreement():
    with patch("trackb.verify.urlopen", return_value=Response({"agrees": "yes", "issues": []})):
        assert verify_report(REPORT, OBSERVATIONS, config=CONFIG)["status"] == "invalid"


def test_saving_advisory_feedback_never_changes_sql_results(tmp_path):
    from pathlib import Path
    from trackb.db import connect, initialize, import_dataset, weekly_symptoms, medication_comparison

    conn = connect(tmp_path / "demo.sqlite")
    initialize(conn)
    import_dataset(conn, Path(__file__).resolve().parents[1] / "data" / "synthetic")
    before = (weekly_symptoms(conn, "SYN-PT-102"), medication_comparison(conn, "SYN-PT-102"))
    conn.execute("UPDATE reports SET verification_json=?", (json.dumps({"status": "disagreements", "issues": [{"description": "Advisory only"}]}),))
    conn.commit()
    after = (weekly_symptoms(conn, "SYN-PT-102"), medication_comparison(conn, "SYN-PT-102"))
    conn.close()
    assert before == after
