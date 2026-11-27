import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    import p430_native_resize_pilot as pilot
    import run_p430_site as site


def point(*, small=98, total=129, negatives=1, boxes=12, confidence=.3):
    return {"point": {"small_tp": small, "tp": total, "negative_frames_flagged": negatives,
                      "fp_boxes": boxes, "confidence": confidence}, "ap50_95": .4}


class NativeResizePilotTests(TestCase):
    def test_tune_gate_requires_clear_gain_with_no_regressions(self):
        control = point()
        for candidate in (control, point(total=130), point(boxes=11), point(total=127, negatives=0),
                          point(small=100, boxes=13), point(small=97, total=131)):
            self.assertFalse(pilot.improves(control, candidate))
        for candidate in (point(small=100), point(total=131), point(negatives=0), point(boxes=10)):
            self.assertTrue(pilot.improves(control, candidate))

    def test_sweep_with_no_clear_gain_leaves_dev_check_unopened(self):
        self.check_tune_gate(point(total=130), None)

    def test_promotion_locks_selection_before_matched_dev_check(self):
        self.check_tune_gate(point(total=131, confidence=.22), "lanczos")

    def check_tune_gate(self, alternative, selected):
        cached = point(small=100, total=133, confidence=.4)
        tune_rows, dev_rows = [{"partition": "tune"}], []
        with (TemporaryDirectory() as folder,
              patch.object(pilot, "pin_plan", return_value={}),
              patch.object(pilot, "use_d1", return_value=Path("d1.pt")),
              patch.object(pilot, "read", return_value={"A0": {}}),
              patch.object(pilot, "sha", return_value=pilot.D1_SHA),
              patch.object(pilot, "predict_arm", return_value=[]) as predict,
              patch.object(pilot, "load_predictions", return_value=({"tune": []}, {})) as cache,
              patch.object(pilot, "tune", side_effect=(cached, point(), alternative, point())),
              patch.object(pilot, "coco_metrics", return_value={}),
              patch.object(pilot, "locked", return_value={"tp": 129}) as locked,
              patch.object(pilot, "load_partition") as load):
            root = Path(folder)
            output = root / "result"

            def partition(_, __, split):
                if split == "tune":
                    return tune_rows
                lock = json.loads((output / "tune-lock.json").read_text(encoding="utf-8"))
                self.assertEqual(lock["selected_arm"], selected)
                self.assertIsNone(lock["dev_check"])
                return dev_rows

            load.side_effect = partition
            pilot.run({"base": str(root / "base")}, root / "snapshot", output)
            self.assertEqual(cache.call_args.kwargs, {"partitions": ("tune",)})
            result = json.loads((output / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["selected_arm"], selected)
            self.assertEqual(result["cached_a0_tune"], cached)
            calls = [(call.args[1], call.args[2]) for call in predict.call_args_list]
            expected = [(tune_rows, arm) for arm in pilot.ARMS]
            if selected:
                expected.extend([(dev_rows, "native"), (dev_rows, selected)])
                self.assertEqual([call.args[-1] for call in locked.call_args_list], [.3, .22])
            else:
                self.assertEqual(load.call_count, 1)
                self.assertFalse((output / "tune-lock.json").exists())
                self.assertIsNone(result["dev_check"])
            self.assertEqual(calls, expected)

    def test_model_boxes_return_to_source_coordinates_before_edge_filtering(self):
        from PIL import Image

        model = Mock(names={0: "knife"})

        def box_result(boxes, confidences):
            return SimpleNamespace(boxes=SimpleNamespace(xyxy=Mock(tolist=Mock(return_value=boxes)),
                                                         conf=Mock(tolist=Mock(return_value=confidences))))

        region = (400, 300, 1168, 940)

        def predict(chips, **settings):
            self.assertEqual([chip.size for chip in chips], [(640, 533)])
            self.assertEqual(settings["imgsz"], 640)
            self.assertEqual(settings["device"], "cpu")
            return [box_result([[100, 200, 300, 400]], [.6])]

        model.predict.side_effect = predict
        with (TemporaryDirectory() as folder,
              patch.dict(sys.modules, {"ultralytics": SimpleNamespace(YOLO=lambda _: model)}),
              patch.object(site, "regions", return_value=[region]),
              patch.object(site, "tile_nms_indices", return_value=[0]) as nms,
              patch.object(site, "touches_internal_tile_edge", return_value=False) as edge):
            image = Path(folder) / "frame.png"
            Image.new("RGB", (1920, 1080)).save(image)
            rows = [{"image_file": str(image), "image_sha256": "image", "source_video_sha256": "source",
                     "boxes": []}]
            predictions = site.tile_predictions(Path("unused.pt"), rows, device="cpu",
                                                interpolation=Image.Resampling.LANCZOS)
        expected = [100 * (768 / 640), 200 * (640 / 533), 300 * (768 / 640), 400 * (640 / 533)]
        edge.assert_called_once_with(expected, region)
        translated = [expected[0] + 400, expected[1] + 300, expected[2] + 400, expected[3] + 300]
        nms.assert_called_once_with([translated], [.6])
        self.assertEqual(predictions[0]["detections"][0]["bbox_xyxy"], translated)
