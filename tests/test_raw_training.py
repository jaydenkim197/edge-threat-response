import json
import tempfile
import unittest
from pathlib import Path

from edge_threat_response.raw_training import prepare_suite, run_queue
from edge_threat_response.training import TrainingConfig, validate_training_approval, _sha256_file
from edge_threat_response.training import _raw_loader_contract
from edge_threat_response.dataset.raw_import import voc_knife, materialize_inventory
from edge_threat_response.dataset.image_screening import image_signature
from edge_threat_response.dataset.materialize import _convert_knife_label


ROOT = Path(__file__).resolve().parents[1]


class RawTrainingTests(unittest.TestCase):
    def test_actual_loader_cannot_drop_rows_or_change_batch(self):
        from types import SimpleNamespace
        class Loader:
            dataset = list(range(6))
            def __len__(self): return 3
        trainer = SimpleNamespace(train_loader=Loader(), test_loader=SimpleNamespace(dataset=[1]), batch_size=2, accumulate=1)
        self.assertEqual(6, _raw_loader_contract(trainer, 6, 2, 1)["train_dataset_length"])
        trainer.batch_size = 1
        with self.assertRaisesRegex(ValueError, "matched budget"):
            _raw_loader_contract(trainer, 6, 2, 1)
    def prepare(self, root):
        (root/"images").mkdir()
        (root/"labels").mkdir()
        rows = []
        for i, (source, split, positive) in enumerate([
            ("sohas", "train", True), ("sohas", "train", False),
            ("dangerous", "train", True), ("catargiu", "train", True),
            ("catargiu", "train", True), ("sohas", "val", True), ("dangerous", "test", True)]):
            image, label = root/"images"/f"{i}.jpg", root/"labels"/f"{i}.txt"
            image.write_bytes(f"unique-test-image-{i}".encode())
            label.write_text("0 .5 .5 .2 .2\n" if positive else "", encoding="utf-8")
            rows.append({"image_id": str(i), "source_dataset": source, "split": split, "source_group": str(i),
                         "image": image.resolve().as_posix(), "label": label.resolve().as_posix(),
                         "image_sha256": _sha256_file(image), "label_sha256": _sha256_file(label), "knife_count": int(positive)})
        inventory = root/"inventory.jsonl"
        inventory.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
        plan = json.loads((ROOT/"configs/training/raw-real.pc13.json").read_text(encoding="utf-8-sig"))
        plan["arguments"].update(batch=2, nbs=2, epochs=1)
        path = root/"plan.json"
        path.write_text(json.dumps(plan))
        checkpoints = {s: root/f"{s}.pt" for s in ("n", "s")}
        for s, p in checkpoints.items(): p.write_bytes(s.encode())
        output = root/"suite"
        return prepare_suite(path, inventory, checkpoints, output, "user authorized raw source experiments 2026-11-05"), output

    def test_matched_budget_common_holdouts_and_honest_scope(self):
        with tempfile.TemporaryDirectory() as d:
            suite, output = self.prepare(Path(d))
            self.assertEqual(6, suite["draws_per_epoch"])
            self.assertFalse(suite["human_review_complete"])
            for item in suite["queue"]:
                config = TrainingConfig.load(Path(item["config"]))
                auth = validate_training_approval(Path(item["config"]), config, Path(item["data"]), Path(item["manifest"]), output/"raw-authorization.json")
                self.assertEqual(6, auth["train_draw_count"])
                self.assertFalse(auth["final_evaluation_allowed"])
            self.assertEqual([2, 1, 5, 5], [q["unique_train"] for q in suite["queue"]])

    def test_cannot_fabricate_review_or_change_bound_labels(self):
        with tempfile.TemporaryDirectory() as d:
            suite, output = self.prepare(Path(d))
            entry = suite["queue"][0]
            config = TrainingConfig.load(Path(entry["config"]))
            path = output/"raw-authorization.json"
            auth = json.loads(path.read_text())
            auth["human_review_complete"] = True
            path.write_text(json.dumps(auth))
            with self.assertRaisesRegex(ValueError, "scope"):
                validate_training_approval(Path(entry["config"]), config, Path(entry["data"]), Path(entry["manifest"]), path)
            auth["human_review_complete"] = False
            path.write_text(json.dumps(auth))
            (Path(d)/"labels/0.txt").write_text("")
            with self.assertRaisesRegex(ValueError, "bytes changed"):
                validate_training_approval(Path(entry["config"]), config, Path(entry["data"]), Path(entry["manifest"]), path)

    def test_queue_is_sequential_and_stops_after_failure(self):
        with tempfile.TemporaryDirectory() as d:
            suite, output = self.prepare(Path(d))
            calls = []
            def fail_second(config, **kwargs):
                calls.append(config.name)
                if len(calls) == 2: raise RuntimeError("injected failure")
                return {"status": "passed"}
            runs = Path(d)/"runs"
            with self.assertRaisesRegex(RuntimeError, "injected"):
                run_queue(output/"queue.json", runs, runner=fail_second)
            state = json.loads(next(runs.glob("*-queue-state.json")).read_text())
            self.assertEqual(["RAW-R1-n"], state["completed"])
            self.assertEqual("failed", state["status"])
            self.assertEqual(2, len(calls))
            self.assertFalse((runs/"gpu0-training.lock").exists())
            with self.assertRaisesRegex(ValueError, "already exists"):
                run_queue(output/"queue.json", runs, runner=fail_second)

    def test_source_class_semantics_and_pixel_bounds(self):
        xml = b'<annotation><size><width>100</width><height>80</height></size><object><name>Knife</name><bndbox><xmin>10</xmin><ymin>10</ymin><xmax>30</xmax><ymax>50</ymax></bndbox></object></annotation>'
        text = voc_knife(xml, width=100, height=80, allowed_names={"knife"})
        self.assertEqual("0", text.split()[0])
        self.assertAlmostEqual(.2, float(text.split()[1]))
        with self.assertRaisesRegex(ValueError, "Unknown source class"):
            voc_knife(xml, width=100, height=80, allowed_names={"gun"})
        with self.assertRaisesRegex(ValueError, "dimensions"):
            voc_knife(xml, width=101, height=80, allowed_names={"knife"})

    def test_multiclass_import_filters_only_explicitly_mapped_other_classes(self):
        with tempfile.TemporaryDirectory() as d:
            label = Path(d)/"mixed.txt"
            label.write_text("1 .5 .5 .2 .2\n0 .4 .4 .1 .1\n")
            with self.assertRaisesRegex(ValueError, "non-knife"):
                _convert_knife_label(label, class_map={0: 1, 1: 0}, canonical_knife_id=1)
            text, count, _ = _convert_knife_label(label, class_map={0: 1, 1: 0}, canonical_knife_id=1, skip_non_knife=True)
            self.assertEqual(1, count)
            self.assertTrue(text.startswith("0 "))
            with self.assertRaisesRegex(ValueError, "non-knife"):
                _convert_knife_label(label, class_map={0: 1}, canonical_knife_id=1, skip_non_knife=True)

    def test_global_protected_images_excluded_and_groups_do_not_cross(self):
        from PIL import Image
        import random
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            rows = []
            for i in range(12):
                name = chr(97+i) * 3
                image = root/(name+".png")
                rng = random.Random(i)
                Image.frombytes("RGB", (16, 16), bytes(rng.randrange(256) for _ in range(768))).save(image)
                rows.append({**image_signature(image), "record_id": name+".png", "dataset_id": "sohas",
                             "image_file": str(image), "original_split": "raw", "source_url": "test-source",
                             "license": "test-only", "label_text": "0 .5 .5 .2 .2\n", "annotation_provenance": {},
                             "coordinate_contract": "test-only"})
            protected = [{**rows[0], "record_id": "protected/image.png", "dataset_id": "protected"}]
            summary = materialize_inventory(rows, protected, root/"out")
            self.assertEqual(1, summary["exclusions"]["protected_proxy_group"])
            saved = [json.loads(s) for s in (root/"out/inventory.jsonl").read_text().splitlines()]
            self.assertNotIn(rows[0]["image_sha256"], {x["image_sha256"] for x in saved})
            self.assertEqual({"train", "val", "test"}, {x["split"] for x in saved})
            self.assertEqual(11, len(saved))


if __name__ == "__main__":
    unittest.main()
