import csv
import hashlib
import json
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

from tools.sohas_review_images import render_sample
from edge_threat_response.dataset.sohas import VOC_ROOT


class SohasImageReviewTests(unittest.TestCase):
    @unittest.skipIf(find_spec("PIL") is None, "Pillow optional review dependency unavailable")
    def test_decode_hash_dimensions_boxes_and_pending_review(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            image = root / VOC_ROOT / "images/sample.jpg"
            image.parent.mkdir(parents=True)
            Image.new("RGB", (100, 100)).save(image)
            xml = root / VOC_ROOT / "annotations/xmls/sample.xml"
            xml.parent.mkdir(parents=True)
            xml.write_bytes(b"<annotation><filename>sample.jpg</filename><size><width>100</width>"
                            b"<height>100</height></size><object><name>knife</name><bndbox>"
                            b"<xmin>1</xmin><ymin>2</ymin><xmax>30</xmax><ymax>40</ymax>"
                            b"</bndbox></object></annotation>")
            inventory = {}
            for path in (image, xml):
                data = path.read_bytes()
                inventory[path.relative_to(root).as_posix()] = hashlib.sha1(
                    f"blob {len(data)}\0".encode() + data).hexdigest()
            sample = Path(temporary) / "sample.csv"
            sample.write_text("image_path,original_split,image_present,reviewer\n"
                              f"{image.relative_to(root).as_posix()},train,False,\n", encoding="utf-8")
            output = Path(temporary) / "review"
            with patch("tools.sohas_review_images._inventory", return_value=inventory):
                summary = render_sample(root, sample, output)
                with self.assertRaises(ValueError):
                    render_sample(root, sample, output)
            self.assertEqual(1, summary["decoded_images"])
            self.assertEqual(1, summary["knife_objects"])
            self.assertFalse(summary["training_approved"])
            self.assertTrue((output / "contact-sheets/page-001.jpg").is_file())
            evidence = json.loads((output / "image-evidence.jsonl").read_text())
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), evidence["image_sha256"])
            with (output / "review.csv").open(encoding="utf-8-sig") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual("True", row["image_present"])
            self.assertEqual("", row["reviewer"])
            # Lean expansion CSVs need not carry the audit-only presence flag.
            sample.write_text("image_path,original_split,reviewer\n"
                              f"{image.relative_to(root).as_posix()},train,\n", encoding="utf-8")
            with patch("tools.sohas_review_images._inventory", return_value=inventory):
                render_sample(root, sample, Path(temporary) / "lean-review")
            lean = json.loads((Path(temporary) / "lean-review/image-evidence.jsonl").read_text())
            self.assertEqual(hashlib.sha256(xml.read_bytes()).hexdigest(), lean["xml_sha256"])

    def test_source_output_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                render_sample(root, root / "sample.csv", root / "review")
