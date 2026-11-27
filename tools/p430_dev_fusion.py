"""Compare a preregistered set of P430 fusions using cached development predictions."""

from argparse import ArgumentParser
from pathlib import Path

from edge_threat_response.detection_evaluation import BBox, evaluate_boxes, iou
from edge_threat_response.detector_comparison import POLICY, coco_metrics
from edge_threat_response.p430_evaluation import capped_selection, make_truth, rank_key
from edge_threat_response.p430_workflow import read, require, save, sha
from edge_threat_response.replay import write_jsonl
from p430_followup_actions import D1_SHA, PLAN_SHA, locked, pin_plan
from run_p430_integration import jsonl
from run_p430_site import development_rows
from run_p430_site_diagnostic import merge


MODELS = ("A0", "A-MIX70", "D1-3409")
VARIANTS = (
    ("D1+MIX70/NMS", "A-MIX70", False),
    ("D1+MIX70/agreement", "A-MIX70", True),
    ("D1+seed3409/NMS", "D1-3409", False),
    ("D1+seed3409/agreement", "D1-3409", True),
)
PARTITIONS = ("tune", "dev_check")


def load_development(work):
    rows = development_rows(work, pin_plan(work))
    require(set(rows) == set(PARTITIONS), "Expected exactly the approved tune and dev-check partitions")
    expected = {"tune": (298, 161, 137), "dev_check": (287, 140, 147)}
    identities = set()
    for split in PARTITIONS:
        values = rows[split]
        keys = {row["image_sha256"] for row in values}
        counts = len(values), sum(len(row["boxes"]) for row in values), sum(not row["boxes"] for row in values)
        require(counts == expected[split] and len(keys) == len(values) and not keys & identities,
                f"{split} membership or annotation counts differ from the development contract")
        require(all(type(row["small"]) is bool and
                    row["small"] == any(min(w * 960, h * 540) < 16 for _, _, w, h in row["boxes"])
                    for row in values), f"{split} small-knife definitions differ")
        identities.update(keys)
    require(sum(row["small"] for row in rows["dev_check"]) == 58, "Unexpected dev-check small-knife count")
    return rows


def load_predictions(name, snapshot_entry, run, rows, *, partitions=PARTITIONS):
    require(snapshot_entry["status"] == "COMPLETED", f"{name} lacks a completion receipt")
    record = snapshot_entry["data"]
    receipt = run / "result.json" if run else Path(record["local_result"])
    receipt_sha = sha(receipt)
    require(receipt_sha == record["result_sha256"], f"{name} evaluation receipt hash mismatch")
    report = read(receipt)
    if name == "A0":
        selected = {split: report[split]["tile640"] for split in PARTITIONS}
        checkpoint_sha = D1_SHA
        files = {split: f"{split}-tile640.jsonl" for split in PARTITIONS}
    else:
        tile = report["result"]["tile640"]
        checkpoint = tile["selected_checkpoint"]
        require(Path(checkpoint).name == checkpoint and Path(checkpoint).suffix == ".pt",
                "Expected a checkpoint filename")
        selected = {"tune": next(item for item in tile["tune"] if item["checkpoint"] == checkpoint),
                    "dev_check": tile["dev_check"][checkpoint]}
        require(report["scope"] == "development" and selected["dev_check"]["threshold_source"] == "tune",
                f"{name} was not evaluated with the development tuning protocol")
        checkpoint_sha = record["checkpoint_sha256"]
        files = {"tune": f"tune-tile640-{Path(checkpoint).stem}.jsonl",
                 "dev_check": f"dev-tile640-{checkpoint}.jsonl"}
    predictions = {}
    hashes = {"result_sha256": receipt_sha, "checkpoint_sha256": checkpoint_sha, "predictions": {}}
    for split in partitions:
        require(selected[split]["checkpoint_sha256"] == checkpoint_sha, f"{name} checkpoint hash mismatch")
        prediction_file = receipt.parent / files[split]
        file_hash = sha(prediction_file)
        require(file_hash == selected[split]["predictions_sha256"], f"{name} {split} prediction hash mismatch")
        predictions[split] = jsonl(prediction_file)
        require([p["source_id"] for p in predictions[split]] == [r["image_sha256"] for r in rows[split]],
                f"{name} {split} image membership or order differs")
        hashes["predictions"][split] = file_hash
    return predictions, hashes


def _rescore(frame, other):
    other_boxes = [BBox(*item["bbox_xyxy"]) for item in other["detections"]]
    detections = []
    for item in frame["detections"]:
        box = BBox(*item["bbox_xyxy"])
        supported = any(iou(box, candidate) >= .40 for candidate in other_boxes)
        detections.append({**item, "confidence": item["confidence"] if supported else max(.001, .50 * item["confidence"])})
    return {**frame, "detections": detections}


