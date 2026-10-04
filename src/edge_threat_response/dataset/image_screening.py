"""Read-only image integrity and heuristic similarity screening, never admission."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .sohas import _inventory, _source_bytes, parse_sohas_voc
from ..training import _git_commit, _sha256_file, _write_json
from ..replay import write_jsonl


def image_signature(path: Path, *, expected_sha256: str | None = None) -> dict:
    from PIL import Image, ImageStat

    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and digest != expected_sha256:
        raise ValueError("Image bytes changed after audit")
    with Image.open(io.BytesIO(raw)) as image:
        image.load()
        width, height = image.size
        # Do not EXIF-transpose: annotations refer to the stored pixel matrix.
        gray = image.convert("L")
        thumb = gray.resize((9, 8), Image.Resampling.LANCZOS)
        pixels = thumb.tobytes()
        bits = 0
        for y in range(8):
            for x in range(8):
                bits = (bits << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
        return {"image_sha256": digest, "image_bytes": len(raw), "width": width,
                "height": height, "dhash64": f"{bits:016x}",
                "low_information": ImageStat.Stat(thumb).stddev[0] < 5,
                "exif_orientation": image.getexif().get(274, 1)}


def similarity_pairs(records: list[dict], distance: int = 4) -> list[dict]:
    if type(distance) is not int or not 0 <= distance <= 8:
        raise ValueError("Screening Hamming distance must be an integer from 0 to 8")
    pairs = []
    for index, left in enumerate(records):
        a = int(left["dhash64"], 16)
        for right in records[index + 1:]:
            exact = left["image_sha256"] == right["image_sha256"]
            difference = (a ^ int(right["dhash64"], 16)).bit_count()
            ratio = (left["width"] / left["height"]) / (right["width"] / right["height"])
            if exact or (difference <= distance and 0.9 <= ratio <= 1.1
                         and not left["low_information"] and not right["low_information"]):
                pairs.append({"left": left["record_id"], "right": right["record_id"],
                              "kind": "exact" if exact else "visual_similarity_candidate",
                              "hamming_distance": difference,
                              "cross_source": left["dataset_id"] != right["dataset_id"],
                              "cross_original_split": left["original_split"] != right["original_split"],
                              "group_confirmed": False})
    return pairs


def screen_images(manifest: Path, output: Path, *, source_root: Path | None = None,
                  distance: int = 4) -> dict:
    similarity_pairs([], distance)  # Validate before decoding the source.
    if output.exists():
        raise ValueError("Use a new screening output directory")
    raw_manifest = manifest.read_bytes()
    rows = [json.loads(line) for line in raw_manifest.decode("utf-8-sig").splitlines() if line.strip()]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Input needs nonempty manifest objects")
    output = output.resolve()
    source_root = source_root.resolve() if source_root else None
    inventory = _inventory(source_root) if source_root else None
    if output.is_relative_to(manifest.parent.resolve()) or (source_root and
            (output.is_relative_to(source_root) or source_root.is_relative_to(output))):
        raise ValueError("Output must be outside the input manifest/source tree")
    records, issues, identities = [], [], set()
    conventions = Counter()
    for row in rows:
        record_id = row["image_path"] if source_root else row["record_id"]
        if not isinstance(record_id, str) or not record_id or record_id in identities:
            raise ValueError("Duplicate or invalid screening record ID")
        identities.add(record_id)
        image = (source_root / row["image_path"]).resolve() if source_root else Path(row["image_file"]).resolve()
        if output.is_relative_to(image.parent):
            raise ValueError("Output cannot be inside an input image directory")
        if source_root and (not image.is_relative_to(source_root) or inventory.get(row["image_path"]) != row["image_git_blob"]
                            or inventory.get(row.get("xml_path")) != row.get("xml_git_blob")):
            raise ValueError("Manifest image identity differs from pinned source")
        try:
            if source_root:
                image_data = _source_bytes(source_root, row["image_path"], row["image_git_blob"])
                xml_data = _source_bytes(source_root, row["xml_path"], row["xml_git_blob"])
                if hashlib.sha256(xml_data).hexdigest() != row["xml_sha256"]:
                    raise ValueError("XML bytes changed after audit")
                annotation = parse_sohas_voc(xml_data, image_name=image.name)
                if annotation["errors"]:
                    raise ValueError("Source annotation has structural errors")
                expected = hashlib.sha256(image_data).hexdigest()
                # Check compatibility, not a vote/automatic choice of convention.
                for convention in ("pixel-edges", "voc-1based-inclusive"):
                    compatible = not parse_sohas_voc(xml_data, image_name=image.name, convention=convention)["errors"]
                    conventions[f"{convention}:{'compatible' if compatible else 'incompatible'}"] += 1
            else:
                annotation, expected = row, row["image_sha256"]
            signature = image_signature(image, expected_sha256=expected)
            if (signature["width"], signature["height"]) != (annotation["width"], annotation["height"]):
                raise ValueError("Decoded image/annotation dimension mismatch")
            records.append({"record_id": record_id, "dataset_id": "sohas" if source_root else row["dataset_id"],
                            "original_split": row.get("original_split", "unknown"), **signature,
                            "training_approved": False, "group_confirmed": False})
        except (OSError, ValueError, KeyError) as exc:
            issues.append({"record_id": record_id, "reason": str(exc), "training_approved": False})
    if manifest.read_bytes() != raw_manifest:
        raise ValueError("Input manifest changed while screening")
    pairs = similarity_pairs(records, distance)
    hashes = defaultdict(list)
    for row in records:
        hashes[row["image_sha256"]].append(row["record_id"])
    summary = {"schema_version": 1, "status": "screened_not_approved", "git_commit": _git_commit(),
               "finished_at": datetime.now(timezone.utc).isoformat(), "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
               "expected_images": len(rows), "decoded_verified": len(records), "errors": len(issues),
               "image_bytes": sum(row["image_bytes"] for row in records),
               "exact_duplicate_groups": sum(len(ids) > 1 for ids in hashes.values()),
               "pair_counts": dict(Counter(row["kind"] for row in pairs)),
               "cross_source_pairs": sum(row["cross_source"] for row in pairs),
               "cross_original_split_pairs": sum(row["cross_original_split"] for row in pairs),
               "coordinate_compatibility": dict(conventions), "hamming_distance": distance,
               "low_information_images": sum(row["low_information"] for row in records),
               "nondefault_exif_orientation": sum(row["exif_orientation"] != 1 for row in records),
               "training_approved": False, "human_verdicts_written": 0,
               "limits": ["dHash is heuristic, not confirmed duplication or session identity",
                          "coordinate compatibility does not establish the original convention",
                          "no crop/flip similarity guarantee; no automatic exclusion or split",
                          "low-information near pairs skipped; exact pairs still included"]}
    output.mkdir(parents=True)
    write_jsonl(output / "image-integrity.jsonl", records)
    write_jsonl(output / "issues.jsonl", issues)
    write_jsonl(output / "similarity-pairs.jsonl", pairs)
    _write_json(output / "summary.json", summary)
    return summary


def compare_integrity(files: list[Path], output: Path, distance: int = 4) -> dict:
    """Compose previously verified screening outputs, without redecoding images."""
    similarity_pairs([], distance)
    if output.exists() or not files or len({path.resolve() for path in files}) != len(files):
        raise ValueError("Use unique integrity inputs and a fresh comparison output")
    if any(output.resolve().is_relative_to(path.parent.resolve()) for path in files):
        raise ValueError("Comparison output cannot be inside an input screening directory")
    records, previous_sources, aliases, identities = [], set(), 0, set()
    input_hashes = {str(path.resolve()): _sha256_file(path) for path in files}
    for path in files:
        current = set()
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if (not isinstance(row, dict) or row.get("training_approved") is not False
                    or any(not isinstance(row.get(k), str) or not row[k] for k in ("record_id", "dataset_id", "original_split"))
                    or any(type(row.get(k)) is not int or row[k] <= 0 for k in ("width", "height"))
                    or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("image_sha256", "")))
                    or not re.fullmatch(r"[a-f0-9]{16}", str(row.get("dhash64", "")))
                    or type(row.get("low_information")) is not bool):
                raise ValueError("Input is not an unapproved image integrity record")
            key = row["dataset_id"], row["image_sha256"]
            current.add(key)
            if key in previous_sources:
                aliases += 1  # Review copy already represented by the full source input.
                continue
            identity = row["dataset_id"], row["record_id"]
            if identity in identities:
                raise ValueError("Duplicate integrity record identity")
            identities.add(identity)
            records.append(row)
        # Keep distinct duplicate files inside the first source input; only skip aliases in later inputs.
        previous_sources.update(current)
    if not records or input_hashes != {str(path.resolve()): _sha256_file(path) for path in files}:
        raise ValueError("Empty or changed integrity inputs")
    pairs = similarity_pairs(records, distance)
    summary = {"schema_version": 1, "status": "screened_not_approved", "git_commit": _git_commit(),
               "finished_at": datetime.now(timezone.utc).isoformat(), "integrity_input_sha256": input_hashes,
               "images": len(records), "source_counts": dict(Counter(row["dataset_id"] for row in records)),
               "shared_source_hash_aliases_skipped": aliases, "hamming_distance": distance,
               "pair_counts": dict(Counter(row["kind"] for row in pairs)),
               "cross_source_pairs": sum(row["cross_source"] for row in pairs),
               "cross_original_split_pairs": sum(row["cross_original_split"] for row in pairs),
               "training_approved": False, "limits": ["cached screening signatures, not a fresh raw image verification",
                                                       "same-source review copies skipped across inputs only",
                                                       "similarity is not confirmed duplicate/session; no split/exclusion"]}
    output.mkdir(parents=True)
    write_jsonl(output / "similarity-pairs.jsonl", pairs)
    _write_json(output / "summary.json", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--manifest", type=Path)
    inputs.add_argument("--integrity", nargs="+", type=Path, help="Compare cached image-integrity.jsonl outputs")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-root", type=Path, help="Pinned SOHAS VOC source; omit for review-linked manifest")
    parser.add_argument("--hamming-distance", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        if args.integrity:
            if args.source_root:
                raise ValueError("--source-root applies only to a SOHAS manifest")
            result = compare_integrity(args.integrity, args.output_dir, args.hamming_distance)
        else:
            result = screen_images(args.manifest, args.output_dir, source_root=args.source_root, distance=args.hamming_distance)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result))
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
