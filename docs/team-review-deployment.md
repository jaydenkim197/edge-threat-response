# PC13 팀 데이터셋 웹 검수

상태: PC13 서버·시작 작업 및 외부 HTTPS 로그인·목록·이미지 접근 통제 `VERIFIED`. 팀원 계정의 실제 판정 저장·재접속과 재부팅 후 자동 복구는 아직 `NOT VERIFIED`. 표본 검수 자체와 데이터 채택은 별도다.

## 팀원 사용법

1. [팀 검수 사이트](https://yu-desktop-97msr1i.tail37c267.ts.net/)에 접속한다.
2. 본인에게 발급된 접속 코드로 로그인한다.
3. 후보를 고른 뒤 CCTV형 장면인지와 칼 라벨이 정상인지 답한다. `문제 있음`은 메모를 쓴다.
4. 저장 문구를 확인하고 `다음 미검수 받기`를 누른다. 배정은 PC13에서 관리하므로 같은 미검수 이미지를 여러 팀원에게 나눠주지 않는다.

관리자 bootstrap 접속 코드는 **ignored** `secrets/team-review-admin.txt`에 있다. 관리자 계정은 현황과 개인 코드 발급·해제에만 사용한다. 관리자가 직접 검수하려면 실제 본인 이름으로 개인 계정을 발급한다. 코드는 Git/채팅에 게시하지 않는다. 접속을 해제하면 기존 로그인 세션도 다음 요청부터 막힌다.

팀원에게 Python, Tailscale, 원본 파일, CSV나 GitHub 계정이 필요하지 않다. 원본 이미지·판정·수정 이력은 PC13에 저장된다. HTTPS 역방향 전달 중 요청한 이미지가 팀원의 브라우저로 전송되는 것은 사이트 기능의 일부다.

## 후보 화면과 한계

| 후보 | 첫 웹 검수 표본 | 용도·현재 제한 |
|---|---:|---|
| SOHAS | 100 | 주력 실사 후보. 기존 인간 판정 6장/history 40건을 일관된 DB 백업으로 PC13에 이전. CC 표기 충돌·원본 좌표 확인 필요 |
| DaSCI unique | 93 | SOHAS와 byte-identical 1,985장은 제외. Near-duplicate와 권리 gate는 남음 |
| Simuletic | 114 | 합성 CCTV 시점. 실사 성능 증거가 아님 |
| US Mock Attack | 100 | Cam1/Cam5/Cam7 및 knife annotation 유무 층화. 연속 영상의 사건 정답을 대신하지 않음 |
| Open Images | 30 | validation metadata에서 knife positive만. 원본 개별 이미지 권리·라벨 완전성 재검수 필요 |
| Legacy MIDAS | 128 | 팀원의 독립 L0 검수 표본. 신규 source 승인과 별개 |
| Dangerous Items | 100 | 공식 Zenodo API CC BY 4.0. 120개 label을 seeded split별로 살펴 뽑은 100장·임시 knife 객체 19개. ZIP에 class YAML이 없어 visual probe에서 raw ID `1=knife`를 작업 가설로 둔다. 박스 검수는 임시 매핑이며 학습 전 사람의 class-map 확인 필요 |
| ACF Knife | 접근 대기 | 논문이 가리킨 원 저장소가 404. 제3자 재배포본을 원본으로 대체하지 않음 |

현재 **8후보 중 7개 표본 화면 준비**, ACF만 원본 부재로 잠겨 있다. 첫 표본은 source 품질을 보는 작업량 단위다. 이를 근거로 전체 source를 채택하거나 10월 말 실험 데이터로 승인하지 않는다. Dangerous `raw ID 1`은 2026-10-04 임시 visual probe 3장의 관찰 결과이며 공식 class map을 뜻하지 않는다. Dangerous 전체 1.4 GB ZIP은 내려받지 않고 공식 archive의 HTTP Range 45,209,628 bytes만 읽었다. 전체 archive checksum은 미검증이고, 표본의 자체 SHA-256·원 경로·원 split은 보존했다. 현재 표본 인벤토리는 PC13의 `data/review/` 및 `data/source-audit/team-review-20261003/`에 있다.

## PC13 운영

- 코드 checkout: `C:\Class6\edge-threat-response`. 원본 아카이브·검수 pack·DB는 ignored `data/`; 모델은 ignored `runs/`/`*.pt`에 둔다. GitHub에는 코드와 사용법만 올라간다.
- 인증 앱: `edge_threat_response.dataset.team_review`, Flask 3.1.3 + Waitress 3.0.2. PC13 `127.0.0.1:8770`만 listen한다. Tailscale Funnel은 HTTPS를 앞단에서 종료한다. 공용 포트포워딩과 LAN bind는 필요 없다.
- Windows 작업 스케줄러 `ETR-Team-Review`: 부팅 시 사용자 PC13 계정의 S4U 제한 권한으로 앱을 재시작한다. 2026-10-04 수동 작업 시작·로컬 로그인 HTTP 200을 확인했다. 실제 재부팅 시험은 아직 하지 않았다.
- PC13 `tailscale set --unattended=true` 적용. 2026-10-04 tailnet 관리자가 Funnel을 승인했고 `tailscale funnel --bg --yes 8770`로 HTTPS 주소를 활성화했다. `tailscale funnel status`에서 백그라운드 proxy를 확인했다. 실제 재부팅 후 Funnel·앱 복구는 아직 시험하지 않았다.
- 설정·비밀값: ignored `data/review/team-server/config.json`, `secrets/team-review-session.key`, `secrets/team-review-admin.txt`. README나 명령 로그에 코드 값을 넣지 않는다. `tools/configure_team_review.py --public-url https://<actual-host>`는 기존 사용자·세션 secret·검수 DB를 덮어쓰지 않고 catalog만 갱신한다. 서버는 변경된 catalog를 재시작 후 읽는다.
- DB: `data/review/team-server/team.sqlite3`는 계정/배정, 각 pack의 `human-review.sqlite3`는 판정/이력이다. 30분마다 SQLite backup API로 `data/review/team-server/backups/`에 일관된 사본을 추가한다. **같은 PC 디스크의 백업은 디스크 고장 대비가 아니다.** 승인된 별도 저장소에 주기적으로 복사하는 운영 절차는 아직 미설정이다.
- 기존 SOHAS 이전은 `tools/migrate_review_db.py`로만 한다. 같은 pack hash와 비어 있는 목적지 DB를 검사하고 version/history를 그대로 옮기며, 어느 한쪽에도 판정이 있으면 자동 병합하지 않는다. 이 기록 이후 노트북의 이전 SOHAS URL에 새로 쓰면 PC13과 판정이 갈라진다. 중앙 사이트를 사용하기 시작하면 기존 로컬 URL은 사용하지 않는다.
- 서비스 변경·재시작 후 PC13 저장소에서 `$env:PYTHONPATH="src"; .\.venv-ml\Scripts\python.exe tools\check_team_review.py`를 실행하면 **실제 pack 각각**의 관리자 로그인·목록·첫 이미지 로딩을 판정 변경 없이 점검하고 건수만 출력한다. 접속 코드는 출력하지 않는다. 이는 PC13 내부 앱 테스트이지 외부 HTTPS 브라우저 검증을 대체하지 않는다.

## 배포·검증 기록

- PC13 Tailscale v1.102.4, C 여유 약 144.5 GiB(작업 전 관찰). Windows Python 3.12.4, RTX 3060 학습 venv의 optional review-server dependencies를 설치했다. 검수 자체는 GPU를 사용하지 않는다.
- PC13 local `GET /login` 200, 인증 없는 `GET /api/catalog` 및 SOHAS/Dangerous 이미지 URL 401. 7/8 후보 pack으로 다시 설정하고 시작 작업을 재실행했다. 읽기 전용 실제 config smoke는 **관리자 로그인→7개 pack 목록/첫 이미지 200**과 SOHAS 기존 판정 6건을 확인했고, 판정·계정은 변경하지 않았다. 노트북과 PC13에서 team tests 4개, 전체 로컬 테스트 83개 통과. Session cookie, Host/Origin/CSRF, role·배정 충돌, history/backup을 fixture에서 검증했다.
- Funnel 승인 후 외부 `GET /login` 200, 비인증 catalog·Dangerous 이미지 401, 관리자 HTTPS 로그인 후 catalog의 준비 후보 7개와 Dangerous 첫 이미지 200/79,893 bytes를 확인했다. 관리자 로그인은 판정을 쓰지 않는다. 팀원 개인 계정의 실제 첫 판정 저장·새로고침/재접속은 첫 검수자가 수행할 때 확인해야 한다.
- 원본 권리·좌표·중복/session gate, 사람 검수, 학습 채택은 별개다. User team accounts는 실제로 발급하기 전까지 관리자 1개뿐이다.
