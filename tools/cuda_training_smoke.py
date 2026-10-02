"""CUDA plumbing check on generated rectangles, not a knife performance experiment."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from edge_threat_response.training import run_training, training_preflight


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--amp", action="store_true", help="Also exercise mixed precision.")
    args = parser.parse_args()

    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    from PIL import Image, ImageDraw
    from ultralytics import YOLO

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required; CPU fallback is not permitted.")
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    tensor = torch.randn(64, 64, device="cuda", requires_grad=True)
    (tensor @ tensor.T).square().mean().backward()
    torch.cuda.synchronize()
    if tensor.grad is None or not torch.isfinite(tensor.grad).all():
        raise RuntimeError("CUDA backward produced invalid gradients.")

    records = []
    for split, count in (("train", 8), ("val", 4)):
        images = root / "dataset" / "images" / split
        labels = root / "dataset" / "labels" / split
        images.mkdir(parents=True)
        labels.mkdir(parents=True)
        for index in range(count):
            image = Image.new("RGB", (320, 320), (25 + index * 5, 35, 45))
            draw = ImageDraw.Draw(image)
            x = 50 + index * 12
            draw.rectangle((x, 100, x + 24, 220), fill=(210, 210, 210))
            path = images / f"synthetic-{index}.png"
            image.save(path)
            label = labels / f"synthetic-{index}.txt"
            label.write_text(
                f"0 {(x + 12) / 320:.6f} 0.500000 0.075000 0.375000\n",
                encoding="utf-8",
            )
            records.append({"split": split, "synthetic": True,
                            "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "label_sha256": hashlib.sha256(label.read_bytes()).hexdigest()})
    data = root / "dataset" / "data.yaml"
    data.write_text(f"path: {data.parent.as_posix()}\ntrain: images/train\n"
                    "val: images/val\nnames:\n  0: knife\n", encoding="utf-8")
    manifest = root / "dataset" / "manifest.jsonl"
    manifest.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    config = root / "smoke-config.json"
    config.write_text(json.dumps({
        "schema_version": 1, "profile_id": "synthetic-cuda-plumbing-only",
        "model": "yolo26n.pt", "task": "detect", "run_name": "training",
        "arguments": {"epochs": 1, "imgsz": 320, "batch": 2, "workers": 0,
                      "device": 0, "amp": args.amp, "cache": False, "plots": False,
                      "seed": 20261002, "deterministic": True, "val": True,
                      "save": True, "verbose": False},
    }), encoding="utf-8")
    preflight = training_preflight(config, data_yaml=data, dataset_manifest=manifest,
                                  require_cuda=True)
    (root / "preflight.json").write_text(json.dumps(preflight, indent=2), encoding="utf-8")
    if preflight["status"] != "passed":
        raise RuntimeError("Training preflight failed.")
    trained_model = None

    def model_factory(source):
        nonlocal trained_model
        trained_model = YOLO(source)
        return trained_model

    result = run_training(config, data_yaml=data, output_dir=root / "runs",
                          dataset_manifest=manifest, model_factory=model_factory)
    checkpoints = Path(result["save_dir"]) / "weights"
    for name in ("best.pt", "last.pt"):
        if not (checkpoints / name).is_file():
            raise RuntimeError(f"Missing checkpoint: {name}")
    YOLO(str(checkpoints / "best.pt")).predict(
        source=str(root / "dataset" / "images" / "val" / "synthetic-0.png"),
        device=0, imgsz=320, save=False, verbose=False,
    )
    summary = {"status": "passed", "scope": "synthetic CUDA plumbing only",
               "gpu": torch.cuda.get_device_name(0), "torch": torch.__version__,
               "cuda_runtime": torch.version.cuda, "train_images": 8, "val_images": 4,
               "training_duration_seconds": result["duration_seconds"],
               "checkpoint_reload_inference": "passed",
               "amp_requested": args.amp, "amp_active": bool(trained_model.trainer.amp),
               "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
               "smoke_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if args.amp and not summary["amp_active"]:
        raise RuntimeError("AMP was requested but disabled by the trainer.")
    (root / "smoke-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
