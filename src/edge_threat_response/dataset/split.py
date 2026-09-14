from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .audit import read_manifest
from .models import ManifestRecord


def parse_ratios(value: str) -> dict[str, float]:
    ratios: dict[str, float] = {}
    for item in value.split(","):
        if "=" not in item:
            raise ValueError("Ratios must use split=value entries separated by commas.")
        name, raw_ratio = item.split("=", 1)
        name = name.strip()
        if not name or name in ratios:
            raise ValueError("Split names must be non-empty and unique.")
        try:
            ratio = float(raw_ratio)
        except ValueError as exc:
            raise ValueError(f"Ratio for {name!r} is not numeric.") from exc
        if not math.isfinite(ratio) or ratio <= 0:
            raise ValueError(f"Ratio for {name!r} must be positive and finite.")
        ratios[name] = ratio
    if len(ratios) < 2:
        raise ValueError("At least two target splits are required.")
    total = sum(ratios.values())
    if not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"Split ratios must sum to 1.0, got {total}.")
    return ratios


def plan_group_split(
    records: tuple[ManifestRecord, ...] | list[ManifestRecord],
    *,
    ratios: dict[str, float],
    seed: int,
) -> tuple[dict[str, object], tuple[ManifestRecord, ...]]:
    _validate_ratios(ratios)
    eligible = [
        record for record in records if record.annotation_status in {"valid", "empty"}
    ]
    excluded = [
        record for record in records if record.annotation_status not in {"valid", "empty"}
    ]

    groups: dict[str, list[ManifestRecord]] = defaultdict(list)
    for record in eligible:
        groups[record.group_key].append(record)

    parent = {group_key: group_key for group_key in groups}

    def find(group_key: str) -> str:
        while parent[group_key] != group_key:
            parent[group_key] = parent[parent[group_key]]
            group_key = parent[group_key]
        return group_key

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        smaller, larger = sorted((left_root, right_root))
        parent[larger] = smaller

    hash_groups: dict[str, set[str]] = defaultdict(set)
    for record in eligible:
        if record.image_sha256:
            hash_groups[record.image_sha256].add(record.group_key)
    for connected_groups in hash_groups.values():
        ordered = sorted(connected_groups)
        for group_key in ordered[1:]:
            union(ordered[0], group_key)

    components: dict[str, list[ManifestRecord]] = defaultdict(list)
    component_group_keys: dict[str, set[str]] = defaultdict(set)
    for group_key, group_records in groups.items():
        root = find(group_key)
        components[root].extend(group_records)
        component_group_keys[root].add(group_key)

    ordered_components = sorted(
        components.items(),
        key=lambda item: (
            -len(item[1]),
            hashlib.sha256(f"{seed}\0{item[0]}".encode("utf-8")).hexdigest(),
            item[0],
        ),
    )
    total_images = len(eligible)
    targets = {name: ratio * total_images for name, ratio in ratios.items()}
    counts = {name: 0 for name in ratios}
    assignments: dict[str, str] = {}

    for component_key, group_records in ordered_components:
        group_size = len(group_records)
        chosen = min(
            ratios,
            key=lambda candidate: (
                _assignment_error(
                    counts,
                    targets,
                    candidate=candidate,
                    group_size=group_size,
                ),
                counts[candidate] / ratios[candidate],
                candidate,
            ),
        )
        for group_key in component_group_keys[component_key]:
            assignments[group_key] = chosen
        counts[chosen] += group_size

    planned_records = tuple(
        replace(record, planned_split=assignments.get(record.group_key))
        for record in records
    )
    planned_group_splits: dict[str, set[str]] = defaultdict(set)
    for record in planned_records:
        if record.planned_split is not None:
            planned_group_splits[record.group_key].add(record.planned_split)
    if any(len(splits) > 1 for splits in planned_group_splits.values()):
        raise AssertionError("Planner split a source group across multiple outputs.")
    planned_hash_splits: dict[str, set[str]] = defaultdict(set)
    for record in planned_records:
        if record.image_sha256 and record.planned_split is not None:
            planned_hash_splits[record.image_sha256].add(record.planned_split)
    if any(len(splits) > 1 for splits in planned_hash_splits.values()):
        raise AssertionError("Planner split exact duplicate images across outputs.")

    class_presence: dict[str, Counter[int]] = {
        name: Counter() for name in ratios
    }
    for record in planned_records:
        if record.planned_split is None:
            continue
        for class_id in record.canonical_class_ids:
            class_presence[record.planned_split][class_id] += 1

    plan: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "ratios": dict(ratios),
        "eligible_images": len(eligible),
        "excluded_images": len(excluded),
        "group_count": len(groups),
        "assignment_unit_count": len(components),
        "image_counts": counts,
        "target_image_counts": targets,
        "class_presence_images": {
            split: {str(key): value for key, value in sorted(counter.items())}
            for split, counter in class_presence.items()
        },
        "assignments": dict(sorted(assignments.items())),
    }
    return plan, planned_records


def write_split_outputs(
    plan: dict[str, object],
    records: tuple[ManifestRecord, ...],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "split-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output_dir / "planned-manifest.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as stream:
        for record in records:
            stream.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True))
            stream.write("\n")


def plan_manifest_file(
    manifest_path: Path,
    *,
    ratios: dict[str, float],
    seed: int,
    output_dir: Path,
) -> dict[str, object]:
    records = read_manifest(manifest_path)
    plan, planned_records = plan_group_split(records, ratios=ratios, seed=seed)
    plan["input_manifest"] = str(manifest_path)
    write_split_outputs(plan, planned_records, output_dir)
    return plan


def _validate_ratios(ratios: dict[str, float]) -> None:
    if len(ratios) < 2:
        raise ValueError("At least two target splits are required.")
    if any(not name or not math.isfinite(value) or value <= 0 for name, value in ratios.items()):
        raise ValueError("Split names and ratios must be positive and finite.")
    total = sum(ratios.values())
    if not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError(f"Split ratios must sum to 1.0, got {total}.")


def _assignment_error(
    counts: dict[str, int],
    targets: dict[str, float],
    *,
    candidate: str,
    group_size: int,
) -> float:
    return sum(
        (
            counts[name]
            + (group_size if name == candidate else 0)
            - targets[name]
        )
        ** 2
        for name in counts
    )
