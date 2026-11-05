"""Lightweight supervised Holding models; torch/vision are lazy dependencies."""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path
from contextlib import nullcontext

from .domain import BBox, FrameStatus
from .dataset.image_screening import image_signature
from .relations import score_row
from .training import _sha256_file, _write_json, _environment_record, _git_commit, gpu_training_lock


FEATURE_VERSION = "union-relative-two-boxes-8-v1"
LABELS = {"not_holding": 0, "holding": 1, "uncertain": None}


def geometry_features(person: BBox, knife: BBox) -> tuple[float, ...]:
    left, top = min(person.x_min, knife.x_min), min(person.y_min, knife.y_min)
    width, height = max(person.x_max, knife.x_max)-left, max(person.y_max, knife.y_max)-top
    return tuple(v for box in (person, knife) for v in
                 ((box.x_min-left)/width, (box.y_min-top)/height,
                  (box.x_max-left)/width, (box.y_max-top)/height))


def load_pairs(path: Path, image_root: Path) -> list[dict]:
    root = image_root.resolve()
    rows, ids, groups, sessions, images, identities = [], set(), {}, {}, {}, set()
    signatures = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip(): continue
        row = json.loads(line)
        if row.get("schema_version") != 1:
            raise ValueError("Only HOI pair schema_version 1 is supported")
        for key in ("pair_id", "source_id", "session_id", "leakage_group_id", "image_path", "annotation_version"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"HOI row requires {key}")
        if row["pair_id"] in ids:
            raise ValueError("Duplicate pair ID")
        ids.add(row["pair_id"])
        partition = row.get("partition")
        if partition not in {"train", "pilot", "tuning", "final_test"}:
            raise ValueError("Unknown HOI partition")
        if row.get("holding_label") not in LABELS or row.get("annotation_origin") not in {"human", "synthetic"}:
            raise ValueError("Explicit holding label and annotation origin required")
        if row.get("boxes_source") not in {"ground_truth", "predicted"}:
            raise ValueError("Explicit GT/predicted box source required")
        if type(row.get("frame_index")) is not int or row["frame_index"] < 0:
            raise ValueError("Nonnegative frame index required")
        value = row.get("timestamp_s")
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Finite nonnegative source timestamp required")
        reference = Path(row["image_path"])
        image = (root/reference).resolve()
        if reference.is_absolute() or not image.is_relative_to(root):
            raise ValueError("Image must be a relative path within image root")
        if image not in signatures:
            signatures[image] = image_signature(image)
        sig = signatures[image]
        if row.get("image_sha256") != sig["image_sha256"] or sig["exif_orientation"] != 1:
            raise ValueError("HOI image hash/orientation changed")
        for key in ("person_bbox_xyxy", "knife_bbox_xyxy"):
            coords = row.get(key)
            if not isinstance(coords, list) or len(coords) != 4 or any(type(v) not in (int, float) for v in coords):
                raise ValueError("Pixel xyxy coordinates required")
            box = BBox(*coords)
            if not (0 <= box.x_min < box.x_max <= sig["width"] and 0 <= box.y_min < box.y_max <= sig["height"]):
                raise ValueError("HOI box exceeds stored image pixels")
        identity = (sig["image_sha256"], tuple(row["person_bbox_xyxy"]), tuple(row["knife_bbox_xyxy"]), row["boxes_source"])
        if identity in identities:
            raise ValueError("Duplicate person/knife pair under different pair IDs")
        identities.add(identity)
        for lookup, key in ((groups, row["leakage_group_id"]), (sessions, (row["source_id"], row["session_id"])),
                            (images, sig["image_sha256"])):
            if key in lookup and lookup[key] != partition:
                raise ValueError("HOI image/session/leakage group crosses partitions")
            lookup[key] = partition
        rows.append({**row, "image": str(image)})
    if not rows:
        raise ValueError("HOI pair manifest is empty")
    return rows


