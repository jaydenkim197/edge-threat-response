import unittest

from edge_threat_response.domain import BBox, Detection, FrameDetections, FrameStatus


class DomainTests(unittest.TestCase):
    def test_bbox_geometry_and_inclusive_boundary(self):
        box = BBox(0.0, 0.0, 2.0, 4.0)

        self.assertEqual((1.0, 2.0), box.center)
        self.assertEqual(2.0, box.width)
        self.assertEqual(4.0, box.height)
        self.assertTrue(box.contains((2.0, 4.0)))
        self.assertEqual(BBox(-1.0, -2.0, 3.0, 6.0), box.expand_by_ratio(0.5))

    def test_invalid_bbox_and_confidence_are_rejected(self):
        with self.assertRaises(ValueError):
            BBox(0.0, 0.0, 0.0, 1.0)
        with self.assertRaises(ValueError):
            Detection("knife", 1.1, BBox(0.0, 0.0, 1.0, 1.0))

    def test_non_valid_frame_cannot_hide_detections(self):
        knife = Detection("knife", 0.9, BBox(0.0, 0.0, 1.0, 1.0))
        with self.assertRaises(ValueError):
            FrameDetections(0, 0.0, "camera", FrameStatus.MISSING, (knife,))

    def test_detector_error_requires_message(self):
        with self.assertRaises(ValueError):
            FrameDetections(0, 0.0, "camera", FrameStatus.DETECTOR_ERROR)


if __name__ == "__main__":
    unittest.main()
