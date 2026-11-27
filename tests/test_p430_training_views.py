import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import run_p430_session_comparison as comparison
import run_p430_site as site
from edge_threat_response.p430_workflow import read


class TrainingViewTests(unittest.TestCase):
    def test_stale_runner_cannot_start_transformed_training(self):
        with TemporaryDirectory() as temp:
            base = Path(temp) / "site"
            base.mkdir()
            (base / "protection.json").write_text("{}")
            with patch.object(site, "trainer_factory", lambda: None):
                with self.assertRaisesRegex(ValueError, "must audit transformed inputs"):
                    comparison.prepare_run(base, {"draws": []}, {"trainer_node": "pc12"},
                                           "stale-view-fixture", transform="blur")

    def test_training_view_receipt_comes_from_the_loaded_batch(self):
        parameter = SimpleNamespace(requires_grad=True)

        class Backbone:
            def __getitem__(self, key):
                return self

            def parameters(self):
                return [parameter]

        class Detector:
            def __init__(self, checkpoint):
                self.names = {0: "knife"}
                self.model = SimpleNamespace(yaml={"backbone": [None] * 11}, model=Backbone())
                self.callbacks = {}

            def add_callback(self, name, function):
                self.callbacks[name] = function

            def train(self, *, trainer):
                return trainer

        class Trainer:
            def preprocess_batch(self, batch):
                return batch

        modules = {
            "torch": SimpleNamespace(utils=SimpleNamespace(data=SimpleNamespace(Sampler=object))),
            "ultralytics": SimpleNamespace(YOLO=Detector),
            "ultralytics.models.yolo.detect": SimpleNamespace(DetectionTrainer=Trainer),
        }
        with TemporaryDirectory() as temp, patch.dict(sys.modules, modules), patch.multiple(site, DRAWS=8, EPOCHS=1):
            root = Path(temp)
            files = [root / (f"{i}.png" if i < 2 else f"{i}.jpg") for i in range(8)]
            create = site.trainer_factory([files], [], False, root / "state.json", transformed_paths=files[:2])
            model = create(root / "test-only.pt")
            cls = model.train()
            trainer = cls()
            trainer.model = model.model
            trainer.epoch = 0
            trainer.optimizer = SimpleNamespace(param_groups=[{"params": [parameter]}])
            trainer.train_loader = [None]
            model.callbacks["on_train_batch_start"](trainer)

            omitted = [str(path.with_suffix(".jpg")) for path in files]
            with self.assertRaisesRegex(ValueError, "Loaded training batch differs"):
                trainer.preprocess_batch({"im_file": omitted})
            self.assertFalse((root / "training-view-exposure.json").exists())

            trainer.preprocess_batch({"im_file": list(map(str, files))})
            model.callbacks["on_train_epoch_end"](trainer)
            self.assertEqual(
                {"expected_per_epoch": [2], "observed_per_epoch": [2], "observed_first_batch": 2},
                read(root / "training-view-exposure.json"),
            )


if __name__ == "__main__":
    unittest.main()
