"""Prepare bounded SOHAS gap-review packs; never write production reviews or training data."""
import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from edge_threat_response.dataset.development_subset import proxy_components
from edge_threat_response.dataset.sohas import _inventory, _source_bytes
from edge_threat_response.replay import write_jsonl
from edge_threat_response.training import TrainingConfig, _git_commit, _sha256_file, _write_json, validate_training_approval
from sohas_review_images import render_sample


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def balanced(pool, count, *, ranked=False):
    buckets = defaultdict(list)
    rng = random.Random(20261026)
    for row in pool:
        classes = tuple(sorted({o["raw_name"] for o in row["objects"]}))
        buckets[(row["source_group"], classes)].append(row)
    for bucket in buckets.values():
        if ranked:
            bucket.sort(key=lambda r: (-r["max_knife_confidence"], r["image_path"]))
        else:
            rng.shuffle(bucket)
    selected = []
    while len(selected) < count:
        added = False
        for key in sorted(buckets):
            if buckets[key] and len(selected) < count:
                selected.append(buckets[key].pop(0))
                added = True
        if not added:
            break
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "voc", "integrity", "pairs", "review", "prepared", "checkpoint", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Preserve prior packs; use a fresh output")
    inputs = {name: getattr(args,name) for name in ("voc","integrity","pairs","review","checkpoint")}
    config = TrainingConfig.load(args.prepared / "training.json")
    validate_training_approval(args.prepared / "training.json", config, args.prepared / "data.yaml",
                               args.prepared / "DEV-manifest.jsonl", args.prepared / "development-authorization.json")
    inputs["prepared_manifest"] = args.prepared / "DEV-manifest.jsonl"
    if any(args.output.resolve().is_relative_to(p.parent.resolve()) for p in inputs.values()) or args.output.resolve().is_relative_to(args.source.resolve()):
        raise ValueError("Output must be separate from inputs")
    hashes = {k: _sha256_file(p) for k,p in inputs.items()}
    signatures = {r["record_id"]:r for r in rows(args.integrity)}
    groups = proxy_components(list(signatures.values()), rows(args.pairs))
    protected = {r["source_group"] for r in rows(inputs["prepared_manifest"]) if r["split"] in {"val","test"}}
    seen = {r["image_sha256"] for r in rows(args.review)}
    unique = set(seen)
    positives, negatives = [], []
    for row in rows(args.voc):
        sig, group = signatures[row["image_path"]], groups[row["image_path"]]
        if group in protected or sig["image_sha256"] in unique or sig["exif_orientation"] != 1 or row["errors"]:
            continue
        unique.add(sig["image_sha256"])
        areas = [(float(o["bbox_xyxy_raw"][2])-float(o["bbox_xyxy_raw"][0])) *
                 (float(o["bbox_xyxy_raw"][3])-float(o["bbox_xyxy_raw"][1])) / (row["width"]*row["height"])
                 for o in row["objects"] if o["raw_name"] == "knife"]
        row.update(source_group=group, image_sha256=sig["image_sha256"], normalized_knife_areas=areas)
        if areas and min(areas) <= .02:
            positives.append(row)
        elif not areas:
            negatives.append(row)
    positive_selection = balanced(positives,100)
    probe = balanced(negatives,512)
    inventory = _inventory(args.source.resolve())
    paths = []
    for row in probe:
        raw = _source_bytes(args.source.resolve(),row["image_path"],inventory[row["image_path"]])
        if hashlib.sha256(raw).hexdigest() != row["image_sha256"]:
            raise ValueError("Mining image bytes changed")
        paths.append(str((args.source / row["image_path"]).resolve()))
    from ultralytics import YOLO
    model = YOLO(str(args.checkpoint))
    if model.names != {0:"knife"}:
        raise ValueError("Use the selected custom knife-only development checkpoint")
    count = 0
    for index,result in enumerate(model.predict(paths,stream=True,batch=16,imgsz=640,device=0,conf=.05,max_det=20,verbose=False)):
        if index >= len(probe) or Path(result.path).resolve() != Path(paths[index]):
            raise ValueError("Mining prediction alignment changed")
        probe[index]["max_knife_confidence"] = max(result.boxes.conf.tolist(),default=0)
        count += 1
    if count != len(probe):
        raise ValueError("Mining result count changed")
    negative_selection = balanced(probe,50,ranked=True)
    selected = positive_selection + negative_selection
    if len(positive_selection)!=100 or len(negative_selection)!=50 or len({r["image_sha256"] for r in selected})!=150:
        raise ValueError("Insufficient bounded unique candidate supply")
    assert all(r["source_group"] not in protected and r["image_sha256"] not in seen for r in selected)
    args.output.mkdir(parents=True)
    for label, selection in (("small-positive",positive_selection),("negative-mined",negative_selection)):
        sample = args.output / f"{label}.csv"
        with sample.open("w",encoding="utf-8",newline="") as handle:
            writer = csv.DictWriter(handle,fieldnames=["image_path","xml_path","original_split","group_id","reviewer"])
            writer.writeheader()
            writer.writerows({"image_path":r["image_path"],"xml_path":r["xml_path"],"original_split":r["original_split"],
                             "group_id":r["source_group"],"reviewer":""} for r in selection)
        render_sample(args.source,sample,args.output / label)
    write_jsonl(args.output / "negative-probe.jsonl",probe)
    write_jsonl(args.output / "selection.jsonl",selected)
    result = {"status":"prepared_not_reviewed_not_approved","git_commit":_git_commit(),"input_sha256":hashes,
              "script_sha256":_sha256_file(Path(__file__)),
              "small_positive_pool":len(positives),"negative_candidate_pool":len(negatives),"negative_probed":len(probe),
              "small_selected":100,"negative_selected":50,"negative_selected_with_prediction_ge05":sum(r["max_knife_confidence"]>=.05 for r in negative_selection),
              "protected_groups_selected":0,"existing_review_images_selected":0,"training_approved":False,"human_verdicts_written":0,
              "limits":["negative annotations are candidates, not verified knife absence","prediction-assisted, group/class-balanced mining, not evaluation",
                        "filename/hash/dHash proxies are not verified sessions","raw annotation coordinates remain unconfirmed","no production site import performed"]}
    if hashes != {k:_sha256_file(p) for k,p in inputs.items()}:
        raise ValueError("Inputs changed during preparation")
    _write_json(args.output / "summary.json",result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
