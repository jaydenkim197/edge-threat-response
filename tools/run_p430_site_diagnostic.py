"""Evaluate the same D1 checkpoint with whole-frame, tile and merged inference."""

import argparse
from pathlib import Path

from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.detector_comparison import POLICY
from edge_threat_response.p430_evaluation import evaluate_checkpoint, make_truth, score_predictions
from edge_threat_response.p430_workflow import read, require, save, sha
from edge_threat_response.training import gpu_training_lock
from run_p430_integration import jsonl
from run_p430_site import development_rows, tile_predictions


def merge(full, tiled):
    import torch
    from torchvision.ops import nms

    output = []
    for left, right in zip(full, tiled, strict=True):
        require(left["source_id"] == right["source_id"], "Prediction order does not match")
        boxes = left["detections"] + right["detections"]
        selected = []
        if boxes:
            coordinates = torch.tensor([row["bbox_xyxy"] for row in boxes], dtype=torch.float32)
            scores = torch.tensor([row["confidence"] for row in boxes], dtype=torch.float32)
            selected = [boxes[index] for index in nms(coordinates, scores, .55).tolist()[:300]]
        output.append({**left, "detections": selected})
    return output


def diagnose(work, checkpoint, output, *, interpolation=False, clahe=False):
    require(sha(checkpoint) == "212a4b80e44674a3863daf240e127af797ac34f235a6e8356f23936b6348d190",
            "Expected the pinned D1 weights")
    plan = read(work / "plan.json")
    require(sha(work / "plan.json") == "8a92eefb8f4bf275d5ace1aae46edb37ad7c6fce02a0484e497fec96deb0a28c"
            and plan["summary"]["protection_sha256"] == sha(work / "protection.json"), "Unverified development input")
    partitions = development_rows(work, plan)
    output.mkdir(exist_ok=False)
    report = {}
    with gpu_training_lock(work.parent / "training/gpu0-training.lock", owner=output.name):
        for partition, rows in partitions.items():
            if interpolation or clahe:
                if interpolation:
                    from PIL.Image import Resampling

                    variants = [("bicubic", {"restore": Resampling.BICUBIC}), ("lanczos", {"restore": Resampling.LANCZOS})]
                else:
                    variants = [("clahe", {"clahe": True})]
                metrics = {}
                for name, options in [("native", {}), *variants]:
                    predicted = tile_predictions(checkpoint, rows, **options)
                    metrics[name] = score_predictions(checkpoint, rows, predicted, output / f"{partition}-{name}.jsonl")
            else:
                full960 = output / f"{partition}-full960.jsonl"
                full1280 = output / f"{partition}-full1280.jsonl"
                tiled = tile_predictions(checkpoint, rows)
                metrics = {
                    "full960": evaluate_checkpoint(checkpoint, rows, full960),
                    "full1280": evaluate_checkpoint(checkpoint, rows, full1280, imgsz=1280),
                    "tile640": score_predictions(checkpoint, rows, tiled, output / f"{partition}-tile640.jsonl"),
                }
                joined = merge(jsonl(full960), tiled)
                metrics["hybrid960"] = score_predictions(checkpoint, rows, joined, output / f"{partition}-hybrid960.jsonl")
            if partition == "dev_check":
                for name, record in metrics.items():
                    threshold = report["tune"][name]["point"]["confidence"]
                    rows_pred = jsonl(output / f"{partition}-{name}.jsonl")
                    if threshold is None:
                        rows_pred = [{**row, "detections": []} for row in rows_pred]
                    result, details = evaluate_boxes(make_truth(rows), rows_pred, {**POLICY, "confidence": threshold or .001})
                    record.pop("point")
                    record["locked_point"] = {"confidence": threshold, **result["counts"],
                        "small_tp": sum(len(info["matches"]) for row, info in zip(rows, details, strict=True) if row["small"])}
            report[partition] = metrics
            save(output / "result.json", report)
            print(f"Completed {partition} on {len(rows)} development frames", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("work", "checkpoint", "output"):
        parser.add_argument(name, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--interpolation", action="store_true", help="Compare native tiles against 2x down/up sampling.")
    mode.add_argument("--clahe", action="store_true", help="Compare native tiles against L-channel CLAHE.")
    args = parser.parse_args()
    diagnose(args.work, args.checkpoint, args.output, interpolation=args.interpolation, clahe=args.clahe)
