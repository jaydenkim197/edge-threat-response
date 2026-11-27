"""Measure the live 4 Hz P430 path on Orin without retaining camera frames."""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
from threading import Lock
import time

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.detect_cli import DetectorConfig, build_detector
from edge_threat_response.domain import AblationMode, FrameStatus
from edge_threat_response.jetson_memory import prepare_jetson_memory
from edge_threat_response.media import RTSPFrameSource
from edge_threat_response.pipeline import ThreatPipeline
from edge_threat_response.ports import JsonlEventRecorder, MockAlarm, SnapshotResult
from edge_threat_response.runtime import _sha256_file, frame_from_inference


SAMPLE_HZ = 4
WARMUP_SECONDS = 60
REPETITION_SECONDS = 600
REPETITIONS = 3


class TimedCapture:
    """Record the host read start for the same decode index used by RTSPFrameSource."""

    def __init__(self, capture):
        self.capture = capture
        self.next_index = 0
        self.starts = deque(maxlen=128)
        self.lock = Lock()

    def isOpened(self):
        return self.capture.isOpened()

    def read(self):
        started = time.monotonic()
        ok, image = self.capture.read()
        if ok:
            with self.lock:
                self.starts.append((self.next_index, started))
            self.next_index += 1
        return ok, image

    def start_for(self, index):
        with self.lock:
            return next((start for candidate, start in reversed(self.starts) if candidate == index), None)

    def release(self):
        self.capture.release()


class EncodeOnlySnapshot:
    """Exercise JPEG encoding on alerts without writing camera pixels to disk."""

    def __init__(self, encode):
        self.encode = encode
        self.image = None

    def capture(self, event_id, frame):
        ok, _ = self.encode(".jpg", self.image)
        return SnapshotResult("captured") if ok else SnapshotResult("failed", error="JPEG encoding failed")


@dataclass(frozen=True)
class Sample:
    valid: bool
    person_seen: bool
    event: bool
    action_errors: int


def quantile(values, probability):
    return sorted(values)[math.ceil(len(values) * probability) - 1] if values else None


