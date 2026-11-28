from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
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
        return self._combine(tuple(component.infer(image) for component in self.components))

    @staticmethod
    def _combine(results: tuple[DetectorInference, ...]) -> DetectorInference:
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


class CudaParallelCompositeDetector(CompositeDetector):
    """Replay native CUDA Graphs on separate streams after serial initialization."""

    def __init__(self, components: Iterable[MappedDetector]) -> None:
        super().__init__(components)
        import torch

        if not torch.cuda.is_available():
            raise ValueError("Parallel CUDA detectors require an available CUDA device.")
        self._cuda = torch.cuda
        self._streams = tuple(self._cuda.Stream(device=0) for _ in self.components)
        self._pools = tuple(ThreadPoolExecutor(max_workers=1, thread_name_prefix="etr-cuda-detector")
                            for _ in self.components)
        self._warmup_remaining = 3
        self._lock = Lock()
        self._closed = False

    def infer(self, image: Any) -> DetectorInference:
        with self._lock:
            if self._closed:
                raise RuntimeError("Parallel CUDA detector is closed.")
            if self._warmup_remaining:
                # The first frame installs graph wrappers. The next captures and the third replays.
                result = super().infer(image)
                if result.status is FrameStatus.VALID:
                    self._warmup_remaining -= 1
                    if not self._warmup_remaining:
                        current = self._cuda.current_stream(device=0)
                        for stream in self._streams:
                            stream.wait_stream(current)
                return result
            futures = []
            try:
                for pool, component, stream in zip(self._pools, self.components, self._streams, strict=True):
                    futures.append(pool.submit(self._infer_component, component, stream, image))
                return self._combine(tuple(future.result() for future in futures))
            finally:
                wait(futures)

    def _infer_component(self, component: MappedDetector, stream: Any, image: Any) -> DetectorInference:
        started = time.perf_counter()
        try:
            try:
                with self._cuda.stream(stream):
                    return component.infer(image)
            finally:
                stream.synchronize()
        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return DetectorInference(status=FrameStatus.DETECTOR_ERROR, detections=(), inference_ms=elapsed,
                                     component_latencies_ms=((component.component_id, elapsed),),
                                     error=f"{component.component_id}: {type(exc).__name__}: {exc}")

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for pool in self._pools:
                pool.shutdown(wait=True)


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
        cuda_graph: bool = False,
    ) -> None:
        self.weights = str(weights)
        self.predict_arguments = dict(predict_arguments or {})
        self._model_factory = model_factory
        self._model: Any | None = None
        self._install_cuda_graph = cuda_graph

    def predict(self, image: Any) -> Iterable[RawDetection]:
        arguments = {"verbose": False, **self.predict_arguments}
        results = self._predict(image, arguments)
        if not results:
            return ()
        return _raw_detections(results[0])

    def predict_batch(self, images: list[Any]) -> tuple[tuple[RawDetection, ...], ...]:
        arguments = {"verbose": False, **self.predict_arguments, "batch": len(images)}
        results = self._predict(images, arguments)
        if len(results) != len(images):
            raise RuntimeError("Ultralytics returned a different number of results than input images.")
        return tuple(_raw_detections(result) for result in results)

    def _predict(self, source: Any, arguments: dict[str, object]) -> Any:
        model = self._get_model()
        results = model.predict(source=source, **arguments)
        if self._install_cuda_graph:
            from .cuda_graph import FixedCudaGraphForward

            backend = model.predictor.model
            if backend.format != "pt" or backend.device.type != "cuda":
                raise ValueError("CUDA Graph requires a native CUDA PyTorch detector.")
            backend.forward = FixedCudaGraphForward(backend.forward)
            self._install_cuda_graph = False
        return results

    def _get_model(self) -> Any:
        if self._model is None:
            factory = self._model_factory
            if factory is None:
                from ultralytics import YOLO

                factory = YOLO
            self._model = factory(self.weights)
        return self._model


def _raw_detections(result: Any) -> tuple[RawDetection, ...]:
    boxes = getattr(result, "boxes", None)
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

def _to_rows(value: Any) -> list[list[float]]:
    converted = value.detach().cpu().tolist() if hasattr(value, "detach") else value
    return [list(row) for row in converted]


def _to_values(value: Any) -> list[float]:
    converted = value.detach().cpu().tolist() if hasattr(value, "detach") else value
    return [float(item) for item in converted]
