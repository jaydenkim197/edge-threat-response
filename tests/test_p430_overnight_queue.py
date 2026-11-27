import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    from p430_overnight_queue import decide, deliver_ensemble, recover
    from p430_followup_actions import replace_reviewed_negatives
    from run_p430_site import replace_tiles, tile_grid, verify_inputs


class OvernightQueueTests(TestCase):
    def test_site_only_verification_accepts_explicit_zero_draw_sources(self):
        plan = {
            "draws": [[("entry", False)]],
            "pool": {"entry": {"domain": "p430", "label_sha256": "label"}},
            "validation": {"tune": ["held"]},
        }
        with (patch("run_p430_site.DRAWS", 1), patch("run_p430_site.EPOCHS", 1),
              patch("run_p430_site.paths", return_value=(Path("image"), Path("label"))),
              patch("run_p430_site.sha", side_effect=("entry", "label"))):
            verify_inputs(Path("."), plan, False, {"p430": 1, "cctv": 0, "m2": 0})

    def test_reviewed_replacements_keep_session_tile_and_class_counts(self):
        pool = {
            "ordinary": {"source_group": "one", "domain": "p430", "n": 0},
            "hard": {"source_group": "one", "domain": "p430", "n": 0},
            "positive": {"source_group": "one", "domain": "p430", "n": 1},
            "other": {"source_group": "two", "domain": "p430", "n": 0},
        }
        fixed = [("ordinary", True), ("positive", False), ("other", False), ("hard", False)]
        baseline = [("ordinary", False)] * 40 + fixed
        deck = [list(baseline), list(baseline)]
        self.assertEqual(replace_reviewed_negatives(deck, pool, ["hard"], .05), [2, 2])
        for epoch in deck:
            self.assertEqual(len(epoch), len(baseline))
            self.assertEqual(epoch[-4:], fixed)
            self.assertEqual(epoch.count(("hard", False)), 3)

    def test_ensemble_requests_distinct_tune_and_dev_filenames(self):
        jobs = {key: {"status": "SKIPPED"} for key in ("A-S", "A-M", "A-P2")}
        jobs["A-N"] = {
            "status": "COMPLETED", "host": "pc11",
            "data": {"local_result": "C:/run/result.json", "result_sha256": "receipt"},
        }
        checkpoint = "ema-batch-1024.pt"
        receipt = {"result": {"tile640": {
            "selected_checkpoint": checkpoint,
            "tune": [{"checkpoint": checkpoint, "predictions_sha256": "tune"}],
            "dev_check": {checkpoint: {"predictions_sha256": "dev_check"}},
        }}}
        options = {"remote_directory": "queue", "nodes": {"pc11": "windows"},
                   "ensemble_approval": "approval.json"}
        with TemporaryDirectory() as directory, \
                patch("p430_overnight_queue.subprocess.run") as run, \
                patch("p430_overnight_queue.read", return_value=receipt), \
                patch("p430_overnight_queue.sha", side_effect=("receipt", "tune", "dev_check")):
            deliver_ensemble(Path(directory), options, jobs)
            sent = [arg for call in run.call_args_list for arg in call.args[0]]
            self.assertIn("pc11:C:/run/tune-tile640-ema-batch-1024.jsonl", sent)
            self.assertIn("pc11:C:/run/dev-tile640-ema-batch-1024.pt.jsonl", sent)
            self.assertIn("pc13:queue/approvals/A-ENSEMBLE.json", sent)

    def test_registered_dependencies_resolve_without_cycles(self):
        registry = json.loads((ROOT / "configs/training/p430-overnight-queue.json").read_text(encoding="utf-8"))
        jobs = {job["id"]: job for job in registry["jobs"]}
        self.assertEqual(len(jobs), len(registry["jobs"]))

        def ancestors(key, active):
            self.assertNotIn(key, active)
            for dependency in jobs[key].get("after", []):
                ancestors(dependency, active | {key})

        for key, job in jobs.items():
            ancestors(key, set())
            for _, subject, *_ in job.get("when", []):
                self.assertIn(subject, job["after"])

    def test_pending_ready_and_skip_use_completed_receipts(self):
        job = {"after": ["X", "Y"], "when": [["win", "X", "Y"]]}
        reference = {"metrics": {"tp": 81, "small": 47, "neg": 0}}
        candidate = {"metrics": {"tp": 90, "small": 49, "neg": 1}}
        self.assertEqual(decide(job, {}, {})[0], "PENDING")
        evidence = {"X": {"status": "COMPLETED", "data": candidate},
                    "Y": {"status": "COMPLETED", "data": reference}}
        self.assertEqual(decide(job, evidence, {})[0], "READY")
        candidate["metrics"]["neg"] = 2
        self.assertEqual(decide(job, evidence, {})[0], "SKIPPED")

    def test_recovery_only_requeues_before_training(self):
        with TemporaryDirectory() as directory:
            record = {"path": directory, "status": "RUNNING", "pid": 42, "attempt": 1}
            with patch("p430_overnight_queue.alive", return_value=False):
                self.assertEqual(recover(record)["status"], "PENDING")
                (Path(directory)/"work.json").write_text("{}")
                self.assertEqual(recover(record)["status"], "FAILED")

    def test_tile_controls_keep_coverage_and_parent_order(self):
        grid = tile_grid(1920, 1080, 512, .40)
        self.assertIn((1408, 568, 1920, 1080), grid)
        self.assertEqual(len(grid), len(set(grid)))
        deck = [("A", True), ("B", False), ("A", False), ("C", False)]
        result = replace_tiles(deck, {"A": {}, "C": {}}, .50)
        self.assertEqual([p[0] for p in result], [p[0] for p in deck])
        self.assertEqual(sum(p[1] for p in result), 2)
