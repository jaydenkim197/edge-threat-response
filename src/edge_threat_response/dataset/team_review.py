"""Authenticated multi-pack review. Bind only to loopback behind HTTPS Funnel."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sqlite3
import threading
import time
from collections import deque
from contextlib import closing, contextmanager
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from .review_web import PRIVATE_REVIEW_SCHEMAS, SCENE_REVIEW_SCHEMA, VIDEO_REVIEW_SCHEMA, BatchReviewStore, ConflictError, ReviewStore, review_verdict

ASSIGNMENT_TIMEOUT_SECONDS = 15 * 60


class TeamDatabase:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, code_hash TEXT NOT NULL, admin INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1)")
            connection.execute("CREATE TABLE IF NOT EXISTS assignments (pack TEXT NOT NULL, sample INTEGER NOT NULL, user TEXT NOT NULL, PRIMARY KEY(pack,sample))")
            connection.execute("CREATE TABLE IF NOT EXISTS assignment_activity (pack TEXT NOT NULL, sample INTEGER NOT NULL, user TEXT NOT NULL, last_seen REAL NOT NULL, PRIMARY KEY(pack,sample))")
            # Additive migration: retain legacy owners and give them a fresh grace period.
            connection.execute("INSERT OR IGNORE INTO assignment_activity SELECT pack,sample,user,? FROM assignments", (time.time(),))

    @staticmethod
    def touch_assignment(connection, pack, sample, user):
        connection.execute("INSERT OR REPLACE INTO assignment_activity VALUES (?,?,?,?)", (pack, sample, user, time.time()))

    @staticmethod
    def expire_pending(connection, pack, items):
        pending = {item["id"] for item in items if not item["version"]}
        now = time.time()
        connection.execute("INSERT OR IGNORE INTO assignment_activity SELECT pack,sample,user,? FROM assignments WHERE pack=?", (now, pack))
        expired = list(connection.execute(
            "SELECT a.sample FROM assignments a JOIN assignment_activity l "
            "ON a.pack=l.pack AND a.sample=l.sample AND a.user=l.user WHERE a.pack=? AND l.last_seen<=?",
            (pack, now - ASSIGNMENT_TIMEOUT_SECONDS)))
        released = 0
        for row in expired:
            if row["sample"] in pending:
                connection.execute("DELETE FROM assignments WHERE pack=? AND sample=?", (pack, row["sample"]))
                connection.execute("DELETE FROM assignment_activity WHERE pack=? AND sample=?", (pack, row["sample"]))
                released += 1
        return released

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def user(self, user_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
        return dict(row) if row else None

    def create_user(self, name, *, admin=False):
        from werkzeug.security import generate_password_hash
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ValueError("검수자 이름은 1~80자로 입력해주세요.")
        code = secrets.token_urlsafe(24)
        user_id = secrets.token_hex(8)
        with self.connect() as connection:
            connection.execute("INSERT INTO users(id,name,code_hash,admin) VALUES (?,?,?,?)",
                               (user_id, name.strip(), generate_password_hash(code), int(admin)))
        return {"id": user_id, "name": name.strip(), "code": code}

    def login(self, code):
        from werkzeug.security import check_password_hash
        if not isinstance(code, str) or not 20 <= len(code) <= 120:
            return None
        with self.connect() as connection:
            rows = list(connection.execute("SELECT * FROM users WHERE active=1 AND code_hash<>''"))
        for row in rows:
            if check_password_hash(row["code_hash"], code):
                return dict(row)
        return None

    def create_video_reviewer(self):
        user_id = secrets.token_hex(8)
        with self.connect() as connection:
            connection.execute("INSERT INTO users(id,name,code_hash,admin) VALUES (?,?,?,0)",
                               (user_id, f"영상 검수자 {user_id}", ""))
        return user_id


    def register_batches(self, stores):
        """Additive registry migration. A deployed prefix can never be reordered."""
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE IF NOT EXISTS review_batches (pack TEXT NOT NULL, batch TEXT NOT NULL, offset INTEGER NOT NULL, count INTEGER NOT NULL, pack_hash TEXT NOT NULL, PRIMARY KEY(pack,batch), UNIQUE(pack,offset))")
            old_packs = {row[0] for row in connection.execute("SELECT DISTINCT pack FROM review_batches")}
            if old_packs - set(stores):
                raise ValueError("Previously deployed dataset cannot be removed implicitly")
            for pack, store in stores.items():
                parts = store.parts if isinstance(store, BatchReviewStore) else [("initial", 0, store)]
                expected = [(batch, offset, len(part.rows), part.pack_hash) for batch, offset, part in parts]
                previous = [tuple(row) for row in connection.execute(
                    "SELECT batch,offset,count,pack_hash FROM review_batches WHERE pack=? ORDER BY offset", (pack,))]
                if previous != expected[:len(previous)]:
                    raise ValueError("Review batch registry mismatch; preserve the deployed prefix")
                for batch, offset, count, digest in expected[len(previous):]:
                    connection.execute("INSERT INTO review_batches VALUES (?,?,?,?,?)", (pack, batch, offset, count, digest))


def create_app(config_path: Path):
    from flask import Flask, abort, g, jsonify, redirect, render_template, request, send_file, session
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    catalog = config["datasets"]
    login_mode = config.get("reviewer_login", "code")
    name_login = login_mode == "name"
    video_link_login = login_mode == "video_link"
    video_public_login = login_mode == "video_public"
    video_only = video_link_login or video_public_login
    private_packs = {entry["id"] for entry in catalog
                     if entry.get("review_schema") in PRIVATE_REVIEW_SCHEMAS or "scene_pack" in entry}
    video_unlock = bool(private_packs and name_login and config.get("private_video_login") is True)
    if private_packs and config.get("reviewer_login") != "code" and not (video_unlock or video_only):
        raise ValueError("Video review packs require explicit reviewer code or an explicit video access mode.")
    if video_only and not private_packs:
        raise ValueError("Video access mode requires video review packs.")
    video_link_hash = None
    if video_link_login:
        token = Path(config["video_link_file"]).read_text(encoding="ascii").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{43,80}", token):
            raise ValueError("Video link mode requires a strong link secret.")
        video_link_hash = hashlib.sha256(token.encode("ascii")).hexdigest()
    origin = config["public_url"].rstrip("/")
    parsed = urlsplit(origin)
    local = parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    if not ((parsed.scheme == "https" or local) and parsed.netloc and parsed.path in {"", "/"}
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment):
        raise ValueError("Use one explicit HTTPS origin (or loopback-only QA).")
    secret_file = Path(config["secret_file"]).resolve()
    secret = secret_file.read_text(encoding="ascii").strip()
    if len(secret) < 43:
        raise ValueError("Session secret is too short")
    assets = Path(__file__).parent / "web_review"
    app = Flask(__name__, static_folder=None, template_folder=str(assets))
    app.config.update(SECRET_KEY=secret, SESSION_COOKIE_SECURE=not local,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax" if video_only else "Strict",
                      SESSION_COOKIE_NAME="etr_review_session",
                      PERMANENT_SESSION_LIFETIME=timedelta(days=30) if name_login or video_only else timedelta(hours=8),
                      MAX_CONTENT_LENGTH=16384, TRUSTED_HOSTS=[parsed.hostname])
    team = TeamDatabase(Path(config["database"]))
    stores, dataset_ids = {}, set()
    for entry in catalog:
        if not re.fullmatch(r"[a-z0-9-]{1,60}", entry["id"]):
            raise ValueError("Invalid dataset identifier")
        if entry["id"] in dataset_ids:
            raise ValueError("Duplicate dataset identifier")
        dataset_ids.add(entry["id"])
        if entry.get("review_dir"):
            schema = entry.get("review_schema", "simple-v2")
            base = ReviewStore(Path(entry["review_dir"]), review_schema=schema)
            batches = []
            for batch in entry.get("review_batches", []):
                if not re.fullmatch(r"[a-z0-9-]{1,60}", batch["id"]):
                    raise ValueError("Invalid batch identifier")
                batches.append((batch["id"], ReviewStore(Path(batch["review_dir"]), review_schema=schema)))
            stores[entry["id"]] = BatchReviewStore(base, batches) if batches else base
    scene_for = {}
    frames_for = {}
    previews = {}
    for entry in catalog:
        if "scene_pack" not in entry:
            continue
        pack, scene = entry["id"], entry["scene_pack"]
        if (not isinstance(scene, str) or scene not in stores or pack not in stores
                or stores[scene].review_schema != SCENE_REVIEW_SCHEMA
                or stores[pack].review_schema != VIDEO_REVIEW_SCHEMA or scene in frames_for):
            raise ValueError("A video box pack must reference one unique video scene pack.")
        scene_for[pack] = scene
        frames_for[scene] = pack
        for sample, frame in enumerate(stores[pack].evidence):
            index, stamp = frame.get("scene_sample"), frame.get("timestamp_s")
            if type(index) is not int or not 0 <= index < len(stores[scene].evidence):
                raise ValueError("Invalid video frame scene reference.")
            bounds = stores[scene].evidence[index]
            if (frame.get("source_id") != bounds["source_id"] or type(stamp) not in (int, float)
                    or not bounds["scene_start_s"] <= stamp <= bounds["scene_end_s"]):
                raise ValueError("Frame does not belong to the referenced scene.")
            previews.setdefault((scene, index), []).append({"id": sample, "timestamp_s": stamp})
    managed = set(scene_for) | set(frames_for)
    limit = config.get("video_review_limit", 8000)
    if managed and (type(limit) is not int or not 1 <= limit < 10000):
        raise ValueError("Video review limit must be between 1 and 9999.")
    if managed:
        with team.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS video_review_budget (id INTEGER PRIMARY KEY CHECK(id=1), used INTEGER NOT NULL)")
            connection.execute("INSERT OR IGNORE INTO video_review_budget VALUES (1,0)")
    team.register_batches(stores)
    app.extensions["review_team"] = team
    app.extensions["review_stores"] = stores
    app.extensions["active_review_stores"] = {pack: store for pack, store in stores.items()
                                             if not video_only or pack in private_packs}
    attempts = deque()
    rate_lock = threading.Lock()

    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    def can_review_video():
        if not video_unlock or g.user["admin"]:
            return True
        return (session.get("video_user") == g.user["id"]
                and 0 <= time.time() - session.get("video_login_at", 0) < 8 * 3600)

    def video_reviewer(user):
        return bool(user and not user["admin"] and not user["code_hash"]
                    and (video_public_login or (video_link_login and session.get("video_link_hash") == video_link_hash)))

    @app.before_request
    def guard():
        if request.host != parsed.netloc:
            abort(403)
        if request.method == "POST":
            if request.headers.get("Origin") != origin:
                abort(403)
            supplied = request.headers.get("X-Review-Token") or request.form.get("csrf", "")
            if not supplied or not secrets.compare_digest(supplied, session.get("csrf", "")):
                abort(403)
        if request.path in {"/login", "/admin/login", "/style.css", "/portal.js", "/install.js", "/manifest.webmanifest",
                            "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png", "/favicon.ico",
                            "/video/open", "/api/video/open", "/video-open.js"}:
            return None
        pack = (request.view_args or {}).get("pack") or request.args.get("dataset")
        if video_only and pack and pack not in private_packs:
            abort(404)
        g.user = team.user(session.get("user", ""))
        if g.user and g.user["admin"] and time.time() - session.get("admin_login_at", 0) > 8 * 3600:
            session.clear()
            g.user = None
        if video_only and g.user and not g.user["admin"] and not video_reviewer(g.user):
            g.user = None
        if not g.user:
            login_url = "/video/open" if video_only else "/login"
            return (jsonify(error="로그인이 필요합니다."), 401) if request.path.startswith("/api/") else redirect(login_url)
        if pack in private_packs and not can_review_video():
            if request.path.startswith("/api/"):
                return jsonify(error="영상 검수 코드가 필요합니다.", video_login_required=True), 403
            return redirect("/video/login")

    @app.after_request
    def security(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Native form POST needs its same-origin Origin header for the CSRF guard.
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; manifest-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if not local:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.errorhandler(ConflictError)
    def conflict(error):
        return jsonify(error=str(error)), 409

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    def login_slot():
        with rate_lock:
            now = time.monotonic()
            while attempts and attempts[0] < now - 60:
                attempts.popleft()
            if len(attempts) >= 12:
                return False
            attempts.append(now)
            return True

    @app.route("/login", methods=["GET", "POST"])
    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        admin_login = request.path == "/admin/login"
        if video_only and not admin_login:
            return redirect("/video/open")
        use_names = name_login and not admin_login
        with team.connect() as connection:
            reviewers = [dict(row) for row in connection.execute("SELECT id,name FROM users WHERE active=1 AND admin=0 ORDER BY rowid")]
        def page(error="", status=200):
            return render_template("login.html", csrf=csrf(), error=error, use_names=use_names,
                                   admin_login=admin_login, reviewers=reviewers), status
        error = ""
        if request.method == "POST":
            if not login_slot():
                return page("시도가 많습니다. 잠시 후 다시 시도해주세요.", 429)
            if use_names:
                user = team.user(request.form.get("reviewer", ""))
                if user and user["admin"]:
                    user = None
            else:
                user = team.login(request.form.get("code", ""))
                if admin_login and user and not user["admin"]:
                    user = None
            if user:
                session.clear()
                session["user"] = user["id"]
                session.permanent = True
                if user["admin"]:
                    session["admin_login_at"] = time.time()
                csrf()
                return redirect("/?resume=1" if use_names else "/")
            error = "본인 이름을 선택해주세요." if use_names else "관리자 코드가 올바르지 않거나 비활성 계정입니다."
        return page(error)

    @app.get("/video/open")
    def open_video():
        if not video_only:
            abort(404)
        user = team.user(session.get("user", ""))
        return render_template("video_open.html", csrf=csrf(), resume=video_reviewer(user), public=video_public_login)

    @app.post("/api/video/open")
    def grant_video_access():
        if not video_only:
            abort(404)
        if video_link_login:
            body = request.get_json(silent=True)
            token = body.get("token") if isinstance(body, dict) else None
            if (not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43,80}", token)
                    or not secrets.compare_digest(hashlib.sha256(token.encode("ascii")).hexdigest(), video_link_hash)):
                if not login_slot():
                    return jsonify(error="시도가 많습니다. 잠시 후 다시 시도해주세요."), 429
                return jsonify(error="영상 검수 공유 링크를 다시 확인해주세요."), 403
        if not video_reviewer(team.user(session.get("user", ""))):
            session.clear()
            session["user"] = team.create_video_reviewer()
            if video_link_login:
                session["video_link_hash"] = video_link_hash
            session.permanent = True
        return jsonify(ok=True)

    @app.route("/video/login", methods=["GET", "POST"])
    def video_login():
        from werkzeug.security import check_password_hash

        if not video_unlock:
            abort(404)
        if can_review_video():
            return redirect("/?video=1")
        error, status = "", 200
        if request.method == "POST":
            code = request.form.get("code", "")
            if not login_slot():
                error, status = "시도가 많습니다. 잠시 후 다시 시도해주세요.", 429
            elif 20 <= len(code) <= 120 and check_password_hash(g.user["code_hash"], code):
                session["video_user"] = g.user["id"]
                session["video_login_at"] = time.time()
                return redirect("/?video=1")
            else:
                error = "선택한 이름의 영상 검수 코드를 확인해주세요."
        return render_template("login.html", csrf=csrf(), error=error, use_names=False,
                               admin_login=False, video_login=True, reviewer_name=g.user["name"]), status

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/")
    def home():
        if (video_public_login and not g.user["admin"]
                and request.args.get("catalog") != "1" and request.args.get("video") != "1"):
            return redirect("/?resume=1&video=1")
        return render_template("portal.html")

    @app.get("/review/<pack>")
    def review(pack):
        if pack not in stores:
            abort(404)
        # Reuse the local UI byte-for-byte; its script switches on /review/<id>.
        return (assets / "index.html").read_text(encoding="utf-8")

    @app.get("/style.css")
    @app.get("/portal.js")
    @app.get("/video-open.js")
    @app.get("/app.js")
    @app.get("/install.js")
    @app.get("/manifest.webmanifest")
    @app.get("/icon-192.png")
    @app.get("/icon-512.png")
    @app.get("/apple-touch-icon.png")
    @app.get("/favicon.ico")
    def asset():
        filename = "icon-192.png" if request.path == "/favicon.ico" else request.path[1:]
        return send_file(assets / filename, mimetype="application/manifest+json" if request.path == "/manifest.webmanifest" else None)

    def eligible_frames(pack):
        if pack not in scene_for:
            return None
        scenes = stores[scene_for[pack]].items()
        ready = set()
        for sample, frame in enumerate(stores[pack].evidence):
            verdict = scenes[frame["scene_sample"]]["review"]
            if (verdict.get("domain") == "target_cctv"
                    and verdict["start_s"] <= frame["timestamp_s"] <= verdict["end_s"]):
                ready.add(sample)
        return ready

    def reserve_review(connection):
        return connection.execute("UPDATE video_review_budget SET used=used+1 WHERE id=1 AND used<?",
                                  (limit,)).rowcount == 1

    def claim_snapshot(connection, pack, store):
        result = store.items()
        team.expire_pending(connection, pack, result)
        owners = {row["sample"]: row["user"] for row in connection.execute(
            "SELECT sample,user FROM assignments WHERE pack=?", (pack,))}
        eligible = eligible_frames(pack)
        owned = next((item for item in result if not item["version"] and owners.get(item["id"]) == g.user["id"]), None)
        ready = next((item for item in result if not item["version"] and item["id"] not in owners
                      and (eligible is None or item["id"] in eligible)), None)
        waiting = sum(not item["version"] and item["id"] in owners for item in result)
        return owned, ready, waiting

    @app.get("/api/catalog")
    def get_catalog():
        entries = []
        for entry in catalog:
            if video_only and entry["id"] not in private_packs:
                continue
            if entry["id"] in private_packs and not can_review_video():
                continue
            store = stores.get(entry["id"])
            items, owners = assigned_items(entry["id"], store) if store else ([], {})
            eligible = eligible_frames(entry["id"])
            reviewed = [item for item in items if item["version"]]
            entries.append({key: value for key, value in entry.items() if key not in {"review_dir", "review_batches"}} | {
                "available": bool(store), "total": len(items), "reviewed": len(reviewed),
                "remaining": sum(not item["version"] and (eligible is None or item["id"] in eligible or item["id"] in owners)
                                 for item in items),
                "held": sum(review_verdict(item["review"], item["knife_count"]) != "ok" for item in reviewed),
                "mine": sum(item["review"].get("reviewer") == g.user["name"] for item in reviewed),
                "batch_count": len(store.parts) if isinstance(store, BatchReviewStore) else int(bool(store))})
        # Python's stable sort preserves catalog order when remaining counts tie.
        entries.sort(key=lambda item: (not item["available"],
                                        not (item["id"] in scene_for and item["remaining"]), -item["remaining"]))
        return jsonify(datasets=entries, user={"id": g.user["id"], "name": g.user["name"], "admin": bool(g.user["admin"])},
                       csrf=csrf(), name_login=name_login, video_login_required=video_unlock and not can_review_video(),
                       video_review_enabled=bool(private_packs), video_only=video_only, video_public=video_public_login)

    def current_store():
        pack = request.args.get("dataset", "")
        if pack not in stores:
            abort(404)
        return pack, stores[pack]

    def assigned_items(pack, store):
        with team.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = store.items()
            team.expire_pending(connection, pack, result)
            owners = {row["sample"]: row["user"] for row in connection.execute("SELECT sample,user FROM assignments WHERE pack=?", (pack,))}
        return result, owners

    @app.get("/api/items")
    def items():
        pack, store = current_store()
        result, owners = assigned_items(pack, store)
        eligible = eligible_frames(pack)
        for item in result:
            item["image_url"] = f"/api/packs/{pack}/images/{item['id']}"
            item["editable"] = bool(not g.user["admin"] and owners.get(item["id"]) == g.user["id"])
            item["assigned_elsewhere"] = item["id"] in owners and owners[item["id"]] != g.user["id"]
            item["coordinate_status"] = store.evidence[item["id"]].get("coordinate_status", "unconfirmed")
            if eligible is not None:
                item["eligible"] = item["id"] in eligible
                evidence = store.evidence[item["id"]]
                item["source_id"] = evidence["source_id"]
                item["timestamp_s"] = evidence["timestamp_s"]
            if pack in frames_for:
                item["previews"] = previews.get((pack, item["id"]), [])
                item["source_id"] = store.evidence[item["id"]]["source_id"]
        return jsonify(items=result, csrf=csrf(), pack_hash=store.pack_hash, review_schema=store.review_schema, team=True,
                       reviewer=g.user["name"], reviewer_id=g.user["id"], admin=bool(g.user["admin"]), training_approved=False,
                       assignment_timeout_seconds=ASSIGNMENT_TIMEOUT_SECONDS, linked_review=pack in managed,
                       video_only=video_only)

    @app.post("/api/claim")
    def claim():
        if g.user["admin"]:
            abort(403)
        pack, store = current_store()
        body = request.get_json() or {}
        if not isinstance(body, dict):
            raise ValueError("Expected claim object")
        known_total = body.get("known_total")
        if known_total is not None and (type(known_total) is not int or known_total < 1):
            raise ValueError("Invalid client sample count")
        with team.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owned, ready, waiting = claim_snapshot(connection, pack, store)
            candidate = owned or ready
            other = frames_for.get(pack) if owned is None else None
            if candidate is None:
                other = other or scene_for.get(pack)
            if other:
                other_owned, other_ready, _ = claim_snapshot(connection, other, stores[other])
                if other_owned or other_ready:
                    return jsonify(id=None, next_review_url=f"/review/{other}")
            if candidate is None:
                if pack in managed:
                    for next_pack in [*scene_for, *frames_for]:
                        if next_pack in {pack, other}:
                            continue
                        next_owned, next_ready, _ = claim_snapshot(connection, next_pack, stores[next_pack])
                        if next_owned or next_ready:
                            return jsonify(id=None, next_review_url=f"/review/{next_pack}")
                return jsonify(id=None, pending_assigned=waiting)
            # Old open tabs know only the original IDs. Do not assign an ID
            # their cached item array cannot display; old saves remain valid.
            client_count = known_total if known_total is not None else len(store.parts[0][2].rows) if isinstance(store, BatchReviewStore) else len(store.rows)
            if candidate["id"] >= client_count:
                return jsonify(id=None, refresh_required=True)
            if not owned and pack in managed and not reserve_review(connection):
                return jsonify(id=None, budget_exhausted=True)
            connection.execute("INSERT OR IGNORE INTO assignments VALUES (?,?,?)", (pack, candidate["id"], g.user["id"]))
            team.touch_assignment(connection, pack, candidate["id"], g.user["id"])
            if pack in scene_for:
                return jsonify(id=candidate["id"], eligible=candidate["id"] in eligible_frames(pack))
        return jsonify(id=candidate["id"])

    @app.post("/api/scene-preview")
    def scene_preview():
        pack, store = current_store()
        body = request.get_json()
        if g.user["admin"] or pack not in frames_for:
            abort(403)
        if not isinstance(body, dict) or type(body.get("scene")) is not int or type(body.get("frame")) is not int:
            raise ValueError("Unknown preview.")
        sample, frame = body["scene"], body["frame"]
        preview = next((row for row in previews.get((pack, sample), []) if row["id"] == frame), None)
        if preview is None:
            abort(404)
        with team.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            team.expire_pending(connection, pack, store.items())
            owner = connection.execute("SELECT user FROM assignments WHERE pack=? AND sample=?", (pack, sample)).fetchone()
            if not owner or owner["user"] != g.user["id"]:
                abort(403)
            if not reserve_review(connection):
                return jsonify(error="영상 검수 한도에 도달했습니다."), 409
            team.touch_assignment(connection, pack, sample, g.user["id"])
        return jsonify(**preview, image_url=f"/api/packs/{frames_for[pack]}/images/{frame}")

    @app.post("/api/heartbeat")
    def heartbeat():
        if g.user["admin"]:
            abort(403)
        pack, store = current_store()
        body = request.get_json()
        sample = body.get("id") if isinstance(body, dict) else None
        if type(sample) is not int or not 0 <= sample < len(store.rows):
            raise ValueError("Unknown sample")
        with team.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            team.expire_pending(connection, pack, store.items())
            owner = connection.execute("SELECT user FROM assignments WHERE pack=? AND sample=?", (pack, sample)).fetchone()
            if not owner or owner["user"] != g.user["id"]:
                return jsonify(assignment_lost=True, error="배정이 만료되거나 회수됐습니다. 다음 미검수를 받아주세요."), 409
            team.touch_assignment(connection, pack, sample, g.user["id"])
        return jsonify(ok=True)

    @app.post("/api/review")
    def save():
        pack, store = current_store()
        body = request.get_json()
        if not isinstance(body, dict) or not isinstance(body.get("fields"), dict):
            raise ValueError("Expected review object")
        sample = body.get("id")
        if type(sample) is not int or not 0 <= sample < len(store.rows):
            raise ValueError("Unknown sample")
        if g.user["admin"]:
            abort(403)
        fields = {**body["fields"], "reviewer": g.user["name"], "review_schema": store.review_schema}
        # Hold the ownership lock until the review commits. Reclaim cannot race a save.
        with team.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            team.expire_pending(connection, pack, store.items())
            owner = connection.execute("SELECT user FROM assignments WHERE pack=? AND sample=?", (pack, sample)).fetchone()
            if not owner or owner["user"] != g.user["id"]:
                return jsonify(assignment_lost=True, error="배정이 만료되거나 회수됐습니다. 입력은 임시 보관되며 다음 미검수를 받을 수 있습니다."), 403 if owner else 409
            if pack in managed and type(body.get("version")) is int and body["version"] > 0 and not reserve_review(connection):
                return jsonify(error="영상 재검수 한도에 도달했습니다."), 409
            result = store.save(sample, body.get("version"), fields)
            team.touch_assignment(connection, pack, sample, g.user["id"])
        return jsonify(result)

    @app.get("/api/packs/<pack>/images/<int:sample>")
    def image(pack, sample):
        if pack not in stores or not 0 <= sample < len(stores[pack].images):
            abort(404)
        return send_file(stores[pack].images[sample], conditional=False)

    @app.post("/api/users")
    def invite():
        if not g.user["admin"]:
            abort(403)
        if video_only:
            abort(404)
        body = request.get_json()
        return jsonify(team.create_user(body.get("name") if isinstance(body, dict) else None))

    @app.get("/api/users")
    def users():
        if not g.user["admin"]:
            abort(403)
        with team.connect() as connection:
            return jsonify(users=[dict(row) for row in connection.execute(
                "SELECT id,name,admin,active FROM users WHERE NOT ? OR admin=1 OR code_hash=''", (video_only,))])

    @app.post("/api/users/<user_id>/disable")
    def disable(user_id):
        if not g.user["admin"] or user_id == g.user["id"]:
            abort(403)
        with team.connect() as connection:
            changed = connection.execute("UPDATE users SET active=0 WHERE id=? AND (NOT ? OR code_hash='')",
                                         (user_id, video_only)).rowcount
            if video_only and not changed:
                abort(404)
            connection.execute("DELETE FROM assignments WHERE user=?", (user_id,))
            connection.execute("DELETE FROM assignment_activity WHERE user=?", (user_id,))
        return jsonify(ok=True)

    @app.post("/api/release")
    def release():
        pack, store = current_store()
        sample = (request.get_json() or {}).get("id")
        if type(sample) is not int:
            raise ValueError("Unknown sample")
        with team.connect() as connection:
            if g.user["admin"]:
                connection.execute("DELETE FROM assignments WHERE pack=? AND sample=?", (pack, sample))
                connection.execute("DELETE FROM assignment_activity WHERE pack=? AND sample=?", (pack, sample))
            else:
                connection.execute("DELETE FROM assignments WHERE pack=? AND sample=? AND user=?", (pack, sample, g.user["id"]))
                connection.execute("DELETE FROM assignment_activity WHERE pack=? AND sample=? AND user=?", (pack, sample, g.user["id"]))
        return jsonify(ok=True)

    return app


def reclaim_expired_assignments(app):
    team = app.extensions["review_team"]
    released = 0
    with team.connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        for pack, store in app.extensions["active_review_stores"].items():
            released += team.expire_pending(connection, pack, store.items())
    return released


def backup_databases(app, directory: Path):
    """Consistent SQLite backups, not live-file copies. Same-disk recovery only."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    directory.mkdir(parents=True, exist_ok=True)
    paths = {"team": app.extensions["review_team"].path}
    for name, store in app.extensions["review_stores"].items():
        parts = store.parts if isinstance(store, BatchReviewStore) else [("initial", 0, store)]
        for batch_id, _, part in parts:
            paths[name if batch_id == "initial" else f"{name}--{batch_id}"] = part.database
    for name, source in paths.items():
        target = directory / f"{stamp}-{name}.sqlite3"
        if target.exists():
            continue
        with closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)) as origin, closing(sqlite3.connect(target)) as output:
            origin.backup(output)
            if output.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity failure")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8770)
    args = parser.parse_args()
    from waitress import serve
    app = create_app(args.config)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    directory = Path(config["database"]).parent / "backups"
    def backup_loop():
        while True:
            try:
                backup_databases(app, directory)
                print("Review DB backup verified", flush=True)
            except Exception as error:
                print(f"Review DB backup failed: {type(error).__name__}", flush=True)
            time.sleep(1800)
    threading.Thread(target=backup_loop, daemon=True).start()
    def reclaim_loop():
        while True:
            try:
                reclaim_expired_assignments(app)
            except Exception as error:
                print(f"Assignment reclaim failed: {type(error).__name__}", flush=True)
            time.sleep(60)
    threading.Thread(target=reclaim_loop, daemon=True).start()
    print(f"Authenticated review listening on loopback:{args.port}", flush=True)
    serve(app, host="127.0.0.1", port=args.port, threads=8, max_request_body_size=16384,
          channel_timeout=30, clear_untrusted_proxy_headers=True)


if __name__ == "__main__":
    main()
