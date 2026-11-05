"""Import source annotations without inventing review or recording-session truth."""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from .development_subset import proxy_components
from .image_screening import image_signature, similarity_pairs
from .models import ManifestRecord
from .split import plan_group_split
from ..replay import write_jsonl
from ..training import _sha256_file, _write_json


def check_detector_image(path: Path) -> None:
    """Match the trainer's strict geometry/JPEG checks without repairing bytes."""
    from PIL import Image
    try:
        with Image.open(path) as image:
            if min(image.size) < 10:
                raise ValueError("Detector image dimensions are smaller than 10 pixels")
            jpeg = image.format.lower() in {"jpeg", "jpg"}
            image.verify()
        if jpeg:
            with path.open("rb") as stream:
                stream.seek(-2, 2)
                if stream.read() != b"\xff\xd9":
                    raise ValueError("Missing JPEG end marker; source repair is not permitted")
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"Invalid detector image: {exc}") from exc


def filter_detector_inventory(inventory: Path, output: Path) -> dict:
    if output.exists(): raise ValueError("Fresh filtered inventory output required")
    rows = [json.loads(x) for x in inventory.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
    keep, excluded = [], []
    for row in rows:
        image = Path(row["image"])
        if _sha256_file(image) != row["image_sha256"]:
            raise ValueError("Materialized bytes changed; do not silently reauthorize repairs")
        try:
            check_detector_image(image)
            image_signature(image, expected_sha256=row["image_sha256"])
        except (OSError, ValueError) as exc:
            excluded.append({"image_id": row["image_id"], "reason": str(exc), "image_sha256": row["image_sha256"]})
            continue
        keep.append(row)
    output.mkdir(parents=True)
    write_jsonl(output/"inventory.jsonl", keep)
    write_jsonl(output/"exclusions.jsonl", excluded)
    result = {"input_inventory_sha256": _sha256_file(inventory), "images": len(keep), "excluded": excluded,
              "split_assignment_changed": False, "source_images_modified": False,
              "split_sources": {s: dict(Counter(r["source_dataset"] for r in keep if r["split"] == s)) for s in ("train", "val", "test")}}
    _write_json(output/"summary.json", result)
    return result


def voc_knife(data: bytes, *, width: int, height: int, allowed_names: set[str]) -> str:
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML declarations not allowed")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid VOC XML: {exc}") from exc
    if root.tag != "annotation" or int(root.findtext("size/width", "0")) != width or int(root.findtext("size/height", "0")) != height:
        raise ValueError("VOC image dimensions mismatch")
    lines = []
    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip().casefold()
        if name not in allowed_names:
            raise ValueError(f"Unknown source class: {name!r}")
        coords = [float(obj.findtext("bndbox/" + k, "nan")) for k in ("xmin", "ymin", "xmax", "ymax")]
        x1, y1, x2, y2 = coords
        if not all(math.isfinite(v) for v in coords) or not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
            raise ValueError("Invalid pixel-edge bbox; no automatic clipping")
        if name == "knife":
            values = ((x1+x2)/(2*width), (y1+y2)/(2*height), (x2-x1)/width, (y2-y1)/height)
            lines.append("0 " + " ".join(format(v, ".17g") for v in values))
    return "\n".join(lines) + ("\n" if lines else "")


