import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from export_p430_review_crops import export_session, load_overrides
from prepare_team_review import write_pack

from edge_threat_response.dataset.review_web import CENTER_REVIEW_SCOPE, VIDEO_REVIEW_SCHEMA, ReviewStore


class P430ReviewExportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.capture = self.root / "p430-fixture"
        self.qa = self.root / "qa-fixture"
        originals = []
        for i, color in enumerate(("red", "blue")):
            stream = io.BytesIO()
            Image.new("RGB", (80, 40), color).save(stream, "PNG")
            originals.append({
                "bytes": stream.getvalue(), "image_path": f"{i}.png", "source_video_sha256": "fixture-video",
                "timestamp_s": i, "boxes": [],
            })
        spot_checks = [
            {**item, "source_id": self.capture.name, "source_review_id": i, "source_review_version": 1,
             "source_image_sha256": hashlib.sha256(item["bytes"]).hexdigest()}
            for i, item in enumerate(originals)
        ]
        self.base = self.make_pack(self.capture, originals)
        self.spot = self.make_pack(self.qa, spot_checks)
        for i in range(2):
            self.base.save(i, 0, self.verdict("target_cctv", "no", []))
        self.spot.save(0, 0, self.verdict("target_cctv", "yes", [[24, 12, 32, 16]]))
        self.spot.save(1, 0, {**self.verdict("non_target", None, []), "exclude_reason": "other"})

    @staticmethod
    def make_pack(root, rows):
        write_pack("review", rows, {"capture_session_id": root.name}, root=root)
        return ReviewStore(root / "review", review_schema=VIDEO_REVIEW_SCHEMA)

    @staticmethod
    def verdict(domain, presence, boxes):
        return {"domain": domain, "knife_presence": presence, "reviewed_boxes": boxes,
                "reviewer": "QA", "review_scope": CENTER_REVIEW_SCOPE}

    def export(self):
        output = self.root / "output"
        (output / "images").mkdir(parents=True)
        (output / "labels").mkdir()
        overrides, _ = load_overrides([self.qa], {self.capture.name})
        manifest, audit = io.StringIO(), io.StringIO()
        summary = export_session(self.capture, output, manifest, overrides, audit, True)
        return output, summary, json.loads(manifest.getvalue()), [
            json.loads(line) for line in audit.getvalue().splitlines()
        ]

    def test_overrides_write_one_positive_and_explicitly_exclude_the_other(self):
        output, counts, row, resolutions = self.export()
        self.assertEqual((1, 1, 2), (counts["positive"], counts["excluded"], counts["overrides_applied"]))
        self.assertEqual(1, counts["overrides_held_out"])
        self.assertEqual(["target_cctv", "non_target"], [r["domain"] for r in resolutions])
        self.assertEqual(1, row["override"]["source_review_version"])
        self.assertEqual("0 0.2000000000 0.2000000000 0.2000000000 0.2000000000",
                         next((output / "labels").iterdir()).read_text().strip())
        self.assertEqual(["no", "no"], [item["review"]["knife_presence"] for item in self.base.items()])

    def test_rejects_stale_and_duplicate_overrides(self):
        with self.assertRaisesRegex(ValueError, "More than one spot-check"):
            load_overrides([self.qa, self.qa], {self.capture.name})
        self.base.save(0, 1, self.verdict("target_cctv", "no", []))
        with self.assertRaisesRegex(ValueError, "saved version changed"):
            self.export()
