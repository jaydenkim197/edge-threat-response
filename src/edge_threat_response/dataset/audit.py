from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .labels import parse_yolo_label
from .models import AuditResult, ManifestRecord, ValidationIssue
from .registry import DatasetRegistry, RegistryError, SourceConfig


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def audit_registry(
    registry: DatasetRegistry,
    *,
    hash_images: bool = True,
) -> AuditResult:
    records: list[ManifestRecord] = []
    issues: list[ValidationIssue] = []

    for source in registry.sources:
        source_records, source_issues = _audit_source(
            source,
            repo_root=registry.repo_root,
            hash_images=hash_images,
        )
        records.extend(source_records)
        issues.extend(source_issues)

    records.sort(key=lambda record: (record.source_dataset, record.original_path))
    issues.extend(_find_group_leakage(records))
    issues.extend(_find_exact_duplicates(records))
    issues.sort(
        key=lambda issue: (
            issue.severity,
            issue.code,
            issue.source_dataset or "",
            issue.path or "",
            issue.line or 0,
        )
    )

    summary = _build_summary(registry, records, issues, hash_images=hash_images)
    return AuditResult(tuple(records), tuple(issues), summary)


def write_audit_outputs(result: AuditResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        output_dir / "manifest.jsonl",
        (record.to_dict() for record in result.records),
    )
    _write_jsonl(
        output_dir / "issues.jsonl",
        (issue.to_dict() for issue in result.issues),
    )
    (output_dir / "summary.json").write_text(
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(
        render_markdown_report(result),
        encoding="utf-8",
    )


def render_markdown_report(result: AuditResult, *, examples_per_issue: int = 5) -> str:
    summary = result.summary
    totals = summary["totals"]
    lines = [
        "# Dataset Audit Report",
        "",
        f"Generated: `{summary['generated_at']}`",
        f"Registry: `{summary['registry']}`",
        f"Image hashing: `{summary['hash_images']}`",
        "",
        "## Totals",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Images | {totals['images']} |",
        f"| Objects parsed | {totals['objects']} |",
        f"| Unique groups | {totals['unique_groups']} |",
        f"| Empty labels | {totals['annotation_status'].get('empty', 0)} |",
        f"| Invalid/missing labels | {totals['invalid_or_missing_labels']} |",
        f"| Exact duplicate groups | {totals['exact_duplicate_groups']} |",
        f"| Groups crossing original splits | {totals['cross_split_group_count']} |",
        f"| Exact hashes crossing original splits | {totals['cross_split_duplicate_hash_count']} |",
        "",
        "## Sources",
        "",
        "| Source | Images | Objects | Empty | Invalid/missing |",
        "|---|---:|---:|---:|---:|",
    ]
    for source_id, source in sorted(summary["sources"].items()):
        status = source["annotation_status"]
        invalid = status.get("invalid", 0) + status.get("missing_label", 0)
        lines.append(
            f"| {source_id} | {source['images']} | {source['objects']} | "
            f"{status.get('empty', 0)} | {invalid} |"
        )

    lines.extend(["", "## Annotation formats", ""])
    if totals["annotation_formats"]:
        for name, count in sorted(totals["annotation_formats"].items()):
            lines.append(f"- `{name}`: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Canonical class distribution", ""])
    if totals["canonical_class_objects"]:
        for class_id, count in sorted(
            totals["canonical_class_objects"].items(), key=lambda item: int(item[0])
        ):
            name = summary["canonical_classes"].get(class_id, "unknown")
            lines.append(f"- `{class_id}` (`{name}`): {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Issues", ""])
    if totals["issue_counts"]:
        lines.extend(
            ["| Code | Count |", "|---|---:|"]
            + [
                f"| `{code}` | {count} |"
                for code, count in sorted(totals["issue_counts"].items())
            ]
        )
    else:
        lines.append("No issues detected.")

    if result.issues:
        lines.extend(["", "### Issue examples", ""])
        issues_by_code: dict[str, list[ValidationIssue]] = defaultdict(list)
        for issue in result.issues:
            issues_by_code[issue.code].append(issue)
        for code, code_issues in sorted(issues_by_code.items()):
            lines.append(f"#### `{code}`")
            lines.append("")
            for issue in code_issues[:examples_per_issue]:
                location = issue.path or str(
                    issue.context.get("group_key")
                    or issue.context.get("sha256")
                    or "dataset"
                )
                if issue.line is not None:
                    location += f":{issue.line}"
                lines.append(
                    f"- **{issue.severity.upper()}** `{location}` — {issue.message}"
                )
            lines.append("")

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This report validates file, label, duplicate, and split-group structure. "
            "It does not verify visual annotation quality, dataset suitability, upstream "
            "availability, licensing of each image, or model performance.",
            "",
        ]
    )
    return "\n".join(lines)


