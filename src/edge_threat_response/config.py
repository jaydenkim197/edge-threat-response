from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .domain import AblationMode


@dataclass(frozen=True)
class PipelineConfig:
    schema_version: int
    config_id: str
    run_id: str
    model_version: str
    mode: AblationMode
    person_confidence_threshold: float
    knife_confidence_threshold: float
    normalized_distance_threshold: float
    expanded_person_ratio: float
    temporal_k: int
    temporal_n: int
    rearm_clear_frames: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.schema_version, bool)
            or not isinstance(self.schema_version, int)
            or self.schema_version != 1
        ):
            raise ValueError("Only pipeline config schema_version 1 is supported.")
        for name in ("config_id", "run_id", "model_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty.")
        if not isinstance(self.mode, AblationMode):
            raise ValueError("mode must be an AblationMode value.")
        for name in (
            "person_confidence_threshold",
            "knife_confidence_threshold",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError(f"{name} must be between 0 and 1.")
        for name in (
            "normalized_distance_threshold",
            "expanded_person_ratio",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0
            ):
                raise ValueError(f"{name} must be finite and non-negative.")
        if _is_not_positive_int(self.temporal_k) or _is_not_positive_int(
            self.temporal_n
        ):
            raise ValueError("temporal k and n must be positive integers.")
        if self.temporal_k > self.temporal_n:
            raise ValueError("K-of-N requires temporal_k <= temporal_n.")
        if _is_not_positive_int(self.rearm_clear_frames):
            raise ValueError("rearm_clear_frames must be a positive integer.")

    def for_mode(self, mode: AblationMode) -> "PipelineConfig":
        return replace(self, mode=mode)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineConfig":
        try:
            confidence = _require_dict(data, "confidence")
            spatial = _require_dict(data, "spatial")
            temporal = _require_dict(data, "temporal")
            state_machine = _require_dict(data, "state_machine")
            return cls(
                schema_version=data["schema_version"],
                config_id=data["config_id"],
                run_id=data["run_id"],
                model_version=data["model_version"],
                mode=AblationMode(data["mode"]),
                person_confidence_threshold=confidence["person"],
                knife_confidence_threshold=confidence["knife"],
                normalized_distance_threshold=spatial[
                    "normalized_distance_threshold"
                ],
                expanded_person_ratio=spatial["expanded_person_ratio"],
                temporal_k=temporal["k"],
                temporal_n=temporal["n"],
                rearm_clear_frames=state_machine["rearm_clear_frames"],
            )
        except KeyError as exc:
            raise ValueError(f"Missing pipeline config field: {exc.args[0]}") from exc
        except (TypeError, AttributeError) as exc:
            raise ValueError("Pipeline config fields have invalid types.") from exc


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    config_path = Path(path)
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in pipeline config {config_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Pipeline config root must be a JSON object.")
    return PipelineConfig.from_dict(data)


def _require_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data[key]
    if not isinstance(value, dict):
        raise ValueError(f"Pipeline config field {key} must be an object.")
    return value


def _is_not_positive_int(value: object) -> bool:
    return isinstance(value, bool) or not isinstance(value, int) or value < 1
