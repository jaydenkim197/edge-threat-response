import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from edge_threat_response.dataset.cli import main


class DatasetCliTests(unittest.TestCase):
    def test_audit_and_plan_split_smoke(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for split, stem in (("train", "one"), ("test", "two")):
                image_dir = root / f"dataset/{split}/images"
                label_dir = root / f"dataset/{split}/labels"
                image_dir.mkdir(parents=True)
                label_dir.mkdir(parents=True)
                (image_dir / f"{stem}.jpg").write_bytes(stem.encode("utf-8"))
                (label_dir / f"{stem}.txt").write_text(
                    "0 0.5 0.5 0.2 0.2\n", encoding="utf-8"
                )
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
                                "group_strategy": "stem",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            audit_dir = root / "audit"
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                audit_exit = main(
                    [
                        "audit",
                        "--registry",
                        str(registry_path),
                        "--repo-root",
                        str(root),
                        "--output-dir",
                        str(audit_dir),
                    ]
                )
                split_exit = main(
                    [
                        "plan-split",
                        "--manifest",
                        str(audit_dir / "manifest.jsonl"),
                        "--output-dir",
                        str(root / "split"),
                        "--ratios",
                        "train=0.5,test=0.5",
                        "--seed",
                        "11",
                    ]
                )

            self.assertEqual(0, audit_exit)
            self.assertEqual(0, split_exit)
            self.assertTrue((root / "split/split-plan.json").is_file())
            self.assertTrue((root / "split/planned-manifest.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
