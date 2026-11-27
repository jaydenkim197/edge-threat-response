"""Train and gate a low-cost ALT-01 crop verifier on the pinned P430 release."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from contextlib import nullcontext
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from itertools import islice
from math import ceil, floor, isfinite
import os
from pathlib import Path
import re

from edge_threat_response.dataset.review_web import CENTER_REVIEW_SCOPE
from edge_threat_response.detection_evaluation import BBox, iou
from edge_threat_response.detector_comparison import coco_metrics
from edge_threat_response.p430_evaluation import make_truth, rank_key, truth_record
from edge_threat_response.p430_workflow import SOURCE_SHA, read, require, save, sha
from edge_threat_response.replay import write_jsonl
from edge_threat_response.training import gpu_training_lock
from p430_dev_fusion import load_predictions, tune
from p430_followup_actions import PLAN_SHA, gpu_name, locked, pin_plan
from run_p430_integration import jsonl, paths
from run_p430_site import development_rows, original_boxes, tile_predictions


BLENDS = (.25, .50)
SCORE_MIN = .01
MAX_TRAIN_PROPOSALS = 3
FIT_STEPS = 250
FIT_L2 = .02
FIT_STEP_SIZE = .10
HOG_FEATURE = "grayscale-hog-64x64-cell8-bin9"
HOG_EXPERIMENT = "ALT-01 HOG/logistic"
MOBILE_FEATURE = "rgb-mobilenet-v3-small-imagenet1k-v1-96x96-l2"
MOBILE_EXPERIMENT = "ALT-01 C01 frozen ImageNet MobileNetV3-Small/logistic probe"
ARCHIVED_COUNTS = {"1": 326, "0": 460}
MOBILE_SIZE = 96
MOBILE_BATCH = 32


@dataclass(frozen=True)
class MobileInputs:
    hog_result: Path
    hog_result_sha256: str
    hog_verifier: Path
    weights: Path
    weights_sha256: str


def verified_sha(path, expected):
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-fA-F]{64}", expected),
            "A full SHA-256 is required for crop verifier inputs")
    actual = sha(path)
    require(actual == expected.lower(), f"Crop verifier SHA-256 differs: {path.name}")
    return actual


def reviewed_train_rows(base, plan, manifest, protection):
    held = {key for split in plan["validation"].values() for key in split}
    held_original = {r["source_sha256"] for r in manifest if r["image_sha256"] in held}
    protected = {protection["edited_sha256"], *protection.get("original_sha256", [])}
    rows = []
    seen = set()
    for record in manifest:
        key = record["image_sha256"]
        parent = plan["pool"].get(key)
        if (record.get("review_scope") != CENTER_REVIEW_SCOPE or not parent or parent["domain"] != "p430"):
            continue
        require(key not in held and key not in seen and record["source_sha256"] not in held_original
                and not protected.intersection({key, record["source_sha256"], record["source_video_sha256"]}),
                "Protected or duplicate crop verifier input")
        require(record["crop_xyxy"] == [960, 540, 2880, 1620] and record["review_version"] >= 1
                and isfinite(record["timestamp_s"]) and record["timestamp_s"] >= 0
                and record["source_video_sha256"] == parent["source_group"]
                and record["label_sha256"] == parent["label_sha256"]
                and record["knife_boxes"] == parent["n"], "Crop verifier review identity changed")
        image, label = paths(base, parent)
        require(sha(image) == key and sha(label) == record["label_sha256"], "Crop verifier train pair changed")
        boxes = original_boxes(label)
        require(len(boxes) == parent["n"], "Crop verifier train knife count changed")
        seen.add(key)
        rows.append({**record, "image_file": str(image), "boxes": boxes})
    return rows


def training_proposals(row, detection):
    require(detection["source_id"] == row["image_sha256"], "Train candidate frame identity differs")
    truth = [BBox(*box) for box in truth_record(row)["knife_boxes_xyxy"]]
    used = set()
    candidates = []
    for item in sorted(detection["detections"], key=lambda obj: -obj["confidence"]):
        if item["label"] != "knife" or item["confidence"] < SCORE_MIN:
            continue
        if truth:
            candidate = BBox(*item["bbox_xyxy"])
            overlap, index = max((iou(candidate, gt), i) for i, gt in enumerate(truth))
            if overlap < .50 or index in used:
                continue
            used.add(index)
        candidates.append({"bbox_xyxy": item["bbox_xyxy"], "confidence": item["confidence"], "label": int(bool(truth))})
        if len(candidates) == MAX_TRAIN_PROPOSALS:
            break
    return candidates


def archived_proposals(inputs, rows, checkpoint_sha):
    result_sha = verified_sha(inputs.hog_result, inputs.hog_result_sha256)
    result = read(inputs.hog_result)
    require(result["schema_version"] == 1 and result["scope"] == "p430_development_only"
            and result["experiment"] == HOG_EXPERIMENT and result["base_plan_sha256"] == PLAN_SHA
            and result["reviewed_manifest_sha256"] == SOURCE_SHA
            and result["baseline_predictions"]["checkpoint_sha256"] == checkpoint_sha
            and result["train_proposal_counts"] == ARCHIVED_COUNTS
            and result["train_proposal_limit_per_image"] == MAX_TRAIN_PROPOSALS
            and result["train_positive_match_iou"] == .50, "Unrecognized HOG pilot receipt")
    model_sha = verified_sha(inputs.hog_verifier, result["crop_verifier_sha256"])
    model = read(inputs.hog_verifier)
    require(model["schema_version"] == 1 and model["feature"] == HOG_FEATURE
            and model["crop_padding_fraction"] == .125 and model["minimum_detector_score"] == SCORE_MIN,
            "Unexpected HOG proposal archive contract")
    examples = model["examples"]
    by_image = {row["image_sha256"]: row for row in rows}
    grouped = defaultdict(list)
    for item in examples:
        row = by_image.get(item["image_sha256"])
        require(row is not None and row["session"] == item["session"], "Proposal is outside its reviewed train session")
        box, score, label = item["bbox_xyxy"], item["confidence"], item["label"]
        require(type(label) is int and label == int(bool(row["boxes"]))
                and type(score) in (float, int) and SCORE_MIN <= score <= 1
                and len(box) == 4 and all(type(value) in (float, int) and isfinite(value) for value in box)
                and 0 <= box[0] < box[2] <= 1920 and 0 <= box[1] < box[3] <= 1080,
                "Invalid archived train label, confidence or geometry")
        grouped[item["image_sha256"]].append({"bbox_xyxy": box, "confidence": score, "label": label})
    require(Counter(str(item["label"]) for item in examples) == ARCHIVED_COUNTS,
            "Archived train proposal counts differ")
    for key, candidates in grouped.items():
        detections = [{**item, "label": "knife"} for item in candidates]
        admitted = training_proposals(by_image[key], {"source_id": key, "detections": detections})
        require(len(admitted) == len(candidates) == len({tuple(item["bbox_xyxy"]) for item in candidates}),
                "Archived proposals exceeded the cap, duplicated a box or mismatched a reviewed positive")
    return examples, result["baseline_predictions"], {"hog_result_sha256": result_sha, "hog_verifier_sha256": model_sha}


def read_gray(row):
    import cv2
    import numpy as np

    data = Path(row["image_file"]).read_bytes()
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    require(image is not None and image.shape == (1080, 1920), "Expected a 1920x1080 reviewed frame")
    return image


def read_rgb(row):
    import cv2
    import numpy as np

    data = Path(row["image_file"]).read_bytes()
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    require(image is not None and image.shape == (1080, 1920, 3), "Expected a 1920x1080 reviewed frame")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def hog_descriptor():
    import cv2
    import numpy as np

    coordinates = np.arange(64) // 8
    offsets = (9 * (8 * coordinates[:, None] + coordinates)).ravel()

    def hog(chip):
        gradients_x = cv2.Sobel(chip, cv2.CV_32F, 1, 0, ksize=1)
        gradients_y = cv2.Sobel(chip, cv2.CV_32F, 0, 1, ksize=1)
        orientations = (np.arctan2(gradients_y, gradients_x) % np.pi).ravel() * (9 / np.pi)
        bins = orientations.astype(np.int32)
        magnitude = np.hypot(gradients_x, gradients_y).ravel()
        fraction = orientations - bins
        left = np.bincount(offsets + bins % 9, weights=magnitude * (1 - fraction), minlength=576)
        right = np.bincount(offsets + (bins + 1) % 9, weights=magnitude * fraction, minlength=576)
        histogram = (left + right).astype(np.float32).reshape(64, 9)
        histogram /= np.linalg.norm(histogram, axis=1, keepdims=True).clip(1e-6)
        return histogram.ravel() / 8

    return hog


def resize_crop(image, coordinates, size):
    import cv2

    left, top, right, bottom = coordinates
    padx, pady = .125 * (right - left), .125 * (bottom - top)
    y1, y2 = max(0, floor(top - pady)), min(1080, ceil(bottom + pady))
    x1, x2 = max(0, floor(left - padx)), min(1920, ceil(right + padx))
    require(x1 < x2 and y1 < y2, "Empty proposal after clipping to the central crop")
    return cv2.resize(image[y1:y2, x1:x2], (size, size), interpolation=cv2.INTER_LINEAR)


def crop_feature(image, coordinates, hog):
    return hog(resize_crop(image, coordinates, 64))


def train_classifier(rows, predictions):
    hog = hog_descriptor()
    examples, features = [], []
    for row, detection in zip(rows, predictions, strict=True):
        candidates = training_proposals(row, detection)
        if not candidates:
            continue
        image = read_gray(row)
        for item in candidates:
            features.append(crop_feature(image, item["bbox_xyxy"], hog))
            examples.append({**item, "image_sha256": row["image_sha256"], "session": row["session"]})
    return (*fit_logistic(features, examples), examples)


def fit_logistic(features, examples):
    import numpy as np

    classes = Counter(example["label"] for example in examples)
    require(min(classes[0], classes[1]) >= 20, "Insufficient trusted train positives or negatives")
    design = np.asarray(features, dtype=np.float32)
    labels = np.asarray([example["label"] for example in examples], dtype=np.float32)
    sample_weights = np.asarray([.5 / classes[example["label"]] for example in examples], dtype=np.float32)
    coef = np.zeros(design.shape[1], dtype=np.float32)
    intercept = 0.
    for _ in range(FIT_STEPS):
        probabilities = 1 / (1 + np.exp(-np.clip(design @ coef + intercept, -30, 30)))
        error = (probabilities - labels) * sample_weights
        coef -= FIT_STEP_SIZE * (design.T @ error + FIT_L2 * coef)
        intercept -= FIT_STEP_SIZE * float(error.sum())
    require(np.isfinite(coef).all() and isfinite(intercept), "Nonfinite fit")
    return coef, intercept


def feature_logits(rows, predictions, coef, intercept):
    import numpy as np

    hog = hog_descriptor()
    scored = []
    for row, prediction in zip(rows, predictions, strict=True):
        indices = [i for i, item in enumerate(prediction["detections"]) if item["confidence"] >= SCORE_MIN]
        if not indices:
            scored.append({})
            continue
        image = read_gray(row)
        features = np.stack([crop_feature(image, prediction["detections"][i]["bbox_xyxy"], hog) for i in indices])
        logits = (features @ coef + intercept).clip(-3., 3.)
        scored.append(dict(zip(indices, logits.tolist(), strict=True)))
    return scored


def mobile_backbone(inputs):
    import torch
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    weights_hash = verified_sha(inputs.weights, inputs.weights_sha256)
    official = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    official_prefix = Path(official.url).stem.rsplit("-", 1)[1]
    require(weights_hash.startswith(official_prefix), "Expected the torchvision ImageNet-1K V1 weights")
    weight_bytes = inputs.weights.read_bytes()
    require(sha256(weight_bytes).hexdigest() == weights_hash, "MobileNet weights changed during load")
    model = mobilenet_v3_small(weights=None)
    model.load_state_dict(torch.load(BytesIO(weight_bytes), map_location="cpu", weights_only=True), strict=True)
    return model.eval().requires_grad_(False), weights_hash


def mobile_features(model, rows, proposals):
    import numpy as np
    import torch

    def chips():
        for row in rows:
            candidates = proposals.get(row["image_sha256"])
            if not candidates:
                continue
            image = read_rgb(row)
            for key, box in candidates:
                yield key, resize_crop(image, box, MOBILE_SIZE)

    source = chips()
    mean = torch.tensor([.485, .456, .406]).view(1, 3, 1, 1)
    std = torch.tensor([.229, .224, .225]).view(1, 3, 1, 1)
    embeddings = {}
    with torch.inference_mode():
        while batch := list(islice(source, MOBILE_BATCH)):
            keys, pixels = zip(*batch)
            images = torch.from_numpy(np.stack(pixels)).permute(0, 3, 1, 2).float() / 255
            vector = model.avgpool(model.features((images - mean) / std)).flatten(1)
            embeddings.update(zip(keys, torch.nn.functional.normalize(vector, dim=1).numpy(), strict=True))
    return embeddings


def mobile_logits(model, rows, predictions, coef, intercept):
    proposals = {
        row["image_sha256"]: [((position, index), item["bbox_xyxy"])
                             for index, item in enumerate(prediction["detections"]) if item["confidence"] >= SCORE_MIN]
        for position, (row, prediction) in enumerate(zip(rows, predictions, strict=True))
    }
    scored = [{} for _ in rows]
    for (position, index), vector in mobile_features(model, rows, proposals).items():
        scored[position][index] = float((vector @ coef + intercept).clip(-3., 3.))
    return scored


def rescore(predictions, logits, blend):
    from math import exp, log

    updated = []
    for prediction, scored in zip(predictions, logits, strict=True):
        detections = []
        for index, item in enumerate(prediction["detections"]):
            if index not in scored:
                detections.append(item)
                continue
            score = min(1 - 1e-6, item["confidence"])
            logit = log(score / (1 - score))
            adjusted = 1 / (1 + exp(-((1 - blend) * logit + blend * scored[index])))
            detections.append({**item, "confidence": max(.001, adjusted)})
        updated.append({**prediction, "detections": detections})
    return updated


def improved(reference, candidate):
    base, new = reference["point"], candidate["point"]
    return (new["small_tp"] >= base["small_tp"] and new["tp"] >= base["tp"]
            and new["negative_frames_flagged"] <= base["negative_frames_flagged"]
            and rank_key(candidate)[:4] > rank_key(reference)[:4])


def mobile_improved(reference, candidate):
    base, new = reference["point"], candidate["point"]
    return (new["small_tp"] >= base["small_tp"] and new["tp"] >= base["tp"]
            and new["negative_frames_flagged"] <= base["negative_frames_flagged"] and new["fp_boxes"] <= base["fp_boxes"]
            and (new["small_tp"] > base["small_tp"] or new["tp"] > base["tp"]
                 or new["negative_frames_flagged"] < base["negative_frames_flagged"]
                 or new["fp_boxes"] <= base["fp_boxes"] - 2))


def load_partition(base, plan, state, run, split):
    rows = development_rows(base, {**plan, "validation": {split: plan["validation"][split]}})
    predictions, evidence = load_predictions("A-MIX70", state, run, rows, partitions=(split,))
    return rows[split], predictions[split], evidence


def run(settings, snapshot_path, output, mix70_run, mix70_checkpoint, worker_evidence, *, device=0, mobile=None):
    require(not output.exists(), "Use a new crop verifier output directory")
    if worker_evidence is not None:
        require(not worker_evidence.exists(), "Use a new Worker evidence file")
    snapshot = read(snapshot_path)
    state = snapshot["A-MIX70"]
    require(state["status"] == "COMPLETED", "MIX70 completion receipt missing")
    record = state["data"]
    checkpoint = mix70_checkpoint or Path(record["checkpoint"])
    checkpoint_sha = sha(checkpoint)
    require(checkpoint_sha == record["checkpoint_sha256"], "MIX70 crop verifier checkpoint SHA-256 differs")
    base = Path(settings["base"])
    plan = pin_plan(base)
    source = base.parent / "p430-t1-20261120-v1/dataset/manifest.jsonl"
    require(sha(source) == SOURCE_SHA, "Reviewed P430 manifest changed")
    train_rows = reviewed_train_rows(base, plan, jsonl(source), read(base / "protection.json"))
    require(train_rows, "No central-reviewed P430 train inputs")
    feature, experiment, provenance = HOG_FEATURE, HOG_EXPERIMENT, {}
    score_features, gate = feature_logits, improved
    if mobile is None:
        if device != "cpu" and not settings["node"].startswith("pc"):
            require(os.environ.get("CUDA_VISIBLE_DEVICES") == settings["uuid"], "Pin the approved GPU UUID")
        lock = nullcontext() if device == "cpu" else gpu_training_lock(
            base.parent / "training" / gpu_name(settings), owner="p430-alt01-crop-verifier"
        )
        with lock:
            train_predictions = tile_predictions(checkpoint, train_rows, device=device)
        require(sha(checkpoint) == checkpoint_sha, "MIX70 checkpoint changed during inference")
        coef, intercept, examples = train_classifier(train_rows, train_predictions)
    else:
        from functools import partial

        require(device == "cpu", "Run the frozen MobileNet probe on CPU")
        examples, archived_evidence, provenance = archived_proposals(mobile, train_rows, checkpoint_sha)
        model, weights_sha = mobile_backbone(mobile)
        provenance["mobilenet_weights_sha256"] = weights_sha
        proposals = defaultdict(list)
        for index, item in enumerate(examples):
            proposals[item["image_sha256"]].append((index, item["bbox_xyxy"]))
        vectors = mobile_features(model, train_rows, proposals)
        coef, intercept = fit_logistic([vectors[i] for i in range(len(examples))], examples)
        feature, experiment = MOBILE_FEATURE, MOBILE_EXPERIMENT
        score_features, gate = partial(mobile_logits, model), mobile_improved
    tune_rows, baseline, evidence = load_partition(base, plan, state, mix70_run, "tune")
    if mobile is not None:
        require(evidence == archived_evidence, "C01 must use the HOG pilot's exact MIX70 tuning predictions")
    logits = score_features(tune_rows, baseline, coef, intercept)
    control = tune(tune_rows, baseline)
    trials = {alpha: tune(tune_rows, rescore(baseline, logits, alpha)) for alpha in BLENDS}
    eligible = [alpha for alpha in BLENDS if gate(control, trials[alpha])]
    selected = max(eligible, key=lambda alpha: rank_key(trials[alpha])) if eligible else None
    output.mkdir()
    model_file = output / "crop-verifier.json"
    save(model_file, {"schema_version": 1, "feature": feature, **provenance,
                      "crop_padding_fraction": .125, "coef": coef.tolist(), "intercept": intercept,
                      "fit_steps": FIT_STEPS, "l2": FIT_L2, "learning_rate": FIT_STEP_SIZE,
                      "minimum_detector_score": SCORE_MIN, "examples": examples})
    result = {
        "schema_version": 1, "scope": "p430_development_only", "experiment": experiment, **provenance,
        "base_plan_sha256": PLAN_SHA, "reviewed_manifest_sha256": SOURCE_SHA,
        "crop_verifier_sha256": sha(model_file), "baseline_predictions": evidence,
        "train_images": len(train_rows), "train_device": device,
        "train_proposal_counts": dict(Counter(example["label"] for example in examples)),
        "train_proposal_limit_per_image": MAX_TRAIN_PROPOSALS, "train_positive_match_iou": .5,
        "tune": {"control": control, **{str(alpha): trial for alpha, trial in trials.items()}},
        "selected_blend": selected, "dev_check": None,
    }
    if selected is not None:
        control_threshold = control["point"]["confidence"]
        selected_threshold = trials[selected]["point"]["confidence"]
        if mobile is not None:
            lock_file = output / "tune-lock.json"
            save(lock_file, {"schema_version": 1, "experiment": experiment, **provenance,
                             "base_plan_sha256": PLAN_SHA, "reviewed_manifest_sha256": SOURCE_SHA,
                             "crop_verifier_sha256": result["crop_verifier_sha256"], "baseline_predictions": evidence,
                             "selected_blend": selected, "confidence": selected_threshold,
                             "control_confidence": control_threshold})
            result["tune_lock_sha256"] = sha(lock_file)
        dev_rows, fixed, dev_evidence = load_partition(base, plan, state, mix70_run, "dev_check")
        reranked = rescore(fixed, score_features(dev_rows, fixed, coef, intercept), selected)
        dev_truth = make_truth(dev_rows)
        dev_output = output / "selected-dev-check.jsonl"
        write_jsonl(dev_output, reranked)
        result.update(dev_check={
            "control": {**locked(dev_rows, fixed, control_threshold), **coco_metrics(dev_truth, fixed)},
            "reranked": {**locked(dev_rows, reranked, selected_threshold),
                         **coco_metrics(dev_truth, reranked)},
            "raw_predictions": dev_evidence, "reranked_predictions_sha256": sha(dev_output),
        })
    save(output / "result.json", result)
    if worker_evidence is not None:
        save(worker_evidence, result)


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("node_settings", type=Path)
    parser.add_argument("shared_snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mix70-run", type=Path)
    parser.add_argument("--mix70-checkpoint", type=Path)
    parser.add_argument("--worker-evidence", type=Path)
    parser.add_argument("--device", choices=("0", "cpu"), default="0")
    parser.add_argument("--feature", choices=("hog", "mobilenet"), default="hog")
    parser.add_argument("--hog-result", type=Path)
    parser.add_argument("--hog-result-sha256")
    parser.add_argument("--hog-verifier", type=Path)
    parser.add_argument("--mobilenet-weights", type=Path)
    parser.add_argument("--mobilenet-sha256")
    args = parser.parse_args()
    mobile_args = (args.hog_result, args.hog_result_sha256, args.hog_verifier, args.mobilenet_weights, args.mobilenet_sha256)
    if args.feature == "mobilenet":
        if not all(mobile_args) or args.device != "cpu":
            parser.error("--feature mobilenet requires the HOG receipt/verifier, trusted hashes, weights, and --device cpu")
    elif any(mobile_args):
        parser.error("MobileNet inputs require --feature mobilenet")
    run(read(args.node_settings), args.shared_snapshot, args.output, args.mix70_run,
        args.mix70_checkpoint, args.worker_evidence, device=0 if args.device == "0" else "cpu",
        mobile=MobileInputs(*mobile_args) if args.feature == "mobilenet" else None)
