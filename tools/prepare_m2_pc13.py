"""Prepare train-only M2 from frozen M1 and the already acquired OI train subset.

No downloads, live review DB access, automatic repairs, resplitting, or training.
"""
import argparse
import json
from pathlib import Path

from edge_threat_response.dataset.followup import open_images_candidates, prepare_followup, read_rows
from edge_threat_response.dataset.image_screening import image_signature
from edge_threat_response.training import _sha256_file, _write_json


def prepare(root: Path, output: Path) -> dict:
    source = root/"data/source-audit/open-images-train-20261105/candidates.jsonl"
    guard = root/"data/review/team-candidates-20261003/us-mock"
    evidence = guard/"image-evidence.jsonl"
    inputs = {str(p): _sha256_file(p) for p in (source, evidence)}
    protected = []
    for row in read_rows(evidence):
        path = (guard/row["image_file"]).resolve()
        if not path.is_relative_to(guard.resolve()):
            raise ValueError("Protected image must remain inside its immutable pack")
        protected.append({**image_signature(path, expected_sha256=row["image_sha256"]),
            "record_id": "us-guard/"+row["image_path"], "dataset_id": "us-mock-protected",
            "image_file": str(path), "original_split": "protected_development"})
    result = prepare_followup(
        baseline=root/"data/processed/raw-real-20261105-v3/inventory.jsonl",
        signatures=root/"data/processed/raw-real-20261105-v2/signatures.jsonl",
        pairs=root/"data/processed/raw-real-20261105-v2/similarity-pairs.jsonl",
        quality_snapshot=root/"data/work/reviewed-next-training-20261106/review-evidence-snapshot.jsonl",
        candidates=open_images_candidates(source), protected=protected, output=output,
        expected_quality_exclusions=88)
    if inputs != {str(p): _sha256_file(p) for p in (source, evidence)}:
        raise ValueError("Source/protected acquisition evidence changed")
    result["additional_input_sha256"] = inputs
    _write_json(output/"summary.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root.resolve(), args.output_dir.resolve()), indent=2))
