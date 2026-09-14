from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Sequence

from .config import load_pipeline_config
from .domain import AblationMode
from .pipeline import ThreatPipeline
from .ports import JsonlEventRecorder, MockAlarm, UnavailableSnapshot
from .replay import load_detection_replay, write_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay recorded detections through B0-B3 threat policies."
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--modes",
        default="B0,B1,B2,B3",
        help="Comma-separated subset of B0,B1,B2,B3 (default: all).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        modes = _parse_modes(args.modes)
        frames = load_detection_replay(args.input)
        base_config = load_pipeline_config(args.config)
        input_sha256 = _file_sha256(args.input)
        config_sha256 = _file_sha256(args.config)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    summaries: list[dict[str, object]] = []
    for mode in modes:
        mode_dir = args.output_dir / mode.value
        recorder = JsonlEventRecorder(mode_dir / "events.jsonl")
        alarm = MockAlarm()
        pipeline = ThreatPipeline(
            base_config.for_mode(mode),
            alarm=alarm,
            recorder=recorder,
            snapshot=UnavailableSnapshot(),
        )
        results = [pipeline.process(frame) for frame in frames]
        write_jsonl(mode_dir / "frames.jsonl", (item.to_dict() for item in results))
        state_counts = Counter(item.transition.after.value for item in results)
        summary: dict[str, object] = {
            "mode": mode.value,
            "input": str(args.input),
            "input_sha256": input_sha256,
            "config": str(args.config),
            "config_sha256": config_sha256,
            "config_id": base_config.config_id,
            "run_id": base_config.run_id,
            "model_version": base_config.model_version,
            "frame_count": len(results),
            "event_count": sum(item.event is not None for item in results),
            "event_frame_indices": [
                item.frame.frame_index for item in results if item.event is not None
            ],
            "state_counts": dict(sorted(state_counts.items())),
            "alarm_signals": [signal.__dict__ for signal in alarm.signals],
            "action_error_count": sum(len(item.action_errors) for item in results),
        }
        mode_dir.mkdir(parents=True, exist_ok=True)
        (mode_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summaries.append(summary)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps({"runs": summaries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"runs": summaries}, ensure_ascii=False, indent=2))
    return 0


def _parse_modes(raw: str) -> tuple[AblationMode, ...]:
    names = [item.strip() for item in raw.split(",") if item.strip()]
    if not names:
        raise ValueError("At least one ablation mode is required.")
    try:
        modes = tuple(AblationMode(name) for name in names)
    except ValueError as exc:
        raise ValueError("Modes must be a comma-separated subset of B0,B1,B2,B3.") from exc
    if len(set(modes)) != len(modes):
        raise ValueError("Ablation modes must not be duplicated.")
    return modes


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
