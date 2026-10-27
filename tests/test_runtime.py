import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.detector import CallableBackend, MappedDetector, RawDetection
from edge_threat_response.media import CurrentFrameSnapshot, FramePacket, IterableFrameSource
from edge_threat_response.runtime import _distribution, run_detection_stream, run_live_pipeline


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_CONFIG = ROOT / "configs/replay/development-v2.example.json"


class RuntimeIntegrationTests(unittest.TestCase):
    def test_max_frames_does_not_consume_an_extra_input(self):
        seen=[]
        def frames():
            for index in range(2):
                seen.append(index)
                yield FramePacket(index,index/10,"fixture",object())
        detector=MappedDetector("empty",CallableBackend(lambda image:()),{0:"knife"})
        with tempfile.TemporaryDirectory() as temp:
            result=run_detection_stream(frames(),detector,output_dir=Path(temp),max_frames=1)
            self.assertEqual([0],seen)
            self.assertEqual(1,result["frame_count"])
            self.assertGreaterEqual(result["frame_processing_ms"]["p95"],0)

    def test_percentile_uses_nearest_rank_definition(self):
        self.assertEqual({"mean":10.5,"median":10.5,"p95":19,"max":20},_distribution(list(range(1,21))))
        self.assertEqual(3,_distribution([3])["p95"])

    def test_existing_output_is_preserved_before_reading_frames(self):
        config = load_pipeline_config(PIPELINE_CONFIG)
        detector = MappedDetector("empty",CallableBackend(lambda image:()),{0:"knife"})
        def forbidden_frames():
            raise AssertionError("Do not consume frames before validating the output")
            yield
        for live in (False,True):
            with self.subTest(live=live), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                (output/"events.jsonl").write_bytes(b"previous evidence\n")
                with self.assertRaisesRegex(ValueError,"empty|existing|non-empty"):
                    if live:
                        run_live_pipeline(forbidden_frames(),detector,config,output_dir=output)
                    else:
                        run_detection_stream(forbidden_frames(),detector,output_dir=output)
                self.assertEqual(b"previous evidence\n",(output/"events.jsonl").read_bytes())

    def test_frame_evidence_is_flushed_before_source_interruption(self):
        config = load_pipeline_config(PIPELINE_CONFIG)
        detector = MappedDetector("empty",CallableBackend(lambda image:()),{0:"knife"})
        for live in (False,True):
            with self.subTest(live=live), tempfile.TemporaryDirectory() as temp:
                output = Path(temp)
                seen = {}
                def interrupted_frames():
                    yield FramePacket(0,0,"fixture",object())
                    path=output/"detections.jsonl"
                    seen["during"] = path.read_text() if path.exists() else ""
                    raise RuntimeError("injected source interruption")
                with self.assertRaisesRegex(RuntimeError,"source interruption"):
                    if live:
                        run_live_pipeline(interrupted_frames(),detector,config,output_dir=output)
                    else:
                        run_detection_stream(interrupted_frames(),detector,output_dir=output)
                self.assertEqual(0,json.loads(seen["during"])["frame_index"])
                self.assertEqual(1,len((output/"latency.jsonl").read_text().splitlines()))
                if live:
                    self.assertEqual(1,len((output/"decisions.jsonl").read_text().splitlines()))
                self.assertFalse((output/"summary.json").exists())

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
