# PC13 팀 데이터셋 웹 검수

상태: PC13 공개 이름 선택·공통 두 질문·모바일 화면·홈 화면 추가 metadata `VERIFIED`(외부 HTTPS·browser). Chrome/Android 화면 및 WebKit/iPhone 화면의 합성 fixture 저장·재접속·이어하기 `VERIFIED`; 실제 휴대폰 홈 화면 설치와 PC13 재부팅 복구는 미검증이다. 표본 검수 자체와 데이터 채택은 별도다.

## 팀원 사용법

1. [팀 검수 사이트](https://yu-desktop-97msr1i.tail37c267.ts.net/)에 접속한다.
2. 드롭다운에서 본인 이름을 선택하고 `검수 시작`을 누른다. 비밀번호·개인 코드는 필요 없다. 이름 선택은 브라우저에 30일간 유지하며, 쿠키를 삭제하거나 새 브라우저를 쓰면 다시 선택한다. 이름을 바꾸려면 후보 목록의 `이름 바꾸기`를 누른다.
3. 어떤 후보든 **같은 두 질문**에 답한다: `CCTV형 / 그 외 / 모르겠음`, `라벨 정상 / 문제 있음 / 모르겠음`. `문제 있음`일 때 메모 칸이 나타나며 한 줄을 쓴다. 검수자 이름은 선택한 이름으로 자동 입력된다.
4. 두 답을 고르면 자동 저장된다. `자동 저장됨`을 확인하고 `다음 미검수 받기`를 누른다. 후보를 열면 첫 미검수 이미지가 자동 배정된다. 배정은 PC13에서 관리하므로 같은 미검수 이미지를 여러 팀원에게 나눠주지 않는다. CSV 제출·별도 파일 업로드는 필요 없다.

2026-10-04 사용자 결정으로 **공개 링크 → 이름 선택** 방식을 채택했다. 이름 선택은 본인 인증이 아니며 링크를 아는 사람이 등록된 이름을 선택할 수 있다. 검수 이력의 이름은 self-declared identity다. 이름·계정 DB는 ignored runtime에만 두고 Git에 기록하지 않는다.

관리자는 `/admin/login`에서 기존 관리자 코드를 사용한다(**ignored** `secrets/team-review-admin.txt`). 관리자 API·팀원 등록/사용 중지는 이름 선택만으로 접근할 수 없고 관리자 세션은 8시간 뒤 만료된다. 본인의 검수는 본인 이름으로 시작한다. 이전 개인 코드는 현재 이름 선택 화면에서 사용하지 않는다. 기존 계정·배정·판정 DB는 그대로 유지한다.

## 휴대폰 홈 화면에서 시작하기

- **아이폰**: Safari로 사이트를 열고 `공유 → 홈 화면에 추가 → 추가`. `웹 앱으로 열기`가 있으면 켠다. [Apple 공식 안내](https://support.apple.com/en-eg/guide/iphone/iphea86e5236/ios)
- **안드로이드**: Chrome의 `⋮ → 홈 화면에 추가` 또는 `설치 및 바로가기 만들기 → 설치`. 브라우저가 설치 가능하다고 판단하면 사이트의 설치 버튼도 표시된다. [Chrome 공식 안내](https://support.google.com/chrome/answer/9658361?co=GENIE.Platform%3DAndroid&hl=en)
- 아이콘으로 열면 해당 브라우저에 기록된 최근 검수 후보로 이동하고 남은 담당 이미지부터 이어간다. 첫 실행·쿠키 삭제 시 이름을 선택한다. 설치된 웹 앱과 기존 Safari 탭의 저장 공간이 분리되는 환경에서는 각각 한 번 선택할 수 있다.
- 작은 칼은 확대/원본 보기로 확인한다. 두 질문·확대·다음 버튼은 휴대폰에서 누르기 쉽게 배치하며 메모는 문제 판정 때만 요구한다. 후보 설명과 출처는 `데이터셋 정보`를 펼쳐 본다.
- PC13과 인터넷 연결이 필요하다. 판정의 완료 여부는 `자동 저장됨`으로 확인한다. 미완성 입력은 브라우저 임시 보관본이며 서버의 완료 판정이 아니다. 원본·판정용 오프라인 캐시나 service worker는 추가하지 않았다.
- manifest는 HTTPS·192/512 PNG icon·standalone·start URL을 제공한다. Chrome의 설치 UI에는 브라우저의 이용 조건이 적용된다. [Chrome 설치 기준](https://web.dev/articles/install-criteria)

팀원에게 Python, Tailscale, 원본 파일, CSV나 GitHub 계정이 필요하지 않다. 원본 이미지·판정·수정 이력은 PC13에 저장된다. HTTPS 역방향 전달 중 요청한 이미지가 팀원의 브라우저로 전송되는 것은 사이트 기능의 일부다.

## 후보 화면과 한계

| 후보 | 현재 웹 검수 표본 | 용도·현재 제한 |
|---|---:|---|
| SOHAS | 200 | 기존100장+추가100장. 판정·history·배정은 보존. CC 표기 충돌·원본 좌표·negative 진위 확인 필요 |
| DaSCI unique | 93 | SOHAS와 byte-identical 1,985장은 제외. Near-duplicate와 권리 gate는 남음 |
| Simuletic | 114 | 합성 CCTV 시점. 실사 성능 증거가 아님 |
| US Mock Attack | 100 | Cam1/Cam5/Cam7 및 knife annotation 유무 층화. 연속 영상의 사건 정답을 대신하지 않음 |
| Open Images | 30 | validation metadata에서 knife positive만. 원본 개별 이미지 권리·라벨 완전성 재검수 필요 |
| Legacy MIDAS | 128 | 팀원의 독립 L0 검수 표본. 신규 source 승인과 별개 |
| Dangerous Items | 100 | 공식 Zenodo API CC BY 4.0. 120개 label을 seeded split별로 살펴 뽑은 100장·임시 knife 객체 19개. ZIP에 class YAML이 없어 visual probe에서 raw ID `1=knife`를 작업 가설로 둔다. 박스 검수는 임시 매핑이며 학습 전 사람의 class-map 확인 필요 |
| ACF Knife | 접근 대기 | 논문이 가리킨 원 저장소가 404. 제3자 재배포본을 원본으로 대체하지 않음 |

현재 **8후보 중 7개 표본 화면 준비**, ACF만 원본 부재로 잠겨 있다. 첫 표본은 source 품질을 보는 작업량 단위다. 이를 근거로 전체 source를 채택하거나 10월 말 실험 데이터로 승인하지 않는다. Dangerous `raw ID 1`은 2026-10-04 임시 visual probe 3장의 관찰 결과이며 공식 class map을 뜻하지 않는다. Dangerous 전체 1.4 GB ZIP은 내려받지 않고 공식 archive의 HTTP Range 45,209,628 bytes만 읽었다. 전체 archive checksum은 미검증이고, 표본의 자체 SHA-256·원 경로·원 split은 보존했다. 현재 표본 인벤토리는 PC13의 `data/review/` 및 `data/source-audit/team-review-20261003/`에 있다.

## PC13 운영

### 표본 확대와 이력 보존 — 2026-10-04

SOHAS 신규 `20261004-b01` 100장을 준비했다. 기존 100장과 별도 immutable pack이며 knife-positive 76 / annotation-negative-unverified 24, 원본 train 48 / test 52, 30,987,546 image bytes다. 원본 commit은 `48860b990e4d4f57fe100248887fceb248475dc8`, seed는 `20261004`다. 기존 7후보 665개 고유 SHA-256과 중복 0, image Git blob·XML hash·원 split·filename group proxy·selection/audit hash를 보존했다. raw bbox area 구간은 표본 선정용이며 좌표 convention·세션 독립성·negative 진위·학습 승인이 아니다. 실제 배포 여부와 관찰 시점 판정 수는 아래 후속 배포 기록으로 구분한다.

2026-10-04에 실제 PC13과 외부 HTTPS에 배포했다(구현 `88067d3`, legacy 집계 보완 `f046520`). 전체107 tests가 개발 PC/PC13에서 통과했고, Chrome/Android와 WebKit/iPhone native form 접속·기존/추가 이미지 표시·두 질문·overflow0을 확인했다. 합성 fixture에서 추가 ID의 저장/재접속을 검증했고 production QA 판정/배정은0건이다. 서비스 정지 최종 백업은 `data/review/team-server/backups/before-expansion-deploy-20261004/`, 집계 보완 직전은 `backups/before-count-fix-20261004/`다. 기존 모든 reviews/history/metadata/users/assignments의 전후 테이블 hash가 동일했고 registry8행만 추가했다. 옛 상세 정상 판정2건의 held 집계는 payload 수정 없이 UI와 같은 규칙으로 바로잡았다.

| 후보 | 준비량 | 판정 저장 | 그중 재확인 |
|---|---:|---:|---:|
| SOHAS | 200 | 98 | 14 |
| DaSCI unique | 93 | 71 | 0 |
| Simuletic | 114 | 42 | 6 |
| US Mock Attack | 100 | 25 | 4 |
| Dangerous Items | 100 | 30 | 6 |
| Open Images | 30 | 17 | 1 |
| Legacy | 128 | 24 | 1 |
| ACF | 0 | 0 | 원본 대기 |
| 합계 | 765 | 307 | 32 |

이 표는 배포 직후 snapshot이며 실시간 수치는 사이트를 따른다. 판정 저장은 `문제 있음/모르겠음`도 포함한다. 새100장은 아직 판정0이며 정상 판정/학습 승인을 뜻하지 않는다. 원시 보존 비교·최종 상태는 PC13 ignored `data/review/expansion-work-20261004/`, 모바일 fixture/외부 QA는 개발 PC ignored `data/review/expansion-qa-20261004/`다. 실제 물리 휴대폰의 홈 화면 설치와 재부팅 복구는 이번 범위에서 미검증이다.

- 기존 CSV/evidence/images와 `human-review.sqlite3`는 덧붙이거나 재생성하지 않는다. config의 같은 후보에 `review_batches: [{"id": "20261004-b01", "review_dir": "<new immutable pack>"}]`를 추가한다. 기본 pack ID 0~99는 그대로이고 새 pack은 100~199로 연결된다.
- 최초 시작 시 team DB에 batch registry만 추가한다. 계정·배정·기존 판정/version/history는 그대로다. 이후 배치 목록의 재정렬·삭제·fingerprint/offset 변경은 startup에서 거부한다. 각각의 pack은 자기 DB를 사용하며 periodic SQLite backup은 모든 배치를 포함한다.
- 같은 데이터셋 선택·같은 두 질문으로 검수한다. 새 batch 때문에 후보 카드나 질문을 추가하지 않는다. 진행 중 탭의 기존 판정 저장은 유지한다. **기존에 열어둔 탭은 저장 완료를 확인하고 한 번 새로고침**하면 확대량을 볼 수 있다. 신규 client는 stale 목록이면 자동 갱신한다. 서버 판정과 원래 draft 키·ID는 유지한다.
- `tools/configure_team_review.py`를 다시 실행해도 등록된 batches를 보존한다. registry와 어긋난 catalog를 자동으로 초기화하지 않는다.
- 확대 준비: `tools/expand_sohas_review.py --config ... --audit .../voc-candidates.jsonl --source .../sohas-upstream-byte-exact --output <new-pack> --proposed-config <new-config> --batch-id <id> --count 100 --fetch-images`. 기존 non-cone sparse checkout에 선택 image만 추가하고 실제 config는 수정하지 않는다. SHA-256·Git blob으로 기존 source의 같은 이미지와 새 배치 내부 중복을 막는다. near-duplicate와 동일 촬영 group 판단은 별도다.
- 상태/백업: `tools/team_review_status.py --config ... --backup <new-backup-dir> --output <snapshot.json>`. app를 만들지 않고 읽기 전용으로 counts·verdict 집계·테이블 hash·quick_check를 관찰하며 SQLite backup API로 config/DB/snapshot을 보관한다. 출력에는 이름·접속 코드·판정 메모를 포함하지 않는다. DB간 시점을 정확히 고정할 최종 백업은 서비스의 짧은 정지 구간에 수행한다.
- 첫 준비 전 consistent backup: PC13 `data/review/team-server/backups/before-expansion-preparation-20261004/`. 관찰 시점 준비/완료는 SOHAS 100/98, DaSCI 93/71, Simuletic 114/42, Mock 100/25, Dangerous 100/30, Open Images 30/17, Legacy 128/24(합계 665/307). 이 수치는 실시간 진행률이 아닌 당시 snapshot이다.
- Dangerous는 임시 class-map 해소 전 확대 보류, Open Images는 validation 30장을 train으로 옮기지 않고 별도 train subset/권리 확인 뒤 확대, DaSCI/Simuletic은 확보한 고유/공개 표본 전체 유지, Legacy는 현재 L0 결과 뒤 gap 기준 추가, Mock은 외부 평가 역할과 sequence 독립성을 유지, ACF는 공식 원본 대기다. 인력 여유가 있다는 이유로 중복·출처 미확인 자료를 재배정하지 않는다.

되돌림은 이전 코드·config와 backup 위치를 먼저 확인하고 수행한다. 새 판정이 생긴 뒤 예전 DB를 복원하면 새 이력을 잃으므로 **자동 rollback/registry 삭제를 하지 않는다**. 실패한 준비 산출물은 catalog에 연결하지 않고 보존한다. 이번 첫 rendering 시 CSV presence 열 누락과 Git `add` 옵션 오류를 수정했고 정상 완성 pack은 `data/review/sohas-expansion-20261004-b01-final/`이다.

- 코드 checkout: `C:\Class6\edge-threat-response`. 원본 아카이브·검수 pack·DB는 ignored `data/`; 모델은 ignored `runs/`/`*.pt`에 둔다. GitHub에는 코드와 사용법만 올라간다.
- 인증 앱: `edge_threat_response.dataset.team_review`, Flask 3.1.3 + Waitress 3.0.2. PC13 `127.0.0.1:8770`만 listen한다. Tailscale Funnel은 HTTPS를 앞단에서 종료한다. 공용 포트포워딩과 LAN bind는 필요 없다.
- Windows 작업 스케줄러 `ETR-Team-Review`: 부팅 시 사용자 PC13 계정의 S4U 제한 권한으로 앱을 재시작한다. 2026-10-04 수동 작업 시작·로컬 로그인 HTTP 200을 확인했다. 실제 재부팅 시험은 아직 하지 않았다.
- PC13 `tailscale set --unattended=true` 적용. 2026-10-04 tailnet 관리자가 Funnel을 승인했고 `tailscale funnel --bg --yes 8770`로 HTTPS 주소를 활성화했다. `tailscale funnel status`에서 백그라운드 proxy를 확인했다. 실제 재부팅 후 Funnel·앱 복구는 아직 시험하지 않았다.
- 설정·비밀값: ignored `data/review/team-server/config.json`, `secrets/team-review-session.key`, `secrets/team-review-admin.txt`. README나 명령 로그에 코드 값을 넣지 않는다. `tools/configure_team_review.py --public-url https://<actual-host> --reviewer-login name`은 기존 사용자·세션 secret·검수 DB를 덮어쓰지 않고 catalog·접속 방식을 갱신한다. 이후 모드를 생략하면 이전 접속 방식을 유지한다. 서버는 변경된 설정을 재시작 후 읽는다.
- DB: `data/review/team-server/team.sqlite3`는 계정/배정, 각 pack의 `human-review.sqlite3`는 판정/이력이다. 30분마다 SQLite backup API로 `data/review/team-server/backups/`에 일관된 사본을 추가한다. **같은 PC 디스크의 백업은 디스크 고장 대비가 아니다.** 승인된 별도 저장소에 주기적으로 복사하는 운영 절차는 아직 미설정이다.
- 기존 SOHAS 이전은 `tools/migrate_review_db.py`로만 한다. 같은 pack hash와 비어 있는 목적지 DB를 검사하고 version/history를 그대로 옮기며, 어느 한쪽에도 판정이 있으면 자동 병합하지 않는다. 이 기록 이후 노트북의 이전 SOHAS URL에 새로 쓰면 PC13과 판정이 갈라진다. 중앙 사이트를 사용하기 시작하면 기존 로컬 URL은 사용하지 않는다.
- 서비스 변경·재시작 후 PC13 저장소에서 `$env:PYTHONPATH="src"; .\.venv-ml\Scripts\python.exe tools\check_team_review.py`를 실행하면 **실제 pack 각각**의 관리자 로그인·목록·첫 이미지 로딩을 판정 변경 없이 점검하고 건수만 출력한다. 접속 코드는 출력하지 않는다. 이는 PC13 내부 앱 테스트이지 외부 HTTPS 브라우저 검증을 대체하지 않는다.

## 배포·검증 기록

- PC13 Tailscale v1.102.4, C 여유 약 144.5 GiB(작업 전 관찰). Windows Python 3.12.4, RTX 3060 학습 venv의 optional review-server dependencies를 설치했다. 검수 자체는 GPU를 사용하지 않는다.
- PC13 local `GET /login` 200, 인증 없는 `GET /api/catalog` 및 SOHAS/Dangerous 이미지 URL 401. 7/8 후보 pack으로 다시 설정하고 시작 작업을 재실행했다. 읽기 전용 실제 config smoke는 **관리자 로그인→7개 pack 목록/첫 이미지 200**과 SOHAS 기존 판정 6건을 확인했고, 판정·계정은 변경하지 않았다. 노트북과 PC13에서 team tests 4개, 전체 로컬 테스트 83개 통과. Session cookie, Host/Origin/CSRF, role·배정 충돌, history/backup을 fixture에서 검증했다.
- Funnel 승인 후 외부 `GET /login` 200, 비인증 catalog·Dangerous 이미지 401, 관리자 HTTPS 로그인 후 catalog의 준비 후보 7개와 Dangerous 첫 이미지 200/79,893 bytes를 확인했다. 관리자 로그인은 판정을 쓰지 않는다. 팀원 개인 계정의 실제 첫 판정 저장·새로고침/재접속은 첫 검수자가 수행할 때 확인해야 한다.
- 2026-10-04 개인 계정 5개를 PC13에 발급하고 관리자 노트북의 ignored `secrets/`에 코드 사본을 옮겼다. 새 서비스로 재시작 후 **공개 HTTPS에서 5/5 계정 로그인·본인 이름 표시**, 첫 계정으로 7개 준비 후보의 공통 `simple-v2` schema·계정 연동을 읽기 전용으로 확인했다. 개발 PC 전체 84 tests, PC13 관련 5 tests와 JS 문법 검사를 통과했다. 이 확인에서 새 판정 0건. 실제 팀원 브라우저의 저장·재개는 미검증이다.
- 원본 권리·좌표·중복/session gate, 사람 검수, 학습 채택은 별개다. 후보마다 질문을 추가하지 않고 공통 `simple-v2` 두 질문을 유지한다. 공유 브라우저의 저장 전 임시 입력은 로그인한 검수자별로 분리한다. 웹 검수 표본의 판정은 source 승인이나 최종 학습 채택이 아니다.
- 이름 선택 변경의 개발 검증: 검수 관련 21 tests, JS 문법·compileall 통과. 합성 fixture에서 Pixel 7/Chrome(412px)과 iPhone 13/WebKit(390px)의 native form 접속·자동 저장·다음·이름 선택 유지·최근 후보 이어하기·미완성 문제 메모 복원을 확인했다. 버튼 높이 46px·가로 overflow 0. 지속형 Chrome profile의 manifest/설치 가능성 검사 오류 0. QA 기록은 로컬 ignored `data/review/mobile-qa-20261004/`에 둔다. 실제 팀원의 판정은 이 테스트에서 쓰지 않았다. 실제 iOS/Android 설치·PC13 재부팅은 미검증이다.
- PC13에 구현 commit `26af97f`를 배포하고 전체 88 tests를 통과했다. 전환 전 SQLite consistent backup을 `data/review/team-server/backups/before-name-login-20261004/`에 작성한 뒤 `reviewer_login=name`으로 전환·시작 작업을 재실행했다. 관리자 actual-config smoke의 전후 SOHAS 판정 6건 및 다른 pack 0건이 일치했다. 외부 HTTPS native form으로 5/5 이름 선택·7개 준비 후보를 확인하고, 본인 계정으로 Chrome/Android·WebKit/iPhone의 실제 SOHAS 화면·이미지를 열었다. 이 과정은 본인의 미검수 배정 1건을 이어받으며 실제 판정은 0건이다. 외부 HTTPS의 Chrome manifest/설치 가능성 오류도 0건이었다. 실제 휴대폰의 설치 UI·홈 화면 아이콘 실행은 아직 확인하지 않았다.
