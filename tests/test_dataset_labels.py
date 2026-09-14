import tempfile
import unittest
from pathlib import Path

from edge_threat_response.dataset.labels import parse_yolo_label


class LabelParserTests(unittest.TestCase):
    def parse(self, content: str, class_map: dict[int, int] | None = None):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "sample.txt"
            path.write_text(content, encoding="utf-8")
            return parse_yolo_label(
                path,
                source_dataset="fixture",
                path_reference="sample.txt",
                class_map=class_map or {0: 1},
            )

    def test_parses_bbox_and_polygon(self):
        result = self.parse(
            "0 0.5 0.5 0.2 0.4\n"
            "0 0.1 0.1 0.4 0.1 0.3 0.5\n"
        )

        self.assertEqual([], list(result.issues))
        self.assertEqual(["bbox", "polygon"], [a.annotation_format for a in result.annotations])
        self.assertTrue(all(a.canonical_class_id == 1 for a in result.annotations))

    def test_rejects_unmapped_class(self):
        result = self.parse("2 0.5 0.5 0.2 0.2\n")

        self.assertEqual((), result.annotations)
        self.assertEqual("unmapped_class_id", result.issues[0].code)

    def test_rejects_bbox_outside_image(self):
        result = self.parse("0 0.95 0.5 0.2 0.2\n")

        self.assertEqual((), result.annotations)
        self.assertEqual("bbox_out_of_bounds", result.issues[0].code)

    def test_rejects_degenerate_polygon(self):
        result = self.parse("0 0.2 0.2 0.2 0.4 0.2 0.6\n")

        self.assertEqual((), result.annotations)
        self.assertEqual("non_positive_polygon_extent", result.issues[0].code)

    def test_empty_label_is_not_a_parse_error(self):
        result = self.parse("")

        self.assertEqual((), result.annotations)
        self.assertEqual((), result.issues)


if __name__ == "__main__":
    unittest.main()