def read_manifest(path: Path) -> tuple[ManifestRecord, ...]:
    records: list[ManifestRecord] = []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Could not read manifest {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            records.append(
                ManifestRecord(
                    schema_version=int(payload["schema_version"]),
                    image_id=str(payload["image_id"]),
                    source_dataset=str(payload["source_dataset"]),
                    source_url=payload.get("source_url"),
                    declared_license=payload.get("declared_license"),
                    original_path=str(payload["original_path"]),
                    label_path=payload.get("label_path"),
                    source_group=str(payload["source_group"]),
                    group_namespace=str(payload["group_namespace"]),
                    original_split=str(payload["original_split"]),
                    planned_split=payload.get("planned_split"),
                    image_sha256=payload.get("image_sha256"),
                    label_sha256=payload.get("label_sha256"),
                    annotation_status=str(payload["annotation_status"]),
                    annotation_formats=tuple(payload.get("annotation_formats", [])),
                    annotation_format_counts=tuple(
                        (str(item[0]), int(item[1]))
                        for item in payload.get("annotation_format_counts", [])
                    ),
                    raw_class_ids=tuple(int(v) for v in payload.get("raw_class_ids", [])),
                    raw_class_counts=tuple(
                        (int(item[0]), int(item[1]))
                        for item in payload.get("raw_class_counts", [])
                    ),
                    canonical_class_ids=tuple(
                        int(v) for v in payload.get("canonical_class_ids", [])
                    ),
                    canonical_class_counts=tuple(
                        (int(item[0]), int(item[1]))
                        for item in payload.get("canonical_class_counts", [])
                    ),
                    object_count=int(payload.get("object_count", 0)),
                    notes=tuple(payload.get("notes", [])),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Invalid manifest record at {path}:{line_number}: {exc}"
            ) from exc
    return tuple(records)


def _audit_source(
    source: SourceConfig,
    *,
    repo_root: Path,
    hash_images: bool,
) -> tuple[list[ManifestRecord], list[ValidationIssue]]:
    records: list[ManifestRecord] = []
    issues: list[ValidationIssue] = []

    if not source.root.is_dir():
        return records, [
            ValidationIssue(
                severity="error",
                code="source_root_missing",
                message="Dataset source root does not exist or is not a directory.",
                source_dataset=source.source_id,
                path=_path_reference(source.root, repo_root),
            )
        ]

    for split_name, split in sorted(source.splits.items()):
        image_dir = source.root / split.images
        label_dir = source.root / split.labels
        if not image_dir.is_dir():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="image_directory_missing",
                    message=f"Image directory for split {split_name!r} is missing.",
                    source_dataset=source.source_id,
                    path=_path_reference(image_dir, repo_root),
                )
            )
            continue
        if not label_dir.is_dir():
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="label_directory_missing",
                    message=f"Label directory for split {split_name!r} is missing.",
                    source_dataset=source.source_id,
                    path=_path_reference(label_dir, repo_root),
                )
            )

        image_files = sorted(
            (
                path
                for path in image_dir.iterdir()
                if path.is_file() and path.suffix.casefold() in _IMAGE_EXTENSIONS
            ),
            key=lambda path: path.name.casefold(),
        )
        label_files = (
            sorted(
                (
                    path
                    for path in label_dir.iterdir()
                    if path.is_file() and path.suffix.casefold() == ".txt"
                ),
                key=lambda path: path.name.casefold(),
            )
            if label_dir.is_dir()
            else []
        )
        images_by_stem = _index_by_stem(
            image_files, source=source, repo_root=repo_root, kind="image", issues=issues
        )
        labels_by_stem = _index_by_stem(
            label_files, source=source, repo_root=repo_root, kind="label", issues=issues
        )

        for stem, image_path in sorted(images_by_stem.items()):
            label_path = labels_by_stem.get(stem)
            image_reference = _path_reference(image_path, repo_root)
            label_reference = (
                _path_reference(label_path, repo_root) if label_path is not None else None
            )
            source_group = _derive_group(
                source, image_path, image_reference=image_reference, issues=issues
            )

            if label_path is None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="missing_label",
                        message="Image has no matching label file.",
                        source_dataset=source.source_id,
                        path=image_reference,
                    )
                )
                annotations = ()
                annotation_formats: tuple[str, ...] = ()
                annotation_format_counts: tuple[tuple[str, int], ...] = ()
                raw_class_ids: tuple[int, ...] = ()
                raw_class_counts: tuple[tuple[int, int], ...] = ()
                canonical_class_ids: tuple[int, ...] = ()
                canonical_class_counts: tuple[tuple[int, int], ...] = ()
                status = "missing_label"
                label_sha256 = None
            else:
                parsed = parse_yolo_label(
                    label_path,
                    source_dataset=source.source_id,
                    path_reference=label_reference or label_path.name,
                    class_map=source.class_map,
                )
                issues.extend(parsed.issues)
                annotations = parsed.annotations
                annotation_formats = tuple(
                    sorted({annotation.annotation_format for annotation in annotations})
                )
                annotation_format_counts = tuple(
                    sorted(Counter(a.annotation_format for a in annotations).items())
                )
                raw_class_ids = tuple(
                    sorted({annotation.raw_class_id for annotation in annotations})
                )
                raw_class_counts = tuple(
                    sorted(Counter(a.raw_class_id for a in annotations).items())
                )
                canonical_class_ids = tuple(
                    sorted({annotation.canonical_class_id for annotation in annotations})
                )
                canonical_class_counts = tuple(
                    sorted(Counter(a.canonical_class_id for a in annotations).items())
                )
                if any(issue.severity == "error" for issue in parsed.issues):
                    status = "invalid"
                elif not annotations:
                    status = "empty"
                else:
                    status = "valid"
                label_sha256 = _sha256_file(label_path)

            identity_basis = (
                f"{source.source_id}\0{image_path.resolve().relative_to(source.root).as_posix()}"
            )
            image_id = "sha256:" + hashlib.sha256(
                identity_basis.encode("utf-8")
            ).hexdigest()
            records.append(
                ManifestRecord(
                    schema_version=1,
                    image_id=image_id,
                    source_dataset=source.source_id,
                    source_url=source.source_url,
                    declared_license=source.declared_license,
                    original_path=image_reference,
                    label_path=label_reference,
                    source_group=source_group,
                    group_namespace=source.group_namespace,
                    original_split=split_name,
                    planned_split=None,
                    image_sha256=_sha256_file(image_path) if hash_images else None,
                    label_sha256=label_sha256,
                    annotation_status=status,
                    annotation_formats=annotation_formats,
                    annotation_format_counts=annotation_format_counts,
                    raw_class_ids=raw_class_ids,
                    raw_class_counts=raw_class_counts,
                    canonical_class_ids=canonical_class_ids,
                    canonical_class_counts=canonical_class_counts,
                    object_count=len(annotations),
                    notes=source.notes,
                )
            )

        for stem, label_path in sorted(labels_by_stem.items()):
            if stem not in images_by_stem:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="missing_image",
                        message="Label has no matching image file.",
                        source_dataset=source.source_id,
                        path=_path_reference(label_path, repo_root),
                    )
                )

    return records, issues


