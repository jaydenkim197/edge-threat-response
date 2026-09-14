from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class FrameStatus(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    DETECTOR_ERROR = "detector_error"


class AlertState(str, Enum):
    CLEAR = "CLEAR"
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    COOLDOWN = "COOLDOWN"


class AblationMode(str, Enum):
    B0 = "B0"
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"


@dataclass(frozen=True)
class BBox:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def __post_init__(self) -> None:
        values = (self.x_min, self.y_min, self.x_max, self.y_max)
        if any(not math.isfinite(value) for value in values):
            raise ValueError("Bounding-box coordinates must be finite.")
        if self.x_max <= self.x_min or self.y_max <= self.y_min:
            raise ValueError("Bounding box must have positive width and height.")

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x_min + self.x_max) / 2, (self.y_min + self.y_max) / 2)

    @property
    def diagonal(self) -> float:
        return math.hypot(self.width, self.height)

    def contains(self, point: tuple[float, float]) -> bool:
        x, y = point
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max

    def expand_by_ratio(self, ratio: float) -> "BBox":
        if not math.isfinite(ratio) or ratio < 0:
            raise ValueError("Expansion ratio must be finite and non-negative.")
        x_padding = self.width * ratio
        y_padding = self.height * ratio
        return BBox(
            self.x_min - x_padding,
            self.y_min - y_padding,
            self.x_max + x_padding,
            self.y_max + y_padding,
        )

    def to_list(self) -> list[float]:
        return [self.x_min, self.y_min, self.x_max, self.y_max]


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    bbox: BBox
    detection_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.label, str):
            raise ValueError("Detection label must be a string.")
        if not self.label.strip():
            raise ValueError("Detection label must not be empty.")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0 <= self.confidence <= 1
        ):
            raise ValueError("Detection confidence must be between 0 and 1.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bbox_xyxy": self.bbox.to_list(),
            "detection_id": self.detection_id,
        }


@dataclass(frozen=True)
class FrameDetections:
    frame_index: int
    timestamp_s: float
    source_id: str
    status: FrameStatus
    detections: tuple[Detection, ...] = ()
    error: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.frame_index, bool) or not isinstance(self.frame_index, int):
            raise ValueError("frame_index must be an integer.")
        if self.frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        if (
            isinstance(self.timestamp_s, bool)
            or not isinstance(self.timestamp_s, (int, float))
            or not math.isfinite(self.timestamp_s)
            or self.timestamp_s < 0
        ):
            raise ValueError("timestamp_s must be finite and non-negative.")
        if not isinstance(self.source_id, str):
            raise ValueError("source_id must be a string.")
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty.")
        if not isinstance(self.status, FrameStatus):
            raise ValueError("status must be a FrameStatus value.")
        if any(not isinstance(item, Detection) for item in self.detections):
            raise ValueError("detections must contain Detection values.")
        if self.status is not FrameStatus.VALID and self.detections:
            raise ValueError("Non-valid frames cannot contain detections.")
        if self.status is FrameStatus.DETECTOR_ERROR and not self.error:
            raise ValueError("detector_error frames require an error message.")
        if self.status is not FrameStatus.DETECTOR_ERROR and self.error is not None:
            raise ValueError("Only detector_error frames may include an error message.")


@dataclass(frozen=True)
class AssociationResult:
    knife: Detection
    person: Detection | None
    center_distance: float | None
    normalized_distance: float | None
    center_in_expanded_person: bool
    associated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "knife": self.knife.to_dict(),
            "person": self.person.to_dict() if self.person else None,
            "center_distance": self.center_distance,
            "normalized_distance": self.normalized_distance,
            "center_in_expanded_person": self.center_in_expanded_person,
            "associated": self.associated,
        }


@dataclass(frozen=True)
class TemporalResult:
    value: bool
    true_count: int
    sample_count: int
    k: int
    n: int
    confirmed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ThreatEvent:
    schema_version: int
    event_id: str
    run_id: str
    sequence: int
    source_id: str
    frame_index: int
    timestamp_s: float
    state: AlertState
    policy: AblationMode
    reasons: tuple[str, ...]
    model_version: str
    config_id: str
    reliable_person_count: int
    reliable_knife_count: int
    associated_pair_count: int
    selected_association: AssociationResult | None
    snapshot_status: str
    snapshot_path: str | None
    snapshot_error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "run_id": self.run_id,
            "sequence": self.sequence,
            "source_id": self.source_id,
            "frame_index": self.frame_index,
            "timestamp_s": self.timestamp_s,
            "state": self.state.value,
            "policy": self.policy.value,
            "reasons": list(self.reasons),
            "model_version": self.model_version,
            "config_id": self.config_id,
            "reliable_person_count": self.reliable_person_count,
            "reliable_knife_count": self.reliable_knife_count,
            "associated_pair_count": self.associated_pair_count,
            "selected_association": (
                self.selected_association.to_dict()
                if self.selected_association is not None
                else None
            ),
            "snapshot_status": self.snapshot_status,
            "snapshot_path": self.snapshot_path,
            "snapshot_error": self.snapshot_error,
        }
