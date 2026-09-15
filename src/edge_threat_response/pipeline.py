from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .config import PipelineConfig
from .domain import (
    AblationMode,
    AlertState,
    AssociationResult,
    Detection,
    FrameDetections,
    FrameStatus,
    TemporalResult,
    ThreatEvent,
)
from .ports import (
    AlarmPort,
    EventRecorderPort,
    MemoryEventRecorder,
    MockAlarm,
    SnapshotPort,
    SnapshotResult,
    UnavailableSnapshot,
)
from .spatial import associate_person_knives
from .state_machine import AlertStateMachine, StateTransition
from .temporal import KOfNBuffer


@dataclass(frozen=True)
class DecisionEvidence:
    reliable_people: tuple[Detection, ...]
    reliable_knives: tuple[Detection, ...]
    associations: tuple[AssociationResult, ...]
    knife_temporal: TemporalResult
    association_temporal: TemporalResult
    candidate: bool
    confirmed: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "reliable_person_count": len(self.reliable_people),
            "reliable_knife_count": len(self.reliable_knives),
            "associated_pair_count": sum(
                association.associated for association in self.associations
            ),
            "associations": [item.to_dict() for item in self.associations],
            "knife_temporal": self.knife_temporal.to_dict(),
            "association_temporal": self.association_temporal.to_dict(),
            "candidate": self.candidate,
            "confirmed": self.confirmed,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class FrameResult:
    frame: FrameDetections
    mode: AblationMode
    evidence: DecisionEvidence
    transition: StateTransition
    event: ThreatEvent | None
    action_errors: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame.frame_index,
            "timestamp_s": self.frame.timestamp_s,
            "source_id": self.frame.source_id,
            "frame_status": self.frame.status.value,
            "mode": self.mode.value,
            "state_before": self.transition.before.value,
            "state_after": self.transition.after.value,
            "entered_confirmed": self.transition.entered_confirmed,
            "exited_confirmed": self.transition.exited_confirmed,
            "rearm_clear_streak": self.transition.rearm_clear_streak,
            "evidence": self.evidence.to_dict(),
            "event_id": self.event.event_id if self.event else None,
            "action_errors": list(self.action_errors),
        }


