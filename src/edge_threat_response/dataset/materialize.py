from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .labels import parse_yolo_label
from .models import ManifestRecord
from .registry import DatasetRegistry


def parse_split_limits(value: str | None) -> dict[str, int] | None:
    if value is None:
        return None
    limits: dict[str, int] = {}
    for item in value.split(","):
        if "=" not in item:
            raise ValueError("Limits must use split=count entries separated by commas.")
        name, raw_count = item.split("=", 1)
        name = name.strip()
        if not name or name in limits:
            raise ValueError("Limit split names must be non-empty and unique.")
        try:
            count = int(raw_count)
        except ValueError as exc:
            raise ValueError(f"Limit for {name!r} is not an integer.") from exc
        if count < 0:
            raise ValueError(f"Limit for {name!r} must be non-negative.")
        limits[name] = count
    return limits


def materialize_knife_yolo(
    records: tuple[ManifestRecord, ...] | list[ManifestRecord],
    *,
    registry: DatasetRegistry,
    output_dir: Path,
    source_manifest: Path | None = None,
    limits: dict[str, int] | None = None,
    link_mode: str = "hardlink",
) -> dict[str, object]:
    if link_mode not in {"hardlink", "copy"}:
        raise ValueError("link_mode must be 'hardlink' or 'copy'.")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Output directory is not empty: {output_dir}")

    knife_ids = [
        class_id
        for class_id, name in registry.canonical_classes.items()
        if name == "knife"
    ]
    if len(knife_ids) != 1:
        raise ValueError("Registry must define exactly one canonical knife class.")
    canonical_knife_id = knife_ids[0]
    sources = {source.source_id: source for source in registry.sources}

    eligible = sorted(
        (
            record
            for record in records
            if record.planned_split is not None
            and record.annotation_status in {"valid", "empty"}
        ),
        key=lambda record: (
            record.planned_split or "",
            record.source_dataset,
            record.original_path,
        ),
    )
    selected: list[ManifestRecord] = []
    split_counts: Counter[str] = Counter()
    seen_hashes: set[str] = set()
    duplicate_records_skipped = 0
    limit_records_skipped = 0
    for record in eligible:
        split = record.planned_split
        assert split is not None
        if limits is not None and split_counts[split] >= limits.get(split, 0):
            limit_records_skipped += 1
            continue
        if record.image_sha256 and record.image_sha256 in seen_hashes:
            duplicate_records_skipped += 1
            continue
        selected.append(record)
        split_counts[split] += 1
        if record.image_sha256:
            seen_hashes.add(record.image_sha256)

    if not selected:
        raise ValueError("No eligible records were selected for materialization.")

    output_dir.mkdir(parents=True, exist_ok=True)
    link_counts: Counter[str] = Counter()
    converted_formats: Counter[str] = Counter()
    object_count = 0
    output_rows: list[dict[str, object]] = []
    for record in selected:
        split = record.planned_split
        assert split is not None
        source = sources.get(record.source_dataset)
        if source is None:
            raise ValueError(
                f"Manifest references unknown source {record.source_dataset!r}."
            )
        image_source = _resolve_source_path(registry.repo_root, record.original_path)
        if record.label_path is None:
            raise ValueError(f"Selected record {record.image_id} has no label path.")
        label_source = _resolve_source_path(registry.repo_root, record.label_path)
        if not image_source.is_file() or not label_source.is_file():
            raise ValueError(f"Selected source files are missing for {record.image_id}.")
        if record.image_sha256 and _sha256_file(image_source) != record.image_sha256:
            raise ValueError(f"Image hash changed after audit for {record.image_id}.")
        if record.label_sha256 and _sha256_file(label_source) != record.label_sha256:
            raise ValueError(f"Label hash changed after audit for {record.image_id}.")
        parsed = parse_yolo_label(
            label_source,
            source_dataset=record.source_dataset,
            path_reference=record.label_path,
            class_map=source.class_map,
        )
        if any(issue.severity == "error" for issue in parsed.issues):
            raise ValueError(f"Label validation failed for {record.image_id}.")

        stem = _safe_stem(record.source_dataset, record.image_id)
        image_target = output_dir / "images" / split / f"{stem}{image_source.suffix.lower()}"
        label_target = output_dir / "labels" / split / f"{stem}.txt"
        image_target.parent.mkdir(parents=True, exist_ok=True)
        label_target.parent.mkdir(parents=True, exist_ok=True)

        actual_link_mode = _place_image(image_source, image_target, link_mode)
        link_counts[actual_link_mode] += 1
        label_text, label_objects, formats = _convert_knife_label(
            label_source,
            class_map=source.class_map,
            canonical_knife_id=canonical_knife_id,
        )
        label_target.write_text(label_text, encoding="utf-8", newline="\n")
        object_count += label_objects
        converted_formats.update(formats)
        output_rows.append(
            {
                "image_id": record.image_id,
                "source_dataset": record.source_dataset,
                "source_group": record.source_group,
                "planned_split": split,
                "source_image": record.original_path,
                "source_label": record.label_path,
                "output_image": image_target.relative_to(output_dir).as_posix(),
                "output_label": label_target.relative_to(output_dir).as_posix(),
                "image_sha256": record.image_sha256,
                "model_local_class": {"0": "knife"},
            }
        )

    split_names = [name for name, count in sorted(split_counts.items()) if count]
    data_yaml_lines = [
        f"path: {output_dir.resolve().as_posix()}",
        *[f"{name}: images/{name}" for name in split_names],
        "names:",
        "  0: knife",
        "",
    ]
    (output_dir / "data.yaml").write_text(
        "\n".join(data_yaml_lines), encoding="utf-8", newline="\n"
    )
    with (output_dir / "materialized-manifest.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        for row in output_rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    summary: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "recipe": "knife-only-yolo-detect-v1",
        "source_manifest": str(source_manifest) if source_manifest else None,
        "source_manifest_sha256": (
            _sha256_file(source_manifest) if source_manifest is not None else None
        ),
        "output_dir": str(output_dir.resolve()),
        "model_local_classes": {"0": "knife"},
        "runtime_class_mapping": {"0": canonical_knife_id},
        "source_hashes_verified": True,
        "image_counts": dict(sorted(split_counts.items())),
        "object_count": object_count,
        "input_annotation_formats": dict(sorted(converted_formats.items())),
        "link_counts": dict(sorted(link_counts.items())),
        "exact_duplicate_records_skipped": duplicate_records_skipped,
        "limit_records_skipped": limit_records_skipped,
        "limits": limits,
    }
    (output_dir / "materialization-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return summary


def _resolve_source_path(repo_root: Path, reference: str) -> Path:
    candidate = Path(reference)
    return candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve()


def _safe_stem(source_dataset: str, image_id: str) -> str:
    source = re.sub(r"[^A-Za-z0-9_.-]+", "-", source_dataset).strip("-._")
    digest = image_id.removeprefix("sha256:")[:20]
    return f"{source}-{digest}"


def _place_image(source: Path, target: Path, link_mode: str) -> str:
    if link_mode == "copy":
        shutil.copy2(source, target)
        return "copy"
    try:
        os.link(source, target)
        return "hardlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy_fallback"


def _convert_knife_label(
    path: Path,
    *,
    class_map: dict[int, int],
    canonical_knife_id: int,
) -> tuple[str, int, Counter[str]]:
    output_lines: list[str] = []
    formats: Counter[str] = Counter()
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        tokens = raw_line.split()
        if not tokens:
            continue
        try:
            raw_class_id = int(tokens[0])
            coordinates = [float(value) for value in tokens[1:]]
        except ValueError as exc:
            raise ValueError(f"Invalid label at {path}:{line_number}.") from exc
        canonical_id = class_map.get(raw_class_id)
        if canonical_id != canonical_knife_id:
            raise ValueError(
                f"Knife-only export found non-knife class at {path}:{line_number}."
            )
        if len(coordinates) == 4:
            center_x, center_y, width, height = coordinates
            formats["bbox"] += 1
        elif len(coordinates) >= 6 and len(coordinates) % 2 == 0:
            xs = coordinates[0::2]
            ys = coordinates[1::2]
            left, right = min(xs), max(xs)
            top, bottom = min(ys), max(ys)
            center_x = (left + right) / 2
            center_y = (top + bottom) / 2
            width = right - left
            height = bottom - top
            formats["polygon"] += 1
        else:
            raise ValueError(f"Invalid annotation shape at {path}:{line_number}.")
        output_lines.append(
            "0 "
            + " ".join(
                _format_coordinate(value)
                for value in (center_x, center_y, width, height)
            )
        )
    text = "\n".join(output_lines)
    if output_lines:
        text += "\n"
    return text, len(output_lines), formats


def _format_coordinate(value: float) -> str:
    return format(value, ".10g")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
