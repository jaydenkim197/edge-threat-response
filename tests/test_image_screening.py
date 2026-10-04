import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from edge_threat_response.dataset.image_screening import image_signature, screen_images, similarity_pairs


class ImageScreeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "inputs").mkdir()
        self.image = self.root / "inputs/a.png"
        from PIL import Image
        image = Image.new("L", (100, 100))
        image.putdata([(x * 3 + y * 5) % 256 for y in range(100) for x in range(100)])
        image.save(self.image)
        self.manifest = self.root / "inputs/manifest.jsonl"
        self.row = {"record_id": "source/a", "dataset_id": "source", "original_split": "train",
                    "image_file": str(self.image), "image_sha256": hashlib.sha256(self.image.read_bytes()).hexdigest(),
                    "width": 100, "height": 100}
        self.manifest.write_text(json.dumps(self.row) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_decode_bytes_preserved_no_approval_and_outputs_guarded(self):
        before = self.image.read_bytes(), self.manifest.read_bytes()
        result = screen_images(self.manifest, self.root / "out")
        self.assertEqual((1, 0, False), (result["decoded_verified"], result["errors"], result["training_approved"]))
        self.assertEqual(before, (self.image.read_bytes(), self.manifest.read_bytes()))
        with self.assertRaises(ValueError):
            screen_images(self.manifest, self.root / "out")
        with self.assertRaises(ValueError):
            screen_images(self.manifest, self.root / "inputs/unsafe")

    def test_corrupt_changed_and_wrong_dimensions_record_issues(self):
        for change in ("hash", "dimensions", "corrupt"):
            row = dict(self.row)
            if change == "hash":
                row["image_sha256"] = "bad"
            elif change == "dimensions":
                row["width"] = 200
            else:
                self.image.write_bytes(b"not an image")
                row["image_sha256"] = hashlib.sha256(self.image.read_bytes()).hexdigest()
            self.manifest.write_text(json.dumps(row), encoding="utf-8")
            result = screen_images(self.manifest, self.root / change)
            self.assertEqual((0, 1), (result["decoded_verified"], result["errors"]))

    def test_exact_and_visual_pairs_separate_low_information_and_aspect_gate(self):
        a = {"record_id": "a", "dataset_id": "one", "original_split": "train", **image_signature(self.image)}
        b = {**a, "record_id": "b", "dataset_id": "two", "original_split": "test"}
        pairs = similarity_pairs([a, b])
        self.assertEqual("exact", pairs[0]["kind"])
        self.assertTrue(pairs[0]["cross_source"] and pairs[0]["cross_original_split"])
        b["image_sha256"] = "different"
        self.assertEqual("visual_similarity_candidate", similarity_pairs([a, b])[0]["kind"])
        b["low_information"] = True
        self.assertEqual([], similarity_pairs([a, b]))
        b["low_information"], b["width"] = False, 200
        self.assertEqual([], similarity_pairs([a, b]))
        with self.assertRaises(ValueError):
            similarity_pairs([a], 64)

    def test_pinned_voc_xml_identity_and_coordinate_compatibility_not_selection(self):
        source = self.root / "source"
        source.mkdir()
        target = source / "a.png"
        target.write_bytes(self.image.read_bytes())
        xml = (b"<annotation><filename>a.png</filename><size><width>100</width><height>100</height></size>"
               b"<object><name>knife</name><bndbox><xmin>0</xmin><ymin>1</ymin><xmax>20</xmax>"
               b"<ymax>20</ymax></bndbox></object></annotation>")
        (source / "a.xml").write_bytes(xml)
        row = {"image_path": "a.png", "image_git_blob": "image-blob", "xml_path": "a.xml", "xml_git_blob": "xml-blob",
               "xml_sha256": hashlib.sha256(xml).hexdigest(), "original_split": "train"}
        self.manifest.write_text(json.dumps(row), encoding="utf-8")
        with patch("edge_threat_response.dataset.image_screening._inventory", return_value={"a.png": "image-blob", "a.xml": "xml-blob"}), patch(
                "edge_threat_response.dataset.image_screening._source_bytes", side_effect=lambda root, path, blob: (root / path).read_bytes()):
            result = screen_images(self.manifest, self.root / "source-out", source_root=source)
            self.assertEqual(1, result["coordinate_compatibility"]["pixel-edges:compatible"])
            self.assertEqual(1, result["coordinate_compatibility"]["voc-1based-inclusive:incompatible"])
            self.assertFalse(result["training_approved"])
            row["xml_git_blob"] = "forged"
            self.manifest.write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaises(ValueError):
                screen_images(self.manifest, self.root / "wrong", source_root=source)
