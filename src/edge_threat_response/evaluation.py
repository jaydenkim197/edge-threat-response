"""Source-level event evaluation on the recorded-video timeline, without ML dependencies."""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any

from .domain import AblationMode
from .replay import load_detection_replay


@dataclass(frozen=True)
class Interval:
    start_s: float
    end_s: float

    def __post_init__(self) -> None:
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
               for value in (self.start_s, self.end_s)) or self.end_s <= self.start_s:
            raise ValueError("Interval must have finite increasing bounds")

    def contains(self, time_s: float) -> bool:
        return self.start_s <= time_s < self.end_s


@dataclass(frozen=True)
class TruthEvent:
    event_id: str
    interval: Interval


@dataclass(frozen=True)
class Alert:
    event_id: str
    timestamp_s: float

    def __post_init__(self) -> None:
        if not isinstance(self.event_id, str) or not self.event_id.strip():
            raise ValueError("Alert ID must be non-empty")
        _number({"timestamp_s": self.timestamp_s}, "timestamp_s")


@dataclass(frozen=True)
class Recording:
    recording_id: str
    session_id: str
    source_id: str
    partition: str
    scenario_id: str
    observation: Interval
    events: tuple[TruthEvent, ...]
    ignore: tuple[Interval, ...]
    leakage_group_id: str = ""


@dataclass(frozen=True)
class MatchingPolicy:
    policy_id: str
    status: str
    early_tolerance_s: float
    late_tolerance_s: float

    @classmethod
    def load(cls, path: Path) -> "MatchingPolicy":
        row = read_json(path)
        _schema(row)
        status = _text(row, "status")
        if status not in {"synthetic_only", "development", "frozen"}:
            raise ValueError("Matching status must be synthetic_only, development or frozen")
        return cls(_text(row, "policy_id"), status,
                   _number(row, "early_tolerance_s"), _number(row, "late_tolerance_s"))

    def window(self, event: TruthEvent) -> Interval:
        return Interval(event.interval.start_s - self.early_tolerance_s,
                        event.interval.end_s + self.late_tolerance_s)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_ground_truth(path: Path) -> tuple[dict[str, Any], tuple[Recording, ...]]:
    document = read_json(path)
    _schema(document)
    _text(document, "annotation_version")
    kind = _text(document, "data_kind")
    if kind not in {"synthetic", "controlled"}:
        raise ValueError("data_kind must be synthetic or controlled")
    rows = document.get("recordings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Ground truth requires at least one recording")
    recordings: list[Recording] = []
    partitions: dict[str, str] = {}
    group_partitions: dict[str, str] = {}
    identifiers: set[str] = set()
    sources: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Recording must be an object")
        recording_id, session_id, source_id = (_text(row, key) for key in ("recording_id", "session_id", "source_id"))
        partition = _text(row, "partition")
        scenario = _text(row, "scenario_id")
        if partition not in {"pilot", "tuning", "final_test"}:
            raise ValueError("partition must be pilot, tuning or final_test")
        if scenario not in {"P1", "P2", "P3", "P4", "N1", "N2", "N3", "N4", "N5"}:
            raise ValueError("Unknown controlled scenario")
        if recording_id in identifiers or source_id in sources:
            raise ValueError("recording_id and source_id must be unique per recording")
        identifiers.add(recording_id)
        sources.add(source_id)
        if session_id in partitions and partitions[session_id] != partition:
            raise ValueError("A recording session cannot cross tuning/final-test partitions")
        partitions[session_id] = partition
        group_id = _text(row, "leakage_group_id") if "leakage_group_id" in row else session_id
        if group_id in group_partitions and group_partitions[group_id] != partition:
            raise ValueError("Related recording group cannot cross tuning/final-test partitions")
        group_partitions[group_id] = partition
        observation = _interval(row)
        raw_events, raw_ignore = row.get("events"), row.get("ignore_intervals", [])
        if not isinstance(raw_events, list) or not isinstance(raw_ignore, list):
            raise ValueError("events and ignore_intervals must be arrays (empty events = negative)")
        events = tuple(TruthEvent(_text(event, "event_id"), _interval(event)) for event in raw_events)
        ignore = tuple(_interval(item) for item in raw_ignore)
        for item in raw_ignore:
            _text(item, "reason")
        if len({event.event_id for event in events}) != len(events):
            raise ValueError("Duplicate ground-truth event ID")
        _disjoint([event.interval for event in events], "Ground-truth events")
        _disjoint(list(ignore), "Ignore intervals")
        for event, raw in zip(events, raw_events):
            if kind == "controlled" or "start_frame" in raw or "end_frame" in raw:
                first, last = raw.get("start_frame"), raw.get("end_frame")
                if type(first) is not int or type(last) is not int or not 0 <= first <= last:
                    raise ValueError("Manual event frames must be inclusive non-negative integers")
            if any(_overlap(event.interval, interval) for interval in ignore):
                raise ValueError("Positive event overlaps ambiguous/ignored time; adjudicate it first")
        for interval in [*(event.interval for event in events), *ignore]:
            if interval.start_s < observation.start_s or interval.end_s > observation.end_s:
                raise ValueError("Annotation interval is outside observation")
        if _union_length(list(ignore)) >= observation.end_s - observation.start_s:
            raise ValueError("No scored observation time remains")
        recordings.append(Recording(recording_id, session_id, source_id, partition, scenario,
                                    observation, events, ignore, group_id))
    return document, tuple(recordings)


