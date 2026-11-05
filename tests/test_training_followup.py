import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.training import _sha256_file


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("raw_followup", ROOT/"tools/finish_raw_training.py")
followup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(followup)


class TrainingFollowupTests(unittest.TestCase):
    def test_failed_or_different_queue_never_starts_evaluation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            queue = root/"queue.json"
            queue.write_text(json.dumps({"suite_id": "test-queue"}))
            state = root/"runs/training/test-queue-queue-state.json"
            state.parent.mkdir(parents=True)
            state.write_text(json.dumps({"queue_sha256": _sha256_file(queue), "status": "failed"}))
            with self.assertRaisesRegex(RuntimeError, "queue failed"):
                followup.finish(root, queue, root/"failed-output", .01)
            result = json.loads((root/"failed-output/state.json").read_text())
            self.assertEqual("failed", result["status"])
            self.assertFalse((root/"failed-output/ap").exists())
            state.write_text(json.dumps({"queue_sha256": "0"*64, "status": "passed"}))
            with self.assertRaisesRegex(ValueError, "identity changed"):
                followup.finish(root, queue, root/"mismatch-output", .01)
            self.assertFalse((root/"mismatch-output/ap").exists())


if __name__ == "__main__":
    unittest.main()
