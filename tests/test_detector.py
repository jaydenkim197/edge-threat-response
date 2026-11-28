import sys
import unittest
from contextlib import nullcontext
from threading import Barrier, get_ident
from types import SimpleNamespace
from unittest.mock import Mock, patch

from edge_threat_response.cuda_graph import FixedCudaGraphForward
from edge_threat_response.detector import (
    CallableBackend,
    CompositeDetector,
    CudaParallelCompositeDetector,
    MappedDetector,
    RawDetection,
    UltralyticsBackend,
)
from edge_threat_response.domain import FrameStatus


class DetectorAdapterTests(unittest.TestCase):
    def test_maps_model_local_classes_and_ignores_unmapped_classes(self):
        backend = CallableBackend(
            lambda image: (
                RawDetection(0, 0.9, (1, 2, 10, 20)),
                RawDetection(43, 0.8, (2, 3, 9, 18)),
            )
        )
        detector = MappedDetector("person", backend, {0: "person"})

        result = detector.infer(object())

        self.assertEqual(FrameStatus.VALID, result.status)
        self.assertEqual(("person",), tuple(item.label for item in result.detections))
        self.assertEqual("person:0", result.detections[0].detection_id)

    def test_composite_fails_closed_when_a_required_component_errors(self):
        person = MappedDetector(
            "person",
            CallableBackend(lambda image: (RawDetection(0, 0.9, (1, 2, 10, 20)),)),
            {0: "person"},
        )

        def fail(_image):
            raise RuntimeError("knife runtime unavailable")

        knife = MappedDetector("knife", CallableBackend(fail), {0: "knife"})

        result = CompositeDetector((person, knife)).infer(object())

        self.assertEqual(FrameStatus.DETECTOR_ERROR, result.status)
        self.assertEqual((), result.detections)
        self.assertIn("knife runtime unavailable", result.error)

    def test_cuda_parallel_warms_serially_preserves_order_and_drains_errors(self):
        streams = (Mock(), Mock())
        owner = get_ident()
        barrier = Barrier(2, timeout=5)
        calls = {"person": [], "knife": []}

        def predict(_image, label):
            calls[label].append(get_ident())
            if len(calls[label]) == 1 and label == "knife":
                raise RuntimeError("temporary startup fault")
            if get_ident() != owner:
                barrier.wait()
            return (RawDetection(0, .9, (1, 2, 10, 20)),)

        cuda = SimpleNamespace(is_available=lambda: True, Stream=Mock(side_effect=streams),
                               current_stream=Mock(return_value=object()), stream=lambda stream: nullcontext())
        with patch.dict(sys.modules, {"torch": SimpleNamespace(cuda=cuda)}):
            person = MappedDetector("p", CallableBackend(lambda image: predict(image, "person")), {0: "person"})
            knife = MappedDetector("k", CallableBackend(lambda image: predict(image, "knife")), {0: "knife"})
            combined = CudaParallelCompositeDetector((person, knife))
        self.addCleanup(combined.close)

        self.assertIs(combined.infer(object()).status, FrameStatus.DETECTOR_ERROR)
        for _ in range(3):
            self.assertIs(combined.infer(object()).status, FrameStatus.VALID)
        self.assertEqual([owner] * 4, calls["person"])
        self.assertEqual([owner] * 4, calls["knife"])
        for stream in streams:
            stream.wait_stream.assert_called_once_with(cuda.current_stream.return_value)

        result = combined.infer(object())
        self.assertEqual(("p:0", "k:0"), tuple(d.detection_id for d in result.detections))
        self.assertEqual(("p", "k"), tuple(key for key, _ in result.component_latencies_ms))
        self.assertNotEqual(calls["person"][-1], calls["knife"][-1])

        streams[0].synchronize.side_effect = RuntimeError("stream fault")
        result = combined.infer(object())
        self.assertIs(result.status, FrameStatus.DETECTOR_ERROR)
        self.assertEqual((), result.detections)
        self.assertIn("p: RuntimeError: stream fault", result.error)
        self.assertEqual(2, streams[1].synchronize.call_count)
        self.assertEqual(calls["person"][-2], calls["person"][-1])
        self.assertEqual(calls["knife"][-2], calls["knife"][-1])
        combined.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            combined.infer(object())

    def test_ultralytics_backend_parses_model_result_without_real_import(self):
        class Values:
            def __init__(self, values):
                self.values = values

            def detach(self):
                return self

            def cpu(self):
                return self

            def tolist(self):
                return self.values

        class Boxes:
            xyxy = Values([[1.0, 2.0, 10.0, 20.0]])
            conf = Values([0.75])
            cls = Values([0.0])

        class Result:
            boxes = Boxes()

        class Model:
            def predict(self, **kwargs):
                return [Result()]

        backend = UltralyticsBackend("fixture.pt", model_factory=lambda _: Model())

        result = tuple(backend.predict("image"))

        self.assertEqual(1, len(result))
        self.assertEqual(0, result[0].class_id)
        self.assertEqual((1.0, 2.0, 10.0, 20.0), result[0].bbox_xyxy)

    def test_explicit_cuda_graph_wraps_only_native_cuda_predictor_once(self):
        for kind, device in (("pt", "cuda"), ("onnx", "cuda"), ("pt", "cpu")):
            with self.subTest(kind=kind, device=device):
                predictor = SimpleNamespace(format=kind, device=SimpleNamespace(type=device), forward=Mock())
                model = SimpleNamespace(predict=Mock(return_value=[]), predictor=SimpleNamespace(model=predictor))
                backend = UltralyticsBackend("fixture.pt", model_factory=lambda _: model, cuda_graph=True)
                if kind == "pt" and device == "cuda":
                    backend.predict("first")
                    hook = predictor.forward
                    backend.predict("second")
                    self.assertIsInstance(hook, FixedCudaGraphForward)
                    self.assertIs(predictor.forward, hook)
                    self.assertFalse(hook.captured)
                    self.assertNotIn("cuda_graph", model.predict.call_args.kwargs)
                else:
                    with self.assertRaisesRegex(ValueError, "native CUDA PyTorch"):
                        backend.predict("first")


if __name__ == "__main__":
    unittest.main()
