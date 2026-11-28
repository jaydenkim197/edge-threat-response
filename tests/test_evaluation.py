import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path

from edge_threat_response.evaluation import (
    Alert, Interval, MatchingPolicy, Recording, TruthEvent,
    evaluate_replays, file_sha256, load_ground_truth, score_recording,
)
from edge_threat_response.evaluate_cli import main as evaluate_main
from edge_threat_response.replay_cli import main as replay_main


ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "tests/fixtures/evaluation/ground-truth.json"
POLICY = ROOT / "configs/evaluation/synthetic.example.json"


class EventEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.policy = MatchingPolicy("zero", "synthetic_only", 0, 0)
        self.recording = Recording("clip", "session", "camera", "pilot", "N5", Interval(0, 10),
                                   (TruthEvent("one", Interval(2, 4)), TruthEvent("two", Interval(6, 8))), ())

    def test_counts_duplicates_background_misses_and_latency(self):
        result = score_recording(self.recording, (Alert("a", 2.5), Alert("repeat", 3), Alert("background", 9)), self.policy)
        self.assertEqual((1, 2, 1), (result["tp"], result["fp"], result["fn"]))
        self.assertEqual(1, result["duplicate_alerts"])
        self.assertEqual(1, result["background_false_alerts"])
        self.assertEqual(6, result["negative_duration_s"])
        self.assertAlmostEqual(1/3, result["metrics"]["event_precision"])
        self.assertEqual(0.5, result["metrics"]["event_recall"])
        self.assertEqual(720, result["metrics"]["false_alerts_per_scored_hour"])
        self.assertEqual(600, result["metrics"]["background_false_alerts_per_negative_hour"])
        self.assertEqual(0.5, result["metrics"]["latency"]["mean_s"])

    def test_boundaries_tolerance_and_signed_early_confirmation(self):
        result = score_recording(self.recording, (Alert("early", 1.9), Alert("start", 2), Alert("end", 4)), self.policy)
        self.assertEqual("start", result["matches"][0]["prediction_event_id"])
        self.assertEqual(2, result["background_false_alerts"])
        policy = MatchingPolicy("padded", "development", 0.2, 0.3)
        padded = score_recording(self.recording, (Alert("early", 1.9), Alert("end", 4)), policy)
        self.assertEqual(1, padded["duplicate_alerts"])
        self.assertAlmostEqual(-0.1, padded["metrics"]["latency"]["mean_s"])
        self.assertEqual(1, padded["metrics"]["latency"]["early_confirmation_count"])

    def test_overlapping_tolerance_windows_preserve_one_to_one_matching(self):
        recording = Recording("clip", "session", "camera", "pilot", "P3", Interval(0, 10),
                              (TruthEvent("first", Interval(2, 3)), TruthEvent("second", Interval(3.1, 4))), ())
        result = score_recording(recording, (Alert("a", 2.5), Alert("b", 3.2)), MatchingPolicy("padded", "development", 1, 1))
        self.assertEqual(2, result["tp"])
        self.assertEqual(["first", "second"], [match["truth_event_id"] for match in result["matches"]])

    def test_negative_empty_runs_are_undefined_not_perfect_scores(self):
        recording = Recording("clip", "session", "camera", "pilot", "N1", Interval(0, 10), (), ())
        empty = score_recording(recording, (), self.policy)
        self.assertIsNone(empty["metrics"]["event_precision"])
        self.assertIsNone(empty["metrics"]["event_recall"])
        self.assertIsNone(empty["metrics"]["event_f1"])
        self.assertIsNone(empty["metrics"]["latency"]["mean_s"])
        false = score_recording(recording, (Alert("a", 1),), self.policy)
        self.assertEqual(0, false["metrics"]["event_precision"])
        self.assertIsNone(false["metrics"]["event_recall"])

    def test_ignore_time_is_removed_from_alerts_and_exposure(self):
        recording = Recording("clip", "session", "camera", "pilot", "N5", Interval(0, 10),
                              self.recording.events, (Interval(9, 10),))
        result = score_recording(recording, (Alert("a", 2), Alert("ambiguous", 9.5)), self.policy)
        self.assertEqual(1, result["ignored_alerts"])
        self.assertEqual(9, result["scored_duration_s"])
        self.assertEqual(5, result["negative_duration_s"])
        self.assertEqual(0, result["fp"])

    def test_rejects_nonfinite_duplicates_and_out_of_recording_alerts(self):
        with self.assertRaises(ValueError):
            Alert("a", float("nan"))
        with self.assertRaises(ValueError):
            score_recording(self.recording, (Alert("a", 10),), self.policy)
        with self.assertRaises(ValueError):
            score_recording(self.recording, (Alert("a", 2), Alert("a", 3)), self.policy)

    def test_manual_annotation_rejects_session_leakage_and_ambiguous_positive_overlap(self):
        document = json.loads(TRUTH.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "truth.json"
            second = {**document["recordings"][0], "recording_id": "other", "source_id": "other", "partition": "final_test"}
            document["recordings"].append(second)
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "session"):
                load_ground_truth(path)
            document["recordings"][0]["leakage_group_id"] = "shared-group"
            document["recordings"][1].update(session_id="independent-name", leakage_group_id="shared-group")
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "group"):
                load_ground_truth(path)
            document["recordings"].pop()
            document["recordings"][0]["ignore_intervals"] = [{"start_s": 0.2, "end_s": 0.4, "reason": "ambiguous"}]
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "overlaps"):
                load_ground_truth(path)

    def test_real_replay_to_evaluation_and_provenance_tamper_detection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            replay = root / "replay"
            detections = ROOT / "tests/fixtures/replay/basic.jsonl"
            config = ROOT / "configs/replay/development-v2.example.json"
            with redirect_stdout(StringIO()):
                replay_main(["--input", str(detections), "--config", str(config), "--output-dir", str(replay)])
            manifest = root / "bindings.json"
            manifest.write_text(json.dumps({"schema_version": 1, "recordings": [
                {"recording_id": "fixture-recording", "detections": str(detections), "pipeline_config": str(config), "replay_dir": "replay"}]}))
            result = evaluate_replays(TRUTH, manifest, POLICY)
            scores = {row["mode"]: row for row in result["comparison"]}
            self.assertEqual((1, 1, 1), (scores["B0"]["tp"], scores["B0"]["fp"], scores["B0"]["fn"]))
            for mode in ("B1", "B2", "B3"):
                self.assertEqual((2, 0, 0), (scores[mode]["tp"], scores[mode]["fp"], scores[mode]["fn"]))
            self.assertAlmostEqual(0.1, scores["B3"]["metrics"]["latency"]["mean_s"])
            output = root / "evaluation"
            args = ["--ground-truth", str(TRUTH), "--replay-manifest", str(manifest), "--policy", str(POLICY), "--output-dir", str(output)]
            with redirect_stdout(StringIO()):
                self.assertEqual(0, evaluate_main(args))
            self.assertTrue((output / "comparison.csv").exists())
            with redirect_stderr(StringIO()):
                self.assertEqual(2, evaluate_main(args))
            summary = replay / "B3/summary.json"
            data = json.loads(summary.read_text(encoding="utf-8"))
            data["input_sha256"] = "0" * 64
            summary.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "provenance"):
                evaluate_replays(TRUTH, manifest, POLICY)

    def test_controlled_final_test_binds_frozen_detector_and_approval(self):
        truth = json.loads(TRUTH.read_text(encoding="utf-8"))
        truth["data_kind"] = "controlled"
        video_hash, config_hash, weight_hash = "a" * 64, "b" * 64, "c" * 64
        truth["recordings"][0].update(partition="final_test", video_sha256=video_hash,
                                      annotator_id="author", boundary_check_id="reviewer")
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            truth_path = root / "truth.json"
            truth_path.write_text(json.dumps(truth), encoding="utf-8")
            policy_path = root / "policy.json"
            policy_path.write_text(json.dumps({**policy, "status": "development"}), encoding="utf-8")
            manifest = root / "bindings.json"
            with self.assertRaisesRegex(ValueError, "requires a frozen matching policy"):
                evaluate_replays(truth_path, manifest, policy_path)
            policy_path.write_text(json.dumps({**policy, "status": "frozen"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires a freeze receipt"):
                evaluate_replays(truth_path, manifest, policy_path)

            detections = root / "detections.jsonl"
            detections.write_bytes((ROOT / "tests/fixtures/replay/basic.jsonl").read_bytes())
            config = ROOT / "configs/replay/development-v2.example.json"
            sampling = {"sample_hz": 4.0}
            provenance = {"input": {"sha256": video_hash}, "detector_config": {"sha256": config_hash},
                          "weights": [{"component_id": "knife", "sha256": weight_hash}], "sampling": sampling,
                          "max_frames": None}
            summary = root / "summary.json"
            detection_receipt = {"schema_version": 1, "frame_count": 9, "detections_sha256": file_sha256(detections)}
            summary.write_text(json.dumps({**detection_receipt, "provenance": provenance}), encoding="utf-8")
            with redirect_stdout(StringIO()):
                self.assertEqual(0, replay_main(["--input", str(detections), "--config", str(config),
                                                "--output-dir", str(root / "replay")]))
            manifest.write_text(json.dumps({"schema_version": 1, "recordings": [
                {"recording_id": "fixture-recording", "detections": str(detections),
                 "pipeline_config": str(config), "replay_dir": "replay"}]}), encoding="utf-8")
            receipt_path = root / "freeze.json"
            receipt = {"schema_version": 1, "status": "frozen", "candidate_id": "fixture-detector",
                       "approved_by_alias": "authority", "final_evaluator_alias": "reviewer",
                       "code_commit": "fixture-code", "frozen_at_kst": "2026-11-29T12:00:00+09:00",
                       "approval_receipt_sha256": "d" * 64, "protected_source_and_edit_lineage_receipt_sha256": "e" * 64,
                       "approved_event_gt_sha256": file_sha256(truth_path),
                       "event_annotation_version": truth["annotation_version"], "matching_policy_sha256": file_sha256(policy_path),
                       "pipeline_config_sha256": file_sha256(config), "detector_config_sha256": config_hash,
                       "detection_input_sampling": sampling, "final_eval_modes": ["B0", "B1", "B2", "B3"],
                       "weights_sha256": {"knife": weight_hash}}
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            result = evaluate_replays(truth_path, manifest, policy_path, freeze_receipt=receipt_path)
            self.assertEqual({"final_test"}, {row["partition"] for row in result["comparison"]})
            self.assertEqual(file_sha256(receipt_path), result["freeze_receipt_sha256"])
            self.assertEqual(file_sha256(summary), result["inputs"][0]["detection_summary_sha256"])
            args = ["--ground-truth", str(truth_path), "--replay-manifest", str(manifest), "--policy", str(policy_path),
                    "--freeze-receipt", str(receipt_path), "--output-dir", str(root / "evaluation")]
            with redirect_stdout(StringIO()):
                self.assertEqual(0, evaluate_main(args))

            for change in ({"max_frames": 9}, {"input": {"sha256": "0" * 64}},
                           {"weights": [{"component_id": "knife", "sha256": "0" * 64}]}):
                with self.subTest(change=change):
                    summary.write_text(json.dumps({**detection_receipt, "provenance": {**provenance, **change}}),
                                       encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Final detection provenance"):
                        evaluate_replays(truth_path, manifest, policy_path, freeze_receipt=receipt_path)
            receipt["approved_event_gt_sha256"] = "0" * 64
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Ground truth or matching policy differs"):
                evaluate_replays(truth_path, manifest, policy_path, freeze_receipt=receipt_path)



if __name__ == "__main__":
    unittest.main()
