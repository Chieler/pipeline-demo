"""Small CLI for reproducing the Track B demonstration."""

import argparse
from contextlib import closing
from datetime import date
import json
import os
from pathlib import Path

from .db import connect, initialize, import_dataset, weekly_symptoms, medication_comparison
from .parser import parse_text
from .verify import verify_report
from .agy_review import process_pending


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="Synthetic patient report pipeline")
    parser.add_argument("--db", type=Path, default=Path(os.getenv("TRACKB_DB_PATH", ROOT / "data" / "trackb.sqlite")))
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("import", help="Parse and import the synthetic dataset (idempotent)")
    ingest.add_argument("--data", type=Path, default=ROOT / "data" / "synthetic")
    ingest.add_argument("--local-only", action="store_true", help="Skip automatic AGY review")
    text = commands.add_parser("parse", help="Inspect text-only local extraction")
    text.add_argument("text")
    text.add_argument("--date", default=date.today().isoformat())
    query = commands.add_parser("query", help="Run one of the two SQLite analyses")
    query.add_argument("kind", choices=["weekly", "medication"])
    query.add_argument("--patient", default="SYN-PT-102")
    verifier = commands.add_parser("verify", help="Optional advisory API check of one stored report")
    verifier.add_argument("report_id")
    review = commands.add_parser("review", help="Review new or changed reports through AGY")
    review.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()

    if args.command == "parse":
        try:
            date.fromisoformat(args.date)
        except ValueError:
            parser.error("--date must be YYYY-MM-DD")
        result = parse_text(args.text, args.date)
    else:
        args.db.parent.mkdir(parents=True, exist_ok=True)
        with closing(connect(args.db)) as conn:
            initialize(conn)
            if args.command == "import":
                result = import_dataset(conn, args.data)
                if not args.local_only:
                    result["symptom_review"] = process_pending(conn)
            elif args.command == "review":
                result = process_pending(conn, retry_failed=args.retry_failed)
            elif args.command == "query":
                function = weekly_symptoms if args.kind == "weekly" else medication_comparison
                result = function(conn, args.patient)
            else:
                row = conn.execute("SELECT * FROM reports WHERE report_id=?", (args.report_id,)).fetchone()
                if row is None:
                    parser.error("report not found; import the dataset first")
                observations = [dict(row) for row in conn.execute("SELECT * FROM symptom_observations WHERE report_id=?", (args.report_id,))]
                result = verify_report(dict(row), observations)
                conn.execute("UPDATE reports SET verification_json=? WHERE report_id=?", (json.dumps(result), args.report_id))
                conn.commit()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
