"""Render short, muted review clips from the original videos on the review host."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from pathlib import Path
import subprocess


def read_evidence(pack):
    path = Path(pack["review_dir"]) / "image-evidence.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def preview_windows(start, end, timestamps):
    if end - start <= 8:
        return [(start, end - start)]
    windows = []
    for stamp in sorted(set(timestamps)):
        window = (max(start, stamp - 0.75), min(end, stamp + 0.75))
        if windows and window[0] <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], window[1]))
        else:
            windows.append(window)
    return [(left, right - left) for left, right in windows]


def render(ffmpeg, source, target, windows):
    if target.is_file() and target.stat().st_size:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".partial.mp4")
    command = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    for start, duration in windows:
        command.extend(["-threads", "1", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(source)])
    size = ("fps=12,scale=480:270:force_original_aspect_ratio=decrease,"
            "pad=480:270:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,setpts=PTS-STARTPTS")
    filters = [f"[{index}:v:0]{size}[v{index}]" for index in range(len(windows))]
    joined = "".join(f"[v{index}]" for index in range(len(windows)))
    filters.append(f"{joined}concat=n={len(windows)}:v=1:a=0[v]")
    command.extend(["-filter_complex_threads", "1", "-filter_complex", ";".join(filters),
                    "-map", "[v]", "-an", "-c:v", "libx264", "-threads", "1",
                    "-preset", "veryfast", "-crf", "27", "-movflags", "+faststart", str(temporary)])
    try:
        result = subprocess.run(command, capture_output=True, timeout=120)
        if result.returncode or not temporary.is_file() or temporary.stat().st_size < 1024:
            raise ValueError(f"Could not render {target.parent.name}/{target.stem}")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def prepare(catalog, sources, output, ffmpeg, workers):
    entries = {entry["id"]: entry for entry in json.loads(catalog.read_text(encoding="utf-8"))}
    sources = sources.resolve()
    output.mkdir(parents=True, exist_ok=True)
    tasks = []
    for entry in entries.values():
        if "scene_pack" not in entry:
            continue
        pack = entries[entry["scene_pack"]]
        scenes = read_evidence(pack)
        frames = [[] for _ in scenes]
        for frame in read_evidence(entry):
            scene = scenes[frame["scene_sample"]]
            if frame["source_video"] != scene["source_video"]:
                raise ValueError("Scene and review frame source mismatch.")
            frames[frame["scene_sample"]].append(frame["timestamp_s"])
        for sample, (scene, stamps) in enumerate(zip(scenes, frames)):
            start, end = scene["scene_start_s"], scene["scene_end_s"]
            stamps = [scene["timestamp_s"], *stamps]
            if (len(stamps) < 2 or not all(math.isfinite(stamp) and start <= stamp <= end for stamp in stamps)
                    or not math.isfinite(start) or not math.isfinite(end) or end <= start):
                raise ValueError("Invalid scene timestamps.")
            source = (sources / scene["source_video"]).resolve()
            if not source.is_relative_to(sources) or not source.is_file():
                raise ValueError("Missing source video inside the intake folder.")
            tasks.append((source, output / pack["id"] / f"{sample}.mp4", preview_windows(start, end, stamps)))
    if not tasks:
        raise ValueError("No linked scene review packs.")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(render, ffmpeg, source, target, windows) for source, target, windows in tasks]
        failures = []
        for count, future in enumerate(as_completed(futures), 1):
            if error := future.exception():
                failures.append(str(error))
            if count % 100 == 0 or count == len(tasks):
                print(json.dumps({"processed": count, "total": len(tasks), "failed": len(failures)}), flush=True)
    if failures:
        raise ValueError("; ".join(failures[:12]))
    print(json.dumps({"ready": len(tasks), "bytes": sum(target.stat().st_size for _, target, _ in tasks)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ffmpeg", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    prepare(args.catalog, args.source_root, args.output, args.ffmpeg, args.workers)
