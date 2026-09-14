from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RegistryError(ValueError):
    """Raised when a dataset registry is incomplete or inconsistent."""


@dataclass(frozen=True)
class SplitConfig:
    images: str
    labels: str


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    root: Path
    root_reference: str
    source_url: str | None
    declared_license: str | None
    class_map: dict[int, int]
    raw_class_names: dict[int, str]
    splits: dict[str, SplitConfig]
    group_namespace: str
    group_strategy: str
    group_pattern: str | None
    notes: tuple[str, ...]

    def derive_group(self, image_path: Path) -> str:
        if self.group_strategy == "roboflow_stem":
            return re.sub(r"\.rf\.[^.]+$", "", image_path.stem)
        if self.group_strategy == "stem":
            return image_path.stem
        if self.group_strategy == "parent":
            return image_path.parent.name
        if self.group_strategy == "regex":
            assert self.group_pattern is not None
            relative = image_path.resolve().relative_to(self.root.resolve()).as_posix()
            match = re.search(self.group_pattern, relative)
            if not match:
                raise RegistryError(
                    f"Source {self.source_id!r} group regex did not match {relative!r}."
                )
            if "group" in match.groupdict():
                return match.group("group")
            if match.lastindex:
                return match.group(1)
            return match.group(0)
        raise RegistryError(
            f"Source {self.source_id!r} has unsupported group strategy "
            f"{self.group_strategy!r}."
        )


@dataclass(frozen=True)
class DatasetRegistry:
    schema_version: int
    canonical_classes: dict[int, str]
    sources: tuple[SourceConfig, ...]
    registry_path: Path
    repo_root: Path


def load_registry(registry_path: Path, *, repo_root: Path) -> DatasetRegistry:
    registry_path = registry_path.resolve()
    repo_root = repo_root.resolve()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"Could not read registry {registry_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise RegistryError("Registry root must be a JSON object.")
    if payload.get("schema_version") != 1:
        raise RegistryError("Only dataset registry schema_version 1 is supported.")

    canonical_classes = _parse_int_string_map(
        payload.get("canonical_classes"), "canonical_classes"
    )
    if not canonical_classes:
        raise RegistryError("canonical_classes must not be empty.")

    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise RegistryError("sources must be a non-empty array.")

    sources: list[SourceConfig] = []
    seen_ids: set[str] = set()
    for index, raw_source in enumerate(raw_sources):
        if not isinstance(raw_source, dict):
            raise RegistryError(f"sources[{index}] must be an object.")
        source = _parse_source(raw_source, repo_root, canonical_classes, index)
        if source.source_id in seen_ids:
            raise RegistryError(f"Duplicate source_id {source.source_id!r}.")
        seen_ids.add(source.source_id)
        sources.append(source)

    return DatasetRegistry(
        schema_version=1,
        canonical_classes=canonical_classes,
        sources=tuple(sources),
        registry_path=registry_path,
        repo_root=repo_root,
    )


