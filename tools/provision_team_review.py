"""Issue named review accounts and save one-time codes outside Git."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from edge_threat_response.dataset.team_review import TeamDatabase


ROOT = Path(__file__).resolve().parents[1]


def provision(config_path: Path, output: Path, names: list[str]) -> int:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    normalized = [name.strip() for name in names]
    if not normalized or any(not name or "\t" in name or "\n" in name for name in normalized):
        raise ValueError("At least one single-line name is required")
    if len(normalized) != len(set(normalized)):
        raise ValueError("Duplicate names in request")
    team = TeamDatabase(Path(config["database"]))
    with team.connect() as connection:
        existing = {row[0] for row in connection.execute("SELECT name FROM users WHERE active=1")}
    if existing.intersection(normalized):
        raise ValueError("One or more names already have active accounts; no code was issued")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as file:
        file.write(f"사이트: {config['public_url']}\n각자 자신의 코드만 전달하세요. Git/공용 문서에는 올리지 마세요.\n\n")
        file.flush()
        os.fsync(file.fileno())
        for name in normalized:
            user = team.create_user(name)
            file.write(f"{user['name']}\t{user['code']}\n")
            file.flush()
            os.fsync(file.fileno())
    return len(normalized)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="+")
    parser.add_argument("--config", type=Path, default=ROOT / "data/review/team-server/config.json")
    parser.add_argument("--output", type=Path, default=ROOT / "secrets/team-review-personal-codes.txt")
    args = parser.parse_args()
    count = provision(args.config, args.output, args.names)
    print(f"Issued {count} personal accounts; codes saved outside Git: {args.output}")