def fuse(left, right, agreement):
    if agreement:
        pairs = list(zip(left, right, strict=True))
        left = [_rescore(a, b) for a, b in pairs]
        right = [_rescore(b, a) for a, b in pairs]
    return merge(left, right)


def tune(rows, predictions):
    truth = make_truth(rows)
    _, matches = evaluate_boxes(truth, predictions, {**POLICY, "confidence": .001})
    point = capped_selection(predictions, rows, matches, sum(not row["boxes"] for row in rows) // 100)
    observed = locked(rows, predictions, point["confidence"])
    require(tuple(observed[key] for key in ("tp", "neg", "fp", "small")) ==
            tuple(point[key] for key in ("tp", "negative_frames_flagged", "fp_boxes", "small_tp")),
            "Tuning operating-point recount failed")
    return {"point": point, **coco_metrics(truth, predictions)}


def coverage(truth, predictions):
    """Find targets with a raw overlapping candidate, ignoring one-to-one constraints."""
    present = set()
    for row, frame in zip(truth["images"], predictions, strict=True):
        predictions_xyxy = [BBox(*item["bbox_xyxy"]) for item in frame["detections"]]
        for index, coordinates in enumerate(row["knife_boxes_xyxy"]):
            box = BBox(*coordinates)
            if any(iou(box, candidate) >= .50 for candidate in predictions_xyxy):
                present.add((row["source_id"], index))
    return present


def research(rows, predictions):
    tune_rows = rows["tune"]
    baseline = {name: tune(tune_rows, predictions[name]["tune"]) for name in MODELS}
    trials = {}
    for name, secondary, agreement in VARIANTS:
        trials[name] = tune(tune_rows, fuse(predictions["A0"]["tune"], predictions[secondary]["tune"], agreement))
    winner, secondary, agreement = max(VARIANTS, key=lambda item: rank_key(trials[item[0]]))

    tune_truth = make_truth(tune_rows)
    spatial_support = {name: coverage(tune_truth, predictions[name]["tune"]) for name in MODELS}
    report = {
        "scope": "p430_development_only",
        "fusion_policy": {"nms_iou": .55, "max_detections": 300, "agreement_iou": .40, "unsupported_score_scale": .50},
        "tune": {**baseline, **trials},
        "tune_geometric_support": {name: {"covered": len(spatial_support[name]),
                                          "additional_vs_d1": len(spatial_support[name] - spatial_support["A0"])}
                                   for name in MODELS},
        "selected_fusion": winner,
    }
    tune_points = {name: report["tune"][name]["point"]["confidence"] for name in (*MODELS, winner)}
    dev = {name: predictions[name]["dev_check"] for name in MODELS}
    dev[winner] = fuse(dev["A0"], dev[secondary], agreement)
    dev_truth = make_truth(rows["dev_check"])
    report["dev_check"] = {
        name: {"confidence": tune_points[name], **locked(rows["dev_check"], values, tune_points[name]),
               **coco_metrics(dev_truth, values)}
        for name, values in dev.items()
    }
    return report, dev[winner]


def main():
    cli = ArgumentParser(description=__doc__)
    cli.add_argument("work", type=Path, help="Pinned development release root")
    cli.add_argument("shared_snapshot", type=Path, help="Queue's merged completion receipts")
    cli.add_argument("output", type=Path, help="New output directory")
    cli.add_argument("--d1-run", type=Path)
    cli.add_argument("--mix70-run", type=Path)
    cli.add_argument("--seed3409-run", type=Path)
    cli.add_argument("--worker-evidence", type=Path, help="Write a successful Worker evidence receipt at this path")
    args = cli.parse_args()
    require(not args.output.exists(), "Use a new output directory")
    rows = load_development(args.work)
    snapshot = read(args.shared_snapshot)
    predictions, evidence = {}, {}
    for name, path in zip(MODELS, (args.d1_run, args.mix70_run, args.seed3409_run), strict=True):
        predictions[name], evidence[name] = load_predictions(name, snapshot[name], path, rows)
    report, fused = research(rows, predictions)
    args.output.mkdir()
    fused_file = args.output / "selected-dev-check.jsonl"
    write_jsonl(fused_file, fused)
    report.update(plan_sha256=PLAN_SHA, shared_snapshot_sha256=sha(args.shared_snapshot), inputs=evidence,
                  selected_dev_check_prediction_sha256=sha(fused_file))
    save(args.output / "result.json", report)
    if args.worker_evidence is not None:
        save(args.worker_evidence, report)


if __name__ == "__main__":
    main()
