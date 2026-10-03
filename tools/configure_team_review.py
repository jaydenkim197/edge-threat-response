"""Initialize ignored deployment files without printing or committing credentials."""
import argparse
import json
import secrets
from pathlib import Path

from edge_threat_response.dataset.team_review import TeamDatabase

ROOT = Path(__file__).resolve().parents[1]


def configure(public_url: str, reviewer_login: str | None = None):
    folder = ROOT / "data/review/team-server"
    folder.mkdir(parents=True, exist_ok=True)
    config_path = folder / "config.json"
    previous = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    reviewer_login = reviewer_login or previous.get("reviewer_login", "code")
    secret_dir = ROOT / "secrets"
    secret_dir.mkdir(exist_ok=True)
    secret_file = secret_dir / "team-review-session.key"
    if not secret_file.exists():
        secret_file.write_text(secrets.token_urlsafe(48), encoding="ascii")
    database = folder / "team.sqlite3"
    team = TeamDatabase(database)
    with team.connect() as connection:
        empty = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    if empty:
        admin = team.create_user("프로젝트 관리자", admin=True)
        (secret_dir / "team-review-admin.txt").write_text(
            f"사이트: {public_url}\n관리자 접속 코드: {admin['code']}\n"
            "관리자 코드 자체는 팀원에게 공유하지 마세요.\n"
            "사이트에서 실제 검수자 이름으로 개인 코드를 발급하세요.\n", encoding="utf-8")
    base = ROOT / "data/review/team-candidates-20261003"
    catalog = [
        ("sohas", "SOHAS", ROOT / "data/review/sohas-click-review-20261003", "신규 실사·hard negative 주력 후보", "https://github.com/ari-dasci/OD-WeaponDetection", "100장 첫 표본. CC notice 충돌과 VOC 좌표·라벨 완전성은 별도 확인."),
        ("dasci-unique", "DaSCI · 고유 후보", base / "dasci-unique", "SOHAS에 없는 byte-unique 이미지 검수", "https://github.com/ari-dasci/OD-WeaponDetection", "중복 1,985장은 반복 검수하지 않음. Near duplicate 여부는 아직 미확정."),
        ("simuletic", "Simuletic CCTV", base / "simuletic", "Synthetic viewpoint 보조 후보", "https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset", "최대 114장 전체. 합성자료이며 실사 성능을 증명하지 않음."),
        ("us-mock", "US Mock Attack", base / "us-mock", "외부 CCTV 평가 후보 · 학습에는 넣지 않음", "https://deepknowledge-us.github.io/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset/", "카메라·sequence 기반 첫 표본. 이미지 검수만으로 event ground truth가 생기지 않음."),
        ("dangerous-items", "Dangerous Items", base / "dangerous-items", "작은 칼·가림 등 gap-filling 후보", "https://zenodo.org/records/16422779", "공식 API CC BY 4.0. raw class 1=knife는 3장씩 본 임시 추정이며 공식 class map·학습 승인이 아님. 원래 random split도 최종 연구 분할이 아님."),
        ("open-images", "Open Images", base / "open-images", "웹 이미지 기반 제한적 보강 후보", "https://storage.googleapis.com/openimages/web/index.html", "개별 source URL·license를 보존한 첫 표본. CCTV 주력으로 자동 채택하지 않음."),
        ("legacy", "Legacy MIDAS", base / "legacy", "팀원 L0 재현·기존 128장 검수", "https://github.com/YEOUL0520/Crime_Prediction", "기존 표본을 웹으로 제공. 다른 팀원의 독립 L0 트랙."),
        ("acf", "ACF Knife", base / "acf", "외부 CCTV 이미지 평가 후보", "https://github.com/iCUBE-Laboratory/The-Armed-CCTV-Footage", "원 저장소 404. 대체 배포본의 provenance를 임의로 인정하지 않음."),
    ]
    entries = []
    outcomes_file = base / "outcomes.json"
    outcomes = json.loads(outcomes_file.read_text()) if outcomes_file.exists() else {}
    for key, name, path, role, source, note in catalog:
        entry = {"id": key, "name": name, "role": role, "source_url": source, "note": note}
        if (path / "image-evidence.jsonl").exists() and (path / "review.csv").exists():
            entry["review_dir"] = str(path)
        else:
            entry["reason"] = outcomes.get(key, "원본/라벨 확보·검증 대기" if key != "acf" else "공식 원 저장소 404 · 파일 확보 필요")
        entries.append(entry)
    config = {"public_url": public_url, "secret_file": str(secret_file), "database": str(database), "datasets": entries,
              "reviewer_login": reviewer_login}
    (folder / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ready": sum("review_dir" in e for e in entries), "listed": len(entries),
                      "config": str(folder / "config.json"), "admin_code_file": str(secret_dir / "team-review-admin.txt")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-url", required=True)
    parser.add_argument("--reviewer-login", choices=("name", "code"))
    args = parser.parse_args()
    configure(args.public_url, args.reviewer_login)
