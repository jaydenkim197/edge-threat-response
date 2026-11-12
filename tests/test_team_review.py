import hashlib
import importlib.util
import json
import re
import sqlite3
import struct
import tempfile
import time
import threading
import unittest
from unittest.mock import patch
from contextlib import closing
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec("flask"), "Optional review-server dependencies not installed")
class TeamReviewTests(unittest.TestCase):
    def setUp(self):
        from edge_threat_response.dataset.team_review import create_app
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        pack = self.root / "pack"
        pack.mkdir()
        (pack / "image.jpg").write_bytes(b"image fixture")
        (pack / "review.csv").write_text("image_path,original_split\none.jpg,train\ntwo.jpg,test\n")
        rows = [{"sample_no": i+1, "image_path": name, "image_file": "image.jpg", "width": 100, "height": 100,
                 "image_sha256": hashlib.sha256(b"image fixture").hexdigest(), "knife_count": 0,
                 "knife_boxes_xyxy_raw": []} for i, name in enumerate(["one.jpg", "two.jpg"])]
        (pack / "image-evidence.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
        secret = self.root / "secret"
        secret.write_text("a" * 64)
        config = self.root / "config.json"
        self.config = config
        config.write_text(json.dumps({"public_url": "https://review.example.test", "secret_file": str(secret),
                                     "database": str(self.root / "team.sqlite3"), "datasets": [
                                         {"id": "fixture", "name": "Fixture", "review_dir": str(pack)},
                                         {"id": "blocked", "name": "Blocked", "reason": "rights pending"}]}))
        self.app = create_app(config)
        self.app.testing = True
        self.team = self.app.extensions["review_team"]
        self.admin = self.team.create_user("fixture-admin", admin=True)
        self.a = self.team.create_user("fixture-a")
        self.b = self.team.create_user("fixture-b")
        self.url = "https://review.example.test"

    def tearDown(self):
        self.temp.cleanup()

    def login(self, user):
        client = self.app.test_client()
        page = client.get("/login", base_url=self.url)
        token = re.search(r'name="csrf" value="([^"]+)"', page.get_data(as_text=True))[1]
        response = client.post("/login", base_url=self.url, headers={"Origin": self.url}, data={"code": user["code"], "csrf": token})
        self.assertEqual(302, response.status_code)
        self.assertIn("Secure", response.headers["Set-Cookie"])
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", response.headers["Set-Cookie"])
        token = client.get("/api/catalog", base_url=self.url).json["csrf"]
        return client, {"Origin": self.url, "X-Review-Token": token}

    def post(self, client, headers, path, body):
        return client.post(path, base_url=self.url, headers=headers, json=body)

    def age_assignment(self, sample, seconds=901):
        with self.team.connect() as connection:
            connection.execute("UPDATE assignment_activity SET last_seen=? WHERE pack='fixture' AND sample=?", (time.time()-seconds, sample))

    def test_expired_pending_reassigned_and_previous_owner_cannot_write(self):
        ca, ha = self.login(self.a)
        cb, hb = self.login(self.b)
        sample = self.post(ca, ha, "/api/claim?dataset=fixture", {}).json["id"]
        self.age_assignment(sample)
        self.assertEqual(sample, self.post(cb, hb, "/api/claim?dataset=fixture", {}).json["id"])
        payload = {"id": sample, "version": 0, "fields": {"domain": "target_cctv", "annotation_verdict": "ok"}}
        self.assertEqual(403, self.post(ca, ha, "/api/review?dataset=fixture", payload).status_code)
        self.assertEqual(409, self.post(ca, ha, "/api/heartbeat?dataset=fixture", {"id": sample}).status_code)
        self.assertEqual(200, self.post(cb, hb, "/api/review?dataset=fixture", payload).status_code)
        item = cb.get("/api/items?dataset=fixture", base_url=self.url).json["items"][sample]
        self.assertEqual(self.b["name"], item["review"]["reviewer"])
        self.assertEqual(1, item["version"])

    def test_expired_owner_save_fails_even_before_another_claim(self):
        client, headers = self.login(self.a)
        sample = self.post(client, headers, "/api/claim?dataset=fixture", {}).json["id"]
        self.age_assignment(sample)
        response = self.post(client, headers, "/api/review?dataset=fixture", {
            "id": sample, "version": 0, "fields": {"domain": "non_target", "annotation_verdict": "ok"}})
        self.assertEqual(409, response.status_code)
        self.assertTrue(response.json["assignment_lost"])
        self.assertEqual(0, client.get("/api/items?dataset=fixture", base_url=self.url).json["items"][sample]["version"])

    def test_activity_renews_pending_but_polling_does_not(self):
        client, headers = self.login(self.a)
        other, other_headers = self.login(self.b)
        sample = self.post(client, headers, "/api/claim?dataset=fixture", {}).json["id"]
        self.age_assignment(sample, 850)
        with self.team.connect() as connection:
            old = connection.execute("SELECT last_seen FROM assignment_activity WHERE pack='fixture' AND sample=?", (sample,)).fetchone()[0]
        client.get("/api/items?dataset=fixture", base_url=self.url)
        client.get("/api/catalog", base_url=self.url)
        self.assertEqual(409, self.post(other, other_headers, "/api/heartbeat?dataset=fixture", {"id": sample}).status_code)
        with self.team.connect() as connection:
            self.assertEqual(old, connection.execute("SELECT last_seen FROM assignment_activity WHERE pack='fixture' AND sample=?", (sample,)).fetchone()[0])
        self.assertEqual(200, self.post(client, headers, "/api/heartbeat?dataset=fixture", {"id": sample}).status_code)
        with self.team.connect() as connection:
            self.assertGreater(connection.execute("SELECT last_seen FROM assignment_activity WHERE pack='fixture' AND sample=?", (sample,)).fetchone()[0], old+800)
        self.assertEqual(403, self.post(client, {**headers, "Origin": "https://attacker.test"}, "/api/heartbeat?dataset=fixture", {"id": sample}).status_code)

    def test_reaper_preserves_completed_reviews_history_and_edit_ownership(self):
        from edge_threat_response.dataset.team_review import reclaim_expired_assignments
        client, headers = self.login(self.a)
        done = self.post(client, headers, "/api/claim?dataset=fixture", {}).json["id"]
        payload = {"id": done, "version": 0, "fields": {"domain": "target_cctv", "annotation_verdict": "ok"}}
        self.assertEqual(200, self.post(client, headers, "/api/review?dataset=fixture", payload).status_code)
        pending = self.post(client, headers, "/api/claim?dataset=fixture", {}).json["id"]
        self.age_assignment(done); self.age_assignment(pending)
        self.assertEqual(1, reclaim_expired_assignments(self.app))
        items = client.get("/api/items?dataset=fixture", base_url=self.url).json["items"]
        self.assertTrue(items[done]["editable"])
        self.assertFalse(items[pending]["editable"])
        self.assertEqual(1, items[done]["version"])
        payload["version"] = 1
        self.assertEqual(200, self.post(client, headers, "/api/review?dataset=fixture", payload).status_code)
        store = self.app.extensions["review_stores"]["fixture"]
        with store.connect() as connection:
            self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM history").fetchone()[0])

    def test_legacy_owners_get_additive_activity_migration_and_grace_period(self):
        from edge_threat_response.dataset.team_review import TeamDatabase
        client, headers = self.login(self.a)
        sample = self.post(client, headers, "/api/claim?dataset=fixture", {}).json["id"]
        with self.team.connect() as connection:
            old = list(connection.execute("SELECT * FROM assignments"))
            connection.execute("DROP TABLE assignment_activity")
        migrated = TeamDatabase(self.team.path)
        with migrated.connect() as connection:
            self.assertEqual([tuple(x) for x in old], [tuple(x) for x in connection.execute("SELECT * FROM assignments")])
            self.assertEqual(3, len(connection.execute("PRAGMA table_info(assignments)").fetchall()))
            self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM assignment_activity").fetchone()[0])
        self.assertEqual(sample, self.post(client, headers, "/api/claim?dataset=fixture", {}).json["id"])

    def test_catalog_reclaims_stale_lock_and_claim_reports_active_work(self):
        client, headers = self.login(self.a)
        other, other_headers = self.login(self.b)
        first = self.post(client, headers, "/api/claim?dataset=fixture", {}).json["id"]
        second = self.post(other, other_headers, "/api/claim?dataset=fixture", {}).json["id"]
        extra = self.team.create_user("fixture-third")
        third, third_headers = self.login(extra)
        unavailable = self.post(third, third_headers, "/api/claim?dataset=fixture", {}).json
        self.assertIsNone(unavailable["id"]); self.assertEqual(2, unavailable["pending_assigned"])
        self.age_assignment(first)
        third.get("/api/catalog", base_url=self.url)
        self.assertEqual(first, self.post(third, third_headers, "/api/claim?dataset=fixture", {}).json["id"])
        self.assertNotEqual(first, second)

    def test_claim_waits_for_inflight_save_before_reading_review_state(self):
        ca, ha = self.login(self.a)
        cb, hb = self.login(self.b)
        first = self.post(ca, ha, "/api/claim?dataset=fixture", {}).json["id"]
        store = self.app.extensions["review_stores"]["fixture"]
        original = store.save
        saving, finish, claiming, claimed = (threading.Event() for _ in range(4))
        results = {}
        def slow_save(*args):
            saving.set()
            if not finish.wait(5): raise RuntimeError("Test save gate timed out")
            return original(*args)
        def save():
            results["save"] = self.post(ca, ha, "/api/review?dataset=fixture", {"id": first,"version":0,"fields":{"domain":"non_target","annotation_verdict":"ok"}})
        def claim():
            claiming.set()
            results["claim"] = self.post(cb, hb, "/api/claim?dataset=fixture", {})
            claimed.set()
        with patch.object(store, "save", side_effect=slow_save):
            a = threading.Thread(target=save); b = threading.Thread(target=claim)
            a.start(); self.assertTrue(saving.wait(5)); b.start(); self.assertTrue(claiming.wait(5))
            try: self.assertFalse(claimed.wait(.15))
            finally: finish.set(); a.join(5); b.join(5)
        self.assertEqual(200, results["save"].status_code)
        self.assertNotEqual(first, results["claim"].json["id"])

    def test_code_only_video_pack_saves_new_and_corrected_boxes(self):
        from edge_threat_response.dataset.team_review import create_app

        video = self.root / "video"
        video.mkdir()
        (video / "review.csv").write_text("image_path,original_split\npositive.jpg,unknown\nmissed.jpg,unknown\n")
        evidence = []
        for index, name in enumerate(("positive.jpg", "missed.jpg"), 1):
            image = name.encode()
            (video / name).write_bytes(image)
            evidence.append({"sample_no": index, "image_path": name, "image_file": name,
                             "width": 100, "height": 60, "image_sha256": hashlib.sha256(image).hexdigest(),
                             "knife_count": int(index == 1),
                             "knife_boxes_xyxy_raw": [[1, 2, 10, 20]] if index == 1 else []})
        original = "\n".join(json.dumps(row) for row in evidence)
        (video / "image-evidence.jsonl").write_text(original)

        config = json.loads(self.config.read_text())
        config["datasets"].append({"id": "video", "name": "Video", "review_dir": str(video),
                                   "review_schema": "video-box-v1"})
        for mode in ("name", None):
            if mode is None:
                del config["reviewer_login"]
            else:
                config["reviewer_login"] = mode
            self.config.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "explicit reviewer code"):
                create_app(self.config)
        self.assertFalse((video / "human-review.sqlite3").exists())
        config["reviewer_login"] = "code"
        self.config.write_text(json.dumps(config))
        self.app = create_app(self.config)
        self.app.testing = True
        endpoint = "/api/items?dataset=video"
        self.assertEqual(401, self.app.test_client().get(endpoint, base_url=self.url).status_code)
        self.assertEqual(401, self.app.test_client().get("/api/packs/video/images/0", base_url=self.url).status_code)

        client, headers = self.login(self.a)
        self.assertEqual("simple-v2", client.get("/api/items?dataset=fixture", base_url=self.url).json["review_schema"])
        self.assertEqual("video-box-v1", client.get(endpoint, base_url=self.url).json["review_schema"])
        save_path = "/api/review?dataset=video"
        fields = {"domain": "target_cctv", "knife_presence": "yes", "reviewed_boxes": [[1, 2.5, 15, 22]],
                  "reviewer": "spoof", "review_schema": "simple-v2"}
        claim = "/api/claim?dataset=video"
        self.assertEqual(0, self.post(client, headers, claim, {}).json["id"])
        for boxes in ([], [[1, 0, 101, 22]], [[True, 0, 15, 22]], [[5, 0, 5, 22]]):
            with self.subTest(boxes=boxes):
                response = self.post(client, headers, save_path,
                                     {"id": 0, "version": 0, "fields": {**fields, "reviewed_boxes": boxes}})
                self.assertEqual(400, response.status_code)
        payload = {"id": 0, "version": 0, "fields": fields}
        response = self.post(client, headers, save_path, payload)
        self.assertEqual(200, response.status_code)
        self.assertEqual(fields["reviewed_boxes"], response.json["review"]["reviewed_boxes"])
        self.assertEqual(self.a["name"], response.json["review"]["reviewer"])
        self.assertEqual(409, self.post(client, headers, save_path, payload).status_code)
        negative = {**fields, "knife_presence": "no", "reviewed_boxes": []}
        response = self.post(client, headers, save_path, {"id": 0, "version": 1, "fields": negative})
        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json["review"]["annotation_verdict"])
        for version, domain, submitted, verdict in (
            (2, "non_target", negative, "problem"),
            (3, "unclear", fields, "unclear"),
        ):
            response = self.post(client, headers, save_path,
                                 {"id": 0, "version": version, "fields": {**submitted, "domain": domain}})
            self.assertEqual(200, response.status_code)
            review = response.json["review"]
            self.assertEqual(verdict, review["annotation_verdict"])
            self.assertIsNone(review["knife_presence"])
            self.assertEqual([], review["reviewed_boxes"])

        self.assertEqual(1, self.post(client, headers, claim, {}).json["id"])
        self.assertEqual(200, self.post(client, headers, save_path, {"id": 1, "version": 0, "fields": fields}).status_code)
        again, _ = self.login(self.a)
        first, second = again.get(endpoint, base_url=self.url).json["items"]
        self.assertEqual([[1, 2, 10, 20]], first["boxes"])
        self.assertIsNone(first["review"]["knife_presence"])
        self.assertEqual([], first["review"]["reviewed_boxes"])
        self.assertEqual([], second["boxes"])
        self.assertEqual(fields["reviewed_boxes"], second["review"]["reviewed_boxes"])
        self.assertEqual(original, (video / "image-evidence.jsonl").read_text())
        store = self.app.extensions["review_stores"]["video"]
        with store.connect() as connection:
            history = [json.loads(payload) for (payload,) in connection.execute(
                "SELECT payload FROM history WHERE sample=0 ORDER BY sequence")]
        self.assertEqual(["yes", "no", None, None], [item["knife_presence"] for item in history])

        config.update(reviewer_login="name", private_video_login=True)
        self.config.write_text(json.dumps(config))
        self.app = create_app(self.config)
        self.app.testing = True
        named, name_headers = self.select_name(self.a)
        catalog = named.get("/api/catalog", base_url=self.url).json
        self.assertTrue(catalog["video_login_required"])
        self.assertNotIn("video", {item["id"] for item in catalog["datasets"]})
        self.assertEqual(200, named.get("/api/items?dataset=fixture", base_url=self.url).status_code)
        self.assertEqual("/video/login", named.get("/review/video", base_url=self.url).location)
        self.assertEqual(403, named.get(endpoint, base_url=self.url).status_code)
        self.assertEqual(403, named.get("/api/packs/video/images/0", base_url=self.url).status_code)
        self.assertEqual(403, self.post(named, name_headers, claim, {}).status_code)
        self.assertEqual(403, self.post(named, name_headers, save_path, payload).status_code)
        for user, status in ((self.b, 200), (self.a, 302)):
            result = named.post("/video/login", base_url=self.url, headers={"Origin": self.url},
                                data={"csrf": catalog["csrf"], "code": user["code"]})
            self.assertEqual(status, result.status_code)
        self.assertEqual(200, named.get(endpoint, base_url=self.url).status_code)
        self.assertEqual(200, named.get("/api/packs/video/images/0", base_url=self.url).status_code)
        self.assertFalse(named.get("/api/catalog", base_url=self.url).json["video_login_required"])
        self.assertEqual(200, self.post(named, name_headers, "/api/logout", {}).status_code)
        self.assertEqual(401, named.get("/api/packs/video/images/0", base_url=self.url).status_code)

    def test_scene_approval_releases_only_selected_frames_and_preserves_leases(self):
        from edge_threat_response.dataset.team_review import create_app

        def pack(name, entries):
            root = self.root / name
            root.mkdir()
            rows, evidence = [], []
            for index, extra in enumerate(entries, 1):
                filename = f"{name}-{index}.jpg"
                content = filename.encode()
                (root / filename).write_bytes(content)
                rows.append(f"{filename},unknown")
                evidence.append({"sample_no": index, "image_path": filename, "image_file": filename,
                                 "width": 100, "height": 60, "image_sha256": hashlib.sha256(content).hexdigest(),
                                 "knife_count": 0, "knife_boxes_xyxy_raw": [], **extra})
            (root / "review.csv").write_text("image_path,original_split\n" + "\n".join(rows))
            (root / "image-evidence.jsonl").write_text("\n".join(json.dumps(row) for row in evidence))
            return str(root)

        scene_root = pack("scene", [{"source_id": f"source-{i}", "scene_start_s": start, "scene_end_s": end}
                                    for i, (start, end) in enumerate(((10, 20), (25, 28), (30, 35)))])
        frame_root = pack("box", [{"source_id": f"source-{i}", "scene_sample": i, "timestamp_s": stamp}
                                  for i, stamp in ((0, 10), (0, 13), (0, 18), (1, 26), (2, 33))])
        config = json.loads(self.config.read_text())
        config.update(reviewer_login="code", video_review_limit=6)
        config["datasets"] += [
            {"id": "scenes", "name": "Scenes", "review_dir": scene_root, "review_schema": "video-scene-v1"},
            {"id": "boxes", "name": "Boxes", "review_dir": frame_root, "review_schema": "video-box-v1",
             "scene_pack": "scenes"},
        ]
        self.config.write_text(json.dumps(config))
        self.app = create_app(self.config)
        self.app.testing = True
        a, ah = self.login(self.a)
        b, bh = self.login(self.b)
        scenes, boxes = "?dataset=scenes", "?dataset=boxes"

        def claim(client, headers, query):
            return self.post(client, headers, "/api/claim" + query, {}).json

        def save(client, headers, query, sample, version, **fields):
            return self.post(client, headers, "/api/review" + query,
                             {"id": sample, "version": version, "fields": fields})

        self.assertEqual("/review/scenes", claim(a, ah, boxes)["next_review_url"])
        self.assertEqual(0, claim(a, ah, scenes)["id"])
        preview = {"scene": 0, "frame": 1}
        self.assertEqual(403, self.post(b, bh, "/api/scene-preview" + scenes, preview).status_code)
        self.assertEqual(13, self.post(a, ah, "/api/scene-preview" + scenes, preview).json["timestamp_s"])
        self.assertEqual(400, save(a, ah, scenes, 0, 0, domain="target_cctv", start_s=9, end_s=15).status_code)
        self.assertEqual(200, save(a, ah, scenes, 0, 0, domain="target_cctv", start_s=10, end_s=15).status_code)
        self.assertEqual("/review/boxes", claim(a, ah, scenes)["next_review_url"])
        self.assertEqual(0, claim(b, bh, boxes)["id"])
        self.assertEqual(200, save(a, ah, scenes, 0, 1, domain="target_cctv", start_s=12, end_s=15).status_code)
        locked = b.get("/api/items" + boxes, base_url=self.url).json["items"][0]
        self.assertFalse(locked["eligible"])
        self.assertTrue(locked["editable"])
        self.assertEqual(0, claim(b, bh, boxes)["id"])
        absence = {"domain": "target_cctv", "knife_presence": "no", "reviewed_boxes": []}
        self.assertEqual(200, save(b, bh, boxes, 0, 0, **absence).status_code)
        self.assertEqual(1, claim(a, ah, boxes)["id"])
        self.assertEqual(200, save(a, ah, boxes, 1, 0, **absence).status_code)
        self.assertEqual("/review/scenes", claim(a, ah, boxes)["next_review_url"])
        self.assertEqual(1, claim(a, ah, scenes)["id"])
        self.assertEqual(200, save(a, ah, scenes, 1, 0, domain="non_target").status_code)
        self.assertTrue(claim(a, ah, scenes)["budget_exhausted"])
        items = a.get("/api/items" + boxes, base_url=self.url).json["items"]
        self.assertEqual([False, True, False, False, False], [item["eligible"] for item in items])
        self.assertEqual([1, 1, 0, 0, 0], [item["version"] for item in items])

    def enable_name_login(self):
        from edge_threat_response.dataset.team_review import create_app
        config = json.loads(self.config.read_text())
        config["reviewer_login"] = "name"
        self.config.write_text(json.dumps(config))
        self.app = create_app(self.config)
        self.app.testing = True

    def select_name(self, user):
        client = self.app.test_client()
        page = client.get("/login", base_url=self.url)
        token = re.search(r'name="csrf" value="([^"]+)"', page.get_data(as_text=True))[1]
        response = client.post("/login", base_url=self.url, headers={"Origin": self.url},
                               data={"reviewer": user["id"], "csrf": token})
        self.assertEqual(302, response.status_code)
        token = client.get("/api/catalog", base_url=self.url).json["csrf"]
        return client, {"Origin": self.url, "X-Review-Token": token}

    def test_name_dropdown_rejects_admin_and_requires_registered_active_identity(self):
        self.enable_name_login()
        client = self.app.test_client()
        page = client.get("/login", base_url=self.url)
        html = page.get_data(as_text=True)
        self.assertIn(self.a["name"], html)
        self.assertNotIn(self.admin["id"], html)
        self.assertNotIn('name="code"', html)
        token = re.search(r'name="csrf" value="([^"]+)"', html)[1]
        for identity in ("", "unknown", self.admin["id"]):
            result = client.post("/login", base_url=self.url, headers={"Origin": self.url},
                                 data={"reviewer": identity, "csrf": token})
            self.assertEqual(200, result.status_code)
            self.assertEqual(401, client.get("/api/catalog", base_url=self.url).status_code)
        client, headers = self.select_name(self.a)
        self.assertEqual(30, self.app.config["PERMANENT_SESSION_LIFETIME"].days)
        self.assertEqual(403, self.post(client, headers, "/api/users", {"name": "unauthorized"}).status_code)
        with self.team.connect() as connection:
            connection.execute("UPDATE users SET active=0 WHERE id=?", (self.a["id"],))
        self.assertEqual(401, client.get("/api/catalog", base_url=self.url).status_code)
        self.assertNotIn(self.a["id"], self.app.test_client().get("/login", base_url=self.url).get_data(as_text=True))

    def test_name_selection_keeps_assignment_and_saved_review_on_reconnect(self):
        self.enable_name_login()
        first, headers = self.select_name(self.a)
        sample = self.post(first, headers, "/api/claim?dataset=fixture", {}).json["id"]
        again, again_headers = self.select_name(self.a)
        self.assertEqual(sample, self.post(again, again_headers, "/api/claim?dataset=fixture", {}).json["id"])
        payload = {"id": sample, "version": 0, "fields": {"domain": "target_cctv", "annotation_verdict": "ok", "reviewer": "spoof"}}
        self.assertEqual(200, self.post(again, again_headers, "/api/review?dataset=fixture", payload).status_code)
        reconnect, _ = self.select_name(self.a)
        data = reconnect.get("/api/items?dataset=fixture", base_url=self.url).json
        self.assertEqual(1, data["items"][sample]["version"])
        self.assertEqual(self.a["name"], data["items"][sample]["review"]["reviewer"])
        self.assertEqual(self.a["id"], data["reviewer_id"])

    def test_admin_login_stays_code_protected_and_session_expires(self):
        self.enable_name_login()
        client = self.app.test_client()
        page = client.get("/admin/login", base_url=self.url)
        html = page.get_data(as_text=True)
        self.assertNotIn('name="reviewer"', html)
        token = re.search(r'name="csrf" value="([^"]+)"', html)[1]
        bad = client.post("/admin/login", base_url=self.url, headers={"Origin": self.url},
                          data={"code": self.a["code"], "csrf": token})
        self.assertEqual(200, bad.status_code)
        result = client.post("/admin/login", base_url=self.url, headers={"Origin": self.url},
                             data={"code": self.admin["code"], "csrf": token})
        self.assertEqual(302, result.status_code)
        self.assertTrue(client.get("/api/catalog", base_url=self.url).json["user"]["admin"])
        with client.session_transaction(base_url=self.url) as session:
            session["admin_login_at"] = 0
        self.assertEqual(401, client.get("/api/catalog", base_url=self.url).status_code)

    def test_public_install_manifest_and_png_icons(self):
        client = self.app.test_client()
        with client.get("/manifest.webmanifest", base_url=self.url) as response:
            self.assertEqual("application/manifest+json", response.mimetype)
            manifest = response.json
        self.assertEqual("standalone", manifest["display"])
        self.assertEqual("/?resume=1", manifest["start_url"])
        for path, size in [("/icon-192.png", 192), ("/icon-512.png", 512), ("/apple-touch-icon.png", 180)]:
            with client.get(path, base_url=self.url) as image:
                self.assertEqual(200, image.status_code)
                self.assertEqual(b"\x89PNG\r\n\x1a\n", image.data[:8])
                self.assertEqual((size, size), struct.unpack(">II", image.data[16:24]))

    def test_catalog_orders_by_current_unreviewed_count_not_total(self):
        from edge_threat_response.dataset.team_review import create_app
        pack = self.root / "larger"
        pack.mkdir()
        (pack / "image.jpg").write_bytes(b"image fixture")
        (pack / "review.csv").write_text("image_path,original_split\na.jpg,train\nb.jpg,train\nc.jpg,train\n")
        evidence = [{"sample_no": i + 1, "image_path": name, "image_file": "image.jpg", "width": 100, "height": 100,
                     "image_sha256": hashlib.sha256(b"image fixture").hexdigest(), "knife_count": 0,
                     "knife_boxes_xyxy_raw": []} for i, name in enumerate(["a.jpg", "b.jpg", "c.jpg"])]
        (pack / "image-evidence.jsonl").write_text("\n".join(json.dumps(item) for item in evidence))
        config = json.loads(self.config.read_text())
        config["datasets"].append({"id": "larger", "name": "Larger", "review_dir": str(pack)})
        self.config.write_text(json.dumps(config))
        self.app = create_app(self.config)
        client, headers = self.login(self.a)
        before = client.get("/api/catalog", base_url=self.url).json["datasets"]
        self.assertEqual(["larger", "fixture", "blocked"], [item["id"] for item in before])
        for dataset, count in [("larger", 2), ("fixture", 2)]:
            for _ in range(count):
                sample = self.post(client, headers, "/api/claim?dataset=" + dataset, {}).json["id"]
                response = self.post(client, headers, "/api/review?dataset=" + dataset,
                                     {"id": sample, "version": 0, "fields": {"domain": "non_target", "annotation_verdict": "ok"}})
                self.assertEqual(200, response.status_code)
            current = client.get("/api/catalog", base_url=self.url).json["datasets"]
            if dataset == "larger":
                self.assertEqual(["fixture", "larger", "blocked"], [item["id"] for item in current])
                self.assertEqual([2, 1, 0], [item["remaining"] for item in current])
            else:
                self.assertEqual(["larger", "fixture", "blocked"], [item["id"] for item in current])
                self.assertEqual([1, 0, 0], [item["remaining"] for item in current])

    def test_auth_images_host_origin_csrf_and_no_credentials_in_catalog(self):
        client = self.app.test_client()
        for path in ["/api/catalog", "/api/items?dataset=fixture", "/api/packs/fixture/images/0", "/app.js"]:
            self.assertIn(client.get(path, base_url=self.url).status_code, {302, 401})
        self.assertIn(client.get("/login", base_url=self.url, headers={"Host": "attacker.example"}).status_code, {400, 403})
        client, headers = self.login(self.a)
        self.assertEqual(403, self.post(client, {**headers, "Origin": "https://attacker.test"}, "/api/claim?dataset=fixture", {}).status_code)
        self.assertEqual(403, self.post(client, {"Origin": self.url}, "/api/claim?dataset=fixture", {}).status_code)
        with client.get("/api/packs/fixture/images/0", base_url=self.url) as image:
            self.assertEqual(200, image.status_code)
            self.assertEqual(b"image fixture", image.data)
        data = client.get("/api/catalog", base_url=self.url).get_data(as_text=True)
        self.assertNotIn("code_hash", data)
        self.assertNotIn(self.a["code"], data)
        self.assertNotIn(str(self.root), data)

    def test_claims_do_not_overlap_reviewer_cannot_be_spoofed_and_version_conflicts(self):
        ca, ha = self.login(self.a)
        cb, hb = self.login(self.b)
        one = self.post(ca, ha, "/api/claim?dataset=fixture", {}).json["id"]
        two = self.post(cb, hb, "/api/claim?dataset=fixture", {}).json["id"]
        self.assertNotEqual(one, two)
        payload = {"id": one, "version": 0, "fields": {"domain": "target_cctv", "annotation_verdict": "ok", "reviewer": "spoof"}}
        self.assertEqual(403, self.post(cb, hb, "/api/review?dataset=fixture", payload).status_code)
        saved = self.post(ca, ha, "/api/review?dataset=fixture", payload)
        self.assertEqual(200, saved.status_code)
        self.assertEqual("fixture-a", saved.json["review"]["reviewer"])
        self.assertEqual(409, self.post(ca, ha, "/api/review?dataset=fixture", payload).status_code)

    def test_admin_invites_revocation_releases_tasks_and_invalidates_session(self):
        ca, ha = self.login(self.a)
        self.post(ca, ha, "/api/claim?dataset=fixture", {})
        self.assertEqual(403, self.post(ca, ha, "/api/users", {"name": "No"}).status_code)
        admin, headers = self.login(self.admin)
        self.assertEqual(403, self.post(admin, headers, "/api/claim?dataset=fixture", {}).status_code)
        invited = self.post(admin, headers, "/api/users", {"name": "fixture-new"})
        self.assertEqual(200, invited.status_code)
        self.assertGreater(len(invited.json["code"]), 20)
        self.assertEqual(200, self.post(admin, headers, f"/api/users/{self.a['id']}/disable", {}).status_code)
        self.assertEqual(401, ca.get("/api/catalog", base_url=self.url).status_code)
        with self.team.connect() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM assignments WHERE user=?", (self.a["id"],)).fetchone()[0])

    def test_validation_blocked_pack_and_consistent_backup(self):
        from edge_threat_response.dataset.team_review import backup_databases
        admin, admin_headers = self.login(self.admin)
        self.assertEqual(404, admin.get("/api/items?dataset=blocked", base_url=self.url).status_code)
        client, headers = self.login(self.a)
        self.post(client, headers, "/api/claim?dataset=fixture", {})
        invalid = {"id": 0, "version": 0, "fields": {"domain": "target_cctv", "annotation_verdict": "problem"}}
        self.assertEqual(400, self.post(client, headers, "/api/review?dataset=fixture", invalid).status_code)
        backup_databases(self.app, self.root / "backups")
        backups = list((self.root / "backups").glob("*.sqlite3"))
        self.assertEqual(2, len(backups))
        for path in backups:
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual("ok", connection.execute("PRAGMA quick_check").fetchone()[0])

    def append_fixture(self, batch_id="batch-1", duplicate=False):
        from edge_threat_response.dataset.team_review import create_app
        pack = self.root / batch_id
        pack.mkdir()
        raw = b"image fixture" if duplicate else batch_id.encode()
        (pack / "image.jpg").write_bytes(raw)
        (pack / "review.csv").write_text(f"image_path,original_split\n{batch_id}.jpg,train\n")
        row = {"sample_no": 1, "image_path": batch_id+".jpg", "image_file": "image.jpg", "width": 100, "height": 100,
               "image_sha256": hashlib.sha256(raw).hexdigest(), "knife_count": 0, "knife_boxes_xyxy_raw": []}
        (pack / "image-evidence.jsonl").write_text(json.dumps(row))
        config = json.loads(self.config.read_text())
        config["datasets"][0].setdefault("review_batches", []).append({"id": batch_id, "review_dir": str(pack)})
        self.config.write_text(json.dumps(config))
        self.app = create_app(self.config)
        self.app.testing = True

    def test_append_preserves_reviews_history_ids_pending_assignment_cookie_and_draft_identity(self):
        self.enable_name_login()
        client, headers = self.select_name(self.a)
        other, other_headers = self.select_name(self.b)
        self.post(client, headers, "/api/claim?dataset=fixture", {})
        self.post(other, other_headers, "/api/claim?dataset=fixture", {})
        payload = {"id": 0, "version": 0, "fields": {"domain": "target_cctv", "annotation_verdict": "ok"}}
        self.assertEqual(200, self.post(client, headers, "/api/review?dataset=fixture", payload).status_code)
        payload["version"] = 1
        self.assertEqual(200, self.post(client, headers, "/api/review?dataset=fixture", payload).status_code)
        base = self.app.extensions["review_stores"]["fixture"]
        with base.connect() as connection:
            before = [list(connection.execute("SELECT * FROM " + table)) for table in ("reviews", "history", "metadata")]
        with self.team.connect() as connection:
            assignments = list(connection.execute("SELECT * FROM assignments ORDER BY sample"))
        pack_hash = base.pack_hash
        cookie = other.get_cookie("etr_review_session", domain="review.example.test").value
        self.append_fixture()
        with base.connect() as connection:
            self.assertEqual(before, [list(connection.execute("SELECT * FROM " + table)) for table in ("reviews", "history", "metadata")])
        with self.team.connect() as connection:
            self.assertEqual([tuple(r) for r in assignments], [tuple(r) for r in connection.execute("SELECT * FROM assignments ORDER BY sample")])
        reconnect = self.app.test_client()
        reconnect.set_cookie("etr_review_session", cookie, domain="review.example.test")
        data = reconnect.get("/api/items?dataset=fixture", base_url=self.url).json
        self.assertEqual(pack_hash, data["pack_hash"])
        self.assertEqual(2, data["items"][0]["version"])
        self.assertEqual([0, 1, 2], [item["id"] for item in data["items"]])
        self.assertTrue(data["items"][1]["editable"])
        self.assertEqual(1, self.post(reconnect, other_headers, "/api/claim?dataset=fixture", {"known_total": 3}).json["id"])
        # Original open-tab update keeps old global IDs and conflict semantics.
        payload["id"], payload["version"] = 1, 0
        self.assertEqual(200, self.post(reconnect, other_headers, "/api/review?dataset=fixture", payload).status_code)
        self.assertEqual(409, self.post(reconnect, other_headers, "/api/review?dataset=fixture", payload).status_code)
        legacy = self.post(reconnect, other_headers, "/api/claim?dataset=fixture", {}).json
        self.assertEqual({"id": None, "refresh_required": True}, legacy)
        self.assertEqual(2, self.post(reconnect, other_headers, "/api/claim?dataset=fixture", {"known_total": 3}).json["id"])
        payload["id"] = 2
        self.assertEqual(200, self.post(reconnect, other_headers, "/api/review?dataset=fixture", payload).status_code)
        self.assertEqual(409, self.post(reconnect, other_headers, "/api/review?dataset=fixture", payload).status_code)
        self.assertEqual(403, self.post(*self.select_name(self.a), "/api/review?dataset=fixture", payload).status_code)
        self.app = __import__("edge_threat_response.dataset.team_review", fromlist=["create_app"]).create_app(self.config)
        resumed, _ = self.select_name(self.b)
        self.assertEqual(1, resumed.get("/api/items?dataset=fixture", base_url=self.url).json["items"][2]["version"])

    def test_append_rejects_duplicate_hash_and_registry_reordering_removal(self):
        from edge_threat_response.dataset.team_review import create_app
        with self.assertRaisesRegex(ValueError, "Duplicate image"):
            self.append_fixture("duplicate", duplicate=True)
        config = json.loads(self.config.read_text())
        config["datasets"][0].pop("review_batches")
        self.config.write_text(json.dumps(config))
        self.append_fixture("one")
        self.append_fixture("two")
        config = json.loads(self.config.read_text())
        config["datasets"][0]["review_batches"].reverse()
        self.config.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "registry mismatch"):
            create_app(self.config)
        config["datasets"][0]["review_batches"] = []
        self.config.write_text(json.dumps(config))
        with self.assertRaisesRegex(ValueError, "registry mismatch"):
            create_app(self.config)

    def test_append_backups_include_each_batch_and_catalog_never_exposes_paths(self):
        from edge_threat_response.dataset.team_review import backup_databases
        self.append_fixture()
        admin, _ = self.login(self.admin)
        response = admin.get("/api/catalog", base_url=self.url)
        self.assertEqual(2, response.json["datasets"][0]["batch_count"])
        self.assertEqual(3, response.json["datasets"][0]["total"])
        self.assertNotIn(str(self.root), response.get_data(as_text=True))
        self.assertNotIn("review_batches", response.get_data(as_text=True))
        backup_databases(self.app, self.root / "expanded-backups")
        self.assertEqual(3, len(list((self.root / "expanded-backups").glob("*.sqlite3"))))

    def test_readonly_status_backup_preserves_all_tables_and_counts_each_batch(self):
        spec = importlib.util.spec_from_file_location("team_status", Path(__file__).resolve().parents[1] / "tools/team_review_status.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.append_fixture()
        first = module.inspect(self.config)
        second = module.inspect(self.config, self.root / "status-backup")
        self.assertEqual(first, second)
        self.assertEqual(3, second["datasets"]["fixture"]["prepared"])
        self.assertEqual(0, second["datasets"]["fixture"]["reviewed"])
        for key in second["databases"]:
            with closing(sqlite3.connect(self.root / "status-backup" / (key+".sqlite3"))) as connection:
                self.assertEqual("ok", connection.execute("PRAGMA quick_check").fetchone()[0])
