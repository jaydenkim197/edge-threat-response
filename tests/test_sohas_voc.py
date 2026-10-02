import csv
import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from edge_threat_response.dataset.cli import main
from edge_threat_response.dataset.labels import parse_yolo_label
from edge_threat_response.dataset.sohas import (
    VOC_ROOT, YOLO_ROOT, UPSTREAM_COMMIT, audit_sohas_voc, parse_sohas_voc,
    _inventory,
)


def xml(name="sample.jpg", objects=None):
    if objects is None:
        objects = [("knife", (10, 20, 30, 40)), ("knife", (50, 60, 80, 90))]
    rows = "".join(
        f"<object><name>{label}</name><difficult>0</difficult><truncated>0</truncated>"
        "<bndbox>" + "".join(f"<{key}>{value}</{key}>" for key, value in
                            zip(("xmin", "ymin", "xmax", "ymax"), box)) + "</bndbox></object>"
        for label, box in objects
    )
    return (f"<annotation><filename>{name}</filename><size><width>100</width>"
            f"<height>100</height></size>{rows}</annotation>").encode()


class SohasVocTests(unittest.TestCase):
    def test_preserves_every_knife_and_roundtrips_through_existing_parser(self):
        data = xml(objects=[("knife", (10, 20, 30, 40)), ("smartphone", (1, 1, 4, 5)),
                            ("knife", (50, 60, 80, 90))])
        result = parse_sohas_voc(data, image_name="sample.jpg", convention="pixel-edges")
        self.assertEqual(2, result["knife_count"])
        self.assertEqual(3, len(result["objects"]))
        self.assertEqual(["10", "20", "30", "40"], result["objects"][0]["bbox_xyxy_raw"])
        box = result["objects"][0]["candidate_yolo_bbox"]
        self.assertEqual((0.2, 0.3, 0.2, 0.2), box)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "label.txt"
            path.write_text("\n".join(result["candidate_yolo_lines"]), encoding="utf-8")
            parsed = parse_yolo_label(path, source_dataset="fixture", path_reference="label.txt", class_map={0: 1})
            self.assertEqual(2, len(parsed.annotations))
            self.assertFalse(parsed.issues)

    def test_coordinate_conventions_have_explicit_different_geometry(self):
        data = xml(objects=[("knife", (1, 1, 100, 100))])
        edge = parse_sohas_voc(data, image_name="sample.jpg", convention="pixel-edges")
        inclusive = parse_sohas_voc(data, image_name="sample.jpg", convention="voc-1based-inclusive")
        self.assertEqual((0.5, 0.5, 1.0, 1.0), inclusive["objects"][0]["candidate_yolo_bbox"])
        self.assertEqual(0.99, edge["objects"][0]["candidate_yolo_bbox"][2])
        self.assertFalse(parse_sohas_voc(data, image_name="sample.jpg")["candidate_yolo_lines"])

    def test_invalid_second_box_never_exports_partial_labels(self):
        for box in ((80, 0, 10, 20), (-1, 0, 10, 20), (0, 0, 101, 20), (0, 0, "nan", 20), (0, 0, 0, 20)):
            with self.subTest(box=box):
                result = parse_sohas_voc(xml(objects=[("knife", (1, 1, 4, 5)), ("knife", box)]),
                                         image_name="sample.jpg", convention="pixel-edges")
                self.assertEqual(2, result["knife_count"])
                self.assertTrue(result["errors"])
                self.assertFalse(result["candidate_yolo_lines"])

    def test_unknown_classes_and_empty_annotations_are_held(self):
        for objects in ([], [("Knife", (1, 1, 4, 5))], [("unmapped", (1, 1, 4, 5))]):
            result = parse_sohas_voc(xml(objects=objects), image_name="sample.jpg", convention="pixel-edges")
            self.assertTrue(result["errors"])
            self.assertFalse(result["candidate_yolo_lines"])

    def test_xml_errors_filename_dimensions_and_entities(self):
        for data in (b"bad", xml().replace(b"<width>100", b"<width>0"),
                     xml().replace(b"<width>100</width>", b"<width>100</width><width>200</width>"),
                     b'<!DOCTYPE annotation [<!ENTITY x "knife">]>' + xml()):
            with self.subTest(data=data[:30]), self.assertRaises(ValueError):
                parse_sohas_voc(data, image_name="sample.jpg")

    def test_filename_mismatch_preserves_all_objects_but_holds_conversion(self):
        for data in (xml(name="other.jpg"),
                     xml().replace(b"<xmin>10</xmin>", b"<xmin>10</xmin><xmin>11</xmin>"),
                     xml().replace(b"<name>knife</name>", b"<name>knife</name><name>smartphone</name>")):
            result = parse_sohas_voc(data, image_name="sample.jpg", convention="pixel-edges")
            self.assertEqual(2, result["knife_count"])
            self.assertEqual(2, len(result["objects"]))
            self.assertTrue(result["errors"])
            self.assertFalse(result["candidate_yolo_lines"])

    def test_unique_pair_case_difference_is_recorded_without_losing_boxes(self):
        result = parse_sohas_voc(xml(name="sample.jpg"), image_name="sample.JPG", convention="pixel-edges")
        self.assertTrue(result["filename_case_difference"])
        self.assertEqual("sample.jpg", result["xml_filename"])
        self.assertFalse(result["errors"])
        self.assertEqual(2, len(result["candidate_yolo_lines"]))

    def test_inclusive_single_pixel_and_invalid_fractional_or_zero_coordinates(self):
        result = parse_sohas_voc(xml(objects=[("knife", (1, 1, 1, 1))]),
                                 image_name="sample.jpg", convention="voc-1based-inclusive")
        self.assertEqual(0.01, result["objects"][0]["candidate_yolo_bbox"][2])
        for box in ((0, 1, 2, 2), (1.5, 1, 2, 2)):
            self.assertTrue(parse_sohas_voc(xml(objects=[("knife", box)]), image_name="sample.jpg",
                                           convention="voc-1based-inclusive")["errors"])


