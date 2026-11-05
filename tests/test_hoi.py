import json
import random
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.domain import AblationMode, BBox
from edge_threat_response.hoi import geometry_features, load_pairs, pair_metrics
from edge_threat_response.pipeline import ThreatPipeline
from edge_threat_response.replay import load_detection_replay, write_jsonl
from edge_threat_response.replay_cli import main as replay_main
from edge_threat_response.evaluation import evaluate_replays
from edge_threat_response.relations import CachedRelationScores, score_row
from edge_threat_response.spatial import associate_person_knives
from edge_threat_response.training import _sha256_file
from edge_threat_response.training import gpu_training_lock


ROOT = Path(__file__).resolve().parents[1]
DETECTIONS = ROOT/"tests/fixtures/replay/basic.jsonl"
CONFIG = ROOT/"configs/replay/development-v2.example.json"


def synthetic_pairs(root):
    from PIL import Image
    rows = []
    for i in range(8):
        rng = random.Random(i)
        path = root/f"image-{i}.png"
        Image.frombytes("RGB", (48, 48), bytes(rng.randrange(256) for _ in range(48*48*3))).save(path)
        rows.append({"schema_version": 1, "pair_id": f"p{i}", "source_id": "synthetic", "session_id": f"session-{i}",
                     "leakage_group_id": f"group-{i}", "partition": "train" if i < 4 else "tuning",
                     "image_path": path.name, "image_sha256": _sha256_file(path), "frame_index": 0, "timestamp_s": 0.,
                     "person_bbox_xyxy": [2, 2, 30, 46], "knife_bbox_xyxy": [24, 20, 29, 30] if i%2 else [37, 20, 43, 30],
                     "holding_label": "holding" if i%2 else "not_holding", "annotation_origin": "synthetic",
                     "annotation_version": "test-v1", "boxes_source": "ground_truth"})
    path = root/"pairs.jsonl"
    write_jsonl(path, rows)
    return path, rows


class HoiContractTests(unittest.TestCase):
    def test_cuda_training_respects_shared_gpu_claim_before_model_loading(self):
        from edge_threat_response.hoi import train
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            lock = root/"gpu0-training.lock"
            config = root/"config.json"
            config.write_text(json.dumps({"device": "cuda:0", "gpu_lock_file": str(lock)}))
            with gpu_training_lock(lock, owner="other-training"):
                with self.assertRaises(FileExistsError):
                    train(config, root/"pairs.jsonl", root, root/"out")
                self.assertTrue(lock.exists())
                self.assertFalse((root/"out").exists())
            self.assertFalse(lock.exists())
    def test_geometry_is_translation_and_scale_invariant(self):
        a = geometry_features(BBox(0, 0, 10, 20), BBox(9, 5, 12, 8))
        b = geometry_features(BBox(7, 11, 27, 51), BBox(25, 21, 31, 27))
        self.assertEqual(a, b)
        self.assertEqual(8, len(a))

    def test_pair_import_preserves_uncertain_and_rejects_leakage_and_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path, rows = synthetic_pairs(root)
            rows[0]["holding_label"] = "uncertain"
            write_jsonl(path, rows)
            self.assertEqual("uncertain", load_pairs(path, root)[0]["holding_label"])
            rows[4]["leakage_group_id"] = rows[0]["leakage_group_id"]
            write_jsonl(path, rows)
            with self.assertRaisesRegex(ValueError, "crosses"):
                load_pairs(path, root)
            rows[4]["leakage_group_id"] = "group-4"
            rows[0]["image_path"] = "../outside.png"
            write_jsonl(path, rows)
            with self.assertRaisesRegex(ValueError, "relative path"):
                load_pairs(path, root)

    def test_metrics_include_all_negative_undefined_precision(self):
        self.assertEqual({"tp": 0, "fp": 0, "fn": 0, "tn": 2, "precision": None, "recall": None, "f1": None},
                         pair_metrics([0, 0], [.1, .2], .5))
        with self.assertRaisesRegex(ValueError, "finite"):
            pair_metrics([1], [float("nan")], .5)


