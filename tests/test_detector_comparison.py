import importlib.util
import math
import unittest

from edge_threat_response.detector_comparison import (
    canonical_prediction, coco_metrics, paired_group_recall_interval,
    select_f2_operating_point,
)


def fixture():
    images = [{"source_id": str(i), "frame_index": 0, "image_sha256": str(i)*64,
               "source_group": "group-"+str(i), "width": 100, "height": 100,
               "knife_boxes_xyxy": [[10, 10, 30, 30]], "knife_absence_verified": False}
              for i in [1, 2]]
    truth = {"schema_version": 1, "status": "development_authorized", "partition": "tuning", "images": images}
    perfect = [canonical_prediction(x, [[10, 10, 30, 30]], [.8], [49], 49)[0] for x in images]
    empty = [canonical_prediction(x, [], [], [], 49)[0] for x in images]
    return truth, perfect, empty


class DetectorComparisonTests(unittest.TestCase):
    def test_f2_threshold_uses_tuning_and_rewards_recall_without_final_selection(self):
        truth, perfect, _ = fixture()
        perfect[1]["detections"][0]["confidence"] = .2
        result = select_f2_operating_point(truth, perfect)
        self.assertEqual(1, result["selected"]["f2"])
        self.assertLessEqual(result["selected"]["confidence"], .2)
        self.assertFalse(result["final_detector_selected"])
        truth["partition"] = "final_test"
        with self.assertRaisesRegex(ValueError, "tuning"):
            select_f2_operating_point(truth, perfect)
    def test_sparse_class_map_and_boundary_clipping(self):
        image = fixture()[0]["images"][0]
        row, adjusted = canonical_prediction(image, [[-2, 10, 30, 102], [10, 10, 30, 30]], [.8, .9], [49, 43], 49)
        self.assertEqual(row["detections"], [{"label": "knife", "confidence": .8, "bbox_xyxy": [0., 10., 30., 100.]}])
        self.assertEqual(adjusted, 1)

    def test_invalid_outputs_fail_instead_of_becoming_misses(self):
        image = fixture()[0]["images"][0]
        for scores, classes in [([math.nan], [49]), ([1.1], [49]), ([.8], [49.5])]:
            with self.assertRaises(ValueError):
                canonical_prediction(image, [[10, 10, 30, 30]], scores, classes, 49)
        with self.assertRaises(ValueError):
            canonical_prediction(image, [], [.8], [49], 49)

    def test_paired_bootstrap_has_correct_sign_and_reproducibility(self):
        truth, perfect, empty = fixture()
        result = paired_group_recall_interval(truth, perfect, empty, repetitions=100)
        self.assertEqual(result["delta_recall"], 1)
        self.assertEqual(result["ci95"], [1, 1])
        self.assertEqual(result, paired_group_recall_interval(truth, perfect, empty, repetitions=100))
        self.assertEqual(paired_group_recall_interval(truth, empty, perfect)["ci95"], [-1, -1])

    def test_one_positive_group_does_not_claim_uncertainty_estimate(self):
        truth, perfect, empty = fixture()
        truth["images"][1]["source_group"] = truth["images"][0]["source_group"]
        self.assertIsNone(paired_group_recall_interval(truth, perfect, empty)["ci95"])

    @unittest.skipUnless(importlib.util.find_spec("ultralytics"), "optional detector environment")
    def test_default_predict_can_remove_a_valid_secondary_knife_class(self):
        import torch
        from ultralytics.utils.nms import non_max_suppression
        # One anchor: class0=.9, target knife class1=.8. Native val keeps
        # secondary-class candidates; default predict keeps only the winner.
        raw = torch.tensor([[[20.], [20.], [20.], [20.], [.9], [.8]]])
        single = non_max_suppression(raw.clone(), .001, .7, classes=[1], nc=2, multi_label=False, end2end=False)
        multiple = non_max_suppression(raw.clone(), .001, .7, classes=[1], nc=2, multi_label=True, end2end=False)
        self.assertEqual(len(single[0]), 0)
        self.assertEqual(len(multiple[0]), 1)
        self.assertEqual(int(multiple[0][0, 5]), 1)

    @unittest.skipUnless(importlib.util.find_spec("pycocotools"), "optional comparison environment")
    def test_coco_perfect_and_no_detections(self):
        truth, perfect, empty = fixture()
        self.assertAlmostEqual(coco_metrics(truth, perfect)["ap50_95"], 1)
        self.assertEqual(coco_metrics(truth, empty)["ap50_95"], 0)

    @unittest.skipUnless(importlib.util.find_spec("pycocotools"), "optional comparison environment")
    def test_missing_prediction_or_final_claim_rejected(self):
        truth, perfect, _ = fixture()
        with self.assertRaises(ValueError):
            coco_metrics(truth, perfect[:1])
        truth["partition"] = "final_test"
        with self.assertRaises(ValueError):
            coco_metrics(truth, perfect)


if __name__ == "__main__":
    unittest.main()
