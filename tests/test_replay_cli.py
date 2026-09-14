import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from edge_threat_response.replay_cli import main


ROOT = Path(__file__).resolve().parents[1]


class ReplayCliTests(unittest.TestCase):
    def test_runs_selected_modes_and_writes_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "replay-output"
            with redirect_stdout(StringIO()):
                exit_code = main(
                    [
                        "--input",
                        str(ROOT / "tests/fixtures/replay/basic.jsonl"),
                        "--config",
                        str(ROOT / "configs/replay/development.example.json"),
                        "--output-dir",
                        str(output),
                        "--modes",
                        "B0,B3",
                    ]
                )

            self.assertEqual(0, exit_code)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(["B0", "B3"], [run["mode"] for run in summary["runs"]])
            self.assertEqual([0, 7], summary["runs"][0]["event_frame_indices"])
            self.assertEqual([2, 8], summary["runs"][1]["event_frame_indices"])
            self.assertEqual(64, len(summary["runs"][0]["input_sha256"]))
            self.assertEqual(64, len(summary["runs"][0]["config_sha256"]))
            for mode in ("B0", "B3"):
                self.assertTrue((output / mode / "frames.jsonl").is_file())
                self.assertTrue((output / mode / "events.jsonl").is_file())
                self.assertTrue((output / mode / "summary.json").is_file())


if __name__ == "__main__":
    unittest.main()
