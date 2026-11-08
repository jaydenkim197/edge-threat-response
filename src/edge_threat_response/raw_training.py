"""Hash-bound, unreviewed development recipes and a fail-stop GPU queue.

Human review is explicitly waived for these recipes, never fabricated. Source
annotations and proxy groups remain fallible; this is not final-test approval.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .dataset.labels import parse_yolo_label
from .training import (_sha256_file, _write_json, _git_commit, run_training,
                       TrainingConfig, validate_training_approval)
from .training_pair import load_plan


def prepare_suite(plan_path: Path, inventory: Path, checkpoints: dict[str, Path],
                  output: Path, authorization_reference: str, *, recipes: list[str] | None = None) -> dict:
    plan = load_plan(plan_path)
    if output.exists() or not authorization_reference.strip():
        raise ValueError("New output and explicit user authorization reference required")
    selected_recipes = recipes if recipes is not None else ["RAW-R1-n", "RAW-H1-n", "RAW-M1-n", "RAW-M1-s"]
    known = {"RAW-R1-n": "n", "RAW-H1-n": "n", "RAW-M1-n": "n", "RAW-M1-s": "s", "RAW-M2-n": "n", "RAW-S1-n": "n"}
    if not selected_recipes or len(set(selected_recipes)) != len(selected_recipes) or any(r not in known for r in selected_recipes):
        raise ValueError("Explicit nonempty unique supported raw recipes required")
    if any(known[r] not in checkpoints or not checkpoints[known[r]].is_file() for r in selected_recipes):
        raise ValueError("Pinned local YOLO26 pretrained checkpoints required for selected recipes")
    rows = [json.loads(x) for x in inventory.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    groups, seen = {}, set()
    for row in rows:
        if row.get("split") not in {"train", "val", "test"} or not row.get("source_dataset") or not row.get("source_group"):
            raise ValueError("Source, split and proxy group required")
        group, split = row["source_group"], row["split"]
        if group in groups and groups[group] != split:
            raise ValueError("Proxy group crosses partitions")
        groups[group] = split
        image, label = Path(row["image"]), Path(row["label"])
        if label != Path(str(image).replace("/images/", "/labels/").replace("\\images\\", "\\labels\\")).with_suffix(".txt"):
            raise ValueError("YOLO image/label paths must correspond")
        for key in ("image", "label"):
            if _sha256_file(Path(row[key])) != row[f"{key}_sha256"]:
                raise ValueError("Inventory bytes changed")
        if row["image_sha256"] in seen:
            raise ValueError("Exact duplicates remain in source inventory")
        seen.add(row["image_sha256"])
        parsed = parse_yolo_label(label, source_dataset=row["source_dataset"], path_reference=str(label), class_map={0: 1})
        if parsed.issues or any(x.annotation_format != "bbox" for x in parsed.annotations):
            raise ValueError("Valid knife-only bboxes/explicit empty labels required")
        if len(parsed.annotations) != row.get("knife_count"):
            raise ValueError("Knife count differs from label")
    splits = {s: [r for r in rows if r["split"] == s] for s in ("train", "val", "test")}
    sohas = [r for r in splits["train"] if r["source_dataset"] == "sohas"]
    positive = [r for r in sohas if r["knife_count"] > 0]
    if not positive or not any(not r["knife_count"] for r in sohas) or any(not splits[s] for s in ("val", "test")):
        raise ValueError("Need SOHAS positives/annotation-negatives and common val/test")
    batch = plan["arguments"]["batch"]
    draws = math.ceil(len(splits["train"]) / batch) * batch
    output.mkdir(parents=True)
    common = {}
    for split in ("val", "test"):
        path = output / f"common-{split}.txt"
        path.write_text("\n".join(r["image"] for r in splits[split]) + "\n", encoding="utf-8")
        common[split] = path.resolve().as_posix()
    authorization = {
        "schema_version": 1, "pair_id": plan["pair_id"], "status": "authorized_raw_exploration",
        "approval_id": plan["pair_id"] + "-raw-authorization", "reviewer_alias": "user-directive",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "authorization_reference": authorization_reference,
        "scope": "raw_source_annotations_development_only", "human_review_complete": False,
        "negative_absence_verified": False, "final_evaluation_allowed": False, "recipes": {},
    }
    queue = []
    selections = {"RAW-R1-n": sohas, "RAW-H1-n": positive,
                  "RAW-M1-n": splits["train"], "RAW-M1-s": splits["train"], "RAW-M2-n": splits["train"],
                  "RAW-S1-n": splits["train"]}
    for recipe in selected_recipes:
        selected, size = selections[recipe], known[recipe]
        repeated = selected * (draws // len(selected))
        repeated += random.Random(plan["arguments"]["seed"]).sample(selected, draws % len(selected))
        counts = Counter(r["image"] for r in repeated)
        train = output / f"{recipe}-train.txt"
        train.write_text("\n".join(r["image"] for r in repeated) + "\n", encoding="utf-8")
        data = output / f"{recipe}-data.yaml"
        _write_json(data, {"path": output.resolve().as_posix(), "train": train.resolve().as_posix(), **common, "names": {"0": "knife"}})
        manifest = output / f"{recipe}-manifest.jsonl"
        with manifest.open("w", encoding="utf-8") as f:
            for row in [*selected, *splits["val"], *splits["test"]]:
                f.write(json.dumps({**row, "draw_count": counts[row["image"]] if row["split"] == "train" else 1,
                                    "human_review_status": "not_required_for_raw_exploration",
                                    "negative_absence_verified": False}, sort_keys=True) + "\n")
        checkpoint = checkpoints[size]
        config = output / f"{recipe}-training.json"
        _write_json(config, {"schema_version": 1, "profile_id": recipe, "recipe_id": recipe,
                            "approval_required": True, "model": checkpoint.resolve().as_posix(), "task": "detect",
                            "run_name": f"{plan['pair_id']}-{recipe.lower()}", "arguments": plan["arguments"]})
        files = {"config": config, "data_yaml": data, "dataset_manifest": manifest, "pretrained": checkpoint,
                 "train_list": train, **{f"{s}_list": Path(common[s]) for s in common}}
        authorization["recipes"][recipe] = {f"{key}_sha256": _sha256_file(p) for key, p in files.items()}
        queue.append({"recipe": recipe, "config": str(config.resolve()), "data": str(data.resolve()),
                      "manifest": str(manifest.resolve()), "unique_train": len(selected),
                      "train_sources": dict(Counter(r["source_dataset"] for r in selected)),
                      "source_draws": dict(Counter(r["source_dataset"] for r in repeated))})
    auth = output / "raw-authorization.json"
    _write_json(auth, authorization)
    result = {"schema_version": 1, "scope": authorization["scope"], "suite_id": plan["pair_id"],
              "authorization": str(auth.resolve()), "inventory_sha256": _sha256_file(inventory),
              "plan_sha256": _sha256_file(plan_path), "git_commit": _git_commit(), "queue": queue,
              "draws_per_epoch": draws, "planned_updates_each": draws // batch * plan["arguments"]["epochs"],
              "human_review_complete": False, "final_evaluation_allowed": False}
    _write_json(output / "queue.json", result)
    return result


def run_queue(queue_path: Path, output: Path, *, runner=run_training) -> dict:
    queue = json.loads(queue_path.read_text(encoding="utf-8-sig"))
    entries = queue.get("queue", [])
    if not entries or len({x["recipe"] for x in entries}) != len(entries):
        raise ValueError("Nonempty queue with unique recipes required")
    for item in entries:
        config = TrainingConfig.load(Path(item["config"]))
        validate_training_approval(Path(item["config"]), config, Path(item["data"]), Path(item["manifest"]), Path(queue["authorization"]))
    if runner is run_training:
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("Raw full-training queue requires CUDA; CPU execution is not allowed")
    output.mkdir(parents=True, exist_ok=True)
    lock = output / "gpu0-training.lock"
    claim = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(claim, json.dumps({"pid": os.getpid(), "queue_sha256": _sha256_file(queue_path)}).encode())
    os.close(claim)
    state_path = output / f"{queue['suite_id']}-queue-state.json"
    if state_path.exists():
        lock.unlink()
        raise ValueError("Queue ID already exists; preserve prior state")
    state = {"status": "running", "queue_sha256": _sha256_file(queue_path), "completed": [], "active": None}
    try:
        for item in entries:
            state["active"] = item["recipe"]
            _write_json(state_path, state)
            result = runner(Path(item["config"]), data_yaml=Path(item["data"]), output_dir=output,
                            dataset_manifest=Path(item["manifest"]), approval_path=Path(queue["authorization"]))
            if result["status"] != "passed":
                raise RuntimeError("Training failed; remaining recipes were not launched")
            state["completed"].append(item["recipe"])
        state.update(status="passed", active=None)
    except BaseException as exc:
        state.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(state_path, state)
        lock.unlink()
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    prep = subs.add_parser("prepare")
    for name in ("plan", "inventory", "checkpoint-n", "output-dir"):
        prep.add_argument("--" + name, type=Path, required=True)
    prep.add_argument("--checkpoint-s", type=Path)
    prep.add_argument("--recipe", action="append", dest="recipes")
    prep.add_argument("--authorization-reference", required=True)
    run = subs.add_parser("run")
    run.add_argument("--queue", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        checkpoints = {"n": args.checkpoint_n}
        if args.checkpoint_s is not None:
            checkpoints["s"] = args.checkpoint_s
        result = prepare_suite(args.plan, args.inventory, checkpoints, args.output_dir, args.authorization_reference, recipes=args.recipes)
    else:
        result = run_queue(args.queue, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
