"""Acquire a bounded Knife train subset without touching review or active runs.

Reuses the official metadata/class/CC-BY selection used by prepare_team_review,
but streams large train CSVs to PC13 disk instead of loading them into RAM.
"""
import argparse
import csv
import hashlib
import json
import re
import shutil
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from edge_threat_response.dataset.image_screening import image_signature
from edge_threat_response.dataset.raw_import import check_detector_image
from edge_threat_response.replay import write_jsonl
from edge_threat_response.training import _write_json, _git_commit


URLS = {
    "classes": "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv",
    "boxes": "https://storage.googleapis.com/openimages/v6/oidv6-train-annotations-bbox.csv",
    "images": "https://storage.googleapis.com/openimages/2018_04/train/train-images-boxable-with-rotation.csv",
}


def download(url, target: Path, limit: int):
    request = urllib.request.Request(url, headers={"User-Agent": "edge-threat-response-academic", "Accept-Encoding": "identity"})
    digest, count = hashlib.sha256(), 0
    partial = target.with_suffix(target.suffix+".partial")
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("xb") as stream:
        expected = int(response.headers.get("Content-Length", "0"))
        if expected > limit: raise ValueError("Source exceeds explicit download size limit")
        headers = {key: response.headers.get(key) for key in ("ETag", "Last-Modified", "Content-Length")}
        while block := response.read(1024*1024):
            count += len(block)
            if count > limit: raise ValueError("Source exceeds explicit download size limit")
            digest.update(block)
            stream.write(block)
        if expected and count != expected: raise ValueError("Incomplete source response")
    partial.rename(target)
    return {"url": url, "bytes": count, "sha256": digest.hexdigest(), "headers": headers}


def acquire(output: Path, *, count: int = 1000, seed: int = 20261105):
    if output.exists() or not 1 <= count <= 2000:
        raise ValueError("Fresh output and bounded image count (1..2000) required")
    output.parent.mkdir(parents=True, exist_ok=True)
    required_space = 25*1024**3 + count*20*1024**2
    if shutil.disk_usage(output.parent).free < required_space:
        raise ValueError("Insufficient free space for bounded metadata/images and disk reserve")
    output.mkdir()
    for folder in ("metadata", "images", "labels"): (output/folder).mkdir()
    state = {"status": "acquiring_metadata", "source_commit": _git_commit(), "original_split": "train",
             "included_in_current_queue": False, "human_review_complete": False,
             "global_duplicate_check_complete": False, "final_evaluation_allowed": False}
    _write_json(output/"state.json", state)
    try:
        records = {}
        for key, url in URLS.items():
            records[key] = download(url, output/"metadata"/(key+".csv"), 8*1024**2 if key == "classes" else 5*1024**3)
            print(json.dumps({"metadata": key, "bytes": records[key]["bytes"]}), flush=True)
        with (output/"metadata/classes.csv").open(encoding="utf-8-sig", newline="") as stream:
            classes = dict(csv.reader(stream))
        knife = next(key for key, label in classes.items() if label == "Knife")
        boxes = defaultdict(list)
        with (output/"metadata/boxes.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row["LabelName"] == knife and float(row["Confidence"]) == 1:
                    boxes[row["ImageID"]].append(row)
        metadata = {}
        with (output/"metadata/images.csv").open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row["ImageID"] in boxes: metadata[row["ImageID"]] = row
        eligible = []
        for key, entries in boxes.items():
            meta = metadata.get(key, {})
            if (not re.fullmatch(r"[0-9a-f]{16}", key) or
                meta.get("License", "").rstrip("/") not in {"http://creativecommons.org/licenses/by/2.0", "https://creativecommons.org/licenses/by/2.0"} or
                meta.get("Rotation", "") not in {"", "0", "0.0"} or any(x.get("IsGroupOf") == "1" for x in entries)):
                continue
            if any(not (0 <= float(x["XMin"]) < float(x["XMax"]) <= 1 and
                            0 <= float(x["YMin"]) < float(x["YMax"]) <= 1) for x in entries):
                continue
            eligible.append(key)
        rank = lambda key: hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()
        small = sorted((key for key in eligible if min((float(x["XMax"])-float(x["XMin"]))*
                    (float(x["YMax"])-float(x["YMin"])) for x in boxes[key]) <= .02), key=rank)
        small_set = set(small)
        other = sorted((key for key in eligible if key not in small_set), key=rank)
        chosen = small[:count//2]+other[:count-count//2]
        chosen_set = set(chosen)
        chosen += [x for x in sorted(eligible, key=rank) if x not in chosen_set][:count-len(chosen)]
        state.update(status="acquiring_images", eligible_images=len(eligible), selected_images=len(chosen), knife_mid=knife)
        _write_json(output/"state.json", state)

        def one(key):
            image, label = output/"images"/(key+".jpg"), output/"labels"/(key+".txt")
            url = f"https://open-images-dataset.s3.amazonaws.com/train/{key}.jpg"
            try:
                origin = download(url, image, 20*1024**2)
                check_detector_image(image)
                signature = image_signature(image)
                if signature["exif_orientation"] != 1: raise ValueError("Unresolved EXIF coordinates")
                lines = []
                for box in boxes[key]:
                    x1, x2, y1, y2 = (float(box[k]) for k in ("XMin", "XMax", "YMin", "YMax"))
                    lines.append("0 "+" ".join(format(v, ".17g") for v in ((x1+x2)/2, (y1+y2)/2, x2-x1, y2-y1)))
                label.write_text("\n".join(lines)+"\n", encoding="utf-8")
                return {**signature, "record_id": "open-images-train/"+key+".jpg", "source_dataset": "open-images-train",
                        "original_split": "train", "image": str(image.resolve()), "label": str(label.resolve()),
                        "download": origin, "image_metadata": metadata[key], "annotation_rows": boxes[key],
                        "knife_absence_verified": False, "source_session_verified": False, "human_review_complete": False}, None
            except Exception as exc:
                return None, {"image_id": key, "error": f"{type(exc).__name__}: {exc}"}
        accepted, errors = [], []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for row, error in pool.map(one, chosen):
                (errors if error else accepted).append(error if error else row)
        if not accepted: raise ValueError("No source images acquired successfully")
        write_jsonl(output/"candidates.jsonl", accepted)
        _write_json(output/"download-issues.json", errors)
        state.update(status="acquired_not_merged", acquired_images=len(accepted), failed_images=len(errors),
                     knife_objects=sum(len(r["annotation_rows"]) for r in accepted), seed=seed,
                     selection="up to half normalized-area<=.02, half other; deterministic source-ID hash; positive-only",
                     source_metadata=records, annotation_license="CC BY 4.0", image_license="publisher metadata CC BY 2.0; attribution retained",
                     individual_rights_independently_verified=False)
    except BaseException as exc:
        state.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        _write_json(output/"state.json", state)
    return state


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--count", default=1000, type=int)
    p.add_argument("--seed", default=20261105, type=int)
    a = p.parse_args()
    print(json.dumps(acquire(a.output_dir, count=a.count, seed=a.seed)))
