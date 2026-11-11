"""Plan complete frame review and materialize individual private review packs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path

from prepare_team_review import write_pack


def read_frames(path):
    raw = path.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    hashes = set()
    paths = set()
    for row in rows:
        digest = row["sha256"]
        image = row["image_path"]
        if digest in hashes or image in paths:
            raise ValueError("Duplicate frame in source manifest")
        hashes.add(digest)
        paths.add(image)
        if (row["classification"] not in {"knife_candidate", "no_detection_candidate"}
                or bool(row["boxes"]) != (row["classification"] == "knife_candidate")
                or row["human_review"] != "pending" or row["training_approved"] is not False):
            raise ValueError("Invalid frame review input")
    return rows, hashlib.sha256(raw).hexdigest()


def spread_sources(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["source_id"]].append(row)
    active = deque(deque(sorted(groups[key], key=lambda row: row["timestamp_s"])) for key in sorted(groups))
    ordered = []
    while active:
        group = active.popleft()
        ordered.append(group.popleft())
        if group:
            active.append(group)
    return ordered


def plan(manifest, output):
    rows, digest = read_frames(manifest)
    positives = spread_sources(row for row in rows if row["boxes"])
    misses = spread_sources(row for row in rows if not row["boxes"])
    pilot = [item for pair in zip(positives[:50], misses[:50]) for item in pair]
    if len(pilot) != 100:
        raise ValueError("Pilot needs at least 50 frames of each classification")
    positives, misses = iter(positives[50:]), iter(misses[50:])
    remaining = len(rows) - 100
    positive_remaining = sum(bool(row["boxes"]) for row in rows) - 50
    ordered = pilot + [
        next(positives) if (index + 1) * positive_remaining // remaining > index * positive_remaining // remaining
        else next(misses)
        for index in range(remaining)
    ]
    if len(ordered) != len(rows) or len({row["sha256"] for row in ordered}) != len(rows):
        raise AssertionError("Frame coverage mismatch")
    output.mkdir(parents=True, exist_ok=False)
    batches = Counter()
    with (output / "queue.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
        for index, row in enumerate(ordered):
            batch = 1 if index < 100 else 2 + (index - 100) // 250
            batches[batch] += 1
            record = {**row, "batch": batch, "position": batches[batch]}
            stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {
        "source_manifest_sha256": digest, "frames": len(rows),
        "source_videos": len({row["source_id"] for row in rows}),
        "classifications": dict(Counter(row["classification"] for row in rows)),
        "batch_sizes": dict(batches), "human_review": "pending", "training_approved": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Queued {len(rows)} frames in {len(batches)} batches")


def materialize(frame_root, queue, batch, output):
    summary = json.loads((queue / "summary.json").read_text(encoding="utf-8"))
    expected = summary["batch_sizes"].get(str(batch))
    if expected is None:
        raise ValueError("Unknown batch")
    with (queue / "queue.jsonl").open(encoding="utf-8") as stream:
        rows = [row for line in stream if (row := json.loads(line))["batch"] == batch]
    if [row["position"] for row in rows] != list(range(1, expected + 1)):
        raise ValueError("Invalid batch order or size")
    samples = []
    frame_root = frame_root.resolve()
    for row in rows:
        path = (frame_root / row["image_path"]).resolve()
        if not path.is_relative_to(frame_root):
            raise ValueError("Frame path escapes the input root")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise ValueError("Frame hash mismatch")
        samples.append({
            "bytes": raw, "image_path": row["image_path"], "original_split": "video-review",
            "boxes": [box["xyxy"] for box in row["boxes"]],
            "box_proposals": row["boxes"], "source_id": row["source_id"],
            "source_video": row["source_video"], "timestamp_s": row["timestamp_s"],
            "classification": row["classification"],
            "coordinate_status": "Model prediction; human review pending",
        })
    write_pack(f"video-{batch:04d}", samples, {
        "source_manifest_sha256": summary["source_manifest_sha256"],
        "batch": batch, "review_schema": "video-box-v1",
    }, root=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    planner = commands.add_parser("plan")
    planner.add_argument("manifest", type=Path)
    planner.add_argument("output", type=Path)
    pack = commands.add_parser("pack")
    pack.add_argument("frame_root", type=Path)
    pack.add_argument("queue", type=Path)
    pack.add_argument("batch", type=int)
    pack.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        plan(args.manifest, args.output)
    else:
        materialize(args.frame_root, args.queue, args.batch, args.output)


if __name__ == "__main__":
    main()
