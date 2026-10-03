"""Loopback-only human image review. Original CSV/images remain read-only."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import mimetypes
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


OPTIONS = {
    "domain": ["target_cctv", "non_target", "useful_real", "closeup_product", "kitchen", "web_misc", "unclear"],
    "annotation_verdict": ["ok", "problem", "unclear"],
    "review_schema": ["simple-v2"],
    "label_quality": ["good", "minor_issue", "bad", "ambiguous"],
    "person_cooccurrence": ["yes", "no", "unclear"],
    "small_or_distant_knife": ["yes", "no", "unclear"],
    "occlusion": ["none", "partial", "severe", "unclear"],
    "negative_knife_absence": ["yes", "no", "unclear"],
    "bbox_completeness": ["yes", "no", "unclear"],
    "exclude": ["no", "yes", "uncertain"],
}
EDITABLE = {*OPTIONS, "reviewer", "notes"}


class ConflictError(ValueError):
    pass


class ReviewStore:
    def __init__(self, review_dir: Path, *, database: Path | None = None):
        self.root = review_dir.resolve()
        csv_bytes = (self.root / "review.csv").read_bytes()
        evidence_bytes = (self.root / "image-evidence.jsonl").read_bytes()
        self.pack_hash = hashlib.sha256(csv_bytes + evidence_bytes).hexdigest()
        self.rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
        self.evidence = [json.loads(line) for line in evidence_bytes.decode().splitlines() if line]
        if not self.rows or len(self.rows) != len(self.evidence):
            raise ValueError("CSV and image evidence must be nonempty and aligned.")
        self.images = []
        for index, (row, item) in enumerate(zip(self.rows, self.evidence), 1):
            if item["sample_no"] != index or item["image_path"] != row["image_path"]:
                raise ValueError("Sample identity mismatch.")
            image = (self.root / item["image_file"]).resolve()
            if not image.is_relative_to(self.root) or not image.is_file():
                raise ValueError("Image missing or outside review pack.")
            if hashlib.sha256(image.read_bytes()).hexdigest() != item["image_sha256"]:
                raise ValueError("Image hash mismatch.")
            if item["width"] <= 0 or item["height"] <= 0:
                raise ValueError("Invalid image dimensions.")
            self.images.append(image)
        self.database = database or self.root / "human-review.sqlite3"
        if self.database.resolve() in {self.root / "review.csv", self.root / "image-evidence.jsonl", *self.images}:
            raise ValueError("Database cannot overwrite an input.")
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            previous = connection.execute("SELECT value FROM metadata WHERE key='pack_hash'").fetchone()
            if previous and previous[0] != self.pack_hash:
                raise ValueError("Database belongs to another review pack.")
            connection.execute("INSERT OR IGNORE INTO metadata VALUES ('pack_hash', ?)", (self.pack_hash,))
            connection.execute("CREATE TABLE IF NOT EXISTS reviews (sample INTEGER PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS history (sequence INTEGER PRIMARY KEY, sample INTEGER NOT NULL, payload TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def items(self):
        with self.connect() as connection:
            saved = {row[0]: (row[1], json.loads(row[2])) for row in connection.execute("SELECT sample,version,payload FROM reviews")}
        items = []
        for index, (row, evidence) in enumerate(zip(self.rows, self.evidence)):
            version, review = saved.get(index, (0, {}))
            items.append({"id": index, "name": Path(row["image_path"]).name,
                          "original_split": row["original_split"], "knife_count": evidence["knife_count"],
                          "width": evidence["width"], "height": evidence["height"],
                          "boxes": evidence["knife_boxes_xyxy_raw"], "version": version,
                          "review": review, "image_url": f"/api/images/{index}",
                          "coordinate_status": "unconfirmed"})
        return items

    def save(self, sample: int, version: int, fields: dict):
        if type(sample) is not int or not 0 <= sample < len(self.rows):
            raise ValueError("Unknown sample.")
        if type(version) is not int or version < 0 or not isinstance(fields, dict):
            raise ValueError("Invalid review request.")
        if set(fields) - EDITABLE:
            raise ValueError("Unsupported review field; source rights/coordinates are not image verdicts.")
        values = {key: fields.get(key, "") for key in EDITABLE}
        for key, value in values.items():
            if not isinstance(value, str) or len(value) > (2000 if key == "notes" else 120):
                raise ValueError("Invalid field value.")
            if key in OPTIONS and value and value not in OPTIONS[key]:
                raise ValueError(f"Invalid {key}.")
        simple = values["review_schema"] == "simple-v2"
        required = ("domain", "annotation_verdict", "reviewer") if simple else (
            "domain", "label_quality", "exclude", "reviewer", "bbox_completeness")
        for key in required:
            if not values[key].strip():
                raise ValueError("장면·라벨·판정·검수자·누락 여부를 선택해주세요.")
        if simple:
            verdict = values["annotation_verdict"]
            negative = not self.evidence[sample]["knife_count"]
            if verdict == "problem" and not values["notes"].strip():
                raise ValueError("문제가 있는 경우 한 줄 메모를 남겨주세요.")
            # 'Normal' explicitly means all visible knives have correct boxes,
            # or that no knife is present in an annotation-negative sample.
            values["label_quality"] = {"ok": "good", "problem": "bad", "unclear": "ambiguous"}[verdict]
            values["bbox_completeness"] = "yes" if verdict == "ok" else "unclear"
            values["exclude"] = "no" if verdict == "ok" else "uncertain"
            if negative:
                values["negative_knife_absence"] = {"ok": "yes", "problem": "no", "unclear": "unclear"}[verdict]
                if verdict == "problem":
                    values["bbox_completeness"] = "no"
            else:
                values["negative_knife_absence"] = ""
        if not simple and not self.evidence[sample]["knife_count"] and not values["negative_knife_absence"]:
            raise ValueError("음성 후보는 실제 칼 부재 여부도 확인해주세요.")
        if not simple and values["exclude"] != "no" and not values["notes"].strip():
            raise ValueError("제외·보류 이유를 한 줄 남겨주세요.")
        values["reviewer"] = values["reviewer"].strip()
        values["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(values, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            previous = connection.execute("SELECT version FROM reviews WHERE sample=?", (sample,)).fetchone()
            if (previous[0] if previous else 0) != version:
                raise ConflictError("다른 탭에서 수정됐습니다. 새로고침 후 다시 확인해주세요.")
            connection.execute("INSERT OR REPLACE INTO reviews VALUES (?,?,?)", (sample, version + 1, payload))
            connection.execute("INSERT INTO history(sample,payload) VALUES (?,?)", (sample, payload))
        return {"version": version + 1, "review": values}

    def export_csv(self):
        stream = io.StringIO(newline="")
        columns = list(self.rows[0])
        for key in sorted(EDITABLE) + ["reviewed_at", "review_version"]:
            if key not in columns:
                columns.append(key)
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row, item in zip(self.rows, self.items()):
            record = {**row, **item["review"], "review_version": item["version"]}
            # Keep the DB exact, but neutralize spreadsheet formula execution on export.
            writer.writerow({key: "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n"))
                             else value for key, value in record.items()})
        return ("\ufeff" + stream.getvalue()).encode("utf-8")


def make_handler(store: ReviewStore, token: str):
    assets = Path(__file__).parent / "web_review"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Never log review content or personal identifiers.

        def respond(self, status, data, mime="application/json; charset=utf-8", *, download=False):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="human-review.csv"')
            self.end_headers()
            self.wfile.write(data)

        def allowed_host(self):
            port = self.server.server_port
            return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def do_GET(self):
            if not self.allowed_host():
                return self.respond(403, {"error": "Loopback host required."})
            path = urlsplit(self.path).path
            if path in {"/", "/app.js", "/style.css"}:
                file = assets / ({"/": "index.html"}.get(path, path[1:]))
                return self.respond(200, file.read_bytes(), mimetypes.guess_type(file)[0] + "; charset=utf-8")
            if path == "/api/items":
                return self.respond(200, {"items": store.items(), "csrf": token, "options": OPTIONS,
                                          "pack_hash": store.pack_hash, "review_schema": "simple-v2", "training_approved": False})
            if path == "/api/export":
                return self.respond(200, store.export_csv(), "text/csv; charset=utf-8", download=True)
            if path.startswith("/api/images/"):
                try:
                    index = int(path.rsplit("/", 1)[1])
                    if not 0 <= index < len(store.images):
                        raise ValueError()
                    image = store.images[index]
                    return self.respond(200, image.read_bytes(), mimetypes.guess_type(image)[0] or "application/octet-stream")
                except ValueError:
                    return self.respond(404, {"error": "Unknown image."})
            self.respond(404, {"error": "Not found."})

        def do_POST(self):
            port = self.server.server_port
            origin = self.headers.get("Origin")
            if (not self.allowed_host() or self.headers.get("X-Review-Token") != token
                    or origin not in {None, f"http://127.0.0.1:{port}", f"http://localhost:{port}"}):
                return self.respond(403, {"error": "Invalid local review request."})
            if self.path != "/api/review":
                return self.respond(404, {"error": "Not found."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Request too large or empty.")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Expected an object.")
                result = store.save(body.get("id"), body.get("version"), body.get("fields"))
                self.respond(200, result)
            except ConflictError as exc:
                self.respond(409, {"error": str(exc)})
            except (ValueError, TypeError) as exc:
                self.respond(400, {"error": str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--database", type=Path, help="Optional separate database, e.g. for UI testing.")
    args = parser.parse_args()
    store = ReviewStore(args.review_dir, database=args.database)
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(store, secrets.token_urlsafe(32))) as server:
        print(f"Review UI: http://127.0.0.1:{server.server_port} (loopback only)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