def drift(values):
    """Compare the first and last thirds, plus the fitted total-window change."""
    if len(values) < 3:
        return None
    third = max(1, len(values) // 3)
    ends = statistics.median(values[-third:]) - statistics.median(values[:third])
    mid = (len(values) - 1) / 2
    slope = sum((index - mid) * value for index, value in enumerate(values))
    slope /= sum((index - mid) ** 2 for index in range(len(values)))
    return max(ends, slope * (len(values) - 1))


def run_window(stream, process, lookup_read_start, seconds, *, clock, sleep, shared_used_mib):
    """Execute at most one inference per fixed slot and never catch up in a burst."""
    period = 1 / SAMPLE_HZ
    expected = seconds * SAMPLE_HZ
    start = clock()
    latencies, queue_ages, ram = [], [], []
    by_minute = [[] for _ in range(math.ceil(seconds / 60))]
    valid = processed = people = events = errors = 0
    problem = None
    last_memory_slot = -1
    for slot in range(expected):
        tick = start + slot * period
        deadline = tick + period
        pause = tick - clock()
        if pause > 0:
            sleep(pause)
        now = clock()
        memory_slot = int(now - start)
        if memory_slot != last_memory_slot and now < start + seconds:
            ram.append(shared_used_mib())
            last_memory_slot = memory_slot
        if now >= deadline:
            continue
        try:
            packet = next(stream)
        except (RuntimeError, StopIteration):
            problem = "rtsp_stream_interrupted"
            break
        acquired = clock()
        captured = packet.captured_at_monotonic
        read_started = lookup_read_start(packet.frame_index)
        if captured is None or read_started is None or not read_started <= captured <= acquired:
            problem = "decode_timing_missing"
            break
        if acquired >= deadline or acquired - captured >= period:
            continue
        try:
            sample = process(packet)
        except ValueError:
            problem = "unexpected_frame_profile"
            break
        completed = clock()
        errors += sample.action_errors
        processed += 1
        people += int(sample.person_seen)
        events += int(sample.event)
        if sample.valid:
            latency = (completed - read_started) * 1000
            latencies.append(latency)
            queue_ages.append((acquired - captured) * 1000)
            by_minute[slot // (60 * SAMPLE_HZ)].append(latency)
            valid += int(completed <= start + seconds)

    if problem is None:
        remaining = start + seconds - clock()
        if remaining > 0:
            sleep(remaining)
    elapsed = clock() - start
    minute_p95 = [quantile(values, .95) for values in by_minute]
    return {
        "seconds": seconds,
        "observed_wall_seconds": elapsed,
        "scheduled_slots": expected,
        "valid_frames_in_window": valid,
        "effective_fps": valid / seconds,
        "missed_scheduled_slots": expected - valid,
        "scheduled_drop_fraction": (expected - valid) / expected,
        "frames_processed": processed,
        "invalid_frames": processed - len(latencies),
        "frames_with_person": people,
        "alarm_activations": events,
        "action_errors": errors,
        "read_start_to_action_p95_ms": quantile(latencies, .95),
        "host_queue_age_p95_ms": quantile(queue_ages, .95),
        "minute_read_start_to_action_p95_ms": minute_p95,
        "shared_used_mib": ram,
        "problem": problem,
    }


def evaluate_j(windows, capture_stats, *, ram_tolerance_mib, latency_tolerance_ms):
    complete = len(windows) == REPETITIONS and all(
        w["problem"] is None and w["invalid_frames"] == 0 and w["action_errors"] == 0 for w in windows
    )
    latency = [v for w in windows for v in w["minute_read_start_to_action_p95_ms"]]
    memory = [v for w in windows for v in w["shared_used_mib"]]
    queue_age = [w["host_queue_age_p95_ms"] for w in windows]
    trends = {
        "shared_used_mib": drift(memory) if all(v is not None for v in memory) else None,
        "minute_processing_p95_ms": drift(latency) if all(v is not None for v in latency) else None,
        "queue_age_p95_ms": drift(queue_age) if all(v is not None for v in queue_age) else None,
    }
    checks = {
        "three_repetitions_without_errors": complete,
        "effective_fps_at_least_3_8": complete and all(w["effective_fps"] >= .95 * SAMPLE_HZ for w in windows),
        "scheduled_drop_at_most_5_percent": complete and all(w["scheduled_drop_fraction"] <= .05 for w in windows),
        "read_start_to_action_p95_at_most_250_ms": complete and all(
            w["read_start_to_action_p95_ms"] is not None and w["read_start_to_action_p95_ms"] <= 1000 / SAMPLE_HZ
            for w in windows
        ),
        "latest_frame_queue_bounded": complete and capture_stats["max_queue_depth"] == 1,
        "shared_ram_stable": trends["shared_used_mib"] is not None and trends["shared_used_mib"] <= ram_tolerance_mib,
        "processing_latency_stable": trends["minute_processing_p95_ms"] is not None
        and trends["minute_processing_p95_ms"] <= latency_tolerance_ms,
        "queue_age_stable": trends["queue_age_p95_ms"] is not None and trends["queue_age_p95_ms"] <= latency_tolerance_ms,
        "person_and_mock_alarm_exercised": any(w["frames_with_person"] for w in windows)
        and any(w["alarm_activations"] for w in windows),
    }
    return {"checks": checks, "positive_drift": trends, "live_j_mock_output_pass": all(checks.values())}


def board_memory():
    fields = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            fields[key] = int(value.split()[0])
    return (fields["MemTotal"] - fields["MemAvailable"]) / 1024


def board_identity():
    model = Path("/proc/device-tree/model").read_text().rstrip("\0\n")
    if platform.machine() != "aarch64" or not re.search(r"\bOrin Nano\b", model, re.IGNORECASE):
        raise ValueError("The measured target must be a Jetson Orin Nano.")
    power = subprocess.run(["/usr/sbin/nvpmodel", "-q"], check=True, capture_output=True, text=True, timeout=5)
    if not re.search(r"\b25\s*W\b", power.stdout, re.IGNORECASE):
        raise ValueError("The bench requires the predeclared 25 W profile.")
    return {"model": model, "power_profile": "25 W"}


def benchmark(connection_path, detector_path, pipeline_path, output, *, ram_tolerance_mib, latency_tolerance_ms):
    if any(not math.isfinite(v) or v < 0 for v in (ram_tolerance_mib, latency_tolerance_ms)):
        raise ValueError("The predeclared drift tolerances must be finite and nonnegative.")
    if output.exists():
        raise ValueError("Use a new output directory.")
    board = board_identity()
    memory_policy = prepare_jetson_memory()
    os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
    import cv2

    cv2.setLogLevel(0)
    connection = json.loads(connection_path.read_text(encoding="utf-8-sig"))
    config = DetectorConfig.load(detector_path)
    pipeline_config = load_pipeline_config(pipeline_path)
    if config.topology != "composite" or {label for c in config.components for label in c.class_map.values()} != {
        "person", "knife"
    }:
        raise ValueError("Use the deployed composite detector with explicit person and knife components.")
    if pipeline_config.mode is not AblationMode.B3:
        raise ValueError("The benchmark uses the fixed B3 geometry and temporal policy.")
    provenance = {
        "benchmark_sha256": _sha256_file(Path(__file__)),
        "detector_sha256": _sha256_file(detector_path),
        "pipeline_sha256": _sha256_file(pipeline_path),
        "weights_sha256": {c.component_id: _sha256_file(Path(c.weights)) for c in config.components},
    }
    detector = build_detector(config)
    snapshot = EncodeOnlySnapshot(cv2.imencode)
    output.mkdir(mode=0o700, parents=True)
    pipeline = ThreatPipeline(
        pipeline_config, alarm=MockAlarm(),
        recorder=JsonlEventRecorder(output / "events.jsonl"), snapshot=snapshot,
    )

    def process(packet):
        if packet.image.shape != (2160, 3840, 3):
            raise ValueError("Expected the frozen 3840×2160 main stream.")
        frame = frame_from_inference(packet, detector.infer(packet.image))
        snapshot.image = packet.image
        try:
            decision = pipeline.process(frame)
        finally:
            snapshot.image = None
        return Sample(frame.status is FrameStatus.VALID, any(d.label == "person" for d in frame.detections),
                      decision.event is not None, len(decision.action_errors))

    timed = None
    url = connection["rtsp_url"]

    def capture_factory():
        nonlocal timed
        timed = TimedCapture(cv2.VideoCapture(url, cv2.CAP_FFMPEG, [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
        ]))
        return timed

    def lookup_start(index):
        return timed.start_for(index) if timed is not None else None

    frames = RTSPFrameSource(url, source_id="p430-development-main", capture_factory=capture_factory)
    stream = iter(frames)
    options = {"clock": time.monotonic, "sleep": time.sleep, "shared_used_mib": board_memory}
    windows = []
    try:
        warmup = run_window(stream, process, lookup_start, WARMUP_SECONDS, **options)
        if warmup["problem"] is None:
            for _ in range(REPETITIONS):
                windows.append(run_window(stream, process, lookup_start, REPETITION_SECONDS, **options))
                if windows[-1]["problem"] is not None:
                    break
    finally:
        stream.close()

    report = evaluate_j(windows, frames.stats, ram_tolerance_mib=ram_tolerance_mib,
                        latency_tolerance_ms=latency_tolerance_ms)
    report.update(
        scope="development_live_full_pipeline_with_mock_alarm",
        timing_scope="host VideoCapture.read start through decision and alarm; includes read wait and decode",
        snapshot_scope="JPEG encoded in memory; disk write not timed",
        capture_scope="bounded RTSP latest-frame queue; raw overwrites include intentional decimation",
        hardware_alarm_verified=False,
        settings={
            "sample_hz": SAMPLE_HZ, "warmup_seconds": WARMUP_SECONDS,
            "repetition_seconds": REPETITION_SECONDS, "repetitions": REPETITIONS,
            "shared_ram_drift_tolerance_mib": ram_tolerance_mib,
            "latency_drift_tolerance_ms": latency_tolerance_ms,
            "capture_profile": "P430 main 3840x2160",
        },
        provenance=provenance, board=board, memory_policy=memory_policy,
        warmup=warmup, windows=windows, capture=dict(frames.stats),
    )
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_rtsp_json", type=Path)
    parser.add_argument("detector_json", type=Path)
    parser.add_argument("pipeline_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--ram-drift-mib", type=float, required=True)
    parser.add_argument("--latency-drift-ms", type=float, required=True)
    args = parser.parse_args()
    try:
        report = benchmark(args.private_rtsp_json, args.detector_json, args.pipeline_json, args.output_dir,
                           ram_tolerance_mib=args.ram_drift_mib, latency_tolerance_ms=args.latency_drift_ms)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, ImportError, subprocess.SubprocessError) as exc:
        # Some parser and capture errors include bytes from the private profile.
        print(f"J benchmark setup or execution failed ({type(exc).__name__}).")
        return 2
    print(json.dumps({key: report[key] for key in ("scope", "checks", "live_j_mock_output_pass")}))
    return 0 if report["live_j_mock_output_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
