from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    import p430_crop_verifier as verifier


def detection(box, score):
    return {"label": "knife", "bbox_xyxy": box, "confidence": score}


class CropVerifierTests(TestCase):
    def test_failed_tune_gate_never_opens_development_check_partition(self):
        ranks = {"point": {"small_tp": 80, "tp": 100, "negative_frames_flagged": 1, "fp_boxes": 20},
                 "ap50_95": .20}
        snapshot = {"A-MIX70": {"status": "COMPLETED", "data": {
            "checkpoint": "model.pt", "checkpoint_sha256": "model-hash",
        }}}
        with (TemporaryDirectory() as folder,
              patch.object(verifier, "pin_plan", return_value={}),
              patch.object(verifier, "read", side_effect=(snapshot, {})),
              patch.object(verifier, "sha", side_effect=("model-hash", verifier.SOURCE_SHA, "model-hash", "verifier-hash")),
              patch.object(verifier, "jsonl", return_value=[]),
              patch.object(verifier, "reviewed_train_rows", return_value=[{}]),
              patch.object(verifier, "gpu_training_lock"),
              patch.object(verifier, "tile_predictions", return_value=[]),
              patch.object(verifier, "train_classifier", return_value=(
                  SimpleNamespace(tolist=lambda: [0.1]), 0.0, [{"label": 1}]
              )),
              patch.object(verifier, "load_partition", return_value=([], [], {})) as load,
              patch.object(verifier, "feature_logits", return_value=[]),
              patch.object(verifier, "tune", return_value=ranks),
              patch.object(verifier, "save") as save):
            root = Path(folder)
            verifier.run({"base": str(root / "plan"), "node": "pc13"}, root / "shared.json",
                         root / "result", None, None, None)
        self.assertEqual([call.args[-1] for call in load.call_args_list], ["tune"])
        self.assertIsNone(save.call_args.args[-1]["dev_check"])

    def test_keeps_one_matched_proposal_and_ignores_other_boxes_in_positive_frame(self):
        row = {"image_sha256": "positive", "source_video_sha256": "source", "boxes": [(.5, .5, .1, .1)]}
        matched = detection([864, 486, 1056, 594], .8)
        duplicate = detection([863, 486, 1056, 594], .7)
        ambiguous = detection([1000, 486, 1200, 594], .95)
        frame = {"source_id": "positive", "detections": [ambiguous, duplicate, matched]}
        self.assertEqual(verifier.training_proposals(row, frame), [{**matched, "label": 1}])

    def test_ordinary_negative_proposals_are_capped_and_reject_other_frame(self):
        row = {"image_sha256": "empty", "source_video_sha256": "source", "boxes": []}
        proposals = [detection([i, 0, i + 2, 2], conf) for i, conf in enumerate((.3, .9, .8, .7, .009))]
        frame = {"source_id": "empty", "detections": proposals}
        self.assertEqual([entry["confidence"] for entry in verifier.training_proposals(row, frame)], [.9, .8, .7])
        with self.assertRaisesRegex(ValueError, "frame identity"):
            verifier.training_proposals(row, {**frame, "source_id": "other"})

    def test_retains_box_geometry_and_does_not_pick_recall_tradeoff(self):
        prediction = {"source_id": "frame", "detections": [detection([1, 1, 10, 10], .5)]}
        reranked, = verifier.rescore([prediction], [{0: -3.}], .25)
        self.assertEqual(reranked["detections"][0]["bbox_xyxy"], [1, 1, 10, 10])
        self.assertLess(reranked["detections"][0]["confidence"], .5)
        self.assertEqual(prediction["detections"][0]["confidence"], .5)
        base = {"point": {"small_tp": 80, "tp": 100, "negative_frames_flagged": 1, "fp_boxes": 20}, "ap50_95": .20}
        self.assertFalse(verifier.improved(base, {**base, "point": {**base["point"], "small_tp": 79, "tp": 102}}))
        self.assertTrue(verifier.improved(base, {**base, "point": {**base["point"], "fp_boxes": 18}}))
