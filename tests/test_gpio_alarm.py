import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, call, patch

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.detector import CallableBackend, MappedDetector, RawDetection
from edge_threat_response.gpio_alarm import JetsonGpioAlarm
from edge_threat_response.media import CurrentFrameSnapshot, FramePacket
from edge_threat_response.runtime import run_live_pipeline

CONFIG = Path(__file__).resolve().parents[1] / "configs/replay/development-v2.example.json"


def gpio_fixture():
    gpio = Mock(BOARD=10, OUT=1, LOW=0, HIGH=1)
    gpio.getmode.return_value = None
    return gpio


class JetsonGpioAlarmTests(unittest.TestCase):
    def test_pipeline_drives_configured_polarity_and_clears_at_exit(self):
        gpio = gpio_fixture()
        alarm = JetsonGpioAlarm({11: False, 13: True}, gpio=gpio)
        config = replace(load_pipeline_config(CONFIG), temporal_k=1, temporal_n=1)
        raw = (
            RawDetection(0, .95, (0, 0, 100, 200)),
            RawDetection(1, .90, (40, 80, 60, 120)),
        )
        detector = MappedDetector("fixture", CallableBackend(lambda _: raw), {0: "person", 1: "knife"})
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(CurrentFrameSnapshot, "encode_jpeg", return_value=(True, b"fixture")):
                summary = run_live_pipeline(
                    [FramePacket(0, 0, "source", object())], detector, config,
                    output_dir=Path(temp), parallel_jpeg=True, alarm_context=alarm,
                )
        self.assertEqual([call(11, gpio.OUT, initial=0), call(13, gpio.OUT, initial=1)], gpio.setup.call_args_list)
        self.assertEqual([call((11, 13), (1, 0)), call(11, 0), call(13, 1)], gpio.output.call_args_list)
        self.assertEqual([call(11), call(13)], gpio.cleanup.call_args_list)
        self.assertEqual("external_driver_commands", summary["alarm_output"])
        self.assertEqual(0, summary["action_error_count"])
        self.assertTrue(summary["alarm_signals"][0]["active"])

    def test_failed_command_attempts_inactive_and_cleanup_for_all_owned_pins(self):
        gpio = gpio_fixture()
        gpio.output.side_effect = [OSError("active write failed"), None, None]
        with self.assertRaisesRegex(OSError, "active write failed"):
            with JetsonGpioAlarm({11: False, 13: True}, gpio=gpio) as alarm:
                alarm.set_active(True, Mock(), None)
        self.assertEqual([call((11, 13), (1, 0)), call(11, 0), call(13, 1)], gpio.output.call_args_list)
        self.assertEqual([call(11), call(13)], gpio.cleanup.call_args_list)

    def test_config_rejects_duplicate_header_pins_before_opening(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "gpio.json"
            path.write_text(json.dumps({
                "schema_version": 1,
                "outputs": [{"board_pin": 11, "active_low": False}, {"board_pin": 11, "active_low": True}],
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must be unique"):
                JetsonGpioAlarm.load(path)
