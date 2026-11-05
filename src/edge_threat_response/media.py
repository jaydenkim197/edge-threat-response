from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from .domain import FrameDetections
from .ports import SnapshotResult


@dataclass(frozen=True)
class FramePacket:
    frame_index: int
    timestamp_s: float
    source_id: str
    image: Any
    captured_at_monotonic: float | None = None


class IterableFrameSource:
    def __init__(self, frames: Iterable[FramePacket]) -> None:
        self.frames = tuple(frames)

    def __iter__(self) -> Iterator[FramePacket]:
        return iter(self.frames)


class OpenCVFrameSource:
    IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    def __init__(self, path: str | Path, *, source_id: str | None = None) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise ValueError(f"Input media does not exist: {self.path}")
        self.source_id = source_id or self.path.stem

    def __iter__(self) -> Iterator[FramePacket]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV is required for image/video input.") from exc
        if self.path.suffix.lower() in self.IMAGE_SUFFIXES:
            image = cv2.imread(str(self.path))
            if image is None:
                raise RuntimeError(f"OpenCV could not decode image: {self.path}")
            yield FramePacket(0, 0.0, self.source_id, image)
            return

        capture = cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            raise RuntimeError(f"OpenCV could not open video: {self.path}")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if fps <= 0:
            fps = 30.0
        try:
            frame_index = 0
            while True:
                ok, image = capture.read()
                if not ok:
                    break
                timestamp_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                timestamp_s = (
                    timestamp_ms / 1000.0
                    if timestamp_ms > 0
                    else frame_index / fps
                )
                yield FramePacket(frame_index, timestamp_s, self.source_id, image)
                frame_index += 1
        finally:
            capture.release()


class RTSPFrameSource:
    """Bounded latest-frame input; timestamps are host decode-arrival times.

    No credentials or complete RTSP URL are returned in metadata/errors.
    A transport failure ends the run explicitly instead of becoming file EOF.
    """
    def __init__(self, url: str, *, source_id: str, capture_factory=None):
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        if parsed.scheme != "rtsp" or not parsed.hostname or not source_id.strip():
            raise ValueError("RTSP URL and explicit source ID required")
        self._url, self.source_id, self.capture_factory = url, source_id, capture_factory
        self.stats = {"decoded_frames": 0, "dropped_frames": 0, "max_queue_depth": 0,
                      "timestamp_boundary": "host monotonic time at completed decode"}

    def __iter__(self):
        import os
        import queue
        import threading
        import time
        factory = self.capture_factory
        if factory is None:
            os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "-8")
            import cv2
            cv2.setLogLevel(0)
            factory = lambda: cv2.VideoCapture(self._url, cv2.CAP_FFMPEG,
                                               [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 20000,
                                                cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])
        pending = queue.Queue(maxsize=1)
        stop, done = threading.Event(), threading.Event()
        failure = []

        def producer():
            capture = None
            try:
                capture = factory()
                if not capture.isOpened(): raise RuntimeError("RTSP open failed; check private connection settings")
                started, index = time.monotonic(), 0
                while not stop.is_set():
                    ok, image = capture.read()
                    if not ok: raise RuntimeError("RTSP read failed or stream disconnected")
                    captured = time.monotonic()
                    packet = FramePacket(index, captured-started, self.source_id, image, captured)
                    index += 1
                    self.stats["decoded_frames"] = index
                    try: pending.put_nowait(packet)
                    except queue.Full:
                        try:
                            pending.get_nowait()
                            self.stats["dropped_frames"] += 1
                        except queue.Empty: pass
                        pending.put_nowait(packet)
                    self.stats["max_queue_depth"] = 1
            except Exception:
                # Third-party exceptions may include the credential-bearing URL.
                failure.append("RTSP capture failed; connection details are omitted")
            finally:
                if capture is not None: capture.release()
                done.set()

        worker = threading.Thread(target=producer, name="rtsp-latest-frame", daemon=True)
        worker.start()
        try:
            while True:
                try: packet = pending.get(timeout=.1)
                except queue.Empty:
                    if done.is_set(): raise RuntimeError(failure[0] if failure else "RTSP stream ended")
                    continue
                yield packet
        finally:
            stop.set()
            worker.join(timeout=6)


class CurrentFrameSnapshot:
    """Bind the current decoded frame to the synchronous pipeline snapshot port."""

    def __init__(
        self,
        output_dir: str | Path,
        *,
        writer: Callable[[Path, Any], bool] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.writer = writer
        self._packet: FramePacket | None = None

    def bind(self, packet: FramePacket) -> None:
        self._packet = packet

    def capture(self, event_id: str, frame: FrameDetections) -> SnapshotResult:
        packet = self._packet
        if packet is None or (
            packet.frame_index != frame.frame_index or packet.source_id != frame.source_id
        ):
            return SnapshotResult(status="failed", error="bound frame does not match event")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{event_id}.jpg"
        writer = self.writer
        if writer is None:
            try:
                import cv2
            except ImportError as exc:
                return SnapshotResult(status="failed", error=f"OpenCV unavailable: {exc}")
            writer = lambda target, image: bool(cv2.imwrite(str(target), image))
        if not writer(path, packet.image):
            return SnapshotResult(status="failed", error="snapshot writer returned false")
        return SnapshotResult(status="captured", path=str(path.resolve()))
