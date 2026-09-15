import unittest
from dataclasses import replace
from pathlib import Path

from edge_threat_response.config import load_pipeline_config
from edge_threat_response.domain import SpatialPolicy


ROOT = Path(__file__).resolve().parents[1]


class PipelineConfigTests(unittest.TestCase):
    def test_loads_development_example(self):
        config = load_pipeline_config(
            ROOT / "configs/replay/development.example.json"
        )

        self.assertEqual(2, config.temporal_k)
        self.assertEqual(3, config.temporal_n)
        self.assertEqual(
            SpatialPolicy.DISTANCE_AND_EXPANDED_BBOX, config.spatial_policy
        )

    def test_loads_v2_expanded_bbox_policy_without_distance_threshold(self):
        config = load_pipeline_config(
            ROOT / "configs/replay/development-v2.example.json"
        )

        self.assertEqual(2, config.schema_version)
        self.assertEqual(SpatialPolicy.EXPANDED_BBOX_ONLY, config.spatial_policy)
        self.assertIsNone(config.normalized_distance_threshold)

    def test_rejects_invalid_k_of_n(self):
        config = load_pipeline_config(
            ROOT / "configs/replay/development.example.json"
        )

        with self.assertRaisesRegex(ValueError, "temporal_k"):
            replace(config, temporal_k=4, temporal_n=3)


if __name__ == "__main__":
    unittest.main()
