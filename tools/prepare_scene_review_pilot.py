"""Build paired scene and knife review packs on PC13 without publishing them."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path

from prepare_team_review import write_pack
from prepare_video_frame_review import read_frames


def candidate_segments(result_dir, rows):
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

    return candidates


def select_segments(candidates):
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


def select_all_videos(candidates, expected_sources):
    by_source = defaultdict(list)
    order = {"cctv": 0, "hold": 1, "exclude": 2}
    for label, segments in candidates.items():
        for frames in segments:
            by_source[frames[0]["source_id"]].append((label, frames))
    if set(by_source) != expected_sources:
        raise ValueError("Some videos lack an eligible representative scene")

    def fingerprint(scene):
        return hashlib.sha256(scene[1][0]["image_path"].encode()).digest()

    def rank(scene):
        label, frames = scene
        hits = sum(bool(frame["boxes"]) for frame in frames)
        return (order[label], not 0 < hits < len(frames), not hits, fingerprint(scene))

    selected, remaining = [], defaultdict(lambda: defaultdict(list))
    for source in sorted(by_source, key=lambda key: hashlib.sha256(key.encode()).digest()):
        first, *rest = sorted(by_source[source], key=rank)
        selected.append(first)
        for scene in rest:
            remaining[scene[0]][source].append(scene)
    initial = Counter(label for label, _ in selected)
    extra = []
    for label, target in (("cctv", 1000), ("hold", 520), ("exclude", 80)):
        queues = deque(deque(scenes) for scenes in remaining[label].values())
        for _ in range(target - initial[label]):
            if not queues:
                raise ValueError(f"Insufficient scenes for {label}")
            queue = queues.popleft()
            extra.append(queue.popleft())
            if queue:
                queues.append(queue)
    selected.extend(sorted(extra, key=fingerprint))
    if len(selected) != 1600:
        raise ValueError("Full review must contain exactly 1600 selected scenes")
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


def write_pair(frame_root, selected, output, digest, batch=""):
    scenes, frames = [], []
    labels = Counter()
    for index, (label, group) in enumerate(selected):
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
    if len(identities) != len(selected) * 4:
        raise ValueError("Review frames must be unique")
    origin = {"input_manifest_sha256": digest, "scene_classifications": dict(labels)}
    scene_id = f"video-scenes{batch}"
    frame_id = f"video-boxes{batch}"
    write_pack(scene_id, scenes, {**origin, "review_schema": "video-scene-v1"}, root=output)
    write_pack(frame_id, frames, {**origin, "review_schema": "video-box-v1"}, root=output)
    return [
        {"id": scene_id, "name": f"영상 구간 검수{batch}", "role": "CCTV 구간",
         "note": "대표 화면과 시작·끝 시각을 확인합니다.", "review_schema": "video-scene-v1",
         "review_dir": str(output / scene_id)},
        {"id": frame_id, "name": f"영상 칼 검수{batch}", "role": "승인된 CCTV 프레임",
         "note": "칼 유무와 박스를 확인합니다.", "review_schema": "video-box-v1",
         "scene_pack": scene_id, "review_dir": str(output / frame_id)},
    ]


def build(frame_root, result_dir, output, *, all_videos=False):
    frame_root, output = frame_root.resolve(), output.resolve()
    rows, digest = read_frames(frame_root / "frames.jsonl")
    config = json.loads((result_dir / "config.json").read_text(encoding="utf-8"))
    progress = json.loads((result_dir / "progress.json").read_text(encoding="utf-8"))
    if config["input_sha256"] != digest or progress["status"] != "completed":
        raise ValueError("Use the completed scene classification for these frames")
    candidates = candidate_segments(result_dir, {row["image_path"]: row for row in rows})
    sources = {row["source_id"] for row in rows}
    selected = select_all_videos(candidates, sources) if all_videos else select_segments(candidates)
    output.mkdir(parents=True, exist_ok=False)
    catalog = []
    if all_videos:
        for offset in range(0, len(selected), 100):
            catalog.extend(write_pair(frame_root, selected[offset:offset+100], output, digest,
                                      batch=f"-{offset//100+1:02d}"))
    else:
        catalog = write_pair(frame_root, selected, output, digest)
    (output / "catalog-fragment.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"scenes": len(selected), "frames": len(selected)*3, "batches": len(catalog)//2,
               "source_videos": len({frames[0]["source_id"] for _, frames in selected}),
               "scene_labels": dict(Counter(label for label, _ in selected)),
               "input_manifest_sha256": digest}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("frame_root", "result_dir", "output"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--all-videos", action="store_true")
    args = parser.parse_args()
    build(args.frame_root, args.result_dir, args.output, all_videos=args.all_videos)
