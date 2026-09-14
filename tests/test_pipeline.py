import unittest
from pathlib import Path

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.domain import (
    AblationMode,
    AlertState,
    FrameDetections,
    FrameStatus,
)
from edge_threat_response.pipeline import ThreatPipeline
from edge_threat_response.ports import MemoryEventRecorder, MockAlarm
from edge_threat_response.replay import load_detection_replay


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/replay/development.example.json"
REPLAY = ROOT / "tests/fixtures/replay/basic.jsonl"


class PipelineAblationTests(unittest.TestCase):
    def test_b0_to_b3_have_distinct_expected_confirmation_frames(self):
        expected = {
            AblationMode.B0: [0, 7],
            AblationMode.B1: [1, 8],
            AblationMode.B2: [1, 7],
            AblationMode.B3: [2, 8],
        }
        frames = load_detection_replay(REPLAY)
        base_config = load_pipeline_config(CONFIG)

        for mode, expected_frames in expected.items():
            with self.subTest(mode=mode.value):
                alarm = MockAlarm()
                recorder = MemoryEventRecorder()
                pipeline = ThreatPipeline(
                    base_config.for_mode(mode), alarm=alarm, recorder=recorder
                )
                results = [pipeline.process(frame) for frame in frames]

                event_frames = [
                    result.frame.frame_index
                    for result in results
                    if result.event is not None
                ]
                self.assertEqual(expected_frames, event_frames)
                self.assertEqual(expected_frames, [e.frame_index for e in recorder.events])
                self.assertEqual(3, len(alarm.signals))
                self.assertEqual([True, False, True], [s.active for s in alarm.signals])

    def test_confirmed_frames_do_not_repeat_event_or_alarm(self):
        frames = load_detection_replay(REPLAY)
        config = load_pipeline_config(CONFIG).for_mode(AblationMode.B3)
        alarm = MockAlarm()
        recorder = MemoryEventRecorder()
        pipeline = ThreatPipeline(config, alarm=alarm, recorder=recorder)

        results = [pipeline.process(frame) for frame in frames[:4]]

        self.assertEqual([2], [r.frame.frame_index for r in results if r.event])
        self.assertEqual(1, len(recorder.events))
        self.assertEqual([True], [signal.active for signal in alarm.signals])
        self.assertEqual(AlertState.CONFIRMED, results[-1].transition.after)
        self.assertEqual("not_captured", recorder.events[0].snapshot_status)

    def test_recorder_failure_does_not_block_alarm(self):
        class FailingRecorder:
            def record(self, event):
                raise OSError("disk unavailable")

        frames = load_detection_replay(REPLAY)
        config = load_pipeline_config(CONFIG).for_mode(AblationMode.B0)
        alarm = MockAlarm()
        pipeline = ThreatPipeline(config, alarm=alarm, recorder=FailingRecorder())

        result = pipeline.process(frames[0])

        self.assertIsNotNone(result.event)
        self.assertTrue(alarm.active)
        self.assertEqual([True], [signal.active for signal in alarm.signals])
        self.assertIn("event_recorder: OSError", result.action_errors[0])

    def test_event_ids_are_deterministic_for_same_input(self):
        frame = load_detection_replay(REPLAY)[0]
        config = load_pipeline_config(CONFIG).for_mode(AblationMode.B0)

        first = ThreatPipeline(config).process(frame).event
        second = ThreatPipeline(config).process(frame).event

        self.assertEqual(first.event_id, second.event_id)

    def test_snapshot_failure_is_explicit_and_does_not_block_alarm(self):
        class FailingSnapshot:
            def capture(self, event_id, frame):
                raise OSError("camera frame unavailable")

        frame = load_detection_replay(REPLAY)[0]
        config = load_pipeline_config(CONFIG).for_mode(AblationMode.B0)
        alarm = MockAlarm()
        result = ThreatPipeline(
            config, alarm=alarm, snapshot=FailingSnapshot()
        ).process(frame)

        self.assertEqual("failed", result.event.snapshot_status)
        self.assertIn("camera frame unavailable", result.event.snapshot_error)
        self.assertTrue(alarm.active)
        self.assertIn("snapshot: OSError", result.action_errors[0])

    def test_detector_error_is_a_false_temporal_sample(self):
        config = load_pipeline_config(CONFIG).for_mode(AblationMode.B1)
        frame = FrameDetections(
            frame_index=0,
            timestamp_s=0.0,
            source_id="camera",
            status=FrameStatus.DETECTOR_ERROR,
            error="inference failed",
        )

        result = ThreatPipeline(config).process(frame)

        self.assertFalse(result.evidence.knife_temporal.value)
        self.assertFalse(result.evidence.candidate)
        self.assertEqual(AlertState.CLEAR, result.transition.after)


if __name__ == "__main__":
    unittest.main()
