import importlib.util
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.training import _sha256_file
from edge_threat_response.dataset.development_subset import proxy_components

spec = importlib.util.spec_from_file_location("prepare_s1", Path(__file__).resolve().parents[1]/"tools/prepare_s1_pc13.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SyntheticSourceTests(unittest.TestCase):
    def test_only_explicit_knife_boxes_are_kept_without_role_or_negative_inference(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            records = []
            for index, text in enumerate(["0 .5 .5 .7 .7\n3 .5 .5 .1 .1\n", "2 .5 .5 .1 .1\n", "3 nan .5 .1 .1\n", "9 .5 .5 .1 .1\n"]):
                Image.new("RGB", (24, 24), (40, 50, 60)).save(root/f"scene{index}.png")
                (root/f"scene{index}.txt").write_text(text)
                records.append({"image": f"scene{index}.png", "label": f"scene{index}.txt"})
            candidates, issues = module.source_candidates(root, records, dataset_id="atm",
                class_names={0: "offender", 1: "victim", 2: "gun", 3: "knife"},
                source_url="https://example.org", license_name="CC BY-NC 4.0", source_evidence={"record": "hash"})
            self.assertEqual(1, len(candidates))
            self.assertEqual("0 .5 .5 .1 .1\n", candidates[0]["label_text"])
            self.assertTrue(candidates[0]["synthetic"])
            self.assertFalse(candidates[0]["annotation_provenance"]["holding_labels_inferred"])
            self.assertEqual(3, len(issues))
            self.assertEqual("no_provider_knife_not_assumed_negative", issues[0]["reason"])

    def test_source_hashes_and_paths_fail_closed(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGB", (24, 24)).save(root/"image.png")
            label = root/"image.txt"
            label.write_text("1 .5 .5 .1 .1\n")
            options = dict(dataset_id="cctv", class_names={0: "person", 1: "knife"},
                source_url="https://example.org", license_name="CC BY-NC 4.0", source_evidence={"record": "hash"})
            record = {"image": "image.png", "label": "image.txt", "image_sha256": _sha256_file(root/"image.png"),
                      "label_sha256": _sha256_file(label)}
            label.write_text("1 .4 .4 .1 .1\n")
            selected, issues = module.source_candidates(root, [record], **options)
            self.assertEqual([], selected)
            self.assertIn("hash changed", issues[0]["reason"])
            with self.assertRaisesRegex(ValueError, "escapes"):
                module.source_candidates(root, [{"image": "../image.png", "label": "image.txt"}], **options)
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                module.source_candidates(root, [record, record], **options)

    def test_provider_declared_negative_is_distinct_from_unlabelled_absence(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGB", (24, 24)).save(root/"negative.png")
            (root/"negative.txt").write_text("0 .5 .5 .5 .5\n")
            record = {"image": "negative.png", "label": "negative.txt", "provider_knife_absence": True}
            options = dict(dataset_id="cctv", class_names={0: "person", 1: "knife"},
                source_url="https://example.org", license_name="CC BY-NC 4.0", source_evidence={"readme": "hash"})
            selected, issues = module.source_candidates(root, [record], **options)
            self.assertEqual([], issues)
            self.assertEqual("\n", selected[0]["label_text"])
            self.assertTrue(selected[0]["annotation_provenance"]["provider_knife_absence"])
            (root/"negative.txt").write_text("1 .5 .5 .1 .1\n")
            selected, issues = module.source_candidates(root, [record], **options)
            self.assertEqual([], selected)
            self.assertIn("no Knife", issues[0]["reason"])

    def test_generic_class_counters_do_not_link_sources_but_exact_hashes_do(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            Image.new("RGB", (24, 24)).save(root/"knife_0002.png")
            (root/"knife_0002.txt").write_text("1 .5 .5 .1 .1\n")
            selected, _ = module.source_candidates(root,
                [{"image": "knife_0002.png", "label": "knife_0002.txt"}], dataset_id="new-cctv",
                class_names={0: "person", 1: "knife"}, source_url="https://example.org",
                license_name="CC BY-NC 4.0", source_evidence={"record": "hash"})
            candidate, = selected
            reference = {"record_id": "sohas/knife_0001.jpg", "image_sha256": "a"*64}
            groups = proxy_components([reference, candidate], [])
            self.assertNotEqual(groups[reference["record_id"]], groups[candidate["record_id"]])
            reference["image_sha256"] = candidate["image_sha256"]
            groups = proxy_components([reference, candidate], [])
            self.assertEqual(groups[reference["record_id"]], groups[candidate["record_id"]])


if __name__ == "__main__":
    unittest.main()
