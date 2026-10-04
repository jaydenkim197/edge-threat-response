import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path


class ReviewExpansionTests(unittest.TestCase):
    def test_legacy_normal_reviews_are_not_miscounted_as_held(self):
        from edge_threat_response.dataset.review_web import review_verdict
        normal = {"label_quality": "good", "bbox_completeness": "yes", "exclude": "no"}
        self.assertEqual("ok", review_verdict(normal, 1))
        self.assertEqual("unclear", review_verdict(normal, 0))
        self.assertEqual("ok", review_verdict({**normal, "negative_knife_absence": "yes"}, 0))
        self.assertEqual("problem", review_verdict({**normal, "bbox_completeness": "no"}, 1))
        self.assertEqual("unclear", review_verdict({"annotation_verdict": "unclear"}, 1))

    def test_seeded_strata_exclude_old_paths_cross_source_hashes_and_error_labels(self):
        folder = Path(__file__).resolve().parents[1] / "tools"
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location("expand_review", folder / "expand_sohas_review.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
        candidates = [{"image_path": f"{i}frame0001.jpg", "image_git_blob": hashlib.sha1(str(i).encode()).hexdigest(),
                       "errors": ["bad"] if i == 9 else [], "objects": [] if i % 2 else [{"raw_name": "knife", "bbox_xyxy_raw": [0, 0, 10, 10]}],
                       "width": 100, "height": 100, "original_split": "test" if i % 3 else "train",
                       "candidate_role": "negative_unverified" if i % 2 else "knife_positive_candidate"} for i in range(10)]
        args = (candidates, {candidates[0]["image_path"]}, {candidates[1]["image_git_blob"]}, 6, 42)
        selected, report = module.select_batch(*args)
        self.assertEqual(selected, module.select_batch(*args)[0])
        self.assertEqual(6, len(selected))
        self.assertFalse({candidates[i]["image_path"] for i in (0, 1, 9)} & {item["image_path"] for item in selected})
        self.assertEqual(2, report["excluded"]["already_prepared"])
        self.assertTrue(any(item["objects"] for item in selected))
        self.assertTrue(any(not item["objects"] for item in selected))
