import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.training import (
    TrainingConfig,
    build_train_arguments,
    run_training,
    training_preflight,
)


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

    def test_preflight_records_cuda_and_dataset_identity(self):
        class FakeCuda:
            @staticmethod
            def is_available():
                return True

            @staticmethod
            def device_count():
                return 1

            @staticmethod
            def get_device_name(index):
                return "Fixture GPU"

        class FakeTorch:
            cuda = FakeCuda()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            data = root / "data.yaml"
            data.write_text("names:\n  0: knife\n", encoding="utf-8")
            dataset_manifest = root / "manifest.jsonl"
            dataset_manifest.write_text('{"image_id":"fixture"}\n', encoding="utf-8")
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profile_id": "cuda",
                        "model": "model.pt",
                        "task": "detect",
                        "run_name": "run",
                        "arguments": {},
                    }
                ),
                encoding="utf-8",
            )

            result = training_preflight(
                config,
                data_yaml=data,
                dataset_manifest=dataset_manifest,
                require_cuda=True,
                torch_module=FakeTorch(),
            )

            self.assertEqual("passed", result["status"])
            self.assertEqual(["Fixture GPU"], result["cuda"]["devices"])
            self.assertTrue(result["dataset_manifest"]["sha256"])

    def test_training_manifest_records_dataset_and_artifact_hashes(self):
        class Result:
            results_dict = {"metrics/mAP50(B)": 0.5}

            def __init__(self, save_dir):
                self.save_dir = save_dir

        class Model:
            def __init__(self, save_dir):
                self.save_dir = save_dir

            def train(self, **arguments):
                self.save_dir.mkdir(parents=True)
                (self.save_dir / "best.pt").write_bytes(b"weights")
                return Result(self.save_dir)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            data = root / "data.yaml"
            data.write_text("names:\n  0: knife\n", encoding="utf-8")
            dataset_manifest = root / "manifest.jsonl"
            dataset_manifest.write_text('{"image_id":"fixture"}\n', encoding="utf-8")
            config = root / "config.json"
            config.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "profile_id": "fixture",
                        "model": "model.pt",
                        "task": "detect",
                        "run_name": "fixture-run",
                        "arguments": {},
                    }
                ),
                encoding="utf-8",
            )
            run_dir = root / "runs" / "fixture-run"

            evidence = run_training(
                config,
                data_yaml=data,
                output_dir=root / "runs",
                dataset_manifest=dataset_manifest,
                model_factory=lambda _: Model(run_dir),
            )

            self.assertEqual("passed", evidence["status"])
            self.assertTrue(evidence["dataset_manifest"]["sha256"])
            self.assertEqual("best.pt", Path(evidence["artifacts"][0]["path"]).name)
            self.assertTrue(evidence["artifacts"][0]["sha256"])


if __name__ == "__main__":
    unittest.main()
