"""Read-only authenticated deployment smoke without printing access codes."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from edge_threat_response.dataset.team_review import create_app


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "data/review/team-server/config.json")
    parser.add_argument("--admin-file", type=Path, default=ROOT / "secrets/team-review-admin.txt")
    args = parser.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    origin = config["public_url"]
    code_line = next(line for line in args.admin_file.read_text(encoding="utf-8").splitlines()
                     if line.startswith("관리자 접속 코드: "))
    code = code_line.split(": ", 1)[1]
    app = create_app(args.config)
    app.testing = True
    client = app.test_client()
    page = client.get("/admin/login", base_url=origin)
    assert page.status_code == 200
    token_match = re.search(r'name="csrf" value="([^"]+)"', page.get_data(as_text=True))
    assert token_match, "Login CSRF field missing"
    token = token_match.group(1)
    login = client.post("/admin/login", base_url=origin, headers={"Origin": origin},
                        data={"code": code, "csrf": token})
    assert login.status_code == 302, "Admin login failed"

    response = client.get("/api/catalog", base_url=origin)
    assert response.status_code == 200
    catalog = response.json["datasets"]
    ready = [entry for entry in catalog if entry["available"]]
    for entry in ready:
        pack = entry["id"]
        items = client.get(f"/api/items?dataset={pack}", base_url=origin)
        assert items.status_code == 200
        assert len(items.json["items"]) == entry["total"] and entry["total"] > 0
        store = app.extensions["review_stores"][pack]
        offsets = [offset for _, offset, _ in store.parts] if hasattr(store, "parts") else [0]
        for offset in offsets:
            assert client.get(f"/api/packs/{pack}/images/{offset}", base_url=origin).status_code == 200

    print(json.dumps({"ready": len(ready), "listed": len(catalog),
                      "samples": {entry["id"]: entry["total"] for entry in ready},
                      "reviewed": {entry["id"]: entry["reviewed"] for entry in ready}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
