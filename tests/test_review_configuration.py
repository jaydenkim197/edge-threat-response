import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("flask"), "Optional review-server dependencies not installed")
class ReviewConfigurationTests(unittest.TestCase):
    def test_reconfigure_retains_added_sources_and_operational_settings(self):
        source = Path(__file__).resolve().parents[1] / "tools/configure_team_review.py"
        spec = importlib.util.spec_from_file_location("configure_review_fixture", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "data/review/team-server"
            folder.mkdir(parents=True)
            extra = {"id": "additional-source", "name": "Additional", "review_dir": str(root / "immutable-pack"),
                     "review_batches": [{"id": "second", "review_dir": str(root / "second-pack")}],
                     "note": "Preserve provenance and original order"}
            config_file = folder / "config.json"
            config_file.write_text(json.dumps({"datasets": [extra, {"id": "acf", "name": "Retired placeholder", "reason": "source unavailable"}], "reviewer_login": "name",
                                               "backup_interval": 123}), encoding="utf-8")
            with patch.object(module, "ROOT", root), contextlib.redirect_stdout(io.StringIO()):
                module.configure("https://review.example.test")
                first = json.loads(config_file.read_text(encoding="utf-8"))
                module.configure("https://review.example.test")
            result = json.loads(config_file.read_text(encoding="utf-8"))
            self.assertEqual([extra], [e for e in result["datasets"] if e["id"] == extra["id"]])
            self.assertNotIn("acf", [entry["id"] for entry in result["datasets"]])
            self.assertEqual(123, result["backup_interval"])
            self.assertEqual("name", result["reviewer_login"])
            self.assertEqual(first, result)


@unittest.skipUnless(importlib.util.find_spec("PIL"), "Optional image dependencies not installed")
class SignedSourceRangeTests(unittest.TestCase):
    def test_signed_query_is_preserved_and_wrong_range_is_rejected(self):
        source = Path(__file__).resolve().parents[1] / "tools/prepare_team_review.py"
        spec = importlib.util.spec_from_file_location("prepare_review_fixture", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        url = "https://example.test/archive.zip?signature=fixture"
        response = io.BytesIO(b"abcd")
        response.status = 206
        response.headers = {"Content-Range": "bytes 0-3/4"}
        with patch.object(module.urllib.request, "urlopen", return_value=response) as opened:
            reader = module.RangeReader(url, 4, isolate_cache_keys=False)
            self.assertEqual(b"abcd", reader.read(4))
            request = opened.call_args.args[0]
            self.assertEqual(url, request.full_url)
            self.assertEqual("bytes=0-3", request.get_header("Range"))
        response = io.BytesIO(b"abcd")
        response.status = 206
        response.headers = {"Content-Range": "bytes 0-2/4"}
        with patch.object(module.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(ValueError, "Content-Range"):
                module.RangeReader(url, 4, isolate_cache_keys=False).read(4)