class B4IntegrationTests(unittest.TestCase):
    def sidecar(self, path, score=.9):
        frames = load_detection_replay(DETECTIONS)
        cfg = load_pipeline_config(CONFIG)
        rows = [{"schema_version": 1, "type": "relation_provenance", "detections_sha256": _sha256_file(DETECTIONS),
                 "classifier_sha256": "1"*64, "image_source_sha256": _sha256_file(DETECTIONS), "pipeline_config_sha256": _sha256_file(CONFIG),
                 "data_kind": "synthetic", "kind": "G"}]
        for f in frames:
            people = tuple(x for x in f.detections if x.label == "person" and x.confidence >= cfg.person_confidence_threshold)
            knives = tuple(x for x in f.detections if x.label == "knife" and x.confidence >= cfg.knife_confidence_threshold)
            pairs = associate_person_knives(people, knives, policy=cfg.spatial_policy,
                                           normalized_distance_threshold=cfg.normalized_distance_threshold,
                                           expanded_person_ratio=cfg.expanded_person_ratio)
            rows.append(score_row(f, pairs, tuple(score if p.person else None for p in pairs)))
        write_jsonl(path, rows)
        return frames

    def test_b4_needs_model_and_low_scores_do_not_fall_back_to_geometry(self):
        cfg = load_pipeline_config(CONFIG)
        with self.assertRaisesRegex(ValueError, "explicit relation"):
            ThreatPipeline(cfg.for_mode(AblationMode.B4))
        frames = load_detection_replay(DETECTIONS)
        baseline = ThreatPipeline(cfg.for_mode(AblationMode.B3))
        b4 = ThreatPipeline(cfg.for_mode(AblationMode.B4), relation=lambda f, pairs: tuple(.01 if p.person else None for p in pairs))
        base_results = [baseline.process(f) for f in frames]
        new_results = [b4.process(f) for f in frames]
        self.assertEqual(2, sum(x.event is not None for x in base_results))
        self.assertEqual(0, sum(x.event is not None for x in new_results))
        self.assertNotIn("holding_scores", base_results[0].evidence.to_dict())
        self.assertIn("holding_scores", new_results[0].evidence.to_dict())

    def test_sidecar_binding_and_b0_b4_event_evaluation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root/"relations.jsonl"
            frames = self.sidecar(path)
            with self.assertRaisesRegex(ValueError, "different detector"):
                CachedRelationScores(path, frames, "0"*64)
            out = root/"replay"
            modes = ["B0", "B1", "B2", "B3", "B4"]
            with redirect_stdout(StringIO()):
                replay_main(["--input", str(DETECTIONS), "--config", str(CONFIG), "--output-dir", str(out),
                             "--modes", ",".join(modes), "--relations", str(path)])
            binding = root/"binding.json"
            binding.write_text(json.dumps({"schema_version": 1, "modes": modes, "recordings": [{
                "recording_id": "fixture-recording", "detections": str(DETECTIONS), "pipeline_config": str(CONFIG),
                "replay_dir": str(out), "relations": str(path), "relation_threshold": .5, "media": str(DETECTIONS)}]}))
            result = evaluate_replays(ROOT/"tests/fixtures/evaluation/ground-truth.json", binding,
                                      ROOT/"configs/evaluation/synthetic.example.json")
            self.assertEqual(modes, [x["mode"] for x in result["comparison"]])
            b4 = result["comparison"][-1]
            self.assertEqual((2, 0, 0), (b4["tp"], b4["fp"], b4["fn"]))
            rows = [json.loads(x) for x in path.read_text().splitlines()]
            rows[1]["frame_sha256"] = "0"*64
            write_jsonl(path, rows)
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                evaluate_replays(ROOT/"tests/fixtures/evaluation/ground-truth.json", binding,
                                  ROOT/"configs/evaluation/synthetic.example.json")

    def test_invalid_scores_fail_instead_of_confirming(self):
        cfg = load_pipeline_config(CONFIG).for_mode(AblationMode.B4)
        pipeline = ThreatPipeline(cfg, relation=lambda f, pairs: tuple(float("nan") for _ in pairs))
        with self.assertRaisesRegex(ValueError, "Holding score"):
            pipeline.process(next(f for f in load_detection_replay(DETECTIONS) if any(x.label == "person" for x in f.detections)))


if __name__ == "__main__":
    unittest.main()
