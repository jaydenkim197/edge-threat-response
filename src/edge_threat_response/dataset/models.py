from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    source_dataset: str | None = None
    path: str | None = None
    line: int | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Annotation:
    raw_class_id: int
    canonical_class_id: int
    annotation_format: str


@dataclass(frozen=True)
class LabelParseResult:
    annotations: tuple[Annotation, ...]
    issues: tuple[ValidationIssue, ...]


@dataclass(frozen=True)
class ManifestRecord:
    schema_version: int
    image_id: str
    source_dataset: str
    source_url: str | None
    declared_license: str | None
    original_path: str
    label_path: str | None
    source_group: str
    group_namespace: str
    original_split: str
    planned_split: str | None
    image_sha256: str | None
    label_sha256: str | None
    annotation_status: str
    annotation_formats: tuple[str, ...]
    annotation_format_counts: tuple[tuple[str, int], ...]
    raw_class_ids: tuple[int, ...]
    raw_class_counts: tuple[tuple[int, int], ...]
    canonical_class_ids: tuple[int, ...]
    canonical_class_counts: tuple[tuple[int, int], ...]
    object_count: int
    notes: tuple[str, ...] = ()

    @property
    def group_key(self) -> str:
        return f"{self.group_namespace}:{self.source_group}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuditResult:
    records: tuple[ManifestRecord, ...]
    issues: tuple[ValidationIssue, ...]
    summary: dict[str, Any]
