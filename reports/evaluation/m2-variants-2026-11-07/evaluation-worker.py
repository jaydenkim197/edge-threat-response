"""Fixed PC13 comparison of completed M2 variants; no training or adoption.

Compose existing inference/metrics tools. Original images, truth, checkpoints,
reviews, runtime configurations and previous experiment results stay intact.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Class6\edge-threat-response")
SOURCE = Path(r"C:\Class6\etr-worktrees\m2-comparison-20261107")
INPUT = ROOT/"data/work/m2-comparison-20261107"
OUTPUT = ROOT/"runs/m2-variants-comparison-20261107-v1"
sys.path[:0] = [str(SOURCE/"src"), str(SOURCE/"tools")]
from edge_threat_response.detector_comparison import POLICY, paired_group_recall_interval
from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.training import _sha256_file, _write_json, _git_commit, gpu_training_lock
from finish_raw_training import preflight_environment


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(path):
    return [json.loads(s) for s in path.read_text(encoding="utf-8-sig").splitlines() if s.strip()]


def prepare():
    preflight_environment()
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("PC13 CUDA required")
    base_suite = ROOT/"data/work/multi-model-20261104/suite-v1/suite.json"
    extra_suite = ROOT/"runs/reviewed-cctv-20261106-v2/suite.json"
    model_path = ROOT/"runs/m2-followup-20261107-v2/predict/models.json"
    suite, extra, models = load(base_suite), load(extra_suite), load(model_path)
    if suite["policy"] != POLICY or extra["policy"] != POLICY or models["suite_sha256"] != _sha256_file(base_suite):
        raise ValueError("Frozen evaluation policy/suite changed")
    if set(suite["datasets"]) & set(extra["datasets"]):
        raise ValueError("Ambiguous dataset identities")
    inputs = {**suite["inputs"], **extra["inputs"]}
    for p in (base_suite, extra_suite, model_path):
        inputs[str(p)] = _sha256_file(p)
    cases = [dict(c) for c in models["cases"]]
    by_id = {c["id"]: c for c in cases}
    if set(by_id) != {"custom-n-640", "raw-m1-n-640", "coco-n-640", "raw-m2-n-640"}:
        raise ValueError("Unexpected completed M2 reference cases")
    template = by_id["raw-m2-n-640"]
    base_inv_path = ROOT/"runs/training/m2-real-20261107-v1-raw-m2-n-invocation.json"
    base_inv = load(base_inv_path)
    if base_inv["status"] != "passed" or base_inv["observed_optimizer_updates"] != 37150:
        raise ValueError("Base M2 did not complete its budget")
    inputs[str(base_inv_path)] = _sha256_file(base_inv_path)
    cases.append({**template, "id": "raw-m2-n-960", "imgsz": 960})
    training = {"pc13": {"source_commit": base_inv["git_commit"], "updates": 37150,
                         "arguments": base_inv["arguments"], "weights_sha256": template["checkpoint_sha256"]}}
    deltas = {"pc11": {"imgsz": 960},
              "pc12": {"mosaic": .5, "scale": .5, "close_mosaic": 20},
              "pc14": {"seed": 20261107}}
    for node, changes in deltas.items():
        meta_path, inv_path = INPUT/(node+"-source.json"), INPUT/(node+"-invocation.json")
        meta, inv = load(meta_path), load(inv_path)
        weight = INPUT/(node+"-best.pt")
        if (_sha256_file(inv_path) != meta["invocation_sha256"]
                or inv["status"] != "passed" or inv["observed_optimizer_updates"] != 37150
                or _sha256_file(weight) != meta["weight_sha256"]):
            raise ValueError("Imported completed model/evidence changed")
        original_artifact = next(a for a in inv["artifacts"] if Path(a["path"]).name == "best.pt")
        if original_artifact["sha256"] != meta["weight_sha256"]:
            raise ValueError("Imported checkpoint differs from recorded training artifact")
        controls = {k: v for k, v in base_inv["arguments"].items() if k not in {"name", "data", "project", "exist_ok"}}
        expected = {**controls, **changes}
        actual = {k: v for k, v in inv["arguments"].items() if k not in {"name", "data", "project", "exist_ok"}}
        if actual != expected or inv["model_source"]["sha256"] != base_inv["model_source"]["sha256"]:
            raise ValueError("Training variant differs outside the declared axis")
        inputs.update({str(meta_path): _sha256_file(meta_path), str(inv_path): _sha256_file(inv_path)})
        for resolution in ([640, 960] if node == "pc11" else [640]):
            cases.append({**template, "id": node+"-infer"+str(resolution), "checkpoint": str(weight),
                "checkpoint_sha256": meta["weight_sha256"], "imgsz": resolution,
                "training_invocation_sha256": meta["invocation_sha256"],
                "training_variant": changes, "training_source_commit": inv["git_commit"]})
        training[node] = {"source_commit": inv["git_commit"], "updates": 37150,
                          "arguments": actual, "weights_sha256": meta["weight_sha256"],
                          "dataset_manifest": inv["dataset_manifest"]}
    combined = {"schema_version": 1, "status": "development_authorized", "policy": POLICY,
                "inputs": inputs, "datasets": {**suite["datasets"], **extra["datasets"]}}
    seen = set()
    for dataset in combined["datasets"].values():
        truth_path = Path(dataset["truth"])
        if _sha256_file(truth_path) != dataset["truth_sha256"]:
            raise ValueError("Frozen truth changed")
        truth = load(truth_path)
        if truth["status"] != "development_authorized" or truth["partition"] != "tuning":
            raise ValueError("Only opened development truth is allowed")
        for image in truth["images"]:
            if _sha256_file(Path(image["image"])) != image["image_sha256"]:
                raise ValueError("Frozen image changed")
            seen.add(image["image_sha256"])
    for case in cases:
        if _sha256_file(Path(case["checkpoint"])) != case["checkpoint_sha256"]:
            raise ValueError("Checkpoint changed")
    for path, digest in inputs.items():
        if _sha256_file(Path(path)) != digest:
            raise ValueError("Frozen source input changed")
    return combined, models, cases, training, len(seen)


def curves(suite, cases, runs, output, track):
    records, intervals = [], {}
    for name, dataset in suite["datasets"].items():
        truth = load(Path(dataset["truth"]))
        predictions = {c["id"]: rows(runs/c["id"]/name/"predictions.jsonl") for c in cases}
        intervals[name] = {}
        for case in cases:
            model, pred = case["id"], predictions[case["id"]]
            summary = load(runs/model/name/"summary.json")
            if (_sha256_file(runs/model/name/"predictions.jsonl") != summary["predictions_sha256"]
                    or summary["truth_sha256"] != dataset["truth_sha256"]):
                raise ValueError("Cached predictions changed before threshold sweep")
            for threshold in [.001, .05, *[i/100 for i in range(10, 51, 5)]]:
                metrics, _ = evaluate_boxes(truth, pred, {**POLICY, "confidence": threshold})
                counts = metrics["counts"]
                records.append({"track": track, "dataset": name, "model": model,
                    "confidence": threshold, "precision": metrics["precision"], "recall": metrics["recall"],
                    "f1": metrics["f1"], "tp": counts["tp"], "fp": counts["fp"], "fn": counts["fn"],
                    "small_recall": metrics["small_box_recall"],
                    "negative_images": counts["negative_images"],
                    "negative_images_with_fp": counts["negative_images_with_fp"],
                    "fp_boxes_per_negative_image": metrics["fp_boxes_per_negative_image"]})
            intervals[name][model] = {ref: paired_group_recall_interval(truth, pred, predictions[ref])
                for ref in ("raw-m1-n-640", "raw-m2-n-640")}
    with (output/"thresholds.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, list(records[0])); writer.writeheader(); writer.writerows(records)
    _write_json(output/"paired-vs-m1-m2.json", intervals)


def projected_boxes(suite):
    truth = load(Path(suite["datasets"]["us-mock-reviewed"]["truth"]))
    output = {}
    for resolution in (640, 960):
        boxes = []
        for im in truth["images"]:
            scale = min(resolution/im["width"], resolution/im["height"])
            boxes.extend(min(b[2]-b[0], b[3]-b[1])*scale for b in im["knife_boxes_xyxy"])
        output[resolution] = {"knife_gt": len(boxes), "projected_min_side_px": sorted(boxes),
            "below4px": sum(b < 4 for b in boxes), "below8px": sum(b < 8 for b in boxes),
            "below16px": sum(b < 16 for b in boxes),
            "interpretation": "Stored GT under square letterbox; does not prove a causal failure mechanism"}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    suite, reference, cases, training, unique = prepare()
    if args.preflight_only:
        print(json.dumps({"status": "passed", "cases": [c["id"] for c in cases],
            "datasets": len(suite["datasets"]), "unique_images": unique, "training": training}))
        return
    if OUTPUT.exists():
        raise ValueError("Fresh evaluation output required")
    OUTPUT.mkdir(parents=True)
    state = {"status": "prepared", "source_commit": _git_commit(),
             "worker_sha256": _sha256_file(Path(__file__)), "training_started": False,
             "final_detector_selected": False, "orin_verified": False, "unique_images": unique,
             "datasets": len(suite["datasets"]), "cases": len(cases)}
    def record(**fields):
        state.update(fields, updated_at_utc=datetime.now(timezone.utc).isoformat())
        _write_json(OUTPUT/"state.json", state)
    _write_json(OUTPUT/"suite.json", suite)
    _write_json(OUTPUT/"training-evidence.json", training)
    _write_json(OUTPUT/"cctv-projected-size.json", projected_boxes(suite))
    env = {**os.environ, "PYTHONPATH": str(SOURCE/"src"), "PYTHONUTF8": "1", "YOLO_AUTOINSTALL": "false"}
    try:
        record()
        with gpu_training_lock(ROOT/"runs/training/gpu0-training.lock", owner="m2-variants-comparison"):
            for track in ("predict", "ap"):
                dest = OUTPUT/track; dest.mkdir()
                selected = [{**c, "ultralytics_multi_label": track == "ap"} for c in cases]
                protocol = {**reference, "cases": selected, "track": track,
                    "suite_sha256": _sha256_file(OUTPUT/"suite.json"), "training_started": False,
                    "policy": {**reference["policy"], "comparison": "opened development; fixed axes; not final test"}}
                _write_json(dest/"models.json", protocol)
                (dest/"models").mkdir()
                for case in selected:
                    record(status="evaluating", track=track, active=case["id"])
                    with (dest/(case["id"]+".log")).open("x", encoding="utf-8") as log:
                        subprocess.run([sys.executable, str(SOURCE/"tools/run_detector_comparison.py"),
                            "--suite", str(OUTPUT/"suite.json"), "--models", str(dest/"models.json"),
                            "--case", case["id"], "--output", str(dest/"models"/case["id"]),
                            "--authorize-development-comparison"], cwd=SOURCE, env=env,
                            stdout=log, stderr=subprocess.STDOUT, check=True)
                with (dest/"aggregate.log").open("x", encoding="utf-8") as log:
                    subprocess.run([sys.executable, str(SOURCE/"tools/summarize_detector_comparison.py"),
                        "--suite", str(OUTPUT/"suite.json"), "--models", str(dest/"models.json"),
                        "--runs", str(dest/"models"), "--output", str(dest/"aggregate")],
                        cwd=SOURCE, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
                record(status="thresholds", active=None, track=track)
                curves(suite, selected, dest/"models", dest, track)
        for p, digest in suite["inputs"].items():
            if _sha256_file(Path(p)) != digest:
                raise ValueError("Original input changed")
        record(status="passed", track=None, active=None)
    except BaseException as exc:
        record(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    print(json.dumps(state))


if __name__ == "__main__":
    main()