def score_recording(recording: Recording, alerts: tuple[Alert, ...], policy: MatchingPolicy) -> dict[str, Any]:
    """Chronological alerts match the earliest-ending eligible unmatched truth event."""
    if len({alert.event_id for alert in alerts}) != len(alerts):
        raise ValueError("Duplicate prediction event ID")
    if any(not math.isfinite(alert.timestamp_s) or not recording.observation.contains(alert.timestamp_s) for alert in alerts):
        raise ValueError("Prediction timestamp is outside scored recording bounds")
    windows = {event.event_id: policy.window(event) for event in recording.events}
    remaining = {event.event_id: event for event in recording.events}
    matches, false_alerts, ignored = [], [], []
    for alert in sorted(alerts, key=lambda item: (item.timestamp_s, item.event_id)):
        if any(interval.contains(alert.timestamp_s) for interval in recording.ignore):
            ignored.append(alert.event_id)
            continue
        eligible = [event for event in recording.events if windows[event.event_id].contains(alert.timestamp_s)]
        candidates = [event for event in eligible if event.event_id in remaining]
        if candidates:
            event = min(candidates, key=lambda item: (windows[item.event_id].end_s, item.interval.start_s, item.event_id))
            del remaining[event.event_id]
            matches.append({"truth_event_id": event.event_id, "prediction_event_id": alert.event_id,
                            "timestamp_s": alert.timestamp_s,
                            "event_start_to_confirmation_s": alert.timestamp_s - event.interval.start_s})
        else:
            false_alerts.append({"prediction_event_id": alert.event_id, "timestamp_s": alert.timestamp_s,
                                 "kind": "duplicate" if eligible else "background"})
    clipped_windows = [Interval(max(recording.observation.start_s, window.start_s),
                                min(recording.observation.end_s, window.end_s)) for window in windows.values()]
    duration = recording.observation.end_s - recording.observation.start_s
    scored = duration - _union_length(list(recording.ignore))
    negative = duration - _union_length([*clipped_windows, *recording.ignore])
    counts = {"tp": len(matches), "fp": len(false_alerts), "fn": len(remaining),
              "duplicate_alerts": sum(item["kind"] == "duplicate" for item in false_alerts),
              "background_false_alerts": sum(item["kind"] == "background" for item in false_alerts),
              "ignored_alerts": len(ignored), "scored_duration_s": scored,
              "negative_duration_s": max(0.0, negative)}
    return {"recording_id": recording.recording_id, "session_id": recording.session_id,
            "leakage_group_id": recording.leakage_group_id or recording.session_id,
            "partition": recording.partition, "scenario_id": recording.scenario_id, **counts,
            "metrics": metrics(counts, [item["event_start_to_confirmation_s"] for item in matches]),
            "matches": matches, "false_alerts": false_alerts, "ignored_prediction_ids": ignored,
            "missed_truth_event_ids": sorted(remaining)}


