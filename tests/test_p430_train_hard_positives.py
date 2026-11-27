from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "tools"), *sys.path]):
    import p430_train_hard_positives as mine


def proposal(key, timestamp, confidence, *, source="a", size=0):
    return {"image_sha256": key, "source_video_sha256": source, "short_side_bin": size,
            "confidence": confidence, "timestamp_s": timestamp}


class TrainHardPositiveTests(TestCase):
    def test_relative_quartile_and_donors_preserve_source_size_and_spacing(self):
        rows = [proposal("x", 10, .01), proposal("b", 10, .01), proposal("c", 20, .02),
                proposal("d", 30, .2), proposal("e", 40, .2), proposal("f", 50, .3),
                proposal("g", 60, .4), proposal("h", 70, .5),
                proposal("i", 14, .015, size=1), proposal("j", 17, .42, size=1),
                proposal("k", 19, .42, size=1), proposal("l", 21, .43, size=1),
                proposal("m", 10, .8, source="b"), proposal("n", 11, .81, source="b"),
                proposal("o", 12, .81, source="b"), proposal("p", 13, .81, source="b")]
        candidates, donors, stats = mine.select_cohorts(rows)
        self.assertEqual([row["image_sha256"] for row in candidates], ["b", "m"])
        self.assertEqual([row["image_sha256"] for row in donors], ["f", "g", "h", "l"])
        self.assertEqual([row["bottom_quartile"] for row in stats], [2, 1, 1])
        self.assertEqual([row["retained"] for row in stats], [1, 0, 1])
        self.assertEqual(mine.select_cohorts(reversed(rows)), (candidates, donors, stats))

    def test_exactly_five_seconds_is_retained(self):
        rows = [proposal(f"{size}-{i}", 10 + size * 5 + i, i / 10, size=size)
                for size in range(2) for i in range(4)]
        self.assertEqual([row["image_sha256"] for row in mine.select_cohorts(rows)[0]], ["0-0", "1-0"])

    def test_only_one_box_positives_with_a_pinned_tile_are_represented(self):
        rows = []
        for key, side in enumerate((7, 8, 16, 32, 11, 18, 25)):
            rows.append({"image_sha256": str(key), "boxes": [(0.2, 0.2, 0.1, side / 540)],
                         "label_sha256": "label", "source_sha256": "source-frame",
                         "source_video_sha256": "source", "timestamp_s": key})
        rows[4]["boxes"] *= 2
        archive = [proposal(str(index), index, .2) | {"label": int(index != 6)} for index in range(len(rows))]
        plan = {"tiles": {str(index): {"image_sha256": "crop", "label_sha256": "crop-label"}
                          for index in range(len(rows)) if index != 5}}
        with patch.object(mine, "verify_tile") as verify:
            eligible = mine.eligible_positives(Path(), plan, rows, archive)
        self.assertEqual(verify.call_count, 4)
        self.assertEqual([row["short_side_bin"] for row in eligible], [0, 1, 2, 3])
        self.assertEqual([row["confidence"] for row in eligible], [.2] * 4)

    def test_tile_verification_requires_correct_hashes_and_projected_label(self):
        with TemporaryDirectory() as folder:
            base = Path(folder)
            key = "0" * 64
            tile = base / "tiles/images" / f"{key}.jpg"
            label = base / "tiles/labels" / f"{key}.txt"
            for path in (tile, label):
                path.parent.mkdir(parents=True)
            tile.write_bytes(b"pinned tile")
            label.write_text("0 0.500000000 0.500000000 0.250000000 0.250000000\n", encoding="ascii")
            box = (.2, 320 / 1080, .1, 160 / 1080)
            evidence = {"image_sha256": mine.sha(tile), "label_sha256": mine.sha(label),
                        "region": [0, 0, 768, 640]}
            mine.verify_tile(base, key, evidence, box)
            label.write_text("0 .4 .5 .25 .25\n", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "changed"):
                mine.verify_tile(base, key, evidence, box)
            with self.assertRaisesRegex(ValueError, "reproduce"):
                mine.verify_tile(base, key, evidence | {"label_sha256": mine.sha(label)}, box)
