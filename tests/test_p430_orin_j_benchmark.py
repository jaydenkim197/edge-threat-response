from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.detector import CallableBackend, MappedDetector, RawDetection
from edge_threat_response.domain import AblationMode
from edge_threat_response.media import FramePacket


TOOLS = Path(__file__).resolve().parents[1] / "tools"
with patch.object(sys, "path", [str(TOOLS), *sys.path]):
    import p430_orin_j_benchmark as bench
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

    def test_benchmark_persists_event_jpeg_and_requires_successful_gpio_commands(self):
        config = replace(
            load_pipeline_config(TOOLS.parent / "configs/replay/development-v2.example.json"),
            mode=AblationMode.B3, temporal_k=1, temporal_n=1, rearm_clear_frames=1,
        )
        detections = (RawDetection(0, .99, (10, 10, 50, 100)), RawDetection(1, .99, (21, 40, 27, 56)))
        detector = MappedDetector(
            "fake", CallableBackend(lambda image: detections if image.index % 4 == 0 else ()),
            {0: "person", 1: "knife"},
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            connection = root / "connection.json"
            connection.write_text('{"rtsp_url":"rtsp://test.example/local"}', encoding="utf-8")
            files = root / "input"
            files.write_bytes(b"fixture")
            components = [SimpleNamespace(component_id="fixture", weights=files, class_map={0: "person", 1: "knife"})]
            detector_config = SimpleNamespace(topology="composite", components=components, parallel_cuda=False)
            for failed in (False, True):
                with self.subTest(failed=failed):
                    clock = Clock()
                    images = (SimpleNamespace(index=i, shape=(2160, 3840, 3)) for i in range(16))
                    capture = Mock()
                    capture.read.side_effect = lambda: (True, next(images))
                    capture.get.return_value = 4
                    cv2 = Mock(CAP_FFMPEG=0, CAP_PROP_OPEN_TIMEOUT_MSEC=1,
                               CAP_PROP_READ_TIMEOUT_MSEC=2, CAP_PROP_N_THREADS=3)
                    cv2.VideoCapture.return_value = capture
                    cv2.getNumThreads.return_value = 1
                    cv2.imencode.side_effect = lambda ext, image: (True, bytes([image.index]))
                    driver = Mock()
                    if failed:
                        def set_active(active, frame, event):
                            if active and frame.frame_index == 4:
                                raise RuntimeError("fixture GPIO error")
                        driver.set_active.side_effect = set_active

                    class FixtureSource:
                        def __init__(self, _url, *, source_id, capture_factory):
                            self.source_id = source_id
                            self.capture_factory = capture_factory
                            self.stats = {"max_queue_depth": 1}

                        def __iter__(self):
                            reader = self.capture_factory()
                            for i in range(16):
                                _, image = reader.read()
                                yield FramePacket(i, i / 4, self.source_id, image, clock())

                    with (
                        patch.dict(sys.modules, {"cv2": cv2}),
                        patch.object(bench, "time", SimpleNamespace(monotonic=clock, sleep=clock.sleep)),
                        patch.object(bench, "WARMUP_SECONDS", 1),
                        patch.object(bench, "REPETITION_SECONDS", 1),
                        patch.object(bench, "board_identity", return_value={}),
                        patch.object(bench, "board_memory", return_value=1000),
                        patch.object(bench, "prepare_jetson_memory", return_value={}),
                        patch.object(bench, "RTSPFrameSource", FixtureSource),
                        patch.object(bench.DetectorConfig, "load", return_value=detector_config),
                        patch.object(bench, "load_pipeline_config", return_value=config),
                        patch.object(bench, "build_detector", return_value=detector),
                        patch.object(bench.JetsonGpioAlarm, "load", return_value=nullcontext(driver)),
                    ):
                        output = root / f"output-{failed}"
                        result = bench.benchmark(
                            connection, files, files, output, ram_tolerance_mib=64, latency_tolerance_ms=10,
                            write_snapshots=True, parallel_jpeg=True, gpio_config=files,
                            decoder_threads=4, opencv_threads=2,
                        )
                    self.assertFalse(result["provenance"]["detector_parallel_cuda"])
                    cv2.setNumThreads.assert_called_once_with(2)
                    self.assertEqual(2, result["settings"]["opencv_threads"])
                    self.assertEqual(1, result["settings"]["effective_opencv_threads_after_warmup"])
                    self.assertEqual(1, result["settings"]["effective_opencv_threads_after_measurement"])
                    self.assertEqual([1, 20000, 2, 5000, 3, 4], cv2.VideoCapture.call_args.args[2])
                    capture.get.assert_called_once_with(3)
                    self.assertEqual([b"\0", b"\x04", b"\x08", b"\x0c"],
                                     sorted(p.read_bytes() for p in (output / "snapshots").glob("*.jpg")))
                    self.assertEqual({"requested": 3, "successful": 2 if failed else 3},
                                     result["gpio_activation_commands"])
                    self.assertIs(result["live_j_gpio_command_path_pass"], not failed)
                    self.assertFalse(result["hardware_alarm_verified"])