def _derive_group(
    source: SourceConfig,
    image_path: Path,
    *,
    image_reference: str,
    issues: list[ValidationIssue],
) -> str:
    try:
        group = source.derive_group(image_path).strip()
    except (RegistryError, ValueError) as exc:
        issues.append(
            ValidationIssue(
                severity="error",
                code="group_derivation_failed",
                message=str(exc),
                source_dataset=source.source_id,
                path=image_reference,
            )
        )
        return image_path.stem
    if not group:
        issues.append(
            ValidationIssue(
                severity="error",
                code="empty_source_group",
                message="Grouping strategy produced an empty source group.",
                source_dataset=source.source_id,
                path=image_reference,
            )
        )
        return image_path.stem
    return group


def _index_by_stem(
    paths: Iterable[Path],
    *,
    source: SourceConfig,
    repo_root: Path,
    kind: str,
    issues: list[ValidationIssue],
) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in paths:
        stem = path.stem.casefold()
        if stem in result:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code=f"duplicate_{kind}_stem",
                    message=f"Multiple {kind} files share the same case-insensitive stem.",
                    source_dataset=source.source_id,
                    path=_path_reference(path, repo_root),
                    context={"first_path": _path_reference(result[stem], repo_root)},
                )
            )
            continue
        result[stem] = path
    return result


