"""Render a pinned SOHAS sample for review, never create training labels."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from edge_threat_response.dataset.sohas import _inventory, _source_bytes, parse_sohas_voc


def render_sample(source: Path, sample_csv: Path, output: Path) -> dict:
    from PIL import Image, ImageDraw

    source, output = source.resolve(), output.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Output must be separate from the source.")
    if output.exists():
        raise ValueError("Use a new output directory; preserve previous reviews.")
    inventory = _inventory(source)
    with sample_csv.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not 1 <= len(rows) <= 100:
        raise ValueError("Expected a bounded sample of 1 to 100 images.")
    if len({row["image_path"] for row in rows}) != len(rows):
        raise ValueError("Duplicate sample paths.")
    output.mkdir(parents=True)
    sheets = output / "contact-sheets"
    sheets.mkdir()
    evidence, tiles = [], []
    for index, row in enumerate(rows, 1):
        path = row["image_path"]
        xml_path = row["xml_path"] if "xml_path" in row else None
        # Audit CSV omits xml_path; pair in the same original source split.
        if not xml_path:
            folder = "annotations/xmls" if row["original_split"] == "train" else "annotations_test/xmls"
            xml_path = f"Weapons and similar handled objects/Sohas_weapon-Detection/{folder}/{Path(path).stem}.xml"
        raw = _source_bytes(source, path, inventory[path])
        annotation = parse_sohas_voc(_source_bytes(source, xml_path, inventory[xml_path]),
                                     image_name=Path(path).name)
        with Image.open(source / path) as original:
            original.load()
            image = original.convert("RGB")
        width, height = image.size
        if (width, height) != (annotation["width"], annotation["height"]):
            raise ValueError(f"Image/XML dimension mismatch: {path}")
        if annotation["errors"]:
            raise ValueError(f"Annotation errors: {path}: {annotation['errors']}")
        image.thumbnail((360, 216))
        tile = Image.new("RGB", (360, 260), "#202124")
        x, y = (360 - image.width) // 2, (216 - image.height) // 2
        tile.paste(image, (x, y))
        draw = ImageDraw.Draw(tile)
        for obj in annotation["objects"]:
            if obj["raw_name"] == "knife":
                left, top, right, bottom = map(float, obj["bbox_xyxy_raw"])
                draw.rectangle((x + left * image.width / width, y + top * image.height / height,
                                x + right * image.width / width, y + bottom * image.height / height),
                               outline="#00ff7f", width=2)
        draw.text((5, 220), f"{index:03d} {Path(path).name}\nknife={annotation['knife_count']} | raw coords, unconfirmed",
                  fill="white")
        tiles.append(tile)
        evidence.append({"sample_no": index, "image_path": path,
                         "image_sha256": hashlib.sha256(raw).hexdigest(),
                         "image_bytes": len(raw), "width": width, "height": height,
                         "knife_count": annotation["knife_count"], "reviewer": "",
                         "coordinate_status": "unconfirmed", "training_approved": False})
    for start in range(0, len(tiles), 16):
        sheet = Image.new("RGB", (1440, 1040), "white")
        for offset, tile in enumerate(tiles[start:start + 16]):
            sheet.paste(tile, ((offset % 4) * 360, (offset // 4) * 260))
        sheet.save(sheets / f"page-{start // 16 + 1:03d}.jpg", quality=90)
    (output / "image-evidence.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in evidence), encoding="utf-8")
    with (output / "review.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            row["image_present"] = True
            row["reviewer"] = ""  # Never carry an AI/supplied verdict into human approval.
            writer.writerow(row)
    summary = {"decoded_images": len(evidence), "image_bytes": sum(row["image_bytes"] for row in evidence),
               "knife_objects": sum(row["knife_count"] for row in evidence),
               "contact_sheets": (len(tiles) + 15) // 16,
               "sample_csv_sha256": hashlib.sha256(sample_csv.read_bytes()).hexdigest(),
               "human_review": "pending", "coordinates": "raw overlay only, unconfirmed",
               "training_approved": False}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--sample-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(render_sample(args.source_root, args.sample_csv, args.output)))
