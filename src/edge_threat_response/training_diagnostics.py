"""Development train/val diagnostics with cached predictions; never inspect reserved test."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .dataset.review import parse_review_boxes
from .detection_evaluation import evaluate_boxes, iou
from .domain import BBox
from .replay import write_jsonl
from .training import TrainingConfig, _git_commit, _sha256_file, _write_json, validate_training_approval


def error_categories(truth, predictions, confidence=.25):
    by_id = {(row["source_id"], row["frame_index"]): row for row in predictions}
    output = []
    for image in truth["images"]:
        detections = by_id[(image["source_id"], 0)]["detections"]
        for index, box in enumerate(image["knife_boxes_xyxy"]):
            gt = BBox(*box)
            candidates = [(iou(gt, BBox(*p["bbox_xyxy"])), p["confidence"]) for p in detections]
            matching_conf = max((score for overlap, score in candidates if overlap >= .5), default=0)
            maximum_iou = max((overlap for overlap, score in candidates if score >= .05), default=0)
            category = ("detected" if matching_conf >= confidence else "low_confidence" if matching_conf > 0
                        else "localization" if maximum_iou >= .25 else "missed")
            output.append({"source_id": image["source_id"], "truth_index": index, "category": category,
                           "matching_confidence": matching_conf, "max_iou_conf_ge05": maximum_iou,
                           "normalized_area": gt.width * gt.height / (image["width"] * image["height"])})
    return output


def _contact_sheets(rows, truth, predictions, output):
    from PIL import Image, ImageDraw
    tiles = []
    for row, image, prediction in zip(rows, truth["images"], predictions):
        with Image.open(row["image"]) as source:
            original = source.convert("RGB")
        original.thumbnail((420, 280))
        tile = Image.new("RGB", (420, 330), "#202124")
        tile.paste(original, (0, 0))
        draw = ImageDraw.Draw(tile)
        for boxes, color in ((image["knife_boxes_xyxy"], "#00ff7f"),
                             ([p["bbox_xyxy"] for p in prediction["detections"] if p["confidence"] >= .05], "#ffae42")):
            for box in boxes:
                draw.rectangle(tuple(value * original.size[i % 2] / (image["width"] if i % 2 == 0 else image["height"])
                                     for i, value in enumerate(box)), outline=color, width=2)
        draw.text((4, 284), f"{len(tiles):02d} GT={len(image['knife_boxes_xyxy'])} pred@.05={sum(p['confidence']>=.05 for p in prediction['detections'])}\nGT green / predictions orange\nAI DIAGNOSTIC - NOT HUMAN REVIEW", fill="white")
        tiles.append(tile)
    for start in range(0, len(tiles), 6):
        sheet = Image.new("RGB", (1260, 660), "#202124")
        for index, tile in enumerate(tiles[start:start + 6]):
            sheet.paste(tile, ((index % 3) * 420, (index // 3) * 330))
        sheet.save(output / f"val-page-{start // 6 + 1:02d}.jpg", quality=90)


def diagnose(prepared: Path, checkpoint: Path, output: Path, *, model_factory=None):
    from PIL import Image
    if output.exists():
        raise ValueError("Use a fresh diagnostics output")
    config = TrainingConfig.load(prepared / "training.json")
    if config.recipe_id != "DEV-SOHAS":
        raise ValueError("Only development-authorized inputs are supported")
    validate_training_approval(prepared / "training.json", config, prepared / "data.yaml",
                               prepared / "DEV-manifest.jsonl", prepared / "development-authorization.json")
    rows = [json.loads(line) for line in (prepared / "DEV-manifest.jsonl").read_text().splitlines()]
    # Do not open the test images/labels or use them for threshold selection.
    selected = [row for row in rows if row["split"] in {"train", "val"}]
    before = _sha256_file(checkpoint)
    if model_factory is None:
        from ultralytics import YOLO
        model_factory = YOLO
    model = model_factory(str(checkpoint))
    knife_ids = [key for key, name in model.names.items() if name == "knife"]
    if len(knife_ids) != 1:
        raise ValueError("Checkpoint must identify exactly one knife class")
    output.mkdir(parents=True)
    summaries = {}
    for partition in ("train", "val"):
        subset = [row for row in selected if row["split"] == partition]
        truth = {"schema_version": 1, "status": "development_authorized",
                 "partition": "train_diagnostic" if partition == "train" else "tuning", "images": []}
        predictions = []
        results = model.predict(source=[row["image"] for row in subset], stream=True, batch=16,
                                imgsz=640, device=0, conf=.05, iou=.7, max_det=300, verbose=False)
        for index, result in enumerate(results):
            if index >= len(subset):
                raise ValueError("Model returned extra images")
            row = subset[index]
            if Path(result.path).resolve() != Path(row["image"]).resolve():
                raise ValueError("Prediction order/image identity mismatch")
            with Image.open(row["image"]) as image:
                width, height = image.size
            boxes = []
            if row["knife_count"]:
                boxes = [[(b.x_center-b.width/2)*width, (b.y_center-b.height/2)*height,
                          (b.x_center+b.width/2)*width, (b.y_center+b.height/2)*height]
                         for b in parse_review_boxes(Path(row["label"]))]
            source = row["image_id"]
            truth["images"].append({"source_id": source, "frame_index": 0, "image_sha256": row["image_sha256"],
                                    "source_group": row["source_group"], "width": width, "height": height,
                                    "knife_boxes_xyxy": boxes, "knife_absence_verified": row["negative_absence_reviewed"]})
            detections = []
            for cls, score, coords in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist(), result.boxes.xyxy.tolist()):
                if int(cls) == knife_ids[0]:
                    detections.append({"label": "knife", "confidence": score, "bbox_xyxy": coords})
            predictions.append({"source_id": source, "frame_index": 0, "timestamp_s": 0, "status": "valid", "detections": detections})
        if len(predictions) != len(subset):
            raise ValueError("Model returned a different number of images")
        _write_json(output / f"{partition}-truth.json", truth)
        write_jsonl(output / f"{partition}-predictions.jsonl", predictions)
        sweep = []
        for overlap in (.25, .5):
            for threshold in (.05, .1, .25, .5):
                policy = {"schema_version": 1, "status": "development", "confidence": threshold, "iou": overlap, "small_area_max": .02}
                summary, details = evaluate_boxes(truth, predictions, policy)
                sweep.append(summary)
                if overlap == .5 and threshold == .25:
                    write_jsonl(output / f"{partition}-matches.jsonl", details)
        categories = error_categories(truth, predictions)
        write_jsonl(output / f"{partition}-errors.jsonl", categories)
        summaries[partition] = {"sweep": sweep, "error_categories": dict(Counter(row["category"] for row in categories))}
        if partition == "val":
            _contact_sheets(subset, truth, predictions, output)
    if _sha256_file(checkpoint) != before:
        raise ValueError("Checkpoint changed during diagnosis")
    record = {"schema_version": 1, "status": "completed_development_diagnostics", "git_commit": _git_commit(),
              "checkpoint_sha256": before, "prepared_manifest_sha256": _sha256_file(prepared / "DEV-manifest.jsonl"),
              "test_used": False, "prediction_confidence_floor": .05, "partitions": summaries,
              "limits": ["fixed-threshold matching differs from Ultralytics best-F1 summary",
                         "train diagnostics are fit measures, not held-out performance", "small normalized area is not physical distance",
                         "predictions below confidence .05 are outside this diagnostic sweep",
                         "AI visual diagnostics do not change human review/ground truth"]}
    _write_json(output / "summary.json", record)
    print(json.dumps({"status": record["status"], "test_used": False,
                      "categories": {key: val["error_categories"] for key, val in summaries.items()}}))
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        diagnose(args.prepared, args.checkpoint, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
