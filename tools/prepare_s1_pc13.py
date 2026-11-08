"""Compose provider-labelled synthetic S1 with frozen M2 real data and holdouts.

Acquisition is separate. Reuses provider-label validation and follow-up grouping;
never reads/writes live review DBs, invents negatives, or infers Holding labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from edge_threat_response.dataset.followup import open_images_candidates, prepare_followup, read_rows
from edge_threat_response.dataset.image_screening import image_signature
from edge_threat_response.dataset.labels import parse_yolo_label
from edge_threat_response.dataset.raw_import import check_detector_image
from edge_threat_response.replay import write_jsonl
from edge_threat_response.training import _sha256_file, _write_json


def source_candidates(root: Path, specifications: list[dict], *, dataset_id: str,
                        class_names: dict[int, str], source_url: str, license_name: str,
                        source_evidence: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """Keep Knife boxes or explicit provider negatives; reject malformed files."""
    knife_ids = [key for key, name in class_names.items() if name == "knife"]
    if len(knife_ids) != 1 or not specifications or not source_evidence:
        raise ValueError("Explicit source Knife class, records and evidence required")
    root = root.resolve()
    candidates, exclusions, seen = [], [], set()
    for item in specifications:
        identity = item["image"]
        if identity in seen:
            raise ValueError("Duplicate source image identity")
        seen.add(identity)
        image, label = (root/identity).resolve(), (root/item["label"]).resolve()
        if not image.is_relative_to(root) or not label.is_relative_to(root):
            raise ValueError("Source image/label escapes its root")
        # A class counter such as knife_0001 is not cross-source lineage.
        # Keep filename families within this pinned source. Global image
        # hash/similarity links to existing and protected sources still apply.
        record_id = dataset_id+"/"+str(Path(identity).with_name(dataset_id+"--"+Path(identity).name)).replace("\\", "/")
        try:
            check_detector_image(image)
            signature = image_signature(image, expected_sha256=item.get("image_sha256"))
            if signature["exif_orientation"] != 1:
                raise ValueError("Nondefault EXIF orientation")
            if any(key in item and signature[key] != item[key] for key in ("width", "height")):
                raise ValueError("Decoded image differs from provider annotation dimensions")
            label_hash = _sha256_file(label)
            if item.get("label_sha256", label_hash) != label_hash:
                raise ValueError("Source label hash changed")
            parsed = parse_yolo_label(label, source_dataset=dataset_id, path_reference=str(label),
                                      class_map={key: 0 for key in class_names})
            if parsed.issues or any(a.annotation_format != "bbox" for a in parsed.annotations):
                raise ValueError("Malformed, unmapped or non-bbox source annotation")
            lines = [line.split() for line in label.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            knife_lines = ["0 "+" ".join(tokens[1:]) for tokens in lines if int(tokens[0]) == knife_ids[0]]
            provider_negative = item.get("provider_knife_absence") is True
            if provider_negative and (knife_lines or not lines):
                raise ValueError("Provider negative must have other labelled objects and no Knife")
            if not knife_lines and not provider_negative:
                exclusions.append({"record_id": record_id, "reason": "no_provider_knife_not_assumed_negative"})
                continue
            if "knife_count" in item and item["knife_count"] != len(knife_lines):
                raise ValueError("Frozen source Knife count changed")
            candidates.append({**signature, "record_id": record_id, "dataset_id": dataset_id,
                "image_file": str(image), "label_text": "\n".join(knife_lines)+"\n",
                "original_split": item.get("original_split", "unsplit"), "source_url": source_url, "license": license_name,
                "synthetic": True, "provider_knife_absence": provider_negative,
                "source_group_basis": "source-namespaced filename family + global image similarity proxies; not verified sessions",
                "coordinate_contract": "provider-normalized-knife-bbox-v1",
                "annotation_provenance": {"source_image": identity, "source_label": item["label"],
                    "source_label_sha256": label_hash, "source_classes": class_names,
                    "source_evidence_sha256": source_evidence, "holding_labels_inferred": False,
                    "provider_knife_absence": provider_negative}})
        except (OSError, ValueError) as error:
            exclusions.append({"record_id": record_id, "reason": str(error)})
    return candidates, exclusions


def prepare(root: Path, output: Path, synthetic_spec: Path) -> dict:
    spec = json.loads(synthetic_spec.read_text(encoding="utf-8-sig"))
    evidence = {str(synthetic_spec): _sha256_file(synthetic_spec)}
    candidates, issues, source_counts = [], [], {}
    for source in spec["sources"]:
        for path, digest in source["evidence_sha256"].items():
            if _sha256_file(Path(path)) != digest:
                raise ValueError("Pinned source evidence changed")
            evidence[path] = digest
        rows, rejected = source_candidates(Path(source["root"]), source["records"],
            dataset_id=source["dataset_id"], class_names={int(k): v for k, v in source["class_names"].items()},
            source_url=source["source_url"], license_name=source["license"],
            source_evidence=source["evidence_sha256"])
        candidates.extend(rows); issues.extend(rejected)
        source_counts[source["dataset_id"]] = {"supplied_images": len(source["records"]),
            "valid_knife_positive_images": sum(not r["provider_knife_absence"] for r in rows),
            "provider_negative_images": sum(r["provider_knife_absence"] for r in rows)}
    if not candidates:
        raise ValueError("No valid synthetic Knife positives")
    guard = root/"data/review/team-candidates-20261003/us-mock"
    guard_evidence = guard/"image-evidence.jsonl"
    oi = root/"data/source-audit/open-images-train-20261105/candidates.jsonl"
    evidence.update({str(p): _sha256_file(p) for p in (guard_evidence, oi)})
    protected = []
    for row in read_rows(guard_evidence):
        path = (guard/row["image_file"]).resolve()
        if not path.is_relative_to(guard.resolve()):
            raise ValueError("Protected image escapes its pack")
        protected.append({**image_signature(path, expected_sha256=row["image_sha256"]),
            "record_id": "us-guard/"+row["image_path"], "dataset_id": "us-mock-protected",
            "image_file": str(path), "original_split": "protected_development"})
    result = prepare_followup(baseline=root/"data/processed/raw-real-20261105-v3/inventory.jsonl",
        signatures=root/"data/processed/raw-real-20261105-v2/signatures.jsonl",
        pairs=root/"data/processed/raw-real-20261105-v2/similarity-pairs.jsonl",
        quality_snapshot=root/"data/work/reviewed-next-training-20261106/review-evidence-snapshot.jsonl",
        candidates=[*open_images_candidates(oi), *candidates], protected=protected, output=output,
        expected_quality_exclusions=88)
    # S1 must add to M2, never silently change its real data or frozen holdouts.
    baseline = read_rows(root/"data/processed/m2-real-20261107-v1/inventory.jsonl")
    actual = read_rows(output/"inventory.jsonl")
    identity = lambda r: (r["image_id"], r["image_sha256"], r["label_sha256"], r["split"], r["knife_count"])
    expected = {identity(r) for r in baseline}
    real = {identity(r) for r in actual if not r.get("synthetic")}
    if real != expected:
        raise ValueError("New group evidence changes M2 real data; investigate before training")
    synthetic = [r for r in actual if r.get("synthetic")]
    if not synthetic or not sum(r["knife_count"] for r in synthetic) or any(r["split"] != "train" for r in synthetic):
        raise ValueError("S1 requires unprotected train-only synthetic additions")
    if evidence != {p: _sha256_file(Path(p)) for p in evidence}:
        raise ValueError("Source/protected evidence changed")
    write_jsonl(output/"source-selection-issues.jsonl", issues)
    result.update(source_candidates=source_counts, synthetic_train_images=len(synthetic),
        synthetic_train_boxes=sum(r["knife_count"] for r in synthetic), m2_real_identity_preserved=True,
        additional_source_evidence_sha256=evidence,
        synthetic_negative_images_added=sum(r["knife_count"] == 0 for r in synthetic),
        holding_labels_inferred=False)
    _write_json(output/"summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "output-dir", "synthetic-spec"):
        parser.add_argument("--"+name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root.resolve(), args.output_dir.resolve(), args.synthetic_spec.resolve()), indent=2))
