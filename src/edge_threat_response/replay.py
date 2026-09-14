from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .domain import BBox, Detection, FrameDetections, FrameStatus


def load_detection_replay(path: str | Path) -> tuple[FrameDetections, ...]:
    replay_path = Path(path)
    frames: list[FrameDetections] = []
    with replay_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
                frames.append(_parse_frame(row))
            except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
                raise ValueError(
                    f"Invalid replay row at {replay_path}:{line_number}: {exc}"
                ) from exc
    if not frames:
        raise ValueError(f"Replay contains no frames: {replay_path}")
    _validate_sequence(frames)
    return tuple(frames)


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_frame(row: Any) -> FrameDetections:
    if not isinstance(row, dict):
        raise ValueError("row must be a JSON object")
    status = FrameStatus(row["status"])
    raw_detections = row.get("detections", [])
    if not isinstance(raw_detections, list):
        raise ValueError("detections must be a JSON array")
    detections = tuple(_parse_detection(item) for item in raw_detections)
    return FrameDetections(
        frame_index=row["frame_index"],
        timestamp_s=row["timestamp_s"],
        source_id=row["source_id"],
        status=status,
        detections=detections,
        error=row.get("error"),
    )


def _parse_detection(data: Any) -> Detection:
    if not isinstance(data, dict):
        raise ValueError("each detection must be a JSON object")
    coordinates = data["bbox_xyxy"]
    if not isinstance(coordinates, list) or len(coordinates) != 4:
        raise ValueError("bbox_xyxy must be a four-element JSON array")
    return Detection(
        label=data["label"],
        confidence=data["confidence"],
        bbox=BBox(*coordinates),
        detection_id=data.get("detection_id"),
    )


def _validate_sequence(frames: list[FrameDetections]) -> None:
    source_id = frames[0].source_id
    previous_index: int | None = None
    previous_timestamp: float | None = None
    for frame in frames:
        if frame.source_id != source_id:
            raise ValueError("Replay must contain exactly one source_id.")
        if previous_index is not None and frame.frame_index <= previous_index:
            raise ValueError("Replay frame_index values must increase strictly.")
        if previous_timestamp is not None and frame.timestamp_s < previous_timestamp:
            raise ValueError("Replay timestamp_s values must not decrease.")
        previous_index = frame.frame_index
        previous_timestamp = frame.timestamp_s