def _parse_source(
    raw: dict[str, Any],
    repo_root: Path,
    canonical_classes: dict[int, str],
    index: int,
) -> SourceConfig:
    source_id = _required_string(raw, "source_id", index)
    root_reference = _required_string(raw, "root", index)
    root_candidate = Path(root_reference)
    root = root_candidate if root_candidate.is_absolute() else repo_root / root_candidate

    class_map = _parse_int_int_map(raw.get("class_map"), f"sources[{index}].class_map")
    if not class_map:
        raise RegistryError(f"Source {source_id!r} class_map must not be empty.")
    unknown_targets = sorted(set(class_map.values()) - set(canonical_classes))
    if unknown_targets:
        raise RegistryError(
            f"Source {source_id!r} maps to unknown canonical IDs {unknown_targets}."
        )

    raw_class_names = _parse_int_string_map(
        raw.get("raw_class_names", {}), f"sources[{index}].raw_class_names"
    )
    missing_raw_names = sorted(set(class_map) - set(raw_class_names))
    if missing_raw_names:
        raise RegistryError(
            f"Source {source_id!r} is missing raw_class_names for IDs "
            f"{missing_raw_names}."
        )

    raw_splits = raw.get("splits")
    if not isinstance(raw_splits, dict) or not raw_splits:
        raise RegistryError(f"Source {source_id!r} splits must be a non-empty object.")
    splits: dict[str, SplitConfig] = {}
    for split_name, raw_split in raw_splits.items():
        if not isinstance(split_name, str) or not split_name.strip():
            raise RegistryError(f"Source {source_id!r} has an invalid split name.")
        if not isinstance(raw_split, dict):
            raise RegistryError(
                f"Source {source_id!r} split {split_name!r} must be an object."
            )
        images = raw_split.get("images")
        labels = raw_split.get("labels")
        if not isinstance(images, str) or not images.strip():
            raise RegistryError(
                f"Source {source_id!r} split {split_name!r} requires images."
            )
        if not isinstance(labels, str) or not labels.strip():
            raise RegistryError(
                f"Source {source_id!r} split {split_name!r} requires labels."
            )
        splits[split_name] = SplitConfig(images=images, labels=labels)

    group_strategy = raw.get("group_strategy", "stem")
    allowed_strategies = {"roboflow_stem", "stem", "parent", "regex"}
    if group_strategy not in allowed_strategies:
        raise RegistryError(
            f"Source {source_id!r} group_strategy must be one of "
            f"{sorted(allowed_strategies)}."
        )
    group_pattern = raw.get("group_pattern")
    if group_strategy == "regex":
        if not isinstance(group_pattern, str) or not group_pattern:
            raise RegistryError(
                f"Source {source_id!r} regex grouping requires group_pattern."
            )
        try:
            re.compile(group_pattern)
        except re.error as exc:
            raise RegistryError(
                f"Source {source_id!r} has invalid group_pattern: {exc}."
            ) from exc
    elif group_pattern is not None:
        raise RegistryError(
            f"Source {source_id!r} group_pattern is only valid with regex grouping."
        )

    notes = raw.get("notes", [])
    if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
        raise RegistryError(f"Source {source_id!r} notes must be an array of strings.")

    return SourceConfig(
        source_id=source_id,
        root=root.resolve(),
        root_reference=root_reference,
        source_url=_optional_string(raw, "source_url", index),
        declared_license=_optional_string(raw, "declared_license", index),
        class_map=class_map,
        raw_class_names=raw_class_names,
        splits=splits,
        group_namespace=str(raw.get("group_namespace") or source_id),
        group_strategy=group_strategy,
        group_pattern=group_pattern,
        notes=tuple(notes),
    )


def _required_string(raw: dict[str, Any], key: str, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError(f"sources[{index}].{key} must be a non-empty string.")
    return value


def _optional_string(raw: dict[str, Any], key: str, index: int) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RegistryError(f"sources[{index}].{key} must be a string or null.")
    return value


def _parse_int_string_map(value: Any, name: str) -> dict[int, str]:
    if not isinstance(value, dict):
        raise RegistryError(f"{name} must be an object.")
    result: dict[int, str] = {}
    for raw_key, raw_value in value.items():
        try:
            key = int(raw_key)
        except (TypeError, ValueError) as exc:
            raise RegistryError(f"{name} key {raw_key!r} is not an integer.") from exc
        if key < 0 or not isinstance(raw_value, str) or not raw_value.strip():
            raise RegistryError(f"{name}[{raw_key!r}] is invalid.")
        result[key] = raw_value
    return result


def _parse_int_int_map(value: Any, name: str) -> dict[int, int]:
    if not isinstance(value, dict):
        raise RegistryError(f"{name} must be an object.")
    result: dict[int, int] = {}
    for raw_key, raw_value in value.items():
        try:
            key = int(raw_key)
            mapped = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise RegistryError(f"{name} contains a non-integer mapping.") from exc
        if key < 0 or mapped < 0:
            raise RegistryError(f"{name} class IDs must be non-negative.")
        result[key] = mapped
    return result
