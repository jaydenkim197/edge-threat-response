import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.dataset.audit import audit_registry, write_audit_outputs
from edge_threat_response.dataset.registry import load_registry


class DatasetAuditTests(unittest.TestCase):
    def test_audit_reports_pairing_duplicates_and_group_leakage(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for split in ("train", "test"):
                (root / f"dataset/{split}/images").mkdir(parents=True)
                (root / f"dataset/{split}/labels").mkdir(parents=True)

            self.write_pair(root, "train", "scene.rf.aaa", b"duplicate")
            self.write_pair(root, "test", "scene.rf.bbb", b"duplicate")
            self.write_pair(root, "train", "empty", b"empty-image", label="")
            (root / "dataset/test/images/missing.jpg").write_bytes(b"missing-label")
            (root / "dataset/test/labels/orphan.txt").write_text(
                "0 0.5 0.5 0.2 0.2\n", encoding="utf-8"
            )
            registry_path = self.write_registry(root)

            result = audit_registry(
                load_registry(registry_path, repo_root=root), hash_images=True
            )
            output_dir = root / "report"
            write_audit_outputs(result, output_dir)

            totals = result.summary["totals"]
            self.assertEqual(4, totals["images"])
            self.assertEqual(2, totals["objects"])
            self.assertEqual(1, totals["annotation_status"]["empty"])
            self.assertEqual(1, totals["annotation_status"]["missing_label"])
            self.assertEqual(1, totals["cross_split_group_count"])
            self.assertEqual(1, totals["cross_split_duplicate_hash_count"])
            self.assertEqual(1, totals["issue_counts"]["missing_image"])
            self.assertTrue((output_dir / "manifest.jsonl").is_file())
            self.assertTrue((output_dir / "issues.jsonl").is_file())
            self.assertTrue((output_dir / "summary.json").is_file())
            self.assertTrue((output_dir / "report.md").is_file())

    @staticmethod
    def write_pair(
        root: Path,
        split: str,
        stem: str,
        image_content: bytes,
        *,
        label: str = "0 0.5 0.5 0.2 0.2\n",
    ) -> None:
        (root / f"dataset/{split}/images/{stem}.jpg").write_bytes(image_content)
        (root / f"dataset/{split}/labels/{stem}.txt").write_text(
            label, encoding="utf-8"
        )

    @staticmethod
    def write_registry(root: Path) -> Path:
        registry_path = root / "registry.json"
        registry_path.write_text(
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
                                "train": {
                                    "images": "train/images",
                                    "labels": "train/labels",
                                },
                                "test": {
                                    "images": "test/images",
                                    "labels": "test/labels",
                                },
                            },
                            "group_namespace": "fixture",
                            "group_strategy": "roboflow_stem",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return registry_path


if __name__ == "__main__":
    unittest.main()