def metrics(counts: dict[str, Any], latencies: list[float]) -> dict[str, Any]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    ordered = sorted(latencies)
    percentile = None
    if ordered:
        position = (len(ordered) - 1) * 0.95
        low, high = math.floor(position), math.ceil(position)
        percentile = ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {"event_precision": _ratio(tp, tp + fp), "event_recall": _ratio(tp, tp + fn),
            "event_f1": _ratio(2 * tp, 2 * tp + fp + fn), "false_alerts": fp, "missed_events": fn,
            "false_alerts_per_scored_hour": _ratio(fp * 3600, counts["scored_duration_s"]),
            "background_false_alerts_per_negative_hour": _ratio(counts["background_false_alerts"] * 3600, counts["negative_duration_s"]),
            "latency": {"basis": "source_timeline_confirmation", "matched_count": len(ordered),
                        "mean_s": mean(ordered) if ordered else None,
                        "median_s": median(ordered) if ordered else None, "p95_s": percentile,
                        "max_s": max(ordered) if ordered else None,
                        "early_confirmation_count": sum(value < 0 for value in ordered)}}


def evaluate_replays(ground_truth: Path, replay_manifest: Path, policy_path: Path) -> dict[str, Any]:
    document, recordings = load_ground_truth(ground_truth)
    policy = MatchingPolicy.load(policy_path)
    if document["data_kind"] == "controlled" and policy.status == "synthetic_only":
        raise ValueError("Synthetic-only matching policy cannot evaluate real recordings")
    bindings_document = read_json(replay_manifest)
    _schema(bindings_document)
    bindings = bindings_document.get("recordings")
    if not isinstance(bindings, list) or len(bindings) != len(recordings):
        raise ValueError("Replay manifest must bind each annotated recording exactly once")
    by_id = {_text(row, "recording_id"): row for row in bindings}
    if len(by_id) != len(bindings) or set(by_id) != {row.recording_id for row in recordings}:
        raise ValueError("Replay and ground-truth recording IDs differ")
    per_mode: dict[str, list[dict[str, Any]]] = {mode.value: [] for mode in AblationMode}
    input_records: list[dict[str, Any]] = []
    common_contract: str | None = None
    for recording in recordings:
        binding = by_id[recording.recording_id]
        detection_path = _reference(replay_manifest, _text(binding, "detections"))
        config_path = _reference(replay_manifest, _text(binding, "pipeline_config"))
        replay_root = _reference(replay_manifest, _text(binding, "replay_dir"))
        frames = load_detection_replay(detection_path)
        if frames[0].source_id != recording.source_id:
            raise ValueError("Detection source_id differs from annotated recording")
        if any(not recording.observation.contains(frame.timestamp_s) for frame in frames):
            raise ValueError("Detection timeline is outside annotated observation")
        frame_times = {frame.frame_index: frame.timestamp_s for frame in frames}
        input_hash, config_hash = file_sha256(detection_path), file_sha256(config_path)
        config = read_json(config_path)
        contract = json.dumps({key: value for key, value in config.items() if key not in {"mode", "run_id", "config_id"}}, sort_keys=True)
        if common_contract is not None and contract != common_contract:
            raise ValueError("Pipeline/model contract changed across recordings")
        common_contract = contract
        provenance = {"recording_id": recording.recording_id, "detections_sha256": input_hash,
                      "pipeline_config_sha256": config_hash, "frame_count": len(frames),
                      "first_sample_s": frames[0].timestamp_s, "last_sample_s": frames[-1].timestamp_s,
                      "missing_or_error_frames": sum(frame.status.value != "valid" for frame in frames), "modes": {}}
        for mode in AblationMode:
            folder = replay_root / mode.value
            summary = read_json(folder / "summary.json")
            expected = {"mode": mode.value, "input_sha256": input_hash, "config_sha256": config_hash,
                        "frame_count": len(frames), "model_version": config["model_version"],
                        "config_id": config["config_id"], "run_id": config["run_id"]}
            if any(summary.get(key) != value for key, value in expected.items()):
                raise ValueError(f"{recording.recording_id}/{mode.value}: replay provenance mismatch")
            events_path = folder / "events.jsonl"
            raw_events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if summary.get("event_count") != len(raw_events):
                raise ValueError("Replay event_count differs from event file")
            alerts = []
            for row in raw_events:
                expected_event = {"schema_version": 1, "state": "CONFIRMED", "policy": mode.value,
                                  "source_id": recording.source_id, "model_version": config["model_version"],
                                  "config_id": config["config_id"], "run_id": config["run_id"]}
                if not isinstance(row, dict) or any(row.get(key) != value for key, value in expected_event.items()):
                    raise ValueError("Prediction is not a compatible CONFIRMED event")
                time_s = _number(row, "timestamp_s")
                index = row.get("frame_index")
                if type(index) is not int or frame_times.get(index) != time_s:
                    raise ValueError("Prediction frame/timestamp is not in detection input")
                alerts.append(Alert(_text(row, "event_id"), time_s))
            score = score_recording(recording, tuple(alerts), policy)
            score["action_error_count"] = summary["action_error_count"]
            per_mode[mode.value].append(score)
            provenance["modes"][mode.value] = {"events_sha256": file_sha256(events_path),
                                               "summary_sha256": file_sha256(folder / "summary.json")}
        input_records.append(provenance)
    comparison = []
    count_keys = ("tp", "fp", "fn", "duplicate_alerts", "background_false_alerts", "ignored_alerts",
                  "scored_duration_s", "negative_duration_s", "action_error_count")
    for partition in sorted({recording.partition for recording in recordings}):
        for mode, scores in per_mode.items():
            selected = [score for score in scores if score["partition"] == partition]
            counts = {key: sum(score[key] for score in selected) for key in count_keys}
            latencies = [match["event_start_to_confirmation_s"] for score in selected for match in score["matches"]]
            comparison.append({"partition": partition, "mode": mode, "recording_count": len(selected),
                               **counts, "metrics": metrics(counts, latencies)})
    return {"schema_version": 1, "data_kind": document["data_kind"],
            "annotation_version": document["annotation_version"], "policy": policy.__dict__,
            "interval_semantics": "start inclusive, end exclusive; manual end_frame is last positive frame",
            "measurement_boundary": "Decision timestamps in source video, not GPIO or real-time end-to-end latency",
            "ground_truth_sha256": file_sha256(ground_truth), "replay_manifest_sha256": file_sha256(replay_manifest),
            "policy_sha256": file_sha256(policy_path), "inputs": input_records,
            "comparison": comparison, "recordings": per_mode}


