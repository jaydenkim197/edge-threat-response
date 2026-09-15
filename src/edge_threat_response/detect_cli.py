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
from .media import OpenCVFrameSource
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
    return parser


def detect_main(argv: Sequence[str] | None = None) -> int:
    args = build_detect_parser().parse_args(argv)
    try:
        config = DetectorConfig.load(args.detector_config)
        detector = build_detector(config)
        frames = OpenCVFrameSource(args.input, source_id=args.source_id)
        summary = run_detection_stream(
            frames,
            detector,
            output_dir=args.output_dir,
            max_frames=args.max_frames,
            provenance=_provenance(args.input, args.detector_config, config),
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def run_main(argv: Sequence[str] | None = None) -> int:
    args = build_run_parser().parse_args(argv)
    try:
        detector_config = DetectorConfig.load(args.detector_config)
        detector = build_detector(detector_config)
        pipeline_config = load_pipeline_config(args.pipeline_config)
        frames = OpenCVFrameSource(args.input, source_id=args.source_id)
        summary = run_live_pipeline(
            frames,
            detector,
            pipeline_config,
            output_dir=args.output_dir,
            max_frames=args.max_frames,
            provenance={
                **_provenance(args.input, args.detector_config, detector_config),
                "pipeline_config": _file_record(args.pipeline_config),
            },
        )
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--detector-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-id")
    parser.add_argument("--max-frames", type=int)


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
    input_path: Path, config_path: Path, config: DetectorConfig
) -> dict[str, object]:
    return {
        "input": _file_record(input_path),
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
