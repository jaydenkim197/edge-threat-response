import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.domain import FrameStatus
from edge_threat_response.replay import load_detection_replay


ROOT = Path(__file__).resolve().parents[1]


class ReplayTests(unittest.TestCase):
    def test_loads_valid_and_missing_frames(self):
        frames = load_detection_replay(ROOT / "tests/fixtures/replay/basic.jsonl")

        self.assertEqual(9, len(frames))
        self.assertEqual(FrameStatus.MISSING, frames[3].status)
        self.assertEqual((), frames[3].detections)

    def test_rejects_mixed_sources(self):
        rows = [
            self._row(0, "first"),
            self._row(1, "second"),
        ]
        self.assert_invalid(rows, "one source_id")

    def test_rejects_non_increasing_frame_index(self):
        rows = [self._row(1, "camera"), self._row(1, "camera")]
        self.assert_invalid(rows, "increase strictly")

    def test_rejects_detections_on_missing_frame(self):
        row = self._row(0, "camera")
        row["status"] = "missing"
        row["detections"] = [
            {"label": "knife", "confidence": 0.9, "bbox_xyxy": [0, 0, 1, 1]}
        ]
        self.assert_invalid([row], "Non-valid frames")

    def assert_invalid(self, rows, message):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        path = Path(temporary_directory.name) / "replay.jsonl"
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, message):
            load_detection_replay(path)

    @staticmethod
    def _row(frame_index, source_id):
        return {
            "frame_index": frame_index,
            "timestamp_s": float(frame_index),
            "source_id": source_id,
            "status": "valid",
            "detections": [],
        }


if __name__ == "__main__":
    unittest.main()
