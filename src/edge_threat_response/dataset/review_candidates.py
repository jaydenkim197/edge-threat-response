"""Read-only review snapshots and unapproved image-level training candidates."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .review_web import review_verdict
from ..training import _git_commit, _sha256_file, _write_json


BLOCKERS = ["source_rights", "coordinate_convention", "annotation_audit", "near_duplicates",
            "source_session_groups", "group_aware_split", "recipe_approval"]
ROLES = {"real_training", "baseline_or_real_augmentation", "synthetic_ablation", "external_evaluation"}


@contextmanager
def readonly_database(path: Path):
    # Do not instantiate ReviewStore/create_app: their constructors migrate/write DBs.
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        if list(connection.execute("PRAGMA quick_check")) != [("ok",)]:
            raise ValueError("Review database integrity check failed")
        yield connection
        if connection.total_changes:
            raise ValueError("Read-only snapshot unexpectedly changed a database")
    finally:
        connection.close()


def _fingerprint(connection, table: str) -> dict:
    if table not in {"reviews", "history", "metadata", "assignments", "users", "review_batches"}:
        raise ValueError("Unsupported snapshot table")
    rows = sorted(tuple(row) for row in connection.execute(f"SELECT * FROM {table}"))
    digest = hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {"rows": len(rows), "logical_sha256": digest}


def _path(value: str, base: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("Missing input path")
    path = Path(value)
    return (path if path.is_absolute() else base / path).resolve()


def _read_pack(root: Path, dataset: str, batch: str, offset: int, policy: dict):
    csv_bytes = (root / "review.csv").read_bytes()
    evidence_bytes = (root / "image-evidence.jsonl").read_bytes()
    pack_hash = hashlib.sha256(csv_bytes + evidence_bytes).hexdigest()
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
    evidence = [json.loads(line) for line in evidence_bytes.decode("utf-8-sig").splitlines() if line.strip()]
    if not rows or len(rows) != len(evidence):
        raise ValueError("Review CSV/evidence must be nonempty and aligned")
    summary_file = root / "summary.json"
    source_summary = json.loads(summary_file.read_text(encoding="utf-8-sig")) if summary_file.is_file() else {}
    if not isinstance(source_summary, dict):
        raise ValueError("Review pack summary must be an object")
    database = root / "human-review.sqlite3"
    with readonly_database(database) as connection:
        registered = connection.execute("SELECT value FROM metadata WHERE key='pack_hash'").fetchone()
        if not registered or registered[0] != pack_hash:
            raise ValueError("Review DB belongs to another pack")
        saved = {sample: (version, json.loads(payload)) for sample, version, payload in
                 connection.execute("SELECT sample,version,payload FROM reviews")}
        if any(type(sample) is not int or not 0 <= sample < len(rows) or type(version) is not int or version < 1
               or not isinstance(payload, dict) for sample, (version, payload) in saved.items()):
            raise ValueError("Invalid saved review identity/version/payload")
        tables = {name: _fingerprint(connection, name) for name in ("metadata", "reviews", "history")}
    records = []
    for index, (row, item) in enumerate(zip(rows, evidence)):
        if not isinstance(item, dict):
            raise ValueError("Review image evidence must be an object")
        if item.get("sample_no") != index + 1 or item.get("image_path") != row.get("image_path"):
            raise ValueError("Review sample identity mismatch")
        image = _path(item["image_file"], root)
        if not image.is_relative_to(root) or not image.is_file() or _sha256_file(image) != item["image_sha256"]:
            raise ValueError("Review image is missing, changed or outside its pack")
        width, height, count = item.get("width"), item.get("height"), item.get("knife_count")
        if any(type(value) is not int or value <= 0 for value in (width, height)) or type(count) is not int or count < 0:
            raise ValueError("Invalid review dimensions/knife count")
        boxes = item.get("knife_boxes_xyxy_raw")
        if not isinstance(boxes, list) or len(boxes) != count:
            raise ValueError("Review box count mismatch")
        areas = []
        for box in boxes:
            if not isinstance(box, list) or len(box) != 4 or any(type(v) not in {int, float} or not math.isfinite(v) for v in box):
                raise ValueError("Invalid raw review bbox")
            left, top, right, bottom = box
            if not (0 <= left < right <= width and 0 <= top < bottom <= height):
                raise ValueError("Raw review bbox outside image")
            areas.append((right - left) * (bottom - top) / (width * height))
        version, review = saved.get(index, (0, {}))
        verdict = review_verdict(review, count) if version else "unreviewed"
        if verdict not in {"ok", "problem", "unclear", "unreviewed"}:
            raise ValueError("Unknown saved verdict")
        reasons = []
        if not version:
            status = "unreviewed"
        elif verdict != "ok":
            status, reasons = "hold_review", ["annotation_" + verdict]
        elif (not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip()
              or review.get("label_quality") != "good" or review.get("bbox_completeness") != "yes"
              or review.get("exclude") != "no" or (not count and review.get("negative_knife_absence") != "yes")):
            status, reasons = "hold_review", ["incomplete_or_conflicting_review_evidence"]
        elif policy["knife_mapping"] != "source_defined" or "hypothesis" in str(source_summary.get("class_mapping_status", "")).lower():
            status, reasons = "hold_mapping", ["knife_class_mapping_unconfirmed"]
        elif (policy.get("training_original_splits") is not None
              and item.get("original_split", row.get("original_split", "unknown")) not in policy["training_original_splits"]):
            status, reasons = "hold_source_split", ["source_partition_not_selected_for_training"]
        elif policy["role"] == "external_evaluation":
            status = "evaluation_candidate"
        elif policy["role"] == "synthetic_ablation":
            status = "synthetic_candidate"
        else:
            status = "candidate_positive" if count else "candidate_negative"
        lineage = {key: item.get(key, source_summary.get(key)) for key in
                   ("source_revision", "image_git_blob", "xml_sha256", "label_sha256", "source_group", "filename_group_proxy")}
        # No reviewer names or free-text notes in the candidate manifest/printed summary.
        record = {"schema_version": 1, "record_id": f"{dataset}/{batch}/{index}", "dataset_id": dataset,
                  "batch_id": batch, "global_sample_id": offset + index, "local_sample_id": index,
                  "pack_hash": pack_hash, "image_path": item["image_path"], "image_file": image.as_posix(),
                  "image_sha256": item["image_sha256"], "width": width, "height": height,
                  "knife_count": count, "annotation_role": "positive" if count else "annotation_negative",
                  "raw_boxes_xyxy": boxes, "diagnostic_normalized_bbox_areas": areas,
                  "coordinate_status": "unconfirmed_for_training", "source_role": policy["role"],
                  "original_split": item.get("original_split", row.get("original_split", "unknown")),
                  "lineage": lineage, "review_version": version, "review_verdict": verdict,
                  "review_schema": review.get("review_schema") or ("legacy" if version else None),
                  "review_payload_sha256": hashlib.sha256(json.dumps(review, sort_keys=True, ensure_ascii=False).encode()).hexdigest() if version else None,
                  "domain": review.get("domain") or "unreviewed", "candidate_status": status,
                  "hold_reasons": reasons, "training_approved": False, "approval_blockers": list(BLOCKERS)}
        records.append(record)
    provenance = {"dataset_id": dataset, "batch_id": batch, "offset": offset, "count": len(rows),
                  "pack_hash": pack_hash, "database": database.as_posix(), "tables": tables,
                  "summary_sha256": _sha256_file(summary_file) if summary_file.is_file() else None,
                  "database_writes": 0, "snapshotted_at": datetime.now(timezone.utc).isoformat()}
    return records, provenance


def collect_candidates(config_path: Path, policy_path: Path) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes.decode("utf-8-sig"))
    policy_bytes = policy_path.read_bytes()
    policy = json.loads(policy_bytes.decode("utf-8-sig"))
    if not isinstance(config, dict) or not isinstance(config.get("datasets"), list) or not config["datasets"]:
        raise ValueError("Review server config needs a nonempty dataset catalog")
    if not isinstance(policy, dict) or policy.get("schema_version") != 1 or not isinstance(policy.get("sources"), dict) or not policy.get("policy_id"):
        raise ValueError("Invalid review candidate policy")
    records, packs, unavailable, expected = [], [], [], []
    sources, roots = set(), []
    for entry in config["datasets"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError("Dataset catalog entry must have an ID")
        dataset = entry["id"]
        if not re.fullmatch(r"[a-z0-9-]{1,60}", dataset) or dataset in sources or dataset not in policy["sources"]:
            raise ValueError("Duplicate, invalid or unmapped dataset ID")
        sources.add(dataset)
        source_policy = policy["sources"][dataset]
        if not isinstance(source_policy, dict) or source_policy.get("role") not in ROLES or source_policy.get("knife_mapping") not in {"source_defined", "unconfirmed"}:
            raise ValueError("Invalid source role/mapping policy")
        splits = source_policy.get("training_original_splits")
        if splits is not None and (not isinstance(splits, list) or not splits or any(not isinstance(split, str) or not split for split in splits)):
            raise ValueError("Invalid source partition policy")
        if not entry.get("review_dir"):
            if entry.get("review_batches"):
                raise ValueError("Appended batches require an initial pack")
            unavailable.append(dataset)
            continue
        parts = [{"id": "initial", "review_dir": entry["review_dir"]}, *entry.get("review_batches", [])]
        offset, batch_ids, source_hashes = 0, set(), set()
        for part in parts:
            if not isinstance(part, dict) or not isinstance(part.get("id"), str):
                raise ValueError("Review batch must have an ID")
            batch = part["id"]
            if not re.fullmatch(r"[a-z0-9-]{1,60}", batch) or batch in batch_ids:
                raise ValueError("Invalid or duplicate batch ID")
            batch_ids.add(batch)
            root = _path(part["review_dir"], config_path.parent)
            roots.append(root)
            rows, provenance = _read_pack(root, dataset, batch, offset, source_policy)
            for row in rows:
                if row["image_sha256"] in source_hashes:
                    raise ValueError("Duplicate image within source batches")
                source_hashes.add(row["image_sha256"])
            expected.append((dataset, batch, offset, len(rows), provenance["pack_hash"]))
            records.extend(rows)
            packs.append(provenance)
            offset += len(rows)
    team_database = _path(config["database"], config_path.parent)
    with readonly_database(team_database) as connection:
        registry = [tuple(row) for row in connection.execute("SELECT pack,batch,offset,count,pack_hash FROM review_batches")]
        if sorted(registry) != sorted(expected):
            raise ValueError("Configured packs do not match deployed batch registry")
        team_tables = {table: _fingerprint(connection, table) for table in ("review_batches", "assignments", "users")}
    if config_path.read_bytes() != config_bytes or policy_path.read_bytes() != policy_bytes:
        raise ValueError("Configuration/policy changed during snapshot; rerun with a fresh output")
    groups = defaultdict(list)
    for row in records:
        groups[row["image_sha256"]].append(row)
    duplicates = []
    for digest, rows in groups.items():
        if len(rows) > 1:
            duplicates.append({"image_sha256": digest, "record_ids": [row["record_id"] for row in rows]})
            overlap = any(row["source_role"] == "external_evaluation" for row in rows)
            for row in rows:
                row["hold_reasons"].append("external_evaluation_overlap" if overlap else "cross_source_exact_duplicate")
                if row["candidate_status"] != "unreviewed":
                    row["candidate_status"] = "hold_duplicate"
    datasets = []
    for source in sorted(sources - set(unavailable)):
        rows = [row for row in records if row["dataset_id"] == source]
        datasets.append({"dataset_id": source, "prepared": len(rows), "reviewed": sum(row["review_version"] > 0 for row in rows),
                         "verdict_counts": dict(Counter(row["review_verdict"] for row in rows)),
                         "candidate_counts": dict(Counter(row["candidate_status"] for row in rows)),
                         "domain_counts": dict(Counter(row["domain"] for row in rows)),
                         "annotation_role_counts": dict(Counter(row["annotation_role"] for row in rows)),
                         "original_split_counts": dict(Counter(row["original_split"] for row in rows)),
                         "cross_counts": dict(Counter("|".join((row["domain"], row["review_verdict"], row["annotation_role"])) for row in rows)),
                         "training_approved": 0})
    return {"schema_version": 1, "status": "candidates_not_approved", "policy_id": policy["policy_id"],
            "snapshot_started_at": started, "snapshot_finished_at": datetime.now(timezone.utc).isoformat(),
            "snapshot_boundary": "Consistent transaction per database; not one atomic snapshot across all live databases",
            "git_commit": _git_commit(), "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
            "policy_sha256": hashlib.sha256(policy_bytes).hexdigest(), "datasets": datasets,
            "unavailable": unavailable, "prepared": len(records), "reviewed": sum(row["review_version"] > 0 for row in records),
            "training_approved": 0, "approval_blockers": BLOCKERS, "packs": packs,
            "team_database_tables": team_tables, "records": records, "duplicates": duplicates,
            "input_roots": [root.as_posix() for root in roots]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.output_dir.exists():
            raise ValueError("Candidate output must be a new directory")
        result = collect_candidates(args.config, args.policy)
        output = args.output_dir.resolve()
        if any(output.is_relative_to(Path(root)) for root in [*result["input_roots"], str(args.config.parent.resolve())]):
            raise ValueError("Candidate output cannot be inside an input pack or server config directory")
        output.mkdir(parents=True)
        records, duplicates = result.pop("records"), result.pop("duplicates")
        for name, rows in (("review-linked-manifest.jsonl", records),
                           ("training-candidates.jsonl", [row for row in records if row["candidate_status"] in {"candidate_positive", "candidate_negative"}]),
                           ("held.jsonl", [row for row in records if row["candidate_status"].startswith("hold_")]),
                           ("duplicates.jsonl", duplicates)):
            with (output / name).open("w", encoding="utf-8") as stream:
                for row in rows:
                    stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        result["cross_source_duplicate_groups"] = len(duplicates)
        _write_json(output / "summary.json", result)
        lines = ["# 웹 검수 → 미승인 학습 후보", "", "이 결과는 판정 snapshot이며 학습 승인/학습 dataset export가 아니다.", "",
                 "| Source | 준비 | 판정 | 정상 | 문제/모름 | 실사 후보 | 학습 승인 |", "|---|---:|---:|---:|---:|---:|---:|"]
        for row in result["datasets"]:
            counts, candidates = row["verdict_counts"], row["candidate_counts"]
            lines.append(f"| {row['dataset_id']} | {row['prepared']} | {row['reviewed']} | {counts.get('ok', 0)} | {counts.get('problem', 0)+counts.get('unclear', 0)} | {candidates.get('candidate_positive', 0)+candidates.get('candidate_negative', 0)} | 0 |")
        lines += ["", "Source별 권리·좌표·near duplicate·실제 session·split·recipe 승인과 materialization이 필요하다.",
                  "미검수/문제/모름·mapping 미확정·exact duplicate는 자동 승인하지 않는다. 후보 이외 source의 확대/촬영도 별도다."]
        (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({key: result[key] for key in ("status", "prepared", "reviewed", "training_approved", "datasets", "unavailable")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
