import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.dataset.registry import RegistryError, load_registry


class RegistryTests(unittest.TestCase):
    def test_rejects_mapping_to_unknown_canonical_class(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            registry_path = root / "registry.json"
            registry_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "canonical_classes": {"0": "person", "1": "knife"},
                        "sources": [
                            {
                                "source_id": "bad",
                                "root": "dataset",
                                "raw_class_names": {"0": "knife"},
                                "class_map": {"0": 9},
                                "splits": {
                                    "train": {
                                        "images": "train/images",
                                        "labels": "train/labels",
                                    }
                                },
                                "group_strategy": "stem",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RegistryError, "unknown canonical IDs"):
                load_registry(registry_path, repo_root=root)

    def test_roboflow_grouping_removes_augmentation_hash(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
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
                                    }
                                },
                                "group_strategy": "roboflow_stem",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            registry = load_registry(registry_path, repo_root=root)
            group = registry.sources[0].derive_group(
                root / "dataset/train/images/frame_001.rf.deadbeef.jpg"
            )

            self.assertEqual("frame_001", group)


if __name__ == "__main__":
    unittest.main()
