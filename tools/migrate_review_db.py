"""Import a consistent local snapshot into an empty server DB; never overwrite reviews."""
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path

from edge_threat_response.dataset.review_web import ReviewStore


def migrate(incoming: Path, review_dir: Path):
    store = ReviewStore(review_dir)
    with closing(sqlite3.connect(f"{incoming.resolve().as_uri()}?mode=ro", uri=True)) as origin:
        if origin.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Incoming database integrity error")
        if origin.execute("SELECT value FROM metadata WHERE key='pack_hash'").fetchone()[0] != store.pack_hash:
            raise ValueError("Migration pack hash mismatch")
        rows = list(origin.execute("SELECT sample,version,payload FROM reviews"))
        history = list(origin.execute("SELECT sequence,sample,payload FROM history"))
        with store.connect() as target:
            target.execute("BEGIN IMMEDIATE")
            if target.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] or target.execute("SELECT COUNT(*) FROM history").fetchone()[0]:
                raise ValueError("Destination has reviews; reconcile explicitly, never overwrite")
            target.executemany("INSERT INTO reviews VALUES (?,?,?)", rows)
            target.executemany("INSERT INTO history VALUES (?,?,?)", history)
    print(f"Imported {len(rows)} reviews and {len(history)} history entries; originals retained")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--review-dir", type=Path, required=True)
    args = parser.parse_args()
    migrate(args.incoming, args.review_dir)
