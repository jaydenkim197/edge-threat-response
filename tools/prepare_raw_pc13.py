"""Prepare available PC13 raw sources; no production review DB access."""
import argparse
import json
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

from edge_threat_response.dataset.image_screening import image_signature
from edge_threat_response.dataset.labels import parse_yolo_label
from edge_threat_response.dataset.materialize import _convert_knife_label
from edge_threat_response.dataset.raw_import import materialize_inventory, voc_knife, check_detector_image, filter_detector_inventory
from edge_threat_response.dataset.sohas import VOC_ROOT, _inventory, _source_bytes, SOURCE_URL
from edge_threat_response.training import _sha256_file, _write_json


def prepare(root: Path, output: Path):
    root, output = root.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(root / "data/source-audit") or output.is_relative_to(root / "data/review"):
        raise ValueError("New output outside raw/review storage required")
    staging = output.with_name(output.name + "-staging")
    staging.mkdir(parents=True, exist_ok=False)
    candidates, issues, source_inputs = [], [], {}

    def add(source, image, annotation, original, split, license_name, url, text_factory, *, provenance):
        try:
            check_detector_image(image)
            signature = image_signature(image)
            if signature["exif_orientation"] != 1:
                raise ValueError("Nondefault EXIF orientation; cannot assume annotation coordinates")
            text = text_factory(signature)
            if text is None:
                return
            candidates.append({**signature, "record_id": source + "/" + original,
                               "dataset_id": source, "image_file": str(image), "original_split": split,
                               "source_url": url, "license": license_name, "label_text": text,
                               "annotation_provenance": {**provenance, "label_sha256": _sha256_file(annotation)},
                               "coordinate_contract": "source-pixel-edges-assumed-v1" if annotation.suffix == ".xml" else "source-normalized-yolo-v1"})
        except (OSError, ValueError) as exc:
            issues.append({"source": source, "original": original, "reason": str(exc)})

    upstream = root / "data/source-audit/sohas-upstream-byte-exact"
    inventory = _inventory(upstream)
    for split, folder, labels in (("train", "images", "annotations/xmls"), ("test", "images_test", "annotations_test/xmls")):
        for path in sorted(inventory):
            if path.startswith(f"{VOC_ROOT}/{folder}/") and Path(path).suffix.lower() in {".jpg", ".jpeg", ".png"}:
                xml = f"{VOC_ROOT}/{labels}/{Path(path).stem}.xml"
                if xml not in inventory:
                    issues.append({"source": "sohas", "original": path, "reason": "Missing VOC label"})
                    continue
                # Verify the pinned upstream blobs, including byte-exact XML.
                _source_bytes(upstream, path, inventory[path])
                data = _source_bytes(upstream, xml, inventory[xml])
                add("sohas", upstream/path, upstream/xml, path, split, "CC-BY/CC-BY-SA conflicting upstream notices; research-only working copy", SOURCE_URL,
                    lambda sig, data=data: voc_knife(data, width=sig["width"], height=sig["height"], allowed_names={"knife", "pistol", "smartphone", "monedero", "billete", "tarjeta"}),
                    provenance={"git_blob": inventory[xml], "source_revision": "48860b990e4d4f57fe100248887fceb248475dc8"})
    extra = root / "data/source-audit/additional-sources-20261026"
    archive = extra / "dangerous-voc.zip"
    if archive.is_file():
        source_inputs[str(archive)] = _sha256_file(archive)
        dangerous = staging/"dangerous"
        (dangerous/"images").mkdir(parents=True)
        (dangerous/"labels").mkdir()
        with zipfile.ZipFile(archive) as z:
            images = {Path(n).stem: n for n in z.namelist() if Path(n).suffix.lower() in {".jpg", ".png", ".jpeg"}}
            for name in sorted(n for n in z.namelist() if n.lower().endswith(".xml")):
                stem = Path(name).stem
                if stem not in images:
                    issues.append({"source": "dangerous", "original": name, "reason": "Unpaired XML"})
                    continue
                image = dangerous/"images"/Path(images[stem]).name
                annotation = dangerous/"labels"/(stem+".xml")
                image.write_bytes(z.read(images[stem]))
                data = z.read(name)
                annotation.write_bytes(data)
                add("dangerous", image, annotation, images[stem], "original_unspecified", "CC BY 4.0", "https://zenodo.org/records/13786228",
                    lambda sig, data=data: voc_knife(data, width=sig["width"], height=sig["height"], allowed_names={"knife", "gun", "rifle", "machete", "baseball bat", "baseball_bat", "baseballbat"}),
                    provenance={"archive_sha256": source_inputs[str(archive)]})
    archive = extra/"catargiu-v11-yolov8.zip"
    corrected = extra/"catargiu-labels-source/DatasetLabels"
    if archive.is_file() and corrected.is_dir():
        revision = subprocess.check_output(["git", "-C", str(corrected.parent), "rev-parse", "HEAD"], text=True).strip()
        if revision != "382d925c0d4ce054c0368ac2778c93b94654954d":
            raise ValueError("Corrected Catargiu source revision changed")
        source_inputs[str(archive)] = _sha256_file(archive)
        extracted = staging/"catargiu"
        extracted.mkdir()
        with zipfile.ZipFile(archive) as z:
            names = {Path(name).name: name for name in z.namelist() if "/images/" in name and not name.endswith("/")}
            for annotation in sorted(corrected.glob("*/labels/*.txt")):
                parsed = parse_yolo_label(annotation, source_dataset="catargiu", path_reference=str(annotation), class_map={0: 1, 1: 0, 2: 0, 3: 0})
                if parsed.issues:
                    issues.append({"source": "catargiu", "original": str(annotation), "reason": "Invalid corrected label"})
                    continue
                if not any(x.raw_class_id == 0 for x in parsed.annotations):
                    continue  # Unmatched/non-knife files are not verified negatives.
                matching = [name for suffix in (".jpg", ".jpeg", ".png") if (name := annotation.stem+suffix) in names]
                if len(matching) != 1:
                    issues.append({"source": "catargiu", "original": str(annotation), "reason": "Missing/ambiguous image pairing"})
                    continue
                member = names[matching[0]]
                image = extracted/matching[0]
                with image.open("xb") as f:
                    f.write(z.read(member))
                text, _, _ = _convert_knife_label(annotation, class_map={0: 1, 1: 0, 2: 0, 3: 0}, canonical_knife_id=1, skip_non_knife=True)
                add("catargiu", image, annotation, member, member.split("/")[0], "CC BY 4.0 export; upstream research-only notice", "https://github.com/CostiCatargiu/Yolov12_WeaponDetection",
                    lambda sig, text=text: text, provenance={"archive_sha256": source_inputs[str(archive)], "corrected_revision": "382d925c0d4ce054c0368ac2778c93b94654954d"})
    protected = []
    suite = root/"data/work/multi-model-20261104/suite-v1"
    for path in sorted(suite.glob("*-truth.json")):
        for index, row in enumerate(json.loads(path.read_text(encoding="utf-8-sig"))["images"]):
            protected.append({**image_signature(Path(row["image"]), expected_sha256=row["image_sha256"]),
                              "record_id": f"protected/{path.stem}/{index}/" + Path(row.get("source_path", row["image"])).name,
                              "dataset_id": "protected", "original_split": "protected_development_comparison"})
    if not protected:
        raise ValueError("Frozen development comparison suite missing; refuse unprotected import")
    result = materialize_inventory(candidates, protected, output)
    _write_json(output/"source-inputs.json", source_inputs)
    _write_json(output/"import-issues.json", issues)
    result["import_issues"] = dict(Counter(x["source"] for x in issues))
    result["not_in_first_mixture"] = {"open_images_train": "not yet acquired", "legacy": "full data not present in PC13 checkout", "dasci": "existing unique candidates protected as development comparison", "synthetic": "separate S1", "us_mock": "evaluation only"}
    _write_json(output/"summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--filter-inventory", type=Path)
    parser.add_argument("--source-signatures", type=Path)
    args = parser.parse_args()
    result = filter_detector_inventory(args.filter_inventory, args.output_dir, source_signatures=args.source_signatures) if args.filter_inventory else prepare(args.root, args.output_dir)
    print(json.dumps(result, ensure_ascii=False), flush=True)