class SohasAuditTests(unittest.TestCase):
    def test_git_inventory_includes_executable_regular_files_but_not_symlinks(self):
        entries = (b"100755 blob abc\texecutable.jpg\0"
                   b"100644 blob def\tregular.xml\0"
                   b"120000 blob ghi\tlink.jpg\0")
        with patch("edge_threat_response.dataset.sohas._git", side_effect=[UPSTREAM_COMMIT.encode(), entries]):
            self.assertEqual({"executable.jpg": "abc", "regular.xml": "def"}, _inventory(Path(".")))

    def fixture(self, root):
        inventory = {}
        def add(path, data=None):
            if data is None:
                inventory[path] = "0" * 40
            else:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                inventory[path] = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        add(f"{VOC_ROOT}/images/sample.jpg")
        add(f"{VOC_ROOT}/annotations/xmls/sample.xml", xml())
        add(f"{VOC_ROOT}/annotations/xmls/orphan.xml", xml("orphan.jpg"))
        add(f"{YOLO_ROOT}/obj_train_data/labels/train/sample.txt", b"2 0.2 0.3 0.2 0.2\n")
        add(f"{VOC_ROOT}/images_test/negative.jpg")
        add(f"{VOC_ROOT}/annotations_test/xmls/negative.xml", xml("negative.jpg", [("smartphone", (1, 1, 4, 5))]))
        add(f"{YOLO_ROOT}/obj_train_data/labels/test/negative.txt", b"1 0.025 0.03 0.03 0.04\n")
        return inventory

    def test_dry_run_pairing_orphans_negative_hold_and_source_immutability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, output = Path(tmp) / "raw", Path(tmp) / "audit"
            inventory = self.fixture(root)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with patch("edge_threat_response.dataset.sohas._inventory", return_value=inventory):
                summary = audit_sohas_voc(root, output)
            self.assertEqual(2, summary["images"])
            self.assertEqual(2, summary["voc_knife_objects"])
            self.assertEqual(1, summary["issue_counts"]["orphan_xml"])
            self.assertEqual(1, summary["issue_counts"]["knife_count_mismatch"])
            self.assertEqual(1, summary["roles"]["negative_unverified"])
            self.assertFalse(summary["training_approved"])
            self.assertEqual(0, summary["images_present"])
            rows = [json.loads(line) for line in (output / "voc-candidates.jsonl").read_text().splitlines()]
            self.assertTrue(all(not row["candidate_yolo_lines"] for row in rows))
            with (output / "review-queue.csv").open(encoding="utf-8-sig") as file:
                review = list(csv.DictReader(file))
            self.assertTrue(all(row["reviewer"] == "" and row["negative_knife_absence"] == "" for row in review))
            self.assertEqual(before, {p: p.read_bytes() for p in root.rglob("*") if p.is_file()})
            self.assertFalse(list(output.rglob("*.txt")))
            self.assertEqual(2, summary["sample_count"])
            with patch("edge_threat_response.dataset.sohas._inventory", return_value=inventory):
                audit_sohas_voc(root, Path(tmp) / "repeat")
            self.assertEqual((output / "review-sample.csv").read_bytes(), (Path(tmp) / "repeat/review-sample.csv").read_bytes())

    def test_explicit_convention_requires_evidence_and_still_does_not_approve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, output = Path(tmp) / "raw", Path(tmp) / "audit"
            inventory = self.fixture(root)
            with self.assertRaises(ValueError):
                audit_sohas_voc(root, output, convention="pixel-edges")
            with patch("edge_threat_response.dataset.sohas._inventory", return_value=inventory):
                summary = audit_sohas_voc(root, output, convention="pixel-edges", coordinate_evidence="fixture spec")
            rows = [json.loads(line) for line in (output / "voc-candidates.jsonl").read_text().splitlines()]
            self.assertEqual(2, len(next(row for row in rows if row["knife_count"])["candidate_yolo_lines"]))
            self.assertFalse(summary["training_approved"])

    def test_missing_modified_and_mispaired_xml_are_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "raw"
            inventory = self.fixture(root)
            path = root / f"{VOC_ROOT}/annotations/xmls/sample.xml"
            path.write_bytes(xml("other.jpg"))
            with patch("edge_threat_response.dataset.sohas._inventory", return_value=inventory):
                summary = audit_sohas_voc(root, Path(tmp) / "changed")
                path.unlink()
                missing = audit_sohas_voc(root, Path(tmp) / "missing")
            self.assertGreater(summary["error_count"], 0)
            self.assertGreater(missing["error_count"], 0)

    def test_output_cannot_overwrite_source_or_previous_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "raw"
            inventory = self.fixture(root)
            with self.assertRaises(ValueError):
                audit_sohas_voc(root, root / "audit")
            with patch("edge_threat_response.dataset.sohas._inventory", return_value=inventory):
                audit_sohas_voc(root, Path(tmp) / "output")
            with self.assertRaises(ValueError):
                audit_sohas_voc(root, Path(tmp) / "output")

    def test_cli_reports_errors_and_rejects_wrong_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "raw"
            inventory = self.fixture(root)
            del inventory[f"{VOC_ROOT}/annotations/xmls/sample.xml"]
            with patch("edge_threat_response.dataset.sohas._inventory", return_value=inventory), redirect_stdout(StringIO()):
                result = main(["sohas-voc-audit", "--source-root", str(root), "--output-dir", str(Path(tmp) / "out")])
            self.assertEqual(1, result)
            with patch("edge_threat_response.dataset.sohas._git", return_value=b"wrong"), redirect_stderr(StringIO()):
                self.assertEqual(2, main(["sohas-voc-audit", "--source-root", str(root), "--output-dir", str(Path(tmp) / "wrong")]))


if __name__ == "__main__":
    unittest.main()
