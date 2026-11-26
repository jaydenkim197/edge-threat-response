"""Box metrics for the reviewed P430 development sessions."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .detection_evaluation import evaluate_boxes
from .detector_comparison import POLICY, canonical_prediction, coco_metrics
from .replay import write_jsonl
from .training import _sha256_file

def truth_record(row):
    boxes=[]
    for x,y,w,h in row['boxes']:
        boxes.append([max(0.,1920*(x-w/2)),max(0.,1080*(y-h/2)),min(1920.,1920*(x+w/2)),min(1080.,1080*(y+h/2))])
    return dict(source_id=row['image_sha256'], image_sha256=row['image_sha256'],
                source_group=row['source_video_sha256'], frame_index=0, width=1920,height=1080,
                knife_absence_verified=not boxes, knife_boxes_xyxy=boxes)

def capped_selection(predictions, rows, details, budget):
    events=defaultdict(list)
    for i,(pred,row,detail) in enumerate(zip(predictions,rows,details,strict=True)):
        matched={item['prediction_index'] for item in detail['matches']}
        for j,obj in enumerate(pred['detections']):
            score=obj['confidence']
            events[score].append((i, j in matched, bool(row['small']), not row['boxes']))
    all_tp=small_tp=false_boxes=0
    false_frames=set()
    best=dict(confidence=None,tp=0,small_tp=0,negative_frames_flagged=0,fp_boxes=0)
    for confidence,items in sorted(events.items(),reverse=True):
        for i,tp,small,empty in items:
            all_tp+=int(tp)
            small_tp+=int(tp and small)
            false_boxes+=int(not tp)
            if empty:
                false_frames.add(i)
        if len(false_frames)>budget:
            break
        key=(small_tp,all_tp,-len(false_frames),-false_boxes)
        if key>(best['small_tp'],best['tp'],-best['negative_frames_flagged'],-best['fp_boxes']):
            best=dict(confidence=confidence,tp=all_tp,small_tp=small_tp,negative_frames_flagged=len(false_frames),fp_boxes=false_boxes)
    return best

def make_truth(rows):
    return {
        "schema_version": 1, "status": "development_authorized", "partition": "tuning",
        "images": [truth_record(row) for row in rows],
    }


def evaluate_checkpoint(checkpoint: Path, rows: list[dict], output: Path, *, imgsz: int = 960) -> dict:
    import torch
    from PIL import Image
    from ultralytics import YOLO

    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.cuda.empty_cache()
    model = YOLO(checkpoint)
    if model.names != {0: "knife"}:
        raise ValueError("Expected the frozen knife-only detector")
    truth = make_truth(rows)
    predictions = []
    for start in range(0, len(rows), 8):
        images = []
        for row in rows[start:start + 8]:
            with Image.open(row["image_file"]) as image:
                if image.size != (1920, 1080):
                    raise ValueError("The development protocol expects a 1920x1080 central crop")
                images.append(image.convert("RGB"))
        batch = model.predict(images, imgsz=imgsz, device=0, batch=len(images), rect=False,
                              conf=.001, classes=[0], iou=.7, max_det=100, verbose=False)
        for index, result in enumerate(batch, start=start):
            prediction, _ = canonical_prediction(
                truth["images"][index], result.boxes.xyxy.tolist(),
                result.boxes.conf.tolist(), result.boxes.cls.tolist(), 0)
            predictions.append(prediction)
    if len(predictions) != len(rows):
        raise RuntimeError("Incomplete evaluation batch")
    return score_predictions(checkpoint, rows, predictions, output)


def score_predictions(checkpoint, rows, predictions, output):
    truth = make_truth(rows)
    fixed, _ = evaluate_boxes(truth, predictions, POLICY)
    _, details = evaluate_boxes(truth, predictions, {**POLICY, "confidence": .001})
    negative = sum(not row["boxes"] for row in rows)
    budget = negative // 100
    point = capped_selection(predictions, rows, details, budget)
    if point["confidence"] is not None:
        validation, matches = evaluate_boxes(truth, predictions, {**POLICY, "confidence": point["confidence"]})
        counts = validation["counts"]
        if (counts["tp"], counts["negative_images_with_fp"], counts["fp"]) != (
            point["tp"], point["negative_frames_flagged"], point["fp_boxes"]
        ) or sum(len(info["matches"]) for row, info in zip(rows, matches, strict=True) if row["small"]) != point["small_tp"]:
            raise RuntimeError("Operating-point recount failed")
    scores = coco_metrics(truth, predictions)
    centered = [i for i, row in enumerate(rows) if row.get("review_scope") == "center-50-v1"]
    center_metrics = {}
    if centered:
        scoped = {**truth, "images": [truth["images"][i] for i in centered]}
        scoped_predictions = [predictions[i] for i in centered]
        center_fixed, _ = evaluate_boxes(scoped, scoped_predictions, POLICY)
        center_metrics = {
            "center_reviewed_ap50": coco_metrics(scoped, scoped_predictions)["ap50"],
            "center_reviewed_fixed025": center_fixed["counts"],
        }
    write_jsonl(output, predictions)
    return {
        "checkpoint": checkpoint.name, "checkpoint_sha256": _sha256_file(checkpoint),
        "predictions_sha256": _sha256_file(output), "ap50": scores["ap50"], "ap50_95": scores["ap50_95"],
        "fixed025": fixed["counts"], **center_metrics, "total_small_960": sum(row["small"] for row in rows),
        "total_positive": sum(bool(row["boxes"]) for row in rows), "negative_frames": negative,
        "negative_budget": budget, "point": point,
    }


def rank_key(record):
    point = record["point"]
    return point["small_tp"], point["tp"], -point["negative_frames_flagged"], -point["fp_boxes"], record["ap50_95"]
