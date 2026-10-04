import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from edge_threat_response.detection_evaluation import evaluate_boxes, iou, main
from edge_threat_response.domain import BBox

ROOT = Path(__file__).resolve().parents[1]


class DetectionEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.truth_path = ROOT / "tests/fixtures/evaluation/detection-truth.json"
        self.pred_path = ROOT / "tests/fixtures/evaluation/detection-predictions.jsonl"
        self.policy_path = ROOT / "configs/evaluation/detection-synthetic.example.json"
        self.truth = json.loads(self.truth_path.read_text())
        self.pred = [json.loads(line) for line in self.pred_path.read_text().splitlines()]
        self.policy = json.loads(self.policy_path.read_text())

    def test_confidence_iou_duplicate_small_recall_and_negative_fp(self):
        summary, details = evaluate_boxes(self.truth, self.pred, self.policy)
        self.assertEqual((2, 2, 1), tuple(summary["counts"][key] for key in ("tp", "fp", "fn")))
        self.assertEqual(0.5, summary["precision"])
        self.assertAlmostEqual(2 / 3, summary["recall"])
        self.assertEqual(0.5, summary["small_box_recall"])
        self.assertEqual(1, summary["fp_boxes_per_negative_image"])
        self.assertEqual(1, summary["negative_image_fp_fraction"])
        self.assertEqual([2], details[0]["missed_truth_indices"])
        self.assertEqual(1, iou(BBox(0, 0, 10, 10), BBox(0, 0, 10, 10)))
        self.assertEqual(0, iou(BBox(0, 0, 10, 10), BBox(10, 0, 20, 10)))

    def test_empty_denominators_remain_null(self):
        truth = {**self.truth, "images": [self.truth["images"][1]]}
        pred = [{**self.pred[1], "detections": []}]
        summary, _ = evaluate_boxes(truth, pred, self.policy)
        self.assertIsNone(summary["precision"])
        self.assertIsNone(summary["recall"])
        self.assertIsNone(summary["small_box_recall"])
        self.assertEqual(0, summary["negative_image_fp_fraction"])

    def test_missing_extra_repeated_or_failed_predictions_rejected(self):
        for pred in (self.pred[:1], [*self.pred, self.pred[0]],
                     [*self.pred, {**self.pred[1], "frame_index": 99}],
                     [{**self.pred[0], "status": "missing", "detections": []}, self.pred[1]]):
            with self.subTest(pred=pred), self.assertRaises(ValueError):
                evaluate_boxes(self.truth, pred, self.policy)

    def test_approval_partition_absence_and_dimensions_gates(self):
        for field, value in (("status", "candidates_not_approved"), ("partition", "train")):
            with self.assertRaises(ValueError):
                evaluate_boxes({**self.truth, field: value}, self.pred, self.policy)
        for modify in ("absence", "bounds", "dimensions"):
            truth = copy.deepcopy(self.truth)
            if modify == "absence":
                truth["images"][1].pop("knife_absence_verified")
            elif modify == "bounds":
                truth["images"][0]["knife_boxes_xyxy"][0][0] = -1
            else:
                truth["images"][0]["width"] = True
            with self.assertRaises(ValueError):
                evaluate_boxes(truth, self.pred, self.policy)
        with self.assertRaises(ValueError):
            evaluate_boxes(self.truth, self.pred, {**self.policy, "iou": float("nan")})
        with self.assertRaises(ValueError):
            evaluate_boxes({**self.truth, "status": "approved", "partition": "final_test"}, self.pred, self.policy)

    def test_frozen_approved_data_requires_hashes_groups(self):
        truth = copy.deepcopy(self.truth)
        truth.update(status="approved", partition="final_test")
        policy = {**self.policy, "status": "frozen"}
        with self.assertRaises(ValueError):
            evaluate_boxes(truth, self.pred, policy)
        for image in truth["images"]:
            image.update(image_sha256="0" * 64, source_group="synthetic-fixture-only")
        summary, _ = evaluate_boxes(truth, self.pred, policy)
        self.assertEqual("final_test", summary["partition"])

    def test_cli_hashes_and_fresh_output(self):
        with tempfile.TemporaryDirectory() as temp:
            args = ["--ground-truth", str(self.truth_path), "--detections", str(self.pred_path),
                    "--policy", str(self.policy_path), "--output-dir", str(Path(temp) / "out")]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(0, main(args))
            result = json.loads((Path(temp) / "out/summary.json").read_text())
            self.assertEqual(3, len(result["input_sha256"]))
            self.assertEqual("synthetic_contract_check", result["status"])
            with redirect_stderr(io.StringIO()):
                self.assertEqual(2, main(args))
