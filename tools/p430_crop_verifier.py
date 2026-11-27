"""Train and gate a low-cost ALT-01 crop verifier on the pinned P430 release."""

from argparse import ArgumentParser
from collections import Counter
from contextlib import nullcontext
from math import ceil, floor, isfinite
import os
from pathlib import Path

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


def read_gray(row):
    import cv2
    import numpy as np

    data = Path(row["image_file"]).read_bytes()
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    require(image is not None and image.shape == (1080, 1920), "Expected a 1920x1080 reviewed frame")
    return image


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


def crop_feature(image, coordinates, hog):
    import cv2

    left, top, right, bottom = coordinates
    padx, pady = .125 * (right - left), .125 * (bottom - top)
    y1, y2 = max(0, floor(top - pady)), min(1080, ceil(bottom + pady))
    x1, x2 = max(0, floor(left - padx)), min(1920, ceil(right + padx))
    require(x1 < x2 and y1 < y2, "Empty proposal after clipping to the central crop")
    chip = cv2.resize(image[y1:y2, x1:x2], (64, 64), interpolation=cv2.INTER_LINEAR)
    return hog(chip)


def train_classifier(rows, predictions):
    import numpy as np

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
    return coef, intercept, examples


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


def load_partition(base, plan, state, run, split):
    rows = development_rows(base, {**plan, "validation": {split: plan["validation"][split]}})
    predictions, evidence = load_predictions("A-MIX70", state, run, rows, partitions=(split,))
    return rows[split], predictions[split], evidence


def run(settings, snapshot_path, output, mix70_run, mix70_checkpoint, worker_evidence, *, device=0):
    require(not output.exists(), "Use a new crop verifier output directory")
    if worker_evidence is not None:
        require(not worker_evidence.exists(), "Use a new Worker evidence file")
    snapshot = read(snapshot_path)
    state = snapshot["A-MIX70"]
    require(state["status"] == "COMPLETED", "MIX70 completion receipt missing")
    record = state["data"]
    checkpoint = mix70_checkpoint or Path(record["checkpoint"])
    require(sha(checkpoint) == record["checkpoint_sha256"], "MIX70 crop verifier checkpoint SHA-256 differs")
    base = Path(settings["base"])
    plan = pin_plan(base)
    source = base.parent / "p430-t1-20261120-v1/dataset/manifest.jsonl"
    require(sha(source) == SOURCE_SHA, "Reviewed P430 manifest changed")
    train_rows = reviewed_train_rows(base, plan, jsonl(source), read(base / "protection.json"))
    require(train_rows, "No central-reviewed P430 train inputs")
    if device != "cpu" and not settings["node"].startswith("pc"):
        require(os.environ.get("CUDA_VISIBLE_DEVICES") == settings["uuid"], "Pin the approved GPU UUID")
    lock = nullcontext() if device == "cpu" else gpu_training_lock(
        base.parent / "training" / gpu_name(settings), owner="p430-alt01-crop-verifier"
    )
    with lock:
        train_predictions = tile_predictions(checkpoint, train_rows, device=device)
    require(sha(checkpoint) == record["checkpoint_sha256"], "MIX70 checkpoint changed during inference")
    coef, intercept, examples = train_classifier(train_rows, train_predictions)
    tune_rows, baseline, evidence = load_partition(base, plan, state, mix70_run, "tune")
    logits = feature_logits(tune_rows, baseline, coef, intercept)
    control = tune(tune_rows, baseline)
    trials = {alpha: tune(tune_rows, rescore(baseline, logits, alpha)) for alpha in BLENDS}
    eligible = [alpha for alpha in BLENDS if improved(control, trials[alpha])]
    selected = max(eligible, key=lambda alpha: rank_key(trials[alpha])) if eligible else None
    output.mkdir()
    model_file = output / "crop-verifier.json"
    save(model_file, {"schema_version": 1, "feature": "grayscale-hog-64x64-cell8-bin9",
                      "crop_padding_fraction": .125, "coef": coef.tolist(), "intercept": intercept,
                      "fit_steps": FIT_STEPS, "l2": FIT_L2, "learning_rate": FIT_STEP_SIZE,
                      "minimum_detector_score": SCORE_MIN, "examples": examples})
    result = {
        "schema_version": 1, "scope": "p430_development_only", "experiment": "ALT-01 HOG/logistic",
        "base_plan_sha256": PLAN_SHA, "reviewed_manifest_sha256": SOURCE_SHA,
        "crop_verifier_sha256": sha(model_file), "baseline_predictions": evidence,
        "train_images": len(train_rows), "train_device": device,
        "train_proposal_counts": dict(Counter(example["label"] for example in examples)),
        "train_proposal_limit_per_image": MAX_TRAIN_PROPOSALS, "train_positive_match_iou": .5,
        "tune": {"control": control, **{str(alpha): trial for alpha, trial in trials.items()}},
        "selected_blend": selected, "dev_check": None,
    }
    if selected is not None:
        dev_rows, fixed, dev_evidence = load_partition(base, plan, state, mix70_run, "dev_check")
        reranked = rescore(fixed, feature_logits(dev_rows, fixed, coef, intercept), selected)
        dev_truth = make_truth(dev_rows)
        dev_output = output / "selected-dev-check.jsonl"
        write_jsonl(dev_output, reranked)
        result.update(dev_check={
            "control": {**locked(dev_rows, fixed, control["point"]["confidence"]), **coco_metrics(dev_truth, fixed)},
            "reranked": {**locked(dev_rows, reranked, trials[selected]["point"]["confidence"]),
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
    args = parser.parse_args()
    run(read(args.node_settings), args.shared_snapshot, args.output, args.mix70_run,
        args.mix70_checkpoint, args.worker_evidence, device=0 if args.device == "0" else "cpu")
