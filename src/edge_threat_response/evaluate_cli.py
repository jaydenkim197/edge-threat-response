from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .evaluation import evaluate_replays
from .training import _git_commit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare B0-B3 decision events with manual event ground truth.")
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--replay-manifest", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists():
            raise ValueError("Evaluation output must be a new directory")
        result = evaluate_replays(args.ground_truth, args.replay_manifest, args.policy)
        result["git_commit"] = _git_commit()
        args.output_dir.mkdir(parents=True)
        (args.output_dir / "evaluation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        rows = []
        for item in result["comparison"]:
            metrics = item["metrics"]
            rows.append({"partition": item["partition"], "mode": item["mode"], "tp": item["tp"], "fp": item["fp"], "fn": item["fn"],
                         "event_precision": metrics["event_precision"], "event_recall": metrics["event_recall"],
                         "event_f1": metrics["event_f1"], "duplicate_alerts": item["duplicate_alerts"],
                         "background_false_alerts": item["background_false_alerts"],
                         "false_alerts_per_scored_hour": metrics["false_alerts_per_scored_hour"],
                         "background_false_alerts_per_negative_hour": metrics["background_false_alerts_per_negative_hour"],
                         "matched_latency_count": metrics["latency"]["matched_count"],
                         "latency_mean_s": metrics["latency"]["mean_s"], "latency_p95_s": metrics["latency"]["p95_s"],
                         "scored_duration_s": item["scored_duration_s"], "negative_duration_s": item["negative_duration_s"],
                         "action_error_count": item["action_error_count"]})
        with (args.output_dir / "comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"data_kind": result["data_kind"], "comparison": result["comparison"]}, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
