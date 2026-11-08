import json
import random
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.dataset.development_subset import proxy_components
from edge_threat_response.dataset.followup import open_images_candidates, prepare_followup, read_rows
from edge_threat_response.dataset.image_screening import image_signature
from edge_threat_response.replay import write_jsonl
from edge_threat_response.training import _sha256_file


class FollowupTests(unittest.TestCase):
    def fixture(self, root):
        from PIL import Image
        root.mkdir(parents=True, exist_ok=True)
        source = root/"source"
        source.mkdir()
        signatures, rows = [], []
        for i, split in enumerate(("train", "train", "train", "val", "test")):
            name = ("alpha", "beta", "gamma", "delta", "epsilon")[i]
            image, label = source/(name+".png"), source/(name+".txt")
            rng = random.Random(i)
            Image.frombytes("RGB", (32, 32), bytes(rng.randrange(256) for _ in range(3072))).save(image)
            label.write_text("0 .5 .5 .2 .2\n")
            signature = {**image_signature(image), "record_id": image.name, "dataset_id": "sohas", "original_split": split}
            signatures.append(signature)
            rows.append({"image_id": image.name, "source_dataset": "sohas", "split": split,
                "image": str(image), "label": str(label), "image_sha256": _sha256_file(image),
                "label_sha256": _sha256_file(label), "knife_count": 1})
        groups = proxy_components(signatures, [])
        for row in rows:
            row["source_group"] = groups[row["image_id"]]
        write_jsonl(source/"inventory.jsonl", rows)
        write_jsonl(source/"signatures.jsonl", signatures)
        write_jsonl(source/"pairs.jsonl", [])
        write_jsonl(source/"quality.jsonl", [{"raw_split": "train", "raw_overlay_matches": True,
            "verdict": "problem", "image_sha256": rows[0]["image_sha256"]}])
        image = root/"new.png"
        rng = random.Random(10)
        Image.frombytes("RGB", (32, 32), bytes(rng.randrange(256) for _ in range(3072))).save(image)
        candidate = {**image_signature(image), "record_id": "new-source/new.png", "dataset_id": "new-source",
            "image_file": str(image), "label_text": "0 .5 .5 .2 .2\n", "original_split": "train",
            "source_url": "test", "license": "test", "annotation_provenance": {}, "coordinate_contract": "test"}
        kwargs = dict(baseline=source/"inventory.jsonl", signatures=source/"signatures.jsonl",
            pairs=source/"pairs.jsonl", quality_snapshot=source/"quality.jsonl", candidates=[candidate],
            protected=[], output=root/"out", expected_quality_exclusions=1)
        return rows, signatures, candidate, kwargs

    def test_train_cleanup_and_additions_preserve_holdout_bytes_order_and_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            rows, _, candidate, args = self.fixture(Path(d))
            old = {p: p.read_bytes() for p in (args["baseline"], args["quality_snapshot"])}
            result = prepare_followup(**args)
            saved = read_rows(args["output"]/"inventory.jsonl")
            self.assertEqual({"train": 3, "val": 1, "test": 1}, result["split_counts"])
            self.assertEqual(1, result["known_quality_exclusions"])
            self.assertNotIn(rows[0]["image_sha256"], {r["image_sha256"] for r in saved})
            for split in ("val", "test"):
                before = [r for r in rows if r["split"] == split]
                after = [r for r in saved if r["split"] == split]
                self.assertEqual([r["image_id"] for r in before], [r["image_id"] for r in after])
                self.assertEqual(Path(before[0]["label"]).read_bytes(), Path(after[0]["label"]).read_bytes())
            self.assertTrue(all(p.read_bytes() == raw for p, raw in old.items()))
            self.assertFalse(result["final_evaluation_allowed"])

    def test_synthetic_provider_negative_requires_evidence_and_preserves_marker(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, candidate, args = self.fixture(Path(d))
            candidate.update(label_text="", synthetic=True)
            with self.assertRaisesRegex(ValueError, "absence evidence"):
                prepare_followup(**args)
            candidate.update(provider_knife_absence=True, annotation_provenance={"provider_knife_absence": True})
            result = prepare_followup(**args)
            saved = next(r for r in read_rows(args["output"]/"inventory.jsonl") if r["image_id"] == candidate["record_id"])
            self.assertTrue(saved["synthetic"])
            self.assertTrue(saved["provider_knife_absence"])
            self.assertEqual(0, saved["knife_count"])
            self.assertFalse(saved["negative_absence_verified"])
            self.assertEqual("", Path(saved["label"]).read_text())

    def test_new_eval_proxy_and_represented_train_are_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            rows, signatures, candidate, args = self.fixture(Path(d))
            for index in (1, 3):
                args["candidates"].append({**candidate, **signatures[index], "record_id": f"other/{index}.png",
                    "dataset_id": "new-source", "image_file": rows[index]["image"]})
            result = prepare_followup(**args)
            self.assertEqual(1, result["accepted_additional_images"])
            self.assertEqual(1, result["exclusions"]["protected_proxy_group"])
            self.assertEqual(1, result["exclusions"]["represented_source_proxy_group"])

    def test_expanded_protected_pack_removes_matching_baseline_train(self):
        with tempfile.TemporaryDirectory() as d:
            rows, signatures, _, args = self.fixture(Path(d))
            args["protected"] = [{**signatures[1], "record_id": "protected/other.png", "dataset_id": "us-mock-protected"}]
            result = prepare_followup(**args)
            self.assertEqual(1, result["exclusions"]["expanded_protected_group"])
            self.assertEqual(2, result["split_counts"]["train"])

    def test_frozen_holdout_bridge_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            _, signatures, candidate, args = self.fixture(Path(d))
            # New proxy filenames bridge the otherwise distinct val/test components.
            args["protected"] = [
                {**signatures[3], "record_id": "guards/session001.png", "dataset_id": "protected"},
                {**signatures[4], "record_id": "guards/session002.png", "dataset_id": "protected"}]
            with self.assertRaisesRegex(ValueError, "links frozen val and test"):
                prepare_followup(**args)
            self.assertFalse(args["output"].exists())

    def test_changed_baseline_and_output_inside_source_fail_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            rows, _, _, args = self.fixture(Path(d))
            args["output"] = args["baseline"].parent/"new-output"
            with self.assertRaisesRegex(ValueError, "separate"):
                prepare_followup(**args)
            args["output"] = Path(d)/"out"
            Path(rows[0]["label"]).write_text("")
            with self.assertRaisesRegex(ValueError, "bytes changed"):
                prepare_followup(**args)

    def test_open_images_uses_provider_knife_boxes_and_rejects_semantic_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            label = root/"0123456789abcdef.txt"
            label.write_text("0 .5 .5 .2 .2\n")
            row = {"image": str(root/"0123456789abcdef.jpg"), "label": str(label), "original_split": "train",
                "image_metadata": {"Rotation": "0", "License": "https://creativecommons.org/licenses/by/2.0/"},
                "annotation_rows": [{"LabelName": "/m/04ctx", "Confidence": "1", "IsGroupOf": "0",
                    "XMin": ".4", "YMin": ".4", "XMax": ".6", "YMax": ".6"}]}
            manifest = root/"candidates.jsonl"
            write_jsonl(manifest, [row])
            self.assertEqual(1, len(open_images_candidates(manifest)))
            row["annotation_rows"][0]["LabelName"] = "weapon"
            write_jsonl(manifest, [row])
            with self.assertRaisesRegex(ValueError, "Knife"):
                open_images_candidates(manifest)
            row["annotation_rows"][0]["LabelName"] = "/m/04ctx"
            row["annotation_rows"][0]["XMin"] = ".3"
            write_jsonl(manifest, [row])
            with self.assertRaisesRegex(ValueError, "no longer match"):
                open_images_candidates(manifest)


if __name__ == "__main__":
    unittest.main()