def _schema(row: dict[str, Any]) -> None:
    if type(row.get("schema_version")) is not int or row["schema_version"] != 1:
        raise ValueError("Only schema_version 1 is supported")


def _text(row: dict[str, Any], key: str) -> str:
    if not isinstance(row, dict):
        raise ValueError("Expected an annotation/binding object")
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _number(row: dict[str, Any], key: str) -> float:
    if not isinstance(row, dict):
        raise ValueError("Expected an interval object")
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be finite and non-negative")
    return float(value)


def _interval(row: dict[str, Any]) -> Interval:
    start, end = _number(row, "start_s"), _number(row, "end_s")
    if end <= start:
        raise ValueError("Interval end_s must be greater than start_s")
    return Interval(start, end)


def _overlap(left: Interval, right: Interval) -> bool:
    return max(left.start_s, right.start_s) < min(left.end_s, right.end_s)


def _disjoint(intervals: list[Interval], label: str) -> None:
    ordered = sorted(intervals, key=lambda item: item.start_s)
    if any(_overlap(left, right) for left, right in zip(ordered, ordered[1:])):
        raise ValueError(f"{label} must not overlap (one source-level event per time)")


def _union_length(intervals: list[Interval]) -> float:
    total, end = 0.0, -math.inf
    for interval in sorted(intervals, key=lambda item: item.start_s):
        total += max(0.0, interval.end_s - max(end, interval.start_s))
        end = max(end, interval.end_s)
    return total


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _reference(manifest: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (manifest.parent / path).resolve()
