"""Stage only the pinned P430 development files needed by the site trainer."""

import argparse
from pathlib import Path
import tarfile

from edge_threat_response.p430_workflow import MODEL_SHA, SOURCE_SHA, read, require, save, sha
from run_p430_integration import jsonl, paths
from run_p430_site import input_paths


def stage(work, output):
    root = work.parent.parent
    baseline = work.parent / "p430-t1-20261120-v1"
    seal = read(work / "protection.json")
    protected = {seal["edited_sha256"], *seal.get("original_sha256", [])}
    plan_file = work / "plan.json"
    plan = read(plan_file)
    require(sha(plan_file) == "8a92eefb8f4bf275d5ace1aae46edb37ad7c6fce02a0484e497fec96deb0a28c"
            and plan["summary"]["scope"] == "development_only"
            and plan["summary"]["protection_sha256"] == sha(work / "protection.json"),
            "Development release seal mismatch")
    manifest = baseline / "dataset/manifest.jsonl"
    original = {row["image_sha256"]: row for row in jsonl(manifest)}
    require(sha(manifest) == SOURCE_SHA, "Reviewed development manifest changed")
    entries = {}

    def add(path, digest=None):
        relative = path.relative_to(root).as_posix()
        if relative not in entries:
            entries[relative] = sha(path)
        require(digest is None or entries[relative] == digest, f"SHA mismatch: {relative}")

    for key, tiled in set((key, tiled) for deck in plan["draws"] for key, tiled in deck):
        row = plan["pool"][key]
        require(row["source_group"] not in protected and key not in protected, "Protected training input")
        image, label = paths(work, row)
        add(image, key)
        add(label, row["label_sha256"])
        if tiled:
            tile, tile_label = input_paths(work, plan, key, True)
            evidence = plan["tiles"][key]
            add(tile, evidence["image_sha256"])
            add(tile_label, evidence["label_sha256"])

    for group in plan["validation"].values():
        for key in group:
            row = original[key]
            require(row["source_video_sha256"] not in protected and key not in protected, "Protected validation input")
            image = baseline / "dataset/images" / Path(row["image"]).name
            add(image, key)
            add(baseline / "dataset/labels" / image.with_suffix(".txt").name, row["label_sha256"])

    reviewed = root / "data/processed/s1-video-reviewed-20261114-v1/added-manifest.jsonl"
    if reviewed.is_file() and any(name.startswith("data/processed/s1-video-reviewed-20261114-v1/") for name in entries):
        add(reviewed)
    add(baseline / "initial.pt", MODEL_SHA)
    for path in (manifest, baseline / "config.json", plan_file, work / "protection.json"):
        add(path)
    with tarfile.open(output, "x", dereference=True) as archive:
        for relative in sorted(entries):
            archive.add(root / relative, arcname=relative, recursive=False)
    receipt = {"scope": "development_only", "archive_sha256": sha(output), "file_count": len(entries),
               "files": entries}
    save(output.with_suffix(".json"), receipt)
    print(f"STAGED files={len(entries)} bytes={output.stat().st_size} sha256={receipt['archive_sha256']}", flush=True)


def unstage(archive, output):
    """Verify the incoming release and publish the extracted tree atomically."""
    receipt = read(archive.with_suffix(".json"))
    files = receipt["files"]
    require(receipt["scope"] == "development_only" and len(files) == receipt["file_count"]
            and sha(archive) == receipt["archive_sha256"], "Incoming archive evidence mismatch")
    require(not output.exists(), "The destination already contains a released dataset")
    partial = output.with_name(output.name + ".partial")
    partial.mkdir(exist_ok=False)
    with tarfile.open(archive, "r:") as bundle:
        members = bundle.getmembers()
        require(len(members) == len(files) and {member.name for member in members} == files.keys()
                and all(member.isfile() and not member.name.startswith("/")
                        and not {".", "..", ""}.intersection(member.name.split("/"))
                        and "\\" not in member.name and ":" not in member.name for member in members),
                "Unexpected or unsafe archive path")
        bundle.extractall(path=partial, members=members, filter="data")
    for relative, digest in files.items():
        require(sha(partial / relative) == digest, f"Extracted file changed: {relative}")
    save(partial / "development-receipt.json", {key: receipt[key] for key in ("scope", "archive_sha256", "file_count")})
    partial.rename(output)
    print(f"VERIFIED files={len(files)} sha256={receipt['archive_sha256']}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--unpack", action="store_true", help="Verify and unpack the staged archive on Python 3.12+.")
    args = parser.parse_args()
    (unstage if args.unpack else stage)(args.work, args.output)
