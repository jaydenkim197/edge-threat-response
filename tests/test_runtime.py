import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.detector import CallableBackend, MappedDetector, RawDetection
from edge_threat_response.media import CurrentFrameSnapshot, FramePacket, IterableFrameSource
from edge_threat_response.runtime import run_detection_stream, run_live_pipeline


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_CONFIG = ROOT / "configs/replay/development-v2.example.json"


class RuntimeIntegrationTests(unittest.TestCase):
    def test_writes_canonical_detection_jsonl(self):
        detector = MappedDetector(
            "knife",
            CallableBackend(lambda image: (RawDetection(0, 0.9, (1, 1, 3, 4)),)),
            {0: "knife"},
        )
        frames = IterableFrameSource((FramePacket(0, 0.0, "fixture", object()),))
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)

            summary = run_detection_stream(frames, detector, output_dir=output)

            row = json.loads((output / "detections.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("valid", row["status"])
            self.assertEqual("knife", row["detections"][0]["label"])
            self.assertEqual(1, summary["detection_count"])
            self.assertTrue(summary["detections_sha256"])

    def test_live_pipeline_binds_real_frame_to_snapshot(self):
        def predictions(image):
            return (
                RawDetection(0, 0.95, (0, 0, 100, 200)),
                RawDetection(1, 0.90, (40, 80, 60, 120)),
            )

        detector = MappedDetector(
            "unified-fixture", CallableBackend(predictions), {0: "person", 1: "knife"}
        )
        frames = IterableFrameSource(
            FramePacket(index, index / 10, "fixture", f"image-{index}")
            for index in range(3)
        )
        config = load_pipeline_config(PIPELINE_CONFIG)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory)
            # Replace OpenCV at the port boundary while retaining the same binding behavior.
            written = []
            original_init = CurrentFrameSnapshot.__init__

            def fixture_init(instance, output_dir, writer=None):
                original_init(
                    instance,
                    output_dir,
                    writer=lambda path, image: written.append((path, image)) is None,
                )

            from unittest.mock import patch

            with patch.object(CurrentFrameSnapshot, "__init__", fixture_init):
                summary = run_live_pipeline(frames, detector, config, output_dir=output)

            self.assertEqual(1, summary["event_count"])
            self.assertEqual(1, len(written))
            event = json.loads((output / "events.jsonl").read_text(encoding="utf-8"))
            self.assertEqual("captured", event["snapshot_status"])


if __name__ == "__main__":
    unittest.main()
