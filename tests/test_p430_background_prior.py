import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    import p430_background_prior as prior


def tuning_point(*, small=98, total=129, negatives=1, boxes=12, confidence=.3):
    return {"point": {"small_tp": small, "tp": total, "negative_frames_flagged": negatives,
                      "fp_boxes": boxes, "confidence": confidence}, "ap50_95": .4}


class BackgroundPriorTests(TestCase):
    def test_rescore_penalizes_only_overlapping_boxes_without_moving_them(self):
        frame = {"detections": [{"bbox_xyxy": [1, 2, 11, 12], "confidence": .8},
                                {"bbox_xyxy": [30, 31, 40, 42], "confidence": .7}]}
        updated, effect = prior.penalize([frame], [prior.BBox(2, 2, 11, 12)], .5)
        self.assertEqual([box["confidence"] for box in updated[0]["detections"]], [.4, .7])
        self.assertEqual([box["bbox_xyxy"] for box in updated[0]["detections"]],
                         [box["bbox_xyxy"] for box in frame["detections"]])
        self.assertEqual(frame["detections"][0]["confidence"], .8)
        self.assertEqual(effect, {"affected_boxes": 1, "affected_frames": 1})

    def test_promotion_requires_strict_gain_and_no_regression_in_each_count(self):
        control = tuning_point()
        self.assertFalse(prior.improves(control, control))
        self.assertFalse(prior.improves(control, tuning_point(total=130, boxes=13)))
        self.assertFalse(prior.improves(control, tuning_point(total=128, negatives=0)))
        self.assertFalse(prior.improves(control, tuning_point(small=97, boxes=11)))
        self.assertTrue(prior.improves(control, tuning_point(boxes=11)))

    def test_recurrent_observations_must_remain_in_confirmed_train_negatives(self):
        item = {"nearby_overlapping_frames": 1, "image_sha256": "image", "source_sha256": "frame",
                "source_video_sha256": "video", "label_sha256": "negative-label",
                "review_scope": prior.CENTER_REVIEW_SCOPE, "review_version": 1, "bbox_xyxy": [1, 2, 11, 12]}
        release = {"schema_version": 1, "scope": "development_train_review_candidates",
                   "base_plan_sha256": prior.PLAN_SHA, "reviewed_manifest_sha256": prior.SOURCE_SHA,
                   "inference": "native-tile640", "detector_sha256": "checkpoint",
                   "candidates": [item, {"nearby_overlapping_frames": 0}]}
        pool = {"image": {"domain": "p430", "n": 0, "source_group": "video", "label_sha256": "negative-label"}}
        protection = {"edited_sha256": "final"}
        plan = {"validation": {"tune": ["tune"], "dev_check": ["dev"]}, "pool": pool}
        self.assertEqual(prior.recurrent_locations(release, plan, protection, "checkpoint"),
                         [prior.BBox(1, 2, 11, 12)])
        plan["validation"]["dev_check"] = ["image"]
        with self.assertRaisesRegex(ValueError, "outside verified"):
            prior.recurrent_locations(release, plan, protection, "checkpoint")

    def test_failed_tune_gate_preserves_dev_check_unopened(self):
        self.check_gate(tuning_point(), None)

    def test_tune_gain_persists_lock_and_reuses_the_locked_cutoff(self):
        self.check_gate(tuning_point(boxes=11, confidence=.2), .75)

    def check_gate(self, candidate, expected_multiplier):
        snapshot = {"A-MIX70": {"status": "COMPLETED", "data": {"checkpoint_sha256": "checkpoint"}}}
        points = (tuning_point(), candidate, tuning_point())
        with (TemporaryDirectory() as folder,
              patch.object(prior, "pin_plan", return_value={}),
              patch.object(prior, "read", side_effect=(snapshot, {}, {})),
              patch.object(prior, "sha", return_value="valid"),
              patch.object(prior, "recurrent_locations", return_value=[prior.BBox(1, 2, 11, 12)]),
              patch.object(prior, "tune", side_effect=points),
              patch.object(prior, "locked", return_value={"tp": 129}) as locked,
              patch.object(prior, "coco_metrics", return_value={}),
              patch.object(prior, "load_partition") as load):
            root = Path(folder)
            output = root / "result"

            def partition(*args):
                if args[-1] == "dev_check":
                    lock = json.loads((output / "tune-lock.json").read_text(encoding="utf-8"))
                    self.assertEqual(lock["selected_multiplier"], expected_multiplier)
                    self.assertIsNone(lock["dev_check"])
                return [], [], {}

            load.side_effect = partition
            prior.run(root / "work", root / "snapshot", root / "mine", "valid", output)
            result = json.loads((output / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["selected_multiplier"], expected_multiplier)
            if expected_multiplier is None:
                self.assertEqual([call.args[-1] for call in load.call_args_list], ["tune"])
                self.assertIsNone(result["dev_check"])
                self.assertFalse((output / "tune-lock.json").exists())
            else:
                self.assertEqual([call.args[-1] for call in load.call_args_list], ["tune", "dev_check"])
                self.assertEqual([call.args[-1] for call in locked.call_args_list], [.3, .2])
