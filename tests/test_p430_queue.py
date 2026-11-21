import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from edge_threat_response.p430_evaluation import capped_selection
from edge_threat_response.p430_queue import Worker, aggregate, choose_noaug, run_child
from edge_threat_response.p430_workflow import read, save, sha


def outcome(baseline, candidate, all_recall=.2, fp=.8):
    return {"eval": {"status": "COMPLETED",
                     "baseline": {"small_recall": baseline, "recall": .2},
                     "selected": {"small_recall": candidate, "recall": all_recall, "fp_negative_per100": fp}}}


class TestP430Queue(unittest.TestCase):
    def test_both_folds_required_and_consistent_lr(self):
        nodes = {"pc11": outcome(.03, .08), "pc12": outcome(.03, .1), "pc13": outcome(.04, .07)}
        self.assertEqual(choose_noaug(nodes)["status"], "PENDING")
        nodes["pc14"] = outcome(.04, .05, all_recall=.17)
        self.assertEqual(choose_noaug(nodes)["lr"], .00005)
        nodes["pc13"] = outcome(.04, .04)
        self.assertEqual(choose_noaug(nodes)["status"], "SKIPPED")

    def test_report_wait_and_freeze_decision(self):
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            values = {n: outcome(.03, .04) for n in ("pc11", "pc12", "pc13", "pc14")}
            self.assertEqual(aggregate(work, values)["lr"], .00005)
            self.assertEqual(aggregate(work, {})["lr"], .00005)
            summary = read(work / "experiment_status.json")
            self.assertEqual(summary["stage_b"], "BLOCKED")
            self.assertEqual(summary["stage_c"], "WAITING_FOR_DATA")
            self.assertFalse(summary["final_detector_selected"])

    def test_failed_child_preserves_exit_receipt(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with patch("edge_threat_response.p430_workflow.main", side_effect=ValueError("bad data")):
                with self.assertRaises(ValueError):
                    run_child(root, "pc11", "train", root, None)
            self.assertEqual(read(root / "exit.json")["code"], 1)
            self.assertFalse((root / "result.json").exists())

    def test_restart_reuses_checked_result_and_rejects_modified_result(self):
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            save(work / "node.json", {})
            run = work / f"{work.name}-pc11-train"
            slot = run / "attempt-01"
            slot.mkdir(parents=True)
            result = slot / "result.json"
            save(result, {"training": "real-subprocess-receipt-fixture"})
            save(slot / "exit.json", {"code": 0, "result_sha256": sha(result)})
            with patch("subprocess.Popen", side_effect=AssertionError("Unexpected re-run")):
                self.assertEqual(Worker(work, "pc11").run_job("train"), slot)
                self.assertEqual(Worker(work, "pc11").run_job("train"), slot)
                result.write_text(json.dumps({"modified": True}))
                self.assertIsNone(Worker(work, "pc11").run_job("train"))
            self.assertEqual(read(work / "worker-status.json")["train"]["status"], "FAILED")

    def test_oom_or_validation_failure_is_terminal(self):
        with tempfile.TemporaryDirectory() as raw:
            work = Path(raw)
            save(work / "node.json", {})
            slot = work / f"{work.name}-pc11-train" / "attempt-01"
            slot.mkdir(parents=True)
            save(slot / "exit.json", {"code": 1})
            with patch("subprocess.Popen", side_effect=AssertionError("Unexpected retry")):
                self.assertIsNone(Worker(work, "pc11").run_job("train"))
                self.assertIsNone(Worker(work, "pc11").run_job("train"))
            self.assertEqual(read(work / "worker-status.json")["train"]["status"], "FAILED")

    def test_threshold_counts_fp_frames_and_keeps_equal_scores_together(self):
        proposals = [{"detections": [{"confidence": .8}, {"confidence": .8}]},
                     {"detections": [{"confidence": .8}]}, {"detections": [{"confidence": .5}]}]
        rows = [{"small": False, "boxes": []}, {"small": True, "boxes": [[0, 0, 1, 1]]},
                {"small": False, "boxes": []}]
        matches = [{"matches": []}, {"matches": [{"prediction_index": 0}]}, {"matches": []}]
        result = capped_selection(proposals, rows, matches, 1)
        self.assertEqual((result["small_tp"], result["negative_frames_flagged"], result["fp_boxes"]), (1, 1, 2))
        self.assertIsNone(capped_selection(proposals, rows, matches, 0)["confidence"])


if __name__ == "__main__":
    unittest.main()
