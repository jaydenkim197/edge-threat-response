"""Read-only gap/overlap audit of reviewed additions; never grants training admission."""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from .development_subset import proxy_components
from .image_screening import image_signature
from ..replay import write_jsonl
from ..training import _git_commit, _sha256_file, _write_json


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def candidate_links(review, full, full_pairs, cross_pairs, protected_hashes, *, candidate_families=True):
    """Conservative transitive proxy links, including unselected image bridges."""
    groups = proxy_components(full, full_pairs)
    identities = [r["record_id"] for r in full + review]
    if len(set(identities)) != len(identities):
        raise ValueError("Full/review record IDs must be unique")
    parent = {key: key for key in identities}
    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key
    def union(a, b):
        if a not in parent or b not in parent:
            raise ValueError("Similarity pair outside the bound inventory")
        a, b = find(a), find(b)
        if a != b:
            parent[max(a,b)] = min(a,b)
    seen_groups, hashes, families = {}, {}, {}
    for row in full + review:
        key, digest = row["record_id"], row["image_sha256"]
        if digest in hashes:
            union(key, hashes[digest])
        hashes[digest] = key
        group = groups.get(key)
        if group:
            if group in seen_groups:
                union(key, seen_groups[group])
            seen_groups[group] = key
        # SOHAS/DaSCI share the same upstream producer; filename families may bridge them.
        # Other sources get their own namespace. These are proxies, not verified sessions.
        if not candidate_families:
            continue
        namespace = "granada" if row["dataset_id"] in {"sohas", "dasci-unique"} else row["dataset_id"]
        stem = Path(row.get("image_path", key)).stem.lower()
        family = (namespace, re.sub(r"\d+(?:v\d+)?$", "", stem).rstrip("_- .") or stem)
        if family in families:
            union(key, families[family])
        families[family] = key
    for pair in cross_pairs:
        union(pair["left"], pair["right"])
    if not protected_hashes <= set(hashes):
        raise ValueError("Protected split identities missing from source inventory")
    protected_roots = {find(hashes[digest]) for digest in protected_hashes}
    return {row["record_id"]: find(row["record_id"]) in protected_roots for row in review}


def audit(review_path, full_path, full_pairs_path, cross_pairs_path, prepared_manifest, output):
    if output.exists():
        raise ValueError("Use a fresh reinforcement audit output")
    files = [review_path, full_path, full_pairs_path, cross_pairs_path, prepared_manifest]
    if any(output.resolve().is_relative_to(p.parent.resolve()) for p in files):
        raise ValueError("Keep output outside input directories")
    before = {str(p): _sha256_file(p) for p in files}
    review, full = _rows(review_path), _rows(full_path)
    protected = {r["image_sha256"] for r in _rows(prepared_manifest) if r["split"] in {"val", "test"}}
    links = candidate_links(review, full, _rows(full_pairs_path), _rows(cross_pairs_path), protected)
    visual_links = candidate_links(review, full, _rows(full_pairs_path), _rows(cross_pairs_path), protected, candidate_families=False)
    candidates = []
    for row in review:
        if row["dataset_id"] not in {"dasci-unique", "simuletic"} or row["review_verdict"] != "ok":
            continue
        signature = image_signature(Path(row["image_file"]), expected_sha256=row["image_sha256"])
        if (signature["width"], signature["height"]) != (row["width"], row["height"]):
            raise ValueError("Candidate image dimensions changed")
        areas = []
        for x1,y1,x2,y2 in row["raw_boxes_xyxy"]:
            if not (0 <= x1 < x2 <= row["width"] and 0 <= y1 < y2 <= row["height"]):
                raise ValueError("Candidate annotation outside decoded pixels")
            areas.append((x2-x1)*(y2-y1)/(row["width"]*row["height"]))
        if len(areas) != row["knife_count"]:
            raise ValueError("Candidate annotation count changed")
        candidates.append({"record_id": row["record_id"], "dataset_id": row["dataset_id"],
                           "image_sha256": row["image_sha256"], "review_version": row["review_version"],
                           "review_payload_sha256": row["review_payload_sha256"], "domain": row["domain"],
                           "knife_count": len(areas), "normalized_areas": areas,
                           "protected_proxy_link": links[row["record_id"]],
                           "protected_link_without_candidate_filename_families": visual_links[row["record_id"]],
                           "nondefault_exif": signature["exif_orientation"] != 1,
                           "source_role": row["source_role"], "training_approved": False,
                           "coordinate_status": row["coordinate_status"]})
    summaries = {}
    for source in ("dasci-unique", "simuletic"):
        selected = [r for r in candidates if r["dataset_id"] == source]
        areas = [a for r in selected for a in r["normalized_areas"]]
        summaries[source] = {"images": len(selected), "positive": sum(r["knife_count"] > 0 for r in selected),
                             "objects": len(areas), "small_objects": sum(a <= .02 for a in areas),
                             "area_median": statistics.median(areas) if areas else None,
                             "domains": dict(Counter(r["domain"] for r in selected)),
                             "protected_proxy_linked": sum(r["protected_proxy_link"] for r in selected),
                             "protected_linked_without_candidate_filename_families": sum(r["protected_link_without_candidate_filename_families"] for r in selected),
                             "nondefault_exif": sum(r["nondefault_exif"] for r in selected)}
    if before != {str(p): _sha256_file(p) for p in files}:
        raise ValueError("Inputs changed during reinforcement audit")
    output.mkdir(parents=True)
    write_jsonl(output / "candidates.jsonl", candidates)
    result = {"schema_version": 1, "status": "audited_not_approved", "git_commit": _git_commit(),
              "input_sha256": before, "sources": summaries, "training_approved": False,
              "test_images_or_labels_opened": False, "human_verdicts_written": 0,
              "limits": ["conservative family/hash/dHash links are not verified shared sessions",
                         "no proxy link does not establish independence or training permission",
                         "review raw overlay coordinates are not a source-coordinate audit",
                         "synthetic additions require a separate ablation, never substitute for real target footage"]}
    _write_json(output / "summary.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("review", "full", "full-pairs", "cross-pairs", "prepared-manifest", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.review, args.full, args.full_pairs, args.cross_pairs, args.prepared_manifest, args.output_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
