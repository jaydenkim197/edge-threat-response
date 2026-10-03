"""Prepare matched-budget R1/H1 inputs; never download data or start training."""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

from .dataset.labels import parse_yolo_label
from .training import TRAINING_GATES, _environment_record, _git_commit, _sha256_file, _write_json


def load_plan(path: Path) -> dict:
    plan = json.loads(path.read_text(encoding="utf-8-sig"))
    if plan.get("schema_version") != 1 or not all(isinstance(plan.get(key), str) and plan[key].strip() for key in ("pair_id", "source_id", "model_family")):
        raise ValueError("Invalid paired training plan")
    arguments = plan.get("arguments", {})
    batch, epochs = arguments.get("batch"), arguments.get("epochs")
    if type(batch) is not int or batch < 1 or type(epochs) is not int or epochs < 1:
        raise ValueError("Matched budget needs positive fixed batch and epochs")
    if arguments.get("nbs") != batch or arguments.get("warmup_epochs") != 0 or arguments.get("patience") != 0 or not isinstance(arguments.get("optimizer"), str) or arguments["optimizer"] in {"", "auto"}:
        raise ValueError("Matched profile requires nbs=batch, warmup=0, patience=0 and explicit optimizer")
    if arguments.get("amp") is not False or type(arguments.get("seed")) is not int:
        raise ValueError("Initial matched budget uses FP32 and an explicit seed")
    if any(key in arguments for key in ("data", "project", "name", "exist_ok", "resume", "time", "fraction")):
        raise ValueError("Unsupported budget/output override in paired plan")
    return plan


