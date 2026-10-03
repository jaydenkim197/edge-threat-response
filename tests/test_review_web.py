import csv
import hashlib
import http.client
import io
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from edge_threat_response.dataset.review_web import ConflictError, ReviewStore, make_handler


class ReviewWebTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "images").mkdir()
        (self.root / "images/001.jpg").write_bytes(b"fixture bytes")
        self.csv = self.root / "review.csv"
        self.csv.write_text("image_path,original_split,reviewer,rights_verified,coordinate_verified\n"
                            "source/sample.jpg,train,,,\n", encoding="utf-8")
        self.evidence = self.root / "image-evidence.jsonl"
        self.evidence.write_text(json.dumps({"sample_no": 1, "image_path": "source/sample.jpg",
                                  "image_file": "images/001.jpg", "width": 100, "height": 100,
                                  "image_sha256": hashlib.sha256(b"fixture bytes").hexdigest(),
                                  "knife_count": 0, "knife_boxes_xyxy_raw": []}), encoding="utf-8")
        self.store = ReviewStore(self.root)
        self.fields = {"domain": "useful_real", "label_quality": "good", "bbox_completeness": "yes",
                       "exclude": "no", "reviewer": "human-fixture", "negative_knife_absence": "yes"}

    def tearDown(self):
        self.temporary.cleanup()

    def test_persist_resume_original_immutable_history_and_export(self):
        original = self.csv.read_bytes()
        result = self.store.save(0, 0, self.fields)
        self.assertEqual(1, result["version"])
        resumed = ReviewStore(self.root)
        self.assertEqual("human-fixture", resumed.items()[0]["review"]["reviewer"])
        resumed.save(0, 1, {**self.fields, "notes": "=1+1"})
        with resumed.connect() as connection:
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM history").fetchone()[0])
        rows = list(csv.DictReader(io.StringIO(resumed.export_csv().decode("utf-8-sig"))))
        self.assertEqual("'=1+1", rows[0]["notes"])
        self.assertEqual("", rows[0]["rights_verified"])
        self.assertEqual("", rows[0]["coordinate_verified"])
        self.assertEqual(original, self.csv.read_bytes())

    def test_validation_blocks_false_approval_incomplete_and_stale_writes(self):
        for fields in ({}, {**self.fields, "reviewer": " "},
                       {**self.fields, "negative_knife_absence": ""},
                       {**self.fields, "rights_verified": "yes"},
                       {**self.fields, "exclude": "uncertain"},
                       {**self.fields, "domain": "invalid"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.store.save(0, 0, fields)
        self.store.save(0, 0, self.fields)
        with self.assertRaises(ConflictError):
            self.store.save(0, 0, self.fields)
        with self.assertRaises(ValueError):
            self.store.save(-1, 0, self.fields)

    def test_pack_changes_and_path_escape_fail_closed(self):
        original = self.evidence.read_bytes()
        row = json.loads(original)
        row["image_file"] = "../escape.jpg"
        self.evidence.write_text(json.dumps(row), encoding="utf-8")
        with self.assertRaises(ValueError):
            ReviewStore(self.root)
        self.evidence.write_bytes(original)
        (self.root / "images/001.jpg").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            ReviewStore(self.root)

    def test_simple_negative_verdict_and_legacy_compatibility(self):
        self.store.save(0, 0, self.fields)
        legacy = self.store.items()[0]["review"].copy()
        self.assertEqual(legacy, ReviewStore(self.root).items()[0]["review"])
        simple = {"review_schema": "simple-v2", "domain": "non_target",
                  "annotation_verdict": "ok", "reviewer": "human-fixture"}
        result = self.store.save(0, 1, simple)
        self.assertEqual("yes", result["review"]["negative_knife_absence"])
        self.assertEqual("yes", result["review"]["bbox_completeness"])
        self.assertEqual("no", result["review"]["exclude"])
        self.store.save(0, 2, {**simple, "annotation_verdict": "unclear"})
        problem = {**simple, "annotation_verdict": "problem", "notes": "Visible knife without a box"}
        result = self.store.save(0, 3, problem)
        self.assertEqual("no", result["review"]["negative_knife_absence"])
        self.assertEqual("no", result["review"]["bbox_completeness"])
        self.assertEqual("uncertain", result["review"]["exclude"])
        with self.store.connect() as connection:
            first = json.loads(connection.execute("SELECT payload FROM history ORDER BY sequence LIMIT 1").fetchone()[0])
        self.assertEqual(legacy, first)
        self.assertIn("simple-v2", self.store.export_csv().decode("utf-8-sig"))

    def test_simple_positive_problem_does_not_invent_missing_boxes(self):
        evidence = json.loads(self.evidence.read_text(encoding="utf-8"))
        evidence.update(knife_count=1, knife_boxes_xyxy_raw=[[1, 2, 10, 20]])
        self.evidence.write_text(json.dumps(evidence), encoding="utf-8")
        positive = ReviewStore(self.root, database=self.root / "positive.sqlite3")
        fields = {"review_schema": "simple-v2", "domain": "target_cctv",
                  "annotation_verdict": "problem", "reviewer": "human-fixture", "notes": "Incorrect box"}
        result = positive.save(0, 0, fields)
        self.assertEqual("unclear", result["review"]["bbox_completeness"])
        self.assertEqual("", result["review"]["negative_knife_absence"])
        result = positive.save(0, 1, {**fields, "annotation_verdict": "ok", "bbox_completeness": "no"})
        self.assertEqual("yes", result["review"]["bbox_completeness"])

    def test_simple_requires_two_answers_identity_and_problem_note(self):
        fields = {"review_schema": "simple-v2", "domain": "non_target",
                  "annotation_verdict": "ok", "reviewer": "human-fixture"}
        for changes in ({"domain": ""}, {"annotation_verdict": ""}, {"reviewer": " "},
                        {"annotation_verdict": "problem"}, {"rights_verified": "yes"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.store.save(0, 0, {**fields, **changes})

    def test_http_assets_save_export_and_security(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.store, "fixture-token"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
            for path in ("/", "/app.js", "/style.css", "/api/items", "/api/images/0"):
                client.request("GET", path)
                response = client.getresponse()
                self.assertEqual(200, response.status, path)
                self.assertIn("frame-ancestors 'none'", response.getheader("Content-Security-Policy"))
                response.read()
            client.request("GET", "/api/items")
            response = client.getresponse()
            self.assertEqual("simple-v2", json.loads(response.read())["review_schema"])
            client.request("GET", "/api/items", headers={"Host": "attacker.example"})
            response = client.getresponse()
            self.assertEqual(403, response.status)
            response.read()
            client.request("GET", "/../../secrets")
            response = client.getresponse()
            self.assertEqual(404, response.status)
            response.read()
            body = json.dumps({"id": 0, "version": 0, "fields": self.fields})
            client.request("POST", "/api/review", body, {"Content-Type": "application/json"})
            response = client.getresponse()
            self.assertEqual(403, response.status)
            response.read()
            client.request("POST", "/api/review", body,
                           {"Content-Type": "application/json", "X-Review-Token": "fixture-token",
                            "Origin": "https://attacker.example"})
            response = client.getresponse()
            self.assertEqual(403, response.status)
            response.read()
            client.request("POST", "/api/review", body,
                           {"Content-Type": "application/json", "X-Review-Token": "fixture-token"})
            response = client.getresponse()
            self.assertEqual(200, response.status)
            self.assertEqual(1, json.loads(response.read())["version"])
            client.request("GET", "/api/export")
            response = client.getresponse()
            self.assertEqual(200, response.status)
            self.assertIn("human-review.csv", response.getheader("Content-Disposition"))
            self.assertIn("human-fixture", response.read().decode("utf-8-sig"))
            client.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
