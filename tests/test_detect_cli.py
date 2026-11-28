import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from edge_threat_response.detect_cli import DetectorConfig, detect_main, run_main
from edge_threat_response.detector import CallableBackend, MappedDetector
from edge_threat_response.media import FramePacket, IterableFrameSource, OpenCVFrameSource


class DetectionCliReadinessTests(unittest.TestCase):
    def test_source_time_sampling_records_original_indices_timestamps_and_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media, weight = root / "input.mp4", root / "fixture.pt"
            media.write_bytes(b"mock capture input")
            weight.touch()
            config = root / "detector.json"
            config.write_text(json.dumps({"schema_version": 1, "topology": "single", "components": [
                {"component_id": "knife", "weights": str(weight), "class_map": {"0": "knife"}}
            ]}))
            capture = Mock()
            capture.isOpened.return_value = True
            capture.read.side_effect = [(True, object()) for _ in range(7)] + [(False, None)]
            capture.get.side_effect = [0.0, 100.0, 250.0, 251.0, 499.0, 520.0, 1001.0]
            fake_cv2 = SimpleNamespace(VideoCapture=Mock(return_value=capture), CAP_PROP_POS_MSEC=0)
            detector = MappedDetector("knife", CallableBackend(lambda image: ()), {0: "knife"})
            output = root / "detections"
            with patch.dict(sys.modules, {"cv2": fake_cv2}), \
                    patch("edge_threat_response.detect_cli.build_detector", return_value=detector), \
                    patch("edge_threat_response.detect_cli.prepare_jetson_memory", return_value=None), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, detect_main(["--input", str(media), "--source-id", "fixture",
                    "--detector-config", str(config), "--sample-hz", "4", "--output-dir", str(output)]))
            rows = [json.loads(line) for line in (output / "detections.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([0, 2, 5, 6], [row["frame_index"] for row in rows])
            self.assertEqual([0., .25, .52, 1.001], [row["timestamp_s"] for row in rows])
            self.assertEqual({"fixture"}, {row["source_id"] for row in rows})
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertIsNone(summary["provenance"]["max_frames"])
            sampling = summary["provenance"]["sampling"]
            self.assertEqual((4.0, 0.0, "skipped"), (sampling["sample_hz"], sampling["anchor_s"], sampling["empty_slots"]))
            self.assertEqual(7, capture.get.call_count)
            capture.release.assert_called_once_with()

    def test_source_time_sampling_rejects_missing_pts_without_reconstructing_fps(self):
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "input.mp4"
            media.touch()
            capture = Mock()
            capture.isOpened.return_value = True
            capture.read.side_effect = [(True, object()), (True, object())]
            capture.get.side_effect = [0.0, 0.0]
            fake_cv2 = SimpleNamespace(VideoCapture=Mock(return_value=capture), CAP_PROP_POS_MSEC=0)
            with patch.dict(sys.modules, {"cv2": fake_cv2}), self.assertRaisesRegex(ValueError, "increasing decoder timestamps"):
                list(OpenCVFrameSource(media, sample_hz=4.0))
            capture.release.assert_called_once_with()

    def test_cuda_graph_is_an_optional_component_boolean(self):
        detector = {"schema_version": 1, "topology": "single", "components": [
            {"component_id": "knife", "weights": "weight.pt", "class_map": {"0": "knife"}}
        ]}
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "detector.json"
            config.write_text(json.dumps(detector))
            self.assertFalse(DetectorConfig.load(config).components[0].cuda_graph)
            detector["components"][0]["cuda_graph"] = True
            config.write_text(json.dumps(detector))
            self.assertTrue(DetectorConfig.load(config).components[0].cuda_graph)
            detector["components"][0]["cuda_graph"] = "true"
            config.write_text(json.dumps(detector))
            with self.assertRaisesRegex(ValueError, "cuda_graph must be a boolean"):
                DetectorConfig.load(config)

    def test_native_policy_failure_stops_before_model_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            weight=root/"weight.pt"
            weight.touch()
            config=root/"detector.json"
            config.write_text(json.dumps({"schema_version":1,"topology":"single","components":[
                {"component_id":"knife","weights":str(weight),"class_map":{"0":"knife"}}]}))
            for main in (detect_main,run_main):
                args=["--input",str(weight),"--detector-config",str(config),"--output-dir",str(root/"out"),"--inherit-thp"]
                if main is run_main:
                    args += ["--pipeline-config",str(root/"pipeline.json")]
                with patch("edge_threat_response.detect_cli.prepare_jetson_memory",side_effect=RuntimeError("native preflight failed")) as policy, \
                     patch("edge_threat_response.detect_cli.build_detector") as build, contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(2,main(args))
                    policy.assert_called_once_with(inherit_thp=True)
                    build.assert_not_called()
                self.assertFalse((root/"out").exists())

    def test_missing_local_weight_is_rejected_before_backend_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            config=root/"detector.json"
            config.write_text(json.dumps({"schema_version":1,"topology":"single","components":[
                {"component_id":"knife","weights":str(root/"absent.pt"),"class_map":{"0":"knife"}}]}))
            for main in (detect_main,run_main):
                args=["--input",str(root/"input.avi"),"--detector-config",str(config),"--output-dir",str(root/"out")]
                if main is run_main:
                    args += ["--pipeline-config",str(root/"pipeline.json")]
                with patch("edge_threat_response.detect_cli.build_detector",side_effect=RuntimeError("backend must not load")) as build:
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(2,main(args))
                    build.assert_not_called()
                self.assertFalse((root/"out").exists())

    def test_all_error_frames_cannot_be_reported_as_successful_cli_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            weights=root/"fixture.pt"
            weights.write_bytes(b"fixture, not real weights")
            config=root/"detector.json"
            config.write_text(json.dumps({"schema_version":1,"topology":"single","components":[
                {"component_id":"knife","weights":str(weights),"class_map":{"0":"knife"}}]}))
            def fail(image):
                raise RuntimeError("injected detector unavailable")
            detector=MappedDetector("knife",CallableBackend(fail),{0:"knife"})
            frames=IterableFrameSource([FramePacket(0,0,"fixture",object())])
            for index,main in enumerate((detect_main,run_main)):
                output=root/f"out{index}"
                args=["--input",str(weights),"--detector-config",str(config),"--output-dir",str(output)]
                if main is run_main:
                    args += ["--pipeline-config",str(Path(__file__).resolve().parents[1]/"configs/replay/development-v2.example.json")]
                with patch("edge_threat_response.detect_cli.build_detector",return_value=detector), \
                     patch("edge_threat_response.detect_cli.OpenCVFrameSource",return_value=frames), \
                     patch("edge_threat_response.detect_cli.prepare_jetson_memory",return_value=None):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(2,main(args))
                summary=json.loads((output/"summary.json").read_text(encoding="utf-8"))
                self.assertEqual({"detector_error":1},summary["frame_status_counts"])
