"""Automatic, cached symptom/presence review through the existing AGY login."""

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
_jobs = {}
_job_lock = threading.Lock()


def fingerprint(report, observations):
    fields = ("symptom", "presence", "evidence", "observed_date", "episode_count", "severity_value")
    rows = [{key: row.get(key) for key in fields} for row in observations if row.get("source") == "text"]
    for row in rows:
        for key in ("episode_count", "severity_value"):
            if row[key] is not None:
                row[key] = float(row[key])
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True))
    source = [2, report.get("raw_text"), report.get("submitted_at"), rows]
    return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


def _validate(rows, text):
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Invalid observations")
    clean, seen = [], set()
    for row in rows:
        symptom, presence, quote = row["symptom"], row["presence"], row["evidence_quote"]
        if not isinstance(symptom, str) or not re.fullmatch(r"[a-z][a-z_]{0,79}", symptom):
            raise ValueError("Invalid symptom")
        if presence not in {"present", "absent", "uncertain"}:
            raise ValueError("Invalid presence")
        if not isinstance(quote, str) or not quote.strip() or quote not in text:
            raise ValueError("Unsupported evidence")
        if (symptom, presence) not in seen:
            clean.append({"symptom": symptom, "presence": presence, "evidence_quote": quote})
            seen.add((symptom, presence))
    return clean


def review_batch(reports, local_by_id, timeout=600):
    def failure(status):
        return {r["report_id"]: {"status": status, "source_fingerprint": fingerprint(r, local_by_id[r["report_id"]])}
                for r in reports}
    binary = shutil.which("agy")
    if not binary:
        return failure("unavailable")
    payload = [{"report_id": r["report_id"], "submitted_at": r.get("submitted_at"), "text": r["raw_text"],
                "local_observations": [row for row in local_by_id[r["report_id"]] if row.get("source") == "text"]}
               for r in reports]
    instructions = Path(__file__).with_name("review_instructions.txt").read_text()
    try:
        with tempfile.TemporaryDirectory(prefix="trackb-review-") as cwd:
            response = subprocess.run([binary, "-p", instructions + json.dumps(payload, default=str),
                                       "--disable-slash-commands", "--output-format", "json"],
                                      cwd=cwd, text=True, capture_output=True, shell=False, timeout=timeout)
        if response.returncode:
            return failure("unavailable")
        envelope = json.loads(response.stdout)
        if envelope.get("status") != "SUCCESS":
            raise ValueError("Unsuccessful response")
        raw = json.loads(envelope["response"])["reports"]
        by_id = {r["report_id"]: r for r in raw}
        if len(raw) != len(by_id) or set(by_id) != {r["report_id"] for r in reports}:
            raise ValueError("Missing, duplicate, or unexpected report IDs")
        now = datetime.now(timezone.utc).isoformat()
        return {r["report_id"]: {"status": "reviewed",
                "observations": _validate(by_id[r["report_id"]]["observations"], r["raw_text"]),
                "source_fingerprint": fingerprint(r, local_by_id[r["report_id"]]),
                "checked_at": now, "provider": "AGY CLI", "duration_seconds": envelope.get("duration_seconds")}
                for r in reports}
    except (subprocess.TimeoutExpired, OSError):
        return failure("unavailable")
    except (ValueError, KeyError, TypeError, IndexError, AttributeError):
        return failure("invalid")


def _sources(conn, patient_id=None, report_id=None):
    sql, args = "SELECT * FROM reports", ()
    if report_id is not None:
        sql += " WHERE report_id=?"
        args = (report_id,)
    elif patient_id is not None:
        sql += " WHERE patient_id=?"
        args = (patient_id,)
    reports = [dict(row) for row in conn.execute(sql + " ORDER BY report_id", args)]
    ids = {r["report_id"] for r in reports}
    local = defaultdict(list)
    for row in conn.execute("SELECT * FROM symptom_observations ORDER BY observation_id"):
        if row["report_id"] in ids:
            local[row["report_id"]].append(dict(row))
    return reports, local


def seed_benchmark_cache(conn):
    """Reuse the real, frozen AGY response only when its original input still matches."""
    folder = ROOT / "data/benchmarks/agy_review"
    if not (folder / "review.json").exists():
        return
    inputs = {r["report_id"]: r for r in json.loads((folder / "input.json").read_text())}
    output = {r["report_id"]: r for r in json.loads((folder / "review.json").read_text())["reports"]}
    reports, local = _sources(conn)
    with conn:
        for report in reports:
            rid = report["report_id"]
            cached = inputs.get(rid)
            previous = json.loads(report["symptom_review_json"])
            current = fingerprint(report, local[rid])
            if previous.get("source_fingerprint") == current:
                continue
            if not cached or rid not in output:
                continue
            cached_report = {"raw_text": cached["text"], "submitted_at": cached["submitted_at"]}
            if fingerprint(cached_report, cached["local_observations"]) != current:
                continue
            result = {"status": "reviewed", "source_fingerprint": current,
                      "observations": _validate(output[rid]["observations"], report["raw_text"]),
                      "provider": "AGY CLI", "cache_origin": "frozen benchmark response"}
            conn.execute("UPDATE reports SET symptom_review_json=? WHERE report_id=?", (json.dumps(result), rid))


