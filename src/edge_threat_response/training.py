from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


TRAINING_GATES = ("rights", "human_review", "labels_coordinates", "negative_absence", "duplicates_groups", "split", "recipe")


@dataclass(frozen=True)
class TrainingConfig:
    schema_version: int
    profile_id: str
    model: str
    task: str
    run_name: str
    arguments: dict[str, object]
    approval_required: bool = False
    recipe_id: str | None = None

    @classmethod
    def load(cls, path: Path) -> "TrainingConfig":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read training config {path}: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Only training config schema_version 1 is supported.")
        for key in ("profile_id", "model", "task", "run_name"):
            if not isinstance(payload.get(key), str) or not payload[key].strip():
                raise ValueError(f"Training config field {key} must not be empty.")
        if payload["task"] != "detect":
            raise ValueError("Only object detection training is supported.")
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict):
            raise ValueError("Training config arguments must be an object.")
        forbidden = {"data", "project", "name", "exist_ok"}.intersection(arguments)
        if forbidden:
            raise ValueError(
                f"Training config arguments are controlled by the runner: {sorted(forbidden)}"
            )
        required = payload.get("approval_required", False)
        if type(required) is not bool or (required and payload.get("recipe_id") not in {"R1", "H1"}) or (payload.get("recipe_id") in {"R1", "H1"} and not required):
            raise ValueError("Approval-gated profiles require recipe_id R1/H1 and a boolean approval_required")
        return cls(
            schema_version=1,
            profile_id=payload["profile_id"],
            model=payload["model"],
            task=payload["task"],
            run_name=payload["run_name"],
            arguments=dict(arguments),
            approval_required=required,
            recipe_id=payload.get("recipe_id"),
        )


def build_train_arguments(
    config: TrainingConfig,
    *,
    data_yaml: Path,
    output_dir: Path,
    batch_override: int | None = None,
    run_name_override: str | None = None,
) -> dict[str, object]:
    if not data_yaml.is_file():
        raise ValueError(f"Dataset YAML does not exist: {data_yaml}")
    if batch_override is not None and batch_override < 1:
        raise ValueError("batch_override must be positive.")
    run_name = run_name_override or config.run_name
    if not isinstance(run_name, str) or not run_name.strip():
        raise ValueError("run_name_override must not be empty.")
    arguments = dict(config.arguments)
    if batch_override is not None:
        arguments["batch"] = batch_override
    arguments.update(
        {
            "data": str(data_yaml.resolve()),
            "project": str(output_dir.resolve()),
            "name": run_name,
            "exist_ok": False,
        }
    )
    return arguments


