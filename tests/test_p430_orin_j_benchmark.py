from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch

from edge_threat_response.media import FramePacket


TOOLS = Path(__file__).resolve().parents[1] / "tools"
with patch.object(sys, "path", [str(TOOLS), *sys.path]):
    from p430_orin_j_benchmark import Sample, evaluate_j, run_window


class Clock:
    def __init__(self):
        self.seconds = 100.0

    def __call__(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds


class OrinJBenchmarkTests(TestCase):
    def _window(self, seconds, processing_seconds, *, transport_stops_after=None, ram=None):
        clock = Clock()
        read_starts = {}
        frames_used = []

        def frames():
            index = 0
            while transport_stops_after is None or index < transport_stops_after:
                read_starts[index] = clock() - .035
                yield FramePacket(index, float(index), "test", object(), clock() - .005)
                index += 1

        def process(packet):
            frames_used.append(packet.frame_index)
            clock.sleep(processing_seconds)
            return Sample(valid=True, person_seen=True, event=not packet.frame_index, action_errors=0)

        result = run_window(
            frames(), process, read_starts.get, seconds, clock=clock, sleep=clock.sleep,
            shared_used_mib=ram or (lambda: 1024),
        )
        return result, frames_used

    def test_latency_includes_decoder_read_and_counts_selected_slots(self):
        result, frames = self._window(2, .10)
        self.assertEqual(frames, list(range(8)))
        self.assertEqual(result["scheduled_slots"], 8)
        self.assertEqual(result["missed_scheduled_slots"], 0)
        self.assertAlmostEqual(result["read_start_to_action_p95_ms"], 135)
        self.assertAlmostEqual(result["host_queue_age_p95_ms"], 5)

    def test_late_processing_skips_slots_without_a_burst(self):
        result, _ = self._window(2, .60)
        self.assertGreater(result["missed_scheduled_slots"], 0)
        self.assertLess(result["effective_fps"], 4)
        self.assertGreater(result["read_start_to_action_p95_ms"], 250)

    def test_transport_interruption_keeps_the_full_planned_denominator(self):
        result, _ = self._window(2, .10, transport_stops_after=2)
        self.assertEqual(result["problem"], "rtsp_stream_interrupted")
        self.assertEqual(result["valid_frames_in_window"], 2)
        self.assertEqual(result["missed_scheduled_slots"], 6)

    def test_j_requires_all_repetitions_and_rejects_ram_growth(self):
        result, _ = self._window(2, .10)
        self.assertFalse(evaluate_j([result], {"max_queue_depth": 1},
                                    ram_tolerance_mib=64, latency_tolerance_ms=10)["live_j_mock_output_pass"])
        passing = evaluate_j([result] * 3, {"max_queue_depth": 1},
                             ram_tolerance_mib=64, latency_tolerance_ms=10)
        self.assertTrue(passing["live_j_mock_output_pass"])
        growing = [{**result, "shared_used_mib": [base, base + 20, base + 40]}
                   for base in (1000, 1100, 1200)]
        self.assertFalse(evaluate_j(growing, {"max_queue_depth": 1},
                                    ram_tolerance_mib=64, latency_tolerance_ms=10)["checks"]["shared_ram_stable"])
