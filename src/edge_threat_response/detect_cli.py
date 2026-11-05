from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .config import load_pipeline_config
from .detector import CompositeDetector, MappedDetector, UltralyticsBackend
from .media import OpenCVFrameSource, RTSPFrameSource
from .jetson_memory import prepare_jetson_memory
from .runtime import run_detection_stream, run_live_pipeline


@dataclass(frozen=True)
class DetectorComponentConfig:
    component_id: str
    weights: str
    class_map: dict[int, str]
    predict_arguments: dict[str, object]


@dataclass(frozen=True)
class DetectorConfig:
    schema_version: int
    topology: str
    components: tuple[DetectorComponentConfig, ...]

    @classmethod
    def load(cls, path: Path) -> "DetectorConfig":
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not read detector config {path}: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Only detector config schema_version 1 is supported.")
        topology = payload.get("topology")
        if topology not in {"single", "composite"}:
            raise ValueError("Detector topology must be single or composite.")
        raw_components = payload.get("components")
        if not isinstance(raw_components, list) or not raw_components:
            raise ValueError("Detector config requires a non-empty components list.")
        if topology == "single" and len(raw_components) != 1:
            raise ValueError("Single topology requires exactly one component.")
        components = tuple(_parse_component(item) for item in raw_components)
        identifiers = [item.component_id for item in components]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Detector component IDs must be unique.")
        return cls(1, topology, components)


def build_detector(config: DetectorConfig):
    components = tuple(
        MappedDetector(
            item.component_id,
            UltralyticsBackend(
                item.weights, predict_arguments=item.predict_arguments
            ),
            item.class_map,
        )
        for item in config.components
    )
    return components[0] if config.topology == "single" else CompositeDetector(components)


def build_detect_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="etr-detect",
        description="Run detector adapters on image/video and write canonical JSONL.",
    )
    _add_common_arguments(parser)
    return parser


def build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="etr-run",
        description="Run detector plus one threat policy and capture event snapshots.",
    )
    _add_common_arguments(parser)
    parser.add_argument("--pipeline-config", type=Path, required=True)
    parser.add_argument("--relation-checkpoint", type=Path)
    parser.add_argument("--relation-device", default="cpu")
    return parser


def detect_main(argv: Sequence[str] | None = None) -> int:
    args = build_detect_parser().parse_args(argv)
    try:
        config = DetectorConfig.load(args.detector_config)
        _validate_local_weights(config)
        native_memory = prepare_jetson_memory(inherit_thp=args.inherit_thp)
        detector = build_detector(config)
        frames = _frame_source(args)
        summary = run_detection_stream(
            frames,
            detector,
            output_dir=args.output_dir,
            max_frames=args.max_frames,
            provenance={**_provenance(args.input, args.detector_config, config, rtsp_env=args.rtsp_env), "native_memory":native_memory},
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["frame_status_counts"].get("valid",0) else 2


def run_main(argv: Sequence[str] | None = None) -> int:
    args = build_run_parser().parse_args(argv)
    try:
        detector_config = DetectorConfig.load(args.detector_config)
        _validate_local_weights(detector_config)
        native_memory = prepare_jetson_memory(inherit_thp=args.inherit_thp)
        detector = build_detector(detector_config)
        pipeline_config = load_pipeline_config(args.pipeline_config)
        relation = None
        if args.relation_checkpoint is not None:
            from .hoi import TorchRelationProvider
            if pipeline_config.mode.value != "B4":
                raise ValueError("--relation-checkpoint is only used by B4")
            relation = TorchRelationProvider(args.relation_checkpoint, device=args.relation_device)
        frames = _frame_source(args)
        summary = run_live_pipeline(
            frames,
            detector,
            pipeline_config,
            output_dir=args.output_dir,
            max_frames=args.max_frames,
            relation=relation,
            relation_threshold=relation.threshold if relation is not None else .5,
            provenance={
                **_provenance(args.input, args.detector_config, detector_config, rtsp_env=args.rtsp_env),
                "pipeline_config": _file_record(args.pipeline_config),
                "native_memory": native_memory,
                **({"relation_checkpoint": _file_record(args.relation_checkpoint), "relation_threshold": relation.threshold} if relation is not None else {}),
            },
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["frame_status_counts"].get("valid",0) else 2


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input", type=Path)
    inputs.add_argument("--rtsp-env", help="Environment variable containing private RTSP URL; never put credentials on the command line")
    parser.add_argument("--detector-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-id")
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--inherit-thp", action="store_true", help="Keep inherited THP policy on Orin for diagnostic comparisons")


def _validate_local_weights(config: DetectorConfig) -> None:
    for component in config.components:
        if not Path(component.weights).is_file():
            raise ValueError(f"Local weight is missing for {component.component_id}: {component.weights}")


def _frame_source(args):
    if args.input is not None:
        return OpenCVFrameSource(args.input, source_id=args.source_id)
    import os
    if not args.source_id or args.max_frames is None or args.max_frames < 1:
        raise ValueError("RTSP requires --source-id and positive --max-frames")
    url = os.environ.get(args.rtsp_env, "")
    if not url:
        raise ValueError("RTSP environment variable is not configured")
    return RTSPFrameSource(url, source_id=args.source_id)


def _parse_component(payload: object) -> DetectorComponentConfig:
    if not isinstance(payload, dict):
        raise ValueError("Each detector component must be an object.")
    component_id = payload.get("component_id")
    weights = payload.get("weights")
    if not isinstance(component_id, str) or not component_id.strip():
        raise ValueError("Detector component_id must not be empty.")
    if not isinstance(weights, str) or not weights.strip():
        raise ValueError("Detector weights must not be empty.")
    raw_class_map = payload.get("class_map")
    if not isinstance(raw_class_map, dict) or not raw_class_map:
        raise ValueError("Detector component class_map must be a non-empty object.")
    try:
        class_map = {int(key): str(value) for key, value in raw_class_map.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError("Detector class_map keys must be integer-like.") from exc
    if any(value not in {"person", "knife"} for value in class_map.values()):
        raise ValueError("Detector class_map values must be person or knife.")
    arguments = payload.get("predict_arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("predict_arguments must be an object.")
    forbidden = {"source", "verbose"}.intersection(arguments)
    if forbidden:
        raise ValueError(f"Predict arguments are controlled by the adapter: {sorted(forbidden)}")
    return DetectorComponentConfig(
        component_id=component_id,
        weights=weights,
        class_map=class_map,
        predict_arguments=dict(arguments),
    )


def _provenance(
    input_path: Path | None, config_path: Path, config: DetectorConfig, *, rtsp_env: str | None = None
) -> dict[str, object]:
    return {
        "input": _file_record(input_path) if input_path is not None else {"kind": "rtsp", "environment_variable": rtsp_env,
                   "timestamp_boundary": "host monotonic time at completed decode; not camera exposure time"},
        "detector_config": _file_record(config_path),
        "weights": [
            {
                "component_id": component.component_id,
                **_file_record(Path(component.weights)),
            }
            for component in config.components
        ],
    }


def _file_record(path: Path) -> dict[str, object]:
    record: dict[str, object] = {"path": str(path.resolve()), "exists": path.is_file()}
    if path.is_file():
        record.update({"size_bytes": path.stat().st_size, "sha256": _sha256_file(path)})
    return record


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(detect_main())


if __name__ == "__main__":
    raise SystemExit(detect_main())
