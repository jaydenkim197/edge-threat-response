from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from .domain import BBox, Detection, FrameStatus


@dataclass(frozen=True)
class RawDetection:
    class_id: int
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class DetectorInference:
    status: FrameStatus
    detections: tuple[Detection, ...]
    inference_ms: float
    component_latencies_ms: tuple[tuple[str, float], ...]
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status is FrameStatus.VALID and self.error is not None:
            raise ValueError("Valid detector inference cannot include an error.")
        if self.status is not FrameStatus.VALID and self.detections:
            raise ValueError("Failed detector inference cannot include detections.")


class CanonicalDetector(Protocol):
    def infer(self, image: Any) -> DetectorInference: ...


class DetectionBackend(Protocol):
    def predict(self, image: Any) -> Iterable[RawDetection]: ...


class MappedDetector:
    """Map model-local class IDs to the runtime canonical string contract."""

    def __init__(
        self,
        component_id: str,
        backend: DetectionBackend,
        class_map: dict[int, str],
    ) -> None:
        if not component_id.strip():
            raise ValueError("component_id must not be empty.")
        if not class_map or any(label not in {"person", "knife"} for label in class_map.values()):
            raise ValueError("class_map must map at least one ID to person or knife.")
        self.component_id = component_id
        self.backend = backend
        self.class_map = dict(class_map)

    def infer(self, image: Any) -> DetectorInference:
        started = time.perf_counter()
        try:
            raw = tuple(self.backend.predict(image))
            elapsed = (time.perf_counter() - started) * 1000
            detections: list[Detection] = []
            for index, item in enumerate(raw):
                label = self.class_map.get(item.class_id)
                if label is None:
                    continue
                detections.append(
                    Detection(
                        label=label,
                        confidence=item.confidence,
                        bbox=BBox(*item.bbox_xyxy),
                        detection_id=f"{self.component_id}:{index}",
                    )
                )
            return DetectorInference(
                status=FrameStatus.VALID,
                detections=tuple(detections),
                inference_ms=elapsed,
                component_latencies_ms=((self.component_id, elapsed),),
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return DetectorInference(
                status=FrameStatus.DETECTOR_ERROR,
                detections=(),
                inference_ms=elapsed,
                component_latencies_ms=((self.component_id, elapsed),),
                error=f"{self.component_id}: {type(exc).__name__}: {exc}",
            )


class CompositeDetector:
    """Run required detector components and fail closed if any component fails."""

    def __init__(self, components: Iterable[CanonicalDetector]) -> None:
        self.components = tuple(components)
        if not self.components:
            raise ValueError("Composite detector requires at least one component.")

    def infer(self, image: Any) -> DetectorInference:
        results = tuple(component.infer(image) for component in self.components)
        latency = sum(item.inference_ms for item in results)
        component_latencies = tuple(
            pair for item in results for pair in item.component_latencies_ms
        )
        failures = [item.error for item in results if item.status is not FrameStatus.VALID]
        if failures:
            return DetectorInference(
                status=FrameStatus.DETECTOR_ERROR,
                detections=(),
                inference_ms=latency,
                component_latencies_ms=component_latencies,
                error="; ".join(item for item in failures if item),
            )
        return DetectorInference(
            status=FrameStatus.VALID,
            detections=tuple(
                detection for item in results for detection in item.detections
            ),
            inference_ms=latency,
            component_latencies_ms=component_latencies,
        )


class CallableBackend:
    """Small adapter used by deterministic tests and non-Ultralytics runtimes."""

    def __init__(self, function: Callable[[Any], Iterable[RawDetection]]) -> None:
        self.function = function

    def predict(self, image: Any) -> Iterable[RawDetection]:
        return self.function(image)


class UltralyticsBackend:
    """Lazy optional Ultralytics backend; importing core modules does not require ML packages."""

    def __init__(
        self,
        weights: str | Path,
        *,
        predict_arguments: dict[str, object] | None = None,
        model_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self.weights = str(weights)
        self.predict_arguments = dict(predict_arguments or {})
        self._model_factory = model_factory
        self._model: Any | None = None

    def predict(self, image: Any) -> Iterable[RawDetection]:
        model = self._get_model()
        arguments = {"verbose": False, **self.predict_arguments}
        results = model.predict(source=image, **arguments)
        if not results:
            return ()
        boxes = getattr(results[0], "boxes", None)
        if boxes is None:
            return ()
        xyxy = _to_rows(getattr(boxes, "xyxy"))
        confidences = _to_values(getattr(boxes, "conf"))
        classes = _to_values(getattr(boxes, "cls"))
        if not (len(xyxy) == len(confidences) == len(classes)):
            raise RuntimeError("Ultralytics result arrays have inconsistent lengths.")
        return tuple(
            RawDetection(
                class_id=int(class_id),
                confidence=float(confidence),
                bbox_xyxy=tuple(float(value) for value in coordinates),
            )
            for coordinates, confidence, class_id in zip(xyxy, confidences, classes)
        )

    def _get_model(self) -> Any:
        if self._model is None:
            factory = self._model_factory
            if factory is None:
                from ultralytics import YOLO

                factory = YOLO
            self._model = factory(self.weights)
        return self._model


def _to_rows(value: Any) -> list[list[float]]:
    converted = value.detach().cpu().tolist() if hasattr(value, "detach") else value
    return [list(row) for row in converted]


def _to_values(value: Any) -> list[float]:
    converted = value.detach().cpu().tolist() if hasattr(value, "detach") else value
    return [float(item) for item in converted]
