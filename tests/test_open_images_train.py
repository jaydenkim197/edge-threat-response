import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("open_images_train", ROOT/"tools/acquire_open_images_train.py")
acquisition = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acquisition)


class OpenImagesTrainTests(unittest.TestCase):
    def test_acquisition_is_train_positive_only_and_not_auto_merged(self):
        from PIL import Image
        small, large = "0000000000000001", "0000000000000002"
        files = {
            "classes": b'/m/test,Knife\n/m/other,Other\n',
            "boxes": ("ImageID,LabelName,Confidence,XMin,XMax,YMin,YMax,IsGroupOf\n"
                      f"{small},/m/test,1,.1,.15,.1,.15,0\n{large},/m/test,1,.1,.8,.1,.8,0\n").encode(),
            "images": ("ImageID,License,Rotation,Author\n"
                       f"{small},https://creativecommons.org/licenses/by/2.0/,0,source-author\n"
                       f"{large},https://creativecommons.org/licenses/by/2.0/,0,source-author\n").encode(),
        }
        urls = []
        def fake_download(url, target, limit):
            urls.append(url)
            key = next((k for k, v in acquisition.URLS.items() if v == url), None)
            if key: target.write_bytes(files[key])
            else:
                self.assertIn("/train/", url)
                Image.new("RGB", (32, 32), (int(target.stem[-1]), 50, 60)).save(target, "JPEG")
            raw = target.read_bytes()
            return {"url": url, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        with tempfile.TemporaryDirectory() as d, patch.object(acquisition, "download", fake_download), patch.object(acquisition.shutil, "disk_usage", return_value=SimpleNamespace(free=100*1024**3)):
            out = Path(d)/"source"
            result = acquisition.acquire(out, count=2)
            self.assertEqual(2, result["acquired_images"])
            self.assertFalse(result["included_in_current_queue"])
            self.assertFalse(result["human_review_complete"])
            self.assertFalse(result["global_duplicate_check_complete"])
            rows = [json.loads(x) for x in (out/"candidates.jsonl").read_text().splitlines()]
            self.assertTrue(all(r["original_split"] == "train" and not r["knife_absence_verified"] for r in rows))
            self.assertEqual(5, len(urls))

    def test_incomplete_download_is_not_promoted_to_complete_file(self):
        class Response(io.BytesIO):
            headers = {"Content-Length": "10"}
        with tempfile.TemporaryDirectory() as d, patch.object(acquisition.urllib.request, "urlopen", return_value=Response(b"short")):
            target = Path(d)/"metadata.csv"
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                acquisition.download("https://example.invalid/source", target, 100)
            self.assertFalse(target.exists())
            self.assertTrue(target.with_suffix(".csv.partial").exists())


if __name__ == "__main__":
    unittest.main()
