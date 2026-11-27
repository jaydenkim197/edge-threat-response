"""Try one extra D1 crop only when no primary candidate clears the operating point."""

from argparse import ArgumentParser
from dataclasses import replace
from pathlib import Path
from statistics import median
import sys
import time

from edge_threat_response.detection_evaluation import BBox, iou
from edge_threat_response.detector_comparison import canonical_prediction, coco_metrics
from edge_threat_response.p430_evaluation import make_truth, score_predictions
from edge_threat_response.p430_workflow import read, require, save, sha
from edge_threat_response.replay import write_jsonl
from p430_followup_actions import D1_SHA, PLAN_SHA, locked, pin_plan
from run_p430_site import development_rows


CONTROL_OPERATING_POINT = .28837335109710693
CANDIDATE_FLOOR = .15
CROP_SIDE = 384
MIN_IOU = .40


def recheck(backend, image, raw):
    if not raw:
        return raw, None
    proposal = max(range(len(raw)), key=lambda index: raw[index].confidence)
    prior = raw[proposal]
    if not CANDIDATE_FLOOR <= prior.confidence < CONTROL_OPERATING_POINT:
        return raw, None
    a, b, c, d = prior.bbox_xyxy
    height, width = image.shape[:2]
    x = min(width - CROP_SIDE, max(0, round((a + c - CROP_SIDE) / 2)))
    y = min(height - CROP_SIDE, max(0, round((b + d - CROP_SIDE) / 2)))
    crop = image[y:y + CROP_SIDE, x:x + CROP_SIDE]
    original = BBox(a, b, c, d)
    started = time.perf_counter()
    detections, = backend.predict_batch([crop])
    elapsed = (time.perf_counter() - started) * 1000
    matched = []
    for detection in detections:
        if detection.class_id != 0:
            continue
        left, top, right, bottom = detection.bbox_xyxy
        if left >= right or top >= bottom:
            continue
        peer = BBox(left + x, top + y, right + x, bottom + y)
        if iou(original, peer) >= MIN_IOU:
            matched.append(detection.confidence)
    refined = max(prior.confidence, (prior.confidence + max(matched, default=0.0)) / 2)
    return (*raw[:proposal], replace(prior, confidence=refined), *raw[proposal + 1:]), elapsed


def paired(backend, rows):
    import cv2
    import numpy as np

    predictions = {"original": [], "one_crop": []}
    costs = []
    for row, truth in zip(rows, make_truth(rows)["images"], strict=True):
        image = cv2.imdecode(np.frombuffer(Path(row["image_file"]).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        require(image is not None and image.shape == (1080, 1920, 3), "Unexpected P430 frame")
        raw = backend.predict(image)
        altered, cost = recheck(backend, image, raw)
        if cost is not None:
            costs.append(cost)
        for name, values in zip(predictions, (raw, altered), strict=True):
            pred, _ = canonical_prediction(truth, [item.bbox_xyxy for item in values],
                                           [item.confidence for item in values],
                                           [item.class_id for item in values], 0)
            predictions[name].append(pred)
    return predictions, {"frames": len(rows), "frames_with_extra_crop": len(costs),
                         "median_crop_ms": median(costs) if costs else None}


def improved(original, candidate):
    return (candidate["negative_frames_flagged"] <= original["negative_frames_flagged"]
            and candidate["fp_boxes"] <= original["fp_boxes"]
            and candidate["small_tp"] >= original["small_tp"]
            and candidate["tp"] >= original["tp"]
            and (candidate["tp"] >= original["tp"] + 3 or candidate["small_tp"] >= original["small_tp"] + 2))


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("settings", "weights", "result"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()

    import torch
    from edge_threat_response.p430_tile_detector import P430TiledBackend

    base = Path(read(args.settings)["base"])
    sys.path.insert(0, str(base.parent / "p430-t1-20261120-v1/evaluation-deps"))
    plan = pin_plan(base)
    require(sha(args.weights) == D1_SHA and torch.cuda.device_count() == 1, "Expected D1 and one reserved GPU")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    detector = P430TiledBackend(str(args.weights), predict_arguments={"device": 0, "conf": .001})

    def partition(name):
        return development_rows(base, {**plan, "validation": {name: plan["validation"][name]}})[name]

    out = args.result.parent
    rows = partition("tune")
    predictions, costs = paired(detector, rows)
    tune = {arm: score_predictions(args.weights, rows, values, out / f"tune-{arm}.jsonl")
            for arm, values in predictions.items()}
    report = {
        "scope": "development_only", "base_plan_sha256": PLAN_SHA, "weights_sha256": D1_SHA,
        "runner_sha256": sha(Path(__file__)), "reference_threshold": CONTROL_OPERATING_POINT,
        "candidate_floor": CANDIDATE_FLOOR, "crop_side": CROP_SIDE, "min_iou": MIN_IOU,
        "device": torch.cuda.get_device_name(0), "torch": str(torch.__version__), "tune": tune,
        "tune_cost": costs, "tune_gate": improved(tune["original"]["point"], tune["one_crop"]["point"]),
        "dev_check": None,
    }
    save(out / "tune-lock.json", report)
    if report["tune_gate"]:
        rows = partition("dev_check")
        predictions, report["dev_cost"] = paired(detector, rows)
        report["dev_check"] = {}
        for arm, values in predictions.items():
            threshold = tune[arm]["point"]["confidence"]
            path = out / f"dev-{arm}.jsonl"
            write_jsonl(path, values)
            report["dev_check"][arm] = {**locked(rows, values, threshold), "confidence": threshold,
                                       **coco_metrics(make_truth(rows), values), "predictions_sha256": sha(path)}
    print("one-crop tune gate:", report["tune_gate"], flush=True)
    save(args.result, report)


if __name__ == "__main__":
    main()
