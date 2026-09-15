import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.training import TrainingConfig, build_train_arguments


class TrainingConfigTests(unittest.TestCase):
    def test_builds_controlled_arguments_and_batch_override(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            data_yaml = root / "data.yaml"
            data_yaml.write_text("names:\n  0: knife\n", encoding="utf-8")
            config_path = root / "training.json"
            config_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profile_id": "smoke",
                        "model": "model.pt",
                        "task": "detect",
                        "run_name": "run",
                        "arguments": {"epochs": 1, "batch": 4},
                    }
                ),
                encoding="utf-8",
            )

            config = TrainingConfig.load(config_path)
            arguments = build_train_arguments(
                config,
                data_yaml=data_yaml,
                output_dir=root / "runs",
                batch_override=2,
                run_name_override="retry-batch2",
            )

            self.assertEqual(2, arguments["batch"])
            self.assertEqual(1, arguments["epochs"])
            self.assertEqual("retry-batch2", arguments["name"])
            self.assertFalse(arguments["exist_ok"])

    def test_rejects_runner_controlled_arguments(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "training.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profile_id": "bad",
                        "model": "model.pt",
                        "task": "detect",
                        "run_name": "run",
                        "arguments": {"data": "other.yaml"},
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "controlled"):
                TrainingConfig.load(path)


if __name__ == "__main__":
    unittest.main()