def materialize_inventory(candidates: list[dict], protected: list[dict], output: Path,
                          *, seed: int = 20261004, distance: int = 4) -> dict:
    """Candidates contain validated knife-only text and decoded signatures.

    Cross-source exact/dHash candidates and filename families form conservative
    proxy groups. A proxy link is never described as a confirmed shared session.
    """
    if output.exists() or not candidates:
        raise ValueError("Nonempty candidates and a new output directory required")
    all_rows = [*candidates, *protected]
    if len({r["record_id"] for r in all_rows}) != len(all_rows):
        raise ValueError("Unique inventory record IDs required")
    output.mkdir(parents=True)
    print(json.dumps({"stage": "global_similarity", "images": len(all_rows)}), flush=True)
    pairs = similarity_pairs(all_rows, distance)
    families = {}
    for row in all_rows:
        stem = Path(row["record_id"]).stem.lower()
        clean = re.sub(r"\.rf\.[a-f0-9]+$", "", stem)
        if clean != stem:
            clean = re.sub(r"_(jpg|png|jpeg)$", "", clean)
            family = re.sub(r"\d+$", "", clean).rstrip("_- .") or clean
            if family in families:
                pairs.append({"left": families[family], "right": row["record_id"], "kind": "roboflow_filename_family_proxy", "group_confirmed": False})
            families[family] = row["record_id"]
    groups = proxy_components(all_rows, pairs)
    protected_groups = {groups[r["record_id"]] for r in protected}
    seen, selected, exclusions = set(), [], []
    for row in candidates:
        reason = "protected_proxy_group" if groups[row["record_id"]] in protected_groups else "exact_duplicate" if row["image_sha256"] in seen else None
        if reason:
            exclusions.append({"record_id": row["record_id"], "reason": reason, "image_sha256": row["image_sha256"]})
            continue
        seen.add(row["image_sha256"])
        selected.append({**row, "source_group": groups[row["record_id"]]})
    records = []
    for row in selected:
        records.append(ManifestRecord(
            schema_version=1, image_id=row["record_id"], source_dataset=row["dataset_id"],
            source_url=row["source_url"], declared_license=row["license"], original_path=row["record_id"],
            label_path=None, source_group=row["source_group"], group_namespace="raw-global-v1",
            original_split=row["original_split"], planned_split=None, image_sha256=row["image_sha256"],
            label_sha256=None, annotation_status="valid" if row["label_text"] else "empty",
            annotation_formats=("bbox",) if row["label_text"] else (), annotation_format_counts=(),
            raw_class_ids=(), raw_class_counts=(), canonical_class_ids=(1,) if row["label_text"] else (),
            canonical_class_counts=(), object_count=len(row["label_text"].splitlines())))
    split_summary, planned = plan_group_split(records, ratios={"train": .8, "val": .1, "test": .1}, seed=seed)
    assignment = {x.image_id: x.planned_split for x in planned}
    (output / "images").mkdir()
    (output / "labels").mkdir()
    rows = []
    for row in selected:
        stem = row["dataset_id"] + "-" + row["image_sha256"][:24]
        image = output / "images" / (stem + Path(row["image_file"]).suffix.lower())
        label = output / "labels" / (stem + ".txt")
        # Copies isolate raw images from any decoder/trainer repair operation.
        shutil.copyfile(row["image_file"], image)
        if _sha256_file(image) != row["image_sha256"]:
            raise ValueError("Source image changed while materializing")
        label.write_text(row["label_text"], encoding="utf-8", newline="\n")
        rows.append({"image_id": row["record_id"], "source_dataset": row["dataset_id"],
                     "source_group": row["source_group"], "split": assignment[row["record_id"]],
                     "image": image.resolve().as_posix(), "label": label.resolve().as_posix(),
                     "image_sha256": row["image_sha256"], "label_sha256": _sha256_file(label),
                     "knife_count": len(row["label_text"].splitlines()), "original_split": row["original_split"],
                     "source_url": row["source_url"], "license": row["license"],
                     "annotation_provenance": row["annotation_provenance"],
                     "coordinate_contract": row["coordinate_contract"],
                     "human_review_status": "not_required_for_raw_exploration", "negative_absence_verified": False})
    write_jsonl(output / "inventory.jsonl", rows)
    write_jsonl(output / "exclusions.jsonl", exclusions)
    write_jsonl(output / "similarity-pairs.jsonl", pairs)
    write_jsonl(output / "signatures.jsonl", [{k: v for k, v in x.items() if k != "label_text"} for x in all_rows])
    result = {"images": len(rows), "sources": dict(Counter(r["source_dataset"] for r in rows)),
              "split_sources": {s: dict(Counter(r["source_dataset"] for r in rows if r["split"] == s)) for s in ("train", "val", "test")},
              "exclusions": dict(Counter(r["reason"] for r in exclusions)), "proxy_split": split_summary,
              "group_policy": "filename-family+global-sha256+dhash4; conservative proxies, not verified sessions",
              "human_review_complete": False, "final_evaluation_allowed": False,
              "coordinate_semantics": "source pixel edges assumed for VOC, not independently verified"}
    _write_json(output / "summary.json", result)
    return result
