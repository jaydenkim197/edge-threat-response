import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from edge_threat_response.dataset.development_subset import prepare_development, proxy_components
from edge_threat_response.dataset.sohas import VOC_ROOT
from edge_threat_response.training import TrainingConfig, run_training, validate_training_approval

ROOT = Path(__file__).resolve().parents[1]


class DevelopmentSubsetTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.manifest = self.inputs / "review.jsonl"
        self.integrity = self.inputs / "integrity.jsonl"
        self.pairs = self.inputs / "pairs.jsonl"
        self.checkpoint = self.root / "model.pt"
        self.checkpoint.write_bytes(b"fixture checkpoint, not real weights")
        rows, integrity, self.inventory = [], [], {}
        for i in range(18):
            split = "train" if i < 12 else "test"
            folder, annotation_folder = ("images", "annotations/xmls") if split == "train" else ("images_test", "annotations_test/xmls")
            stem = f"scene{chr(97+i)}0001"
            image_ref = f"{VOC_ROOT}/{folder}/{stem}.jpg"
            xml_ref = f"{VOC_ROOT}/{annotation_folder}/{stem}.xml"
            image, xml_path = self.source / image_ref, self.source / xml_ref
            image.parent.mkdir(parents=True, exist_ok=True)
            xml_path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (100, 100), (i * 11, i * 7, i * 3)).save(image)
            positive = i % 3 != 0
            label = "knife" if positive else "pistol"
            xml_path.write_text(f"<annotation><filename>{stem}.jpg</filename><size><width>100</width><height>100</height></size>"
                                f"<object><name>{label}</name><bndbox><xmin>10</xmin><ymin>20</ymin><xmax>30</xmax>"
                                "<ymax>40</ymax></bndbox></object></annotation>", encoding="utf-8")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            for ref in (image_ref, xml_ref):
                data = (self.source / ref).read_bytes()
                self.inventory[ref] = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
            rows.append({"dataset_id": "sohas", "candidate_status": "candidate_positive" if positive else "candidate_negative",
                         "record_id": f"sohas/initial/{i}", "review_verdict": "ok", "review_version": 1,
                         "review_payload_sha256": "0" * 64, "image_path": image_ref, "image_sha256": digest,
                         "original_split": split, "width": 100, "height": 100, "knife_count": int(positive),
                         "raw_boxes_xyxy": [[10, 20, 30, 40]] if positive else []})
            integrity.append({"record_id": image_ref, "image_sha256": digest})
        self.rows = rows
        self.manifest.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        self.integrity.write_text("\n".join(json.dumps(row) for row in integrity), encoding="utf-8")
        self.pairs.write_text(json.dumps({"left": rows[1]["image_path"], "right": rows[2]["image_path"]}), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, output="prepared"):
        target = self.root / output
        with patch("edge_threat_response.dataset.development_subset._inventory", return_value=self.inventory):
            result = prepare_development(manifest=self.manifest, source_root=self.source, integrity_path=self.integrity,
                pairs_path=self.pairs, plan_path=ROOT / "configs/training/sohas-pair.pc13.json", checkpoint=self.checkpoint,
                output=target, authorization_id="fixture-only-not-human-authorization", expected_count=18)
        return target, result

    def test_prepares_only_development_preserves_source_and_bounds_authorization(self):
        before = {str(p): p.read_bytes() for p in self.source.rglob("*") if p.is_file()}
        target, summary = self.prepare()
        self.assertEqual(18, summary["exported"])
        self.assertEqual(12, summary["object_count"])
        self.assertFalse(summary["formal_source_approval"])
        self.assertFalse(summary["final_evaluation_allowed"])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.source.rglob("*") if p.is_file()})
        config = TrainingConfig.load(target / "training.json")
        approval = validate_training_approval(target / "training.json", config, target / "data.yaml",
                                              target / "DEV-manifest.jsonl", target / "development-authorization.json")
        self.assertFalse(approval["final_evaluation_allowed"])
        self.assertEqual("reviewed_sohas_development_only", approval["scope"])
        rows = [json.loads(line) for line in (target / "DEV-manifest.jsonl").read_text().splitlines()]
        assignments = {row["review_record_id"]: row["split"] for row in rows}
        self.assertEqual(assignments["sohas/initial/1"], assignments["sohas/initial/2"])
        with self.assertRaises(ValueError):
            self.prepare()

    def test_snapshot_count_and_box_mutation_rejected(self):
        rows = copy.deepcopy(self.rows)
        rows[0]["candidate_status"] = "hold_review"
        self.manifest.write_text("\n".join(json.dumps(row) for row in rows))
        with self.assertRaisesRegex(ValueError, "Selection changed"):
            self.prepare()
        rows = copy.deepcopy(self.rows)
        rows[1]["raw_boxes_xyxy"][0][0] = 9
        self.manifest.write_text("\n".join(json.dumps(row) for row in rows))
        with self.assertRaisesRegex(ValueError, "annotation mismatch"):
            self.prepare()

    def test_missing_scope_and_changed_bytes_fail_before_model_loading(self):
        target, _ = self.prepare()
        config = TrainingConfig.load(target / "training.json")
        with self.assertRaises(ValueError):
            validate_training_approval(target / "training.json", config, target / "data.yaml", target / "DEV-manifest.jsonl", None)
        path = target / "development-authorization.json"
        original = json.loads(path.read_text())
        for mutate in ("formal", "status", "hash"):
            approval = copy.deepcopy(original)
            if mutate == "formal":
                approval["final_evaluation_allowed"] = True
            elif mutate == "status":
                approval["status"] = "approved"
            else:
                approval["recipes"]["DEV-SOHAS"]["config_sha256"] = "bad"
            path.write_text(json.dumps(approval))
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                validate_training_approval(target / "training.json", config, target / "data.yaml", target / "DEV-manifest.jsonl", path)
        path.write_text(json.dumps(original))
        first = json.loads((target / "DEV-manifest.jsonl").read_text().splitlines()[0])
        Path(first["label"]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            validate_training_approval(target / "training.json", config, target / "data.yaml", target / "DEV-manifest.jsonl", path)

    def test_dev_recipe_cannot_disable_approval_or_promote_to_formal_r1(self):
        target, _ = self.prepare()
        path = target / "training.json"
        payload = json.loads(path.read_text())
        payload["approval_required"] = False
        path.write_text(json.dumps(payload))
        with self.assertRaises(ValueError):
            TrainingConfig.load(path)
        payload.update(approval_required=True, recipe_id="R1")
        path.write_text(json.dumps(payload))
        config = TrainingConfig.load(path)
        with self.assertRaisesRegex(ValueError, "pending"):
            validate_training_approval(path, config, target / "data.yaml", target / "DEV-manifest.jsonl", target / "development-authorization.json")

    def test_family_and_transitive_full_inventory_pairs_are_not_split(self):
        records = [{"record_id": name, "image_sha256": name} for name in ("a001.jpg", "a002.jpg", "bridge.jpg", "c1.jpg")]
        groups = proxy_components(records, [{"left": "a002.jpg", "right": "bridge.jpg"}, {"left": "bridge.jpg", "right": "c1.jpg"}])
        self.assertEqual(1, len(set(groups.values())))
        with self.assertRaises(ValueError):
            proxy_components(records, [{"left": "a001.jpg", "right": "outside.jpg"}])

    def test_fake_training_evidence_is_explicitly_development_only(self):
        target, _ = self.prepare()
        class FakeModel:
            def train(self, **kwargs):
                path = Path(kwargs["project"]) / kwargs["name"]
                path.mkdir(parents=True)
                return type("Result", (), {"save_dir": path, "results_dict": {}})()
        result = run_training(target / "training.json", data_yaml=target / "data.yaml", output_dir=self.root / "runs",
                              dataset_manifest=target / "DEV-manifest.jsonl", approval_path=target / "development-authorization.json",
                              model_factory=lambda _: FakeModel())
        self.assertEqual("development_only", result["evaluation_scope"])
        self.assertEqual("DEV-SOHAS", result["recipe_id"])