def prepare_pair(plan_path: Path, manifest_path: Path, checkpoint: Path, output: Path) -> dict:
    plan = load_plan(plan_path)
    if output.exists():
        raise ValueError("Paired output must be a new directory")
    if not checkpoint.is_file():
        raise ValueError("Provide a local pinned pretrained checkpoint; preparation never downloads it")
    rows = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Materialized source manifest is empty")
    root = manifest_path.parent.resolve()
    normalized = []
    groups, hashes, image_ids = {}, set(), set()
    for row in rows:
        image_id = row.get("image_id")
        if not isinstance(image_id, str) or not image_id.strip() or image_id in image_ids:
            raise ValueError("Materialized image IDs must be nonempty and unique")
        image_ids.add(image_id)
        split = row.get("planned_split")
        if split not in {"train", "val", "test"} or row.get("source_dataset") != plan["source_id"]:
            raise ValueError("Expected the specified source and train/val/test split in materialized manifest")
        group = row.get("source_group")
        if not isinstance(group, str) or not group.strip():
            raise ValueError("Source/session group must be known before paired preparation")
        if group in groups and groups[group] != split:
            raise ValueError("Source/session group crosses dataset splits")
        groups[group] = split
        image, label = (root / row["output_image"]).resolve(), (root / row["output_label"]).resolve()
        if not image.is_relative_to(root / "images") or not label.is_relative_to(root / "labels"):
            raise ValueError("Materialized paths must stay inside source images/labels")
        relative = image.relative_to(root / "images")
        if label != (root / "labels" / relative).with_suffix(".txt"):
            raise ValueError("Labels must match YOLO images-to-labels path convention")
        digest = _sha256_file(image)
        if digest != row.get("image_sha256") or digest in hashes:
            raise ValueError("Source image hash changed or duplicate images remain")
        hashes.add(digest)
        parsed = parse_yolo_label(label, source_dataset=plan["source_id"], path_reference=str(label), class_map={0: 1})
        if parsed.issues or any(item.annotation_format != "bbox" for item in parsed.annotations):
            raise ValueError("Paired preparation requires valid model-local knife bbox/empty labels")
        normalized.append({"image_id": row["image_id"], "source_group": group, "split": split,
                           "image": image.as_posix(), "label": label.as_posix(), "image_sha256": digest,
                           "label_sha256": _sha256_file(label), "knife_count": len(parsed.annotations)})
    normalized.sort(key=lambda item: item["image_id"])
    splits = {split: [row for row in normalized if row["split"] == split] for split in ("train", "val", "test")}
    positives = [row for row in splits["train"] if row["knife_count"]]
    negatives = [row for row in splits["train"] if not row["knife_count"]]
    if not positives or not negatives or not splits["val"] or not splits["test"]:
        raise ValueError("R1/H1 needs train positives+verified negatives and common val/test sets")
    batch = plan["arguments"]["batch"]
    draws = math.ceil(len(splits["train"]) / batch) * batch
    output.mkdir(parents=True)
    lists = {}
    for split in ("val", "test"):
        path = output / f"common-{split}.txt"
        path.write_text("\n".join(row["image"] for row in splits[split]) + "\n", encoding="utf-8")
        lists[split] = path.resolve().as_posix()
    approval = {"schema_version": 1, "pair_id": plan["pair_id"], "status": "pending",
                "approval_id": None, "reviewer_alias": None, "approved_at": None,
                "gates": {key: False for key in TRAINING_GATES}, "recipes": {}}
    for recipe, training_rows in (("R1", splits["train"]), ("H1", positives)):
        # Balanced repetition preserves every unique positive; only training entries repeat.
        repeated = training_rows * (draws // len(training_rows))
        repeated += random.Random(plan["arguments"]["seed"]).sample(training_rows, draws % len(training_rows))
        counts = Counter(row["image"] for row in repeated)
        train_list = output / f"{recipe}-train.txt"
        train_list.write_text("\n".join(row["image"] for row in repeated) + "\n", encoding="utf-8")
        data_yaml = output / f"{recipe}-data.yaml"
        _write_json(data_yaml, {"path": output.resolve().as_posix(), "train": train_list.resolve().as_posix(),
                                **lists, "names": {"0": "knife"}})
        dataset_manifest = output / f"{recipe}-manifest.jsonl"
        selected = [*training_rows, *splits["val"], *splits["test"]]
        with dataset_manifest.open("w", encoding="utf-8") as stream:
            for row in selected:
                stream.write(json.dumps({**row, "draw_count": counts[row["image"]] if row["split"] == "train" else 1}, sort_keys=True) + "\n")
        config_path = output / f"{recipe}-training.json"
        _write_json(config_path, {"schema_version": 1, "profile_id": f"{plan['pair_id']}-{recipe}",
                                  "recipe_id": recipe, "approval_required": True, "model": checkpoint.resolve().as_posix(),
                                  "task": "detect", "run_name": f"{plan['pair_id']}-{recipe}", "arguments": plan["arguments"]})
        bound_files = {"config": config_path, "data_yaml": data_yaml, "dataset_manifest": dataset_manifest,
                       "pretrained": checkpoint, "train_list": train_list, **{f"{split}_list": Path(lists[split]) for split in lists}}
        approval["recipes"][recipe] = {f"{key}_sha256": _sha256_file(path) for key, path in bound_files.items()}
    _write_json(output / "approval.pending.json", approval)
    result = {"schema_version": 1, "pair_id": plan["pair_id"], "status": "prepared_not_approved",
              "plan_sha256": _sha256_file(plan_path), "source_manifest_sha256": _sha256_file(manifest_path),
              "checkpoint_sha256": _sha256_file(checkpoint), "git_commit": _git_commit(),
              "train_unique_positive": len(positives), "train_unique_negative": len(negatives),
              "draws_per_epoch_each": draws, "batches_per_epoch_each": draws // batch,
              "planned_optimizer_updates_each": (draws // batch) * plan["arguments"]["epochs"],
              "common_val_count": len(splits["val"]), "common_test_count": len(splits["test"]),
              "budget_method": "Equal list length; H1 positive repetition; fixed batch/nbs, FP32, no warmup accumulation/early stop",
              "environment": _environment_record()}
    _write_json(output / "pair-preparation.json", result)
    return result


def check_readiness(plan_path: Path, manifest: Path, checkpoint: Path, output: Path) -> dict:
    plan = load_plan(plan_path)
    if output.exists():
        raise ValueError("Readiness output must be a new directory")
    try:
        import torch
        cuda = bool(torch.cuda.is_available())
        devices = [torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())] if cuda else []
    except ImportError:
        cuda, devices = False, []
    missing = [key for key, path in (("approved_materialized_source_manifest", manifest), ("local_pretrained_checkpoint", checkpoint)) if not path.is_file()]
    result = {"schema_version": 1, "pair_id": plan["pair_id"], "status": "blocked" if missing or not cuda else "inputs_present_approval_pending",
              "missing": missing, "cuda_available": cuda, "cuda_devices": devices, "training_started": False,
              "approval_required": True, "manifest": str(manifest.resolve()), "checkpoint": str(checkpoint.resolve()),
              "plan_sha256": _sha256_file(plan_path), "git_commit": _git_commit(), "environment": _environment_record()}
    output.mkdir(parents=True)
    _write_json(output / "readiness.json", result)
    return result


def compare_pair(r1_path: Path, h1_path: Path, output: Path) -> dict:
    if output.exists():
        raise ValueError("Comparison output must be a new directory")
    runs = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (r1_path, h1_path)]
    if [run.get("recipe_id") for run in runs] != ["R1", "H1"] or any(run.get("status") != "passed" for run in runs):
        raise ValueError("Comparison needs completed, approval-gated R1 and H1 invocations")
    a, b = runs
    if not a.get("approval") or not b.get("approval") or a["approval"]["pair_id"] != b["approval"]["pair_id"]:
        raise ValueError("Runs do not share a recorded approved pair")
    for key in ("pretrained", "val_list", "test_list"):
        if a["approval"]["bound_inputs"][key] != b["approval"]["bound_inputs"][key]:
            raise ValueError("Initial checkpoint/common evaluation lists differ")
    if any(a["approval"][key] != b["approval"][key] for key in ("train_draw_count", "planned_optimizer_updates")):
        raise ValueError("Paired sample/update budgets differ")
    args = [{key: value for key, value in run["arguments"].items() if key not in {"data", "project", "name"}} for run in runs]
    if args[0] != args[1] or a["environment"]["packages"] != b["environment"]["packages"]:
        raise ValueError("Training settings or software versions differ")
    keys = ("metrics/precision(B)", "metrics/recall(B)", "metrics/mAP50(B)", "metrics/mAP50-95(B)")
    result = {"schema_version": 1, "pair_id": a["approval"]["pair_id"], "evaluation_partition": "common_validation_tuning",
              "status": "comparison_not_detector_selection", "invocation_sha256": [_sha256_file(path) for path in (r1_path, h1_path)],
              "train_draw_count_each": a["approval"]["train_draw_count"],
              "planned_optimizer_updates_each": a["approval"]["planned_optimizer_updates"],
              "runs": [{"recipe": run["recipe_id"], "metrics": run["metrics"], "duration_seconds": run["duration_seconds"],
                        "artifacts": run["artifacts"]} for run in runs],
              "R1_minus_H1": {key: a["metrics"][key] - b["metrics"][key] for key in keys if key in a["metrics"] and key in b["metrics"]},
              "still_required": ["small/distant knife recall", "hard-negative false positives at documented threshold", "CCTV error review", "repeat seed if difference is small", "Orin runtime check"]}
    output.mkdir(parents=True)
    _write_json(output / "comparison.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "prepare"):
        command = commands.add_parser(name)
        command.add_argument("--plan", required=True, type=Path)
        command.add_argument("--manifest", required=True, type=Path)
        command.add_argument("--checkpoint", required=True, type=Path)
        command.add_argument("--output-dir", required=True, type=Path)
    comparison = commands.add_parser("compare")
    comparison.add_argument("--r1", required=True, type=Path)
    comparison.add_argument("--h1", required=True, type=Path)
    comparison.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            result = compare_pair(args.r1, args.h1, args.output_dir)
        elif args.command == "prepare":
            result = prepare_pair(args.plan, args.manifest, args.checkpoint, args.output_dir)
        else:
            result = check_readiness(args.plan, args.manifest, args.checkpoint, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
