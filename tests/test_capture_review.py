import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from prepare_capture_review import existing_frames, near_duplicate


class CaptureReviewTests(unittest.TestCase):
    def test_small_local_change_is_preserved_even_in_a_large_image(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = Image.new("L", (3840, 2160), 40)
            first.save(root / "first.png")
            self.assertTrue(near_duplicate(root / "first.png", root / "first.png")[0])
            second = first.copy()
            second.paste(220, (1200, 1400, 1208, 1416))
            second.save(root / "second.png")
            self.assertFalse(near_duplicate(root / "first.png", root / "second.png")[0])

    def test_reused_frames_are_bound_to_the_recording_and_original_bytes(self):
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new("RGB", (40, 30), "red").save(root / "one.jpg")
            digest = hashlib.sha256((root / "one.jpg").read_bytes()).hexdigest()
            row = {"file": "one.jpg", "sha256": digest, "width": 40, "height": 30,
                   "timestamp_s": .025, "human_review": "pending", "training_approved": False}
            (root / "frames.jsonl").write_text(json.dumps(row), encoding="utf-8")
            (root / "summary.json").write_text(json.dumps(
                {"source_sha256": "source", "frames": 1, "width": 40, "height": 30}), encoding="utf-8")
            self.assertEqual([(root / "one.jpg", .025)], existing_frames(root, "source"))
            with self.assertRaises(ValueError):
                existing_frames(root, "wrong source")
            (root / "one.jpg").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                existing_frames(root, "source")
