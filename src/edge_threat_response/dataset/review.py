from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import ManifestRecord


@dataclass(frozen=True)
class ReviewBox:
    x_center: float
    y_center: float
    width: float
    height: float
    annotation_format: str

    @property
    def area_ratio(self) -> float:
        return self.width * self.height


@dataclass(frozen=True)
class ReviewCandidate:
    record: ManifestRecord
    image_path: Path
    label_path: Path
    boxes: tuple[ReviewBox, ...]
    size_bucket: str
    strata: tuple[str, ...]


def size_bucket(area_ratio: float) -> str:
    """Return a review-only normalized-area bucket, not a model threshold."""
    if not math.isfinite(area_ratio) or area_ratio <= 0:
        raise ValueError("area_ratio must be finite and positive.")
    if area_ratio < 0.005:
        return "tiny"
    if area_ratio < 0.02:
        return "small"
    if area_ratio < 0.10:
        return "medium"
    return "large"


def parse_review_boxes(label_path: Path) -> tuple[ReviewBox, ...]:
    boxes: list[ReviewBox] = []
    for line_number, raw_line in enumerate(
        label_path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        tokens = raw_line.strip().split()
        if not tokens:
            continue
        try:
            coordinates = [float(value) for value in tokens[1:]]
        except ValueError as exc:
            raise ValueError(f"Non-numeric label at {label_path}:{line_number}") from exc
        if len(coordinates) == 4:
            x_center, y_center, width, height = coordinates
            annotation_format = "bbox"
        elif len(coordinates) >= 6 and len(coordinates) % 2 == 0:
            xs = coordinates[0::2]
            ys = coordinates[1::2]
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            x_center = (x_min + x_max) / 2
            y_center = (y_min + y_max) / 2
            width = x_max - x_min
            height = y_max - y_min
            annotation_format = "polygon"
        else:
            raise ValueError(f"Unsupported label shape at {label_path}:{line_number}")
        if width <= 0 or height <= 0:
            raise ValueError(f"Non-positive label extent at {label_path}:{line_number}")
        boxes.append(
            ReviewBox(
                x_center=x_center,
                y_center=y_center,
                width=width,
                height=height,
                annotation_format=annotation_format,
            )
        )
    if not boxes:
        raise ValueError(f"Review candidate has no annotations: {label_path}")
    return tuple(boxes)


def build_review_candidates(
    records: Iterable[ManifestRecord], *, repo_root: Path
) -> tuple[ReviewCandidate, ...]:
    candidates: list[ReviewCandidate] = []
    seen_hashes: set[str] = set()
    for record in records:
        if record.planned_split is None or record.label_path is None:
            continue
        if record.image_sha256 and record.image_sha256 in seen_hashes:
            continue
        if record.image_sha256:
            seen_hashes.add(record.image_sha256)
        image_path = _resolve_path(repo_root, record.original_path)
        label_path = _resolve_path(repo_root, record.label_path)
        boxes = parse_review_boxes(label_path)
        smallest_bucket = size_bucket(min(box.area_ratio for box in boxes))
        formats = sorted({box.annotation_format for box in boxes})
        strata = {
            f"source={record.source_dataset}",
            f"split={record.planned_split}",
            f"size={smallest_bucket}",
        }
        strata.update(f"format={name}" for name in formats)
        candidates.append(
            ReviewCandidate(
                record=record,
                image_path=image_path,
                label_path=label_path,
                boxes=boxes,
                size_bucket=smallest_bucket,
                strata=tuple(sorted(strata)),
            )
        )
    if not candidates:
        raise ValueError("No planned, annotated records are available for review.")
    return tuple(candidates)


def select_stratified_candidates(
    candidates: Iterable[ReviewCandidate], *, per_stratum: int, seed: int
) -> tuple[ReviewCandidate, ...]:
    if per_stratum < 1:
        raise ValueError("per_stratum must be positive.")
    by_stratum: dict[str, list[ReviewCandidate]] = defaultdict(list)
    for candidate in candidates:
        for stratum in candidate.strata:
            by_stratum[stratum].append(candidate)
    selected: dict[str, ReviewCandidate] = {}
    for stratum, values in sorted(by_stratum.items()):
        ranked = sorted(
            values,
            key=lambda item: _sample_key(seed, stratum, item.record.image_id),
        )
        for candidate in ranked[:per_stratum]:
            selected[candidate.record.image_id] = candidate
    return tuple(
        sorted(
            selected.values(),
            key=lambda item: (item.record.source_dataset, item.record.image_id),
        )
    )


def generate_review_pack(
    records: Iterable[ManifestRecord],
    *,
    repo_root: Path,
    output_dir: Path,
    per_stratum: int,
    seed: int,
    contact_sheet_columns: int = 4,
    tile_width: int = 360,
    tile_height: int = 260,
) -> dict[str, object]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Output directory is not empty: {output_dir}")
    try:
        from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for visual review generation; install requirements/review.txt."
        ) from exc

    candidates = build_review_candidates(records, repo_root=repo_root)
    decode_errors: list[dict[str, str]] = []
    decoded_dimensions: dict[str, tuple[int, int]] = {}
    for candidate in candidates:
        try:
            with Image.open(candidate.image_path) as image:
                image.load()
                decoded_dimensions[candidate.record.image_id] = image.size
        except (OSError, UnidentifiedImageError) as exc:
            decode_errors.append(
                {
                    "image_id": candidate.record.image_id,
                    "path": str(candidate.image_path),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    selected = select_stratified_candidates(
        (
            candidate
            for candidate in candidates
            if candidate.record.image_id in decoded_dimensions
        ),
        per_stratum=per_stratum,
        seed=seed,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    rows = _write_review_csv(
        output_dir / "review.csv", selected, decoded_dimensions=decoded_dimensions
    )
    sheet_dir = output_dir / "contact-sheets"
    sheet_dir.mkdir(parents=True, exist_ok=True)
    pages = []
    page_size = contact_sheet_columns * 4
    font = ImageFont.load_default()
    for page_index, start in enumerate(range(0, len(selected), page_size), start=1):
        page_candidates = selected[start : start + page_size]
        sheet = Image.new(
            "RGB",
            (contact_sheet_columns * tile_width, 4 * tile_height),
            "white",
        )
        for offset, candidate in enumerate(page_candidates):
            row, column = divmod(offset, contact_sheet_columns)
            tile = _render_tile(
                candidate,
                Image=Image,
                ImageDraw=ImageDraw,
                font=font,
                tile_width=tile_width,
                tile_height=tile_height,
            )
            sheet.paste(tile, (column * tile_width, row * tile_height))
        page_path = sheet_dir / f"page-{page_index:03d}.jpg"
        sheet.save(page_path, format="JPEG", quality=90)
        pages.append(str(page_path.relative_to(output_dir)))

    decode_path = output_dir / "decode-errors.jsonl"
    with decode_path.open("w", encoding="utf-8", newline="\n") as handle:
        for error in decode_errors:
            handle.write(json.dumps(error, ensure_ascii=False) + "\n")

    summary: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "per_stratum": per_stratum,
        "candidate_count": len(candidates),
        "decoded_count": len(decoded_dimensions),
        "decode_error_count": len(decode_errors),
        "selected_count": len(selected),
        "contact_sheet_count": len(pages),
        "selected_by_source": dict(
            sorted(Counter(item.record.source_dataset for item in selected).items())
        ),
        "selected_by_split": dict(
            sorted(Counter(item.record.planned_split for item in selected).items())
        ),
        "selected_by_size_bucket": dict(
            sorted(Counter(item.size_bucket for item in selected).items())
        ),
        "selected_by_annotation_format": dict(
            sorted(
                Counter(
                    box.annotation_format
                    for item in selected
                    for box in item.boxes
                ).items()
            )
        ),
        "review_csv": "review.csv",
        "decode_errors": "decode-errors.jsonl",
        "contact_sheets": pages,
        "review_status": "pending_human_review",
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_readme(output_dir / "README.md", summary, rows)
    return summary


def _write_review_csv(
    path: Path,
    candidates: tuple[ReviewCandidate, ...],
    *,
    decoded_dimensions: dict[str, tuple[int, int]],
) -> int:
    fields = [
        "sample_no",
        "image_id",
        "source_dataset",
        "source_group",
        "planned_split",
        "original_split",
        "annotation_formats",
        "object_count",
        "smallest_bbox_area_ratio",
        "size_bucket",
        "image_width",
        "image_height",
        "image_path",
        "label_path",
        "sampling_strata",
        "domain",
        "label_quality",
        "person_cooccurrence",
        "small_or_distant_knife",
        "occlusion",
        "exclude",
        "reviewer",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index, candidate in enumerate(candidates, start=1):
            width, height = decoded_dimensions[candidate.record.image_id]
            writer.writerow(
                {
                    "sample_no": index,
                    "image_id": candidate.record.image_id,
                    "source_dataset": candidate.record.source_dataset,
                    "source_group": candidate.record.source_group,
                    "planned_split": candidate.record.planned_split,
                    "original_split": candidate.record.original_split,
                    "annotation_formats": ";".join(
                        sorted({box.annotation_format for box in candidate.boxes})
                    ),
                    "object_count": len(candidate.boxes),
                    "smallest_bbox_area_ratio": f"{min(box.area_ratio for box in candidate.boxes):.8f}",
                    "size_bucket": candidate.size_bucket,
                    "image_width": width,
                    "image_height": height,
                    "image_path": str(candidate.image_path),
                    "label_path": str(candidate.label_path),
                    "sampling_strata": ";".join(candidate.strata),
                    "domain": "",
                    "label_quality": "",
                    "person_cooccurrence": "",
                    "small_or_distant_knife": "",
                    "occlusion": "",
                    "exclude": "",
                    "reviewer": "",
                    "notes": "",
                }
            )
    return len(candidates)


def _render_tile(
    candidate: ReviewCandidate,
    *,
    Image: object,
    ImageDraw: object,
    font: object,
    tile_width: int,
    tile_height: int,
):
    caption_height = 44
    canvas = Image.new("RGB", (tile_width, tile_height), "#202124")
    with Image.open(candidate.image_path) as source:
        image = source.convert("RGB")
        image.thumbnail((tile_width, tile_height - caption_height))
    x_offset = (tile_width - image.width) // 2
    y_offset = (tile_height - caption_height - image.height) // 2
    canvas.paste(image, (x_offset, y_offset))
    draw = ImageDraw.Draw(canvas)
    for box in candidate.boxes:
        left = x_offset + (box.x_center - box.width / 2) * image.width
        top = y_offset + (box.y_center - box.height / 2) * image.height
        right = x_offset + (box.x_center + box.width / 2) * image.width
        bottom = y_offset + (box.y_center + box.height / 2) * image.height
        color = "#00ff7f" if box.annotation_format == "bbox" else "#ffd54f"
        draw.rectangle((left, top, right, bottom), outline=color, width=3)
    caption = (
        f"{candidate.record.source_dataset} | {candidate.record.planned_split} | "
        f"{candidate.size_bucket}\n{candidate.record.image_id[-18:]}"
    )
    draw.text((5, tile_height - caption_height + 4), caption, fill="white", font=font)
    return canvas


def _sample_key(seed: int, stratum: str, image_id: str) -> str:
    value = f"{seed}|{stratum}|{image_id}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _resolve_path(repo_root: Path, reference: str) -> Path:
    return (repo_root / Path(reference.replace("\\", "/"))).resolve()


def _write_readme(path: Path, summary: dict[str, object], rows: int) -> None:
    path.write_text(
        "# Dataset Visual Review Pack\n\n"
        "이 디렉터리는 원본 dataset을 수정하지 않고 생성한 로컬 검수 자료다. "
        "contact sheet에서 초록색은 bbox, 노란색은 polygon에서 계산한 bbox다.\n\n"
        f"- 전체 후보: {summary['candidate_count']}\n"
        f"- decode 성공: {summary['decoded_count']}\n"
        f"- decode 오류: {summary['decode_error_count']}\n"
        f"- 표본: {rows}\n"
        f"- 상태: `{summary['review_status']}`\n\n"
        "`review.csv`의 빈 검수 열을 팀이 채운 뒤 dataset 승인·제외 결정을 별도 문서에 남긴다. "
        "이 표본 검수는 전체 dataset의 완전한 품질 보증이 아니다.\n",
        encoding="utf-8",
        newline="\n",
    )
