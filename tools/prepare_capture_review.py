"""Sample one local CCTV recording and stage CUDA box proposals for human review."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from prepare_team_review import write_pack

from edge_threat_response.detection_evaluation import iou
from edge_threat_response.domain import BBox
from edge_threat_response.training import _sha256_file


def extract(video, ffmpeg, folder):
    # Select the first decoded frame in each second, then retain its actual PTS.
    select = "select='isnan(prev_selected_t)+gt(floor(t),floor(prev_selected_t))',showinfo"
    result = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-nostdin", "-i", str(video), "-map", "0:v:0",
         "-vf", select, "-fps_mode", "passthrough", "-q:v", "2", "-start_number", "0",
         str(folder / "%06d.jpg")],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    stamps = [float(value) for value in re.findall(
        r"Parsed_showinfo_\d+[^\r\n]*?\bn:\s*\d+[^\r\n]*?\bpts_time:([-+\d.eE]+)", result.stderr)]
    images = sorted(folder.glob("*.jpg"))
    if not stamps or len(images) != len(stamps) or any(a >= b for a, b in zip(stamps, stamps[1:])):
        raise ValueError("Extracted frames and source timestamps do not align.")
    return list(zip(images, stamps, strict=True))


def infer(model, image):
    from PIL import Image

    with Image.open(image) as frame:
        width, height = frame.size
        tile_w, tile_h = round(width * .57), round(height * .70)
        offsets = [(0, 0), (width-tile_w, 0), (0, height-tile_h), (width-tile_w, height-tile_h)]
        tiles = [frame.crop((x, y, x+tile_w, y+tile_h)) for x, y in offsets]
    full = model.predict(str(image), device=0, imgsz=960, conf=.10, max_det=8, verbose=False)
    tiled = model.predict(tiles, device=0, imgsz=640, conf=.10, max_det=8, verbose=False)
    pool = []
    for prediction, (x, y), view in zip(
        [*full, *tiled], [(0, 0), *offsets], ["full", "tile-1", "tile-2", "tile-3", "tile-4"], strict=True
    ):
        for left, top, right, bottom, score, _ in prediction.boxes.data.detach().cpu().tolist():
            coords = [round(v, 2) for v in (left+x, top+y, right+x, bottom+y)]
            if not 0 <= coords[0] < coords[2] <= width or not 0 <= coords[1] < coords[3] <= height:
                continue
            pool.append((score, coords, view))
    kept, boxes = [], []
    for score, coords, view in sorted(pool, key=lambda item: -item[0]):
        box = BBox(*coords)
        if all(iou(box, prior) <= .55 for prior in kept):
            kept.append(box)
            boxes.append({"xyxy": coords, "confidence": round(score, 5), "view": view})
    return boxes[:8]


def prepare(video, ffmpeg, weights, output, session_id, pack_id):
    import torch
    from ultralytics import YOLO, __version__ as ultralytics_version

    if output.exists():
        raise ValueError("Choose a new output directory so existing reviews are preserved.")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required.")
    model = YOLO(str(weights))
    if model.names != {0: "knife"}:
        raise ValueError("Expected a knife-only detector.")
    source_hash = _sha256_file(video)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".capture-review-", dir=output.parent) as staging:
        scratch = Path(staging)
        sampled = extract(video, ffmpeg, scratch)
        counts = Counter(sampled=len(sampled))
        seen = set()

        def samples():
            for index, (frame, stamp) in enumerate(sampled, 1):
                data = frame.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if digest in seen:
                    counts["exact_duplicates"] += 1
                    continue
                seen.add(digest)
                proposals = infer(model, frame)
                counts["with_proposal" if proposals else "without_proposal"] += 1
                if index % 100 == 0:
                    print(f"Processed {index}/{len(sampled)} frames", flush=True)
                yield {"bytes": data, "image_path": f"{session_id}/{frame.name}", "timestamp_s": stamp,
                       "source_id": session_id, "capture_session_id": session_id,
                       "source_video_sha256": source_hash, "original_split": "capture-review-pending",
                       "boxes": [row["xyxy"] for row in proposals], "box_proposals": proposals,
                       "coordinate_status": "CUDA proposals in original image pixels; human review pending",
                       "human_review": "pending"}

        summary = write_pack(pack_id, samples(), {
            "source_video_sha256": source_hash, "capture_session_id": session_id,
            "device": torch.cuda.get_device_name(0), "torch": torch.__version__, "ultralytics": ultralytics_version,
            "weights_sha256": _sha256_file(weights), "review_schema": "video-box-v1",
            "sample_rule": "first decoded frame per second, byte-identical JPEGs removed",
            "knife_candidate_confidence": .10, "view_sizes": [960, 640], "merge_iou": .55,
        }, root=scratch)
        if summary["images"] + counts["exact_duplicates"] != len(sampled):
            raise ValueError("Staged frame counts do not balance.")
        summary.update(counts)
        (scratch / pack_id / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        entry = {"id": pack_id, "name": "P430 직접 촬영 · 칼 검수", "role": "직접 촬영 CCTV",
                 "note": "칼 유무를 확인하고 제안 박스를 수정하거나 추가합니다.",
                 "review_schema": "video-box-v1", "review_dir": str(output)}
        (scratch / pack_id / "catalog-entry.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Publish only the completed pack to the staging path.
        (scratch / pack_id).rename(output)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "ffmpeg", "weights", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]{1,60}", args.session_id):
        parser.error("--session-id must be a lowercase review dataset identifier")
    prepare(args.video.resolve(), args.ffmpeg.resolve(), args.weights.resolve(), args.output.resolve(),
            args.session_id, args.session_id)
