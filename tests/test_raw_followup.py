import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.training import _sha256_file

spec = importlib.util.spec_from_file_location("finish_raw_training", Path(__file__).resolve().parents[1]/"tools/finish_raw_training.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FollowupReferenceTests(unittest.TestCase):
    def test_only_selected_hash_bound_reference_checkpoints_are_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            weight = root/"m1.pt"
            weight.write_bytes(b"frozen-m1")
            protocol = root/"models.json"
            protocol.write_text(json.dumps({"cases": [{"id": "m1", "checkpoint": str(weight),
                "checkpoint_sha256": _sha256_file(weight)}, {"id": "unused"}]}))
            self.assertEqual(["m1"], [c["id"] for c in module.reference_cases(protocol, ["m1"])])
            for ids in ([], ["missing"], ["m1", "m1"]):
                with self.assertRaises(ValueError):
                    module.reference_cases(protocol, ids)
            weight.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "changed"):
                module.reference_cases(protocol, ["m1"])
