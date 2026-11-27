"""Train RF-DETR on the pinned P430 development release and evaluate six tiles."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import nullcontext
from pathlib import Path
import os

from edge_threat_response.detector_comparison import canonical_prediction, coco_metrics
from edge_threat_response.p430_evaluation import make_truth, score_predictions
from edge_threat_response.p430_tile_detector import tile_nms_indices, tile_regions, touches_internal_tile_edge
from edge_threat_response.p430_workflow import now, read, require, save, sha
from edge_threat_response.training import gpu_training_lock
from p430_followup_actions import D1_SHA, PLAN_SHA, gpu_name, locked, pin_plan
from run_p430_site import development_rows, input_paths, original_boxes


COCO_RF_SMALL_SHA = "d81979a9213a2109345158ce9232668df4c1ae52e9b8db3f2ec0a8cbad959b33"
SEED = 3407
SIZE = 640


def export_coco(folder, items):
    from PIL import Image

    folder.mkdir(exist_ok=False, parents=True)
    images, annotations = [], []
    for image_id, (image, boxes) in enumerate(items, 1):
        filename = f"{image_id:06d}{image.suffix}"
        with Image.open(image) as pixels:
            width, height = pixels.size
        target = folder / filename
        if os.name == "nt":
            os.link(image, target)
        else:
            target.symlink_to(image)
        images.append({"id": image_id, "file_name": filename, "width": width, "height": height})
        for x, y, w, h in boxes:
            left, top = max(0., (x - w / 2) * width), max(0., (y - h / 2) * height)
            right, bottom = min(width, (x + w / 2) * width), min(height, (y + h / 2) * height)
            bbox = [left, top, right - left, bottom - top]
            annotations.append({"id": len(annotations) + 1, "image_id": image_id,
                                "category_id": 1, "bbox": bbox, "area": bbox[2] * bbox[3], "iscrowd": 0})
    save(folder / "_annotations.coco.json", {"info": {}, "licenses": [], "images": images,
             "annotations": annotations, "categories": [{"id": 1, "name": "knife"}]})


def verified_train(base, plan):
    protection = read(base / "protection.json")
    protected = {protection["edited_sha256"], *protection.get("original_sha256", [])}
    held = {key for keys in plan["validation"].values() for key in keys}
    verified, items = {}, []
    for key, tiled in plan["draws"][0]:
        parent = plan["pool"][key]
        require(key not in held | protected and parent["source_group"] not in protected, "Protected training source")
        if (key, tiled) not in verified:
            image, label = input_paths(base, plan, key, tiled)
            evidence = plan["tiles"][key] if tiled else parent
            require(sha(image) == (evidence["image_sha256"] if tiled else key)
                    and sha(label) == evidence["label_sha256"], "Input pair hash changed")
            verified[key, tiled] = image, original_boxes(label)
        items.append(verified[key, tiled])
    return items


def balanced_pilot(items, count):
    positives = [item for item in items if item[1]]
    negatives = [item for item in items if not item[1]]
    require(len(positives) >= count // 2 and len(negatives) >= count // 2, "Incomplete pilot cohort")
    return positives[:count // 2] + negatives[:count // 2]


def knife_predictions(prediction):
    names = prediction.data.get("class_name")
    require(names is not None and prediction.class_id is not None, "RF-DETR prediction has no class metadata")
    for box, score, class_id, name in zip(
        prediction.xyxy, prediction.confidence, prediction.class_id, names, strict=True,
    ):
        # RF-DETR 1.11.2 remaps the exported knife category to foreground
        # slot 0 and can return the no-object slot 1 above the score floor.
        if class_id == 1 and name == "__background__":
            continue
        require(class_id == 0 and str(name).lower() == "knife", "Unexpected fine-tuned class")
        yield box, score


def infer_tiles(model, rows):
    from PIL import Image

    require(tuple(model.class_names) == ("knife",), "Expected a knife-only RF-DETR checkpoint")
    outputs = []
    for row, truth in zip(rows, make_truth(rows)["images"], strict=True):
        with Image.open(row["image_file"]) as image:
            require(image.size == (1920, 1080), "Unexpected P430 evaluation dimensions")
            grid = tile_regions(*image.size)
            tiles = [image.crop(region).convert("RGB") for region in grid]
        detections = model.predict(tiles, threshold=.001, include_source_image=False)
        boxes, scores = [], []
        for region, prediction in zip(grid, detections, strict=True):
            x, y = region[:2]
            for box, score in knife_predictions(prediction):
                if not touches_internal_tile_edge(box, region):
                    boxes.append([float(box[0] + x), float(box[1] + y), float(box[2] + x), float(box[3] + y)])
                    scores.append(float(score))
        keep = tile_nms_indices(boxes, scores)
        pred, _ = canonical_prediction(truth, [boxes[i] for i in keep], [scores[i] for i in keep], [0] * len(keep), 0)
        outputs.append(pred)
    return outputs


def best_checkpoint(directory):
    for name in ("checkpoint_best_total.pth", "checkpoint_best_ema.pth", "checkpoint_best_regular.pth", "last.ckpt"):
        file = directory / name
        if file.is_file() and file.stat().st_size > 0:
            return file
    raise ValueError("RF-DETR did not save a checkpoint")


def fit(dataset, output, initial, epochs):
    from rfdetr import RFDETRSmall

    model = RFDETRSmall(device="cuda", pretrain_weights=str(initial), resolution=SIZE, amp=False)
    model.train(dataset_dir=str(dataset), output_dir=str(output), epochs=epochs,
                batch_size=4, grad_accum_steps=2, num_workers=0, lr=.0001,
                multi_scale="off", accelerator="gpu", devices=1, checkpoint_interval=1, seed=SEED,
                eval_backend="faster_coco_eval", tensorboard=False, run_test=False, early_stopping=False)
    return best_checkpoint(output)


def run(args):
    settings = read(args.settings)
    lock = (
        gpu_training_lock(Path(settings["base"]).parent / "training" / gpu_name(settings), owner="RF-DETR")
        if os.name == "nt" else nullcontext()
    )
    with lock:
        train_and_evaluate(args, settings)


def train_and_evaluate(args, settings):
    import importlib.metadata
    import torch
    from rfdetr import RFDETRSmall
    from edge_threat_response.replay import write_jsonl

    base, output = Path(settings["base"]), args.output.resolve()
    output.mkdir(exist_ok=False)
    require(importlib.metadata.version("rfdetr") == "1.11.2" and torch.cuda.device_count() == 1
            and os.environ.get("CUDA_VISIBLE_DEVICES", "").startswith("GPU-"), "Expected pinned RF-DETR and one GPU")
    require(sha(args.initial) == COCO_RF_SMALL_SHA, "RF-DETR COCO checkpoint changed")
    plan = pin_plan(base)
    train = verified_train(base, plan)
    tuning = development_rows(base, {**plan, "validation": {"tune": plan["validation"]["tune"]}})["tune"]
    tune = [(Path(row["image_file"]), row["boxes"]) for row in tuning]
    phase = output / "state.json"
    save(output / "training-input.json", {"plan_sha256": PLAN_SHA, "initial_sha256": COCO_RF_SMALL_SHA,
         "operational_d1_sha256": D1_SHA, "initialization": "RF-DETR official COCO pretrained",
         "scope": "development_only", "deck": "epoch-1 of pinned plan repeated each epoch; RF-DETR sampler shuffles",
         "per_epoch": len(train), "source_counts": dict(Counter(plan["pool"][k]["domain"] for k, _ in plan["draws"][0])),
         "tile_count": sum(t for _, t in plan["draws"][0]), "seed": SEED, "epochs": args.epochs,
         "loader_batch": 4, "gradient_accumulation": 2, "resolution": SIZE})
    small = output / "smoke-data"
    export_coco(small / "train", balanced_pilot(train, 8))
    export_coco(small / "valid", balanced_pilot(tune, 8))
    save(phase, {"phase": "smoke", "at": now()})
    smoke = fit(small, output / "smoke-run", args.initial, 1)
    restored = RFDETRSmall.from_checkpoint(smoke, device="cuda")
    prediction = restored.predict(str(tune[0][0]), threshold=.001, include_source_image=False)
    names = restored.class_names
    require(prediction.xyxy.ndim == 2 and prediction.xyxy.shape[1] == 4
            and set(names.values() if isinstance(names, dict) else names) == {"knife"},
            "Reloaded smoke checkpoint did not produce knife boxes")
    save(output / "smoke.json", {"checkpoint_sha256": sha(smoke), "prediction_rows": len(prediction), "at": now()})
    del restored
    torch.cuda.empty_cache()
    full = output / "data"
    export_coco(full / "train", train)
    export_coco(full / "valid", tune)
    save(phase, {"phase": "training", "at": now()})
    checkpoint = fit(full, output / "train", args.initial, args.epochs)
    save(phase, {"phase": "evaluation", "at": now(), "checkpoint_sha256": sha(checkpoint)})
    model = RFDETRSmall.from_checkpoint(checkpoint, device="cuda")
    tune_result = score_predictions(checkpoint, tuning, infer_tiles(model, tuning), output / "tune.jsonl")
    threshold = tune_result["point"]["confidence"]
    save(output / "operating-point.json", {"confidence": threshold, "checkpoint_sha256": sha(checkpoint)})
    checked = development_rows(base, {**plan, "validation": {"dev_check": plan["validation"]["dev_check"]}})["dev_check"]
    predictions = infer_tiles(model, checked)
    write_jsonl(output / "dev_check.jsonl", predictions)
    metrics = {**locked(checked, predictions, threshold), **coco_metrics(make_truth(checked), predictions)}
    save(args.evidence, {"checkpoint": str(checkpoint), "checkpoint_sha256": sha(checkpoint),
                         "metrics": metrics, "tune": tune_result, "training_input_sha256": sha(output / "training-input.json")})
    save(phase, {"phase": "completed", "at": now()})


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    for name in ("settings", "initial", "output", "evidence"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--epochs", type=int, default=12)
    run(parser.parse_args())
