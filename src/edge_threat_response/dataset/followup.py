"""Train-only source additions with immutable baseline holdouts and proxy guards."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter
from pathlib import Path

from .development_subset import proxy_components
from .image_screening import image_signature, similarity_pairs
from .labels import parse_yolo_label
from .raw_import import check_detector_image
from ..replay import write_jsonl
from ..training import _sha256_file, _write_json


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def open_images_candidates(manifest: Path) -> list[dict]:
    """Read previously acquired provider Knife boxes; never create negatives."""
    candidates = []
    manifest_hash = _sha256_file(manifest)
    for row in read_rows(manifest):
        metadata, annotations = row["image_metadata"], row["annotation_rows"]
        if (row.get("original_split") != "train" or not annotations
                or metadata.get("Rotation", "") not in {"", "0", "0.0"}
                or metadata.get("License", "").rstrip("/") not in {
                    "http://creativecommons.org/licenses/by/2.0", "https://creativecommons.org/licenses/by/2.0"}
                or any(b["LabelName"] != "/m/04ctx" or float(b["Confidence"]) != 1
                       or b.get("IsGroupOf") == "1" for b in annotations)):
            raise ValueError("Expected the acquired Open Images train Knife/CC-BY subset")
        image, label = Path(row["image"]), Path(row["label"])
        if not re.fullmatch(r"[0-9a-f]{16}", image.stem):
            raise ValueError("Invalid Open Images source identity")
        parsed = parse_yolo_label(label, source_dataset="open-images-train", path_reference=str(label), class_map={0: 1})
        if (parsed.issues or len(parsed.annotations) != len(annotations)
                or any(b.annotation_format != "bbox" for b in parsed.annotations)):
            raise ValueError("Open Images labels are not valid positive knife boxes")
        supplied = sorted(tuple(float(b[k]) for k in ("XMin", "YMin", "XMax", "YMax")) for b in annotations)
        coordinates = [tuple(map(float, line.split()[1:])) for line in label.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        converted = sorted((x-w/2, y-h/2, x+w/2, y+h/2) for x, y, w, h in coordinates)
        if any(abs(a-b) > 1e-12 for left, right in zip(supplied, converted) for a, b in zip(left, right)):
            raise ValueError("Knife label bytes no longer match provider annotations")
        candidates.append({**row, "record_id": "open-images-train/"+image.name,
            "dataset_id": "open-images-train", "image_file": str(image),
            "label_text": label.read_text(encoding="utf-8"), "original_split": "train",
            "source_url": "https://storage.googleapis.com/openimages/web/index.html",
            "license": "image metadata CC BY 2.0; annotations CC BY 4.0; attribution retained at source",
            "coordinate_contract": "provider-normalized-knife-bbox-v1",
            "annotation_provenance": {"acquisition_manifest_sha256": manifest_hash,
                "source_label_sha256": _sha256_file(label), "open_images_id": image.stem}})
    if _sha256_file(manifest) != manifest_hash:
        raise ValueError("Acquisition manifest changed during selection")
    return candidates


def _cross_pairs(left: list[dict], right: list[dict]) -> list[dict]:
    """Compose the existing screen, including conservative stretch candidates."""
    result = []
    encoded = [(int(r["dhash64"], 16), r) for r in right]
    for a in left:
        value = int(a["dhash64"], 16)
        for other, b in encoded:
            exact = a["image_sha256"] == b["image_sha256"]
            distance = (value ^ other).bit_count()
            if not exact and (distance > 4 or a["low_information"] or b["low_information"]):
                continue
            found = similarity_pairs([a, b], 4)
            result.extend(found or [{"left": a["record_id"], "right": b["record_id"],
                "kind": "stretch_similarity_proxy", "hamming_distance": distance, "group_confirmed": False}])
    return result


def _holdout_identities(rows: list[dict], split: str) -> list[tuple]:
    return [(r["image_id"], r["image_sha256"], r["label_sha256"], r["knife_count"])
            for r in rows if r["split"] == split]


def prepare_followup(*, baseline: Path, signatures: Path, pairs: Path, quality_snapshot: Path,
                     candidates: list[dict], protected: list[dict], output: Path,
                     expected_quality_exclusions: int | None = None) -> dict:
    """Create fresh copies; never resplit holdouts or touch live human reviews."""
    output = output.resolve()
    inputs = [baseline, signatures, pairs, quality_snapshot]
    if output.exists() or any(output.is_relative_to(p.resolve().parent) or p.resolve().is_relative_to(output) for p in inputs):
        raise ValueError("Fresh output separate from baseline and evidence required")
    hashes = {str(p): _sha256_file(p) for p in inputs}
    original, source = read_rows(baseline), read_rows(signatures)
    if any(output.is_relative_to(Path(r[key]).resolve().parent) for r in original for key in ("image", "label")):
        raise ValueError("Fresh output separate from baseline image/label directories required")
    source_pairs = read_rows(pairs)
    initial_groups = proxy_components(source, source_pairs)
    if any(initial_groups.get(r["image_id"]) != r["source_group"] for r in original):
        raise ValueError("Baseline inventory does not match its source/group evidence")
    baseline_groups, baseline_hashes = {}, set()
    for row in original:
        if row.get("split") not in {"train", "val", "test"} or row["image_sha256"] in baseline_hashes:
            raise ValueError("Baseline split or image identity invalid")
        if row["source_group"] in baseline_groups and baseline_groups[row["source_group"]] != row["split"]:
            raise ValueError("Baseline group crosses partitions")
        baseline_groups[row["source_group"]] = row["split"]
        baseline_hashes.add(row["image_sha256"])
        for key in ("image", "label"):
            if _sha256_file(Path(row[key])) != row[key+"_sha256"]:
                raise ValueError("Baseline image/label bytes changed")
    if any(not _holdout_identities(original, split) for split in ("val", "test")):
        raise ValueError("Frozen validation and test records required")
    held = {r["image_sha256"] for r in read_rows(quality_snapshot)
            if r.get("raw_split") == "train" and r.get("raw_overlay_matches") is True and r.get("verdict") != "ok"}
    train_hashes = {r["image_sha256"] for r in original if r["split"] == "train"}
    if not held <= train_hashes or (expected_quality_exclusions is not None and len(held) != expected_quality_exclusions):
        raise ValueError("Quality exclusions must bind the expected baseline training rows")
    additions = []
    for row in candidates:
        check_detector_image(Path(row["image_file"]))
        signature = image_signature(Path(row["image_file"]), expected_sha256=row["image_sha256"])
        if signature["exif_orientation"] != 1 or (signature["width"], signature["height"]) != (row["width"], row["height"]):
            raise ValueError("Additional image/annotation geometry mismatch")
        if not row.get("label_text", "").strip() and not (
                row.get("provider_knife_absence") is True
                and row.get("annotation_provenance", {}).get("provider_knife_absence") is True):
            raise ValueError("Source addition needs positive labels or explicit provider Knife absence evidence")
        additions.append({**row, **signature})
    if not additions:
        raise ValueError("No additional provider-annotated candidates")
    references = [*source, *protected]
    all_rows = [*references, *additions]
    if len({r["record_id"] for r in all_rows}) != len(all_rows):
        raise ValueError("Source/protected/additional record IDs must be unique")
    new_pairs = [*_cross_pairs(protected, source), *similarity_pairs(protected, 4),
                 *_cross_pairs(additions, references), *similarity_pairs(additions, 4)]
    groups = proxy_components(all_rows, [*source_pairs, *new_pairs])
    protected_ids = {r["record_id"] for r in source if r["dataset_id"] == "protected"}
    protected_ids |= {r["record_id"] for r in protected}
    protected_ids |= {r["image_id"] for r in original if r["split"] in {"val", "test"}}
    guarded = {groups[key] for key in protected_ids}
    represented = {groups[r["record_id"]] for r in source}
    frozen_groups = {split: {groups[r["image_id"]] for r in original if r["split"] == split} for split in ("val", "test")}
    if frozen_groups["val"] & frozen_groups["test"]:
        raise ValueError("New evidence links frozen val and test; preserve inputs and investigate")
    selected, exclusions = [], []
    for row in original:
        reason = None
        if row["split"] == "train":
            reason = "known_quality_hold" if row["image_sha256"] in held else "expanded_protected_group" if groups[row["image_id"]] in guarded else None
        if reason:
            exclusions.append({"record_id": row["image_id"], "image_sha256": row["image_sha256"], "reason": reason})
        else:
            selected.append({**row, "source_group": groups[row["image_id"]], "parent_image": row["image"], "parent_label": row["label"]})
    seen = {r["image_sha256"] for r in selected}
    accepted = []
    for row in sorted(additions, key=lambda r: r["record_id"]):
        group = groups[row["record_id"]]
        reason = ("protected_proxy_group" if group in guarded else "represented_source_proxy_group" if group in represented
                  else "exact_new_duplicate" if row["image_sha256"] in seen else None)
        if reason:
            exclusions.append({"record_id": row["record_id"], "image_sha256": row["image_sha256"], "reason": reason})
            continue
        seen.add(row["image_sha256"])
        accepted.append(row)
        selected.append({"image_id": row["record_id"], "source_dataset": row["dataset_id"],
            "source_group": group, "split": "train", "parent_image": row["image_file"],
            "label_text": row["label_text"], "image_sha256": row["image_sha256"],
            "knife_count": sum(bool(line.strip()) for line in row["label_text"].splitlines()), "original_split": row["original_split"],
            "source_url": row["source_url"], "license": row["license"],
            "annotation_provenance": row["annotation_provenance"], "coordinate_contract": row["coordinate_contract"],
            **{key: row[key] for key in ("synthetic", "source_group_basis", "provider_knife_absence") if key in row}})
    if not accepted:
        raise ValueError("No unprotected new source groups; do not run M2 as a relabeled Q1")
    output.mkdir(parents=True)
    (output/"images").mkdir(); (output/"labels").mkdir()
    materialized = []
    for row in selected:
        if not re.fullmatch(r"[a-z0-9-]+", row["source_dataset"]):
            raise ValueError("Invalid source name for materialized filename")
        stem = row["source_dataset"]+"-"+row["image_sha256"][:24]
        image = output/"images"/(stem+Path(row["parent_image"]).suffix.lower())
        label = output/"labels"/(stem+".txt")
        if image.exists() or label.exists():
            raise ValueError("Duplicate materialized identity")
        check_detector_image(Path(row["parent_image"]))
        shutil.copyfile(row["parent_image"], image)
        if "parent_label" in row:
            shutil.copyfile(row["parent_label"], label)
        else:
            label.write_text(row["label_text"], encoding="utf-8", newline="\n")
        if _sha256_file(image) != row["image_sha256"]:
            raise ValueError("Image changed during isolated copy")
        if "label_sha256" in row and _sha256_file(label) != row["label_sha256"]:
            raise ValueError("Frozen baseline label changed during copy")
        parsed = parse_yolo_label(label, source_dataset=row["source_dataset"], path_reference=str(label), class_map={0: 1})
        if parsed.issues or len(parsed.annotations) != row["knife_count"] or any(b.annotation_format != "bbox" for b in parsed.annotations):
            raise ValueError("Materialized knife annotation invalid")
        row = {k:v for k,v in row.items() if k != "label_text"}
        materialized.append({**row, "image": image.as_posix(), "label": label.as_posix(),
            "label_sha256": _sha256_file(label), "human_review_status": "not_required_for_raw_exploration",
            "negative_absence_verified": False})
    for split in ("val", "test"):
        if _holdout_identities(original, split) != _holdout_identities(materialized, split):
            raise ValueError("Frozen holdout identities/order changed")
    if hashes != {str(p):_sha256_file(p) for p in inputs}:
        raise ValueError("Input evidence changed during preparation")
    write_jsonl(output/"inventory.jsonl", materialized)
    write_jsonl(output/"exclusions.jsonl", exclusions)
    write_jsonl(output/"new-similarity-pairs.jsonl", new_pairs)
    result = {"schema_version":1,"status":"prepared_raw_followup_not_final",
        "input_sha256":hashes,"inventory_sha256":_sha256_file(output/"inventory.jsonl"),
        "baseline_images":len(original),"known_quality_exclusions":len(held),
        "exclusions":dict(Counter(r["reason"] for r in exclusions)),
        "additional_candidates":len(additions),"accepted_additional_images":len(accepted),
        "split_counts":dict(Counter(r["split"] for r in materialized)),
        "train_sources":dict(Counter(r["source_dataset"] for r in materialized if r["split"]=="train")),
        "frozen_holdout_identity_sha256":{s:hashlib.sha256(json.dumps(_holdout_identities(original,s)).encode()).hexdigest() for s in ("val","test")},
        "baseline_holdouts_preserved":True,"protected_extra_images":len(protected),
        "group_policy":"cached source components + new hash/dhash/stretch + filename proxies; not verified sessions",
        "human_review_complete":False,"final_evaluation_allowed":False,"production_review_modified":False}
    _write_json(output/"summary.json", result)
    return result
