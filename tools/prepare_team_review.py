"""Bounded, provenance-preserving review packs; never approve or train datasets."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/source-audit/team-review-20261003"
PACKS = ROOT / "data/review/team-candidates-20261003"
UPSTREAM = "48860b990e4d4f57fe100248887fceb248475dc8"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def get(url: str, limit: int = 30_000_000) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "ETR academic dataset review/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Response exceeds review download limit")
    return data


def download(url: str, target: Path, *, size: int, checksum: str | None = None):
    if size > 2_000_000_000:
        raise ValueError("Archive exceeds 2 GB source limit")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size != size:
        partial = target.with_suffix(target.suffix + ".partial")
        print(f"Downloading {target.name}: {size} bytes", flush=True)
        with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as output:
            count = 0
            while chunk := response.read(2**20):
                count += len(chunk)
                if count > size:
                    raise ValueError("Download exceeds declared size")
                output.write(chunk)
        if count != size:
            raise ValueError("Incomplete download")
        partial.replace(target)
    digest = hashlib.sha256()
    md5 = hashlib.md5()  # Only compare provider's non-security archive checksum.
    with target.open("rb") as stream:
        while chunk := stream.read(2**20):
            digest.update(chunk)
            md5.update(chunk)
    if checksum and checksum != "md5:" + md5.hexdigest():
        raise ValueError("Provider checksum mismatch")
    return digest.hexdigest()


def seeded(paths):
    return sorted(paths, key=lambda value: hashlib.sha256(("20261003:" + value).encode()).hexdigest())


def yolo_boxes(text: str, width: int, height: int, knife_class: int):
    boxes = []
    for line in text.splitlines():
        if not line.strip():
            continue
        tokens = line.split()
        if len(tokens) != 5:
            raise ValueError("Unsupported annotation shape")
        if int(tokens[0]) != knife_class:
            continue
        x, y, w, h = map(float, tokens[1:])
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            raise ValueError("Invalid YOLO coordinates")
        boxes.append([(x-w/2)*width, (y-h/2)*height, (x+w/2)*width, (y+h/2)*height])
    return boxes


def write_pack(name, samples, provenance):
    output = PACKS / name
    if output.exists():
        raise ValueError(f"Preserve existing pack: {output}")
    output.mkdir(parents=True)
    (output / "images").mkdir()
    evidence, rows = [], []
    for number, sample in enumerate(samples, 1):
        raw = sample.pop("bytes")
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            width, height = image.size
        suffix = Path(sample["image_path"]).suffix.lower()
        filename = f"images/{number:03d}{suffix}"
        (output / filename).write_bytes(raw)
        boxes = sample.pop("boxes", None)
        if boxes is None:
            boxes = yolo_boxes(sample.pop("yolo"), width, height, sample.pop("knife_class"))
        for left, top, right, bottom in boxes:
            if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise ValueError(f"Invalid box: {sample['image_path']}")
        evidence.append({"sample_no": number, "image_path": sample["image_path"],
                         "image_file": filename, "width": width, "height": height,
                         "image_sha256": hashlib.sha256(raw).hexdigest(), "image_bytes": len(raw),
                         "knife_count": len(boxes), "knife_boxes_xyxy_raw": boxes,
                         "coordinate_status": "source annotation; human verification pending",
                         "training_approved": False, **sample})
        rows.append({"sample_no": number, "image_path": sample["image_path"],
                     "original_split": sample.get("original_split", "unknown"),
                     "reviewer": "", "notes": ""})
    if not rows:
        raise ValueError("No review samples")
    with (output / "review.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output / "image-evidence.jsonl").write_text("".join(json.dumps(row) + "\n" for row in evidence), encoding="utf-8")
    summary = {"images": len(rows), "knife_objects": sum(item["knife_count"] for item in evidence),
               "image_bytes": sum(item["image_bytes"] for item in evidence),
               "human_review": "pending", "training_approved": False, **provenance}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def archives():
    RAW.mkdir(parents=True, exist_ok=True)
    zenodo = json.loads(get("https://zenodo.org/api/records/16422779"))
    (RAW / "dangerous-items-record.json").write_text(json.dumps(zenodo, indent=2), encoding="utf-8")
    if zenodo["metadata"].get("license", {}).get("id") != "cc-by-4.0":
        raise ValueError("Dangerous Items license not confirmed")
    item = zenodo["files"][0]
    hf = "https://huggingface.co/api/datasets/jsalazar/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset"
    metadata = json.loads(get(hf))
    revision = metadata["sha"]
    (RAW / "us-mock-attack-record.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    jobs = [
        (item["links"]["self"], RAW / "dangerous-items.zip", item["size"], item["checksum"]),
        (f"https://huggingface.co/datasets/jsalazar/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset/resolve/{revision}/weapons_images_2fps.zip", RAW / "us-mock-attack.zip", 1485019798, None),
    ]
    def run(job):
        url, file, size, checksum = job
        sha = download(url, file, size=size, checksum=checksum)
        with zipfile.ZipFile(file) as archive:
            names = archive.namelist()
            report = {"url": url, "sha256": sha, "files": len(names), "first_paths": names[:15],
                      "annotation_paths": [n for n in names if Path(n).suffix in {".xml", ".txt", ".yaml", ".json"}][:15]}
        (RAW / (file.stem + "-inventory.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, jobs))


def simuletic():
    base = "https://huggingface.co/api/datasets/Simuletic/cctv-knife-detection-dataset"
    metadata = json.loads(get(base))
    revision = metadata["sha"]
    files = json.loads(get(base + f"/tree/{revision}/Knife_Dataset?recursive=true&limit=1000"))
    paths = [item["path"] for item in files if Path(item["path"]).suffix.lower() in IMAGE_EXTENSIONS]
    config_url = f"https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset/resolve/{revision}/Knife_Dataset/dataset.yaml"
    config = get(config_url).decode()
    if "person" not in config or "knife" not in config:
        raise ValueError("Verify Simuletic class mapping")
    def load(path):
        url = f"https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset/resolve/{revision}/"
        label = str(Path(path).with_suffix(".txt")).replace("\\", "/").replace("/images/", "/labels/")
        return {"image_path": path, "bytes": get(url + urllib.parse.quote(path)),
                "yolo": get(url + urllib.parse.quote(label)).decode(), "knife_class": 1,
                "source_url": url + path, "original_split": "unsplit"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        samples = list(pool.map(load, seeded(paths)))
    return write_pack("simuletic", samples, {"source_revision": revision, "license": "CC BY 4.0 (dataset card)",
                                            "class_config": config, "role": "synthetic review only"})


def dasci():
    source = ROOT / "data/source-audit/sohas-upstream-byte-exact"
    tree = subprocess.check_output(["git", "ls-tree", "-r", UPSTREAM], cwd=source).decode().splitlines()
    entries = {line.split("\t", 1)[1]: line.split()[2] for line in tree}
    sohas_blobs = {blob for path, blob in entries.items() if "Sohas_weapon-Detection/" in path and Path(path).suffix.lower() in IMAGE_EXTENSIONS}
    images = [path for path in entries if path.startswith("Knife_detection/Images/") and Path(path).suffix.lower() in IMAGE_EXTENSIONS and entries[path] not in sohas_blobs]
    def raw(path):
        data = get(f"https://raw.githubusercontent.com/ari-dasci/OD-WeaponDetection/{UPSTREAM}/" + urllib.parse.quote(path))
        if hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() != entries[path]:
            raise ValueError("Pinned Git blob mismatch")
        return data
    from edge_threat_response.dataset.sohas import parse_sohas_voc
    samples = []
    for path in seeded(images):
        labels = [p for p in entries if p.startswith("Knife_detection/") and Path(p).stem == Path(path).stem and p.endswith(".xml")]
        if len(labels) != 1:
            raise ValueError(f"DaSCI XML pairing: {path}")
        annotation = parse_sohas_voc(raw(labels[0]), image_name=Path(path).name)
        if annotation["errors"]:
            raise ValueError(f"DaSCI annotation: {path}")
        samples.append({"image_path": path, "bytes": raw(path),
                        "boxes": [list(map(float, obj["bbox_xyxy_raw"])) for obj in annotation["objects"] if obj["raw_name"] == "knife"],
                        "source_revision": UPSTREAM, "original_split": "unsplit"})
    return write_pack("dasci-unique", samples, {"source_revision": UPSTREAM, "license": "upstream CC notices conflict; internal review only",
                                               "selection": "Git image blobs absent from SOHAS; near duplicates not yet checked"})


def legacy(csv_path: Path):
    from edge_threat_response.dataset.review import parse_review_boxes
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig", newline="")))
    samples = []
    for row in rows:
        original = row["image_path"].replace("\\", "/")
        image = ROOT / ("legacy/" + original.split("/legacy/", 1)[1])
        label_original = row["label_path"].replace("\\", "/")
        label = ROOT / ("legacy/" + label_original.split("/legacy/", 1)[1])
        with Image.open(image) as opened:
            w, h = opened.size
        boxes = [[(b.x_center-b.width/2)*w, (b.y_center-b.height/2)*h,
                  (b.x_center+b.width/2)*w, (b.y_center+b.height/2)*h] for b in parse_review_boxes(label)]
        samples.append({"image_path": str(image.relative_to(ROOT)).replace("\\", "/"), "bytes": image.read_bytes(),
                        "boxes": boxes, "original_split": row["original_split"], "annotation_formats": row["annotation_formats"]})
    return write_pack("legacy", samples, {"role": "L0 team review; original 128 samples", "license": "legacy declared CC BY 4.0; provenance review pending"})


def xml_knives(raw):
    root = ET.fromstring(raw)
    width, height = int(root.findtext("size/width")), int(root.findtext("size/height"))
    boxes = []
    for obj in root.findall("object"):
        if obj.findtext("name", "").strip().lower() == "knife":
            boxes.append([float(obj.findtext("bndbox/" + coordinate)) for coordinate in ("xmin", "ymin", "xmax", "ymax")])
    return width, height, boxes


def us_mock():
    archive_path = RAW / "us-mock-attack.zip"
    groups = defaultdict(list)
    annotations = {}
    with zipfile.ZipFile(archive_path) as archive:
        for path in archive.namelist():
            if Path(path).suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            label = str(Path(path).with_suffix(".xml")).replace("\\", "/")
            width, height, boxes = xml_knives(archive.read(label))
            camera = Path(path).name.split("-", 1)[0]
            sequence = Path(path).stem.rsplit("_frame_", 1)[0]
            annotations[path] = (width, height, boxes, camera, sequence)
            groups[(camera, bool(boxes))].append(path)
        queues = [seeded(paths) for _, paths in sorted(groups.items())]
        selected = []
        while len(selected) < 100 and any(queues):
            for queue in queues:
                if queue and len(selected) < 100:
                    selected.append(queue.pop(0))
        samples = []
        for path in selected:
            w, h, boxes, camera, sequence = annotations[path]
            raw = archive.read(path)
            with Image.open(io.BytesIO(raw)) as image:
                if image.size != (w, h):
                    raise ValueError("US image/XML dimension mismatch")
            samples.append({"image_path": path, "bytes": raw, "boxes": boxes,
                            "camera": camera, "source_group": sequence, "original_split": "external-unsplit"})
    inventory = json.loads((RAW / "us-mock-attack-inventory.json").read_text())
    return write_pack("us-mock", samples, {"license": "CC BY-NC 4.0; official academic use notice",
                                         "archive_sha256": inventory["sha256"], "source_url": inventory["url"],
                                         "population_strata": {str(key): len(value) for key, value in groups.items()},
                                         "selection": "100 deterministic camera x annotation-positive strata; not continuous event GT"})


def open_images():
    metadata_urls = {
        "classes": "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv",
        "boxes": "https://storage.googleapis.com/openimages/v5/validation-annotations-bbox.csv",
        "images": "https://storage.googleapis.com/openimages/2018_04/validation/validation-images-with-rotation.csv",
    }
    content = {}
    for key, url in metadata_urls.items():
        cache = RAW / f"open-images-{key}.csv"
        if not cache.exists():
            cache.write_bytes(get(url, limit=100_000_000))
        content[key] = cache.read_bytes()
    classes = dict(csv.reader(io.StringIO(content["classes"].decode())))
    knife = next(key for key, name in classes.items() if name == "Knife")
    boxes = defaultdict(list)
    for row in csv.DictReader(io.StringIO(content["boxes"].decode())):
        if row["LabelName"] == knife:
            boxes[row["ImageID"]].append(row)
    metadata = {row["ImageID"]: row for row in csv.DictReader(io.StringIO(content["images"].decode()))}
    candidates = [key for key in boxes if key in metadata and metadata[key].get("License", "").rstrip("/") in {
        "https://creativecommons.org/licenses/by/2.0", "http://creativecommons.org/licenses/by/2.0"}]
    # Only knife-positive images: absence of a Knife label is not a verified negative.
    small = [key for key in candidates if min((float(b["XMax"])-float(b["XMin"]))*(float(b["YMax"])-float(b["YMin"])) for b in boxes[key]) < 0.005]
    other = [key for key in candidates if key not in set(small)]
    chosen = seeded(small)[:30] + seeded(other)[:30]
    def load(image_id):
        url = f"https://open-images-dataset.s3.amazonaws.com/validation/{image_id}.jpg"
        raw = get(url)
        with Image.open(io.BytesIO(raw)) as image:
            w, h = image.size
        return {"image_path": f"validation/{image_id}.jpg", "bytes": raw,
                "boxes": [[float(b["XMin"])*w, float(b["YMin"])*h, float(b["XMax"])*w, float(b["YMax"])*h] for b in boxes[image_id]],
                "original_split": "validation-source-only", "source_url": url,
                "image_metadata": metadata[image_id], "annotation_rows": boxes[image_id]}
    with ThreadPoolExecutor(max_workers=4) as pool:
        samples = list(pool.map(load, chosen))
    return write_pack("open-images", samples, {"license": "annotations CC BY 4.0; image metadata CC BY 2.0",
                                              "metadata_urls": metadata_urls,
                                              "metadata_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in content.items()},
                                              "population": len(candidates), "selection": "up to 30 tiny + 30 other knife positives; image rights still individually reviewable",
                                              "role": "review only; source validation split is not our final holdout"})


class RangeReader(io.RawIOBase):
    """Read only bounded ZIP ranges from the official endpoint, not all 1.4 GB."""
    def __init__(self, url, size):
        self.url, self.size, self.position = url, size, 0
        self.cache = OrderedDict()
        self.downloaded = 0

    def seekable(self):
        return True

    def seek(self, offset, whence=0):
        self.position = offset if whence == 0 else self.position + offset if whence == 1 else self.size + offset
        if self.position < 0:
            raise ValueError("Negative seek")
        return self.position

    def tell(self):
        return self.position

    def read(self, size=-1):
        end = min(self.size, self.position + size if size >= 0 else self.size)
        if end - self.position > 10_000_000:
            raise ValueError("Unbounded ZIP read")
        pieces = []
        while self.position < end:
            start = self.position // 262144 * 262144
            if start not in self.cache:
                stop = min(self.size-1, start+262143)
                # Isolate cache keys: some upstream caches do not vary on Range.
                parts, offset = [], start
                for _ in range(4):
                    request = urllib.request.Request(self.url + f"&review_range={offset}-{stop}", headers={"Range": f"bytes={offset}-{stop}", "User-Agent": "ETR academic review/1.0"})
                    with urllib.request.urlopen(request, timeout=45) as response:
                        if response.status != 206:
                            raise ValueError("Server did not honor bounded Range request")
                        if response.headers.get("Content-Range") != f"bytes {offset}-{stop}/{self.size}":
                            raise ValueError("Unexpected HTTP Content-Range")
                        part = response.read(stop-offset+2)
                    if not part or len(part) > stop-offset+1:
                        raise ValueError("Invalid range response length")
                    parts.append(part)
                    offset += len(part)
                    if offset == stop+1:
                        break
                chunk = b"".join(parts)
                if len(chunk) != stop-start+1:
                    raise ValueError("Incomplete source range after bounded retries")
                self.downloaded += len(chunk)
                if self.downloaded > 200_000_000:
                    raise ValueError("Source review range budget exceeded")
                self.cache[start] = chunk
                if len(self.cache) > 16:
                    self.cache.popitem(last=False)
            chunk = self.cache[start]
            offset = self.position-start
            take = min(len(chunk)-offset, end-self.position)
            pieces.append(chunk[offset:offset+take])
            self.position += take
        return b"".join(pieces)


def dangerous_inventory():
    record = json.loads((RAW / "dangerous-items-record.json").read_text())
    file = record["files"][0]
    reader = RangeReader("https://zenodo.org/records/16422779/files/Dangerous%20Items.zip?download=1", file["size"])
    with zipfile.ZipFile(reader) as archive:
        names = archive.namelist()
        configs = {name: archive.read(name).decode("utf-8-sig") for name in names if Path(name).suffix.lower() in {".yaml", ".yml"}}
        result = {"first_paths": names[:12], "configs": configs, "files": len(names),
                  "first_labels": [name for name in names if name.endswith(".txt")][:6], "range_bytes": reader.downloaded}
        result["other_paths"] = [name for name in names if name and not name.endswith("/") and "/images/" not in name and "/labels/" not in name][:30]
    (RAW / "dangerous-range-inventory.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def dangerous_probe():
    from PIL import ImageDraw
    record = json.loads((RAW / "dangerous-items-record.json").read_text())
    reader = RangeReader("https://zenodo.org/records/16422779/files/Dangerous%20Items.zip?download=1", record["files"][0]["size"])
    by_class = defaultdict(list)
    with zipfile.ZipFile(reader) as archive:
        names = set(archive.namelist())
        for label in sorted(name for name in names if "/labels/" in name and name.endswith(".txt")):
            classes = {int(line.split()[0]) for line in archive.read(label).decode("utf-8-sig").splitlines() if line.strip()}
            path = str(Path(label).with_suffix(".jpg")).replace("\\", "/").replace("/labels/", "/images/")
            if path not in names:
                continue
            for class_id in classes:
                if len(by_class[class_id]) < 3:
                    by_class[class_id].append(path)
            if len(by_class) >= 5 and all(len(paths) >= 3 for paths in by_class.values()):
                break
        sheet = Image.new("RGB", (960, 5*210), "white")
        for row, (class_id, paths) in enumerate(sorted(by_class.items())):
            for col, path in enumerate(paths):
                with Image.open(io.BytesIO(archive.read(path))) as opened:
                    opened.thumbnail((315, 175))
                    tile = opened.convert("RGB")
                x, y = col*320, row*210
                sheet.paste(tile, (x, y))
                ImageDraw.Draw(sheet).text((x+3, y+177), f"raw class {class_id} · {Path(path).name[:20]}", fill="black")
        output = RAW / "dangerous-class-probe.jpg"
        sheet.save(output)
    result = {"class_samples": {str(key): paths for key, paths in by_class.items()}, "range_bytes": reader.downloaded,
              "contact_sheet": str(output), "mapping_status": "visual inference only; not training-approved"}
    (RAW / "dangerous-class-probe.json").write_text(json.dumps(result, indent=2))
    return result


def dangerous_items(knife_class_override=None):
    import yaml  # Already installed by the training environment; offline prep only.
    record = json.loads((RAW / "dangerous-items-record.json").read_text())
    if record["metadata"]["license"]["id"] != "cc-by-4.0":
        raise ValueError("Source rights changed")
    reader = RangeReader("https://zenodo.org/records/16422779/files/Dangerous%20Items.zip?download=1", record["files"][0]["size"])
    groups = defaultdict(list)
    with zipfile.ZipFile(reader) as archive:
        names = archive.namelist()
        configs = [name for name in names if name.lower().endswith((".yaml", ".yml"))]
        if configs:
            if len(configs) != 1:
                raise ValueError("Ambiguous Dangerous Items class config")
            config = yaml.safe_load(archive.read(configs[0]))
            classes = config["names"]
            if isinstance(classes, list):
                classes = dict(enumerate(classes))
            knife_class = next(int(key) for key, value in classes.items() if value.lower() == "knife")
            mapping_status = "source YAML"
        else:
            if knife_class_override is None or not (RAW / "dangerous-class-probe.json").exists():
                raise ValueError("Missing source class map; make visual class probe before review")
            knife_class = knife_class_override
            classes = {knife_class: "knife (visual working hypothesis)"}
            mapping_status = "review overlay working hypothesis; human class-map confirmation required"
        annotations = {}
        labels_by_split = defaultdict(list)
        for name in names:
            if name.lower().endswith(".txt") and "/labels/" in name:
                split = next((part for part in Path(name).parts if part in {"train", "valid", "val", "test"}), "unknown")
                labels_by_split[split].append(name)
        # A first-review pack is not an inventory of every label. Reading all
        # ~8k labels through a remote ZIP wastes bandwidth and makes the site
        # wait for hours. Inspect a small, seeded subset per original split.
        labels = [name for split in sorted(labels_by_split)
                  for name in seeded(labels_by_split[split])[:40]]
        for scanned, label in enumerate(labels, 1):
            if scanned % 20 == 0:
                print(f"Dangerous Items label probe {scanned}/{len(labels)}", flush=True)
            text = archive.read(label).decode("utf-8-sig")
            image_prefix = str(Path(label).with_suffix("")).replace("\\", "/").replace("/labels/", "/images/")
            images = [image_prefix+ext for ext in (".jpg", ".png", ".jpeg", ".JPG") if image_prefix+ext in names]
            if len(images) != 1:
                continue
            path = images[0]
            positive = any(line.split() and int(line.split()[0]) == knife_class for line in text.splitlines())
            original_split = next((part for part in Path(label).parts if part in {"train", "valid", "val", "test"}), "unknown")
            annotations[path] = (text, original_split)
            groups[(original_split, positive)].append(path)
        queues = [seeded(paths) for _, paths in sorted(groups.items())]
        chosen = []
        while len(chosen) < 100 and any(queues):
            for queue in queues:
                if queue and len(chosen) < 100:
                    chosen.append(queue.pop(0))
        samples = [{"image_path": path, "bytes": archive.read(path), "yolo": annotations[path][0],
                    "knife_class": knife_class, "original_split": annotations[path][1]} for path in chosen]
    return write_pack("dangerous-items", samples, {"license": "CC BY 4.0; Zenodo record 16422779", "class_map": classes,
                                                   "class_mapping_status": mapping_status,
                                                   "archive_checksum_declared": record["files"][0]["checksum"], "full_archive_checksum_verified": False,
                                                   "source_url": reader.url, "range_bytes": reader.downloaded,
                                                   "source_label_counts_by_split": {split: len(paths) for split, paths in labels_by_split.items()},
                                                   "scanned_label_strata": {str(key): len(value) for key, value in groups.items()},
                                                   "selection": "up to 40 seeded labels per original split, then up to 100 original split x knife-positive review samples; not representative of full source; no training import"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=["archives", "simuletic", "dasci", "legacy", "us_mock", "open_images", "dangerous_inventory", "dangerous_probe", "dangerous_items"])
    parser.add_argument("--legacy-csv", type=Path)
    parser.add_argument("--knife-class", type=int)
    args = parser.parse_args()
    if args.source == "archives":
        archives()
    elif args.source == "dangerous_items":
        print(json.dumps(dangerous_items(args.knife_class)))
    elif args.source == "legacy":
        print(json.dumps(legacy(args.legacy_csv)))
    else:
        print(json.dumps(globals()[args.source]()))
