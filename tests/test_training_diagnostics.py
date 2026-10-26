import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from edge_threat_response.training_diagnostics import diagnose, error_categories


class TrainingDiagnosticTests(unittest.TestCase):
    def setUp(self):
        import test_development_subset
        self.fixture = test_development_subset.DevelopmentSubsetTests()
        self.fixture.setUp()
        self.prepared, _ = self.fixture.prepare()

    def tearDown(self):
        self.fixture.tearDown()

    def fake_model(self, checkpoint):
        class Values(list):
            def tolist(self):
                return list(self)
        class Model:
            names = {0: "knife"}
            def predict(self, source, **kwargs):
                if kwargs["conf"] != .05:
                    raise AssertionError("Use the minimum evaluated threshold as prediction floor")
                for path in source:
                    yield SimpleNamespace(path=path, boxes=SimpleNamespace(cls=Values([0]), conf=Values([.9]), xyxy=Values([[10,20,30,40]])))
        return Model()

    def test_diagnosis_uses_train_val_only_preserves_inputs_and_marks_scope(self):
        from PIL import Image
        actual_open = Image.open
        seen = []
        def guarded_open(path, *args, **kwargs):
            self.assertNotIn("/images/test/", Path(path).as_posix())
            seen.append(str(path))
            return actual_open(path, *args, **kwargs)
        output = self.fixture.root / "diagnostics"
        before = (self.prepared / "DEV-manifest.jsonl").read_bytes()
        with patch("PIL.Image.open", side_effect=guarded_open):
            result = diagnose(self.prepared, self.fixture.checkpoint, output, model_factory=self.fake_model)
        self.assertFalse(result["test_used"])
        self.assertEqual({"train", "val"}, set(result["partitions"]))
        self.assertTrue(seen)
        self.assertEqual(before, (self.prepared / "DEV-manifest.jsonl").read_bytes())
        self.assertTrue((output / "val-page-01.jpg").is_file())
        self.assertEqual("development_image_boxes", result["partitions"]["val"]["sweep"][0]["status"])
        with self.assertRaises(ValueError):
            diagnose(self.prepared, self.fixture.checkpoint, output, model_factory=self.fake_model)

    def test_error_categories_separate_confidence_location_and_absence(self):
        truth = {"images": [{"source_id": "x", "width":100, "height":100,
                 "knife_boxes_xyxy": [[0,0,10,10],[20,0,30,10],[40,0,50,10],[70,70,80,80]]}]}
        predictions = [{"source_id":"x","frame_index":0,"detections":[
            {"confidence":.9,"bbox_xyxy":[0,0,10,10]}, {"confidence":.1,"bbox_xyxy":[20,0,30,10]},
            {"confidence":.9,"bbox_xyxy":[40,0,44,10]}]}]
        result = error_categories(truth, predictions)
        self.assertEqual(["detected","low_confidence","localization","missed"], [row["category"] for row in result])

    def test_wrong_image_alignment_is_rejected(self):
        original = self.fake_model
        def factory(path):
            model = original(path)
            predict = model.predict
            def wrong(**kwargs):
                for item in predict(**kwargs):
                    item.path = "wrong.jpg"
                    yield item
            model.predict = wrong
            return model
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            diagnose(self.prepared, self.fixture.checkpoint, self.fixture.root / "bad", model_factory=factory)
