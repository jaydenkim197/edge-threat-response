import json
import unittest
from pathlib import Path

from edge_threat_response.training_pair import load_plan


class M2ProfilesTests(unittest.TestCase):
    def test_variants_change_only_the_declared_axes_and_preserve_fixed_budget(self):
        folder = Path(__file__).resolve().parents[1]/"configs/training"
        base = load_plan(folder/"m2-real.pc13.json")
        axes = {"m2-res960.pc11.json": {"imgsz"},
                "m2-mildaug.pc12.json": {"mosaic", "scale", "close_mosaic"},
                "m2-seed2.pc14.json": {"seed"}}
        ids = {base["pair_id"]}
        for filename, expected in axes.items():
            plan = load_plan(folder/filename)
            self.assertEqual(expected, {k for k in base["arguments"] if base["arguments"][k] != plan["arguments"][k]})
            self.assertNotIn(plan["pair_id"], ids)
            ids.add(plan["pair_id"])
            self.assertEqual((50, 16, 16), tuple(plan["arguments"][k] for k in ("epochs", "batch", "nbs")))