def _find_group_leakage(records: list[ManifestRecord]) -> list[ValidationIssue]:
    grouped: dict[str, list[ManifestRecord]] = defaultdict(list)
    for record in records:
        grouped[record.group_key].append(record)

    issues: list[ValidationIssue] = []
    for group_key, group_records in sorted(grouped.items()):
        splits = sorted({record.original_split for record in group_records})
        if len(splits) <= 1:
            continue
        issues.append(
            ValidationIssue(
                severity="error",
                code="group_split_leakage",
                message="A source/session group crosses original dataset splits.",
                source_dataset=None,
                path=None,
                context={
                    "group_key": group_key,
                    "splits": splits,
                    "image_count": len(group_records),
                    "sources": sorted(
                        {record.source_dataset for record in group_records}
                    ),
                },
            )
        )
    return issues


def _find_exact_duplicates(records: list[ManifestRecord]) -> list[ValidationIssue]:
    by_hash: dict[str, list[ManifestRecord]] = defaultdict(list)
    for record in records:
        if record.image_sha256:
            by_hash[record.image_sha256].append(record)

    issues: list[ValidationIssue] = []
    for digest, duplicate_records in sorted(by_hash.items()):
        if len(duplicate_records) <= 1:
            continue
        splits = sorted({record.original_split for record in duplicate_records})
        issues.append(
            ValidationIssue(
                severity="error" if len(splits) > 1 else "warning",
                code=(
                    "duplicate_split_leakage"
                    if len(splits) > 1
                    else "exact_duplicate_image"
                ),
                message=(
                    "Identical image content crosses original dataset splits."
                    if len(splits) > 1
                    else "Identical image content appears more than once."
                ),
                source_dataset=None,
                path=None,
                context={
                    "sha256": digest,
                    "splits": splits,
                    "image_count": len(duplicate_records),
                    "paths": [record.original_path for record in duplicate_records],
                },
            )
        )
    return issues


def _build_summary(
    registry: DatasetRegistry,
    records: list[ManifestRecord],
    issues: list[ValidationIssue],
    *,
    hash_images: bool,
) -> dict[str, object]:
    status_counts = Counter(record.annotation_status for record in records)
    format_counts: Counter[str] = Counter()
    raw_class_counts: Counter[int] = Counter()
    canonical_class_counts: Counter[int] = Counter()
    for record in records:
        format_counts.update(dict(record.annotation_format_counts))
        raw_class_counts.update(dict(record.raw_class_counts))
        canonical_class_counts.update(dict(record.canonical_class_counts))

    issue_counts = Counter(issue.code for issue in issues)
    issue_severity_counts = Counter(issue.severity for issue in issues)
    group_keys = {record.group_key for record in records}
    exact_duplicate_groups = sum(
        1
        for issue in issues
        if issue.code in {"exact_duplicate_image", "duplicate_split_leakage"}
    )

    source_summaries: dict[str, object] = {}
    for source in registry.sources:
        source_records = [
            record for record in records if record.source_dataset == source.source_id
        ]
        source_summaries[source.source_id] = {
            "images": len(source_records),
            "objects": sum(record.object_count for record in source_records),
            "annotation_status": dict(
                sorted(Counter(r.annotation_status for r in source_records).items())
            ),
            "original_splits": dict(
                sorted(Counter(r.original_split for r in source_records).items())
            ),
            "unique_groups": len({r.group_key for r in source_records}),
        }

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry": _path_reference(registry.registry_path, registry.repo_root),
        "hash_images": hash_images,
        "canonical_classes": {
            str(key): value for key, value in sorted(registry.canonical_classes.items())
        },
        "totals": {
            "images": len(records),
            "objects": sum(record.object_count for record in records),
            "unique_groups": len(group_keys),
            "annotation_status": dict(sorted(status_counts.items())),
            "annotation_formats": {
                str(key): value for key, value in sorted(format_counts.items())
            },
            "raw_class_objects": {
                str(key): value for key, value in sorted(raw_class_counts.items())
            },
            "canonical_class_objects": {
                str(key): value for key, value in sorted(canonical_class_counts.items())
            },
            "invalid_or_missing_labels": status_counts.get("invalid", 0)
            + status_counts.get("missing_label", 0),
            "issue_counts": dict(sorted(issue_counts.items())),
            "issue_severity_counts": dict(sorted(issue_severity_counts.items())),
            "exact_duplicate_groups": exact_duplicate_groups,
            "cross_split_group_count": issue_counts.get("group_split_leakage", 0),
            "cross_split_duplicate_hash_count": issue_counts.get(
                "duplicate_split_leakage", 0
            ),
        },
        "sources": source_summaries,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_reference(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            stream.write("\n")
