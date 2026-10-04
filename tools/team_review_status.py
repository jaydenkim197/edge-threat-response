"""Read-only counts/integrity and optional consistent backups; no user data output."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path

from edge_threat_response.dataset.review_web import review_verdict


def inspect(config_path: Path, backup: Path | None = None) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if backup:
        backup.mkdir(parents=True, exist_ok=False)
        (backup / "config.json").write_bytes(config_path.read_bytes())
    report = {"datasets": {}, "databases": {}}
    paths, knife_counts = [("team", Path(config["database"]))], {}
    for entry in config["datasets"]:
        if not entry.get("review_dir"):
            report["datasets"][entry["id"]] = {"prepared": 0, "blocked": True}
            continue
        batches = [{"id": "initial", "review_dir": entry["review_dir"]}, *entry.get("review_batches", [])]
        details, offset = [], 0
        for batch in batches:
            root = Path(batch["review_dir"])
            evidence = [json.loads(line) for line in (root / "image-evidence.jsonl").read_text(encoding="utf-8").splitlines() if line]
            with (root / "review.csv").open(encoding="utf-8-sig", newline="") as handle:
                if len(list(csv.DictReader(handle))) != len(evidence):
                    raise ValueError("Evidence/CSV alignment failure")
            details.append({"batch": batch["id"], "offset": offset, "prepared": len(evidence)})
            offset += len(evidence)
            key = entry["id"] if batch["id"] == "initial" else entry["id"]+"--"+batch["id"]
            paths.append((key, root / "human-review.sqlite3"))
            knife_counts[key] = [item["knife_count"] for item in evidence]
        report["datasets"][entry["id"]] = {"prepared": offset, "batches": details}
    for name, path in paths:
        with closing(sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)) as connection:
            connection.execute("BEGIN")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("DB integrity failure")
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            result = {"integrity": "ok", "tables": {}}
            for table in sorted(tables):
                rows = list(connection.execute(f'SELECT * FROM "{table}" ORDER BY 1'))
                result["tables"][table] = {"count": len(rows), "sha256": hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()}
            if name != "team":
                verdicts = Counter(review_verdict(json.loads(payload), knife_counts[name][sample]) for sample, payload in connection.execute("SELECT sample,payload FROM reviews"))
                result["verdicts"] = dict(verdicts)
            if backup:
                with closing(sqlite3.connect(backup / f"{name}.sqlite3")) as target:
                    connection.backup(target)
                    if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise ValueError("Backup integrity failure")
            report["databases"][name] = result
    for pack, item in report["datasets"].items():
        if item.get("blocked"):
            continue
        item.update(reviewed=0, held=0, history=0)
        for batch in item["batches"]:
            key = pack if batch["batch"] == "initial" else pack+"--"+batch["batch"]
            db = report["databases"][key]
            batch["reviewed"] = db["tables"]["reviews"]["count"]
            item["reviewed"] += batch["reviewed"]
            item["held"] += sum(count for verdict, count in db["verdicts"].items() if verdict != "ok")
            item["history"] += db["tables"]["history"]["count"]
    if backup:
        (backup / "status.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect(args.config, args.backup)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["datasets"], ensure_ascii=True))
