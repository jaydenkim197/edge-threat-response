"""Read-only SOHAS VOC screening; outputs proposals, never training admission."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from .labels import parse_yolo_label
from .models import ValidationIssue
from .review import size_bucket


UPSTREAM_COMMIT = "48860b990e4d4f57fe100248887fceb248475dc8"
SOURCE_URL = "https://github.com/ari-dasci/OD-WeaponDetection"
BASE = "Weapons and similar handled objects"
VOC_ROOT = f"{BASE}/Sohas_weapon-Detection"
YOLO_ROOT = f"{BASE}/Sohas_weapon-Detection-YOLOv5"
RAW_NAMES = {0: "pistol", 1: "smartphone", 2: "knife", 3: "monedero", 4: "billete", 5: "tarjeta"}
CONVENTIONS = ("unknown", "pixel-edges", "voc-1based-inclusive")


def parse_sohas_voc(data: bytes, *, image_name: str, convention: str = "unknown") -> dict:
    """Preserve each object; fail the whole image rather than drop a bad knife."""
    if convention not in CONVENTIONS:
        raise ValueError("Unsupported coordinate convention.")
    # ElementTree does not fetch external entities; forbid declarations as well.
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("XML entity/doctype declarations are not supported.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Malformed XML: {exc}") from exc
    if root.tag != "annotation":
        raise ValueError("Expected an annotation XML root.")
    filename = root.findtext("filename")
    if len(root.findall("size")) != 1 or any(
        len(root.findall(f"size/{key}")) != 1 for key in ("width", "height")
    ):
        raise ValueError("Image dimensions are missing or ambiguous.")
    dimensions = [root.findtext(f"size/{key}") for key in ("width", "height")]
    try:
        width, height = (int(value) for value in dimensions)
    except (TypeError, ValueError) as exc:
        raise ValueError("Image dimensions must be positive integers.") from exc
    if width <= 0 or height <= 0:
        raise ValueError("Image dimensions must be positive integers.")
    objects = []
    lines = []
    case_difference = filename is not None and filename != image_name and filename.casefold() == image_name.casefold()
    issues = [] if filename == image_name or case_difference else ["XML filename does not match paired image; identity requires review."]
    if len(root.findall("filename")) != 1:
        issues.append("XML filename is missing or ambiguous.")
    for index, obj in enumerate(root.findall("object")):
        name = obj.findtext("name")
        item = {
            "object_index": index, "raw_name": name,
            "raw_class_id": next((key for key, value in RAW_NAMES.items() if value == name), None),
            "bbox_xyxy_raw": [obj.findtext(f"bndbox/{key}") for key in ("xmin", "ymin", "xmax", "ymax")],
            "difficult": obj.findtext("difficult"), "truncated": obj.findtext("truncated"),
        }
        objects.append(item)
        try:
            if item["raw_class_id"] is None:
                raise ValueError(f"Unknown SOHAS class {name!r}.")
            if len(obj.findall("name")) != 1:
                raise ValueError("Object class name is ambiguous.")
            if len(obj.findall("bndbox")) != 1:
                raise ValueError("Expected exactly one bndbox per object.")
            if any(len(obj.findall(f"bndbox/{key}")) != 1 for key in ("xmin", "ymin", "xmax", "ymax")):
                raise ValueError("BBox coordinates are missing or ambiguous.")
            coords = [float(value) for value in item["bbox_xyxy_raw"]]
            if not all(math.isfinite(value) for value in coords):
                raise ValueError("Non-finite bbox coordinate.")
            left, top, right, bottom = coords
            if convention == "voc-1based-inclusive":
                if not all(value.is_integer() for value in coords):
                    raise ValueError("Inclusive pixel coordinates must be integers.")
                if not (1 <= left <= right <= width and 1 <= top <= bottom <= height):
                    raise ValueError("Invalid 1-based inclusive bounds.")
                left -= 1
                top -= 1
            elif not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise ValueError("Invalid or ambiguous bbox bounds; no clipping is performed.")
            if name == "knife" and convention != "unknown":
                bbox = ((left + right) / (2 * width), (top + bottom) / (2 * height),
                        (right - left) / width, (bottom - top) / height)
                item["candidate_yolo_bbox"] = bbox
                lines.append("0 " + " ".join(format(value, ".17g") for value in bbox))
        except (TypeError, ValueError) as exc:
            issues.append(f"object {index}: {exc}")
    if not objects:
        issues.append("No annotated objects; completeness requires review.")
    if issues:
        lines = []  # A partial annotation must never become a training proposal.
    return {"width": width, "height": height, "xml_filename": filename,
            "filename_case_difference": case_difference, "objects": objects,
            "knife_count": sum(item["raw_name"] == "knife" for item in objects),
            "candidate_yolo_lines": lines, "errors": issues}


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise ValueError("Could not read upstream Git metadata: " + result.stderr.decode(errors="replace"))
    return result.stdout


def _inventory(root: Path) -> dict[str, str]:
    if _git(root, "rev-parse", "HEAD").decode().strip() != UPSTREAM_COMMIT:
        raise ValueError(f"SOHAS source must be pinned at {UPSTREAM_COMMIT}.")
    files = {}
    for entry in _git(root, "ls-tree", "-r", "-z", "HEAD").split(b"\0"):
        if not entry:
            continue
        header, path = entry.split(b"\t", 1)
        mode, kind, blob = header.split()
        if kind == b"blob" and mode in {b"100644", b"100755"}:
            files[path.decode("utf-8")] = blob.decode()
    return files


def _source_bytes(root: Path, path: str, blob: str) -> bytes:
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Source path escapes upstream root.")
    data = target.read_bytes()
    actual = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if actual != blob:
        raise ValueError("Local source bytes differ from pinned Git blob.")
    return data


def audit_sohas_voc(
    source_root: Path, output_dir: Path, *, convention: str = "unknown",
    coordinate_evidence: str | None = None, sample_count: int = 100, seed: int = 20261002,
) -> dict:
    source_root, output_dir = source_root.resolve(), output_dir.resolve()
    if convention not in CONVENTIONS:
        raise ValueError("Unsupported coordinate convention.")
    if sample_count <= 0:
        raise ValueError("Sample count must be positive.")
    if convention != "unknown" and not (coordinate_evidence and coordinate_evidence.strip()):
        raise ValueError("An explicit coordinate convention requires --coordinate-evidence.")
    if output_dir.is_relative_to(source_root) or source_root.is_relative_to(output_dir):
        raise ValueError("Output must be separate from the read-only source tree.")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output directory must be empty; preserve previous audit runs.")
    inventory = _inventory(source_root)
    rows, issues = [], []

    def issue(code: str, path: str, message: str, severity: str = "error") -> None:
        issues.append(ValidationIssue(severity, code, message, "sohas-voc", path))

    for split, image_folder, xml_folder in (
        ("train", "images", "annotations/xmls"),
        ("test", "images_test", "annotations_test/xmls"),
    ):
        images = {path: blob for path, blob in inventory.items()
                  if path.startswith(f"{VOC_ROOT}/{image_folder}/") and Path(path).suffix.lower() in {".jpg", ".jpeg", ".png"}}
        xmls = defaultdict(list)
        for path in inventory:
            if path.startswith(f"{VOC_ROOT}/{xml_folder}/") and path.endswith(".xml"):
                xmls[Path(path).stem].append(path)
        paired_xmls = set()
        stems = Counter(Path(path).stem.casefold() for path in images)
        if not images:
            raise ValueError(f"No SOHAS {split} images in pinned Git inventory.")
        for image_path, image_blob in sorted(images.items()):
            image = Path(image_path)
            xml_candidates = xmls.get(image.stem, [])
            paired_xmls.update(xml_candidates)
            row = {
                "image_path": image_path, "image_git_blob": image_blob,
                "original_split": split, "xml_path": None, "xml_sha256": None,
                "xml_git_blob": None, "yolo_path": None, "yolo_sha256": None,
                "image_present": (source_root / image_path).is_file(),
                "group_status": "unverified", "group_id": None,
                "coordinate_convention": convention, "training_approved": False,
                "human_review_status": "pending", "reviewer": "",
                "errors": [], "candidate_yolo_lines": [], "objects": [],
                "knife_count": None, "yolo_knife_count": None,
            }
            if len(xml_candidates) != 1 or stems[image.stem.casefold()] != 1:
                row["errors"].append("Missing or ambiguous split-local image/XML pairing.")
                issue("image_xml_pairing", image_path, row["errors"][-1])
            else:
                xml_path = xml_candidates[0]
                row["xml_path"] = xml_path
                row["xml_git_blob"] = inventory[xml_path]
                try:
                    data = _source_bytes(source_root, xml_path, inventory[xml_path])
                    row["xml_sha256"] = hashlib.sha256(data).hexdigest()
                    row.update(parse_sohas_voc(data, image_name=image.name, convention=convention))
                    if row["filename_case_difference"]:
                        issue("filename_case_difference", xml_path,
                              "XML filename differs only by case from uniquely paired image; raw spelling preserved.", "warning")
                    for error in row["errors"]:
                        issue("voc_annotation_error", xml_path, error)
                except (OSError, ValueError) as exc:
                    row["errors"].append(str(exc))
                    issue("voc_read_error", xml_path, str(exc))
            yolo_path = f"{YOLO_ROOT}/obj_train_data/labels/{split}/{image.stem}.txt"
            row["yolo_path"] = yolo_path
            try:
                yolo_data = _source_bytes(source_root, yolo_path, inventory[yolo_path])
                row["yolo_sha256"] = hashlib.sha256(yolo_data).hexdigest()
                parsed = parse_yolo_label(source_root / yolo_path, source_dataset="sohas-yolo",
                                          path_reference=yolo_path, class_map={key: key for key in RAW_NAMES})
                issues.extend(parsed.issues)
                if not parsed.issues:
                    row["yolo_knife_count"] = sum(a.raw_class_id == 2 for a in parsed.annotations)
                else:
                    row["errors"].append("Upstream YOLO annotation has structural errors.")
            except (KeyError, OSError, ValueError) as exc:
                row["errors"].append("Upstream YOLO comparison unavailable.")
                issue("yolo_read_error", yolo_path, str(exc))
            if row["knife_count"] is not None and row["yolo_knife_count"] is not None and row["knife_count"] != row["yolo_knife_count"]:
                issue("knife_count_mismatch", image_path,
                      f"VOC={row['knife_count']}, YOLO={row['yolo_knife_count']}; use all VOC knife boxes for review.", "warning")
            if row["errors"]:
                row["candidate_yolo_lines"] = []
            row["candidate_role"] = ("hold_invalid" if row["errors"] else
                                     "knife_positive_candidate" if row["knife_count"] else "negative_unverified")
            row["conversion_status"] = ("hold_invalid" if row["errors"] else
                                         "coordinate_unresolved" if convention == "unknown" else "proposal_only")
            rows.append(row)
        for paths in xmls.values():
            for path in paths:
                if path not in paired_xmls:
                    issue("orphan_xml", path, "No split-local image in pinned Git inventory; excluded.", "warning")

    strata = defaultdict(list)
    for row in rows:
        mismatch = row["knife_count"] != row["yolo_knife_count"]
        key = f"{row['original_split']}|{row['candidate_role']}|multi={bool((row['knife_count'] or 0) > 1)}|count_mismatch={mismatch}"
        strata[key].append(row)
    ordered = {key: sorted(values, key=lambda row: hashlib.sha256(
        f"{seed}|{row['image_path']}".encode()).hexdigest()) for key, values in sorted(strata.items())}
    selected = []
    for index in range(max(map(len, ordered.values()))):
        for values in ordered.values():
            if index < len(values) and len(selected) < sample_count:
                selected.append(values[index])
        if len(selected) >= sample_count:
            break
    selected_paths = {row["image_path"] for row in selected}
    summary = {
        "schema_version": 1, "source_url": SOURCE_URL, "upstream_commit": UPSTREAM_COMMIT,
        "coordinate_convention": convention, "coordinate_evidence": coordinate_evidence,
        "raw_class_names": RAW_NAMES, "knife_map": {"raw_name": "knife", "raw_id": 2, "canonical_id": 1, "model_local_id": 0},
        "images": len(rows), "images_present": sum(row["image_present"] for row in rows),
        "voc_knife_objects": sum(row["knife_count"] or 0 for row in rows),
        "yolo_knife_objects": sum(row["yolo_knife_count"] or 0 for row in rows),
        "roles": dict(Counter(row["candidate_role"] for row in rows)),
        "issue_counts": dict(Counter(item.code for item in issues)),
        "error_count": sum(item.severity == "error" for item in issues),
        "training_approved": False, "image_decode_verified": False,
        "rights_status": "unresolved_README_CC_BY_SA_4_vs_License_CC_BY_4",
        "grouping_status": "unverified", "human_review_status": "pending",
        "sample_seed": seed, "sample_count": len(selected),
        "sample_strata": {key: {"population": len(values), "selected": sum(
            row["image_path"] in selected_paths for row in values)} for key, values in ordered.items()},
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, values in (("voc-candidates.jsonl", rows), ("issues.jsonl", [item.to_dict() for item in issues])):
        (output_dir / name).write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in values), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["image_path", "original_split", "candidate_role", "knife_count", "yolo_knife_count",
              "size_bucket", "image_present", "coordinate_convention", "group_id", "domain", "label_quality",
              "negative_knife_absence", "bbox_completeness", "coordinate_verified", "rights_verified",
              "near_duplicate_group", "exclude", "reviewer", "notes"]
    for name, review_rows in (("review-queue.csv", rows), ("review-sample.csv", selected)):
        with (output_dir / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in review_rows:
                review = {key: row.get(key, "") for key in fields}
                boxes = [obj["candidate_yolo_bbox"] for obj in row["objects"] if "candidate_yolo_bbox" in obj]
                review["size_bucket"] = size_bucket(min(box[2] * box[3] for box in boxes)) if boxes else "unknown"
                review["notes"] = "; ".join(row["errors"])
                writer.writerow(review)
    return summary