def make_model(kind: str, *, pretrained: bool):
    import torch
    from torch import nn
    if kind not in {"G", "VG"}:
        raise ValueError("HOI kind must be G or VG")

    class HoldingModel(nn.Module):
        def __init__(self):
            super().__init__()
            if kind == "VG":
                from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
                net = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None)
                self.visual = net.features
                self.head = nn.Sequential(nn.Linear(576+8, 64), nn.ReLU(), nn.Linear(64, 1))
            else:
                self.visual = None
                self.head = nn.Sequential(nn.Linear(8, 32), nn.ReLU(), nn.Linear(32, 16), nn.ReLU(), nn.Linear(16, 1))

        def forward(self, crop, geometry):
            if self.visual is not None:
                visual = self.visual(crop).mean((2, 3))
                geometry = torch.cat((visual, geometry), dim=1)
            return self.head(geometry).flatten()
    return HoldingModel()


def crop_tensor(image, person: BBox, knife: BBox, size: int):
    import torch
    from PIL import Image
    if size not in {224, 256}:
        raise ValueError("Union crop size must be 224 or 256")
    x1, y1 = min(person.x_min, knife.x_min), min(person.y_min, knife.y_min)
    x2, y2 = max(person.x_max, knife.x_max), max(person.y_max, knife.y_max)
    pad_x, pad_y = .1*(x2-x1), .1*(y2-y1)
    crop = image.crop((max(0, math.floor(x1-pad_x)), max(0, math.floor(y1-pad_y)),
                       min(image.width, math.ceil(x2+pad_x)), min(image.height, math.ceil(y2+pad_y))))
    ratio = min(size/crop.width, size/crop.height)
    resized = crop.resize((max(1, round(crop.width*ratio)), max(1, round(crop.height*ratio))), Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    canvas.paste(resized, ((size-resized.width)//2, (size-resized.height)//2))
    # Avoid numpy and keep RGB order explicit for both file and BGR live input.
    values = torch.frombuffer(bytearray(canvas.tobytes()), dtype=torch.uint8).reshape(size, size, 3).permute(2, 0, 1).float()/255
    mean = torch.tensor([.485, .456, .406])[:, None, None]
    std = torch.tensor([.229, .224, .225])[:, None, None]
    return (values-mean)/std


def pair_tensors(row, size, visual):
    import torch
    from PIL import Image
    person, knife = BBox(*row["person_bbox_xyxy"]), BBox(*row["knife_bbox_xyxy"])
    if visual:
        with Image.open(row["image"]) as im:
            crop = crop_tensor(im.convert("RGB"), person, knife, size)
    else:
        crop = torch.zeros(1)
    return crop, torch.tensor(geometry_features(person, knife), dtype=torch.float32), torch.tensor(float(LABELS[row["holding_label"]]))


def pair_metrics(truth, scores, threshold):
    if (len(truth) != len(scores) or any(y not in (0, 1) for y in truth)
            or type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1
            or any(type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1 for p in scores)):
        raise ValueError("Pair metrics require aligned binary labels and finite probability scores")
    tp = sum(y == 1 and p >= threshold for y, p in zip(truth, scores))
    fp = sum(y == 0 and p >= threshold for y, p in zip(truth, scores))
    fn = sum(y == 1 and p < threshold for y, p in zip(truth, scores))
    tn = len(truth)-tp-fp-fn
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp/(tp+fp) if tp+fp else None, "recall": tp/(tp+fn) if tp+fn else None,
            "f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None}


def predict_rows(model, rows, *, kind, size, device):
    import torch
    model.eval()
    probabilities = []
    with torch.inference_mode():
        for row in rows:
            crop, geometry, _ = pair_tensors(row, size, kind == "VG")
            probabilities.append(float(model(crop.unsqueeze(0).to(device), geometry.unsqueeze(0).to(device)).sigmoid().cpu()[0]))
    return probabilities


def train(config_path: Path, manifest: Path, image_root: Path, output: Path):
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    guard = gpu_training_lock(Path(config.get("gpu_lock_file", "runs/training/gpu0-training.lock")), owner="hoi:"+output.name) if config.get("device", "cpu") != "cpu" else nullcontext()
    with guard:
        return _train_claimed(config_path, manifest, image_root, output, config)


def _train_claimed(config_path, manifest, image_root, output, config):
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch
    if output.exists(): raise ValueError("HOI run output must be new")
    if config.get("schema_version") != 1 or config.get("kind") not in {"G", "VG"} or config.get("crop_size") not in {224, 256}:
        raise ValueError("Invalid HOI config")
    for key in ("epochs", "batch", "seed", "early_stopping_patience"):
        if type(config.get(key)) is not int or config[key] < 1:
            raise ValueError(f"Positive {key} required")
    if config.get("data_kind") not in {"human", "synthetic"} or type(config.get("pretrained")) is not bool:
        raise ValueError("Explicit data_kind and pretrained policy required")
    if config["data_kind"] == "human" and config["kind"] == "VG" and not config["pretrained"]:
        raise ValueError("Real B4-VG starts from ImageNet pretrained weights")
    device = config.get("device", "cpu")
    if device != "cpu" and not torch.cuda.is_available(): raise RuntimeError("Requested HOI CUDA device unavailable")
    rows = load_pairs(manifest, image_root)
    selected = {s: [r for r in rows if r["partition"] == s and r["holding_label"] != "uncertain"] for s in ("train", "tuning")}
    if any(not selected[s] for s in selected): raise ValueError("Labeled train and tuning pairs required")
    if any(r["boxes_source"] != "ground_truth" or r["annotation_origin"] != config["data_kind"] for s in selected for r in selected[s]):
        raise ValueError("Training/tuning requires GT boxes and matching human/synthetic origin")
    if any({r["holding_label"] for r in selected[s]} != {"holding", "not_holding"} for s in selected):
        raise ValueError("Both labels required in train and tuning")
    random.seed(config["seed"])
    torch.manual_seed(config["seed"])
    torch.set_num_threads(min(4, torch.get_num_threads()))
    torch.use_deterministic_algorithms(True)
    output.mkdir(parents=True)
    evidence = {"status": "running", "config": config, "config_sha256": _sha256_file(config_path),
                "pairs_sha256": _sha256_file(manifest), "git_commit": _git_commit(), "environment": _environment_record(),
                "feature_version": FEATURE_VERSION, "trained_partitions": ["train"], "selection_partition": "tuning",
                "final_test_used": False, "counts": {s: len(v) for s, v in selected.items()},
                "uncertain_excluded": sum(r["holding_label"] == "uncertain" for r in rows)}
    _write_json(output/"invocation.json", evidence)
    started = time.monotonic()
    try:
        model = make_model(config["kind"], pretrained=config["pretrained"]).to(device)
        torch.save(model.state_dict(), output/"initial-state.pt")
        evidence["initial_state_sha256"] = _sha256_file(output/"initial-state.pt")
        evidence["optimizer"] = {"name": "AdamW", "head_lr": .001, "visual_lr": .0001, "weight_decay": .0001}
        evidence["visual_initialization"] = "MobileNet_V3_Small_Weights.IMAGENET1K_V1" if config["kind"] == "VG" and config["pretrained"] else "random_seeded"
        if config["kind"] == "VG" and config["pretrained"]:
            from torchvision.models import MobileNet_V3_Small_Weights
            from urllib.parse import urlsplit
            url = MobileNet_V3_Small_Weights.IMAGENET1K_V1.url
            pretrained = Path(torch.hub.get_dir())/"checkpoints"/Path(urlsplit(url).path).name
            evidence["visual_pretrained"] = {"url": url, "sha256": _sha256_file(pretrained)}
        groups = [{"params": model.head.parameters(), "lr": .001}]
        if model.visual is not None: groups.append({"params": model.visual.parameters(), "lr": .0001})
        optimizer = torch.optim.AdamW(groups, weight_decay=.0001)
        positives = sum(r["holding_label"] == "holding" for r in selected["train"])
        criterion = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor([(len(selected["train"])-positives)/positives], device=device))
        history, best, stale = [], -1., 0
        truth = [LABELS[r["holding_label"]] for r in selected["tuning"]]
        for epoch in range(config["epochs"]):
            model.train()
            order = list(selected["train"])
            random.Random(config["seed"]+epoch).shuffle(order)
            losses = []
            for start in range(0, len(order), config["batch"]):
                items = [pair_tensors(r, config["crop_size"], config["kind"] == "VG") for r in order[start:start+config["batch"]]]
                crop, geometry, labels = [torch.stack(v).to(device) for v in zip(*items)]
                # MobileNet BatchNorm requires >1 sample in a final singleton batch.
                if len(items) == 1 and config["kind"] == "VG":
                    for layer in model.visual.modules():
                        if isinstance(layer, torch.nn.BatchNorm2d): layer.eval()
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(model(crop, geometry), labels)
                loss.backward()
                optimizer.step()
                losses.append(float(loss.detach().cpu()))
            scores = predict_rows(model, selected["tuning"], kind=config["kind"], size=config["crop_size"], device=device)
            choices = [(pair_metrics(truth, scores, i/100), i/100) for i in range(5, 100, 5)]
            metrics, threshold = max(choices, key=lambda x: (x[0]["f1"] or 0, x[0]["recall"] or 0, -x[0]["fp"], -x[1]))
            history.append({"epoch": epoch+1, "loss_mean": sum(losses)/len(losses), "tuning": metrics, "threshold": threshold})
            payload = {"schema_version": 1, "feature_version": FEATURE_VERSION, "config": config,
                       "state_dict": model.state_dict(), "threshold": threshold, "epoch": epoch+1,
                       "pairs_sha256": evidence["pairs_sha256"], "data_kind": config["data_kind"]}
            torch.save(payload, output/"last.pt")
            if (metrics["f1"] or 0) > best:
                best, stale = metrics["f1"] or 0, 0
                torch.save(payload, output/"best.pt")
            else: stale += 1
            _write_json(output/"history.json", history)
            if stale >= config["early_stopping_patience"]: break
        evidence.update(status="passed", duration_seconds=time.monotonic()-started, best_tuning_f1=best,
                        checkpoint_sha256={s: _sha256_file(output/(s+".pt")) for s in ("best", "last")})
    except BaseException as exc:
        evidence.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(output/"invocation.json", evidence)
    return evidence


class TorchRelationProvider:
    def __init__(self, checkpoint: Path, *, device="cpu"):
        import torch
        self.payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if self.payload.get("schema_version") != 1 or self.payload.get("feature_version") != FEATURE_VERSION:
            raise ValueError("Unsupported HOI checkpoint/feature contract")
        self.config = self.payload["config"]
        self.model = make_model(self.config["kind"], pretrained=False).to(device)
        self.model.load_state_dict(self.payload["state_dict"], strict=True)
        self.model.eval()
        self.device, self.packet = device, None
        self.threshold = self.payload["threshold"]
        if type(self.threshold) not in (int, float) or not math.isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("Invalid checkpoint holding threshold")
        self.checkpoint_sha256 = _sha256_file(checkpoint)

    def bind(self, packet): self.packet = packet

    def __call__(self, frame, pairs):
        import torch
        from PIL import Image
        if not pairs: return ()
        if frame.status is not FrameStatus.VALID: return tuple(None for _ in pairs)
        if self.packet is None or (self.packet.source_id, self.packet.frame_index) != (frame.source_id, frame.frame_index):
            raise ValueError("HOI provider has no matching source image")
        image = Image.fromarray(self.packet.image[:, :, ::-1]) if self.config["kind"] == "VG" else None
        scores = []
        with torch.inference_mode():
            for pair in pairs:
                if pair.person is None:
                    scores.append(None)
                    continue
                geometry = torch.tensor([geometry_features(pair.person.bbox, pair.knife.bbox)], dtype=torch.float32, device=self.device)
                crop = crop_tensor(image, pair.person.bbox, pair.knife.bbox, self.config["crop_size"]).unsqueeze(0).to(self.device) if image else torch.zeros(1, 1, device=self.device)
                scores.append(float(self.model(crop, geometry).sigmoid().cpu()[0]))
        return tuple(scores)


def export_scores(checkpoint, detections, media, pipeline_config, output, device):
    from .config import load_pipeline_config
    from .media import OpenCVFrameSource
    from .replay import load_detection_replay, write_jsonl
    from .spatial import associate_person_knives
    frames = load_detection_replay(detections)
    config = load_pipeline_config(pipeline_config)
    if output.exists(): raise ValueError("Relation output must be new")
    detector_summary = json.loads((detections.parent/"summary.json").read_text(encoding="utf-8-sig"))
    if (detector_summary.get("detections_sha256") != _sha256_file(detections)
            or detector_summary.get("provenance", {}).get("input", {}).get("sha256") != _sha256_file(media)):
        raise ValueError("Original media/detection summary provenance mismatch")
    provider = TorchRelationProvider(checkpoint, device=device)
    by_index = iter(OpenCVFrameSource(media, source_id=frames[0].source_id))
    current = next(by_index, None)
    rows = [{"type": "relation_provenance", "schema_version": 1, "detections_sha256": _sha256_file(detections),
             "classifier_sha256": provider.checkpoint_sha256, "image_source_sha256": _sha256_file(media),
             "pipeline_config_sha256": _sha256_file(pipeline_config), "feature_version": FEATURE_VERSION,
             "data_kind": provider.payload["data_kind"], "kind": provider.config["kind"]}]
    for frame in frames:
        while current is not None and current.frame_index < frame.frame_index: current = next(by_index, None)
        if current is None or current.frame_index != frame.frame_index:
            raise ValueError("Original media does not cover detection frames")
        if abs(current.timestamp_s-frame.timestamp_s) > .001:
            raise ValueError("Media and detector timestamp contracts differ")
        provider.bind(current)
        people = tuple(x for x in frame.detections if x.label == "person" and x.confidence >= config.person_confidence_threshold)
        knives = tuple(x for x in frame.detections if x.label == "knife" and x.confidence >= config.knife_confidence_threshold)
        pairs = associate_person_knives(people, knives, policy=config.spatial_policy,
                                       normalized_distance_threshold=config.normalized_distance_threshold,
                                       expanded_person_ratio=config.expanded_person_ratio)
        rows.append(score_row(frame, pairs, provider(frame, pairs)))
    write_jsonl(output, rows)
    return {"frames": len(frames), "relations_sha256": _sha256_file(output), "threshold": provider.threshold}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "train", "evaluate"):
        p = subs.add_parser(name)
        p.add_argument("--pairs", type=Path, required=True)
        p.add_argument("--image-root", type=Path, required=True)
        if name == "train": p.add_argument("--config", type=Path, required=True)
        if name != "validate": p.add_argument("--output-dir", type=Path, required=True)
        if name == "evaluate":
            p.add_argument("--checkpoint", type=Path, required=True)
            p.add_argument("--partition", choices=("tuning", "final_test"), required=True)
            p.add_argument("--boxes-source", choices=("ground_truth", "predicted"), required=True)
            p.add_argument("--device", default="cpu")
    p = subs.add_parser("score")
    for key in ("checkpoint", "detections", "input", "pipeline-config", "output"):
        p.add_argument("--"+key, type=Path, required=True)
    p.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    if args.command == "train": result = train(args.config, args.pairs, args.image_root, args.output_dir)
    elif args.command == "score": result = export_scores(args.checkpoint, args.detections, args.input, args.pipeline_config, args.output, args.device)
    else:
        rows = load_pairs(args.pairs, args.image_root)
        if args.command == "validate":
            result = {"pairs": len(rows), "uncertain": sum(r["holding_label"] == "uncertain" for r in rows)}
        else:
            if args.output_dir.exists(): raise ValueError("New pair-evaluation output required")
            provider = TorchRelationProvider(args.checkpoint, device=args.device)
            selected = [r for r in rows if r["partition"] == args.partition and r["holding_label"] != "uncertain" and r["boxes_source"] == args.boxes_source]
            if not selected: raise ValueError("No labeled pairs in requested partition")
            if any(r["annotation_origin"] != provider.payload["data_kind"] for r in selected):
                raise ValueError("Synthetic/human checkpoint and evaluation origin differ")
            scores = predict_rows(provider.model, selected, kind=provider.config["kind"], size=provider.config["crop_size"], device=args.device)
            truth = [LABELS[r["holding_label"]] for r in selected]
            result = {"partition": args.partition, "boxes_source": args.boxes_source, "data_kind": provider.payload["data_kind"],
                      "session_count": len({r["session_id"] for r in selected}), "group_count": len({r["leakage_group_id"] for r in selected}),
                      "checkpoint_sha256": provider.checkpoint_sha256, "pairs_sha256": _sha256_file(args.pairs),
                      "threshold": provider.threshold, "metrics": pair_metrics(truth, scores, provider.threshold),
                      "predictions": [{"pair_id": r["pair_id"], "boxes_source": r["boxes_source"], "truth": y, "holding_score": p}
                                      for r, y, p in zip(selected, truth, scores)]}
            args.output_dir.mkdir(parents=True)
            _write_json(args.output_dir/"evaluation.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
