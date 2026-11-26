import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    from p430_overnight_queue import decide, recover
    from run_p430_site import replace_tiles, tile_grid


class OvernightQueueTests(TestCase):
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
