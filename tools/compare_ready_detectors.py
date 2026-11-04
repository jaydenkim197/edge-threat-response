"""Read-only development comparison; explicitly discloses the reserved test split."""
import argparse
import gc
import json
import shutil
import time
from pathlib import Path

from edge_threat_response.dataset.review import parse_review_boxes
from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.replay import write_jsonl
from edge_threat_response.training import (TrainingConfig, _environment_record, _git_commit,
                                          _sha256_file, _write_json, validate_training_approval)


def run(args):
    if not args.open_reserved_test:
        raise ValueError("Explicit --open-reserved-test required; these test images cease to be unseen final evaluation")
    if args.output.exists():
        raise ValueError("Use a fresh output directory")
    config = TrainingConfig.load(args.prepared / "training.json")
    validate_training_approval(args.prepared / "training.json", config, args.prepared / "data.yaml",
                               args.prepared / "DEV-manifest.jsonl", args.prepared / "development-authorization.json")
    records = [json.loads(x) for x in (args.prepared / "DEV-manifest.jsonl").read_text(encoding="utf-8-sig").splitlines()]
    if config.recipe_id != "DEV-SOHAS" or any(not row.get("development_only") for row in records):
        raise ValueError("This experiment requires the frozen DEV-SOHAS development set")
    selected = [r for r in records if r["split"] in {"val", "test"}]
    cases = [("custom-n-640", args.checkpoint, 640), ("coco-n-640", args.small, 640),
             ("coco-x-640", args.large, 640), ("coco-x-1280", args.large, 1280)]
    watched = [args.prepared / name for name in ("training.json", "DEV-manifest.jsonl", "development-authorization.json",
                                                "train.txt", "val.txt", "test.txt")]
    watched += list({p for _, p, _ in cases})
    before = {str(p): _sha256_file(p) for p in watched}
    from PIL import Image
    from ultralytics import YOLO
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("PC13 CUDA required; no CPU fallback")
    args.output.mkdir(parents=True)
    _write_json(args.output / "test-access.json", {
        "date": "2026-11-04", "authority": "Direct user request to evaluate strongest ready YOLO on the test set",
        "purpose": "development_model_comparison", "original_partition": "reserved test",
        "test_is_unseen_after_this_run": False, "formal_annotation_or_recipe_approval_granted": False,
        "cases": [{"id": name, "weights_sha256": before[str(p)], "imgsz": size} for name, p, size in cases],
        "fixed_policy": {"confidence": .25, "iou": .5, "small_area_max": .02},
        "native_ap_policy": {"confidence_floor": .001, "matching": "Ultralytics validator default .50:.95"}})
    truths = {}
    for partition in ("val", "test"):
        images = []
        subset = [r for r in selected if r["split"] == partition]
        if not subset:
            raise ValueError("Missing comparison partition")
        for row in subset:
            if _sha256_file(Path(row["image"])) != row["image_sha256"] or _sha256_file(Path(row["label"])) != row["label_sha256"]:
                raise ValueError("Frozen source bytes changed")
            with Image.open(row["image"]) as image:
                width, height = image.size
            boxes = parse_review_boxes(Path(row["label"])) if row["knife_count"] else []
            if len(boxes) != row["knife_count"]:
                raise ValueError("Knife count/label mismatch")
            images.append({"source_id": row["image_id"], "frame_index": 0, "image_sha256": row["image_sha256"],
                           "source_group": row["source_group"], "width": width, "height": height,
                           "knife_boxes_xyxy": [[(b.x_center-b.width/2)*width, (b.y_center-b.height/2)*height,
                                                  (b.x_center+b.width/2)*width, (b.y_center+b.height/2)*height] for b in boxes],
                           "knife_absence_verified": row["negative_absence_reviewed"]})
        # The opened test is now development comparison data, not approved final truth.
        truth = {"schema_version": 1, "status": "development_authorized", "partition": "tuning",
                 "original_split": partition, "purpose": "opened_development_comparison", "images": images}
        _write_json(args.output / f"{partition}-truth.json", truth)
        truths[partition] = truth
    results = {}
    for name, checkpoint, size in cases:
        case = args.output / name
        case.mkdir()
        model = YOLO(str(checkpoint))
        ids = [i for i, label in model.names.items() if label == "knife"]
        if len(ids) != 1:
            raise ValueError("Exactly one knife class required")
        knife = ids[0]
        names = [model.names[i] for i in range(len(model.names))]
        data = case / "evaluation-copy"
        identity = {}
        for partition in ("val", "test"):
            paths = []
            subset = [r for r in selected if r["split"] == partition]
            for index, row in enumerate(subset):
                dest = data / "images" / partition / f"{index:04d}{Path(row['image']).suffix}"
                label = data / "labels" / partition / f"{index:04d}.txt"
                dest.parent.mkdir(parents=True, exist_ok=True)
                label.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(row["image"], dest)
                if _sha256_file(dest) != row["image_sha256"]:
                    raise ValueError("Evaluation copy changed image bytes")
                boxes = parse_review_boxes(Path(row["label"])) if row["knife_count"] else []
                label.write_text("".join(f"{knife} {b.x_center:.17g} {b.y_center:.17g} {b.width:.17g} {b.height:.17g}\n" for b in boxes), encoding="utf-8")
                paths.append(str(dest.resolve()))
                identity[str(dest.resolve())] = row
            (data / f"{partition}.txt").write_text("\n".join(paths) + "\n", encoding="utf-8")
        yaml = data / "data.yaml"
        _write_json(yaml, {"path": str(data.resolve()), "train": [], "val": str((data / "val.txt").resolve()),
                           "test": str((data / "test.txt").resolve()), "names": names})
        record = {"weights_sha256": before[str(checkpoint)], "knife_class_id": knife, "class_count": len(names),
                  "imgsz": size, "batch": 1, "rect": False, "half": False, "nms_argument": None, "partitions": {}}
        for partition in ("val", "test"):
            metrics = model.val(data=str(yaml), split=partition, device=0, imgsz=size, batch=1, workers=0,
                                rect=False, half=False, conf=.001, iou=.7, max_det=300, nms=None, classes=[knife],
                                plots=False, save_json=False, verbose=False, project=str(case / "native-val"),
                                name=partition, exist_ok=False)
            if list(metrics.box.ap_class_index) != [knife]:
                raise ValueError("Native AP did not evaluate the intended knife class")
            record["partitions"][partition] = {"native_map50": float(metrics.box.map50),
                                                "native_map50_95": float(metrics.box.map),
                                                "native_best_f1_results": {k: float(v) for k, v in metrics.results_dict.items()}}
        del model
        gc.collect()
        torch.cuda.empty_cache()
        model = YOLO(str(checkpoint))
        for partition in ("val", "test"):
            paths = (data / f"{partition}.txt").read_text(encoding="utf-8").splitlines()
            predictions = []
            started = time.perf_counter()
            stream = model.predict(source=paths, stream=True, batch=1, imgsz=size, device=0, conf=.05,
                                   classes=[knife], iou=.7, max_det=300, half=False, rect=False, nms=None, verbose=False)
            for result in stream:
                if str(Path(result.path).resolve()) != paths[len(predictions)]:
                    raise ValueError("Prediction order/image identity changed")
                row = identity[str(Path(result.path).resolve())]
                detections = [{"label": "knife", "confidence": float(score), "bbox_xyxy": [float(x) for x in box]}
                              for cls, score, box in zip(result.boxes.cls.tolist(), result.boxes.conf.tolist(), result.boxes.xyxy.tolist())
                              if int(cls) == knife]
                predictions.append({"source_id": row["image_id"], "frame_index": 0, "timestamp_s": 0,
                                    "status": "valid", "detections": detections})
            if len(predictions) != len(paths):
                raise ValueError("Incomplete predictions")
            write_jsonl(case / f"{partition}-predictions.jsonl", predictions)
            policy = {"schema_version": 1, "status": "development", "confidence": .25, "iou": .5, "small_area_max": .02}
            fixed, matches = evaluate_boxes(truths[partition], predictions, policy)
            write_jsonl(case / f"{partition}-matches.jsonl", matches)
            record["partitions"][partition]["fixed_conf025_iou050"] = fixed
            record["partitions"][partition]["prediction_elapsed_s_not_benchmark"] = time.perf_counter()-started
        record["effective_predictor_end2end"] = bool(getattr(model.predictor.model, "end2end", False))
        _write_json(case / "summary.json", record)
        results[name] = record
        print(json.dumps({"completed_case": name, "partitions": record["partitions"]}), flush=True)
        del model
        gc.collect()
        torch.cuda.empty_cache()
    if {str(p): _sha256_file(p) for p in watched} != before:
        raise ValueError("Source manifest/config/checkpoint changed during evaluation")
    for row in selected:
        if _sha256_file(Path(row["image"])) != row["image_sha256"] or _sha256_file(Path(row["label"])) != row["label_sha256"]:
            raise ValueError("Source image/label changed")
    summary = {"status": "completed_opened_development_comparison", "git_commit": _git_commit(),
               "script_sha256": _sha256_file(Path(__file__)), "environment": _environment_record(),
               "source_sha256": before, "test_no_longer_unseen": True, "training_started": False,
               "counts": {p: {"images": len(t["images"]), "knife_objects": sum(len(x["knife_boxes_xyxy"]) for x in t["images"])} for p, t in truths.items()},
               "cases": results}
    _write_json(args.output / "summary.json", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("prepared", "checkpoint", "small", "large", "output"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--open-reserved-test", action="store_true")
    run(parser.parse_args())
