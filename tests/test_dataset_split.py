import unittest

from edge_threat_response.dataset.models import ManifestRecord
from edge_threat_response.dataset.split import parse_ratios, plan_group_split


def record(
    image_id: str,
    group: str,
    status: str = "valid",
    image_hash: str | None = None,
) -> ManifestRecord:
    return ManifestRecord(
        schema_version=1,
        image_id=image_id,
        source_dataset="fixture",
        source_url=None,
        declared_license=None,
        original_path=f"images/{image_id}.jpg",
        label_path=f"labels/{image_id}.txt",
        source_group=group,
        group_namespace="fixture",
        original_split="unsplit",
        planned_split=None,
        image_sha256=image_hash or image_id,
        label_sha256=image_id,
        annotation_status=status,
        annotation_formats=("bbox",) if status == "valid" else (),
        annotation_format_counts=(("bbox", 1),) if status == "valid" else (),
        raw_class_ids=(0,) if status == "valid" else (),
        raw_class_counts=((0, 1),) if status == "valid" else (),
        canonical_class_ids=(1,) if status == "valid" else (),
        canonical_class_counts=((1, 1),) if status == "valid" else (),
        object_count=1 if status == "valid" else 0,
    )


class GroupSplitTests(unittest.TestCase):
    def test_group_members_stay_together_and_plan_is_deterministic(self):
        records = (
            record("a1", "a"),
            record("a2", "a"),
            record("b1", "b"),
            record("c1", "c"),
            record("d1", "d"),
        )
        ratios = {"train": 0.6, "val": 0.2, "test": 0.2}

        first_plan, first_records = plan_group_split(records, ratios=ratios, seed=7)
        second_plan, second_records = plan_group_split(records, ratios=ratios, seed=7)

        self.assertEqual(first_plan["assignments"], second_plan["assignments"])
        self.assertEqual(
            [r.planned_split for r in first_records],
            [r.planned_split for r in second_records],
        )
        a_splits = {r.planned_split for r in first_records if r.source_group == "a"}
        self.assertEqual(1, len(a_splits))
        self.assertEqual(5, sum(first_plan["image_counts"].values()))

    def test_invalid_records_are_excluded(self):
        records = (record("good", "a"), record("bad", "b", status="invalid"))

        plan, planned = plan_group_split(
            records, ratios={"train": 0.5, "test": 0.5}, seed=0
        )

        self.assertEqual(1, plan["eligible_images"])
        self.assertEqual(1, plan["excluded_images"])
        self.assertIsNone(planned[1].planned_split)

    def test_exact_duplicates_in_different_groups_stay_together(self):
        records = (
            record("a", "source-a", image_hash="same"),
            record("b", "source-b", image_hash="same"),
            record("c", "source-c"),
        )

        plan, planned = plan_group_split(
            records, ratios={"train": 0.5, "test": 0.5}, seed=3
        )

        duplicate_splits = {r.planned_split for r in planned if r.image_sha256 == "same"}
        self.assertEqual(1, len(duplicate_splits))
        self.assertEqual(3, plan["group_count"])
        self.assertEqual(2, plan["assignment_unit_count"])

    def test_ratio_parser_requires_sum_of_one(self):
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            parse_ratios("train=0.8,test=0.3")


if __name__ == "__main__":
    unittest.main()
