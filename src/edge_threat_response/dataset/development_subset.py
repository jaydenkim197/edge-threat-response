"""Prepare the explicitly authorized, reviewed SOHAS development trial only."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .image_screening import image_signature
from .labels import parse_yolo_label
from .materialize import _place_image, _safe_stem
from .models import ManifestRecord
from .sohas import VOC_ROOT, _inventory, _source_bytes, parse_sohas_voc
from .split import plan_group_split
from ..replay import write_jsonl
from ..training import _git_commit, _sha256_file, _write_json
from ..training_pair import load_plan


COORDINATE_CONTRACT = "review-overlay-pixel-edges-v1"
GROUP_POLICY = "filename-family+full-source-dhash-components-v1"


def proxy_components(integrity: list[dict], pairs: list[dict]) -> dict[str, str]:
    parent = {row["record_id"]: row["record_id"] for row in integrity}
    if len(parent) != len(integrity) or not parent:
        raise ValueError("Integrity inventory must have unique image paths")

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left, right):
        if left not in parent or right not in parent:
            raise ValueError("Similarity pair outside the full source inventory")
        left, right = find(left), find(right)
        if left != right:
            parent[max(left, right)] = min(left, right)

    families, hashes = {}, {}
    for row in integrity:
        path = row["record_id"]
        stem = Path(path).stem.lower()
        family = re.sub(r"\d+(?:v\d+)?$", "", stem).rstrip("_- .") or stem
        if family in families:
            union(path, families[family])
        families[family] = path
        digest = row["image_sha256"]
        if digest in hashes:
            union(path, hashes[digest])
        hashes[digest] = path
    for pair in pairs:
        union(pair["left"], pair["right"])
    return {path: "proxy-" + hashlib.sha256(find(path).encode()).hexdigest()[:24] for path in parent}


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def prepare_development(*, manifest: Path, source_root: Path, integrity_path: Path, pairs_path: Path,
                        plan_path: Path, checkpoint: Path, output: Path, authorization_id: str,
                        expected_count: int = 183) -> dict:
    if not authorization_id.strip() or expected_count < 1 or output.exists():
        raise ValueError("Explicit user authorization, bounded selection and a fresh output are required")
    source_root, output = source_root.resolve(), output.resolve()
    inputs = {"review_snapshot": manifest, "integrity": integrity_path, "similarity_pairs": pairs_path,
              "plan": plan_path, "checkpoint": checkpoint}
    if (source_root.is_relative_to(output) or output.is_relative_to(source_root)
            or any(output.is_relative_to(path.parent.resolve()) for path in (manifest, integrity_path, pairs_path))):
        raise ValueError("Development output must be outside input directories")
    input_hashes = {key: _sha256_file(path) for key, path in inputs.items()}
    plan = load_plan(plan_path)
    if plan["source_id"] != "sohas" or plan["model_family"] != "yolo26n":
        raise ValueError("This authorization is restricted to SOHAS/YOLO26n")
    inventory = _inventory(source_root)
    integrity = _jsonl(integrity_path)
    signatures = {row["record_id"]: row for row in integrity}
    groups = proxy_components(integrity, _jsonl(pairs_path))
    selected = [row for row in _jsonl(manifest) if row.get("dataset_id") == "sohas"
                and row.get("candidate_status") in {"candidate_positive", "candidate_negative"}]
    if len(selected) != expected_count or len({row["record_id"] for row in selected}) != len(selected):
        raise ValueError("Selection changed or has duplicate identities; re-authorize the new snapshot/count")
    eligible, exclusions, seen_hashes = [], [], set()
    for row in selected:
        if row.get("review_verdict") != "ok" or type(row.get("review_version")) is not int or row["review_version"] < 1:
            raise ValueError("Only actual normal human-reviewed rows may enter the trial")
        path, digest = row["image_path"], row["image_sha256"]
        if path not in signatures or signatures[path]["image_sha256"] != digest:
            raise ValueError("Review image is not bound to the full source integrity inventory")
        raw = _source_bytes(source_root, path, inventory[path])
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Reviewed source image bytes changed")
        signature = image_signature(source_root / path, expected_sha256=digest)
        if signature["exif_orientation"] != 1:
            exclusions.append({"record_id": row["record_id"], "reason": "nondefault_exif_orientation"})
            continue
        if digest in seen_hashes:
            exclusions.append({"record_id": row["record_id"], "reason": "exact_duplicate"})
            continue
        seen_hashes.add(digest)
        split = row["original_split"]
        if split not in {"train", "test"}:
            raise ValueError("SOHAS original split must be known")
        folder = "annotations/xmls" if split == "train" else "annotations_test/xmls"
        xml_path = f"{VOC_ROOT}/{folder}/{Path(path).stem}.xml"
        xml = _source_bytes(source_root, xml_path, inventory[xml_path])
        annotation = parse_sohas_voc(xml, image_name=Path(path).name, convention="pixel-edges")
        boxes = [[float(value) for value in item["bbox_xyxy_raw"]] for item in annotation["objects"] if item["raw_name"] == "knife"]
        if (annotation["errors"] or boxes != row["raw_boxes_xyxy"] or len(boxes) != row["knife_count"]
                or (signature["width"], signature["height"]) != (row["width"], row["height"])
                or (annotation["width"], annotation["height"]) != (row["width"], row["height"])):
            raise ValueError("VOC/review/decode annotation mismatch; no partial box export")
        eligible.append((row, annotation, hashlib.sha256(xml).hexdigest()))
    records = []
    for row, annotation, _ in eligible:
        count = row["knife_count"]
        records.append(ManifestRecord(
            schema_version=1, image_id="sha256:" + row["image_sha256"], source_dataset="sohas",
            source_url=None, declared_license=None, original_path=row["image_path"], label_path=None,
            source_group=groups[row["image_path"]], group_namespace=GROUP_POLICY, original_split=row["original_split"],
            planned_split=None, image_sha256=row["image_sha256"], label_sha256=None,
            annotation_status="valid" if count else "empty", annotation_formats=("bbox",) if count else (),
            annotation_format_counts=(("bbox", count),) if count else (), raw_class_ids=(2,) if count else (),
            raw_class_counts=((2, count),) if count else (), canonical_class_ids=(1,) if count else (),
            canonical_class_counts=((1, count),) if count else (), object_count=count))
    split_plan, planned = plan_group_split(records, ratios={"train": .7, "val": .15, "test": .15}, seed=20261026)
    assignments = {row.original_path: row.planned_split for row in planned}
    for partition in ("train", "val", "test"):
        if not any(assignments[row["image_path"]] == partition and row["knife_count"] for row, _, _ in eligible):
            raise ValueError("Each development partition needs at least one positive; do not break groups to fill it")
    if input_hashes != {key: _sha256_file(path) for key, path in inputs.items()}:
        raise ValueError("Preparation inputs changed")
    output.mkdir(parents=True)
    exported = []
    for row, annotation, xml_hash in eligible:
        partition = assignments[row["image_path"]]
        stem = _safe_stem("sohas", "sha256:" + row["image_sha256"])
        image = output / "images" / partition / (stem + Path(row["image_path"]).suffix.lower())
        label = output / "labels" / partition / (stem + ".txt")
        image.parent.mkdir(parents=True, exist_ok=True)
        label.parent.mkdir(parents=True, exist_ok=True)
        _place_image(source_root / row["image_path"], image, "copy")
        lines = annotation["candidate_yolo_lines"]
        label.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        parsed = parse_yolo_label(label, source_dataset="sohas", path_reference=str(label), class_map={0: 1})
        if parsed.issues or len(parsed.annotations) != row["knife_count"]:
            raise ValueError("Exported label did not round-trip")
        if _sha256_file(image) != row["image_sha256"]:
            raise ValueError("Copied image bytes changed")
        exported.append({"image_id": "sha256:" + row["image_sha256"], "source_dataset": "sohas",
                         "image": image.as_posix(), "label": label.as_posix(), "split": partition,
                         "image_sha256": row["image_sha256"], "label_sha256": _sha256_file(label),
                         "source_group": groups[row["image_path"]], "draw_count": 1,
                         "knife_count": row["knife_count"], "review_record_id": row["record_id"],
                         "review_version": row["review_version"], "review_verdict": "ok",
                         "review_payload_sha256": row["review_payload_sha256"], "xml_sha256": xml_hash,
                         "original_split": row["original_split"], "coordinate_contract": COORDINATE_CONTRACT,
                         "development_only": True})
        exported[-1]["negative_absence_reviewed"] = row["knife_count"] == 0 and row["candidate_status"] == "candidate_negative"
    dataset_manifest = output / "DEV-manifest.jsonl"
    write_jsonl(dataset_manifest, exported)
    write_jsonl(output / "excluded.jsonl", exclusions)
    lists = {}
    for partition in ("train", "val", "test"):
        path = output / f"{partition}.txt"
        path.write_text("\n".join(row["image"] for row in exported if row["split"] == partition) + "\n", encoding="utf-8")
        lists[f"{partition}_list"] = path
    data_yaml, config_path = output / "data.yaml", output / "training.json"
    _write_json(data_yaml, {"path": output.as_posix(), **{key.removesuffix("_list"): path.as_posix() for key, path in lists.items()}, "names": {"0": "knife"}})
    run_id = output.name
    _write_json(config_path, {"schema_version": 1, "profile_id": run_id, "recipe_id": "DEV-SOHAS",
                              "approval_required": True, "model": checkpoint.resolve().as_posix(),
                              "task": "detect", "run_name": run_id, "arguments": plan["arguments"]})
    bound = {"config": config_path, "data_yaml": data_yaml, "dataset_manifest": dataset_manifest,
             "pretrained": checkpoint, **lists}
    approval = {"schema_version": 1, "status": "authorized_development_only", "pair_id": run_id,
                "approval_id": authorization_id, "reviewer_alias": "project-owner", "approved_at": datetime.now(timezone.utc).isoformat(),
                "scope": "reviewed_sohas_development_only", "coordinate_contract": COORDINATE_CONTRACT,
                "group_policy": GROUP_POLICY, "formal_source_approval": False,
                "original_coordinate_semantics_verified": False, "recording_session_independence_verified": False,
                "final_evaluation_allowed": False, "redistribution_approved": False,
                "rights_scope": "internal_course_research_no_redistribution",
                "recipes": {"DEV-SOHAS": {f"{key}_sha256": _sha256_file(path) for key, path in bound.items()}}}
    _write_json(output / "development-authorization.json", approval)
    for name in ("README.md", "License.md"):
        if name in inventory:
            (output / ("upstream-" + name)).write_bytes(_source_bytes(source_root, name, inventory[name]))
    summary = {"schema_version": 1, "status": "authorized_development_only", "git_commit": _git_commit(),
               "authorization_id": authorization_id, "input_sha256": input_hashes, "selected_reviewed": len(selected),
               "exported": len(exported), "excluded": exclusions, "object_count": sum(row["knife_count"] for row in exported),
               "proxy_groups": len({row["source_group"] for row in exported}), "split_plan": split_plan,
               "split_counts": {split: {"images": sum(row["split"] == split for row in exported),
                   "positive": sum(row["split"] == split and row["knife_count"] > 0 for row in exported),
                   "negative": sum(row["split"] == split and row["knife_count"] == 0 for row in exported)} for split in ("train", "val", "test")},
               "coordinate_contract": COORDINATE_CONTRACT, "group_policy": GROUP_POLICY,
               "formal_source_approval": False, "final_evaluation_allowed": False,
               "limits": ["review overlay coordinates interpreted literally as pixel edges, not recovered source semantics",
                          "proxy connected components are not verified camera/recording sessions",
                          "test partition reserved, not used for development model selection", "no final research performance or redistribution approval"]}
    _write_json(output / "preparation.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "source-root", "integrity", "pairs", "plan", "checkpoint", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--expected-count", type=int, default=183)
    args = parser.parse_args(argv)
    try:
        result = prepare_development(manifest=args.manifest, source_root=args.source_root, integrity_path=args.integrity,
                                     pairs_path=args.pairs, plan_path=args.plan, checkpoint=args.checkpoint,
                                     output=args.output_dir, authorization_id=args.authorization_id, expected_count=args.expected_count)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({key: value for key, value in result.items() if key not in {"split_plan", "excluded"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
