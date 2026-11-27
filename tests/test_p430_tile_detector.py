import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from edge_threat_response.detect_cli import DetectorConfig, build_detector, detect_main
from edge_threat_response.domain import FrameStatus
from edge_threat_response.media import FramePacket, IterableFrameSource


class Frame:
    """Make image coordinates and channel order observable without NumPy."""

    def __init__(self, shape):
        self.shape = shape

    def __getitem__(self, index):
        return index


def result(*candidates):
    return SimpleNamespace(boxes=SimpleNamespace(
        xyxy=[box for box, _ in candidates],
        conf=[confidence for _, confidence in candidates],
        cls=[0] * len(candidates),
    ))


class P430TileDetectorTests(unittest.TestCase):
    def write_config(self, root, weights, **overrides):
        config = root / "detector.json"
        config.write_text(json.dumps({
            "schema_version": 1,
            "topology": "single",
            "components": [{
                "component_id": "knife",
                "weights": str(weights),
                "class_map": {"0": "knife"},
                "input_layout": "p430_tile640",
                "predict_arguments": {"conf": .3, "device": 0},
                **overrides,
            }],
        }), encoding="utf-8")
        return config

    def test_detect_cli_emits_full_frame_boxes_after_edge_filter_merge_and_confidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            weights = root / "fixture.pt"
            weights.touch()
            config = self.write_config(root, weights)
            for (height, width, _), left, top in (
                ((2160, 3840, 3), 960, 540),
                ((1080, 1920, 3), 0, 0),
            ):
                with self.subTest(width=width):
                    model = Mock(names={0: "knife"})
                    model.predict.return_value = [
                        result(((600, 100, 620, 120), .8), ((80, 80, 90, 90), .2)),
                        result(((24, 100, 44, 120), .9), ((1, 200, 9, 220), .99)),
                        result(), result(), result(), result(),
                    ]
                    frames = IterableFrameSource([FramePacket(0, 0, "mock-p430", Frame((height, width, 3)))])
                    output = root / f"out-{width}"
                    with (
                        patch("edge_threat_response.detector.UltralyticsBackend._get_model", return_value=model),
                        patch("edge_threat_response.detect_cli.OpenCVFrameSource", return_value=frames),
                        patch("edge_threat_response.p430_tile_detector.tile_nms_indices", return_value=[2, 1]) as merge,
                        contextlib.redirect_stdout(io.StringIO()),
                    ):
                        code = detect_main(["--input", str(weights), "--detector-config", str(config),
                                            "--output-dir", str(output)])
                    self.assertEqual(0, code)
                    row = json.loads((output / "detections.jsonl").read_text(encoding="utf-8"))
                    self.assertEqual("valid", row["status"])
                    self.assertEqual([{
                        "label": "knife",
                        "confidence": .9,
                        "bbox_xyxy": [left + 600, top + 100, left + 620, top + 120],
                        "detection_id": "knife:0",
                    }], row["detections"])
                    merge.assert_called_once_with(
                        [(600., 100., 620., 120.), (80., 80., 90., 90.), (600., 100., 620., 120.)],
                        [.8, .2, .9],
                    )
                    model.predict.assert_called_once_with(
                        source=[
                            (slice(top + y, top + y + 640), slice(left + x, left + x + 768))
                            for y in (0, 440) for x in (0, 576, 1152)
                        ],
                        verbose=False, device=0, imgsz=640, rect=False,
                        conf=.001, iou=.7, classes=[0], max_det=100, batch=6,
                    )

    def test_unsupported_camera_resolution_and_short_batch_are_detector_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = DetectorConfig.load(self.write_config(root, root / "knife.pt"))
            detector = build_detector(config)
            model = Mock(names={0: "knife"})
            model.predict.return_value = [result()] * 5
            with patch("edge_threat_response.detector.UltralyticsBackend._get_model", return_value=model):
                small_frame = detector.infer(Frame((360, 640, 3)))
                self.assertEqual(FrameStatus.DETECTOR_ERROR, small_frame.status)
                self.assertIn("3840×2160 or 1920×1080", small_frame.error)
                model.predict.assert_not_called()
                short_batch = detector.infer(Frame((1080, 1920, 3)))
                self.assertEqual(FrameStatus.DETECTOR_ERROR, short_batch.status)
                self.assertIn("number of results", short_batch.error)
                self.assertEqual((), short_batch.detections)

    def test_declarative_precision_and_prefilter_keep_postmerge_threshold(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = DetectorConfig.load(self.write_config(
                root, root / "knife.pt", predict_arguments={"conf": .3, "premerge_conf": .15, "half": True},
            ))
            detector = build_detector(config)
            model = Mock(names={0: "knife"})
            model.predict.return_value = [result(((80, 80, 90, 90), .2), ((120, 120, 140, 140), .4)),
                                          *[result()] * 5]
            with (
                patch("edge_threat_response.detector.UltralyticsBackend._get_model", return_value=model),
                patch("edge_threat_response.p430_tile_detector.tile_nms_indices", return_value=[1, 0]),
            ):
                observed = detector.infer(Frame((1080, 1920, 3)))
            self.assertEqual((.4,), tuple(item.confidence for item in observed.detections))
            self.assertEqual(.15, model.predict.call_args.kwargs["conf"])
            self.assertIs(True, model.predict.call_args.kwargs["half"])

    def test_declarative_profile_rejects_invalid_filters_or_precision(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for extra, error in (({"premerge_conf": .4}, "premerge_conf"),
                                 ({"premerge_conf": True}, "premerge_conf"),
                                 ({"half": "yes"}, "half")):
                with self.subTest(extra=extra):
                    config = DetectorConfig.load(self.write_config(
                        root, root / "knife.pt", predict_arguments={"conf": .3, **extra},
                    ))
                    with self.assertRaisesRegex(ValueError, error):
                        build_detector(config)

    def test_tiled_person_component_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self.write_config(root, root / "person.pt", class_map={"0": "person"})
            with self.assertRaisesRegex(ValueError, "requires class_map"):
                DetectorConfig.load(config)
