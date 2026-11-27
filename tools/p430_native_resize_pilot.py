"""Compare D1's native tile input with one-step resize alternatives."""

from argparse import ArgumentParser
from pathlib import Path

from edge_threat_response.detector_comparison import coco_metrics
from edge_threat_response.p430_evaluation import make_truth, rank_key
from edge_threat_response.p430_workflow import read, require, save, sha
from edge_threat_response.replay import write_jsonl
from p430_dev_fusion import load_predictions, tune
from p430_followup_actions import D1_SHA, PLAN_SHA, locked, pin_plan, use_d1
from run_p430_site import development_rows, tile_predictions


ARMS = ("native", "lanczos", "bicubic")
COUNTS = {"tune": (298, 161, 137), "dev_check": (287, 140, 147)}


def improves(control, candidate):
    baseline, result = control["point"], candidate["point"]
    small = result["small_tp"] - baseline["small_tp"]
    total = result["tp"] - baseline["tp"]
    negative = baseline["negative_frames_flagged"] - result["negative_frames_flagged"]
    boxes = baseline["fp_boxes"] - result["fp_boxes"]
    return min(small, total, negative, boxes) >= 0 and (
        small >= 2 or total >= 2 or negative >= 1 or boxes >= 2
    )


def load_partition(base, plan, split):
    rows = development_rows(base, {**plan, "validation": {split: plan["validation"][split]}})[split]
    counts = len(rows), sum(len(row["boxes"]) for row in rows), sum(not row["boxes"] for row in rows)
    require(counts == COUNTS[split] and len({row["image_sha256"] for row in rows}) == len(rows),
            f"{split} differs from the pinned D1 evaluation partition")
    return rows


def predict_arm(checkpoint, rows, arm):
    from PIL import Image

    interpolations = {"native": None, "lanczos": Image.Resampling.LANCZOS, "bicubic": Image.Resampling.BICUBIC}
    return tile_predictions(checkpoint, rows, device="cpu", interpolation=interpolations[arm])


def run(settings, shared_snapshot, output, *, d1_run=None, worker_evidence=None):
    require(not output.exists() and (worker_evidence is None or not worker_evidence.exists()),
            "Use fresh output and optional worker evidence paths")
    base = Path(settings["base"])
    plan = pin_plan(base)
    checkpoint = use_d1(settings)
    baseline_receipt = read(shared_snapshot)["A0"]
    rows = load_partition(base, plan, "tune")
    cached, cache_evidence = load_predictions(
        "A0", baseline_receipt, d1_run, {"tune": rows}, partitions=("tune",)
    )
    report = {
        "schema_version": 1,
        "scope": "p430_development_only",
        "experiment": "ALT-07 native resampling",
        "device": "cpu",
        "plan_sha256": PLAN_SHA,
        "checkpoint_sha256": D1_SHA,
        "runner_sha256": sha(Path(tile_predictions.__code__.co_filename).resolve()),
        "cached_a0_tune": tune(rows, cached["tune"]),
        "cached_a0_evidence": cache_evidence,
        "tune": {},
        "selected_arm": None,
        "dev_check": None,
        "status": "no_tune_improvement",
    }
    output.mkdir()
    for arm in ARMS:
        predictions = predict_arm(checkpoint, rows, arm)
        prediction_path = output / f"tune-{arm}.jsonl"
        write_jsonl(prediction_path, predictions)
        report["tune"][arm] = {**tune(rows, predictions), "predictions_sha256": sha(prediction_path)}
    control = report["tune"]["native"]
    eligible = [arm for arm in ARMS[1:] if improves(control, report["tune"][arm])]
    if eligible:
        selected = max(eligible, key=lambda arm: rank_key(report["tune"][arm]))
        report.update(selected_arm=selected, status="locked_dev_check")
        lock_path = output / "tune-lock.json"
        save(lock_path, report)
        report["tune_lock_sha256"] = sha(lock_path)
        rows = load_partition(base, plan, "dev_check")
        truth = make_truth(rows)
        report["dev_check"] = {}
        for arm in ("native", selected):
            threshold = report["tune"][arm]["point"]["confidence"]
            predictions = predict_arm(checkpoint, rows, arm)
            prediction_path = output / f"dev_check-{arm}.jsonl"
            write_jsonl(prediction_path, predictions)
            report["dev_check"][arm] = {
                **locked(rows, predictions, threshold),
                **coco_metrics(truth, predictions),
                "confidence": threshold,
                "predictions_sha256": sha(prediction_path),
            }
    require(sha(checkpoint) == D1_SHA, "D1 changed during the pilot")
    save(output / "result.json", report)
    if worker_evidence is not None:
        save(worker_evidence, report)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("node_settings", type=Path)
    parser.add_argument("shared_snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--d1-run", type=Path)
    parser.add_argument("--worker-evidence", type=Path)
    args = parser.parse_args()
    run(read(args.node_settings), args.shared_snapshot, args.output,
        d1_run=args.d1_run, worker_evidence=args.worker_evidence)
