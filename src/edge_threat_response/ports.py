from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .domain import FrameDetections, ThreatEvent


@dataclass(frozen=True)
class SnapshotResult:
    status: str
    path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class AlarmSignal:
    active: bool
    frame_index: int
    timestamp_s: float
    event_id: str | None


class AlarmPort(Protocol):
    def set_active(
        self,
        active: bool,
        frame: FrameDetections,
        event: ThreatEvent | None,
    ) -> None: ...


class EventRecorderPort(Protocol):
    def record(self, event: ThreatEvent) -> None: ...


class SnapshotPort(Protocol):
    def capture(self, event_id: str, frame: FrameDetections) -> SnapshotResult: ...


class MockAlarm:
    def __init__(self) -> None:
        self.active = False
        self.signals: list[AlarmSignal] = []

    def set_active(
        self,
        active: bool,
        frame: FrameDetections,
        event: ThreatEvent | None,
    ) -> None:
        self.active = active
        self.signals.append(
            AlarmSignal(
                active=active,
                frame_index=frame.frame_index,
                timestamp_s=frame.timestamp_s,
                event_id=event.event_id if event is not None else None,
            )
        )


class MemoryEventRecorder:
    def __init__(self) -> None:
        self.events: list[ThreatEvent] = []

    def record(self, event: ThreatEvent) -> None:
        self.events.append(event)


class JsonlEventRecorder:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def record(self, event: ThreatEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")


class UnavailableSnapshot:
    def capture(self, event_id: str, frame: FrameDetections) -> SnapshotResult:
        return SnapshotResult(status="not_captured")
