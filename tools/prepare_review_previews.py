"""Build small review-only derivatives bound to an immutable image pack."""
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image


def prepare(pack: Path, output: Path):
    pack, output = pack.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(pack):
        raise ValueError("Use a new output folder outside the source pack.")
    evidence = (pack / "image-evidence.jsonl").read_bytes()
    digest = hashlib.sha256((pack / "review.csv").read_bytes() + evidence).hexdigest()
    rows = [json.loads(line) for line in evidence.splitlines() if line]
    output.parent.mkdir(parents=True, exist_ok=True)
    original_bytes = 0
    with TemporaryDirectory(prefix=".review-previews-", dir=output.parent) as temporary:
        staging = Path(temporary) / "previews"
        staging.mkdir()
        for index, row in enumerate(rows):
            path = (pack / row["image_file"]).resolve()
            if not path.is_relative_to(pack):
                raise ValueError("Image escapes its source pack.")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row["image_sha256"]:
                raise ValueError("Source image changed.")
            with Image.open(path) as image:
                if image.size != (row["width"], row["height"]):
                    raise ValueError("Source dimensions changed.")
                image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                image.convert("RGB").save(staging / f"{index}.jpg", quality=90, subsampling=0)
            original_bytes += len(raw)
        manifest = {"pack_hash": digest, "count": len(rows), "max_edge": 1920,
                    "original_bytes": original_bytes,
                    "preview_bytes": sum(path.stat().st_size for path in staging.glob("*.jpg"))}
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        staging.rename(output)
    print(json.dumps(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    prepare(args.pack, args.output)
