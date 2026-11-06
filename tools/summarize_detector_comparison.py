"""Export complete paired comparison results without pooling unlike domains."""
import argparse
import csv
import json
from pathlib import Path

from edge_threat_response.detector_comparison import POLICY, paired_group_recall_interval
from edge_threat_response.detection_evaluation import evaluate_boxes
from edge_threat_response.training import _sha256_file, _write_json


def jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def summarize(args):
    if args.output.exists():
        raise ValueError("Use a fresh aggregate directory")
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    models = json.loads(args.models.read_text(encoding="utf-8"))
    suite_hash, model_hash = _sha256_file(args.suite), _sha256_file(args.models)
    if models["suite_sha256"] != suite_hash:
        raise ValueError("Model protocol does not identify this suite")
    completed = {}
    for root in args.runs:
        for path in root.glob("*/summary.json"):
            result = json.loads(path.read_text(encoding="utf-8"))
            name = result["case"]["id"]
            if name in completed:
                raise ValueError("Ambiguous multiple completed runs for "+name)
            if (result["status"] != "completed_development_comparison" or result["suite_sha256"] != suite_hash
                    or result["models_sha256"] != model_hash or result["training_started"]):
                raise ValueError("Incomplete or different protocol")
            completed[name] = (path, result)
    wanted = {c["id"] for c in models["cases"]}
    if set(completed) != wanted:
        raise ValueError("Missing/extra completed models: "+str(set(completed)^wanted))
    reference_name = "custom-n-640"
    summary, rows, selections = {}, [], []
    for name, dataset in suite["datasets"].items():
        truth_path = Path(dataset["truth"])
        if _sha256_file(truth_path) != dataset["truth_sha256"]:
            raise ValueError("Changed truth")
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        reference = jsonl(completed[reference_name][0].parent/name/"predictions.jsonl")
        summary[name] = {**{k: v for k, v in dataset.items() if k != "truth"},
                         "group_basis": truth["source_group_basis"],
                         "same_family_as_protected_images": truth.get("same_family_as_protected_images", 0),
                         "models": {}}
        for image in truth["images"]:
            selections.append({"dataset": name, "source_id": image["source_id"],
                               "image_sha256": image["image_sha256"], "width": image["width"], "height": image["height"],
                               "source_group": image["source_group"], "knife_objects": len(image["knife_boxes_xyxy"]),
                               "same_family_as_protected": image.get("same_filename_family_as_protected", False)})
        for case in models["cases"]:
            model = case["id"]
            path, result = completed[model]
            partition = result["results"][name]
            pred_path = path.parent/name/"predictions.jsonl"
            if (_sha256_file(pred_path) != partition["predictions_sha256"]
                    or partition["truth_sha256"] != dataset["truth_sha256"]
                    or result["case"] != case):
                raise ValueError("Cached prediction/model identity changed")
            predictions = jsonl(pred_path)
            verified, _ = evaluate_boxes(truth, predictions, POLICY)
            if verified != partition["fixed"]:
                raise ValueError("Cached fixed metrics differ on recomputation")
            interval = paired_group_recall_interval(truth, predictions, reference)
            c = verified["counts"]
            summary[name]["models"][model] = {"coco": partition["coco"], "fixed": verified,
                                                "paired_recall_vs_custom": interval,
                                                "predictions_sha256": partition["predictions_sha256"],
                                                "case_summary_sha256": _sha256_file(path)}
            rows.append({"dataset": name, "model": model, "images": verified["images"],
                         "knife_gt": c["tp"]+c["fn"], "groups": dataset["groups"],
                         "ap50": partition["coco"]["ap50"], "ap50_95": partition["coco"]["ap50_95"],
                         "precision025": verified["precision"], "recall025": verified["recall"], "f1_025": verified["f1"],
                         "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
                         "small_gt": c["small_gt"], "small_tp": c["small_tp"], "small_recall025": verified["small_box_recall"],
                         "negative_images": c["negative_images"], "negative_images_with_fp": c["negative_images_with_fp"],
                         "fp_boxes_per_negative_image": verified["fp_boxes_per_negative_image"],
                         "delta_recall_vs_custom": interval["delta_recall"],
                         "delta_recall_ci95_low": interval["ci95"][0] if interval["ci95"] else None,
                         "delta_recall_ci95_high": interval["ci95"][1] if interval["ci95"] else None,
                         "weights_sha256": case["checkpoint_sha256"], "truth_sha256": dataset["truth_sha256"],
                         "predictions_sha256": partition["predictions_sha256"]})
    for path, digest in suite["inputs"].items():
        if _sha256_file(Path(path)) != digest:
            raise ValueError("Original input changed")
    args.output.mkdir(parents=True)
    _write_json(args.output/"aggregate.json", {"status": "completed_development_comparison",
                                               "suite_sha256": suite_hash, "model_protocol_sha256": model_hash,
                                               "protocol": models.get("policy"),
                                               "protocol_metadata_missing": "policy" not in models,
                                               "policy": POLICY, "reference": reference_name,
                                               "datasets": summary,
                                               "environments": {n: r["environment"] for n, (_, r) in completed.items()},
                                               "extra_packages": next(iter(completed.values()))[1]["extra_packages"],
                                               "training_started": False, "all_source_hashes_preserved": True})
    for filename, records in [("comparison.csv", rows), ("selection.csv", selections)]:
        with (args.output/filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    _write_json(args.output/"artifact-index.json", {n: {"summary": str(p), "summary_sha256": _sha256_file(p),
                                                       "effective_model": r["effective_model"], "case": r["case"],
                                                       "script_sha256": r["script_sha256"], "git_commit": r["git_commit"]}
                                                    for n, (p, r) in completed.items()})
    print(json.dumps({"models": len(wanted), "datasets": len(summary), "rows": len(rows),
                      "unique_evaluation_images": len(selections), "training_started": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", required=True, type=Path)
    parser.add_argument("--models", required=True, type=Path)
    parser.add_argument("--runs", required=True, type=Path, nargs="+")
    parser.add_argument("--output", required=True, type=Path)
    summarize(parser.parse_args())
