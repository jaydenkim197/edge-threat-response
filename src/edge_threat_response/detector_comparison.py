"""Common, cached-prediction metrics for the development detector comparison.

Model-specific preprocessing stays in the experiment driver. No training, review
approval, or runtime detector selection is performed here.
"""
from __future__ import annotations

import contextlib
import io
import math
import random
from collections import defaultdict

from .detection_evaluation import evaluate_boxes, iou
from .domain import BBox


POLICY = {"schema_version": 1, "status": "development", "confidence": .25,
          "iou": .5, "small_area_max": .02}


def nms_ensemble(truth: dict, members: list[list[dict]], *, overlap: float = .7) -> list[dict]:
    """Pool cached knife candidates and retain max-score boxes with NMS.

    This is an uncalibrated development ensemble, not WBF or a deployable
    runtime. Every member must cover exactly the same truth image identities.
    """
    if len(members) < 2 or type(overlap) not in {int, float} or not math.isfinite(overlap) or not 0 < overlap <= 1:
        raise ValueError("Need two or more members and finite NMS IoU in (0,1]")
    if truth.get("status") != "development_authorized":
        raise ValueError("Cached ensemble exploration requires development truth")
    indexed = []
    for predictions in members:
        evaluate_boxes(truth, predictions, POLICY)
        indexed.append({(p["source_id"], p["frame_index"]): p for p in predictions})
    output = []
    for image in truth["images"]:
        key = image["source_id"], image["frame_index"]
        pool = [dict(d) for model in indexed for d in model[key]["detections"] if d["label"] == "knife"]
        pool.sort(key=lambda d: (-d["confidence"], tuple(d["bbox_xyxy"])))
        kept, kept_boxes = [], []
        for detection in pool:
            box = BBox(*detection["bbox_xyxy"])
            if all(iou(box, other) <= overlap for other in kept_boxes):
                kept.append(detection)
                kept_boxes.append(box)
                if len(kept) == 300:
                    break
        output.append({"source_id": key[0], "frame_index": key[1], "timestamp_s": 0,
                       "status": "valid", "detections": kept})
    return output


def select_f2_operating_point(truth: dict, predictions: list[dict]) -> dict:
    """Choose a development threshold on tuning only, never final-test truth."""
    if truth.get("partition") != "tuning":
        raise ValueError("Detector threshold selection requires tuning truth")
    curve = []
    for i in range(5, 100, 5):
        threshold = i/100
        metrics, _ = evaluate_boxes(truth, predictions, {**POLICY, "confidence": threshold})
        c = metrics["counts"]
        denominator = 5*c["tp"] + 4*c["fn"] + c["fp"]
        curve.append({"confidence": threshold, "f2": 5*c["tp"]/denominator if denominator else None,
                      "recall": metrics["recall"], "precision": metrics["precision"], "counts": c})
    best = max(curve, key=lambda x: (x["f2"] or 0, x["recall"] or 0, -x["counts"]["fp"], -x["confidence"]))
    return {"selected": best, "curve": curve, "selection_partition": "tuning", "final_detector_selected": False}


def canonical_prediction(image: dict, boxes, scores, classes, knife_id: int) -> tuple[dict, int]:
    """Map an explicitly verified class ID, clipping all backends consistently.

    Invalid numbers are errors, never silently skipped inference failures. Boxes
    with no remaining area after clipping are counted as discarded outputs.
    """
    if not (len(boxes) == len(scores) == len(classes)):
        raise ValueError("Detector arrays have different lengths")
    width, height = image["width"], image["height"]
    detections, adjusted = [], 0
    for box, score, class_id in zip(boxes, scores, classes):
        if (len(box) != 4 or not all(math.isfinite(float(x)) for x in [*box, score, class_id])
                or not 0 <= float(score) <= 1 or int(class_id) != class_id):
            raise ValueError("Invalid detector output")
        if int(class_id) != knife_id or score < .001:
            continue
        clipped = [max(0., min(float(x), float(limit)))
                   for x, limit in zip(box, (width, height, width, height))]
        if clipped != list(box):
            adjusted += 1
        if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
            adjusted += 1
            continue
        detections.append({"label": "knife", "confidence": float(score), "bbox_xyxy": clipped})
    return {"source_id": image["source_id"], "frame_index": 0, "timestamp_s": 0,
            "status": "valid", "detections": detections}, adjusted


