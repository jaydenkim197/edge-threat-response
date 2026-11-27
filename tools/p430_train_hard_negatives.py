"""Mine review candidates only from P430's pinned train negatives."""

from argparse import ArgumentParser
from collections import Counter
from math import isfinite
from pathlib import Path
import os

from edge_threat_response.dataset.review_web import CENTER_REVIEW_SCOPE
from edge_threat_response.detection_evaluation import BBox, iou
from edge_threat_response.p430_workflow import SOURCE_SHA, now, read, require, save, sha
from edge_threat_response.training import gpu_training_lock
from p430_followup_actions import PLAN_SHA, gpu_name, pin_plan, use_d1
from run_p430_integration import jsonl, paths
from run_p430_site import tile_predictions


def reviewed_train_negatives(base, plan, manifest, protection):
    held = {key for partition in plan["validation"].values() for key in partition}
    held_original = {row["source_sha256"] for row in manifest if row["image_sha256"] in held}
    protected = {protection["edited_sha256"], *protection.get("original_sha256", [])}
    selected = []
    seen = set()
    for record in manifest:
        key = record["image_sha256"]
        parent = plan["pool"].get(key)
        if (not parent or parent["domain"] != "p430" or parent["n"] != 0
                or record.get("review_scope") != CENTER_REVIEW_SCOPE):
            continue
        require(not {key, record["source_sha256"], record["source_video_sha256"]} & protected
                and record["source_sha256"] not in held_original and key not in held and key not in seen,
                "Protected or duplicate hard-negative candidate")
        require(record["knife_boxes"] == 0 and record["crop_xyxy"] == [960, 540, 2880, 1620]
                and record["source_video_sha256"] == parent["source_group"]
                and record["label_sha256"] == parent["label_sha256"]
                and record["review_version"] >= 1 and isfinite(record["timestamp_s"])
                and record["timestamp_s"] >= 0, "Hard-negative review identity changed")
        image, label = paths(base, parent)
        require(sha(image) == key and sha(label) == record["label_sha256"] and label.stat().st_size == 0,
                "Hard-negative image or empty label failed byte validation")
        seen.add(key)
        selected.append({**record, "image_file": str(image), "boxes": []})
    return selected


def select_candidates(rows, predictions, confidence, spacing_s, limit):
    ranked = []
    for row, prediction in zip(rows, predictions, strict=True):
        require(prediction["source_id"] == row["image_sha256"], "Prediction order does not match review inputs")
        detection = max(prediction["detections"], key=lambda item: item["confidence"], default=None)
        if detection and detection["confidence"] >= confidence:
            ranked.append((row, detection))
    ranked.sort(key=lambda pair: (-pair[1]["confidence"], pair[0]["image_sha256"]))
    candidates = []
    for row, detection in ranked:
        def near(other):
            return (row["source_video_sha256"] == other["source_video_sha256"]
                    and abs(row["timestamp_s"] - other["timestamp_s"]) < spacing_s)

        if any(near(selected) for selected in candidates):
            continue
        box = BBox(*detection["bbox_xyxy"])
        recurring = sum(near(other) and iou(box, BBox(*item["bbox_xyxy"])) >= .5
                        for other, item in ranked if other["image_sha256"] != row["image_sha256"])
        fields = ("image", "image_sha256", "label_sha256", "source_sha256", "source_video_sha256",
                  "session", "timestamp_s", "review_scope", "review_version")
        candidates.append({**{field: row[field] for field in fields},
                           "bbox_xyxy": detection["bbox_xyxy"], "confidence": detection["confidence"],
                           "nearby_overlapping_frames": recurring})
        if len(candidates) == limit:
            break
    return candidates, len(ranked)


def mine(settings, output, *, confidence, spacing_s, limit, checkpoint=None, checkpoint_sha256=None):
    require(0 < confidence <= 1 and 0 < spacing_s < float("inf") and limit > 0, "Invalid triage parameters")
    require(not output.exists(), "Use a new review candidate result path")
    require((checkpoint is None) == (checkpoint_sha256 is None), "Provide both checkpoint path and SHA-256")
    checkpoint = use_d1(settings) if checkpoint is None else checkpoint
    detector_hash = sha(checkpoint)
    require(checkpoint_sha256 is None or detector_hash == checkpoint_sha256.lower(),
            "Mining checkpoint SHA-256 differs from its receipt")
    base = Path(settings["base"])
    plan = pin_plan(base)
    source = base.parent / "p430-t1-20261120-v1/dataset/manifest.jsonl"
    require(sha(source) == SOURCE_SHA, "Reviewed P430 manifest changed")
    rows = reviewed_train_negatives(base, plan, jsonl(source), read(base / "protection.json"))
    require(rows, "No proven P430 train negatives with central review scope")
    if not settings["node"].startswith("pc"):
        require(os.environ.get("CUDA_VISIBLE_DEVICES") == settings["uuid"], "Pin the approved GPU UUID")
    with gpu_training_lock(base.parent / "training" / gpu_name(settings), owner="p430-hard-negative-mining"):
        predictions = tile_predictions(checkpoint, rows)
    require(sha(checkpoint) == detector_hash, "Mining checkpoint changed during inference")
    candidates, flagged = select_candidates(rows, predictions, confidence, spacing_s, limit)
    save(output, {
        "schema_version": 1, "scope": "development_train_review_candidates",
        "base_plan_sha256": PLAN_SHA, "reviewed_manifest_sha256": SOURCE_SHA,
        "detector": checkpoint.name, "detector_sha256": detector_hash, "inference": "native-tile640",
        "confidence_floor": confidence, "same_recording_spacing_s": spacing_s, "max_candidates": limit,
        "scanned": len(rows), "scanned_by_session": dict(Counter(row["session"] for row in rows)),
        "flagged": flagged, "candidates": candidates, "created_at": now(),
    })


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("settings", type=Path, help="Existing node settings with the pinned P430 base and D1")
    parser.add_argument("output", type=Path, help="New JSON path in a private run directory")
    parser.add_argument("--checkpoint", type=Path, help="Use this knife detector instead of D1")
    parser.add_argument("--checkpoint-sha256", help="Required SHA-256 from the alternate detector's receipt")
    parser.add_argument("--confidence", type=float, default=.15)
    parser.add_argument("--spacing-s", type=float, default=5.)
    parser.add_argument("--limit", type=int, default=24)
    args = parser.parse_args()
    mine(read(args.settings), args.output, confidence=args.confidence, spacing_s=args.spacing_s,
         limit=args.limit, checkpoint=args.checkpoint, checkpoint_sha256=args.checkpoint_sha256)