def run_training(
    config_path: Path,
    *,
    data_yaml: Path,
    output_dir: Path,
    batch_override: int | None = None,
    run_name_override: str | None = None,
    dataset_manifest: Path | None = None,
    model_factory: Callable[[str], Any] | None = None,
    approval_path: Path | None = None,
) -> dict[str, object]:
    config = TrainingConfig.load(config_path)
    approval = validate_training_approval(config_path, config, data_yaml, dataset_manifest, approval_path)
    if config.approval_required and batch_override is not None and batch_override != config.arguments.get("batch"):
        raise ValueError("Paired batch changes require regenerating both profiles and their approval")
    arguments = build_train_arguments(
        config,
        data_yaml=data_yaml,
        output_dir=output_dir,
        batch_override=batch_override,
        run_name_override=run_name_override,
    )
    run_name = str(arguments["name"])
    run_dir = output_dir / run_name
    if run_dir.exists():
        raise ValueError(f"Training run directory already exists: {run_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / f"{run_name}-invocation.json"
    if evidence_path.exists():
        raise ValueError(f"Training evidence already exists: {evidence_path}")
    started_at = datetime.now(timezone.utc)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "status": "running",
        "started_at": started_at.isoformat(),
        "profile_id": config.profile_id,
        "config_path": str(config_path.resolve()),
        "config_sha256": _sha256_file(config_path),
        "data_yaml": str(data_yaml.resolve()),
        "data_yaml_sha256": _sha256_file(data_yaml),
        "model": config.model,
        "arguments": arguments,
        "environment": _environment_record(),
        "git_commit": _git_commit(),
        "recipe_id": config.recipe_id,
        "approval": approval,
    }
    if dataset_manifest is not None:
        if not dataset_manifest.is_file():
            raise ValueError(f"Dataset manifest does not exist: {dataset_manifest}")
        manifest["dataset_manifest"] = {
            "path": str(dataset_manifest.resolve()),
            "sha256": _sha256_file(dataset_manifest),
        }
    _write_json(evidence_path, manifest)
    started = time.monotonic()
    try:
        if model_factory is None:
            from ultralytics import YOLO

            model_factory = YOLO
        model = model_factory(config.model)
        model_source = Path(config.model)
        if model_source.is_file():
            manifest["model_source"] = {
                "path": str(model_source.resolve()),
                "size_bytes": model_source.stat().st_size,
                "sha256": _sha256_file(model_source),
            }
            _write_json(evidence_path, manifest)
        result = model.train(**arguments)
        elapsed = time.monotonic() - started
        save_dir = Path(getattr(result, "save_dir", run_dir))
        manifest.update(
            {
                "status": "passed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": elapsed,
                "save_dir": str(save_dir.resolve()),
                "artifacts": _artifact_records(save_dir),
                "metrics": _json_safe(getattr(result, "results_dict", {})),
            }
        )
    except BaseException as exc:
        manifest.update(
            {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": time.monotonic() - started,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        _write_json(evidence_path, manifest)
        raise
    _write_json(evidence_path, manifest)
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="etr-train", description="Run a recorded, config-driven detector training job."
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch", type=int)
    parser.add_argument("--run-name")
    parser.add_argument("--dataset-manifest", type=Path)
    parser.add_argument("--approval", type=Path, help="Hash-bound human approval required by R1/H1 profiles.")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate the training environment and exit without loading a model.",
    )
    parser.add_argument(
        "--require-cuda",
        action="store_true",
        help="Make preflight fail unless a CUDA device is available.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.preflight_only:
            result = training_preflight(
                args.config,
                data_yaml=args.data,
                dataset_manifest=args.dataset_manifest,
                require_cuda=args.require_cuda,
                approval_path=args.approval,
            )
            args.output_dir.mkdir(parents=True, exist_ok=True)
            _write_json(args.output_dir / "preflight.json", result)
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0 if result["status"] == "passed" else 2
        if args.require_cuda:
            preflight = training_preflight(args.config, data_yaml=args.data, dataset_manifest=args.dataset_manifest,
                                           require_cuda=True, approval_path=args.approval)
            if preflight["status"] != "passed":
                print(json.dumps(preflight, ensure_ascii=False))
                return 2
        manifest = run_training(
            args.config,
            data_yaml=args.data,
            output_dir=args.output_dir,
            batch_override=args.batch,
            run_name_override=args.run_name,
            dataset_manifest=args.dataset_manifest,
            approval_path=args.approval,
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


def training_preflight(
    config_path: Path,
    *,
    data_yaml: Path,
    dataset_manifest: Path | None,
    require_cuda: bool,
    torch_module: Any | None = None,
    approval_path: Path | None = None,
) -> dict[str, object]:
    config = TrainingConfig.load(config_path)
    approval = validate_training_approval(config_path, config, data_yaml, dataset_manifest, approval_path)
    if not data_yaml.is_file():
        raise ValueError(f"Dataset YAML does not exist: {data_yaml}")
    if dataset_manifest is not None and not dataset_manifest.is_file():
        raise ValueError(f"Dataset manifest does not exist: {dataset_manifest}")
    if torch_module is None:
        try:
            import torch as torch_module
        except ImportError as exc:
            raise RuntimeError("PyTorch is not installed in the training environment.") from exc
    cuda_available = bool(torch_module.cuda.is_available())
    device_count = int(torch_module.cuda.device_count()) if cuda_available else 0
    devices = [torch_module.cuda.get_device_name(index) for index in range(device_count)]
    errors = []
    if require_cuda and not cuda_available:
        errors.append("CUDA is required but torch.cuda.is_available() is false.")
    return {
        "schema_version": 1,
        "status": "failed" if errors else "passed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "profile_id": config.profile_id,
        "config_path": str(config_path.resolve()),
        "config_sha256": _sha256_file(config_path),
        "data_yaml": str(data_yaml.resolve()),
        "data_yaml_sha256": _sha256_file(data_yaml),
        "dataset_manifest": (
            {
                "path": str(dataset_manifest.resolve()),
                "sha256": _sha256_file(dataset_manifest),
            }
            if dataset_manifest is not None
            else None
        ),
        "git_commit": _git_commit(),
        "environment": _environment_record(),
        "cuda": {
            "required": require_cuda,
            "available": cuda_available,
            "device_count": device_count,
            "devices": devices,
        },
        "errors": errors,
        "approval": approval,
    }


def validate_training_approval(config_path: Path, config: TrainingConfig, data_yaml: Path,
                               dataset_manifest: Path | None, approval_path: Path | None) -> dict[str, object] | None:
    if not config.approval_required:
        return None
    if approval_path is None or dataset_manifest is None:
        raise ValueError("R1/H1 training requires --approval and --dataset-manifest before model loading")
    approval = json.loads(approval_path.read_text(encoding="utf-8-sig"))
    if not isinstance(approval, dict) or approval.get("schema_version") != 1 or approval.get("status") != "approved":
        raise ValueError("Dataset/recipe approval is pending; training is blocked")
    if any(not isinstance(approval.get(key), str) or not approval[key].strip() for key in ("pair_id", "approval_id", "reviewer_alias", "approved_at")):
        raise ValueError("Approval identity/date is missing")
    if not isinstance(approval.get("gates"), dict) or any(approval["gates"].get(key) is not True for key in TRAINING_GATES):
        raise ValueError("Source/label/negative/group/split/recipe gates are not all approved")
    entry = approval.get("recipes", {}).get(config.recipe_id) if isinstance(approval.get("recipes"), dict) else None
    if not isinstance(entry, dict):
        raise ValueError("Approval does not bind this recipe")
    data = json.loads(data_yaml.read_text(encoding="utf-8-sig"))
    files = {"config": config_path, "data_yaml": data_yaml, "dataset_manifest": dataset_manifest,
             "pretrained": Path(config.model), **{f"{split}_list": Path(data[split]) for split in ("train", "val", "test")}}
    hashes = {key: _sha256_file(path) for key, path in files.items()}
    if any(entry.get(f"{key}_sha256") != digest for key, digest in hashes.items()):
        raise ValueError("Approved training inputs/config/checkpoint hashes changed")
    rows = [json.loads(line) for line in dataset_manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("Approved dataset manifest is empty")
    from collections import Counter
    expected = {split: Counter() for split in ("train", "val", "test")}
    for row in rows:
        if row.get("split") not in expected or type(row.get("draw_count")) is not int or row["draw_count"] < 1:
            raise ValueError("Invalid split/draw count in approved manifest")
        for key in ("image", "label"):
            if _sha256_file(Path(row[key])) != row[f"{key}_sha256"]:
                raise ValueError("Approved image/label bytes changed")
        expected[row["split"]][row["image"]] += row["draw_count"]
    for split in expected:
        actual = Counter(files[f"{split}_list"].read_text(encoding="utf-8").splitlines())
        if actual != expected[split]:
            raise ValueError("Training list multiplicities differ from approved manifest")
    train_draws = sum(expected["train"].values())
    return {"pair_id": approval["pair_id"], "approval_id": approval["approval_id"],
            "approval_sha256": _sha256_file(approval_path), "bound_inputs": hashes,
            "train_draw_count": train_draws,
            "planned_optimizer_updates": math.ceil(train_draws / config.arguments["batch"]) * config.arguments["epochs"]}


def _environment_record() -> dict[str, object]:
    packages: dict[str, str | None] = {}
    for name in ("ultralytics", "torch", "torchvision", "opencv-python", "numpy"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "packages": packages,
    }


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _artifact_records(save_dir: Path) -> list[dict[str, object]]:
    if not save_dir.is_dir():
        return []
    records: list[dict[str, object]] = []
    for path in sorted(save_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".pt", ".csv", ".json"}:
            continue
        records.append(
            {
                "path": str(path.resolve()),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return records


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    return str(value)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    raise SystemExit(main())
