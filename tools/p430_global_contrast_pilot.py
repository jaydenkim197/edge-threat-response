"""Test one low-contrast adjustment on approved P430 development frames."""

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import sys

from edge_threat_response.detector_comparison import canonical_prediction, coco_metrics
from edge_threat_response.p430_evaluation import make_truth, score_predictions
from edge_threat_response.p430_workflow import read, require, save, sha
from edge_threat_response.replay import write_jsonl
from p430_followup_actions import D1_SHA, PLAN_SHA, locked, pin_plan
from run_p430_site import development_rows


LOW_CONTRAST_SESSION = "c99952c70775158343ee97709443258c0bf7786dfe621d15ad0b09ae9d931e92"
APPLY_BELOW_STD = 40
TARGET_STD = 55
MAX_GAIN = 1.6


def adjust(image):
    import cv2
    import numpy as np

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sampled = cv2.resize(gray, (960, 540), interpolation=cv2.INTER_AREA)
    mean, std = (float(value.item()) for value in cv2.meanStdDev(sampled))
    if std >= APPLY_BELOW_STD:
        return image, False
    gain = min(MAX_GAIN, TARGET_STD / max(std, 1.0))
    curve = np.rint(mean + gain * (np.arange(256) - mean)).clip(0, 255).astype(np.uint8)
    return cv2.LUT(image, curve), True


def paired_predictions(backend, rows):
    import cv2
    import numpy as np

    controls, transformed = [], []
    counts = Counter()
    for row, truth in zip(rows, make_truth(rows)["images"], strict=True):
        image = cv2.imdecode(np.frombuffer(Path(row["image_file"]).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        require(image is not None and image.shape == (1080, 1920, 3), "Unexpected central frame")
        adjusted, changed = adjust(image)
        baseline = backend.predict(image)
        variant = backend.predict(adjusted) if changed else baseline
        counts[row["source_video_sha256"]] += int(changed)
        for results, destination in ((baseline, controls), (variant, transformed)):
            prediction, _ = canonical_prediction(
                truth, [item.bbox_xyxy for item in results], [item.confidence for item in results],
                [item.class_id for item in results], 0,
            )
            destination.append(prediction)
    return {"original": controls, "adjusted": transformed}, dict(counts)


def adjusted_session(rows, predictions, threshold):
    pairs = [(row, item) for row, item in zip(rows, predictions, strict=True)
             if row["source_video_sha256"] == LOW_CONTRAST_SESSION]
    require(pairs, "11/19 recording missing from development partition")
    truth, pred = zip(*pairs, strict=True)
    return {**locked(truth, pred, threshold), "positives": sum(len(row["boxes"]) for row in truth)}


def main():
    import torch
    from edge_threat_response.p430_tile_detector import P430TiledBackend

    parser = ArgumentParser(description=__doc__)
    for name in ("settings", "weights", "result"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    base = Path(read(args.settings)["base"])
    sys.path.insert(0, str(base.parent / "p430-t1-20261120-v1/evaluation-deps"))
    plan = pin_plan(base)
    require(sha(args.weights) == D1_SHA and torch.cuda.device_count() == 1, "Expected D1 and one reserved GPU")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    detector = P430TiledBackend(str(args.weights), predict_arguments={"device": 0, "conf": .001})

    def partition(name):
        return development_rows(base, {**plan, "validation": {name: plan["validation"][name]}})[name]

    rows = partition("tune")
    predictions, counts = paired_predictions(detector, rows)
    report = {
        "scope": "development_only", "base_plan_sha256": PLAN_SHA, "weight_sha256": D1_SHA,
        "runner_sha256": sha(Path(__file__)), "recipe": {"apply_below_std": APPLY_BELOW_STD,
        "target_std": TARGET_STD, "max_gain": MAX_GAIN}, "tune": {}, "tune_adjusted_frames": counts,
        "dev_check": None,
    }
    for arm, values in predictions.items():
        metrics = score_predictions(args.weights, rows, values, args.result.parent / f"tune-{arm}.jsonl")
        metrics["low_contrast_session"] = adjusted_session(rows, values, metrics["point"]["confidence"])
        report["tune"][arm] = metrics
    old, new = (report["tune"][arm] for arm in ("original", "adjusted"))
    report["tune_gate"] = (new["low_contrast_session"]["tp"] >= old["low_contrast_session"]["tp"] + 2
                           and new["point"]["small_tp"] >= old["point"]["small_tp"] - 1
                           and new["point"]["tp"] >= old["point"]["tp"]
                           and new["point"]["negative_frames_flagged"] <= 1)
    save(args.result.parent / "tune-lock.json", report)
    if report["tune_gate"]:
        rows = partition("dev_check")
        predictions, report["dev_check_adjusted_frames"] = paired_predictions(detector, rows)
        report["dev_check"] = {}
        for arm, values in predictions.items():
            threshold = report["tune"][arm]["point"]["confidence"]
            path = args.result.parent / f"dev-{arm}.jsonl"
            write_jsonl(path, values)
            report["dev_check"][arm] = {**locked(rows, values, threshold), "confidence": threshold,
                                       **coco_metrics(make_truth(rows), values), "predictions_sha256": sha(path),
                                       "low_contrast_session": adjusted_session(rows, values, threshold)}
    save(args.result, report)
    print("contrast tune gate:", report["tune_gate"], flush=True)


if __name__ == "__main__":
    main()
