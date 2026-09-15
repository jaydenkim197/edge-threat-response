import tempfile
import unittest
from pathlib import Path

from edge_threat_response.dataset.models import ManifestRecord
from edge_threat_response.dataset.review import (
    build_review_candidates,
    parse_review_boxes,
    select_stratified_candidates,
    size_bucket,
)


def _record(image_id: str, image_path: str, label_path: str, split: str = "train"):
    return ManifestRecord(
        schema_version=1,
        image_id=image_id,
        source_dataset="source-a",
        source_url=None,
        declared_license=None,
        original_path=image_path,
        label_path=label_path,
        source_group=image_id,
        group_namespace="test",
        original_split="train",
        planned_split=split,
        image_sha256=None,
        label_sha256=None,
        annotation_status="valid",
        annotation_formats=("bbox",),
        annotation_format_counts=(("bbox", 1),),
        raw_class_ids=(0,),
        raw_class_counts=((0, 1),),
        canonical_class_ids=(1,),
        canonical_class_counts=((1, 1),),
        object_count=1,
    )


class DatasetReviewTests(unittest.TestCase):
    def test_parses_bbox_and_polygon_for_review(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "label.txt"
            path.write_text(
                "0 0.5 0.5 0.2 0.1\n0 0.1 0.2 0.3 0.2 0.3 0.6 0.1 0.6\n",
                encoding="utf-8",
            )

            boxes = parse_review_boxes(path)

            self.assertEqual(("bbox", "polygon"), tuple(b.annotation_format for b in boxes))
            self.assertAlmostEqual(0.02, boxes[0].area_ratio)
            self.assertAlmostEqual(0.08, boxes[1].area_ratio)

    def test_size_buckets_are_review_only_area_groups(self):
        self.assertEqual("tiny", size_bucket(0.001))
        self.assertEqual("small", size_bucket(0.01))
        self.assertEqual("medium", size_bucket(0.05))
        self.assertEqual("large", size_bucket(0.2))

    def test_selection_is_deterministic_and_covers_strata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            records = []
            for index, split in enumerate(("train", "train", "val", "test")):
                image = root / f"{index}.jpg"
                image.write_bytes(b"fixture")
                label = root / f"{index}.txt"
                width = 0.02 if index < 2 else 0.5
                label.write_text(f"0 0.5 0.5 {width} {width}\n", encoding="utf-8")
                records.append(_record(f"id-{index}", image.name, label.name, split))

            candidates = build_review_candidates(records, repo_root=root)
            first = select_stratified_candidates(candidates, per_stratum=1, seed=7)
            second = select_stratified_candidates(candidates, per_stratum=1, seed=7)

            self.assertEqual(
                tuple(item.record.image_id for item in first),
                tuple(item.record.image_id for item in second),
            )
            selected_strata = {value for item in first for value in item.strata}
            self.assertIn("split=val", selected_strata)
            self.assertIn("split=test", selected_strata)
            self.assertIn("size=tiny", selected_strata)
            self.assertIn("size=large", selected_strata)


if __name__ == "__main__":
    unittest.main()