class ThreatPipeline:
    def __init__(
        self,
        config: PipelineConfig,
        *,
        alarm: AlarmPort | None = None,
        recorder: EventRecorderPort | None = None,
        snapshot: SnapshotPort | None = None,
    ) -> None:
        if not isinstance(config, PipelineConfig):
            raise TypeError("config must be a PipelineConfig instance.")
        self.config = config
        self.alarm = alarm if alarm is not None else MockAlarm()
        self.recorder = recorder if recorder is not None else MemoryEventRecorder()
        self.snapshot = snapshot if snapshot is not None else UnavailableSnapshot()
        self._knife_temporal = KOfNBuffer(k=config.temporal_k, n=config.temporal_n)
        self._association_temporal = KOfNBuffer(
            k=config.temporal_k, n=config.temporal_n
        )
        self._state_machine = AlertStateMachine(
            rearm_clear_frames=config.rearm_clear_frames
        )
        self._event_sequence = 0
        self._source_id: str | None = None
        self._last_frame_index: int | None = None
        self._last_timestamp_s: float | None = None

    @property
    def state(self) -> AlertState:
        return self._state_machine.state

    def process(self, frame: FrameDetections) -> FrameResult:
        self._validate_sequence(frame)
        people, knives = self._reliable_detections(frame)
        associations = associate_person_knives(
            people,
            knives,
            policy=self.config.spatial_policy,
            normalized_distance_threshold=self.config.normalized_distance_threshold,
            expanded_person_ratio=self.config.expanded_person_ratio,
        )
        has_knife = bool(knives)
        has_association = any(item.associated for item in associations)
        knife_temporal = self._knife_temporal.update(has_knife)
        association_temporal = self._association_temporal.update(has_association)
        candidate, confirmed, reasons = _evaluate_policy(
            self.config.mode,
            has_knife=has_knife,
            has_association=has_association,
            knife_temporal=knife_temporal,
            association_temporal=association_temporal,
        )
        evidence = DecisionEvidence(
            reliable_people=people,
            reliable_knives=knives,
            associations=associations,
            knife_temporal=knife_temporal,
            association_temporal=association_temporal,
            candidate=candidate,
            confirmed=confirmed,
            reasons=reasons,
        )
        transition = self._state_machine.update(
            candidate=candidate, confirmed=confirmed
        )
        event: ThreatEvent | None = None
        errors: list[str] = []

        if transition.entered_confirmed:
            self._event_sequence += 1
            event_id = self._make_event_id(frame)
            snapshot_result = self._capture_snapshot(event_id, frame, errors)
            associated = tuple(item for item in associations if item.associated)
            event = ThreatEvent(
                schema_version=1,
                event_id=event_id,
                run_id=self.config.run_id,
                sequence=self._event_sequence,
                source_id=frame.source_id,
                frame_index=frame.frame_index,
                timestamp_s=frame.timestamp_s,
                state=transition.after,
                policy=self.config.mode,
                reasons=reasons,
                model_version=self.config.model_version,
                config_id=self.config.config_id,
                reliable_person_count=len(people),
                reliable_knife_count=len(knives),
                associated_pair_count=len(associated),
                selected_association=(
                    min(
                        associated,
                        key=lambda item: item.normalized_distance
                        if item.normalized_distance is not None
                        else float("inf"),
                    )
                    if associated
                    else None
                ),
                snapshot_status=snapshot_result.status,
                snapshot_path=snapshot_result.path,
                snapshot_error=snapshot_result.error,
            )
            try:
                self.recorder.record(event)
            except Exception as exc:  # Port failures must not suppress the alarm.
                errors.append(f"event_recorder: {type(exc).__name__}: {exc}")
            try:
                self.alarm.set_active(True, frame, event)
            except Exception as exc:
                errors.append(f"alarm_activate: {type(exc).__name__}: {exc}")
        elif transition.exited_confirmed:
            try:
                self.alarm.set_active(False, frame, None)
            except Exception as exc:
                errors.append(f"alarm_deactivate: {type(exc).__name__}: {exc}")

        return FrameResult(
            frame=frame,
            mode=self.config.mode,
            evidence=evidence,
            transition=transition,
            event=event,
            action_errors=tuple(errors),
        )

    def _reliable_detections(
        self, frame: FrameDetections
    ) -> tuple[tuple[Detection, ...], tuple[Detection, ...]]:
        if frame.status is not FrameStatus.VALID:
            return (), ()
        people = tuple(
            item
            for item in frame.detections
            if item.label == "person"
            and item.confidence >= self.config.person_confidence_threshold
        )
        knives = tuple(
            item
            for item in frame.detections
            if item.label == "knife"
            and item.confidence >= self.config.knife_confidence_threshold
        )
        return people, knives

    def _validate_sequence(self, frame: FrameDetections) -> None:
        if self._source_id is None:
            self._source_id = frame.source_id
        elif frame.source_id != self._source_id:
            raise ValueError("A pipeline instance accepts exactly one source_id.")
        if self._last_frame_index is not None and frame.frame_index <= self._last_frame_index:
            raise ValueError("frame_index must increase strictly.")
        if self._last_timestamp_s is not None and frame.timestamp_s < self._last_timestamp_s:
            raise ValueError("timestamp_s must not decrease.")
        self._last_frame_index = frame.frame_index
        self._last_timestamp_s = frame.timestamp_s

    def _make_event_id(self, frame: FrameDetections) -> str:
        identity = (
            f"{self.config.run_id}|{self.config.mode.value}|"
            f"{frame.source_id}|{self._event_sequence}"
        )
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
        return (
            f"{self.config.run_id}-{self.config.mode.value}-"
            f"{self._event_sequence:04d}-{digest}"
        )

    def _capture_snapshot(
        self,
        event_id: str,
        frame: FrameDetections,
        errors: list[str],
    ) -> SnapshotResult:
        try:
            return self.snapshot.capture(event_id, frame)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            errors.append(f"snapshot: {message}")
            return SnapshotResult(status="failed", error=message)


def _evaluate_policy(
    mode: AblationMode,
    *,
    has_knife: bool,
    has_association: bool,
    knife_temporal: TemporalResult,
    association_temporal: TemporalResult,
) -> tuple[bool, bool, tuple[str, ...]]:
    if mode is AblationMode.B0:
        candidate = confirmed = has_knife
        reasons = ("reliable_knife_current_frame",) if confirmed else ()
    elif mode is AblationMode.B1:
        confirmed = knife_temporal.confirmed
        candidate = knife_temporal.true_count > 0
        reasons = ("reliable_knife_k_of_n",) if confirmed else ()
    elif mode is AblationMode.B2:
        confirmed = has_association
        candidate = has_knife
        reasons = ("person_knife_association_current_frame",) if confirmed else ()
    else:
        confirmed = association_temporal.confirmed
        candidate = has_knife or association_temporal.true_count > 0
        reasons = ("person_knife_association_k_of_n",) if confirmed else ()
    return candidate, confirmed, reasons
