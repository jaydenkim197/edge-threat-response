import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.dataset.materialize import (
    materialize_knife_yolo,
    parse_split_limits,
)
from edge_threat_response.dataset.models import ManifestRecord
from edge_threat_response.dataset.registry import load_registry


class DatasetMaterializeTests(unittest.TestCase):
    def test_materializes_bbox_and_polygon_as_model_local_knife(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            dataset = root / "dataset"
            (dataset / "images").mkdir(parents=True)
            (dataset / "labels").mkdir()
            (dataset / "images/a.jpg").write_bytes(b"image-a")
            (dataset / "images/b.jpg").write_bytes(b"image-b")
            (dataset / "labels/a.txt").write_text(
                "0 0.5 0.5 0.2 0.4\n", encoding="utf-8"
            )
            (dataset / "labels/b.txt").write_text(
                "0 0.2 0.3 0.6 0.3 0.6 0.7 0.2 0.7\n", encoding="utf-8"
            )
            registry_path = self._write_registry(root)
            registry = load_registry(registry_path, repo_root=root)
            records = (
                self._record("a", "train", hashlib.sha256(b"image-a").hexdigest()),
                self._record("b", "val", hashlib.sha256(b"image-b").hexdigest()),
            )

            summary = materialize_knife_yolo(
                records,
                registry=registry,
                output_dir=root / "output",
                link_mode="copy",
            )

            self.assertEqual({"train": 1, "val": 1}, summary["image_counts"])
            self.assertEqual({"0": 1}, summary["runtime_class_mapping"])
            self.assertTrue(summary["source_hashes_verified"])
            labels = sorted((root / "output/labels").rglob("*.txt"))
            self.assertEqual(2, len(labels))
            self.assertTrue(all(path.read_text().startswith("0 ") for path in labels))
            polygon = next(path for path in labels if "-bbbb" in path.name)
            self.assertEqual(
                "0 0.4 0.5 0.4 0.4\n", polygon.read_text(encoding="utf-8")
            )
            self.assertIn("0: knife", (root / "output/data.yaml").read_text())

    def test_deduplicates_exact_images_and_obeys_limits(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            dataset = root / "dataset"
            (dataset / "images").mkdir(parents=True)
            (dataset / "labels").mkdir()
            for stem in ("a", "b", "c"):
                image_bytes = b"same" if stem in {"a", "b"} else b"different"
                (dataset / f"images/{stem}.jpg").write_bytes(image_bytes)
                (dataset / f"labels/{stem}.txt").write_text(
                    "0 0.5 0.5 0.2 0.2\n", encoding="utf-8"
                )
            registry = load_registry(self._write_registry(root), repo_root=root)
            records = (
                self._record("a", "train", hashlib.sha256(b"same").hexdigest()),
                self._record("b", "train", hashlib.sha256(b"same").hexdigest()),
                self._record("c", "val", hashlib.sha256(b"different").hexdigest()),
            )

            summary = materialize_knife_yolo(
                records,
                registry=registry,
                output_dir=root / "output",
                limits={"train": 2, "val": 0},
                link_mode="copy",
            )

            self.assertEqual({"train": 1}, summary["image_counts"])
            self.assertEqual(1, summary["exact_duplicate_records_skipped"])
            self.assertEqual({"train": 32, "val": 8, "test": 0}, parse_split_limits("train=32,val=8,test=0"))

    def test_rejects_source_changed_after_audit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            dataset = root / "dataset"
            (dataset / "images").mkdir(parents=True)
            (dataset / "labels").mkdir()
            (dataset / "images/a.jpg").write_bytes(b"changed")
            (dataset / "labels/a.txt").write_text(
                "0 0.5 0.5 0.2 0.2\n", encoding="utf-8"
            )
            registry = load_registry(self._write_registry(root), repo_root=root)

            with self.assertRaisesRegex(ValueError, "hash changed"):
                materialize_knife_yolo(
                    (self._record("a", "train", "stale-hash"),),
                    registry=registry,
                    output_dir=root / "output",
                    link_mode="copy",
                )

    def _write_registry(self, root: Path) -> Path:
        path = root / "registry.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "canonical_classes": {"0": "person", "1": "knife"},
                    "sources": [
                        {
                            "source_id": "fixture",
                            "root": "dataset",
                            "raw_class_names": {"0": "knife"},
                            "class_map": {"0": 1},
                            "splits": {
                                "all": {"images": "images", "labels": "labels"}
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return path

    def _record(self, stem: str, split: str, image_hash: str) -> ManifestRecord:
        return ManifestRecord(
            schema_version=1,
            image_id=f"sha256:{stem * 20}",
            source_dataset="fixture",
            source_url=None,
            declared_license=None,
            original_path=f"dataset/images/{stem}.jpg",
            label_path=f"dataset/labels/{stem}.txt",
            source_group=stem,
            group_namespace="fixture",
            original_split="all",
            planned_split=split,
            image_sha256=image_hash,
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


if __name__ == "__main__":
    unittest.main()
