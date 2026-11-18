"""Score a frozen AGY review against synthetic symptom/presence reference pairs."""

import argparse
import json
from collections import Counter
from pathlib import Path


ALIASES = {"mucositis": "mouth_sores", "syncope": "fainting"}


def pairs(observations, reference=False):
    if reference:
        return {(ALIASES.get(o["normalized_concept"], o["normalized_concept"]), o["status"])
                for o in observations if o["entity_type"] == "symptom"}
    return {(ALIASES.get(o["symptom"], o["symptom"]), o["presence"]) for o in observations}


def metrics(counts):
    tp, fp, fn = counts
    return {"matched": tp, "extra": fp, "missed": fn,
            "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0}


def score(inputs, reviewed, labels):
    source = {r["report_id"]: r for r in inputs}
    revisions = {r["report_id"]: r for r in reviewed["reports"]}
    if len(revisions) != len(reviewed["reports"]) or set(revisions) != set(source):
        raise ValueError("Review must contain each input report exactly once")
    reference = {r["checkin_id"]: r for r in labels}
    totals = {"local": [0, 0, 0], "agy_reviewed": [0, 0, 0]}
    changes = Counter()
    report_results = []
    for report_id, report in source.items():
        observations = revisions[report_id]["observations"]
        for observation in observations:
            quote = observation.get("evidence_quote")
            if not isinstance(quote, str) or not quote.strip() or quote not in report["text"]:
                raise ValueError(f"Unsupported evidence: {report_id}: {observation}")
            if observation.get("presence") not in {"present", "absent", "uncertain"}:
                raise ValueError(f"Invalid presence: {report_id}")
            if not isinstance(observation.get("symptom"), str) or not observation["symptom"].strip():
                raise ValueError(f"Invalid symptom: {report_id}")
        expected = pairs(reference[report_id]["extractable_entities"], reference=True)
        baseline = pairs(report["local_observations"])
        proposed = pairs(observations)
        for name, actual in [("local", baseline), ("agy_reviewed", proposed)]:
            for i, count in enumerate((len(actual & expected), len(actual - expected), len(expected - actual))):
                totals[name][i] += count
        changes.update({"recovered_misses": len((proposed - baseline) & expected),
                        "new_extras": len((proposed - baseline) - expected),
                        "removed_extras": len((baseline - proposed) - expected),
                        "lost_matches": len((baseline - proposed) & expected)})
        report_results.append({"report_id": report_id,
                               "local_missed": sorted(expected - baseline),
                               "reviewed_missed": sorted(expected - proposed),
                               "reviewed_extra": sorted(proposed - expected)})
    result = {name: metrics(counts) for name, counts in totals.items()}
    return {"reports": len(source), "scoring": "Unique symptom/presence pairs per report; text only",
            **result, "f1_delta": result["agy_reviewed"]["f1"] - result["local"]["f1"],
            "changes": dict(changes), "per_report": report_results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--labels", type=Path, default=Path("data/synthetic/expected_annotations.json"))
    args = parser.parse_args()
    print(json.dumps(score(json.loads(args.input.read_text()), json.loads(args.review.read_text()),
                           json.loads(args.labels.read_text())), indent=2))
