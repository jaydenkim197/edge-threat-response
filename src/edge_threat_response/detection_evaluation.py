"""Fixed-threshold knife box evaluation; not event metrics, AP or device latency."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

from .domain import BBox, FrameStatus
from .replay import _parse_frame, write_jsonl
from .training import _git_commit, _sha256_file, _write_json


def iou(left: BBox, right: BBox) -> float:
    intersection = max(0, min(left.x_max, right.x_max) - max(left.x_min, right.x_min)) * max(
        0, min(left.y_max, right.y_max) - max(left.y_min, right.y_min))
    return intersection / (left.width * left.height + right.width * right.height - intersection)


def _unit(value, name, *, zero=True):
    if type(value) not in {int, float} or not math.isfinite(value) or not (0 <= value <= 1 if zero else 0 < value <= 1):
        raise ValueError(f"{name} must be finite and in {'[0,1]' if zero else '(0,1]'}")
    return value


def _box(coords, width, height):
    if not isinstance(coords, list) or len(coords) != 4 or any(type(v) not in {int, float} for v in coords):
        raise ValueError("Knife boxes need four pixel coordinates")
    box = BBox(*coords)
    if not (0 <= box.x_min < box.x_max <= width and 0 <= box.y_min < box.y_max <= height):
        raise ValueError("Knife bbox outside the annotated pixel matrix")
    return box


def evaluate_boxes(truth: dict, prediction_rows: list[dict], policy: dict) -> tuple[dict, list[dict]]:
    if truth.get("schema_version") != 1 or truth.get("status") not in {"synthetic", "approved"}:
        raise ValueError("Ground truth must be synthetic or explicitly approved; review candidates are not ground truth")
    if policy.get("schema_version") != 1 or policy.get("status") not in {"development", "frozen"}:
        raise ValueError("Evaluation policy must be development or frozen")
    partition = truth.get("partition")
    if partition not in {"synthetic", "tuning", "final_test"}:
        raise ValueError("Keep tuning, final test and synthetic partitions separate")
    if (truth["status"] == "synthetic") != (partition == "synthetic"):
        raise ValueError("Synthetic truth must stay in the synthetic partition")
    if partition == "final_test" and policy["status"] != "frozen":
        raise ValueError("Final test requires a frozen evaluation policy")
    confidence = _unit(policy.get("confidence"), "confidence")
    overlap = _unit(policy.get("iou"), "IoU", zero=False)
    small_area = _unit(policy.get("small_area_max"), "small_area_max", zero=False)
    images = truth.get("images")
    if not isinstance(images, list) or not images:
        raise ValueError("Ground truth needs annotated images")
    predicted = {}
    for row in prediction_rows:
        frame = _parse_frame(row)
        key = (frame.source_id, frame.frame_index)
        if key in predicted:
            raise ValueError("Duplicate prediction identity")
        if frame.status is not FrameStatus.VALID:
            raise ValueError("Detector failure/missing frames must be repaired or separately reported, not silently scored")
        predicted[key] = frame
    details, seen, totals = [], set(), Counter()
    for image in images:
        if not isinstance(image, dict) or not isinstance(image.get("source_id"), str) or not image["source_id"].strip():
            raise ValueError("Image must identify its source")
        frame_index = image.get("frame_index")
        if type(frame_index) is not int or frame_index < 0:
            raise ValueError("Image needs a nonnegative frame index")
        key = image["source_id"], frame_index
        if key in seen or key not in predicted:
            raise ValueError("Repeated truth image or missing prediction row")
        seen.add(key)
        if truth["status"] == "approved" and not all(isinstance(image.get(k), str) and image[k].strip()
                                                       for k in ("image_sha256", "source_group")):
            raise ValueError("Approved image truth needs image hash and source/session group")
        if truth["status"] == "approved" and not re.fullmatch(r"[a-f0-9]{64}", image["image_sha256"]):
            raise ValueError("Approved image truth needs a SHA-256 image identity")
        width, height = image.get("width"), image.get("height")
        if any(type(v) is not int or v <= 0 for v in (width, height)):
            raise ValueError("Image dimensions must be positive integers")
        raw_boxes = image.get("knife_boxes_xyxy")
        if not isinstance(raw_boxes, list):
            raise ValueError("Explicit knife boxes or empty array required")
        boxes = [_box(coords, width, height) for coords in raw_boxes]
        if not boxes and image.get("knife_absence_verified") is not True:
            raise ValueError("Empty labels alone do not prove knife absence")
        detections = [item for item in predicted[key].detections if item.label == "knife" and item.confidence >= confidence]
        for item in detections:
            _box(item.bbox.to_list(), width, height)
        # Stable confidence-first greedy one-to-one matching; duplicate boxes remain FP.
        order = sorted(enumerate(detections), key=lambda item: (-item[1].confidence, item[0]))
        unmatched = set(range(len(boxes)))
        matches, false_positives = [], []
        for index, detection in order:
            options = sorted(((iou(detection.bbox, boxes[g]), g) for g in unmatched), key=lambda pair: (-pair[0], pair[1]))
            if options and options[0][0] >= overlap:
                score, target = options[0]
                unmatched.remove(target)
                matches.append({"prediction_index": index, "truth_index": target, "iou": score})
            else:
                false_positives.append(index)
        small = {index for index, box in enumerate(boxes) if box.width * box.height / (width * height) <= small_area}
        totals.update({"tp": len(matches), "fp": len(false_positives), "fn": len(unmatched),
                       "small_gt": len(small), "small_tp": sum(match["truth_index"] in small for match in matches),
                       "negative_images": int(not boxes), "negative_fp_boxes": len(false_positives) if not boxes else 0,
                       "negative_images_with_fp": int(not boxes and bool(false_positives))})
        details.append({"source_id": key[0], "frame_index": key[1], "matches": matches,
                        "false_positive_prediction_indices": false_positives, "missed_truth_indices": sorted(unmatched),
                        "small_truth_indices": sorted(small), "gt_count": len(boxes), "prediction_count": len(detections)})
    if set(predicted) != seen:
        raise ValueError("Prediction rows outside the ground-truth image set")
    ratio = lambda numerator, denominator: numerator / denominator if denominator else None
    tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
    result = {"schema_version": 1, "status": "synthetic_contract_check" if partition == "synthetic" else "measured_image_boxes",
              "partition": partition, "images": len(images), "policy": policy, "counts": dict(totals),
              "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn), "f1": ratio(2 * tp, 2 * tp + fp + fn),
              "small_box_recall": ratio(totals["small_tp"], totals["small_gt"]),
              "negative_image_fp_fraction": ratio(totals["negative_images_with_fp"], totals["negative_images"]),
              "fp_boxes_per_negative_image": ratio(totals["negative_fp_boxes"], totals["negative_images"]),
              "limits": ["normalized bbox area is not physical distance", "fixed-threshold greedy IoU matching, not mAP",
                         "image metrics are not event false alerts/hour or GPIO latency",
                         "annotation approval and frozen status are declarations, not cryptographic identity verification"]}
    return result, details


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--detections", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists():
            raise ValueError("Evaluation output must be a new directory")
        paths = {"ground_truth": args.ground_truth, "detections": args.detections, "policy": args.policy}
        hashes = {key: _sha256_file(path) for key, path in paths.items()}
        truth = json.loads(args.ground_truth.read_text(encoding="utf-8-sig"))
        policy = json.loads(args.policy.read_text(encoding="utf-8-sig"))
        predictions = [json.loads(line) for line in args.detections.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        summary, details = evaluate_boxes(truth, predictions, policy)
        if hashes != {key: _sha256_file(path) for key, path in paths.items()}:
            raise ValueError("Evaluation inputs changed during execution")
        summary.update({"input_sha256": hashes, "git_commit": _git_commit()})
        args.output_dir.mkdir(parents=True)
        _write_json(args.output_dir / "summary.json", summary)
        write_jsonl(args.output_dir / "image-matches.jsonl", details)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
