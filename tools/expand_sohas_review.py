"""Prepare one bounded, deduplicated SOHAS batch; never mutate the live catalog."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from collections import Counter, defaultdict, deque
from pathlib import Path

from edge_threat_response.dataset.review import size_bucket
from edge_threat_response.dataset.sohas import UPSTREAM_COMMIT
from sohas_review_images import render_sample


def group_proxy(path):
    stem = Path(path).stem.lower()
    return re.sub(r"(?:frame|img|image)[_-]?\d+.*$", "", stem) or stem


def select_batch(candidates, existing_paths, existing_blobs, count, seed):
    groups = defaultdict(list)
    excluded = Counter()
    for item in candidates:
        if item["image_path"] in existing_paths or item["image_git_blob"] in existing_blobs:
            excluded["already_prepared"] += 1
            continue
        if item["errors"]:
            excluded["annotation_structure_error"] += 1
            continue
        boxes = [obj["bbox_xyxy_raw"] for obj in item["objects"] if obj["raw_name"] == "knife"]
        areas = [(float(b[2])-float(b[0]))*(float(b[3])-float(b[1]))/(item["width"]*item["height"]) for b in boxes]
        bucket = size_bucket(min(areas)) if areas else "negative-unverified"
        key = (item["original_split"], bool(boxes), bucket)
        groups[key].append(item)
    queues = [deque(sorted(items, key=lambda row: hashlib.sha256(f"{seed}:{row['image_path']}".encode()).hexdigest())) for _, items in sorted(groups.items())]
    selected, deferred, seen = [], [], set(existing_blobs)
    proxies = {group_proxy(path) for path in existing_paths}
    while any(queues) and len(selected) < count:
        for queue in queues:
            if queue and len(selected) < count:
                item = queue.popleft()
                if item["image_git_blob"] in seen:
                    excluded["duplicate_within_selection"] += 1
                    continue
                if group_proxy(item["image_path"]) in proxies:
                    deferred.append(item)
                    continue
                selected.append(item)
                proxies.add(group_proxy(item["image_path"]))
                seen.add(item["image_git_blob"])
    # Filename proxies are not verified sessions. Prefer diversity, then fill
    # from remaining unique images rather than inventing a session guarantee.
    for item in deferred:
        if len(selected) >= count:
            break
        if item["image_git_blob"] not in seen:
            selected.append(item)
            seen.add(item["image_git_blob"])
    strata = Counter((row["original_split"], row["candidate_role"]) for row in selected)
    return selected, {"excluded": dict(excluded), "selected_split_role": {str(k): v for k, v in strata.items()},
                      "eligible_strata": {str(k): len(v) for k, v in groups.items()}}


def prepare(args):
    if not re.fullmatch(r"[a-z0-9-]{1,60}", args.batch_id) or args.batch_id == "initial":
        raise ValueError("Invalid batch ID")
    if not 1 <= args.count <= 100 or args.output.exists() or args.proposed_config.exists():
        raise ValueError("Use new output/proposal paths and a bounded 1..100 batch")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    target = next(entry for entry in config["datasets"] if entry["id"] == "sohas")
    if any(batch["id"] == args.batch_id for batch in target.get("review_batches", [])):
        raise ValueError("Batch already registered")
    paths, blobs, hashes = set(), set(), set()
    for entry in config["datasets"]:
        for root in [entry.get("review_dir"), *(batch["review_dir"] for batch in entry.get("review_batches", []))]:
            if not root:
                continue
            folder = Path(root)
            for item in map(json.loads, (folder / "image-evidence.jsonl").read_text(encoding="utf-8").splitlines()):
                raw = (folder / item["image_file"]).read_bytes()
                hashes.add(hashlib.sha256(raw).hexdigest())
                blobs.add(hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest())
                if entry["id"] == "sohas":
                    paths.add(item["image_path"])
    candidates = [json.loads(line) for line in args.audit.read_text(encoding="utf-8").splitlines()]
    selected, report = select_batch(candidates, paths, blobs, args.count, args.seed)
    if len(selected) != args.count:
        raise ValueError(f"Only {len(selected)} eligible candidates; no pack published")
    # Write preparation files outside both the original source and live packs.
    selection = args.output.with_suffix(".selection.csv")
    columns = ["image_path", "original_split", "candidate_role", "knife_count", "xml_path", "group_id", "reviewer"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    writer.writerows({key: group_proxy(item["image_path"]) if key == "group_id" else item.get(key, "") for key in columns} for item in selected)
    selection_bytes = stream.getvalue().encode("utf-8-sig")
    if selection.exists() and selection.read_bytes() != selection_bytes:
        raise ValueError("Existing selection differs; preserve it and use another path")
    if not selection.exists():
        selection.write_bytes(selection_bytes)
    if args.fetch_images:
        if subprocess.run(["git", "-C", str(args.source), "config", "--get", "core.sparseCheckoutCone"], capture_output=True, text=True).stdout.strip() != "false":
            raise ValueError("Use the existing non-cone sparse checkout; never reset source selection")
        subprocess.run(["git", "-C", str(args.source), "sparse-checkout", "add", "--stdin"],
                       input="".join(f"/{item['image_path']}\n" for item in selected), text=True, check=True)
    summary = render_sample(args.source, selection, args.output)
    evidence = [json.loads(line) for line in (args.output / "image-evidence.jsonl").read_text().splitlines()]
    if hashes & {item["image_sha256"] for item in evidence}:
        raise ValueError("Cross-source SHA-256 duplicate; staged pack NOT published")
    report.update(summary, batch_id=args.batch_id, source_revision=UPSTREAM_COMMIT, seed=args.seed,
                  selection_policy="split x annotation role x normalized bbox area; prefer new filename proxy groups",
                  group_status="filename proxies only; session/near-duplicate audit still pending",
                  existing_unique_image_hashes=len(hashes), cross_source_exact_overlap=0,
                  audit_sha256=hashlib.sha256(args.audit.read_bytes()).hexdigest(), training_approved=False)
    (args.output / "batch-provenance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    target.setdefault("review_batches", []).append({"id": args.batch_id, "review_dir": str(args.output.resolve())})
    args.proposed_config.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--proposed-config", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261004)
    parser.add_argument("--fetch-images", action="store_true")
    prepare(parser.parse_args())