def coco_metrics(truth: dict, predictions: list[dict]) -> dict:
    """Use the same pycocotools AP implementation for every model family.

    validate_boxes runs first, including exact image identity, empty-label
    evidence, dimensions, finite coordinates and failed-frame checks.
    """
    evaluate_boxes(truth, predictions, POLICY)
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval
    images, annotations, results = [], [], []
    by_id = {(p["source_id"], p["frame_index"]): p for p in predictions}
    for image_id, image in enumerate(truth["images"], 1):
        images.append({"id": image_id, "width": image["width"], "height": image["height"]})
        for box in image["knife_boxes_xyxy"]:
            x, y, x2, y2 = box
            annotations.append({"id": len(annotations)+1, "image_id": image_id, "category_id": 1,
                                "bbox": [x, y, x2-x, y2-y], "area": (x2-x)*(y2-y), "iscrowd": 0})
        for detection in by_id[(image["source_id"], 0)]["detections"]:
            x, y, x2, y2 = detection["bbox_xyxy"]
            results.append({"image_id": image_id, "category_id": 1, "bbox": [x, y, x2-x, y2-y],
                            "score": detection["confidence"]})
    if not annotations:
        raise ValueError("AP requires at least one positive ground-truth object")
    with contextlib.redirect_stdout(io.StringIO()):
        gt = COCO()
        gt.dataset = {"info": {}, "images": images, "annotations": annotations,
                      "categories": [{"id": 1, "name": "knife"}]}
        gt.createIndex()
        if results:
            dt = gt.loadRes(results)
        else:
            dt = COCO()
            dt.dataset = {"info": {}, "images": images, "annotations": [], "categories": gt.dataset["categories"]}
            dt.createIndex()
        evaluator = COCOeval(gt, dt, "bbox")
        evaluator.params.imgIds = [x["id"] for x in images]
        evaluator.params.catIds = [1]
        evaluator.evaluate()
        evaluator.accumulate()
        evaluator.summarize()
    return {"ap50_95": float(evaluator.stats[0]), "ap50": float(evaluator.stats[1]),
            "ap75": float(evaluator.stats[2]), "max_dets": 100,
            "implementation": "pycocotools.COCOeval", "confidence_floor": .001,
            "iou_thresholds": [round(.5+.05*i, 2) for i in range(10)],
            "recall_points": 101, "area": "all", "knife_category_id": 1}


def paired_group_recall_interval(truth: dict, candidate: list[dict], reference: list[dict],
                                 *, repetitions: int = 2000, seed: int = 20261104) -> dict:
    """Descriptive paired group bootstrap, not an independent final-test claim.

    Resample the same groups for both models. Filename/dHash proxies must not
    be described as verified recording sessions. Zero-positive replicates are
    omitted and counted explicitly; fewer than two positive groups yields no CI.
    """
    if repetitions < 1:
        raise ValueError("Positive bootstrap repetitions required")
    _, left = evaluate_boxes(truth, candidate, POLICY)
    _, right = evaluate_boxes(truth, reference, POLICY)
    groups = defaultdict(lambda: [0, 0, 0])
    for image, a, b in zip(truth["images"], left, right):
        item = groups[image["source_group"]]
        item[0] += len(a["matches"])
        item[1] += len(b["matches"])
        item[2] += a["gt_count"]
    values = [groups[key] for key in sorted(groups)]
    gt_count = sum(x[2] for x in values)
    delta = (sum(x[0] for x in values)-sum(x[1] for x in values))/gt_count if gt_count else None
    output = {"delta_recall": delta, "groups": len(values),
              "positive_groups": sum(x[2] > 0 for x in values), "repetitions": repetitions,
              "seed": seed, "ci95": None, "method": "paired percentile group bootstrap",
              "limits": "descriptive; group proxies and small samples do not establish general superiority"}
    if output["positive_groups"] < 2:
        return {**output, "valid_replicates": 0, "reason": "fewer than two positive groups"}
    rng = random.Random(seed)
    samples = []
    for _ in range(repetitions):
        sample = rng.choices(values, k=len(values))
        denominator = sum(x[2] for x in sample)
        if denominator:
            samples.append((sum(x[0] for x in sample)-sum(x[1] for x in sample))/denominator)
    samples.sort()
    def percentile(q):
        index = (len(samples)-1)*q
        low = int(index)
        return samples[low]+(samples[min(low+1, len(samples)-1)]-samples[low])*(index-low)
    return {**output, "valid_replicates": len(samples),
            "ci95": [percentile(.025), percentile(.975)] if samples else None}
