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

from edge_threat_response.dataset.review_web import (
    CENTER_REVIEW_SCOPE, VIDEO_REVIEW_SCHEMA, _check_boxes, center_review_crop,
)


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


def read_review_pack(pack):
    raw_evidence = (pack / "image-evidence.jsonl").read_bytes()
    evidence = [json.loads(line) for line in raw_evidence.splitlines() if line]
    pack_hash = hashlib.sha256((pack / "review.csv").read_bytes() + raw_evidence).hexdigest()
    db = (pack / "human-review.sqlite3").resolve().as_uri()
    with closing(sqlite3.connect(db + "?mode=ro", uri=True)) as conn:
        conn.execute("BEGIN")
        if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Review database failed its integrity check.")
        metadata = dict(conn.execute("SELECT key,value FROM metadata"))
        if metadata.get("pack_hash") != pack_hash or metadata.get("review_schema") != VIDEO_REVIEW_SCHEMA:
            raise ValueError("Review database and pack do not match.")
        reviews = {sample: (version, json.loads(payload)) for sample, version, payload in
                   conn.execute("SELECT sample,version,payload FROM reviews ORDER BY sample")}
    if any(row["sample_no"] != i + 1 for i, row in enumerate(evidence)) or any(
        not 0 <= sample < len(evidence) or version < 1 for sample, (version, _) in reviews.items()
    ):
        raise ValueError("Review sample does not match evidence.")
    return evidence, pack_hash, reviews


def load_overrides(roots, sessions):
    overrides, records = {}, []
    for root in roots:
        evidence, pack_hash, reviews = read_review_pack(root / "review")
        if not evidence or len(reviews) != len(evidence):
            raise ValueError("Every spot-check sample must have a saved verdict.")
        for sample, (version, review) in reviews.items():
            item = evidence[sample]
            session, source_sample = item["source_id"], item["source_review_id"]
            if session not in sessions or type(source_sample) is not int or source_sample < 0:
                raise ValueError("Spot-check sample does not identify an input session and frame.")
            key = session, source_sample
            if key in overrides:
                raise ValueError("More than one spot-check result for the same source frame.")
            if (review.get("review_scope") != CENTER_REVIEW_SCOPE
                    or item["source_image_sha256"] != item["image_sha256"]):
                raise ValueError("Spot-check image identity or center crop scope is invalid.")
            overrides[key] = ({
                "pack": root.name, "pack_sha256": pack_hash, "sample": sample, "review_version": version,
                "source_review_version": item["source_review_version"], "source_sha256": item["source_image_sha256"],
            }, review)
        records.append({"pack": root.name, "pack_sha256": pack_hash, "reviewed": len(reviews)})
    return overrides, records


def export_session(root, output, audit, overrides, resolved, require_complete):
    session = root.name
    pack = root / "review"
    summary = json.loads((pack / "summary.json").read_text(encoding="utf-8"))
    if summary.get("capture_session_id") != session or not session.startswith("p430-"):
        raise ValueError("Expected a P430 capture session with a matching pack.")
    evidence, pack_hash, reviews = read_review_pack(pack)
    if require_complete and (not evidence or len(reviews) != len(evidence)):
        raise ValueError("Every original sample must have a saved verdict.")

    counts = Counter(prepared=len(evidence), reviewed=len(reviews), pending=len(evidence) - len(reviews))
    for sample, (version, review) in reviews.items():
        item = evidence[sample]
        override = overrides.pop((session, sample), None)
        if override:
            resolution, reviewed_again = override
            if resolution["source_review_version"] != version or resolution["source_sha256"] != item["image_sha256"]:
                raise ValueError(f"Spot-check source frame or saved version changed: {session}/{sample}")
            resolved.write(json.dumps({
                "session": session, "source_sample": sample, "override": resolution,
                "previous_knife_presence": review["knife_presence"], "domain": reviewed_again["domain"],
                "knife_presence": reviewed_again["knife_presence"],
                "knife_boxes": len(reviewed_again["reviewed_boxes"]),
            }) + "\n")
            review = reviewed_again
            counts["overrides_applied"] += 1
        domain, presence = review["domain"], review["knife_presence"]
        if domain != "target_cctv" or presence not in {"yes", "no"}:
            counts["excluded" if domain == "non_target" else "uncertain"] += 1
            if override:
                counts["overrides_held_out"] += 1
            continue
        size = item["width"], item["height"]
        crop = center_review_crop(*size)
        boxes = review["reviewed_boxes"]
        _check_boxes(boxes, *size, crop=crop if review.get("review_scope") == CENTER_REVIEW_SCOPE else None)
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
        output_image = output / "images" / f"{stem}.jpg"
        output_label = output / "labels" / f"{stem}.txt"
        with Image.open(source) as image:
            if image.size != size:
                raise ValueError("Source size mismatch.")
            image.crop(crop).convert("RGB").save(output_image, quality=95)
        output_label.write_text("".join(labels), encoding="ascii")
        scope = review.get("review_scope", "legacy-unspecified")
        audit.write(json.dumps({
            "image": f"images/{stem}.jpg", "session": session, "sample": sample, "review_version": version,
            "source_sha256": source_hash, "crop_xyxy": crop, "knife_boxes": len(labels),
            "source_video_sha256": item["source_video_sha256"], "timestamp_s": item["timestamp_s"],
            "image_sha256": hashlib.sha256(output_image.read_bytes()).hexdigest(),
            "label_sha256": hashlib.sha256(output_label.read_bytes()).hexdigest(),
            "review_scope": scope, **({"override": override[0]} if override else {}),
        }) + "\n")
        counts["positive" if labels else "negative"] += 1
        counts["boxes"] += len(labels)
        counts[scope] += 1
        counts["out_of_crop_boxes"] += len(boxes) - len(labels)
    return {"session": session, "pack_sha256": pack_hash, **counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", nargs="+", type=Path, required=True)
    parser.add_argument("--review-overrides", nargs="+", type=Path, default=[])
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = [path.resolve() for path in args.sessions]
    override_paths = [path.resolve() for path in args.review_overrides]
    if len({path.name for path in paths}) != len(paths):
        parser.error("Session names must be unique.")
    output = args.output.resolve()
    if output.exists() or any(output.is_relative_to(path) for path in paths + override_paths):
        parser.error("Use a new output folder outside the input packs.")
    overrides, override_packs = load_overrides(override_paths, {path.name for path in paths})
    started = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    with TemporaryDirectory(prefix="p430-crop-", dir=output.parent) as temporary:
        stage = Path(temporary) / "dataset"
        (stage / "images").mkdir(parents=True)
        (stage / "labels").mkdir()
        with ((stage / "manifest.jsonl").open("w", encoding="utf-8") as audit,
              (stage / "overrides.jsonl").open("w", encoding="utf-8") as resolved):
            sessions = [export_session(path, stage, audit, overrides, resolved, args.require_complete)
                        for path in paths]
        if overrides:
            raise ValueError("Spot-check result did not match a saved source review.")
        report = {"observed_from_kst": started, "crop": "central 50% width and height",
                  "sessions": sessions, "override_packs": override_packs, "split_assigned": False}
        (stage / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        stage.rename(output)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
