import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from edge_threat_response.detect_cli import detect_main, run_main
from edge_threat_response.detector import CallableBackend, MappedDetector
from edge_threat_response.media import FramePacket, IterableFrameSource


class DetectionCliReadinessTests(unittest.TestCase):
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
                with patch("edge_threat_response.detect_cli.build_detector",return_value=detector),patch("edge_threat_response.detect_cli.OpenCVFrameSource",return_value=frames):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(2,main(args))
                summary=json.loads((output/"summary.json").read_text())
                self.assertEqual({"detector_error":1},summary["frame_status_counts"])
