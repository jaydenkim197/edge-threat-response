from __future__ import annotations

import math
from pathlib import Path

from .models import Annotation, LabelParseResult, ValidationIssue


_BOUNDARY_TOLERANCE = 1e-9


def parse_yolo_label(
    label_path: Path,
    *,
    source_dataset: str,
    path_reference: str,
    class_map: dict[int, int],
) -> LabelParseResult:
    annotations: list[Annotation] = []
    issues: list[ValidationIssue] = []

    try:
        lines = label_path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        return LabelParseResult(
            annotations=(),
            issues=(
                ValidationIssue(
                    severity="error",
                    code="label_read_error",
                    message=f"Could not read label file: {exc}",
                    source_dataset=source_dataset,
                    path=path_reference,
                ),
            ),
        )

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        tokens = line.split()
        try:
            raw_class_id = int(tokens[0])
        except (ValueError, IndexError):
            issues.append(
                _issue(
                    "invalid_class_id",
                    "Class ID must be an integer.",
                    source_dataset,
                    path_reference,
                    line_number,
                )
            )
            continue

        canonical_class_id = class_map.get(raw_class_id)
        if canonical_class_id is None:
            issues.append(
                _issue(
                    "unmapped_class_id",
                    f"Raw class ID {raw_class_id} has no source-specific mapping.",
                    source_dataset,
                    path_reference,
                    line_number,
                    raw_class_id=raw_class_id,
                )
            )
            continue

        try:
            coordinates = [float(value) for value in tokens[1:]]
        except ValueError:
            issues.append(
                _issue(
                    "non_numeric_coordinate",
                    "All annotation coordinates must be numeric.",
                    source_dataset,
                    path_reference,
                    line_number,
                )
            )
            continue

        if any(not math.isfinite(value) for value in coordinates):
            issues.append(
                _issue(
                    "non_finite_coordinate",
                    "Annotation coordinates must be finite.",
                    source_dataset,
                    path_reference,
                    line_number,
                )
            )
            continue

        if len(coordinates) == 4:
            line_issues = _validate_bbox(
                coordinates,
                source_dataset=source_dataset,
                path_reference=path_reference,
                line_number=line_number,
            )
            annotation_format = "bbox"
        elif len(coordinates) >= 6 and len(coordinates) % 2 == 0:
            line_issues = _validate_polygon(
                coordinates,
                source_dataset=source_dataset,
                path_reference=path_reference,
                line_number=line_number,
            )
            annotation_format = "polygon"
        else:
            line_issues = [
                _issue(
                    "invalid_annotation_shape",
                    "Expected YOLO bbox (4 coordinates) or polygon (at least 3 x/y points).",
                    source_dataset,
                    path_reference,
                    line_number,
                    coordinate_count=len(coordinates),
                )
            ]
            annotation_format = "unknown"

        issues.extend(line_issues)
        if not any(issue.severity == "error" for issue in line_issues):
            annotations.append(
                Annotation(
                    raw_class_id=raw_class_id,
                    canonical_class_id=canonical_class_id,
                    annotation_format=annotation_format,
                )
            )

    return LabelParseResult(tuple(annotations), tuple(issues))


def _validate_bbox(
    coordinates: list[float],
    *,
    source_dataset: str,
    path_reference: str,
    line_number: int,
) -> list[ValidationIssue]:
    center_x, center_y, width, height = coordinates
    issues: list[ValidationIssue] = []

    if width <= 0 or height <= 0:
        issues.append(
            _issue(
                "non_positive_bbox_size",
                "Bounding-box width and height must be greater than zero.",
                source_dataset,
                path_reference,
                line_number,
                width=width,
                height=height,
            )
        )

    left = center_x - width / 2
    right = center_x + width / 2
    top = center_y - height / 2
    bottom = center_y + height / 2
    if (
        left < -_BOUNDARY_TOLERANCE
        or top < -_BOUNDARY_TOLERANCE
        or right > 1 + _BOUNDARY_TOLERANCE
        or bottom > 1 + _BOUNDARY_TOLERANCE
    ):
        issues.append(
            _issue(
                "bbox_out_of_bounds",
                "Normalized bounding box extends outside image boundaries.",
                source_dataset,
                path_reference,
                line_number,
                left=left,
                top=top,
                right=right,
                bottom=bottom,
            )
        )
    return issues


def _validate_polygon(
    coordinates: list[float],
    *,
    source_dataset: str,
    path_reference: str,
    line_number: int,
) -> list[ValidationIssue]:
    xs = coordinates[0::2]
    ys = coordinates[1::2]
    issues: list[ValidationIssue] = []

    if any(
        value < -_BOUNDARY_TOLERANCE or value > 1 + _BOUNDARY_TOLERANCE
        for value in coordinates
    ):
        issues.append(
            _issue(
                "polygon_out_of_bounds",
                "Normalized polygon coordinate lies outside image boundaries.",
                source_dataset,
                path_reference,
                line_number,
            )
        )

    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    if width <= 0 or height <= 0:
        issues.append(
            _issue(
                "non_positive_polygon_extent",
                "Polygon must span a positive width and height.",
                source_dataset,
                path_reference,
                line_number,
                width=width,
                height=height,
            )
        )
    return issues


def _issue(
    code: str,
    message: str,
    source_dataset: str,
    path: str,
    line: int,
    **context: float | int | str,
) -> ValidationIssue:
    return ValidationIssue(
        severity="error",
        code=code,
        message=message,
        source_dataset=source_dataset,
        path=path,
        line=line,
        context=context,
    )
