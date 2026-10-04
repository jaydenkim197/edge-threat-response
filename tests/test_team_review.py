import hashlib
import importlib.util
import json
import re
import sqlite3
import struct
import tempfile
import unittest
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
