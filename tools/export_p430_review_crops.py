"""Export reviewed P430 frames as centered half-width, half-height YOLO crops."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from PIL import Image

from edge_threat_response.dataset.review_web import VIDEO_REVIEW_SCHEMA, _check_boxes, center_review_crop


def yolo_lines(boxes, crop):
    left, top, right, bottom = crop
    width, height = right - left, bottom - top
    for x1, y1, x2, y2 in boxes:
        x1, x2 = max(left, x1), min(right, x2)
        y1, y2 = max(top, y1), min(bottom, y2)
        if x2 > x1 and y2 > y1:
            yield "0 " + " ".join(f"{value:.10f}" for value in (
                ((x1 + x2) / 2 - left) / width, ((y1 + y2) / 2 - top) / height,
                (x2 - x1) / width, (y2 - y1) / height,
            )) + "\n"


def export_session(root, output, audit):
    session = root.name
    pack = root / "review"
    summary = json.loads((pack / "summary.json").read_text(encoding="utf-8"))
    if summary.get("capture_session_id") != session or not session.startswith("p430-"):
        raise ValueError("Expected a P430 capture session with a matching pack.")
    raw_evidence = (pack / "image-evidence.jsonl").read_bytes()
    evidence = [json.loads(line) for line in raw_evidence.splitlines() if line]
    pack_hash = hashlib.sha256((pack / "review.csv").read_bytes() + raw_evidence).hexdigest()
    db = (pack / "human-review.sqlite3").resolve().as_uri()
    with closing(sqlite3.connect(db + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        metadata = dict(conn.execute("SELECT key,value FROM metadata"))
        if metadata.get("pack_hash") != pack_hash or metadata.get("review_schema") != VIDEO_REVIEW_SCHEMA:
            raise ValueError("Review database and pack do not match.")
        reviews = list(conn.execute("SELECT sample,version,payload FROM reviews ORDER BY sample"))

    counts = Counter(prepared=len(evidence), reviewed=len(reviews), pending=len(evidence) - len(reviews))
    for sample, version, payload in reviews:
        if not 0 <= sample < len(evidence) or evidence[sample]["sample_no"] != sample + 1:
            raise ValueError("Review sample does not match evidence.")
        review = json.loads(payload)
        domain, presence = review["domain"], review["knife_presence"]
        if domain != "target_cctv" or presence not in {"yes", "no"}:
            counts["excluded" if domain == "non_target" else "uncertain"] += 1
            continue
        item = evidence[sample]
        size = item["width"], item["height"]
        crop = center_review_crop(*size)
        boxes = review["reviewed_boxes"]
        _check_boxes(boxes, *size)
        if bool(boxes) != (presence == "yes"):
            raise ValueError("Saved review has inconsistent boxes.")
        labels = list(yolo_lines(boxes, crop))
        if presence == "yes" and not labels:
            counts["positive_outside_crop"] += 1
            continue
        source = (pack / item["image_file"]).resolve()
        if not source.is_relative_to(pack.resolve()):
            raise ValueError("Frame outside source pack.")
        source_bytes = source.read_bytes()
        source_hash = hashlib.sha256(source_bytes).hexdigest()
        if source_hash != item["image_sha256"]:
            raise ValueError("Frame hash mismatch.")
        stem = f"{session}-{sample:06d}"
        with Image.open(source) as image:
            if image.size != size:
                raise ValueError("Source size mismatch.")
            image.crop(crop).convert("RGB").save(output / "images" / f"{stem}.jpg", quality=95)
        (output / "labels" / f"{stem}.txt").write_text("".join(labels), encoding="ascii")
        audit.write(json.dumps({
            "image": f"images/{stem}.jpg", "session": session, "sample": sample, "review_version": version,
            "source_sha256": source_hash, "crop_xyxy": crop, "knife_boxes": len(labels),
            "review_scope": review.get("review_scope", "legacy-unspecified"),
        }) + "\n")
        counts["positive" if labels else "negative"] += 1
        counts["boxes"] += len(labels)
        counts["out_of_crop_boxes"] += len(boxes) - len(labels)
    return {"session": session, "pack_sha256": pack_hash, **counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = [path.resolve() for path in args.sessions]
    if len({path.name for path in paths}) != len(paths):
        parser.error("Session names must be unique.")
    output = args.output.resolve()
    if output.exists() or any(output.is_relative_to(path) for path in paths):
        parser.error("Use a new output folder outside the original capture sessions.")
    started = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    with TemporaryDirectory(prefix="p430-crop-", dir=output.parent) as temporary:
        stage = Path(temporary) / "dataset"
        (stage / "images").mkdir(parents=True)
        (stage / "labels").mkdir()
        with (stage / "manifest.jsonl").open("w", encoding="utf-8") as audit:
            sessions = [export_session(path, stage, audit) for path in paths]
        report = {"observed_from_kst": started, "crop": "central 50% width and height", "sessions": sessions}
        (stage / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        stage.rename(output)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
