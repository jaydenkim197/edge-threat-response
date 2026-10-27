from __future__ import annotations

import hashlib
import json
import math
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from itertools import islice
from typing import Iterable

from .config import PipelineConfig
from .detector import CanonicalDetector, DetectorInference
from .domain import FrameDetections, FrameStatus
from .media import CurrentFrameSnapshot, FramePacket
from .pipeline import ThreatPipeline
from .ports import JsonlEventRecorder, MockAlarm


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
    _prepare_output(output_dir)
    inference_samples, processing_samples = [], []
    detection_count = 0
    statuses: Counter[str] = Counter()
    detection_path = output_dir / "detections.jsonl"
    latency_path = output_dir / "latency.jsonl"
    with detection_path.open("x",encoding="utf-8") as detections, latency_path.open("x",encoding="utf-8") as latencies:
        for packet in islice(frames,max_frames):
            started = time.perf_counter()
            inference = detector.infer(packet.image)
            frame = frame_from_inference(packet,inference)
            processing_ms = (time.perf_counter()-started)*1000
            _write_row(detections,_frame_to_dict(frame))
            _write_row(latencies,{"frame_index":packet.frame_index,"timestamp_s":packet.timestamp_s,
                                  "inference_ms":inference.inference_ms,"frame_processing_ms":processing_ms,
                                  "component_latencies_ms":dict(inference.component_latencies_ms)})
            inference_samples.append(inference.inference_ms)
            processing_samples.append(processing_ms)
            statuses[frame.status.value] += 1
            detection_count += len(frame.detections)
    summary = _runtime_summary(detection_path,detection_count,inference_samples,processing_samples,statuses)
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
    _prepare_output(output_dir)
    recorder = JsonlEventRecorder(output_dir / "events.jsonl")
    alarm = MockAlarm()
    snapshot = CurrentFrameSnapshot(output_dir / "snapshots")
    pipeline = ThreatPipeline(
        config, alarm=alarm, recorder=recorder, snapshot=snapshot
    )
    inference_samples, processing_samples = [], []
    detection_count = event_count = action_error_count = 0
    statuses: Counter[str] = Counter()
    detection_path = output_dir / "detections.jsonl"
    with (detection_path.open("x",encoding="utf-8") as detections,
          (output_dir/"decisions.jsonl").open("x",encoding="utf-8") as decisions,
          (output_dir/"latency.jsonl").open("x",encoding="utf-8") as latencies):
        for packet in islice(frames,max_frames):
            started = time.perf_counter()
            inference = detector.infer(packet.image)
            frame = frame_from_inference(packet,inference)
            snapshot.bind(packet)
            decision = pipeline.process(frame)
            processing_ms = (time.perf_counter()-started)*1000
            _write_row(detections,_frame_to_dict(frame))
            _write_row(decisions,decision.to_dict())
            _write_row(latencies,{"frame_index":packet.frame_index,"timestamp_s":packet.timestamp_s,
                                  "inference_ms":inference.inference_ms,"frame_processing_ms":processing_ms,
                                  "component_latencies_ms":dict(inference.component_latencies_ms)})
            inference_samples.append(inference.inference_ms)
            processing_samples.append(processing_ms)
            statuses[frame.status.value] += 1
            detection_count += len(frame.detections)
            event_count += int(decision.event is not None)
            action_error_count += len(decision.action_errors)
    summary = _runtime_summary(detection_path,detection_count,inference_samples,processing_samples,statuses)
    if provenance is not None:
        summary["provenance"] = provenance
    summary.update(
        {
            "mode": config.mode.value,
            "event_count": event_count,
            "snapshot_count": len(tuple((output_dir / "snapshots").glob("*.jpg"))),
            "alarm_signals": [signal.__dict__ for signal in alarm.signals],
            "action_error_count": action_error_count,
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
    detection_count: int,
    inference_samples: list[float],
    processing_samples: list[float],
    statuses: Counter[str],
) -> dict[str, object]:
    if not inference_samples:
        raise ValueError("Frame source yielded no frames.")
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frame_count": len(inference_samples),
        "frame_status_counts": dict(sorted(statuses.items())),
        "detection_count": detection_count,
        "inference_ms": _distribution(inference_samples),
        "frame_processing_ms": _distribution(processing_samples),
        "timing_scope": "decoded frame to inference/decision/actions; excludes decode and per-frame diagnostic log writes; not GPIO latency",
        "log_scope": "completed rows flushed per frame; no cross-file transaction or power-loss fsync guarantee",
        "detections_path": str(detection_path.resolve()),
        "detections_sha256": _sha256_file(detection_path),
    }


def _prepare_output(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("Output must be new or empty; preserve existing evidence.")
    output_dir.mkdir(parents=True,exist_ok=True)


def _write_row(handle, row) -> None:
    handle.write(json.dumps(row,ensure_ascii=False)+"\n")
    handle.flush()


def _distribution(values: list[float]) -> dict[str,float]:
    ordered = sorted(values)
    return {"mean":statistics.fmean(values),"median":statistics.median(ordered),
            "p95":ordered[math.ceil(.95*len(ordered))-1],"max":max(ordered)}


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
