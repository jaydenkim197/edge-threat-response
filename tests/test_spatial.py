import math
import unittest

from edge_threat_response.domain import BBox, Detection, SpatialPolicy
from edge_threat_response.spatial import associate_person_knives


def detection(label, bbox, detection_id):
    return Detection(label, 0.9, BBox(*bbox), detection_id)


class SpatialAssociationTests(unittest.TestCase):
    def test_selects_nearest_person_and_normalizes_by_person_diagonal(self):
        far = detection("person", (0.0, 0.0, 1.0, 2.0), "far")
        near = detection("person", (2.0, 0.0, 4.0, 4.0), "near")
        knife = detection("knife", (3.0, 1.9, 3.2, 2.1), "knife")

        result = associate_person_knives(
            (far, near),
            (knife,),
            normalized_distance_threshold=0.5,
            expanded_person_ratio=0.0,
        )[0]

        self.assertEqual("near", result.person.detection_id)
        self.assertAlmostEqual(0.1 / math.hypot(2.0, 4.0), result.normalized_distance)
        self.assertTrue(result.associated)

    def test_requires_both_distance_and_expanded_region(self):
        person = detection("person", (0.0, 0.0, 1.0, 1.0), "person")
        knife = detection("knife", (1.1, 0.45, 1.2, 0.55), "knife")

        outside = associate_person_knives(
            (person,),
            (knife,),
            normalized_distance_threshold=1.0,
            expanded_person_ratio=0.0,
        )[0]
        inside = associate_person_knives(
            (person,),
            (knife,),
            normalized_distance_threshold=1.0,
            expanded_person_ratio=0.2,
        )[0]

        self.assertFalse(outside.associated)
        self.assertTrue(inside.associated)

    def test_knife_without_person_is_explicitly_unassociated(self):
        knife = detection("knife", (0.0, 0.0, 1.0, 1.0), "knife")
        result = associate_person_knives(
            (),
            (knife,),
            normalized_distance_threshold=1.0,
            expanded_person_ratio=0.0,
        )[0]

        self.assertIsNone(result.person)
        self.assertIsNone(result.normalized_distance)
        self.assertFalse(result.associated)

    def test_expanded_bbox_only_keeps_distance_as_diagnostic(self):
        person = detection("person", (0.0, 0.0, 1.0, 1.0), "person")
        knife = detection("knife", (1.15, 1.15, 1.25, 1.25), "knife")

        result = associate_person_knives(
            (person,),
            (knife,),
            policy=SpatialPolicy.EXPANDED_BBOX_ONLY,
            expanded_person_ratio=0.25,
        )[0]

        self.assertTrue(result.center_in_expanded_person)
        self.assertIsNotNone(result.normalized_distance)
        self.assertTrue(result.associated)

    def test_expanded_bbox_only_rejects_distance_threshold(self):
        with self.assertRaisesRegex(ValueError, "must be omitted"):
            associate_person_knives(
                (),
                (),
                policy=SpatialPolicy.EXPANDED_BBOX_ONLY,
                expanded_person_ratio=0.25,
                normalized_distance_threshold=0.5,
            )


if __name__ == "__main__":
    unittest.main()
