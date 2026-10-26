"""Bounded development refinements of the same reviewed SOHAS split."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .training import TrainingConfig, _git_commit, _sha256_file, _write_json, validate_training_approval


VARIANTS = {
    "adamw": {"optimizer": "AdamW", "lr0": .001},
    "smallscale": {"optimizer": "AdamW", "lr0": .001, "scale": .9},
}


def prepare_refinement(base: Path, output: Path, variant: str, authorization_id: str) -> dict:
    base, output = base.resolve(), output.resolve()
    if (variant not in VARIANTS or not authorization_id.strip() or output.exists()
            or output.is_relative_to(base) or base.is_relative_to(output)):
        raise ValueError("Use a known bounded variant, explicit authorization and fresh independent output")
    config = TrainingConfig.load(base / "training.json")
    if config.recipe_id != "DEV-SOHAS":
        raise ValueError("Only the authorized SOHAS development subset can be refined")
    validate_training_approval(base / "training.json", config, base / "data.yaml",
                               base / "DEV-manifest.jsonl", base / "development-authorization.json")
    if config.arguments.get("optimizer") != "SGD" or config.arguments.get("scale") != .5:
        raise ValueError("Refinements must branch from the original SGD/scale=.5 baseline")
    original = {name: _sha256_file(base / name) for name in
                ("training.json", "data.yaml", "DEV-manifest.jsonl", "development-authorization.json", "train.txt", "val.txt", "test.txt")}
    output.mkdir(parents=True)
    for name in ("DEV-manifest.jsonl", "train.txt", "val.txt", "test.txt"):
        shutil.copyfile(base / name, output / name)
    data = json.loads((base / "data.yaml").read_text(encoding="utf-8-sig"))
    data.update(path=output.as_posix(), **{split: (output / f"{split}.txt").as_posix() for split in ("train", "val", "test")})
    _write_json(output / "data.yaml", data)
    payload = json.loads((base / "training.json").read_text(encoding="utf-8-sig"))
    payload.update(profile_id=output.name, run_name=output.name)
    payload["arguments"].update(VARIANTS[variant])
    _write_json(output / "training.json", payload)
    approval = json.loads((base / "development-authorization.json").read_text(encoding="utf-8-sig"))
    approval.update(pair_id=output.name, approval_id=authorization_id, approved_at=datetime.now(timezone.utc).isoformat())
    files = {"config": output / "training.json", "data_yaml": output / "data.yaml", "dataset_manifest": output / "DEV-manifest.jsonl",
             "pretrained": Path(config.model), **{f"{split}_list": output / f"{split}.txt" for split in ("train", "val", "test")}}
    approval["recipes"] = {"DEV-SOHAS": {f"{key}_sha256": _sha256_file(path) for key, path in files.items()}}
    _write_json(output / "development-authorization.json", approval)
    result = {"schema_version": 1, "status": "authorized_development_only", "variant": variant,
              "git_commit": _git_commit(), "base": base.as_posix(), "base_sha256": original,
              "argument_changes": {key: {"before": config.arguments[key], "after": val} for key, val in VARIANTS[variant].items()},
              "train_val_test_lists_unchanged": True, "new_source_images": 0, "final_evaluation_allowed": False,
              "limits": ["development tuning on 23 validation images, not final research evaluation",
                         "AdamW and learning rate change together; optimizer alone is not isolated",
                         "scale=.9 broadens random affine scale; generated small boxes are not new real CCTV observations"]}
    if original != {name: _sha256_file(base / name) for name in original}:
        raise ValueError("Base inputs changed during preparation")
    validate_training_approval(output / "training.json", TrainingConfig.load(output / "training.json"),
                               output / "data.yaml", output / "DEV-manifest.jsonl", output / "development-authorization.json")
    _write_json(output / "refinement.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--variant", choices=VARIANTS, required=True)
    parser.add_argument("--authorization-id", required=True)
    args = parser.parse_args(argv)
    result = prepare_refinement(args.base, args.output_dir, args.variant, args.authorization_id)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
