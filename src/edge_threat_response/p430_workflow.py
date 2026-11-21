"""Run the fixed P430 experiments and the separately approved data stages."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import time

from .p430_evaluation import evaluate_checkpoint, make_truth, rank_key
from .training import _sha256_file as sha, gpu_training_lock, run_training

NODES = {"pc11": (1, .00005), "pc12": (1, .00025), "pc13": (2, .00005), "pc14": (2, .00025)}
MODEL_SHA = "c6e5244f649de9722c956e0c861e98975c4334e08cdd9c0a6a74dd53f0e28d0a"
SOURCE_SHA = "f7b49693358f2c3ce7221fa49a3efd9a713b2a2d7c8fcb30a8805ef508e7e90d"
EXTERNAL_SHA = "7b1097509636955d95361b967e36e4e2edfabe7bf1ef64b0beb147234b2bd8b6"
AUGMENTATION = ("translate", "scale", "fliplr", "hsv_h", "hsv_s", "hsv_v")
EPOCHS = 12


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, value):
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        temporary = Path(stream.name)
    try:
        for attempt in range(4):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(.1)
    finally:
        temporary.unlink(missing_ok=True)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def model_path(work):
    return work.parent / "p430-t1-20261120-v1" / "initial.pt"


def config_inputs(work, node, run, unaugmented):
    original = work.parent / "p430-t1-20261120-v1"
    config = read(work / "node.json")
    profile = read(work / "mixed-profile.json")
    fold, lr = NODES[node]
    train_path = work / "mixed-train.json"
    require(sha(train_path) == config["mixed_manifest_sha256"], "Mixed manifest hash does not match the plan")
    require(sha(work / "mixed-profile.json") == config["mixed_profile_sha256"], "Mixed profile hash does not match the plan")
    train = read(train_path)
    val_path = original / "config/val-manifest.json"
    require(sha(val_path) == config["val_manifest_sha256"], "Validation manifest hash does not match the plan")
    val = read(val_path)
    require(sha(model_path(work)) == MODEL_SHA, "Initial detector checkpoint hash mismatch")
    require(sha(original / "dataset/manifest.jsonl") == SOURCE_SHA, "P430 source manifest hash mismatch")
    require(profile["arm"] == "b" and profile["train_session"].endswith(f"{fold:02d}")
            and profile["val_session"].endswith(f"{3-fold:02d}"), "Mixed profile does not match the allocated fold")
    require(len(train) == profile["train_draws"] == (1056 if fold == 1 else 1312)
            and len(val) == profile["val_count"] == (1052 if fold == 1 else 849), "Unexpected train or validation size")
    require(not ({r["image_sha256"] for r in train} & {r["image_sha256"] for r in val}),
            "Train and validation image overlap")
    require(len({r["image_sha256"] for r in train}) == len(train) and len({r["image_sha256"] for r in val}) == len(val),
            "Duplicate supervised input")
    previous_plan = work.parent / "s1-adapt-20261115-v1/plan.json"
    require(sha(previous_plan) == EXTERNAL_SHA, "Protected external split hash mismatch")
    external = read(previous_plan)
    pool = {r["image_sha256"]: r for r in external["pos"] + external["neg_pool"]}
    protected_group = {r["source_group"] for r in external["tune"]}
    protected_hash = {r["image_sha256"] for r in external["tune"]}
    approved_p430 = {r["image_sha256"]: r for r in
                     map(json.loads, (original / "dataset/manifest.jsonl").read_text(encoding="utf-8-sig").splitlines())}
    external_count = 0
    for section, rows in (("train", train), ("val", val)):
        for row in rows:
            if row["origin"] == "p430":
                source = approved_p430[row["image_sha256"]]
                expected_session = profile[f"{section}_session"]
                require(source["session"] == row["session"] == expected_session and
                        row["source_video_sha256"] == source["source_video_sha256"] and
                        source["label_sha256"] == row["label_sha256"], "P430 session or label mismatch")
            else:
                external_count += 1
                source = pool[row["image_sha256"]]
                require(section == "train" and row["origin"] == "reviewed-external-cctv"
                        and row["source_group"] == source["source_group"] not in protected_group
                        and row["image_sha256"] not in protected_hash and row["label_sha256"] == source["label_sha256"],
                        "External record crosses a protected split")
            image, label = Path(row["image_file"]), Path(row["annotation_file"])
            expected_label = image.parent.parent / "labels" / (image.stem + ".txt")
            require(expected_label == label and sha(image) == row["image_sha256"] and sha(label) == row["label_sha256"],
                    f"Input file hash mismatch: {image.name}")
            if section == "val":
                boxes = [list(map(float, line.split()[1:])) for line in label.read_text().splitlines() if line.strip()]
                require(boxes == row["boxes"], "Validation boxes differ from checked labels")
    require(external_count == profile["external_positive"] + profile["external_negative"] ==
            (207 if fold == 1 else 260), "External mixture count mismatch")
    for section, rows in (("train", train), ("val", val)):
        (run / (section + ".txt")).write_text(
            "".join(Path(row["image_file"]).as_posix() + "\n" for row in rows), encoding="utf-8")
    dataset = run / "data.yaml"
    dataset.write_text(f"path: {run.as_posix()}\ntrain: train.txt\nval: val.txt\nnames:\n  0: knife\n", encoding="utf-8")
    arguments = {**profile["args"], "epochs": EPOCHS, "lr0": lr, "save_period": 1}
    if unaugmented:
        arguments.update(dict.fromkeys(AUGMENTATION, 0.0))
    settings = dict(schema_version=1, profile_id="p430-t1-short-development", model=str(model_path(work)),
                    task="detect", run_name="training", arguments=arguments)
    save(run / "profile.json", settings)
    return train, val, dataset


def validate_training(run):
    artifact = run / "training"
    receipt = read(run / "training-invocation.json")
    require(receipt["status"] == "passed", "Training receipt is incomplete")
    with (artifact / "results.csv").open(newline="", encoding="utf-8") as stream:
        require(len(list(csv.DictReader(stream))) == EPOCHS, "Training did not reach 12 epochs")
    weights = artifact / "weights"
    expected = {"best.pt", "last.pt"} | {f"epoch{i}.pt" for i in range(EPOCHS)}
    weight_paths = sorted(weights.glob("*.pt"))
    require({path.name for path in weight_paths} == expected, "Incomplete checkpoint series")
    return {path.name: sha(path) for path in weight_paths}


def train_short(work, node, run, unaugmented):
    import torch
    from ultralytics import YOLO

    require(torch.cuda.is_available() and "RTX 3060" in torch.cuda.get_device_name(0), "Expected an RTX 3060 at CUDA 0")
    train, val, data = config_inputs(work, node, run, unaugmented)
    expected_train = Counter(Path(row["image_file"]) for row in train)
    expected_val = Counter(Path(row["image_file"]) for row in val)

    def model_factory(name):
        model = YOLO(name)
        require(model.names == {0: "knife"}, "Initial model classes differ")

        def check_loaders(trainer):
            require(Counter(Path(x) for x in trainer.train_loader.dataset.im_files) == expected_train,
                    "Train loader differs from the verified manifest")
            require(Counter(Path(x) for x in trainer.test_loader.dataset.im_files) == expected_val,
                    "Validation loader differs from the verified manifest")
            save(run / "progress.json", {"epoch": 0, "epochs": EPOCHS, "train_batches": len(trainer.train_loader),
                                         "gpu": torch.cuda.get_device_name(0), "at": now()})

        def epoch_done(trainer):
            save(run / "progress.json", {"epoch": int(trainer.epoch) + 1, "epochs": EPOCHS, "at": now()})

        model.add_callback("on_train_start", check_loaders)
        model.add_callback("on_fit_epoch_end", epoch_done)
        return model

    run_training(run / "profile.json", data_yaml=data, output_dir=run,
                 dataset_manifest=work / "mixed-train.json", model_factory=model_factory)
    return {"checkpoints": validate_training(run), "training_receipt_sha256": sha(run / "training-invocation.json")}


def evaluate_short(work, node, run, training):
    original = work.parent / "p430-t1-20261120-v1"
    sys.path.insert(0, str(original / "evaluation-deps"))
    val_path = original / "config/val-manifest.json"
    require(sha(val_path) == read(work / "node.json")["val_manifest_sha256"], "Validation manifest changed")
    rows = read(val_path)
    baseline_dir = original / "evaluation"
    baseline = read(baseline_dir / "summary.json")["baseline"]
    require(baseline["checkpoint_sha256"] == sha(model_path(work)) == MODEL_SHA
            and baseline["predictions_sha256"] == sha(baseline_dir / "initial.jsonl")
            and make_truth(rows) == read(baseline_dir / "ground-truth.json"), "Cached baseline does not match the exact validation data")
    checks = validate_training(training)
    require(checks == read(training / "result.json")["checkpoints"], "Trained checkpoint changed")
    files = training / "training/weights"
    candidates = {}
    for name, digest in sorted(checks.items()):
        if digest not in candidates:
            record = evaluate_checkpoint(files / name, rows, run / (Path(name).stem + ".jsonl"))
            require(record["checkpoint_sha256"] == digest, "Evaluated checkpoint changed")
            candidates[digest] = {**record, "aliases": []}
        candidates[digest]["aliases"].append(name)
        save(run / "partial-evaluation.json", list(candidates.values()))
    ranked = sorted(candidates.values(), key=rank_key, reverse=True)
    baseline.update(total_positive=sum(bool(row["boxes"]) for row in rows),
                    negative_frames=sum(not row["boxes"] for row in rows))
    return dict(baseline=baseline, selected=ranked[0], ranked=ranked, selection_partition="tuning",
                val_manifest_sha256=sha(val_path), final_test_used=False)


def approved_manifest(work, name, filename):
    directory = work / name
    approval = read(directory / "approval.json")
    manifest = directory / filename
    require(approval["schema_version"] == 1 and approval["approved_development"] is True
            and approval["manifest_sha256"] == sha(manifest) and approval["annotation_origin"] == "human",
            f"{name} manifest needs matching human-approved development evidence")
    return directory, manifest


def run_hoi(work, run, kind, code_root):
    from .hoi import train

    directory, manifest = approved_manifest(work, "hoi", "pairs.jsonl")
    filename = "geometry.pc13.json" if kind == "g" else "visual-geometry.pc13.json"
    config = code_root / "configs/hoi" / filename
    result = train(config, manifest, directory, run / "model")
    require(result["status"] == "passed" and result["final_test_used"] is False, "HOI training receipt is invalid")
    require(all(sha(run / "model" / f"{key}.pt") == value for key, value in result["checkpoint_sha256"].items()),
            "HOI checkpoint hash mismatch")
    return result


def evaluate_zoom(work, run):
    from statistics import median

    directory, manifest = approved_manifest(work, "zoom", "manifest.json")
    source = read(manifest)
    frames = source["frames"]
    require(source["schema_version"] == 1 and source["partition"] == "tuning"
            and frames and {row["zoom"] for row in frames} == {1, 3, 5},
            "Zoom comparison needs three reviewed development views")
    require(len({row["image_sha256"] for row in frames}) == len(frames), "Duplicate zoom image")
    groups = {row["pair_group"] for row in frames}
    for group in groups:
        paired = [row for row in frames if row["pair_group"] == group]
        zoom_counts = Counter(row["zoom"] for row in paired)
        require(set(zoom_counts) == {1, 3, 5} and len(set(zoom_counts.values())) == 1,
                "Zoom pair group needs a matched number of frames at every setting")
    result = {}
    reference = model_path(work)
    require(sha(reference) == MODEL_SHA, "Invalid reference checkpoint")
    sys.path.insert(0, str(work.parent / "p430-t1-20261120-v1/evaluation-deps"))
    for zoom in (1, 3, 5):
        subset = [row for row in frames if row["zoom"] == zoom]
        for row in subset:
            path = (directory / row["image_path"]).resolve()
            require(path.is_relative_to(directory.resolve()) and sha(path) == row["image_sha256"],
                    "Invalid zoom image path or hash")
            require(type(row["expected_in_view"]) is bool and type(row["in_view"]) is bool
                    and isinstance(row["pair_group"], str) and row["pair_group"]
                    and row["holding_label"] in {"holding", "not_holding", "uncertain"}
                    and isinstance(row["source_video_sha256"], str) and len(row["source_video_sha256"]) == 64,
                    "Missing view coverage or holding annotation")
            require(len(row["boxes"]) <= 1 and all(len(box) == 4 and 0 <= box[0]-box[2]/2 < box[0]+box[2]/2 <= 1
                    and 0 <= box[1]-box[3]/2 < box[1]+box[3]/2 <= 1 for box in row["boxes"]), "Invalid zoom box")
            require((row["holding_label"] != "holding" or row["expected_in_view"])
                    and (row["holding_label"] != "holding" or not row["in_view"] or row["boxes"])
                    and (row["in_view"] or not row["boxes"]), "Inconsistent holding, view coverage or box annotation")
            row.update(image_file=str(path), small=any(min(b[2]*1920, b[3]*1080)/2 < 16 for b in row["boxes"]))
        eligible = [row for row in subset if row["in_view"] or not row["expected_in_view"]]
        sides = [min(b[2]*1920, b[3]*1080) for row in eligible for b in row["boxes"]]
        require(sides and any(not row["boxes"] for row in eligible), "Each zoom needs visible positive and negative frames")
        result[str(zoom)] = {
            **evaluate_checkpoint(reference, eligible, run / f"zoom-{zoom}.jsonl"),
            "short_side_px_median": median(sides), "target_missing": sum(r["expected_in_view"] and not r["in_view"] for r in subset),
            "targets_expected": sum(r["expected_in_view"] for r in subset),
            "target_missing_fraction": (sum(r["expected_in_view"] and not r["in_view"] for r in subset) /
                                        sum(r["expected_in_view"] for r in subset))
                                       if any(r["expected_in_view"] for r in subset) else None,
            "holding_counts": dict(Counter(r["holding_label"] for r in subset)),
        }
    return dict(manifest_sha256=sha(manifest), partition="tuning", zoom=result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("node", choices=NODES)
    parser.add_argument("stage", choices=("train", "eval", "noaug-train", "noaug-eval", "zoom", "hoi-g", "hoi-vg"))
    parser.add_argument("run", type=Path)
    parser.add_argument("--training", type=Path)
    args = parser.parse_args()
    code_root = Path(__file__).resolve().parents[2]
    if args.stage.startswith("hoi-"):
        result = run_hoi(args.work, args.run, args.stage[4:], code_root)
    else:
        lock_path = args.work.parent / "training/gpu0-training.lock"
        lock = gpu_training_lock(lock_path, owner=args.run.parent.name)
        try:
            lock.__enter__()
        except FileExistsError:
            return 75  # A different worker holds this GPU.
        try:
            if args.stage.endswith("train"):
                result = train_short(args.work, args.node, args.run, args.stage == "noaug-train")
            elif args.stage.endswith("eval"):
                result = evaluate_short(args.work, args.node, args.run, args.training)
            else:
                result = evaluate_zoom(args.work, args.run)
        finally:
            lock.__exit__(None, None, None)
    save(args.run / "result.json", result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
