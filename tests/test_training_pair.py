import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from edge_threat_response.training import TrainingConfig, run_training, training_preflight, _sha256_file
from edge_threat_response.training_pair import prepare_pair, compare_pair, load_plan


ROOT = Path(__file__).resolve().parents[1]


class TrainingPairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.manifest = self.source / "materialized-manifest.jsonl"
        rows = []
        for index, (split, positive) in enumerate([("train", True), ("train", True), ("train", False),
                                                  ("train", False), ("train", False), ("val", True),
                                                  ("val", False), ("test", True), ("test", False)]):
            image, label = self.source / "images" / split / f"{index}.png", self.source / "labels" / split / f"{index}.txt"
            image.parent.mkdir(parents=True, exist_ok=True)
            label.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(f"unique fixture {index}".encode())
            label.write_text("0 0.5 0.5 0.2 0.2\n" if positive else "", encoding="utf-8")
            rows.append({"image_id": str(index), "source_dataset": "sohas", "source_group": f"group-{index}",
                         "planned_split": split, "output_image": image.relative_to(self.source).as_posix(),
                         "output_label": label.relative_to(self.source).as_posix(), "image_sha256": _sha256_file(image)})
        self.rows = rows
        self.manifest.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        self.plan = self.root / "plan.json"
        plan = json.loads((ROOT / "configs/training/sohas-pair.pc13.json").read_text(encoding="utf-8"))
        plan["arguments"].update(batch=2, nbs=2, epochs=2)
        self.plan.write_text(json.dumps(plan), encoding="utf-8")
        self.checkpoint = self.root / "pretrained.pt"
        self.checkpoint.write_bytes(b"not a real model - plumbing fixture")
        self.output = self.root / "pair"

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        return prepare_pair(self.plan, self.manifest, self.checkpoint, self.output)

    def approve_fixture(self):
        path = self.output / "approval.pending.json"
        approval = json.loads(path.read_text(encoding="utf-8"))
        approval.update(status="approved", approval_id="fixture", reviewer_alias="fixture-reviewer", approved_at="2026-10-04")
        approval["gates"] = {key: True for key in approval["gates"]}
        path.write_text(json.dumps(approval), encoding="utf-8")
        return path

    def arguments(self, recipe):
        return {"config_path": self.output / f"{recipe}-training.json", "data_yaml": self.output / f"{recipe}-data.yaml",
                "dataset_manifest": self.output / f"{recipe}-manifest.jsonl", "output_dir": self.root / "runs"}

    def test_same_unique_positives_common_eval_and_equal_draw_budget(self):
        result = self.prepare()
        self.assertEqual(6, result["draws_per_epoch_each"])
        self.assertEqual(6, result["planned_optimizer_updates_each"])
        r1 = (self.output / "R1-train.txt").read_text().splitlines()
        h1 = (self.output / "H1-train.txt").read_text().splitlines()
        self.assertEqual(len(r1), len(h1))
        self.assertEqual(2, len(set(h1)))
        self.assertTrue(set(h1).issubset(r1))
        self.assertEqual([3, 3], sorted(Counter(h1).values()))
        data = [json.loads((self.output / f"{recipe}-data.yaml").read_text()) for recipe in ("R1", "H1")]
        self.assertEqual(data[0]["val"], data[1]["val"])
        self.assertEqual(data[0]["test"], data[1]["test"])
        self.assertEqual("pending", json.loads((self.output / "approval.pending.json").read_text())["status"])
        with self.assertRaisesRegex(ValueError, "new directory"):
            self.prepare()

    def test_pending_or_missing_approval_blocks_before_model_loading(self):
        self.prepare()
        called = []
        factory = lambda name: called.append(name)
        with self.assertRaisesRegex(ValueError, "requires"):
            run_training(**self.arguments("R1"), model_factory=factory)
        with self.assertRaisesRegex(ValueError, "pending"):
            run_training(**self.arguments("R1"), approval_path=self.output / "approval.pending.json", model_factory=factory)
        self.assertEqual([], called)
        self.assertFalse((self.root / "runs").exists())

    def test_byte_mutation_and_batch_change_invalidate_approval(self):
        self.prepare()
        approval = self.approve_fixture()
        with self.assertRaisesRegex(ValueError, "batch changes"):
            run_training(**self.arguments("R1"), approval_path=approval, batch_override=4, model_factory=lambda _: None)
        label = self.source / "labels/train/0.txt"
        label.write_text("0 0.4 0.4 0.2 0.2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "bytes changed"):
            run_training(**self.arguments("R1"), approval_path=approval, model_factory=lambda _: None)

    def test_rejects_leakage_invalid_budget_and_gate_disabling(self):
        self.rows[1]["image_id"] = self.rows[0]["image_id"]
        self.manifest.write_text("\n".join(json.dumps(row) for row in self.rows), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "IDs"):
            self.prepare()
        self.rows[1]["image_id"] = "1"
        self.rows[-1]["source_group"] = self.rows[0]["source_group"]
        self.manifest.write_text("\n".join(json.dumps(row) for row in self.rows), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "crosses"):
            self.prepare()
        plan = json.loads(self.plan.read_text())
        plan["arguments"]["nbs"] = 64
        self.plan.write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, "nbs"):
            load_plan(self.plan)
        config = self.root / "gated.json"
        config.write_text(json.dumps({"schema_version": 1, "profile_id": "test", "model": "model.pt", "task": "detect",
                                     "run_name": "test", "recipe_id": "R1", "approval_required": False, "arguments": {}}))
        with self.assertRaises(ValueError):
            TrainingConfig.load(config)

    def test_approved_fake_runs_record_hashes_and_compare_only_common_tuning(self):
        self.prepare()
        approval = self.approve_fixture()

        class FakeModel:
            def train(self, **arguments):
                directory = Path(arguments["project"]) / arguments["name"]
                (directory / "weights").mkdir(parents=True)
                (directory / "weights/best.pt").write_bytes(b"fake checkpoint")
                return SimpleNamespace(save_dir=directory, results_dict={"metrics/precision(B)": 0.5, "metrics/recall(B)": 0.5})

        for recipe in ("R1", "H1"):
            result = run_training(**self.arguments(recipe), approval_path=approval, model_factory=lambda _: FakeModel())
            self.assertEqual(6, result["approval"]["planned_optimizer_updates"])
            self.assertEqual(recipe, result["recipe_id"])
            self.assertTrue(result["artifacts"])
        paths = sorted((self.root / "runs").glob("*-invocation.json"))
        by_recipe = {json.loads(path.read_text(encoding="utf-8"))["recipe_id"]: path for path in paths}
        result = compare_pair(by_recipe["R1"], by_recipe["H1"], self.root / "comparison")
        self.assertEqual("common_validation_tuning", result["evaluation_partition"])
        h1 = json.loads(by_recipe["H1"].read_text(encoding="utf-8"))
        h1["approval"]["bound_inputs"]["val_list"] = "different"
        by_recipe["H1"].write_text(json.dumps(h1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "lists differ"):
            compare_pair(by_recipe["R1"], by_recipe["H1"], self.root / "bad-comparison")


if __name__ == "__main__":
    unittest.main()
