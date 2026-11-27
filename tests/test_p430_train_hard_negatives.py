from hashlib import sha256
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch


with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1] / "tools"), *sys.path]):
    from p430_train_hard_negatives import mine, reviewed_train_negatives, select_candidates


def row(key, timestamp=0, source="session-a"):
    return {"image": "negative.jpg", "image_sha256": key, "label_sha256": sha256(b"").hexdigest(),
            "source_sha256": f"original-{key}", "source_video_sha256": source, "knife_boxes": 0,
            "session": source, "timestamp_s": timestamp, "review_scope": "center-50-v1",
            "review_version": 1, "crop_xyxy": [960, 540, 2880, 1620]}


class TrainHardNegativesTests(TestCase):
    def test_unpinned_checkpoint_fails_before_opening_training_inputs(self):
        with TemporaryDirectory() as directory, patch("p430_train_hard_negatives.pin_plan") as pin:
            root = Path(directory)
            checkpoint = root / "candidate.pt"
            checkpoint.write_bytes(b"checkpoint")
            config = {"confidence": .15, "spacing_s": 5., "limit": 24}
            with self.assertRaisesRegex(ValueError, "both checkpoint path and SHA-256"):
                mine({}, root / "candidates.json", **config, checkpoint=checkpoint)
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                mine({}, root / "candidates.json", **config, checkpoint=checkpoint, checkpoint_sha256="a" * 64)
            pin.assert_not_called()

    def test_only_scoped_train_negatives_open_verified_images(self):
        content = b"test image bytes"
        key = sha256(content).hexdigest()
        approved = row(key)
        parent = {"domain": "p430", "n": 0, "source_group": approved["source_video_sha256"],
                  "label_sha256": approved["label_sha256"], "image": "negative.jpg", "label": "negative.txt"}
        held = row("tune")
        legacy = {**row("legacy"), "review_scope": "legacy-unspecified"}
        external = row("external")
        positive = {**row("positive"), "knife_boxes": 1}
        plan = {"validation": {"tune": ["tune"], "dev_check": ["dev"]},
                "pool": {key: parent, "legacy": parent, "external": {**parent, "domain": "cctv"},
                         "positive": {**parent, "n": 1}}}
        records = [approved, held, legacy, external, positive]
        protection = {"edited_sha256": "protected"}
        with TemporaryDirectory() as directory:
            image = Path(directory) / "negative.jpg"
            image.write_bytes(content)
            label = image.with_suffix(".txt")
            label.touch()
            with patch("p430_train_hard_negatives.paths", return_value=(image, label)) as placement:
                found = reviewed_train_negatives(Path(directory), plan, records, protection)
                self.assertEqual(found, [{**approved, "image_file": str(image), "boxes": []}])
                placement.assert_called_once_with(Path(directory), parent)
                image.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "byte validation"):
                    reviewed_train_negatives(Path(directory), plan, records, protection)

    def test_protected_or_shared_original_never_opened(self):
        original = row("train")
        plan = {"validation": {"tune": ["tune"]}, "pool": {"train": {"domain": "p430", "n": 0}}}
        held = {**row("tune"), "source_sha256": original["source_sha256"]}
        with patch("p430_train_hard_negatives.paths") as placement:
            with self.assertRaisesRegex(ValueError, "Protected"):
                reviewed_train_negatives(Path("."), plan, [original, held], {"edited_sha256": "elsewhere"})
            with self.assertRaisesRegex(ValueError, "Protected"):
                reviewed_train_negatives(Path("."), plan, [original], {"edited_sha256": "session-a"})
            placement.assert_not_called()

    def test_same_source_spacing_and_recurrence_are_deterministic(self):
        rows = [row("x", 0), row("y", 2), row("z", 7), row("b", 1, "session-b"), row("low", 20)]
        box = [2, 2, 10, 10]
        predictions = [{"source_id": record["image_sha256"],
                        "detections": [{"bbox_xyxy": box, "confidence": score}]}
                       for record, score in zip(rows, (.9, .8, .7, .85, .05), strict=True)]
        selected, flagged = select_candidates(rows, predictions, .15, 5., 3)
        self.assertEqual(flagged, 4)
        self.assertEqual([item["image_sha256"] for item in selected], ["x", "b", "z"])
        self.assertEqual([item["nearby_overlapping_frames"] for item in selected], [1, 0, 0])
        with self.assertRaisesRegex(ValueError, "Prediction order"):
            select_candidates(rows, list(reversed(predictions)), .15, 5., 3)
