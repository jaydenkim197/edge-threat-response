from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from edge_threat_response.p430_workflow import save, sha
from edge_threat_response.replay import write_jsonl


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    import p430_dev_fusion as fusion


def frame(image_id, *boxes):
    return {
        "source_id": image_id, "frame_index": 0, "timestamp_s": 0, "status": "valid",
        "detections": [{"label": "knife", "confidence": score, "bbox_xyxy": box} for score, box in boxes],
    }


class DevelopmentFusionTests(TestCase):
    def test_agreement_keeps_supported_scores_and_penalizes_disjoint_boxes(self):
        a = frame("image", (.9, [0, 0, 10, 10]), (.4, [100, 100, 110, 110]))
        b = frame("image", (.6, [1, 0, 11, 10]), (.001, [20, 20, 30, 30]))
        with patch.object(fusion, "merge") as merge:
            fusion.fuse([a], [b], True)
        left, right = merge.call_args.args
        self.assertEqual([p["confidence"] for p in left[0]["detections"]], [.9, .2])
        self.assertEqual([p["confidence"] for p in right[0]["detections"]], [.6, .001])
        self.assertEqual(a["detections"][1]["confidence"], .4)
        self.assertEqual(b["detections"][1]["confidence"], .001)

    def test_only_selected_fusion_reaches_dev_and_uses_tune_threshold(self):
        rows = {"tune": [], "dev_check": []}
        predictions = {name: {"tune": [frame("tune")], "dev_check": [frame("dev")]} for name in fusion.MODELS}
        points = [dict(confidence=.2, small_tp=i, tp=i, fp_boxes=0, negative_frames_flagged=0)
                  for i in (1, 2, 3, 9, 4, 5, 6)]
        scores = [{"point": point, "ap50_95": 0.0} for point in points]
        with (patch.object(fusion, "fuse", side_effect=lambda a, b, agreement: a) as combine,
              patch.object(fusion, "tune", side_effect=scores) as evaluate_tune,
              patch.object(fusion, "coverage", return_value=set()),
              patch.object(fusion, "locked", return_value={"tp": 5}) as evaluate_dev,
              patch.object(fusion, "coco_metrics", return_value={})):
            report, _ = fusion.research(rows, predictions)
        self.assertEqual(report["selected_fusion"], "D1+MIX70/NMS")
        self.assertEqual([call.args[0][0]["source_id"] for call in combine.call_args_list], ["tune"] * 4 + ["dev"])
        self.assertTrue(all(call.args[0] is rows["tune"] for call in evaluate_tune.call_args_list))
        self.assertEqual(evaluate_dev.call_args.args[-1], .2)
        self.assertEqual(set(report["dev_check"]), {*fusion.MODELS, "D1+MIX70/NMS"})

    def test_load_predictions_requires_the_exact_checkpoint_suffix_and_receipt_hashes(self):
        with TemporaryDirectory() as folder:
            run = Path(folder)
            tune = run / "tune-tile640-best.jsonl"
            dev = run / "dev-tile640-best.pt.jsonl"
            write_jsonl(tune, [frame("tune")])
            write_jsonl(dev, [frame("dev")])
            receipt = run / "result.json"
            save(receipt, {"scope": "development", "result": {"tile640": {
                "selected_checkpoint": "best.pt",
                "tune": [{"checkpoint": "best.pt", "checkpoint_sha256": "test", "predictions_sha256": sha(tune)}],
                "dev_check": {"best.pt": {"checkpoint_sha256": "test", "predictions_sha256": sha(dev),
                                         "threshold_source": "tune"}},
            }}})
            snapshot = {"status": "COMPLETED", "data": {"result_sha256": sha(receipt), "checkpoint_sha256": "test"}}
            rows = {"tune": [{"image_sha256": "tune"}], "dev_check": [{"image_sha256": "dev"}]}
            predictions, evidence = fusion.load_predictions("A-MIX70", snapshot, run, rows)
            self.assertEqual(predictions["dev_check"], [frame("dev")])
            self.assertEqual(evidence["predictions"]["dev_check"], sha(dev))
            write_jsonl(dev, [frame("wrong-image")])
            with self.assertRaisesRegex(ValueError, "prediction hash mismatch"):
                fusion.load_predictions("A-MIX70", snapshot, run, rows)
