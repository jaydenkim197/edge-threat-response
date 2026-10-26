import json
import unittest

from edge_threat_response.training_refinement import prepare_refinement


class TrainingRefinementTests(unittest.TestCase):
    def setUp(self):
        import test_development_subset
        self.fixture = test_development_subset.DevelopmentSubsetTests()
        self.fixture.setUp()
        self.base, _ = self.fixture.prepare()

    def tearDown(self):
        self.fixture.tearDown()

    def test_only_bounded_args_change_and_holdouts_and_base_are_preserved(self):
        before = {p.name: p.read_bytes() for p in self.base.iterdir() if p.is_file()}
        for variant in ("adamw", "smallscale"):
            output = self.fixture.root / variant
            result = prepare_refinement(self.base, output, variant, "fixture-not-human-approval")
            for name in ("train.txt", "val.txt", "test.txt", "DEV-manifest.jsonl"):
                self.assertEqual(before[name], (output / name).read_bytes())
            config = json.loads((output / "training.json").read_text())
            old = json.loads(before["training.json"])
            changed = {key for key in config["arguments"] if config["arguments"][key] != old["arguments"][key]}
            self.assertEqual({"optimizer", "lr0"} | ({"scale"} if variant == "smallscale" else set()), changed)
            self.assertFalse(result["final_evaluation_allowed"])
            self.assertEqual(0, result["new_source_images"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.base.iterdir() if p.is_file()})

    def test_unknown_variant_overwrite_and_changed_parent_rejected(self):
        output = self.fixture.root / "new"
        with self.assertRaises(ValueError):
            prepare_refinement(self.base, output, "unbounded", "fixture")
        with self.assertRaises(ValueError):
            prepare_refinement(self.base, self.base, "adamw", "fixture")
        (self.base / "train.txt").write_text("changed")
        with self.assertRaisesRegex(ValueError, "hashes changed"):
            prepare_refinement(self.base, output, "adamw", "fixture")
