"""Select reviewed training positives for the matched MIX70 replay experiment."""

from argparse import ArgumentParser
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
from statistics import median

from edge_threat_response.p430_workflow import SOURCE_SHA, read, require, save, sha
from p430_crop_verifier import archived_proposals, reviewed_train_rows, verified_sha
from p430_followup_actions import PLAN_SHA, pin_plan
from run_p430_integration import jsonl
from run_p430_site import normalized_crop, original_boxes, regions


SIZE_EDGES = (8, 16, 32)
MIN_GAP_SECONDS = 5
RECIPE = {
    "budget": {"p430": 5734, "cctv": 1638, "m2": 820},
    "tile_share": .48,
    "tile_policy": "pinned-plan-native-768x640",
    "seed": 3407,
    "target_fraction": .10,
    "max_extra_uses_per_parent_per_epoch": 2,
}


def confidence_order(row):
    return row["confidence"], row["image_sha256"]


def select_cohorts(rows):
    """Rank within each source and size, then enforce spacing across that source."""
    groups = defaultdict(list)
    for row in rows:
        groups[row["source_video_sha256"], row["short_side_bin"]].append(row)

    quartile = []
    donors = []
    strata = {}
    for (source, size), group in sorted(groups.items()):
        ranked = sorted(group, key=confidence_order)
        cutoff = median(row["confidence"] for row in ranked)
        low = ranked[:len(ranked) // 4]
        normal = [row for row in ranked if row["confidence"] > cutoff]
        quartile.extend(low)
        donors.extend(normal)
        strata[source, size] = {"source_video_sha256": source, "short_side_bin": size, "eligible": len(ranked),
                                "bottom_quartile": len(low), "median_confidence": cutoff,
                                "normal_donors": len(normal), "retained": 0}

    candidates = []
    timestamps = defaultdict(list)
    for row in sorted(quartile, key=confidence_order):
        source = row["source_video_sha256"]
        stamp = row["timestamp_s"]
        if all(abs(stamp - other) >= MIN_GAP_SECONDS for other in timestamps[source]):
            candidates.append(row)
            timestamps[source].append(stamp)
            strata[source, row["short_side_bin"]]["retained"] += 1
    return candidates, donors, list(strata.values())


def verify_tile(base, key, tile, box):
    image = base / "tiles/images" / f"{key}.jpg"
    label = base / "tiles/labels" / f"{key}.txt"
    require(sha(image) == tile["image_sha256"] and sha(label) == tile["label_sha256"],
            "Pinned training tile or label changed")
    native_regions = regions(1920, 1080)
    x, y, width, height = box
    parent_boxes = [(1920 * x, 1080 * y, 1920 * width, 1080 * height)]
    valid = [(region, normalized_crop(parent_boxes, region)) for region in native_regions]
    valid = [(region, retained) for region, retained in valid if retained]
    require(valid, "Positive training parent had no valid native tile")
    region, expected = valid[int(key[:12], 16) % len(valid)]
    actual = original_boxes(label)
    require(list(region) == tile["region"] and len(actual) == len(expected) == 1
            and all(abs(left - right) < 1e-8 for left, right in zip(actual[0], expected[0], strict=True)),
            "Pinned tile does not reproduce the single reviewed box")


def eligible_positives(base, plan, rows, proposals):
    by_image = {row["image_sha256"]: row for row in rows}
    eligible = []
    for proposal in proposals:
        if proposal["label"] != 1:
            continue
        key = proposal["image_sha256"]
        row = by_image[key]
        tile = plan["tiles"].get(key)
        if len(row["boxes"]) != 1 or tile is None:
            continue
        box = row["boxes"][0]
        verify_tile(base, key, tile, box)
        short_side = min(box[2] * 960, box[3] * 540)
        eligible.append({
            "image_sha256": key,
            "label_sha256": row["label_sha256"],
            "source_sha256": row["source_sha256"],
            "source_video_sha256": row["source_video_sha256"],
            "tile_image_sha256": tile["image_sha256"],
            "tile_label_sha256": tile["label_sha256"],
            "timestamp_s": row["timestamp_s"],
            "confidence": proposal["confidence"],
            "short_side_px": short_side,
            "short_side_bin": bisect_right(SIZE_EDGES, short_side),
        })
    require(len(eligible) == len({row["image_sha256"] for row in eligible}),
            "Expected one archived matching proposal per eligible positive frame")
    return eligible


def run(settings, shared_snapshot, output, archive, mix70_checkpoint=None):
    require(settings["node"] == "pc13" and not output.exists(), "Use a fresh evidence path on PC13")
    snapshot = read(shared_snapshot)
    snapshot = snapshot.get("evidence", snapshot)
    hog, mix70 = snapshot["B-ALT01-CROP-PILOT"], snapshot["A-MIX70"]
    require(hog["status"] == mix70["status"] == "COMPLETED"
            and hog["result_sha256"] == archive.hog_result_sha256.lower(),
            "Expected a completed PC13 HOG archive receipt and MIX70 run")
    model = mix70["data"]
    checkpoint = mix70_checkpoint or Path(model["checkpoint"])
    checkpoint_sha = verified_sha(checkpoint, model["checkpoint_sha256"])

    base = Path(settings["base"])
    plan = pin_plan(base)
    protection = base / "protection.json"
    manifest = base.parent / "p430-t1-20261120-v1/dataset/manifest.jsonl"
    require(sha(manifest) == SOURCE_SHA, "Reviewed P430 manifest changed")
    rows = reviewed_train_rows(base, plan, jsonl(manifest), read(protection))
    proposals, _, provenance = archived_proposals(archive, rows, checkpoint_sha)
    positives = eligible_positives(base, plan, rows, proposals)
    candidates, donors, strata = select_cohorts(positives)
    donor_strata = {(row["source_video_sha256"], row["short_side_bin"]) for row in donors}
    require(candidates and all((row["source_video_sha256"], row["short_side_bin"]) in donor_strata
                               for row in candidates), "No matching above-median donors for every target stratum")
    save(output, {
        "schema_version": 1,
        "scope": "development_train_review_positive_replay",
        "experiment": "A-MIX70-POS-MINE",
        "base_plan_sha256": PLAN_SHA,
        "reviewed_manifest_sha256": SOURCE_SHA,
        "protection_sha256": plan["summary"]["protection_sha256"],
        "mix70_checkpoint_sha256": checkpoint_sha,
        "mix70_result_sha256": model["result_sha256"],
        "selector_sha256": sha(Path(__file__)),
        **provenance,
        "recipe": RECIPE,
        "selection": {
            "short_side_pixels_at": [960, 540], "bin_edges": SIZE_EDGES,
            "strata": ["source_video_sha256", "short_side_bin"],
            "target_rule": "lowest floor(n / 4) scores within a stratum",
            "target_order": ["confidence ascending", "image_sha256 ascending"],
            "minimum_seconds_apart_within_source_across_bins": MIN_GAP_SECONDS,
            "donor_rule": "confidence strictly above the median within a stratum",
        },
        "counts": {
            "verified_train_images": len(rows),
            "archived_train_positives": sum(proposal["label"] == 1 for proposal in proposals),
            "eligible_train_positives": len(positives),
            "before_spacing": sum(group["bottom_quartile"] for group in strata),
            "candidates": len(candidates),
            "normal_donors": len(donors),
        },
        "strata": strata,
        "candidates": candidates,
        "normal_donors": donors,
    })


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("node_settings", type=Path)
    parser.add_argument("shared_snapshot", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--hog-result", type=Path, required=True)
    parser.add_argument("--hog-result-sha256", required=True)
    parser.add_argument("--hog-verifier", type=Path, required=True)
    parser.add_argument("--mix70-checkpoint", type=Path)
    args = parser.parse_args()
    run(read(args.node_settings), args.shared_snapshot, args.output, args, args.mix70_checkpoint)
