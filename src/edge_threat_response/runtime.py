from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .config import PipelineConfig
from .detector import CanonicalDetector, DetectorInference
from .domain import FrameDetections, FrameStatus
from .media import CurrentFrameSnapshot, FramePacket
from .pipeline import ThreatPipeline
from .ports import JsonlEventRecorder, MockAlarm
from .replay import write_jsonl


def frame_from_inference(packet: FramePacket, result: DetectorInference) -> FrameDetections:
    return FrameDetections(
        frame_index=packet.frame_index,
        timestamp_s=packet.timestamp_s,
        source_id=packet.source_id,
        status=result.status,
        detections=result.detections if result.status is FrameStatus.VALID else (),
        error=result.error if result.status is FrameStatus.DETECTOR_ERROR else None,
    )


def run_detection_stream(
    frames: Iterable[FramePacket],
    detector: CanonicalDetector,
    *,
    output_dir: Path,
    max_frames: int | None = None,
    provenance: dict[str, object] | None = None,
) -> dict[str, object]:
    if max_frames is not None and max_frames < 1:
        raise ValueError("max_frames must be positive.")
    output_dir.mkdir(parents=True, exist_ok=True)
    detection_rows: list[dict[str, object]] = []
    latency_rows: list[dict[str, object]] = []
    statuses: Counter[str] = Counter()
    for count, packet in enumerate(frames, start=1):
        if max_frames is not None and count > max_frames:
            break
        inference = detector.infer(packet.image)
        frame = frame_from_inference(packet, inference)
        detection_rows.append(_frame_to_dict(frame))
        statuses[frame.status.value] += 1
        latency_rows.append(
            {
                "frame_index": packet.frame_index,
                "timestamp_s": packet.timestamp_s,
                "inference_ms": inference.inference_ms,
                "component_latencies_ms": dict(inference.component_latencies_ms),
            }
        )
    if not detection_rows:
        raise ValueError("Frame source yielded no frames.")
    detection_path = output_dir / "detections.jsonl"
    latency_path = output_dir / "latency.jsonl"
    write_jsonl(detection_path, detection_rows)
    write_jsonl(latency_path, latency_rows)
    summary = _runtime_summary(detection_path, detection_rows, latency_rows, statuses)
    if provenance is not None:
        summary["provenance"] = provenance
    _write_json(output_dir / "summary.json", summary)
    return summary


def run_live_pipeline(
    frames: Iterable[FramePacket],
    detector: CanonicalDetector,
    config: PipelineConfig,
    *,
    output_dir: Path,
    max_frames: int | None = None,
    provenance: dict[str, object] | None = None,
) -> dict[str, object]:
    if max_frames is not None and max_frames < 1:
        raise ValueError("max_frames must be positive.")
    output_dir.mkdir(parents=True, exist_ok=True)
    recorder = JsonlEventRecorder(output_dir / "events.jsonl")
    alarm = MockAlarm()
    snapshot = CurrentFrameSnapshot(output_dir / "snapshots")
    pipeline = ThreatPipeline(
        config, alarm=alarm, recorder=recorder, snapshot=snapshot
    )
    detection_rows: list[dict[str, object]] = []
    decision_rows: list[dict[str, object]] = []
    latency_rows: list[dict[str, object]] = []
    statuses: Counter[str] = Counter()
    for count, packet in enumerate(frames, start=1):
        if max_frames is not None and count > max_frames:
            break
        inference = detector.infer(packet.image)
        frame = frame_from_inference(packet, inference)
        snapshot.bind(packet)
        decision = pipeline.process(frame)
        detection_rows.append(_frame_to_dict(frame))
        decision_rows.append(decision.to_dict())
        statuses[frame.status.value] += 1
        latency_rows.append(
            {
                "frame_index": packet.frame_index,
                "timestamp_s": packet.timestamp_s,
                "inference_ms": inference.inference_ms,
                "component_latencies_ms": dict(inference.component_latencies_ms),
            }
        )
    if not detection_rows:
        raise ValueError("Frame source yielded no frames.")
    detection_path = output_dir / "detections.jsonl"
    write_jsonl(detection_path, detection_rows)
    write_jsonl(output_dir / "decisions.jsonl", decision_rows)
    write_jsonl(output_dir / "latency.jsonl", latency_rows)
    summary = _runtime_summary(detection_path, detection_rows, latency_rows, statuses)
    if provenance is not None:
        summary["provenance"] = provenance
    summary.update(
        {
            "mode": config.mode.value,
            "event_count": sum(row["event_id"] is not None for row in decision_rows),
            "snapshot_count": len(tuple((output_dir / "snapshots").glob("*.jpg"))),
            "alarm_signals": [signal.__dict__ for signal in alarm.signals],
            "action_error_count": sum(len(row["action_errors"]) for row in decision_rows),
        }
    )
    _write_json(output_dir / "summary.json", summary)
    return summary


def _frame_to_dict(frame: FrameDetections) -> dict[str, object]:
    return {
        "frame_index": frame.frame_index,
        "timestamp_s": frame.timestamp_s,
        "source_id": frame.source_id,
        "status": frame.status.value,
        "detections": [item.to_dict() for item in frame.detections],
        "error": frame.error,
    }


def _runtime_summary(
    detection_path: Path,
    detection_rows: list[dict[str, object]],
    latency_rows: list[dict[str, object]],
    statuses: Counter[str],
) -> dict[str, object]:
    latencies = [float(row["inference_ms"]) for row in latency_rows]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frame_count": len(detection_rows),
        "frame_status_counts": dict(sorted(statuses.items())),
        "detection_count": sum(len(row["detections"]) for row in detection_rows),
        "inference_ms": {
            "mean": statistics.fmean(latencies),
            "median": statistics.median(latencies),
            "max": max(latencies),
        },
        "detections_path": str(detection_path.resolve()),
        "detections_sha256": _sha256_file(detection_path),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
