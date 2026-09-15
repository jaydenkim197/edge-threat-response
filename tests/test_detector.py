import unittest

from edge_threat_response.detector import (
    CallableBackend,
    CompositeDetector,
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


if __name__ == "__main__":
    unittest.main()
