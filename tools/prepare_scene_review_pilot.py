"""Build paired scene and knife review packs on PC13 without publishing them."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from prepare_team_review import write_pack
from prepare_video_frame_review import read_frames


def select_segments(result_dir, rows):
    candidates = defaultdict(list)
    for path in sorted((result_dir / "by-video").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        offset = 0
        for segment in data["segments"]:
            predictions = data["frames"][offset:offset + segment["frames"]]
            offset += segment["frames"]
            if len(predictions) >= 4:
                frames = [rows[prediction["image_path"]] for prediction in predictions]
                if (any(frame["source_id"] != data["source_id"] for frame in frames)
                        or [frame["timestamp_s"] for frame in frames] != [p["timestamp_s"] for p in predictions]):
                    raise ValueError("Scene and frame provenance mismatch")
                candidates[segment["class"]].append(frames)
        if offset != len(data["frames"]):
            raise ValueError("Scene and frame counts differ")

    selected, used_sources = [], set()
    for label, quota in (("cctv", 25), ("hold", 20), ("exclude", 5)):
        order = sorted(candidates[label], key=lambda frames: hashlib.sha256(
            frames[0]["image_path"].encode()).digest())
        picked = []
        for frames in order:
            source = frames[0]["source_id"]
            if source not in used_sources:
                picked.append((label, frames))
                used_sources.add(source)
                if len(picked) == quota:
                    break
        if len(picked) != quota:
            raise ValueError(f"Not enough independent pilot candidates for {label}")
        selected.extend(picked)
    return selected


def sample(frame_root, row, boxes):
    path = (frame_root / row["image_path"]).resolve()
    if not path.is_relative_to(frame_root):
        raise ValueError("Frame path escapes input root")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != row["sha256"]:
        raise ValueError("Frame hash mismatch")
    return {"bytes": content, "image_path": row["image_path"], "original_split": "video-review",
            "boxes": boxes, "source_id": row["source_id"], "source_video": row["source_video"],
            "timestamp_s": row["timestamp_s"]}


def build(frame_root, result_dir, output):
    frame_root = frame_root.resolve()
    output = output.resolve()
    rows, digest = read_frames(frame_root / "frames.jsonl")
    config = json.loads((result_dir / "config.json").read_text(encoding="utf-8"))
    progress = json.loads((result_dir / "progress.json").read_text(encoding="utf-8"))
    if config["input_sha256"] != digest or progress["status"] != "completed":
        raise ValueError("Use the completed scene classification for these frames")
    scenes, frames = [], []
    labels = Counter()
    for index, (label, group) in enumerate(select_segments(result_dir, {row["image_path"]: row for row in rows})):
        labels[label] += 1
        interior = group[1:-1]
        proposed = [row for row in interior if row["boxes"]]
        middle = (proposed or interior)[len(proposed or interior) // 2]
        alternatives = [row for row in interior if row is not middle]
        representative = alternatives[len(alternatives) // 2]
        scene = sample(frame_root, representative, [])
        scene.update(scene_start_s=group[0]["timestamp_s"], scene_end_s=group[-1]["timestamp_s"],
                     automatic_scene_class=label)
        scenes.append(scene)
        for row in (group[0], middle, group[-1]):
            frame = sample(frame_root, row, [box["xyxy"] for box in row["boxes"]])
            frame.update(scene_sample=index, box_proposals=row["boxes"],
                         coordinate_status="Model prediction; human review pending")
            frames.append(frame)
    identities = {row["image_path"] for row in scenes + frames}
    if len(identities) != len(scenes) + len(frames) or len(identities) != 200:
        raise ValueError("Pilot frames must be unique")
    output.mkdir(parents=True, exist_ok=False)
    origin = {"input_manifest_sha256": digest, "scene_classifications": dict(labels)}
    write_pack("video-scenes", scenes, {**origin, "review_schema": "video-scene-v1"}, root=output)
    write_pack("video-boxes", frames, {**origin, "review_schema": "video-box-v1"}, root=output)
    catalog = [
        {"id": "video-scenes", "name": "영상 구간 검수", "role": "CCTV 구간",
         "note": "대표 화면과 시작·끝 시각을 확인합니다.", "review_schema": "video-scene-v1",
         "review_dir": str(output / "video-scenes")},
        {"id": "video-boxes", "name": "영상 칼 검수", "role": "승인된 CCTV 프레임",
         "note": "칼 유무와 박스를 확인합니다.", "review_schema": "video-box-v1",
         "scene_pack": "video-scenes", "review_dir": str(output / "video-boxes")},
    ]
    (output / "catalog-fragment.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"scenes": len(scenes), "frames": len(frames), "scene_labels": dict(labels)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("frame_root", "result_dir", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    build(args.frame_root, args.result_dir, args.output)
