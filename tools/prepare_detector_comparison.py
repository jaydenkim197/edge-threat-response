"""Freeze a read-only, reviewed development comparison suite on PC13.

This consumes existing source evidence and read-only review snapshots. It never
approves a source for training or manufactures an independent final test set.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from edge_threat_response.dataset.development_subset import proxy_components
from edge_threat_response.dataset.image_screening import image_signature, similarity_pairs
from edge_threat_response.dataset.review import parse_review_boxes
from edge_threat_response.dataset.review_web import review_verdict
from edge_threat_response.detector_comparison import POLICY
from edge_threat_response.replay import write_jsonl
from edge_threat_response.training import TrainingConfig, _sha256_file, _write_json, validate_training_approval


def jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]


def family(path):
    stem = Path(path).stem.lower()
    return re.sub(r"\d+(?:v\d+)?$", "", stem).rstrip("_- .") or stem


def prepare(args):
    if not args.authorize_development_comparison:
        raise ValueError("Explicit development comparison authorization required")
    if args.output.exists():
        raise ValueError("Fresh output required")
    args.root = args.root.resolve()
    prepared = args.root / "data/processed/sohas-reviewed-development-20261026-smallscale-v1"
    paths = [prepared / n for n in ["training.json", "data.yaml", "DEV-manifest.jsonl",
                                    "development-authorization.json", "train.txt", "val.txt", "test.txt"]]
    inputs = {str(p): _sha256_file(p) for p in paths}
    config = TrainingConfig.load(prepared / "training.json")
    validate_training_approval(prepared / "training.json", config, prepared / "data.yaml",
                               prepared / "DEV-manifest.jsonl", prepared / "development-authorization.json")
    records = jsonl(prepared / "DEV-manifest.jsonl")
    if config.recipe_id != "DEV-SOHAS" or any(not x.get("development_only") for x in records):
        raise ValueError("Expected the unchanged DEV-SOHAS development recipe")
    protected = []
    for row in records:
        image, label = Path(row["image"]), Path(row["label"])
        signature = image_signature(image, expected_sha256=row["image_sha256"])
        if _sha256_file(label) != row["label_sha256"]:
            raise ValueError("Frozen label changed")
        protected.append(signature)
        inputs[str(image)], inputs[str(label)] = row["image_sha256"], row["label_sha256"]
    full_path = args.root / "data/work/image-screening/sohas-full-20261004-v1/image-integrity.jsonl"
    inputs[str(full_path)] = _sha256_file(full_path)
    full_inventory = jsonl(full_path)
    protected_hashes = {x["image_sha256"] for x in protected}
    protected_families = {family(x["record_id"]) for x in full_inventory if x["image_sha256"] in protected_hashes}
    datasets, exclusions = {}, []
    args.output.mkdir(parents=True)
    for split in ["val", "test"]:
        images = []
        for row in records:
            if row["split"] != split:
                continue
            signature = next(x for x in protected if x["image_sha256"] == row["image_sha256"])
            width, height = signature["width"], signature["height"]
            boxes = parse_review_boxes(Path(row["label"])) if row["knife_count"] else []
            if len(boxes) != row["knife_count"]:
                raise ValueError("Object count mismatch")
            images.append({"source_id": row["image_id"], "frame_index": 0, "image": row["image"],
                           "image_sha256": row["image_sha256"], "source_group": row["source_group"],
                           "width": width, "height": height, "knife_absence_verified": row["negative_absence_reviewed"],
                           "knife_boxes_xyxy": [[(b.x_center-b.width/2)*width, (b.y_center-b.height/2)*height,
                                                  (b.x_center+b.width/2)*width, (b.y_center+b.height/2)*height] for b in boxes]})
        datasets["sohas-"+split] = {"images": images, "domain": "reviewed real SOHAS development",
                                    "role": "opened development split; not unseen final test",
                                    "source_group_basis": "frozen full-source filename/dHash proxies"}
    accepted_signatures = []
    for name in ["dasci-unique", "us-mock", "open-images", "simuletic"]:
        pack = args.root / "data/review/team-candidates-20261003" / name
        for n in ["image-evidence.jsonl", "review.csv", "summary.json"]:
            inputs[str(pack/n)] = _sha256_file(pack/n)
        evidence = jsonl(pack / "image-evidence.jsonl")
        # Snapshot into memory. The site DB remains read-only and may continue receiving reviews.
        snapshot = sqlite3.connect(":memory:")
        with sqlite3.connect((pack/"human-review.sqlite3").as_uri()+"?mode=ro", uri=True) as source:
            source.backup(snapshot)
        pack_hash = hashlib.sha256((pack/"review.csv").read_bytes()+(pack/"image-evidence.jsonl").read_bytes()).hexdigest()
        if snapshot.execute("SELECT value FROM metadata WHERE key='pack_hash'").fetchone() != (pack_hash,):
            raise ValueError("Review snapshot belongs to a different pack")
        reviews = {i: (v, json.loads(p)) for i, v, p in snapshot.execute("SELECT sample,version,payload FROM reviews")}
        snapshot.close()
        # No reviewer names, notes, or other identity values in the experiment's exported snapshot.
        review_snapshot = [{"sample": i, "version": v, "verdict": review_verdict(p, evidence[i]["knife_count"]),
                            "payload_sha256": hashlib.sha256(json.dumps(p, sort_keys=True, ensure_ascii=False).encode()).hexdigest()}
                           for i, (v, p) in sorted(reviews.items())]
        _write_json(args.output/(name+"-review-snapshot.json"), review_snapshot)
        images, signatures, seen = [], [], set()
        counts = Counter()
        for i, row in enumerate(evidence):
            reason = None
            if i not in reviews or review_verdict(reviews[i][1], row["knife_count"]) != "ok":
                reason = "not_human_reviewed_ok"
            if reason:
                exclusions.append({"dataset": name, "sample": i, "reason": reason})
                counts[reason] += 1
                continue
            image = (pack/row["image_file"]).resolve()
            if not image.is_relative_to(pack.resolve()):
                raise ValueError("Image outside source pack")
            sig = image_signature(image, expected_sha256=row["image_sha256"])
            if (sig["width"], sig["height"]) != (row["width"], row["height"]):
                raise ValueError("Stored-pixel size changed")
            if sig["exif_orientation"] != 1:
                reason = "nondefault_exif_orientation"
            elif sig["image_sha256"] in protected_hashes or sig["image_sha256"] in seen:
                reason = "exact_duplicate_protected_or_internal"
            else:
                for target in protected+accepted_signatures:
                    ratio = (sig["width"]/sig["height"])/(target["width"]/target["height"])
                    distance = (int(sig["dhash64"], 16)^int(target["dhash64"], 16)).bit_count()
                    if sig["image_sha256"] == target["image_sha256"] or (distance <= 4 and .9 <= ratio <= 1.1
                            and not sig["low_information"] and not target["low_information"]):
                        reason = "exact_or_dhash_candidate_against_protected_or_prior_dataset"
                        break
            if any(str(x.get("IsGroupOf", "0")) == "1" or str(x.get("IsDepiction", "0")) == "1"
                   for x in row.get("annotation_rows", [])):
                reason = "group_or_depiction_annotation_not_supported"
            if reason:
                exclusions.append({"dataset": name, "sample": i, "reason": reason})
                counts[reason] += 1
                continue
            boxes = row["knife_boxes_xyxy_raw"]
            if len(boxes) != row["knife_count"]:
                raise ValueError("Raw box count mismatch")
            inputs[str(image)] = sig["image_sha256"]
            source_id = name+":"+sig["image_sha256"]
            signatures.append({**sig, "record_id": row["image_path"], "dataset_id": name,
                               "original_split": row["original_split"]})
            seen.add(sig["image_sha256"])
            images.append({"source_id": source_id, "frame_index": 0, "image": str(image),
                           "image_sha256": sig["image_sha256"], "width": sig["width"], "height": sig["height"],
                           "knife_boxes_xyxy": boxes, "knife_absence_verified": not boxes and reviews[i][1].get("negative_knife_absence") == "yes",
                           "source_group": row.get("source_group", ""), "source_path": row["image_path"],
                           "same_filename_family_as_protected": name == "dasci-unique" and family(row["image_path"]) in protected_families,
                           "review_version": reviews[i][0]})
        if not images or not any(x["knife_boxes_xyxy"] for x in images):
            raise ValueError("No usable positive evaluation images for "+name)
        groups = proxy_components(signatures, similarity_pairs(signatures))
        for image in images:
            if not image["source_group"]:
                image["source_group"] = name+":"+groups[image["source_path"]]
        accepted_signatures.extend(signatures)
        datasets[name] = {"images": images, "human_review_snapshot": name+"-review-snapshot.json",
                          "excluded_counts": dict(counts), "domain": "synthetic CCTV" if name == "simuletic" else "public real images",
                          "role": "source-label development comparison; not certified independent final test",
                          "same_family_as_protected_images": sum(x["same_filename_family_as_protected"] for x in images),
                          "source_group_basis": "source sequence" if name == "us-mock" else "filename/dHash proxies",
                          "source_evidence_sha256": inputs[str(pack/"image-evidence.jsonl")],
                          "source_metadata": json.loads((pack/"summary.json").read_text(encoding="utf-8"))}
    suite = {"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
             "purpose": "user-authorized multi-source development comparison; no training authorization",
             "status": "development_authorized", "partition": "tuning", "policy": POLICY,
             "training_started": False, "test_previously_opened": True, "inputs": inputs, "datasets": {}}
    for name, data in datasets.items():
        truth = {"schema_version": 1, "status": "development_authorized", "partition": "tuning", **data}
        _write_json(args.output/(name+"-truth.json"), truth)
        suite["datasets"][name] = {"truth": str((args.output/(name+"-truth.json")).resolve()),
                                   "truth_sha256": _sha256_file(args.output/(name+"-truth.json")),
                                   "images": len(data["images"]), "knife_objects": sum(len(x["knife_boxes_xyxy"]) for x in data["images"]),
                                   "groups": len({x["source_group"] for x in data["images"]}),
                                   "role": data["role"], "domain": data["domain"]}
    write_jsonl(args.output/"exclusions.jsonl", exclusions)
    if inputs != {p: _sha256_file(Path(p)) for p in inputs}:
        raise ValueError("Source inputs changed during suite preparation")
    _write_json(args.output/"suite.json", suite)
    print(json.dumps(suite["datasets"], ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authorize-development-comparison", action="store_true")
    prepare(parser.parse_args())