def review_status(conn, patient_id=None):
    reports, local = _sources(conn, patient_id=patient_id)
    counts = {"total": len(reports), "reviewed": 0, "pending": 0, "failed": 0}
    for report in reports:
        result = json.loads(report["symptom_review_json"])
        if result.get("source_fingerprint") != fingerprint(report, local[report["report_id"]]):
            counts["pending"] += 1
        elif result.get("status") == "reviewed":
            counts["reviewed"] += 1
        elif result.get("status") in {"invalid", "unavailable"}:
            counts["failed"] += 1
        else:
            counts["pending"] += 1
    return counts


@contextmanager
def _processing_lock(conn):
    path = conn.execute('PRAGMA database_list').fetchone()[2]
    if not path:
        yield
        return
    with open(path + '.review.lock', 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def process_pending(conn, **options):
    # The CLI and dashboard may run simultaneously; only one spends model quota.
    with _processing_lock(conn):
        return _process_pending(conn, **options)


def _process_pending(conn, *, reviewer=None, seed_cache=True, retry_failed=False, batch_size=26):
    if seed_cache:
        seed_benchmark_cache(conn)
    reports, local = _sources(conn)
    pending = []
    for report in reports:
        previous = json.loads(report["symptom_review_json"])
        unchanged = previous.get("source_fingerprint") == fingerprint(report, local[report["report_id"]])
        if unchanged and previous.get("status") == "reviewed":
            continue
        if unchanged and previous.get("status") in {"invalid", "unavailable"} and not retry_failed:
            continue
        pending.append(report)
    reviewer = reviewer or review_batch
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset:offset + batch_size]
        results = reviewer(batch, local)
        with conn:
            for report in batch:
                rid = report["report_id"]
                # Never attach a result to source data that changed while the model ran.
                current, current_local = _sources(conn, report_id=rid)
                if current and fingerprint(current[0], current_local[rid]) == fingerprint(report, local[rid]):
                    conn.execute("UPDATE reports SET symptom_review_json=? WHERE report_id=?", (json.dumps(results[rid]), rid))
    return review_status(conn)


def effective_observations(conn, *, patient_id=None, report_id=None):
    from .parser import resolve_review_date
    reports, local = _sources(conn, patient_id, report_id)
    effective = []
    for report in reports:
        rid = report["report_id"]
        original = local[rid]
        review = json.loads(report["symptom_review_json"])
        if review.get("status") != "reviewed" or review.get("source_fingerprint") != fingerprint(report, original):
            effective.extend(original)
            continue
        effective.extend(row for row in original if row["source"] == "questionnaire")
        texts = [row for row in original if row["source"] == "text"]
        for index, proposal in enumerate(review["observations"]):
            matches = [row for row in texts if (row["symptom"], row["presence"]) == (proposal["symptom"], proposal["presence"])]
            if matches:
                effective.extend({**row, "review_origin": "agy"} for row in matches)
                continue
            day = resolve_review_date(report["raw_text"], proposal["evidence_quote"], report["submitted_at"][:10])
            effective.append(dict(observation_id=f"{rid}:agy:{index}", report_id=rid, source="text",
                symptom=proposal["symptom"], presence=proposal["presence"], evidence=proposal["evidence_quote"],
                original_phrase=proposal["evidence_quote"], observed_date=day, severity_value=None, severity_scale=None,
                severity_text=None, episode_count=None, timing_text=None, medication_mentioned=None,
                issues_json=json.dumps([] if day else ["ambiguous_review_date"]),
                is_full_day=False, count_eligible=False, review_origin="agy"))
    return effective


def ensure_background_review(db_path):
    """Start at most one automatic worker per database in this dashboard process."""
    if os.getenv("TRACKB_AUTO_REVIEW", "1") == "0":
        return
    key = str(Path(db_path).resolve())
    with _job_lock:
        previous = _jobs.get(key)
        if previous and (previous.is_alive() or getattr(previous, "failed", False)):
            return
        def work():
            from .db import connect, initialize
            conn = connect(key)
            try:
                initialize(conn)
                process_pending(conn)
            except Exception:
                threading.current_thread().failed = True
                # Stop showing endless progress if an unexpected worker error occurs.
                reports, local = _sources(conn)
                with conn:
                    for report in reports:
                        rid = report['report_id']
                        previous = json.loads(report['symptom_review_json'])
                        current = fingerprint(report, local[rid])
                        if previous.get('status') == 'reviewed' and previous.get('source_fingerprint') == current:
                            continue
                        conn.execute('UPDATE reports SET symptom_review_json=? WHERE report_id=?',
                                     (json.dumps({'status': 'unavailable', 'source_fingerprint': current}), rid))
            finally:
                conn.close()
        thread = threading.Thread(target=work, daemon=True, name="symptom-review")
        _jobs[key] = thread
        thread.start()
