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
    def test_mobile_reuses_authenticated_proposals_and_revalidates_train_session(self):
        rows = [
            {"image_sha256": "positive", "session": "s01", "source_video_sha256": "a",
             "boxes": [(.5, .5, .1, .1)]},
            {"image_sha256": "negative", "session": "s02", "source_video_sha256": "b", "boxes": []},
        ]
        examples = [
            {**detection([864, 486, 1056, 594], .75), "label": 1, "image_sha256": "positive", "session": "s01"},
            {**detection([5, 5, 10, 10], .15), "label": 0, "image_sha256": "negative", "session": "s02"},
        ]
        counts = {"1": 1, "0": 1}
        with TemporaryDirectory() as folder, patch.object(verifier, "ARCHIVED_COUNTS", counts):
            root = Path(folder)
            model, receipt = root / "hog-verifier.json", root / "hog-result.json"
            model_record = {"schema_version": 1, "feature": verifier.HOG_FEATURE, "crop_padding_fraction": .125,
                            "minimum_detector_score": verifier.SCORE_MIN, "examples": examples}
            receipt_record = {
                "schema_version": 1, "scope": "p430_development_only", "experiment": verifier.HOG_EXPERIMENT,
                "base_plan_sha256": verifier.PLAN_SHA, "reviewed_manifest_sha256": verifier.SOURCE_SHA,
                "baseline_predictions": {"checkpoint_sha256": "checkpoint"}, "train_proposal_counts": counts,
                "train_proposal_limit_per_image": verifier.MAX_TRAIN_PROPOSALS, "train_positive_match_iou": .5,
            }

            def write_archive():
                verifier.save(model, model_record)
                verifier.save(receipt, {**receipt_record, "crop_verifier_sha256": verifier.sha(model)})
                return verifier.MobileInputs(receipt, verifier.sha(receipt), model, root / "weights", "0" * 64)

            inputs = write_archive()
            actual, _, provenance = verifier.archived_proposals(inputs, rows, "checkpoint")
            self.assertEqual(actual, examples)
            self.assertEqual(provenance["hog_verifier_sha256"], verifier.sha(model))
            model.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                verifier.archived_proposals(inputs, rows, "checkpoint")
            examples[0]["session"] = "wrong-session"
            with self.assertRaisesRegex(ValueError, "reviewed train session"):
                verifier.archived_proposals(write_archive(), rows, "checkpoint")
            examples[0].update(session="s01", bbox_xyxy=[5, 5, 20, 20])
            with self.assertRaisesRegex(ValueError, "mismatched a reviewed positive"):
                verifier.archived_proposals(write_archive(), rows, "checkpoint")

    def test_mobile_gate_rejects_more_false_boxes_and_one_box_only_improvement(self):
        control = {"point": {"small_tp": 80, "tp": 100, "negative_frames_flagged": 1, "fp_boxes": 20}}

        def trial(**changes):
            return {"point": {**control["point"], **changes}}

        self.assertFalse(verifier.mobile_improved(control, trial(tp=101, fp_boxes=21)))
        self.assertFalse(verifier.mobile_improved(control, trial(tp=101, small_tp=79)))
        self.assertFalse(verifier.mobile_improved(control, trial(small_tp=81, tp=99)))
        self.assertFalse(verifier.mobile_improved(control, trial(tp=101, negative_frames_flagged=2)))
        self.assertFalse(verifier.mobile_improved(control, trial(fp_boxes=19)))
        self.assertTrue(verifier.mobile_improved(control, trial(fp_boxes=18)))
        self.assertTrue(verifier.mobile_improved(control, trial(tp=101)))

    def test_mobile_saves_tune_cutoff_before_opening_development_partition(self):
        snapshot = {"A-MIX70": {"status": "COMPLETED", "data": {
            "checkpoint": "model.pt", "checkpoint_sha256": "model-hash",
        }}}
        control = {"point": {"small_tp": 80, "tp": 100, "negative_frames_flagged": 1, "fp_boxes": 20,
                             "confidence": .25}, "ap50_95": .20}
        winner = {**control, "point": {**control["point"], "tp": 101, "confidence": .29}}
        cached = {"predictions": {"tune": "cached-predictions"}}
        model = SimpleNamespace(tolist=lambda: [0.1])
        read, sha = verifier.read, verifier.sha
        with (TemporaryDirectory() as folder,
              patch.object(verifier, "pin_plan", return_value={}),
              patch.object(verifier, "read", side_effect=(snapshot, {})),
              patch.object(verifier, "sha", side_effect=lambda p: {
                  "model.pt": lambda: "model-hash", "manifest.jsonl": lambda: verifier.SOURCE_SHA,
              }.get(p.name, lambda: sha(p))()),
              patch.object(verifier, "jsonl", return_value=[]),
              patch.object(verifier, "reviewed_train_rows", return_value=[{}]),
              patch.object(verifier, "archived_proposals", return_value=([], cached, {})),
              patch.object(verifier, "mobile_backbone", return_value=(object(), "backbone-hash")),
              patch.object(verifier, "mobile_features", return_value={}),
              patch.object(verifier, "fit_logistic", return_value=(model, 0.)),
              patch.object(verifier, "mobile_logits", return_value=[]),
              patch.object(verifier, "tune", side_effect=(control, control, winner)),
              patch.object(verifier, "locked", return_value={}) as fixed,
              patch.object(verifier, "coco_metrics", return_value={}),
              patch.object(verifier, "tile_predictions") as infer,
              patch.object(verifier, "load_partition") as load):
            root = Path(folder)
            output = root / "result"

            def partitions(base, plan, state, run, split):
                if split == "dev_check":
                    self.assertEqual(read(output / "tune-lock.json")["confidence"], .29)
                return [], [], cached

            load.side_effect = partitions
            verifier.run({"base": str(root / "plan"), "node": "pc13"}, root / "shared.json",
                         output, None, None, None, device="cpu", mobile=object())
            infer.assert_not_called()
            self.assertEqual([call.args[-1] for call in fixed.call_args_list], [.25, .29])
            self.assertEqual(read(output / "result.json")["tune_lock_sha256"], sha(output / "tune-lock.json"))

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
