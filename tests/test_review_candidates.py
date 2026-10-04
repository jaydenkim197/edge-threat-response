import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout, redirect_stderr
from pathlib import Path

from edge_threat_response.dataset.review_candidates import collect_candidates, main, readonly_database
from edge_threat_response.dataset.review_web import ReviewStore


ROOT = Path(__file__).resolve().parents[1]


class ReviewCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.policy = ROOT / "configs/datasets/review-candidate-policy.json"
        self.initial = self.pack("sohas", [True, False, True, True])
        self.extra = self.pack("extra", [False, True])
        self.simple(self.initial, 0)
        self.simple(self.initial, 1)
        self.simple(self.initial, 2, "problem")
        self.simple(self.extra, 0, "unclear")
        self.extra.save(1, 0, {"domain": "non_target", "label_quality": "good", "exclude": "no",
                               "bbox_completeness": "yes", "reviewer": "fixture-person", "notes": ""})
        self.others = {}
        for source in ("simuletic", "us-mock", "dangerous-items", "open-images"):
            store = self.pack(source, [True])
            self.simple(store, 0)
            self.others[source] = store
        self.team = self.root / "team.sqlite3"
        self.config = self.root / "config.json"
        config = {"database": str(self.team), "secret_file": "DO-NOT-EXPORT-SECRET",
                  "datasets": [{"id": "sohas", "review_dir": str(self.initial.root),
                                "review_batches": [{"id": "b01", "review_dir": str(self.extra.root)}]},
                               *[{"id": key, "review_dir": str(store.root)} for key, store in self.others.items()],
                               {"id": "acf", "reason": "blocked"}]}
        self.config.write_text(json.dumps(config), encoding="utf-8")
        with closing(sqlite3.connect(self.team)) as connection, connection:
            connection.execute("CREATE TABLE users(id TEXT PRIMARY KEY,name TEXT,code_hash TEXT,admin INT,active INT)")
            connection.execute("INSERT INTO users VALUES ('fake','fixture-person','secret-hash',0,1)")
            connection.execute("CREATE TABLE assignments(pack TEXT,sample INT,user TEXT)")
            connection.execute("INSERT INTO assignments VALUES ('sohas',3,'fake')")
            connection.execute("CREATE TABLE review_batches(pack TEXT,batch TEXT,offset INT,count INT,pack_hash TEXT)")
            connection.executemany("INSERT INTO review_batches VALUES (?,?,?,?,?)", [
                ("sohas", "initial", 0, 4, self.initial.pack_hash), ("sohas", "b01", 4, 2, self.extra.pack_hash),
                *[(key, "initial", 0, 1, store.pack_hash) for key, store in self.others.items()]])

    def tearDown(self):
        self.temp.cleanup()

    def pack(self, name, positives):
        root = self.root / name
        root.mkdir()
        evidence, rows = [], []
        for index, positive in enumerate(positives):
            image = root / f"{index}.jpg"
            raw = f"image {name}/{index}".encode()
            image.write_bytes(raw)
            path = f"{name}/{index}.jpg"
            evidence.append({"sample_no": index + 1, "image_path": path, "image_file": image.name,
                             "width": 100, "height": 100, "knife_count": int(positive),
                             "knife_boxes_xyxy_raw": [[40, 40, 60, 60]] if positive else [],
                             "image_sha256": hashlib.sha256(raw).hexdigest(), "source_group": f"proxy-{index}"})
            rows.append({"image_path": path, "original_split": "train"})
        with (root / "review.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["image_path", "original_split"])
            writer.writeheader()
            writer.writerows(rows)
        (root / "image-evidence.jsonl").write_text("\n".join(json.dumps(row) for row in evidence), encoding="utf-8")
        return ReviewStore(root)

    def simple(self, store, sample, verdict="ok"):
        return store.save(sample, 0, {"review_schema": "simple-v2", "domain": "target_cctv",
                                    "annotation_verdict": verdict, "reviewer": "fixture-person",
                                    "notes": "fixture-problem-note" if verdict == "problem" else ""})

    def files(self):
        return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in self.root.rglob("*") if path.is_file()}

    def test_readonly_snapshots_join_batches_preserve_inputs_and_block_approval(self):
        before = self.files()
        result = collect_candidates(self.config, self.policy)
        self.assertEqual(before, self.files())
        self.assertEqual((10, 9, 0), (result["prepared"], result["reviewed"], result["training_approved"]))
        rows = {row["record_id"]: row for row in result["records"]}
        self.assertEqual("candidate_negative", rows["sohas/initial/1"]["candidate_status"])
        self.assertEqual("candidate_positive", rows["sohas/b01/1"]["candidate_status"])
        self.assertEqual(5, rows["sohas/b01/1"]["global_sample_id"])
        self.assertEqual("non_target", rows["sohas/b01/1"]["domain"])
        self.assertEqual("hold_mapping", rows["dangerous-items/initial/0"]["candidate_status"])
        self.assertEqual("synthetic_candidate", rows["simuletic/initial/0"]["candidate_status"])
        self.assertEqual("evaluation_candidate", rows["us-mock/initial/0"]["candidate_status"])
        self.assertTrue(all(not row["training_approved"] and row["approval_blockers"] for row in rows.values()))
        self.assertTrue(all(pack["database_writes"] == 0 for pack in result["packs"]))
        self.assertAlmostEqual(0.04, rows["sohas/initial/0"]["diagnostic_normalized_bbox_areas"][0])
        with readonly_database(self.initial.database) as connection:
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute("UPDATE reviews SET version=999")
        policy = json.loads(self.policy.read_text(encoding="utf-8"))
        policy["sources"]["open-images"]["training_original_splits"] = ["validation"]
        path = self.root / "partition-policy.json"
        path.write_text(json.dumps(policy), encoding="utf-8")
        changed = collect_candidates(self.config, path)
        row = next(row for row in changed["records"] if row["dataset_id"] == "open-images")
        self.assertEqual("hold_source_split", row["candidate_status"])

    def test_cli_writes_unapproved_lists_without_names_or_secret_and_rejects_overwrite(self):
        output = self.root / "output"
        args = ["--config", str(self.config), "--policy", str(self.policy), "--output-dir", str(output)]
        # Server config must not share the output tree: use sibling paths, not its directory.
        config_dir = self.root / "server"
        config_dir.mkdir()
        config_copy = config_dir / "config.json"
        config_copy.write_bytes(self.config.read_bytes())
        args[1] = str(config_copy)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(args))
        candidates = [json.loads(line) for line in (output / "training-candidates.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(4, len(candidates))
        self.assertTrue(all(row["source_role"] not in {"external_evaluation", "synthetic_ablation"} for row in candidates))
        for file in output.iterdir():
            content = file.read_text(encoding="utf-8")
            self.assertNotIn("fixture-person", content)
            self.assertNotIn("DO-NOT-EXPORT-SECRET", content)
            self.assertNotIn("fixture-problem-note", content)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, main(args))
            bad = [*args[:-1], str(self.initial.root / "unsafe-output")]
            self.assertEqual(2, main(bad))
        self.assertFalse((self.initial.root / "unsafe-output").exists())

    def test_missing_db_is_not_created_and_wrong_pack_hash_fails(self):
        db = self.extra.database
        db.unlink()
        with self.assertRaises(sqlite3.OperationalError):
            collect_candidates(self.config, self.policy)
        self.assertFalse(db.exists())
        self.extra = ReviewStore(self.extra.root)
        with closing(sqlite3.connect(db)) as connection, connection:
            connection.execute("UPDATE metadata SET value='wrong' WHERE key='pack_hash'")
        with self.assertRaisesRegex(ValueError, "another pack"):
            collect_candidates(self.config, self.policy)

    def mutate_image(self, store, raw):
        path = store.root / "image-evidence.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        store.images[0].write_bytes(raw)
        rows[0]["image_sha256"] = hashlib.sha256(raw).hexdigest()
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        digest = hashlib.sha256((store.root / "review.csv").read_bytes() + path.read_bytes()).hexdigest()
        with closing(sqlite3.connect(store.database)) as connection, connection:
            connection.execute("UPDATE metadata SET value=? WHERE key='pack_hash'", (digest,))
        with closing(sqlite3.connect(self.team)) as connection, connection:
            connection.execute("UPDATE review_batches SET pack_hash=? WHERE pack=?", (digest, store.root.name))

    def test_external_exact_duplicate_blocks_training_and_reports_lineage(self):
        self.mutate_image(self.others["us-mock"], self.initial.images[0].read_bytes())
        result = collect_candidates(self.config, self.policy)
        self.assertEqual(1, len(result["duplicates"]))
        rows = [row for row in result["records"] if row["record_id"] in result["duplicates"][0]["record_ids"]]
        self.assertEqual(2, len(rows))
        self.assertTrue(all(row["candidate_status"] == "hold_duplicate" for row in rows))
        self.assertTrue(all("external_evaluation_overlap" in row["hold_reasons"] for row in rows))

    def test_changed_image_and_registry_reordering_fail_before_output(self):
        self.initial.images[0].write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "image"):
            collect_candidates(self.config, self.policy)
        self.initial.images[0].write_bytes(b"image sohas/0")
        with closing(sqlite3.connect(self.team)) as connection, connection:
            connection.execute("UPDATE review_batches SET offset=99 WHERE batch='b01'")
        with self.assertRaisesRegex(ValueError, "registry"):
            collect_candidates(self.config, self.policy)

    def test_conflicting_negative_payload_is_held_not_selected(self):
        with closing(sqlite3.connect(self.initial.database)) as connection, connection:
            payload = json.loads(connection.execute("SELECT payload FROM reviews WHERE sample=1").fetchone()[0])
            payload["negative_knife_absence"] = "unclear"
            connection.execute("UPDATE reviews SET payload=? WHERE sample=1", (json.dumps(payload),))
        result = collect_candidates(self.config, self.policy)
        row = next(row for row in result["records"] if row["record_id"] == "sohas/initial/1")
        self.assertEqual("hold_review", row["candidate_status"])


if __name__ == "__main__":
    unittest.main()
