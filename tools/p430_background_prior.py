"""Test whether recurrent train-only locations improve MIX70 on the fixed P430 crop."""

from argparse import ArgumentParser
from math import isfinite
from pathlib import Path

from edge_threat_response.dataset.review_web import CENTER_REVIEW_SCOPE
from edge_threat_response.detection_evaluation import BBox, iou
from edge_threat_response.detector_comparison import coco_metrics
from edge_threat_response.p430_evaluation import make_truth, rank_key
from edge_threat_response.p430_workflow import SOURCE_SHA, read, require, save, sha
from p430_crop_verifier import load_partition
from p430_dev_fusion import tune
from p430_followup_actions import PLAN_SHA, locked, pin_plan


OVERLAP = .50
MULTIPLIERS = (.75, .50)
CONSTRAINTS = (
    ("small_tp", 1), ("tp", 1), ("negative_frames_flagged", -1), ("fp_boxes", -1),
)


def recurrent_locations(mined, plan, protection, checkpoint_sha):
    require(mined["schema_version"] == 1 and mined["scope"] == "development_train_review_candidates"
            and mined["base_plan_sha256"] == PLAN_SHA and mined["reviewed_manifest_sha256"] == SOURCE_SHA
            and mined["inference"] == "native-tile640" and mined["detector_sha256"] == checkpoint_sha,
            "Unexpected provenance for recurrent background observations")
    held = {key for partition in plan["validation"].values() for key in partition}
    protected = {protection["edited_sha256"], *protection.get("original_sha256", [])}
    seen = set()
    locations = []
    for observation in mined["candidates"]:
        repeats = observation["nearby_overlapping_frames"]
        require(type(repeats) is int and repeats >= 0, "Invalid recurrence evidence")
        if repeats == 0:
            continue
        key = observation["image_sha256"]
        row = plan["pool"].get(key)
        identity = {key, observation["source_sha256"], observation["source_video_sha256"]}
        require(key not in held and key not in seen and not identity & protected and row
                and row["domain"] == "p430" and row["n"] == 0
                and row["label_sha256"] == observation["label_sha256"]
                and row["source_group"] == observation["source_video_sha256"]
                and observation["review_scope"] == CENTER_REVIEW_SCOPE and observation["review_version"] >= 1,
                "Invalid recurrent observation outside verified P430 train negatives")
        x1, y1, x2, y2 = observation["bbox_xyxy"]
        require(all(isfinite(x) for x in (x1, y1, x2, y2))
                and 0 <= x1 < x2 <= 1920 and 0 <= y1 < y2 <= 1080,
                "Recurrent location is outside the central crop")
        locations.append(BBox(x1, y1, x2, y2))
        seen.add(key)
    return locations


def penalize(predictions, locations, multiplier):
    updated = []
    affected_boxes = affected_frames = 0
    for frame in predictions:
        detections = []
        affected = 0
        for item in frame["detections"]:
            box = BBox(*item["bbox_xyxy"])
            if any(iou(box, location) >= OVERLAP for location in locations):
                confidence = max(.001, item["confidence"] * multiplier)
                affected += int(confidence < item["confidence"])
                detections.append({**item, "confidence": confidence})
            else:
                detections.append(item)
        updated.append({**frame, "detections": detections})
        affected_boxes += affected
        affected_frames += int(affected > 0)
    return updated, {"affected_boxes": affected_boxes, "affected_frames": affected_frames}


def improves(control, candidate):
    base = control["point"]
    changed = candidate["point"]
    differences = [direction * (changed[key] - base[key]) for key, direction in CONSTRAINTS]
    return all(value >= 0 for value in differences) and any(value > 0 for value in differences)


def run(work, snapshot, mining_path, mining_sha, output, *, mix70_run=None, worker_evidence=None):
    require(not output.exists() and (worker_evidence is None or not worker_evidence.exists()),
            "Use fresh output and optional Worker evidence paths")
    require(sha(mining_path) == mining_sha.lower(), "Mining receipt hash mismatch")
    plan = pin_plan(work)
    state = read(snapshot)["A-MIX70"]
    require(state["status"] == "COMPLETED", "Completed MIX70 receipt required")
    checkpoint_sha = state["data"]["checkpoint_sha256"]
    locations = recurrent_locations(read(mining_path), plan, read(work / "protection.json"), checkpoint_sha)
    output.mkdir()
    report = {
        "schema_version": 1, "scope": "p430_development_only", "experiment": "ALT-02 recurrent position",
        "plan_sha256": PLAN_SHA, "mining_sha256": mining_sha.lower(), "checkpoint_sha256": checkpoint_sha,
        "location_count": len(locations), "location_xyxy_central_1920x1080": [
            [box.x_min, box.y_min, box.x_max, box.y_max] for box in locations
        ],
        "limit": "Fixed central crop only; stationary-background and view-transfer assumptions are unverified.",
        "iou_overlap": OVERLAP, "score_multipliers": MULTIPLIERS, "tune": None, "dev_check": None,
        "selected_multiplier": None, "status": "no_recurrent_train_locations",
    }
    if locations:
        rows, predictions, evidence = load_partition(work, plan, state, mix70_run, "tune")
        control = tune(rows, predictions)
        trials = {}
        for multiplier in MULTIPLIERS:
            changed, counts = penalize(predictions, locations, multiplier)
            trials[multiplier] = {**tune(rows, changed), **counts}
        eligible = [value for value in MULTIPLIERS if improves(control, trials[value])]
        report.update(tune={"control": control, **{str(key): value for key, value in trials.items()}},
                      tune_inputs=evidence, status="no_tune_improvement")
        if eligible:
            selected = max(eligible, key=lambda value: rank_key(trials[value]))
            report.update(selected_multiplier=selected, status="locked_dev_check")
            save(output / "tune-lock.json", report)
            rows, predictions, evidence = load_partition(work, plan, state, mix70_run, "dev_check")
            changed, counts = penalize(predictions, locations, selected)
            truth = make_truth(rows)
            report["dev_check"] = {
                "control": {**locked(rows, predictions, control["point"]["confidence"]),
                            **coco_metrics(truth, predictions)},
                "adjusted": {**locked(rows, changed, trials[selected]["point"]["confidence"]),
                             **coco_metrics(truth, changed)},
                "adjusted_effect": counts, "inputs": evidence,
            }
    save(output / "result.json", report)
    if worker_evidence is not None:
        save(worker_evidence, report)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="Pinned development release root")
    parser.add_argument("shared_snapshot", type=Path, help="Queue receipt including completed A-MIX70")
    parser.add_argument("mining_result", type=Path, help="Completed train-only mining result")
    parser.add_argument("output", type=Path, help="Fresh private output directory")
    parser.add_argument("--mining-sha256", required=True, help="Authoritative mining completion hash")
    parser.add_argument("--mix70-run", type=Path, help="Verified alternate directory with MIX70 predictions")
    parser.add_argument("--worker-evidence", type=Path)
    args = parser.parse_args()
    run(args.work, args.shared_snapshot, args.mining_result, args.mining_sha256, args.output,
        mix70_run=args.mix70_run, worker_evidence=args.worker_evidence)
