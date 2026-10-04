"""Authenticated multi-pack review. Bind only to loopback behind HTTPS Funnel."""
from __future__ import annotations

import argparse
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

from .review_web import BatchReviewStore, ConflictError, ReviewStore


class TeamDatabase:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT NOT NULL, code_hash TEXT NOT NULL, admin INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1)")
            connection.execute("CREATE TABLE IF NOT EXISTS assignments (pack TEXT NOT NULL, sample INTEGER NOT NULL, user TEXT NOT NULL, PRIMARY KEY(pack,sample))")

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
            rows = list(connection.execute("SELECT * FROM users WHERE active=1"))
        for row in rows:
            if check_password_hash(row["code_hash"], code):
                return dict(row)
        return None


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
    name_login = config.get("reviewer_login", "code") == "name"
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
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      SESSION_COOKIE_NAME="etr_review_session", PERMANENT_SESSION_LIFETIME=timedelta(days=30) if name_login else timedelta(hours=8),
                      MAX_CONTENT_LENGTH=16384, TRUSTED_HOSTS=[parsed.hostname])
    team = TeamDatabase(Path(config["database"]))
    catalog, stores, dataset_ids = config["datasets"], {}, set()
    for entry in catalog:
        if not re.fullmatch(r"[a-z0-9-]{1,60}", entry["id"]):
            raise ValueError("Invalid dataset identifier")
        if entry["id"] in dataset_ids:
            raise ValueError("Duplicate dataset identifier")
        dataset_ids.add(entry["id"])
        if entry.get("review_dir"):
            base = ReviewStore(Path(entry["review_dir"]))
            batches = []
            for batch in entry.get("review_batches", []):
                if not re.fullmatch(r"[a-z0-9-]{1,60}", batch["id"]):
                    raise ValueError("Invalid batch identifier")
                batches.append((batch["id"], ReviewStore(Path(batch["review_dir"]))))
            stores[entry["id"]] = BatchReviewStore(base, batches) if batches else base
    team.register_batches(stores)
    app.extensions["review_team"] = team
    app.extensions["review_stores"] = stores
    attempts = deque()
    rate_lock = threading.Lock()

    def csrf():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

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
                            "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png", "/favicon.ico"}:
            return None
        g.user = team.user(session.get("user", ""))
        if g.user and g.user["admin"] and time.time() - session.get("admin_login_at", 0) > 8 * 3600:
            session.clear()
            g.user = None
        if not g.user:
            return (jsonify(error="로그인이 필요합니다."), 401) if request.path.startswith("/api/") else redirect("/login")

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

    @app.route("/login", methods=["GET", "POST"])
    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        admin_login = request.path == "/admin/login"
        use_names = name_login and not admin_login
        with team.connect() as connection:
            reviewers = [dict(row) for row in connection.execute("SELECT id,name FROM users WHERE active=1 AND admin=0 ORDER BY rowid")]
        def page(error="", status=200):
            return render_template("login.html", csrf=csrf(), error=error, use_names=use_names,
                                   admin_login=admin_login, reviewers=reviewers), status
        error = ""
        if request.method == "POST":
            with rate_lock:
                now = time.monotonic()
                while attempts and attempts[0] < now - 60:
                    attempts.popleft()
                if len(attempts) >= 12:
                    return page("시도가 많습니다. 잠시 후 다시 시도해주세요.", 429)
                attempts.append(now)
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

    @app.post("/api/logout")
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/")
    def home():
        return render_template("portal.html")

    @app.get("/review/<pack>")
    def review(pack):
        if pack not in stores:
            abort(404)
        # Reuse the local UI byte-for-byte; its script switches on /review/<id>.
        return (assets / "index.html").read_text(encoding="utf-8")

    @app.get("/style.css")
    @app.get("/portal.js")
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

    @app.get("/api/catalog")
    def get_catalog():
        entries = []
        for entry in catalog:
            store = stores.get(entry["id"])
            items = store.items() if store else []
            reviewed = [item for item in items if item["version"]]
            entries.append({key: value for key, value in entry.items() if key not in {"review_dir", "review_batches"}} | {
                "available": bool(store), "total": len(items), "reviewed": len(reviewed),
                "held": sum(item["review"].get("annotation_verdict") != "ok" for item in reviewed),
                "mine": sum(item["review"].get("reviewer") == g.user["name"] for item in reviewed),
                "batch_count": len(store.parts) if isinstance(store, BatchReviewStore) else int(bool(store))})
        return jsonify(datasets=entries, user={"id": g.user["id"], "name": g.user["name"], "admin": bool(g.user["admin"])}, csrf=csrf(), name_login=name_login)

    def current_store():
        pack = request.args.get("dataset", "")
        if pack not in stores:
            abort(404)
        return pack, stores[pack]

    def owner_map(pack):
        with team.connect() as connection:
            return {row["sample"]: row["user"] for row in connection.execute("SELECT sample,user FROM assignments WHERE pack=?", (pack,))}

    @app.get("/api/items")
    def items():
        pack, store = current_store()
        owners = owner_map(pack)
        result = store.items()
        for item in result:
            item["image_url"] = f"/api/packs/{pack}/images/{item['id']}"
            item["editable"] = bool(not g.user["admin"] and owners.get(item["id"]) == g.user["id"])
            item["assigned_elsewhere"] = item["id"] in owners and owners[item["id"]] != g.user["id"]
            item["coordinate_status"] = store.evidence[item["id"]].get("coordinate_status", "unconfirmed")
        return jsonify(items=result, csrf=csrf(), pack_hash=store.pack_hash, review_schema="simple-v2", team=True,
                       reviewer=g.user["name"], reviewer_id=g.user["id"], admin=bool(g.user["admin"]), training_approved=False)

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
        result = store.items()
        with team.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owners = {row["sample"]: row["user"] for row in connection.execute("SELECT sample,user FROM assignments WHERE pack=?", (pack,))}
            candidate = next((item for item in result if not item["version"] and owners.get(item["id"]) == g.user["id"]), None)
            if candidate is None:
                candidate = next((item for item in result if not item["version"] and item["id"] not in owners), None)
            if candidate is None:
                return jsonify(id=None)
            # Old open tabs know only the original IDs. Do not assign an ID
            # their cached item array cannot display; old saves remain valid.
            client_count = known_total if known_total is not None else len(store.parts[0][2].rows) if isinstance(store, BatchReviewStore) else len(store.rows)
            if candidate["id"] >= client_count:
                return jsonify(id=None, refresh_required=True)
            connection.execute("INSERT OR IGNORE INTO assignments VALUES (?,?,?)", (pack, candidate["id"], g.user["id"]))
        return jsonify(id=candidate["id"])

    @app.post("/api/review")
    def save():
        pack, store = current_store()
        body = request.get_json()
        if not isinstance(body, dict) or not isinstance(body.get("fields"), dict):
            raise ValueError("Expected review object")
        sample = body.get("id")
        if type(sample) is not int or not 0 <= sample < len(store.rows):
            raise ValueError("Unknown sample")
        owners = owner_map(pack)
        if g.user["admin"] or owners.get(sample) != g.user["id"]:
            abort(403)
        fields = {**body["fields"], "reviewer": g.user["name"], "review_schema": "simple-v2"}
        return jsonify(store.save(sample, body.get("version"), fields))

    @app.get("/api/packs/<pack>/images/<int:sample>")
    def image(pack, sample):
        if pack not in stores or not 0 <= sample < len(stores[pack].images):
            abort(404)
        return send_file(stores[pack].images[sample], conditional=False)

    @app.post("/api/users")
    def invite():
        if not g.user["admin"]:
            abort(403)
        body = request.get_json()
        return jsonify(team.create_user(body.get("name") if isinstance(body, dict) else None))

    @app.get("/api/users")
    def users():
        if not g.user["admin"]:
            abort(403)
        with team.connect() as connection:
            return jsonify(users=[dict(row) for row in connection.execute("SELECT id,name,admin,active FROM users")])

    @app.post("/api/users/<user_id>/disable")
    def disable(user_id):
        if not g.user["admin"] or user_id == g.user["id"]:
            abort(403)
        with team.connect() as connection:
            connection.execute("UPDATE users SET active=0 WHERE id=?", (user_id,))
            connection.execute("DELETE FROM assignments WHERE user=?", (user_id,))
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
            else:
                connection.execute("DELETE FROM assignments WHERE pack=? AND sample=? AND user=?", (pack, sample, g.user["id"]))
        return jsonify(ok=True)

    return app


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
    print(f"Authenticated review listening on loopback:{args.port}", flush=True)
    serve(app, host="127.0.0.1", port=args.port, threads=8, max_request_body_size=16384,
          channel_timeout=30, clear_untrusted_proxy_headers=True)


if __name__ == "__main__":
    main()
