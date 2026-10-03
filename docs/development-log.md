# Context-Aware Edge Threat Detection System - Development Log

이 문서는 제품, 기술 구조, 운영, 검증 및 연구 설계의 material change를 시간순으로 보존한다. 과거 항목은 삭제하지 않으며, 대체된 내용은 후속 항목에서 연결한다.

## 2026-10-04 - 공개 이름 선택과 모바일 홈 화면 검수

- 사용자 결정: 개인 코드 대신 공개 링크에서 본인 이름을 드롭다운으로 선택한다. 이름은 self-declared identity이며 본인 인증의 증거가 아니다. 기존 계정·배정·판정 DB를 보존하고 관리자 기능은 별도 코드 접속으로 유지한다. 이전 개인 코드 사용 안내는 이 기록으로 `SUPERSEDED`다.
- 작업 카드·범위: 기존 Flask/Waitress·두 질문·SQLite를 재사용해 이름 선택, 30일 검수 session, 관리자 8시간 session, 모바일 큰 버튼·메모 조건 표시, manifest/192·512 icon/Apple icon, 설치 안내와 최근 후보 이어하기를 구현한다. 완료 기준은 실제 native form·저장·재접속·임시 입력 복원, install metadata, PC13 HTTPS 접속 확인이다. 이는 데이터 준비 도구이며 Jetson runtime MVP 범위는 변경하지 않는다.
- 변경 파일: `team_review.py`, 공통 웹 UI·install assets, local review asset routing, configure/check helpers, team tests, README·architecture·팀 배포 사용법·verification. 신규 dependency는 runtime에 추가하지 않았다. 브라우저 QA는 기존 bundled Playwright와 격리 WebKit을 사용하고 결과는 ignored `data/review/mobile-qa-20261004/`에 보관한다.
- 발견·수정: 기존 `Referrer-Policy: no-referrer`는 Chrome native form POST에 `Origin: null`을 만들어 server의 Origin guard가 정상 접속을 403으로 막았다. 실제 browser 재현 뒤 `same-origin`으로 수정해 외부 referrer는 보내지 않으면서 내부 form 접속을 허용했다.
- 개발 검증: 관련 21 tests, JS 문법·compileall·diff 확인 통과. 합성 fixture의 Pixel 7/Chrome 412px와 iPhone 13/WebKit 390px에서 이름 선택→자동 배정→두 질문 저장→다음→재접속·recent candidate·문제 메모 draft 복원 모두 통과했다. 가로 overflow 0, 질문 버튼 46px. 지속형 Chrome profile의 manifest/설치 가능성 오류 0. 실제 source에 새 사람 판정은 쓰지 않았다.
- 배포·검증: 구현 commit `26af97f`를 PC13에 반영하고 전체 88 tests 통과. SQLite consistent backup 후 `reviewer_login=name` 전환·시작 작업 재실행. 외부 HTTPS native form의 이름 선택 5/5·7개 준비 후보·Chrome/Android와 WebKit/iPhone 실제 화면/이미지·manifest 및 설치 가능성 오류 0을 확인했다. 전후 SOHAS 기존 판정 6건 및 나머지 pack 0건을 보존했고 실제 데이터 판정은 추가하지 않았다. 본인의 미검수 배정 1건은 재접속 테스트에 사용했다. 결과는 ignored `public-result.json`에 있고 구현 및 후속 배포 기록 커밋으로 보존한다.
- 한계·다음 작업: 실제 iOS/Android 홈 화면 설치·아이콘 실행과 reboot recovery는 물리 장비에서 확인한다. 이름 선택은 본인 인증이 아니므로 검수 provenance에 그 한계를 유지한다.

## 2026-10-04 - 개인 계정 발급과 후보 공통 검수 흐름

- 목적·이유: 다섯 팀원이 데이터셋마다 다른 양식을 익히거나 CSV를 주고받지 않도록, 기존 `simple-v2` 두 질문·자동 배정·자동 저장을 공통 사용한다. 화면은 기존 구현을 재사용하고 source별 특수 양식은 추가하지 않았다.
- 범위·변경: `app.js`의 미저장 임시 입력 키를 로그인한 검수자별로 분리하고, 화면의 SOHAS/XML 전용 문구를 후보 공통 문구로 바꿨다. 일회성 개인 계정 발급 helper와 재발급 방지 테스트를 추가했다. 본인 이름은 로그인으로 자동 입력된다. 원본·기존 판정·연구용 source 승인 규칙은 바꾸지 않았다.
- 운영 결과: PC13에 개인 계정 5개를 발급했다. 코드 파일은 PC13과 관리자 노트북의 ignored `secrets/`에만 두고 커밋하지 않았다. HTTPS 공개 주소에서 5/5 개인 로그인 및 7개 후보의 동일 `simple-v2` 계약을 읽기 전용으로 확인했다. 새 인간 판정은 0건이다.
- 검증: 개발 PC `unittest discover -s tests -q` 84 tests, `node --check` 및 `compileall` 통과; PC13 관련 5 tests 통과; 서비스 재시작 후 외부 인증·계정/후보 계약 확인. `git diff --check` 통과. 변경 파일: 공통 검수 UI, 발급 helper/test, README·팀 배포 사용법·검증 문서. 커밋 `9340e09`, `9e86f50` 및 후속 README 커밋.
- 한계·다음 작업: 실제 팀원이 두 질문을 저장하고 재접속 시 판정이 유지되는지, 재부팅 후 서비스 복구는 아직 미검증이다. 첫 사용자 검수 후 저장·재개를 확인하고, 표본 판단은 source 권리·좌표·중복 gate와 분리한다.

## 2026-10-04 - 팀 검수 사이트의 외부 HTTPS 활성화

- 사용자 tailnet 관리자 승인을 받은 뒤 PC13에서 `tailscale funnel --bg --yes 8770`를 적용했다. Funnel status는 `https://yu-desktop-97msr1i.tail37c267.ts.net/`에서 loopback `127.0.0.1:8770`으로 proxy 중임을 보였다.
- 노트북의 실제 외부 HTTPS 요청에서 로그인 화면 200, 미인증 후보 목록·이미지 401을 확인했다. ignored 파일의 관리자 코드로 HTTPS 세션 로그인 후 7개 준비 후보 목록과 Dangerous 첫 이미지 200/79,893 bytes를 확인했다. 코드는 명령 출력·Git에 기록하지 않았고 실제 사람 판정은 쓰지 않았다.
- 다음 검증은 개인 코드 발급 후 팀원 본인의 첫 판정을 저장하고 새로고침·재접속 시 같은 값을 보는 것이다. 재부팅 후 앱/Funnel 자동 복구는 아직 미검증이다. 데이터셋 표본의 사람 검수와 원본 class/권리·학습 승인은 별도 gate다.

## 2026-10-04 - PC13 중앙 검수 배포·후보 표본 확장

- 사용자 운영 결정: PC13을 상시 켜고 대용량 원본·검수 pack·DB를 해당 PC에 둔다. 팀원은 브라우저와 개인 코드만 사용하고 CSV 수동 회수·각 PC 설치는 요구하지 않는다. GitHub에는 코드/절차만 동기화한다.
- 2026-10-03 구현된 인증 서비스를 PC13에 배치하고 기존 SOHAS SQLite 백업의 인간 판정 6건·수정 이력 40건을 pack hash 검증 뒤 이전했다. 기존 노트북 DB는 보존하지만 중앙 시작 이후 병행 저장하면 분기하므로 사용하지 않는다. 관리자 bootstrap 파일은 ignored secrets에만 두고 실제 판정은 개인 계정으로만 수행하게 바꿨다.
- PC13 `ETR-Team-Review` 부팅 작업이 실행 중이고 앱은 `127.0.0.1:8770`만 수신한다. `tailscale set --unattended=true`를 적용했다. 루프백 `/login` 200, 인증 없는 catalog·이미지 401, backup integrity를 확인했다. 실제 재부팅과 외부 브라우저 저장은 아직 검증하지 않았다.
- SOHAS 100, DaSCI byte-unique 93, Simuletic 114, US Mock Attack 100, Open Images validation 30, Legacy 128, Dangerous Items 100을 PC13 팀 catalog에 준비했다. ACF 원 source 404는 임의 mirror로 대체하지 않는다. Dangerous Items 공식 Zenodo API CC BY 4.0 확인; ZIP에 YAML class map이 없어 3장/클래스 visual probe 결과 `raw ID 1 = knife`를 **표본 화면의 작업 가설**로만 사용한다. 이 가설로 학습·성능 주장하지 않는다. 전체 1.4 GB 직접 다운로드가 지연되어 고정 크기 HTTP Range 45,209,628 bytes로 120 label을 조사하고 100장·임시 knife 19개 표본을 준비했다. 전체 archive checksum은 아직 검증하지 못했다.
- 검증: 신규 팀 service 4 tests 및 개발 PC 전체 83 tests 통과. 실제 PC13 config의 관리자 로그인·7개 pack 목록·각 첫 이미지 200을 읽기 전용 smoke로 확인해 SOHAS 6판정이 유지됐다. 검수 DB/이미지·원본은 ignored, source 채택·라벨 검증·모델 학습은 진행하지 않았다. Tailscale Funnel은 tailnet의 관리자 enable gate를 반환했고 현재 `No serve config`이므로 외부 URL은 아직 `NOT VERIFIED`다. 승인 후 HTTPS 로그인/이미지 차단/팀원 저장·재개를 따로 확인해야 한다. 상세 운영·source별 범위는 [PC13 팀 웹 검수](team-review-deployment.md)에 둔다.

## 2026-10-03 - PC13 중앙 팀 검수 구현 (배포 검증 전)

- 사용자 결정: PC13 상시 운용·팀 웹서비스 운영 가능, 대용량 자료는 PC13에 두고 브라우저만으로 후보 검수한다. CSV 회수·각 PC Python 설치 방식은 채택하지 않는다.
- 작업 카드: 기존 두 질문 UI·SQLite/history를 재사용해 다중 후보, 개인 코드 로그인, 관리자 초대/해제, 미검수 자동 배정, 동시 수정 차단, 백업을 구현한다. 완료 기준은 인증 없는 이미지 차단·권한/CSRF/Host·저장/재개·원격 HTTPS 확인과 기존 인간 판정 보존이다. 학습·source 자동 승인·전체 PC 공유는 제외한다.
- search-first 선택: stdlib 개발 HTTP 서버의 직접 공개 대신 Windows 지원 Flask 3.1.3 + Waitress 3.0.2를 별도 review-server requirements로 채택한다. Core의 무의존성과 로컬 검수 서버는 유지한다. 공식 Flask deployment/waitress 문서를 확인했다.
- 구현: signed Secure/HttpOnly/SameSite cookie, 8시간 세션, 개인 고엔트로피 접속 코드의 scrypt hash, 접근 해제 시 세션 무효화, origin·CSRF·명시적 Host 경계, 계정 기반 reviewer, 배정 중복 방지와 review version 유지. 관리자만 계정을 발급·해제한다. 코드·키·원본·개인 판정은 Git 제외다.
- Source preparation: SOHAS 100 기존 pack, DaSCI byte-unique 93(98 knife), Simuletic 114(99 knife), US camera/positive strata 100(47 knife), Open Images validation 첫 표본 30(40 knife), 기존 legacy 표본 128(147 knife) 준비. 표본은 source 채택이나 전체 구성비의 증거가 아니다. ACF upstream 404 유지. Dangerous Items official Zenodo record는 현재 CC BY 4.0이며 과거 권리 보류를 갱신하지만 다운로드·실제 pack 검증은 진행 중이다.
- PC13의 US 원본 archive 1,485,019,798 bytes와 SHA-256 `558f5baa109abe8fba57b61fa177c75358001f5499f5e78178f4bf7dc9f55e8c`를 확인했다. 원본은 PC13에만 두며 full dataset import/training은 하지 않았다. Simuletic HF snapshot `c71bb6186c9849edf2216909febffb979b89b838`, US HF `07ced721cd90973f66806c0b3ee01e80c439ba90`을 기록한다.
- 검증: Windows Python 3.11 전체 83 tests 통과, compileall/JS check. 신규 테스트에서 Flask trusted Host의 400 거부와 SQLite context manager가 close하지 않는 Windows file-lock을 재현했고 fail-closed assertion·explicit closing으로 수정했다. local pip console 인코딩 경고는 설치 후 import/test로 확인했다.
- 기존 SOHAS human DB 관찰: 6행/history 40건의 consistent migration snapshot 작성, 원본과 실행 중 로컬 탭은 그대로 보존. 원격 import·서비스 자동 실행·Funnel 공개·브라우저 통합은 아직 이 항목 시점 NOT VERIFIED이며 후속 기록으로 갱신한다. 관리자 bootstrap 코드 파일은 ignored secrets에만 생성한다.

## 2026-10-03 - 진행 중 저장 확인·검수 질문 최소화·팀 배포 점검

- 작업 카드: 사용자 요청에 따라 실제 저장을 비파괴적으로 확인하고 중복 UI 항목을 줄인다. 완료 기준은 DB 무결성·백업, 기존 판정 보존, 2-question 저장·재개 테스트와 문서/Git 반영이다. 공개 배포·공유 권한 변경·훈련·사용자 대리 판정은 제외했다. 진행 중 탭/저장을 끊지 않는 것이 주요 위험 통제다.
- 관찰: 실제 API/DB는 100장 중 5행, 수정 history 39건, `quick_check=ok`. read-only DB 연결에서 SQLite backup API로 `backup-before-simple-ui.sqlite3`에 일관된 snapshot을 남겼다. 초기 latest-time 조회 shell quoting 오류는 데이터 변경 없이 실패했고 JSON timestamp read로 재실행했다. 이는 관찰 시점 수치이며 완료된 전체 검수가 아니다. 사용자 이름·판정 내용은 Git/로그에 옮기지 않았다.
- search-first로 기존 CSV/SQLite/version/history를 재사용했다. 기본 입력은 CCTV형/그 외/모르겠음과 라벨 정상/문제 있음/모르겠음 두 질문이다. 품질·박스 완전성·별도 처리 질문과 중복 빠른 버튼·선택적 사람/크기/가림을 제거했다. Normal의 의미에 모든 knife box와 음성 실제 부재 확인을 명시했다. 문제는 메모 후 재확인 후보이고 자동 제외하지 않는다.
- `simple-v2` schema·coarse annotation verdict를 추가해 명시적 통합 답을 기존 export 열에 매핑한다. positive 문제를 누락으로 단정하지 않고 완전성 unclear로 둔다. 상세 기존 enum·판정은 일괄 변환하지 않으며 수정 전 payload는 history에 보존한다. 기존 client 저장 계약도 유지한다. 재검수 아닌 사람 이름 자동 채움/AI 승인 없음.
- 사용 중 서버/탭을 재시작하지 않았다. 새 8768 서버가 동일 DB를 사용하며 기존 8765는 유지한다. launcher 기본을 8768로 변경하고 오래된 서버는 새 UI에서 오류 안내로 차단한다. 기존 창에서 저장 후 새 주소를 사용한다. 두 주소의 browser-local 미완성 draft는 서로 자동 이전되지 않는다.
- verification-loop: 새 3 regression tests 포함 focused 7 tests 및 전체 **79 tests 통과**(1.940 s), compileall·JS 문법 정상. 첫 신규 테스트 삽입 위치 때문에 fixture `original`의 scope 오류가 나와 테스트 위치를 수정해 재검증했다. Computer Use로 별도 QA DB에만 테스트 판정을 입력해 화면 질문 2개, 저장/다음/새로고침 재개를 확인했다. 실제 검수 DB에 QA 값을 쓰지 않았다.
- 배포 판단: 현재 listener 127.0.0.1이며 login/roles/담당 배정·remote HTTPS/backup은 없다. 로컬 pack + Python 배포와 비공개 인증 서비스 경로를 검수 기준에 기록했다. CSRF를 인증으로 오인하거나 정적 호스팅만으로 DB 저장을 제공한다고 주장하지 않는다. 팀원 접속·package 배포·인터넷 공개·Drive 업로드는 미수행이다.
- 변경: review server, JS/HTML, Windows launcher, tests, README·검수 기준·verification·이 로그. raw/DB/backup은 ignored이고 recipe/MVP 불변이다. 다음은 사용자가 간단 UI에서 계속 검수하고 팀 배포 방식/접근 범위를 선택하는 것이다. Git: 이 기록을 포함하는 commit.

## 2026-10-03 - 버튼 기반 로컬 SOHAS 검수 화면

- 요청/작업 카드: CSV 대신 사이트처럼 클릭하며 표본을 확인하도록 원본·raw knife 박스·판정 버튼·이동·자동 저장·CSV export를 구현한다. 완료 기준은 실제 100장 로딩·별도 테스트 DB의 저장/재개와 원본 보존·전체 tests·문서/Git 반영이다. 데이터 채택·인간 대리 판정·실제 학습·공개 배포/Drive 업로드는 범위 밖이다.
- search-first로 기존 review CSV/evidence/VOC/Pillow helper를 재사용하고 원본 보존 output만 얇게 확장했다. 서버/저장은 Python stdlib `http.server`/SQLite, 화면은 HTML/CSS/JS이며 새 framework/dependency를 추가하지 않았다. Windows built-in launcher는 재사용/재개 시 반복 명령을 없애려는 사용자 UI 요구를 지원한다.
- 변경: `review_web.py`, 정적 자산 3개, `etr-review` 및 package-data 설정, source image helper, Windows launcher, store/API tests; README·검수 기준·handoff·verification·이 로그. `domain`/품질/누락/처리 후보/검수자 필수, 음성의 실제 칼 부재 확인, 제외/보류 이유를 검증하며 권리/좌표 승인 입력은 제공하지 않는다.
- 원격에서 기존 sample의 새 `sohas-click-review-20261003/` pack을 생성한 뒤 노트북으로 SCP 복사했다. 원본 100장 31,100,785 bytes와 knife 객체 103개·7 sheets를 보존했다. SQLite와 image/CSV는 ignored로 Git에 올리지 않는다. 기존 pack은 보존한다.
- verification-loop: focused store/API 4 tests 후 전체 **76 tests 통과**(1.873 s 관찰), `compileall`·Node JS 문법 확인. 초기 SQLite connection context가 연결을 닫지 않아 Windows fixture cleanup이 실패한 것을 재현·수정하고 재검증했다. 저장은 transaction+version으로 오래된 탭 덮어쓰기를 차단하고 source hash가 바뀌면 DB 재사용을 거부한다. CSV formula 입력은 export에서만 neutralize한다.
- 실제 브라우저에서는 **별도 QA DB**에 `UI_TEST_NOT_HUMAN` 1행을 저장해 다음 이동·새로고침 후 동일 값 재개·확대·박스 숨기기·음성 필터를 확인했다. browser warn/error 0개. 이는 UI 기능 확인이며 인간 검수 완료가 아니다. 실제 human DB는 0행임을 확인했다.
- 현재 setuptools의 한글 경로 editable wheel `.pth` 생성(cp1252)과 초기 한국어 stdout 오류를 재현했다. startup 메시지를 ASCII로 바꾸고 launcher는 `PYTHONPATH=src`/UTF-8 모듈 실행으로 설치 없이 사용한다. editable install 성공을 주장하지 않는다. 일반 wheel build 성공·정적 자산 포함을 확인했다. Windows launcher 기존 서버 재사용 및 새 포트 시작도 통과했다.
- 한계/영향: loopback 단일 PC 검수 도구이며 공유 계정/원격 다중 사용자/자동 Drive 백업/annotation 수정/학습은 없다. 미완성 입력은 browser-local draft다. Legacy L0와 recipe 승인 상태는 불변. 다음은 사용자가 이 UI에서 100장 검수 → 표본 오류/누락/negative·좌표·촬영 group 확인 → source/split/recipe 결정이다. Git: 이 기록을 포함하는 commit.

## 2026-10-03 - 비상용 내부 연구 범위의 SOHAS 이미지 검수 준비

- 사용자 clarification: 상용 목적이 아닌 수업 연구이며 작업 진행을 요청했고 `C:\Class6` 보존도 확인했다. 메일 회신을 모든 데이터 확보의 필수 조건으로 둔 이전 설명을 수정한다. 공식 연구진의 public research 설명 및 CC BY/CC BY-SA의 복제·변형 허용을 확인해 제한된 로컬 sample 검수는 진행하고 외부 공개 조건은 분리한다. license 차이 해결·학습 채택을 주장하지 않는다.
- 작업 카드: 기존 100개 표본의 원본 확보·decode/hash/dimension 확인·raw knife overlay·빈 human CSV를 완료 기준으로 둔다. 전체 다운로드·학습·외부 공유·AI 판정의 human 대체는 제외하며 10 GB 한도를 유지한다.
- search-first로 기존 SOHAS pinned inventory/blob 검사/VOC parser·Pillow를 재사용했다. 기존 legacy review-pack은 knife annotation 없는 negative 및 미확정 VOC 좌표를 입력으로 못 받으므로 작은 source-specific `tools/sohas_review_images.py`를 추가했다. 학습 label/manifest export나 downloader를 새로 만들지 않았다.
- remote `git sparse-checkout add --stdin`에 기존 sample의 image path 100개만 전달해 원본을 확보했다. helper의 실제 실행 결과 100개 decode·blob·dimension 확인 성공, 총 31,100,785 bytes, knife 객체 103개, 7 contact sheets. 첫 생성 CSV의 image_present는 이전 audit 시점 값이라 최종 helper에서 현재 True로 갱신하고 `sohas-100-20261003-final/`로 별도 재생성했다. reviewer는 빈칸, training 승인 false다.
- 노트북에는 작은 pack만 SCP로 복사했다. 첫 sheet를 육안 개발 확인해 caption/overlay가 표시되는 것을 확인했다. 제품/클로즈업·워터마크·반복 촬영 장면도 보여 무검수 전체 승인하지 않는다. 사람의 100장 판정 또는 coordinate convention 확정으로 기록하지 않는다.
- verification-loop: 신규 fixture 2개 통과, 전체 72 tests 통과(0.822 s), helper actual integration 성공. 초기 단일 테스트 module 경로 호출은 tests가 package가 아니어서 실패했고 `unittest discover -s tests -p test_sohas_review_images.py`로 올바르게 재실행했다. initial SCP cwd 누락은 경로를 지정해 재실행했으며 원본 삭제 없음.
- 변경: helper/test, source strategy/evaluation criteria/handoff/verification/이 로그. 코드·문서만 Git에 넣고 raw/pack은 ignored. source/model recipe는 미승인이고 메일·Drive 업로드·실제 학습은 수행하지 않았다. 다음은 인간 표본 검수·좌표 근거·negative 누락·near duplicate/session split이다. Git: 이 기록을 포함하는 commit.

## 2026-10-03 - 외장 저장장치 없는 데이터 준비·권리 확인 초안

- 사용자 요청: SOHAS 준비를 진행하고 필요한 정보를 요청하되 GPU PC/노트북에 외장 저장장치를 상시 연결하지 않는 저장 방식을 정한다.
- 범위/완료 기준: 내장 디스크 여유·기존 ignore·공식 pinned license/contact를 확인하고 기존 전략/report에 작업 위치·백업 경계·권리 확인 초안을 추가한다. 신규 source 채택·메일 발송·전체 image 다운로드·학습은 제외했다.
- Windows `Get-PSDrive C` 관찰: 학습 PC 144.5 GiB, 노트북 16.4 GiB 여유. GPU PC의 기존 `data/`와 `runs/`를 사용하고 노트북은 코드·소형 검수 pack 위주로 둔다. Drive 실제 연결/업로드는 미수행이며 로컬 dataset 10 GB 한도와 권리 gate를 유지한다.
- 고정 upstream의 README CC BY-SA 4.0과 License.md CC BY 4.0 및 공개 기관 연락처를 재확인했다. 사용 조건·제한 공유 백업·weight 공개·VOC 좌표·group metadata를 묻는 영문 메일 초안을 기존 SOHAS report에 작성했다. 외부 연락을 보내지 않았다.
- package 크기 측정을 위해 partial clone에서 `git ls-tree -r -l`을 시도했으나 lazy blob fetch/auto maintenance가 유발되어 해당 크기 조회 프로세스만 중단했다. 파일 삭제·원본 변경 없이 보존했으며 체크아웃된 이미지 0개를 확인했다. Git cache 일부 반입은 있었으므로 metadata만 읽었다고 주장하지 않는다. 이 조회의 0 count/size 출력은 유효한 package 용량이 아니며 사용하지 않는다. 이후 크기 조회는 공식 tree API의 size 등 blob fetch 없는 방식으로 수행한다.
- 변경: dataset-source-strategy, 기존 SOHAS report, 이 로그. verification-loop 기준 문서 diff/ignore를 확인하며 코드 변경이 없어 코드 테스트는 생략한다. recipe 승인 상태 불변.
- 필요한 사용자 정보: `C:\Class6`의 기간 중 보존/초기화 정책, 권리 확인 메일 발송 담당. 다음은 회신 근거 또는 명확한 공식 사용 조건 확보 후 이미지 검수다. Git: 이 기록을 포함하는 commit.

## 2026-10-03 - 남은 사용량으로 SSH 독립 GPU 실행 검증

상태: 단기 SSH 종료 후 CUDA 작업 지속 `VERIFIED`; 실제 데이터 학습·장시간 안정성 `PLANNED`.

- 목적/범위/완료 기준: 사용자가 남은 Plus 사용량을 효율적으로 배분해 작업하도록 요청했다. 긴 학습 전에 연결 종료 시 작업이 유지되는지 확인하는 범위로 한정했다. 기존 생성 데이터 helper를 재사용하고 exit code·summary·checkpoint 증거와 문서/Git 기록을 완료 기준으로 잡았다. source/recipe 승인 우회나 실제 full training은 제외했다.
- search-first로 기존 helper와 Windows built-in을 선택하고 verification-loop로 실제 시작 SSH 종료와 새 연결 확인을 수행했다. 새 의존성/helper/서비스/예약 작업은 설치하지 않았다.
- 기존 `Start-Process`+20초 지연 방식은 시작 SSH 종료 뒤 프로세스/summary/exit code가 남지 않았다. ignored `runs/pc13-detached-smoke-20261002/`는 실패 증거로 보존했다.
- CIM `Win32_Process.Create`로 hidden PowerShell을 생성(ReturnValue 0, PID 12068), 15초 지연 후 생성 CUDA/AMP helper 실행. 시작 SSH는 학습 전에 종료됐다. 이후 새 SSH에서 exit-code 0 및 summary passed를 읽었다. 생성 8 train/4 val·1 epoch·validation·best/last·reload GPU inference 통과, runner duration 5.875 s. 확인 명령 exit 1은 이미 종료된 launcher PID 조회 때문이며 학습 exit와 별개다.
- 원격 Windows/RTX 3060/torch 2.6.0+cu124 환경, 실행 소스 commit `1c176ae`. raw evidence는 `runs/pc13-cim-smoke-20261002/`; helper hash는 summary에 보존했다. 코드 변경 없이 handoff·verification·이 로그만 갱신했다.
- 한계/결정 영향: 재부팅/절전/로그아웃·장시간 학습·재시작·Drive 업로드·모델 품질은 미검증. R1/H1 승인과 image/rights/coordinate/group gate는 유지한다. 다음은 dataset 권리 및 표본 검수이고, 사용량을 소진하기 위한 새 기능은 추가하지 않는다. Git: 이 기록을 포함하는 commit.

## 2026-10-02 - 로컬 SSH 작업 재개와 Windows SOHAS byte-exact audit

상태: 로컬→학습 PC SSH·Windows label audit `VERIFIED`; 실제 이미지/권리/좌표/recipe 승인·full training `PLANNED`.

- 목적/범위/완료 기준: 사용자의 연결 복구 후 작업 재개 요청에 따라 Cloud 변경을 pull하고 기존 audit를 원격에서 재현한다. 기존 staging 보존, 테스트·실제 audit·검수 목록 생성·문서 기록을 완료 기준으로 잡았다. 위험은 Windows checkout 변환과 미승인 source 반입이며 학습 gate를 유지했다.
- `search-first`와 `verification-loop`를 적용해 기존 VOC CLI를 재사용했다. source/helper/dependency 추가 없이 clone-local 설정만 사용했다. 변경 문서는 이 로그·verification·training-cuda-handoff·SOHAS metadata report다.
- Windows/Python 3.12.4 원격 repo를 `0b51dd4`까지 fast-forward했다. 전체 70 tests는 원격 0.554 s, 로컬 1.212 s에 통과했다.
- 첫 실제 audit는 XML 4,686개 blob 불일치로 exit 1. upstream clone의 `core.autocrlf=true`를 확인했고, byte 검증을 완화하지 않았다. 기존 source/output은 보존하고 새 `data/source-audit/sohas-upstream-byte-exact/`를 `git clone --config core.autocrlf=false --filter=blob:none --no-checkout`으로 준비했다. upstream `48860b9`, 같은 label/XML-only sparse checkout이며 전역 설정·이미지를 변경/다운로드하지 않았다.
- CLI 정상 출력 `data/source-audit/sohas-voc-pc13-byte-exact-20261002/`: exit 0, 구조 오류 0; metadata 5,859 / VOC knife 2,349 / YOLO knife 2,277 / mismatch 58 / orphan 83 / case-only warning 181. 100개 review sample·전체 queue를 생성했다.
- 한계/결정 영향: 이미지 0, 좌표 `unknown`, 사람 검수 pending, 학습 승인 false. R1/H1은 기존 PROPOSAL을 유지한다. Cloud 연결·SSH 종료 후 job 지속·Drive 업로드·실제 full training은 미검증이다.
- 다음: 사용 권리 근거 확인 → 승인된 이미지 표본/좌표 검수 → near duplicate/session grouping 및 공통 tuning/test → recipe 승인 후 CUDA 학습. Git: 이 기록을 포함하는 commit.

## 2026-10-02 - Cloud 장시간 작업 인계와 SOHAS VOC 승인 전 준비

상태: source-specific 변환·audit `IMPLEMENTED`, synthetic 좌표 계약·Cloud label dry-run `VERIFIED`; 실제 이미지/좌표/권리/recipe 승인·full training `PLANNED`; Cloud→학습 PC SSH `BLOCKED`.

### Goal / Why / Scope / Changed files

- 사용자의 로컬 채팅 인계를 받아 이 Cloud에서 bounded dataset 준비·검증을 수행한다. 준비된 YOLO label의 72개 knife 객체 누락 차이를 그대로 학습에 반영하지 않기 위해 VOC의 모든 knife 객체를 보존한다.
- 작업 카드: 목적은 source-specific 변환/audit 및 검수 대기 파일 준비; 범위는 raw read-only metadata/label과 pure Python; 완료 기준은 기존+오류경로 테스트, 실제 dry-run, 관련 문서 및 commit/push; 위험은 좌표 convention·negative 누락·권리·group 미확정이다. full training, 이미지 source 채택, Drive 업로드, 네트워크/방화벽 변경은 이번 작업 범위 밖이다.
- `rg`로 기존 dataset tooling을 검색해 `parse_yolo_label`, `ValidationIssue`, review `size_bucket`을 재사용했다. 이 Cloud에는 별도 search-first/verification-loop skill이 제공되지 않아 AGENTS의 절차를 직접 따랐다. XML·Git inventory·CSV 처리는 표준 라이브러리를 사용하며 추가 dependency는 없다.
- 변경: `src/edge_threat_response/dataset/sohas.py`, CLI, `tests/test_sohas_voc.py`; README, model-data-plan, dataset-source-strategy, verification, 기존 SOHAS metadata report, training-cuda-handoff, 이 로그. 원본·generated 출력·model/venv는 Git에 넣지 않는다.
- 사용자에게 명시적으로 위임된 코드 작업이며 onboarding의 설치 작업과 구분한다. 기존 clean checkout을 그대로 사용하고 새 worktree는 만들지 않았다.

### Environment / Commands / Result / Verification

- Linux x86_64 Cloud / Python 3.12.14, 기존 pure/review `.venv`. `work` branch에서 clean 상태를 확인하고 `git pull --ff-only origin main`으로 `0d9ce87`까지 반영했다. `/dev/nvidia*`와 `nvidia-smi`가 없으므로 CUDA GPU를 확인하지 못했으며 CPU full training을 실행하지 않았다.
- 환경 config read는 onboarding draft의 존재를 확인할 뿐 publication 상태를 제공하지 않았다. 현재 shell/코드 실행은 확인했지만 published 환경·새 task restoration·장시간 프로세스 수명을 확인했다고 주장하지 않는다. 설정 초안 저장은 publication이 아니다.
- 원격 SSH는 BatchMode/5초 timeout/1회 연결/StrictHostKeyChecking=yes로 안전하게 확인했다. 초기 system SSH include의 ownership/permission 오류 후, 파일을 수정하지 않고 관련 없는 systemd local-host 설정을 제외하는 `-F /dev/null`로 다시 확인했다. 사용자가 제공한 사설 PC 주소의 TCP/22가 `Connection refused`를 반환했으며 인증 전에 실패했다. raw key 추출·복사, Tailscale 설치, 방화벽/포트 개방 또는 로컬 노트북 우회 실행을 하지 않았다.
- 공식 upstream의 pinned partial/sparse clone은 ignored `data/source-audit/sohas-upstream/`에 59 MB이며 XML·YOLO label·README/license/YAML만 checkout했다. 이미지 0개, source status clean. Git regular-file executable mode도 포함하는 inventory로 image metadata 5,859개를 사용하고 source bytes의 blob/SHA-256을 확인했다.
- `.venv/bin/python -m unittest discover -s tests -q`: 기존 56 + 신규 14 = **70 passed**, 실패/skip 0. 신규 테스트는 모든 knife bbox와 raw map, 두 좌표 convention, unknown 보류, malformed/entity/filename/dimension/unknown-class/범위 오류, 부분-label 차단, input immutability, pinned inventory, orphan/negative 대기, CLI exit 및 표본 재현성을 확인한다.
- `.venv/bin/etr-dataset sohas-voc-audit --source-root data/source-audit/sohas-upstream --output-dir data/source-audit/sohas-voc-cloud-final`: exit 0, VOC knife 2,349 / YOLO 2,277, count mismatch 58 images, orphan XML 83, filename 대소문자 warning 181. 초기 엄격 filename 검사에서 나온 181 항목은 모두 대소문자만 다른 것을 확인한 뒤 unique pairing의 case-only warning으로 처리했다. 다른 identity 오류는 계속 보류한다.
- `voc-candidates.jsonl`에 `knife_108`의 2개/`knife_1162`의 3개 객체가 보존되고, 모든 행이 미승인·빈 reviewer·변환 lines 없음임을 assertion으로 확인했다. 전체 review queue 및 seed 20261002의 100개 층화 sample CSV를 생성하고 층별 n/N을 summary에 기록했다. 원시 출력은 ignored `data/source-audit/sohas-voc-cloud-final/`이다.
- 최종 코드로 `sohas-voc-cloud-repeat/`에 다시 실행해 exit 0과 기존 candidate JSONL·sample CSV의 byte-identical 재현성을 확인했다. 문서 로컬 링크·`git diff --check`를 확인하고 최종 status에서 의도한 code/test/docs만 변경됐음을 검토했다.
- 단위 테스트의 explicit-convention geometry는 synthetic 계약 증거다. SOHAS convention 자체는 미확정이며 기본 `unknown`으로 실제 training label·split·학습을 생성하지 않았다. 이미지 decode/시각적 bbox 완전성·negative 진위는 미수행이다.

### Decision impact / Next action / Git

- R1/H1 우선 제안과 gate를 유지한다. 다음은 권리·좌표 근거 확인, 승인된 이미지 검수, near duplicate/session grouping, 공통 tuning/final-test 및 명시적 batch/optimizer-step 예산 결정이다. 100개 sample은 전체 source 승인이 아니다.
- 원격 GPU 작업에는 Cloud에서 사설/Tailscale 대상까지의 지원되는 네트워크 경로와 PC SSH service/접근 정책이 필요하다. TCP 연결이 가능해진 뒤 기존 SSH 인증을 재확인한다. 기존 PC CUDA smoke 근거는 유효하지만 이 Cloud의 연결·background 지속성을 증명하지 않는다.
- Git: 이 기록을 포함하는 commit. 의도한 code/test/docs만 stage하며 non-force push 결과를 확인한다.

## 2026-10-02 - 3개 screening 제안 검토와 SOHAS 실제 라벨 대조

상태: upstream metadata·실제 label/XML object count `VERIFIED`; recipe 채택·변환·human review·학습 `PLANNED`/기존 `PROPOSAL` 유지.

- 목적: 사용자가 전달한 SOHAS/DaSCI/Combined 3연속 screening 제안을 현재 증거로 평가하고 안전한 준비 작업을 진행한다.
- `search-first`/`verification-loop`를 사용해 기존 metadata 보고서와 source 정책을 재사용했다. 새로운 모델·다운로더·학습 framework는 추가하지 않았다.
- GPT가 지정한 SOHAS YOLO 배포본의 image/label tree와 YAML을 확인했다. image 5,859장, label 5,859개, orphan label 0; DaSCI exact blob overlap 1,985장으로 기존 결과와 일치했다.
- 원격 PC의 ignored `data/source-audit/sohas-upstream/`에 고정 upstream partial/sparse clone으로 license/README/YAML·YOLO label·VOC XML만 확보했다. image checkout·Drive 공유·실제 학습은 수행하지 않았다.
- PowerShell로 5,859 label을 집계하고 같은 split/basename VOC와 비교했다. knife annotation positive 2,277 / no-knife candidate 3,582; YOLO knife objects 2,277 vs VOC 2,349, 58 images 불일치. label-only negative 진위·bbox 품질은 미검증이다. generated 집계 JSON은 원격 `data/source-audit/`에 있다.
- raw root의 image 확인은 파일 확장자 필터로 0개임을 확인했다. sparse-checkout add의 잘못된 `--no-cone` 옵션은 실패했고, 기존 non-cone 설정에서 옵션 없이 재실행해 XML을 확보했다. 원본 파일을 수정하지 않았다.
- [metadata 보고서](../reports/datasets/sohas-dasci-metadata-2026-10-02/report.md), source strategy와 verification에 결과·해석·한계를 추가했다. 코드 변경이 없어 코드 테스트는 생략하고 링크·diff를 검사한다.
- 판단: 짧은 screening과 공통 tuning/오류 분석은 타당하지만 세 source가 독립적이라는 가정과 YOLO label 즉시 사용은 채택하지 않는다. R1/H1 우선, 고유 DaSCI는 조건부 U1을 유지한다. 다음은 권리 확인·VOC 전체 bbox 변환·표본 검수·cross-source group split이며, 승인 전에 training을 시작하지 않는다.
- Git: 이 기록을 포함하는 commit.

## 2026-10-02 - 원격 RTX 3060 학습 환경 설정

상태: 원격 clone·격리 ML 환경 `IMPLEMENTED`; CUDA/AMP 학습 plumbing `VERIFIED`; 실제 dataset full training `PLANNED`.

### Goal / Why / Scope / Changed files

- 사용자가 제공한 SSH PC에서 비어 있는 `C:\Class6`를 확인하고 `edge-threat-response` clone과 `.venv-ml`을 생성했다. 전역 Anaconda·GPU driver·기존 파일은 변경하지 않았다.
- 기존 runner를 재사용하고 `tools/cuda_training_smoke.py`, `configs/training/requirements-pc13.txt`를 추가했다. `training-cuda-handoff.md`, verification, 이 로그와 [검증 report](../reports/training/pc13-cuda-smoke-2026-10-02/report.md)를 갱신했다.
- legacy 학습 절차는 팀원의 L0 트랙임을 handoff에 명시하고 신규 source audit와 독립적으로 환경을 준비했다. 실제 source 다운로드·병합·학습 승인과 모델 선택은 범위 밖이다.

### Environment / Commands / Result / Limitations

- Windows / Python 3.12.4 / i9-13900 / RAM 약 32 GB / RTX 3060 12 GB / driver 560.94. torch 2.6.0+cu124·torchvision 0.21.0+cu124와 Ultralytics 8.4.152 조합을 설치했다. 상세 pin·재설치 명령은 handoff에 있다.
- `pip check` 정상, 원격 `python -m unittest discover -s tests -q` 56개 통과. 로컬도 56개 통과, helper compile 확인.
- `python tools/cuda_training_smoke.py --output runs/pc13-cuda-smoke-20261002`와 별도 `--amp` run: 8 train/4 val 생성 이미지, 320 px, batch 2, workers 0, 1 epoch에서 forward/backward·loss·validation·best/last.pt·checkpoint reload GPU inference 확인. runner duration 각각 8.765/5.063 s. 실모델 성능·FPS 근거가 아니다.
- 초기 deterministic 경고를 보고 helper에서 torch import 전 cuBLAS workspace 설정을 추가해 AMP run을 검증했다. 반복 동일 결과·큰 batch·장시간 학습·SSH 단절 지속·Drive 업로드·Orin은 미검증이다.
- raw run과 전체 pip freeze는 원격 ignored `runs/`에 보존했다. 생성 데이터·weight·환경은 Git에 넣지 않고 code/config/요약만 sync한다.
- 문서 로컬 링크 4개 오류 0건, `git diff --check` 통과. SCP 반입 helper·requirements의 로컬/원격 SHA-256 일치를 확인했다. 원격 CLI help도 실행됐다.

### Decision impact / Next action / Git

- 실제 GPU 학습 경로는 준비됐지만 source·label·split 승인 gate는 유지한다. 다음은 SOHAS audit과 신규 recipe 승인 후 actual CUDA run이다.
- Commit: 이 기록을 포함하는 commit. 원격에는 의도적으로 반입한 파일만 path-scoped stash로 보존한 뒤 fast-forward한다. 모델·runs·venv는 ignored 상태로 그대로 유지한다.

## 2026-10-02 - 개발 Agent Layer 참고자료의 최소 적용

상태: 작업 규칙·문서 절차 `IMPLEMENTED`; 검증 결과는 아래에 기록. 모델·시스템 기능 변경 없음.

### Goal / Why / Scope

- 사용자가 제공한 baseline ZIP, 문서화 스킬북, Agent Layer 계획에서 현재 프로젝트의 개발 효율에 도움이 되는 기능만 가져온다. 첨부자료의 전체 설치 계획을 사용자 요청으로 해석하지 않는다.
- 기존 구현 우선·최소 변경·실패 재현과 회귀 검증·선택적 문서 갱신을 `AGENTS.md`에 반영했다. `documentation-governance.md`에 작업별 검증·문서 routing과 도입/보류 경계를 기록했다.
- 기존 전역 `search-first`·`verification-loop`를 재사용한다. ZIP의 template나 구버전 skill로 기존 파일을 덮어쓰지 않았다. 별도 프로젝트 status/ADR/skill 파일을 추가하지 않았다.
- Serena·Graphify·Archify·Claude-mem·Headroom·OmniRoute는 설치하지 않았다. 앱 설정·전역 MCP·권한·Git hook·소스·dataset·학습 조건은 변경하지 않았다.

### Environment / Verification / Limitations

- Windows PowerShell, 저장소 `main`. 작업 시작 `git status --short --branch` clean, `git pull --ff-only` already up to date.
- 세 참고자료와 현재 AGENTS·governance·Master Plan·MVP·open decisions·architecture·verification·최근 개발 로그·test 목록을 확인했다. 기존 source와 unittest 경로를 탐색해 새 도구 없이 유지 가능한 절차를 선택했다.
- 검증: PowerShell 정규식으로 변경 Markdown의 로컬 링크 1개를 확인해 오류 0건, `git diff --check` 통과, 최종 diff·status에서 의도한 문서 3개만 변경됨을 확인했다. 문서만 변경하여 코드 테스트·GPU/Orin smoke는 실행하지 않았다. 규칙의 장기적인 시간·토큰 절감 효과는 아직 측정하지 않았다.

### Decision impact / Next action / Git

- 프로젝트 MVP·연구·dataset recipe의 상태는 변경하지 않는다. 다음 material task부터 이 절차를 적용하고 반복 병목이 나타날 때만 추가 도구를 재평가한다.
- 현재 개발 후속 작업은 승인 전 SOHAS source/label/sample audit이며, 팀 legacy 재현과 독립적으로 진행한다.
- Commit: 이 기록을 포함하는 commit.

## 2026-10-02 - 신규 knife detector 후보와 데이터 보관 경계 재정렬

상태: 공식 Git image metadata 중복 `VERIFIED`; 후보 recipe `PROPOSAL`; Google Drive 폴더 `IMPLEMENTED`/목록 확인; raw source·CUDA 학습 `PLANNED`

### Goal / Why

- legacy 재현은 다른 팀원이 담당하고, 신규 detector 담당자는 source audit와 핵심 모델 제작을 독립적으로 진행한다.
- 여러 GPU를 사용할 수 있어도 중복 데이터셋을 조합한 학습을 필수 실험으로 늘리지 않고, hard-negative 효과와 target CCTV 적응 효과를 분리한다.

### Scope / Changed files

- `dataset-source-strategy.md`에 R1(SOHAS 검수 양성+음성), H1(같은 양성만), T1(R1+직접 촬영 training session)을 우선 후보로, L1(선별 legacy)/U1(고유 DaSCI)/S1/G1을 조건부 보강으로 기록했다. L0 model은 별도 트랙이며 그 데이터의 선별 활용 가능성까지 없애지 않았다. 최종 recipe의 팀 승인 전까지 모두 `PROPOSAL`이다.
- `project-plan.md`, `pre-orin-work-plan.md`, `open-decisions.md`, `model-data-plan.md`, `prior-work-and-dataset-review.md`, `verification.md`, README의 L0 선행 의존과 후보·증거 설명을 정합화했다. 코드·모델·raw data는 바꾸지 않았다.
- 팀 Google Drive의 [모델개발_데이터셋·실험결과](https://drive.google.com/drive/folders/1tBI7EkxKLN41CwHWA60ENXCgOw_0iYiz)에 원본(권리확인 후)/검수·분할명세/학습결과/독립평가 폴더를 만들고 목록으로 확인했다. [metadata 보고서](../reports/datasets/sohas-dasci-metadata-2026-10-02/report.md)만 [Drive 보관본](https://drive.google.com/file/d/1h10H-lSCS81TbUTP8epF0qotx5MVkzDy/view?usp=drivesdk)으로 업로드하고 metadata로 파일·부모 폴더를 재확인했다. 원본·자체 촬영 영상은 업로드하지 않았다. 10 GB 미만 로컬 staging을 허용한다.

### Environment / Evidence / Limitations

- Windows PowerShell과 GitHub REST Git tree metadata. 원본 저장소 `ari-dasci/OD-WeaponDetection`의 `master` commit `48860b990e4d4f57fe100248887fceb248475dc8`에서 SOHAS train/test image 5,002/857장, DaSCI image 2,078장을 집계했다. DaSCI 1,985장은 SOHAS와 basename 및 Git blob ID가 일치하고 93장만 byte-unique 후보이다. SOHAS image 5,859장 대비 XML 5,942개로 orphan XML 83개가 있다.
- Git blob 일치는 바이트 동일성 근거지만, 남은 93장의 perceptual 중복·annotation·target 적합성과 SOHAS negative의 knife 부재는 검증하지 않았다. SOHAS README/License 표기 충돌과 ACF 원 저장소 404도 여전히 남아 있다. 공개 원본 다운로드·공유·학습은 이번 작업에서 수행하지 않았다.

### Decision impact / Next action

- SOHAS 사용 조건과 raw package를 확인하고 source/label/sample audit를 수행한다. 승인 전에는 R1/H1도 학습하지 않는다.
- 공통 tuning/독립 test를 먼저 설계하고 R1/H1을 같은 모델·설정에서 비교한다. 직접 촬영 session이 준비되면 T1을 판단한다. L0 완료는 이 작업을 막지 않는다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-29 - 수업 자료와 개발 저장소 폴더 통합

상태: 로컬 폴더 구조 `IMPLEMENTED`; Git·submodule·Python import·CLI `VERIFIED`; Orin 실기기와 관련 없음

### Goal / Why

- 바탕화면의 수업 자료 폴더를 상위로 두고 개발 저장소를 그 안으로 옮긴다. GitHub 동기화 범위를 개발 저장소로 한정한다.
- 비개발 자료는 날짜·내용 중심 파일명과 역할별 폴더로 정리하되, 개인정보가 포함될 수 있는 채팅·팀원 사진·서명은 저장소 밖에 둔다.

### Scope / Changed files

- 기존 `Desktop/00_Development_Github`을 수업 상위 폴더의 `03_개발_GitHub`으로 이동했다. 저장소 내부 소스·모델·실험 데이터 이름은 바꾸지 않았다.
- 상위 폴더의 오래된 별도 `.git`은 현재 저장소 `main`의 조상 commit `f209940`을 가리켰고, 고유한 추적 변경 없이 파일 이동으로 인한 삭제 상태였다. 삭제하지 않고 `99_이전Git_백업/.git`에 보존했다.
- 상위 폴더의 비개발 자료 46개 중 SHA-256이 정확히 같은 제안서 PDF와 주간보고서 양식 HWP 각 중복본 1개를 제거했다. 나머지 44개를 날짜 접두어와 역할별 폴더로 정리했다. 상위 `260929_폴더안내.md`가 구조·날짜 해석·동기화 범위를 설명한다.
- 이 저장소에서는 `AGENTS.md`, `README.md`, 이 개발 로그와 검증 매트릭스의 경로·상태만 갱신한다.

### Environment / Verification / Limitations

- Windows PowerShell, Git `main`; 이동 전후 `git status --short --branch`는 clean, `origin/main`과 일치. `git pull --ff-only`는 already up to date. 고정된 `Crime_Prediction` submodule commit `5e228697`도 유지됐다.
- 로컬 `.venv-ml` 이동 후 이전 절대 경로의 editable `.pth`와 CLI launcher가 깨졌다. Python 3.11.9·현재 setuptools에서 한글 경로의 `pip install -e .`는 cp1252 `UnicodeEncodeError`로 실패했다. 일반 `pip install . --force-reinstall --no-deps --no-build-isolation`로 launcher를 갱신하고, 로컬 `.pth`에 가상환경 기준 상대 `src` 경로를 먼저 넣어 live source import를 복구했다. 이 `.venv-ml` 변경은 Git에 포함되지 않는다.
- 복구 시험 중 만든 `%LOCALAPPDATA%/edge-threat-response-worktree` junction은 제거 명령이 호스트 정책에 막혀 남아 있다. 실제 파일 복사본은 아니며 새 저장소를 가리키는 로컬 링크다. 개발 경로로 사용하지 않는다.
- 이후 source import와 `etr-dataset --help`, `etr-replay --help`가 실행됐다. `python -m unittest discover -s tests -q`는 56개 전부 통과했고 `git diff --check`도 통과했다. 장비 기능 검증은 이번 파일 정리의 범위가 아니다.

### Decision impact / Next action

- 이후 개발 작업은 새 `03_개발_GitHub` 경로만 사용한다. 기존 절대 경로를 하드코딩한 외부 자동화가 있다면 별도로 갱신해야 한다.
- 구형 가상환경의 설치 문제는 로컬에서 우회 복구했지만, 새 환경의 editable 설치는 경로 인코딩 문제를 확인한 뒤 실행한다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-26 - 중복·과거형 문서 정리

상태: 문서 구조 `IMPLEMENTED`; 내부 참조·변경 범위 검증은 아래 명령 결과로 기록

### Goal / Why

- 현재 MVP와 실행 상태를 빠르게 찾을 수 있도록 중복된 계획 문서와 끝난 단계 중심 문구를 줄인다.
- 과거 결정·실험 증거는 보존하면서 현행 작업 순서가 오래된 초안에 의해 혼동되지 않게 한다.

### Scope / Changed files

- `research-or-product-plan.md`는 확정된 MVP 명세·Project Plan과 내용이 겹치고 MVP에서 제외한 threat score 초안이 남아 있어 삭제했다.
- `implementation-plan.md`은 이미 끝난 Increment A/B와 현재 구조·Pre-Orin 계획을 중복해 삭제했다. 두 파일의 Git 이력은 복구 가능하다.
- 빈 미추적 `C++기반 코드 전환 가능성.txt`를 제거했다. 파일 크기는 0 byte였고 Git에는 추적된 적이 없다.
- `pre-orin-work-plan.md`를 남은 W4 사람 검수·source audit·CUDA 학습·Orin 통합 중심으로 다시 작성했다.
- README, Master Plan, 문서 운영 규칙, architecture, open decisions, verification, 2026-09-04 회의 기록과 legacy asset 기록의 오래된 참조·상태를 정리했다.
- Code, dataset, model, run result와 회의·실험 원본 증거는 변경하지 않았다.

### Environment / Verification / Limitations

- 환경: Windows PowerShell, Git `main`. `git pull --ff-only` → already up to date.
- `rg --files docs`, 문서별 참조 검색, Git status와 파일 크기로 삭제 범위를 확인했다.
- README·AGENTS·docs의 Markdown 문서 19개를 검사했고 로컬 파일 링크 오류는 0건이었다. 삭제 문서의 현행 참조는 없고 과거 개발 로그의 언급만 남겼다.
- `git diff --check`와 변경 범위 확인을 commit 전 실행한다. 문서 전용 작업이어서 code test는 실행하지 않는다.
- 보고서와 과거 회의 요약은 당시의 사실을 보존한다. 현재 상태로 읽어야 하는 부분에는 최신 기준 문서 링크를 추가했다.

### Decision impact / Next action

1. Legacy 128장 사람 검수 및 L0 사용 범위 결정.
2. 권리·라벨·중복 gate를 통과한 공개 source만 추가 평가.
3. 승인된 데이터의 CUDA baseline과 Orin 실기기 통합 증거 확보.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-26 - 선행연구 검토 정정과 역할별 dataset 평가 기준

상태: 문헌·저장소 desk review `VERIFIED` (표기·접근 상태 한정), 평가 절차 `DECISION`, raw package·legacy 사람 판정·source 채택 `PLANNED`

### Goal / Why

- GPT가 작성한 선행연구·dataset 자료의 사실관계와 과장된 점수·채택 표현을 고쳐 연구 근거로 쓸 수 있게 한다.
- 다음 작업인 legacy 128장 사람 검수와 공개 source 표본 검수에 동일한 역할별 판정 기준을 적용한다.

### Scope / Changed files

- `prior-work-and-dataset-review.md`를 재작성해 논문별 확인 사실, 우리 구성요소와의 관계, 적용 한계 및 공개 dataset의 역할을 명시했다.
- `dataset-evaluation-criteria.md`를 추가해 권리·라벨·독립성 gate, training/image/event/synthetic 역할별 질문, legacy `review.csv` 열 정의를 기록했다.
- `dataset-source-strategy.md`, `model-data-plan.md`, `open-decisions.md`, `architecture.md`, `verification.md`, `documentation-governance.md`, README를 정합화했다.
- 코드·raw dataset·검수 CSV·모델과 학습 run은 수정하지 않았다. 기존 C++ 관련 미추적 파일도 변경하지 않았다.

### Evidence / Result

- OD-WeaponDetection 공식 README의 CC BY-SA 4.0 표기와 같은 저장소 `License.md`의 CC BY 4.0 전문이 충돌한다. 실제 적용 범위 확인 전 권리 gate 미통과로 기록했다.
- ACF 논문이 인용한 GitHub 저장소는 2026-09-26 `git ls-remote`에서 repository not found였다. 외부 image 평가 **후보**로 유지하며 사용 가능성을 확정하지 않았다.
- DISARM 공식 페이지에서 현재 공개된 것은 test subset임을 확인했다. DISARM temporal window는 bbox 연속성을 사용하고 우리 K-of-N boolean window와 구현이 다르다.
- local `review.csv` header가 문서의 8개 판정 열과 일치하고 contact sheet 8장이 존재함을 확인했다.
- 선행연구의 근거 없는 100점 순위를 제거하고, 공개 bbox dataset만으로 B0~B3 event metric을 평가할 수 없다는 경계를 추가했다.

### Verification / Limitations

- 검증 환경: Windows PowerShell, 공식 논문·제공자 저장소·dataset card의 공개 페이지와 현재 로컬 저장소.
- `git pull --ff-only` → already up to date. 문서 변경이므로 code test는 실행하지 않았다. `git diff --check`와 내부 링크 검사는 commit 전 실행한다.
- 외부 raw package, bbox 시각 품질, image 중복, 성능, 실제 CCTV event annotation은 확인하지 않았다. 특정 공개 dataset은 아직 `ADOPTED`가 아니다.

### Decision impact / Next action

1. 다음 gate는 legacy 128장의 사람이 하는 visual review다. CSV는 현재 판정 전 상태로 보존한다.
2. 결과를 source/version·split·bbox size 구간으로 집계해 L0의 전체/선별/역사적 기준 중 역할을 결정한다.
3. 이후 SOHAS 권리 충돌과 source package를 확인하고, 통과한 source만 표본·중복 audit으로 진행한다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-22 - Target-CCTV dataset source strategy and admission gates

상태: target domain·source 역할 분리 `DECISION`, individual source import·recipe·full training `PROPOSAL`/`PLANNED`

### Goal / Why

- 공개 dataset의 이미지 수나 설명만으로 source를 합쳐 기존 legacy의 domain mismatch·duplicate·split leakage 문제를 되풀이하지 않는다.
- 최종 설치 환경에 가까운 data를 학습·외부평가·synthetic 보조 실험으로 분리해 detector 성능과 B0~B3 event 판단 실험의 근거를 보존한다.

### Scope / Changed files

- `docs/dataset-source-strategy.md`를 새로 만들어 target CCTV assumption, source별 역할·적용 한계, first recipe 순서, admission audit, 근거와 즉시 작업을 기록했다.
- README, master plan, MVP specification, model/data plan, open decisions, architecture, verification, pre-Orin plan, documentation governance를 해당 기준으로 정합화했다.
- 코드, raw dataset, external download, model weight, training config 및 model run은 변경하지 않았다.

### Decision

- 목표 domain은 약 3 m 높이의 fixed indoor CCTV가 사람을 elevated/oblique angle로 보는 복도·출입구·공용공간이다. 작은/먼 knife, person co-occurrence, 손·팔 occlusion을 우선한다.
- legacy는 사람 review 후 별도의 L0 baseline으로만 사용한다. SOHAS는 첫 public real-world training 후보, DaSCI는 cross-source dedup audit 후 보강 후보로 둔다.
- ACF Knife와 US Mock Attack은 Dataset v1 training에 넣지 않고 external CCTV holdout 후보로 보존한다. Simuletic 114장은 primary recipe에서 제외하며 real-data baseline 뒤 synthetic ablation에만 사용한다.
- publicly described source 수치나 license는 raw package·usage terms·manifest audit 전 project inventory나 성능 근거로 쓰지 않는다.

### Evidence / Verification

- 공식 source page와 ACF peer-reviewed paper를 desk review했다. SOHAS repository는 CC BY-SA 4.0을 명시한다.
- ACF paper는 full-HD CCTV와 small knife 문제를 설명하지만, raw package manifest·license·접근성은 확인하지 않았다. 논문 본문의 ACF Knife image 수와 표의 label 수 표기가 달라 raw manifest가 권위 있는 inventory가 되어야 한다.
- 문서 링크와 상태 표현을 검토했으며, code test는 source code가 변경되지 않아 실행하지 않았다. `git diff --check`는 commit 전 실행한다.

### Limitations / Next action

1. legacy review CSV의 human verdict가 아직 없어 L0 full training도 승인되지 않았다.
2. SOHAS, DaSCI, ACF, US Mock Attack의 raw package·license·source/session metadata와 100장 표본 audit이 남아 있다.
3. SOHAS–DaSCI–legacy exact/perceptual duplicate report가 없으므로 source 병합이나 CUDA full training을 시작하지 않는다.
4. audit 승인 후에만 R1 SOHAS recipe, external CCTV holdout 및 CUDA run을 확정한다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-15 - W4 review pack·W5 detector/video·W6 CUDA handoff 구현

상태: W4 tooling·W5·W6 handoff `IMPLEMENTED`/PC `VERIFIED`, W4 사람 판정·CUDA full training·Orin `PLANNED`

### Goal / Why

- Orin 도착 전 legacy dataset의 시각 검수 근거를 만들고, 새 knife weight가 없어도 image/video→canonical detection→B0~B3→metadata/snapshot 전체 경로를 검증한다.
- 첫 full training을 사람의 data review 뒤 CUDA 환경으로 안전하게 넘기고, run·dataset·artifact provenance를 남긴다.

### Scope / Changed files

- `dataset/review.py`, `etr-dataset review-pack`, review requirement와 test를 추가했다.
- `detector.py`, `media.py`, `runtime.py`, `detect_cli.py`에 lazy Ultralytics single/composite adapter, class remap, fail-closed component error, OpenCV image/video, canonical JSONL, latency/provenance와 current-frame snapshot을 구현했다.
- `etr-detect`, `etr-run`, development/legacy smoke config와 detector/runtime test를 추가했다.
- training runner에 Git commit, dataset manifest, artifact hash와 GPU-required preflight를 추가하고 CUDA development profile, Colab notebook, handoff 문서를 작성했다.
- README, architecture, implementation/pre-Orin/model-data plan, open decisions, verification과 재현 가능한 summary/report를 갱신했다.
- legacy submodule과 raw dataset은 수정하지 않았다. review image/CSV, run output, video, snapshot, weights는 Git에서 제외했다.

### Environment / Commands

- Windows build 26200, Python 3.11.9, AMD Ryzen 5 4600H, CUDA false.
- `.venv-ml`: torch 2.14.0+cpu, torchvision 0.29.0, Ultralytics 8.4.152, OpenCV 5.0.0.93, Pillow 12.3.0.
- W4: `etr-dataset review-pack ... --per-stratum 12 --seed 20260915`.
- W5: 실제 YOLO26n person + legacy `customknife_v1.1.pt` composite로 image와 3-frame video를 `etr-detect`/`etr-run` 실행하고, 생성 detection JSONL을 `etr-replay` B0~B3에 재사용했다.
- W6: CUDA-required local preflight를 실행해 CUDA false를 명시적으로 탐지했다. 실제 full training은 실행하지 않았다.

### Results / Measured evidence

- W4: exact duplicate 제외 7,361장 decode 성공, 오류 0. deterministic sample 128장, contact sheet 8장 생성.
- 표본 구성: source 92/36, split train 71/val 27/test 30, 최소 bbox area bucket tiny 14/small 13/medium 18/large 83.
- 개발자가 contact sheet 8페이지 전체를 확인했으며 사람 동반 장면과 제품·주방·손/knife 클로즈업·워터마크·저해상도 장면이 혼재했다. 같은 인물·배경의 반복은 filename/exact-hash만으로 near-duplicate/session 분리가 완전하지 않을 수 있음을 보여준다. row별 사람 판정은 아직 완료되지 않았다.
- W5 actual PC smoke: 3 valid frames, canonical detections 9개, B3 event frame 1에서 1회, JPEG snapshot 1장, action error 0.
- 같은 detection JSONL의 event frame은 B0=0, B1=1, B2=0, B3=1이었다.
- model cold load가 포함된 첫 frame 6,210.685 ms, 3-frame median inference 106.694 ms. 이 수치는 배포 성능 근거가 아니다.
- W6 local preflight: expected exit 2, `torch.cuda.is_available() == false`; Git/config/data/dataset manifest와 환경 hash evidence 생성 확인.

### Verification / Limitations

- `python -m unittest discover -s tests -v` → 56 tests, all passed.
- `python -m compileall -q src tests` → passed.
- notebook/training/detector JSON parse → passed.
- `git diff --check` → passed.
- review sample은 전체 품질 보증이 아니며 `review.csv`의 사람 판정 전에는 Baseline v1 학습 승인으로 간주하지 않는다.
- legacy 반복 양성 이미지는 정확도·일반화 평가 자료가 아니다. legacy knife weight의 성능 lineage도 `UNVERIFIED`다.
- 실제 CUDA full training, 선택 detector, 독립 영상, Orin runtime/camera/GPIO와 benchmark는 검증하지 않았다.

### Decision impact / Next action

- composite topology는 구현 가능성이 확인됐지만 P0-05의 최종 detector 결정으로 승격하지 않는다.
- 팀이 local `data/review/legacy-development-v1/review.csv`를 검토하고 baseline 학습 승인·제외 규칙을 기록한다.
- 승인 후 Colab notebook으로 legacy Baseline v1을 학습하고 `best.pt`를 동일 W5 pipeline에 경로 교체해 독립 영상 smoke를 수행한다.
- W7은 Baseline v1을 막지 않으며 DaSCI Knife/SOHAS → Open Images selective → Simuletic smoke 순으로 표본 검토한다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-15 - Spatial v2·knife exporter·YOLO26n CPU smoke 구현

상태: class mapping·spatial v2·dataset exporter·training runner `IMPLEMENTED`/PC `VERIFIED`, detector 성능·CUDA/Orin `PLANNED`

### Goal / Why

- 실제 detector 연결 전에 신규 spatial 정책과 raw/model-local/runtime class 경계를 코드로 고정한다.
- group-aware knife-only dataset이 실제 YOLO 학습까지 연결되는지 작은 CPU smoke로 확인한다.

### Scope / Changed files

- pipeline config schema v2와 `expanded_bbox_only` spatial policy를 추가하고 schema v1 결과를 호환 보존했다.
- `etr-dataset materialize-knife-yolo` exporter를 추가해 polygon→bbox, knife model-local class 0, hardlink/copy, exact duplicate 제거와 manifest를 구현했다.
- config-driven `etr-train`, CPU smoke config와 고정 ML requirement를 추가했다.
- 관련 config, 단위 test, README, 계획·검증 문서와 재현 가능한 smoke summary/report를 갱신했다.
- raw dataset과 legacy submodule은 수정하지 않았다. generated dataset, venv, runs와 weights는 Git에서 제외했다.

### Environment / Results

- Windows/Python 3.11.9, AMD Ryzen 5 4600H, CUDA false.
- `.venv-ml`: torch 2.14.0+cpu, torchvision 0.29.0, Ultralytics 8.4.152, OpenCV 5.0.0.93.
- development split default 70/15/15, seed 20260915: train 5,155 / val 1,104 / test 1,105 planned.
- exact duplicate 3장 제거 후 전체 materialized output: train 5,153 / val 1,104 / test 1,104, 총 7,361 images/labels와 9,057 objects.
- bbox 7,610건과 polygon→bbox 1,447건. output bad label line 0, cross-split source group 0, exact hash 0.
- audit 이후 source image 7,364장과 대응 label의 SHA-256 변경 0건을 재확인했다.
- smoke: train 32 / val 8, 49 objects, 40 images decode 성공, YOLO26n 320 px/1 epoch/batch 4.
- wrapper 측정 training duration 18.282 s. validation과 best/last checkpoint 생성, best checkpoint 재로딩·단일 이미지 inference 성공.

### Verification / Limitations

- `python -m unittest discover -s tests -v` → 46 tests, all passed.
- smoke의 precision/recall/mAP 0은 1 epoch·극소 표본 결과이며 성능 근거로 사용하지 않는다.
- 전체 materialized split은 development default이고 visual label 품질 검수와 최종 연구 split 승인을 대신하지 않는다.
- YOLO26n 선택, detector topology, threshold, CUDA/Jetson 호환성과 성능은 아직 `PROPOSAL`/`PLANNED`다.

### Next action

1. Dataset visual-review pack과 ambiguous annotation 검토 자료
2. fake backend 기반 detector/video/detection-JSONL/snapshot integration
3. CUDA profile·GPU preflight·Colab/학교 GPU 인계 절차

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-15 - Orin 도착 전 작업 재정렬과 CPU smoke 제외

상태: pre-Orin 작업 순서·class mapping·spatial v2 방향 `DECISION`, 실제 adapter·exporter·학습 `PLANNED`

### Goal / Why

- 외부 GPT 평가를 저장소·개발 PC·공식 플랫폼 정보와 대조하고, 현재 노트북에서 어려운 CPU model smoke가 전체 개발을 막지 않도록 작업 경계를 다시 정한다.
- Jetson 도착 전에는 ML dependency가 없는 계약·데이터 변환·adapter/video 골격을 최대한 끝내고, 실제 model·CUDA·hardware 검증은 증거를 만들 수 있는 환경으로 이관한다.

### Scope / Changed files

- `pre-orin-work-plan.md`를 추가하고 README, implementation plan, model/data plan, MVP specification, architecture, open decisions, verification을 정합화했다.
- 코드, dataset, model, ML package와 Jetson 설정은 변경하지 않았다.

### Verified findings and decisions

- 기준 commit `f8acb89`가 원격 `main`과 일치하고 working tree가 깨끗한 상태에서 시작했다.
- Windows Python 3.11.9 환경에 torch·Ultralytics·OpenCV가 설치되어 있지 않다. 현재 순수 로직은 `unittest` 38개가 통과했다.
- CPU training smoke를 pre-Orin 완료 조건에서 제외하고 fake backend·dataset contract·replay integration으로 대체한다.
- raw class, model-local training class, runtime canonical class를 분리한다. knife-only YOLO는 model-local `0=knife`, runtime은 canonical `knife`/ID `1`이다.
- 신규 spatial schema v2는 expanded bbox만 association gate로 사용하고 normalized distance는 진단값으로 남긴다. 기존 v1은 replay 호환성을 위해 보존한다.
- composite detector는 primary proposal일 뿐 최종 topology가 아니다. split·seed·epoch·batch·image size는 development default다.
- 저장소 전체 AGPL 지정은 수행하지 않고 Ultralytics 사용·배포 정책을 P0-12로 추가했다.
- JetPack 7.2.1 actual-board runtime은 native smoke 우선, container 비교 순서로 수정했다.

### Verification / Limitations

- `git pull --ff-only` → already up to date.
- `python -m unittest discover -s tests -v` → 38 tests, all passed.
- 모델 load, CPU/CUDA training, OpenCV video, snapshot, Orin runtime은 수행하지 않았다.
- 공식 플랫폼 지원은 실제 대여 장비의 모델 호환성과 성능을 증명하지 않는다.

### Next action

1. class/config와 spatial v2의 하위 호환 구현
2. knife-only dataset exporter와 visual-review pack
3. fake detector 기반 detector/video/snapshot integration scaffold
4. CUDA training handoff package와 외부 dataset 후보 기록

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-14 - Increment A 판단 core와 B0~B3 replay 구현

상태: pure core·recorded-detection replay `IMPLEMENTED` / 개발 PC `VERIFIED`, detector·영상·snapshot·GPIO·Jetson `PLANNED`

### Goal / Why

- 실제 모델과 Jetson이 준비되기 전에 연구 핵심인 geometry association, K-of-N, 상태 전이와 B0~B3 차이를 결정론적으로 검증한다.
- 향후 detector, camera, snapshot, GPIO adapter가 따를 입력·event·오류 계약을 고정한다.

### Scope / Changed files

- `src/edge_threat_response/`에 domain, config, spatial, temporal, state machine, ports, pipeline, replay loader와 `etr-replay` CLI를 구현했다.
- `configs/replay/development.example.json`과 synthetic detection fixture를 추가했다.
- geometry·K-of-N·전 상태·cooldown/rearm·B0~B3·event 중복 억제·port 실패 격리·replay validation·CLI test를 추가했다.
- 실제 영상 decode, detector, model weight, camera, snapshot 저장, GPIO, Jetson runtime, dataset 학습은 수행하지 않았다.

### Implemented contracts and judgment

- reliable knife마다 중심점이 가장 가까운 person을 선택하고 person bbox diagonal로 거리를 정규화한다. 거리 threshold와 확장 person bbox 포함을 모두 만족해야 associated다.
- knife presence와 associated-pair presence에 별도 K-of-N buffer를 사용한다. `missing`·`detector_error`도 false sample로 window에 포함하고, N개가 차기 전이라도 K개 true이면 확인한다.
- B0는 current knife, B1은 knife K-of-N, B2는 current association, B3는 association K-of-N으로 한 pipeline에서 predicate만 바꾼다.
- `CONFIRMED` 진입당 event·alarm을 한 번만 발생시키고 근거 소실 시 alarm을 해제한다. cooldown은 설정된 연속 clear sample 뒤에만 rearm된다.
- event recorder 실패는 alarm을 차단하지 않는다. snapshot port 실패와 action 오류는 frame evidence에 명시한다.
- tracking이 없으므로 temporal signal은 동일 person이 아닌 source-level boolean이다.

### Environment / Commands / Verification

- 환경: Windows, Python 3.11.9, editable package `edge-threat-response 0.1.0`
- 테스트: `python -m unittest discover -s tests -v` → 38 tests, all passed
- 구문 검사: `python -m compileall -q src tests` → passed
- 설치: `python -m pip install -e .` → passed
- CLI smoke: `etr-replay --input tests/fixtures/replay/basic.jsonl --config configs/replay/development.example.json --output-dir reports/replay/increment-a-smoke` → passed, action error 0
- Git commit: 이 기록을 포함하는 commit

### Measured software-smoke result

- 동일 9-frame synthetic detection 입력에서 최초 event frame: B0=0, B1=1, B2=1, B3=2
- cooldown 후 두 번째 event frame: B0=7, B1=8, B2=7, B3=8
- mode별 event 2개, event recorder/alarm action error 0

### Known limitations / Decision impact

- 이 결과는 detector 정확도, 실제 frame snapshot, GPIO, Jetson 성능 또는 연구 가설을 검증하지 않는다.
- development config의 confidence, distance, bbox expansion, K/N, rearm 수치는 테스트 fixture용이며 최종 파라미터가 아니다.
- frame rate와 시간 간격이 불규칙한 실제 입력에서도 frame-count K-of-N을 쓸지는 baseline에서 sampling contract와 함께 확인해야 한다.
- Increment B는 P0-05 detector topology와 P0-09 runtime 결정 뒤 진행한다.

### Next action

1. D2 sample review로 external/legacy source와 ambiguous annotation rule을 승인한다.
2. Orin Nano 수령 시 hardware/JetPack inventory와 container GPU smoke를 수행한다.
3. detector topology·runtime을 고정한 뒤 video/detector/snapshot adapter를 Increment B로 연결한다.

## 2026-09-14 - D1 dataset audit·manifest·split planning 도구 구현

상태: D1 `IMPLEMENTED`, synthetic/legacy structure `VERIFIED`, 시각 품질·외부 source·학습 `PLANNED`

### Goal / Why

- source별 class 의미를 보존하면서 YOLO bbox/polygon dataset을 일관되게 검사한다.
- 동일 원본 group과 exact duplicate가 train/test에 나뉘는 누수를 실제 학습 전에 탐지·방지한다.

### Scope / Changed files

- `pyproject.toml`과 `src/edge_threat_response/dataset/`에 registry, label parser, audit, manifest, report, group split planner와 CLI를 구현했다.
- `configs/datasets/`에 JSON schema와 legacy v1.0/v1.1 registry를 추가했다.
- `tests/`에 parser·registry·audit·split·CLI fixture test를 추가했다.
- `reports/datasets/legacy-2026-09-14/`에 추적 가능한 summary와 Markdown report를 생성했다. 대용량 manifest와 issues JSONL은 재생성 가능하므로 Git에서 제외했다.
- legacy submodule과 raw image/label은 수정하지 않았다. 외부 다운로드·실제 split 적용·학습은 수행하지 않았다.

### Implemented behavior

- source별 raw→canonical class mapping을 registry load 시 검증한다.
- YOLO normalized bbox와 polygon을 구분하고 class, finite coordinate, boundary, positive extent를 검사한다.
- image/label pairing, empty label, orphan, case-insensitive duplicate stem을 검사한다.
- stable image ID, source/group/split, source/license reference, annotation·class counts, SHA-256을 JSONL manifest로 생성한다.
- original split의 source-group·exact-hash leakage를 탐지한다.
- split planner는 source group과 exact duplicate 연결요소를 하나의 assignment unit으로 배치하며 raw 파일은 이동하지 않는다.
- audit은 CI용 fail-on severity와 알려진 legacy 문제를 inventory할 `--fail-on never`를 분리한다.

### Environment / Commands / Verification

- 환경: Windows, Python 3.11.9, editable package `edge-threat-response 0.1.0`
- 테스트: `python -m unittest discover -s tests -v` → 13 tests, all passed
- 구문 검사: `python -m compileall -q src tests` → passed
- 설치·CLI: `python -m pip install -e . --no-deps`, `etr-dataset --help` → passed
- 전체 audit: `etr-dataset audit --registry configs/datasets/legacy.json --repo-root . --output-dir reports/datasets/legacy-2026-09-14 --fail-on never`
- split smoke: 전체 manifest, development-only ratio 0.70/0.15/0.15, seed 20260914 → 7,364 eligible, 0 excluded, 3,552 groups; raw 파일 변경 없음
- lint: `ruff`는 개발 PC에 설치되어 있지 않아 실행하지 못했다.
- Git commit: 이 기록을 포함하는 commit

### Measured result

- images 7,364, objects 9,060, valid label files 7,364, invalid/missing/empty 0
- annotation: bbox 7,613, polygon 1,447; raw class `0` 9,060건을 canonical knife `1`로 mapping
- unique source groups 3,552, original split crossing groups 317
- exact duplicate image groups 3, exact hashes crossing original splits 0

### Known limitations / Decision impact

- image decode·손상 검사와 시각적 label 품질 검수는 하지 않는다.
- filename grouping은 registry가 지정한 규칙의 결과이며 실제 촬영 session ground truth가 아니다.
- perceptual near-duplicate 검사는 구현하지 않았다.
- smoke-test split 비율과 seed는 연구 결정이 아니며 어떤 학습 dataset에도 적용하지 않았다.
- legacy 기존 split은 최종 detector 평가에 사용하지 않고 승인된 source/session group 기준으로 다시 계획해야 한다.

### Next action

1. 외부·legacy sample의 시각 검수와 ambiguous annotation rule을 팀이 확정한다.
2. 시스템 Increment A의 domain·spatial·temporal·state-machine·B0~B3 core를 구현한다.
3. 승인 source가 정해진 뒤에만 D2 importer와 processed recipe를 추가한다.

## 2026-09-14 - 모델·데이터 준비 구현 범위 확정과 legacy dataset 구조 점검

상태: D1 구현 범위·class contract `DECISION`, 외부 dataset·detector·학습 `PROPOSAL`, legacy 구조 `VERIFIED`

### Goal / Why

- detector 재학습 전에 raw label 의미, provenance, split leakage를 확인해 잘못된 2-class 병합과 평가 누수를 방지한다.
- 시스템 core 개발과 병렬로 진행할 수 있는 최소 dataset tooling만 고정하고 대규모 다운로드·학습은 근거가 생길 때까지 미룬다.

### Scope / Changed files

- `model-data-plan.md`를 추가하고 implementation plan, README, AGENTS, project plan, open decisions, verification, legacy asset 기록을 갱신했다.
- legacy submodule은 읽기 전용으로 조사했으며 dataset·weight·source code를 수정하지 않았다.
- 외부 dataset 다운로드, 신규 코드 구현, model load·학습·추론은 수행하지 않았다.

### Verified findings

- legacy v1.0 1,183장과 v1.1 6,181장, 총 JPG 7,364장과 basename이 일치하는 label을 확인했다. missing image, missing label, empty label file은 0개다.
- 두 dataset은 모두 `knife` 단일 클래스이고 9,060개 annotation의 raw class ID는 전부 0이다.
- annotation은 bbox 7,613개와 polygon 1,447개가 혼재한다.
- filename source group 기준 v1.0 내부 3개 group이 split을 교차하며, 두 version을 합치면 317개 group이 기존 split을 교차한다.
- COCO의 person/knife class, Open Images의 box 규모·Person/Knife class, Simuletic sample의 114장·synthetic·person/knife·CC BY 4.0 선언을 각 공식/제공자 페이지에서 확인했다.

### Decisions and judgment

- detector output은 person/knife 두 logical class로 유지하되 단일 2-class model은 확정하지 않는다.
- raw source class map을 별도로 관리하고 processed dataset에서만 canonical `0=person`, `1=knife`를 사용한다.
- D1은 registry·manifest, bbox/polygon validator, exact duplicate와 group split leakage, report, fixture test까지 구현한다.
- source별 downloader, 실제 병합, training wrapper는 각각 sample 승인과 detector 결정 뒤로 미룬다.
- legacy knife-only data를 재사용할 수 있는 composite person+knife detector를 우선 후보로 두고, unified model은 person annotation 완전성 확보 시에만 검토한다.

### Evidence / Limitations

- 파일 개수·YAML·label token structure·filename group을 자동 집계했다. image 내용, bbox/polygon의 시각적 정확성, upstream source 접근성, 개별 image license는 검수하지 않았다.
- exact image hash와 near-duplicate 검사는 아직 구현·실행하지 않았다.
- provider가 제시한 dataset 설명은 후보 근거이며 프로젝트 적합성이나 성능을 증명하지 않는다.

### Environment / Verification commands

- 환경: Windows, PowerShell, 기준 작업공간 `00_Development_Github`
- 원격 동기화: `git pull --ff-only`
- legacy 조사: `Get-ChildItem`, `Get-Content`, `rg`, label token/group 집계
- 공식 근거: Ultralytics COCO docs, Open Images V7와 boxable class CSV, Hugging Face provider dataset card
- Git commit: 이 기록을 포함하는 commit

### Next action

1. 시스템 Increment A와 dataset D1 중 착수 순서를 정해 작은 단위로 구현한다.
2. D1 결과로 legacy exact duplicate와 split leakage report를 생성한다.
3. 팀이 외부 후보 sample과 ambiguous annotation rule을 검토한 뒤 D2 source를 승인한다.

## 2026-09-14 - 신규 기준 플랫폼을 Jetson Orin Nano로 변경하고 구현 단계를 고정

상태: 플랫폼·구현 순서 `DECISION`, 실기기·ML runtime `PLANNED`

### Goal / Why

- 구형 Jetson Nano 환경에 신규 코드를 맞추지 않고 최신 Jetson Orin Nano 지원 환경을 기준으로 개발한다.
- 실기기와 detector가 준비되기 전에도 연구 핵심인 spatial·temporal·state-machine·B0~B3를 PC에서 검증할 수 있도록 작업을 분리한다.

### Scope / Changed files

- `implementation-plan.md`를 추가하고 README, AGENTS, project plan, MVP specification, architecture, open decisions, verification, research plan을 정합화했다.
- 소스 코드, 모델, dataset, container, Jetson 설정은 변경하지 않았다.

### Decisions

- 신규 기준 플랫폼은 Jetson Orin Nano Developer Kit, 고정 기준 소프트웨어는 JetPack 7.2.1 / Jetson Linux 39.2.1이다.
- 기존 Jetson Nano 4GB는 legacy baseline과 선택적 cross-device 비교용으로 격리한다.
- B0~B3 ablation은 동일 Orin 장비·detector·입력·설정에서 수행하며 Nano/Orin 비교와 섞지 않는다.
- 첫 구현은 platform-neutral pure core, JSONL detection replay, mock alarm·metadata, B0~B3와 테스트다.
- 실제 video/detector는 model/runtime 결정 후, camera/GPIO/resource adapter는 Orin inventory와 runtime smoke test 후 연결한다.
- tracking이 없는 MVP의 K-of-N은 동일 개인이 아니라 source-level association boolean을 집계한다.
- legacy가 person과 knife에 별도 모델을 사용하는 만큼 단일 2-class 재학습은 자동 채택하지 않고 person annotation 완전성을 먼저 확인한다.

### Evidence / Limitations

- 2026-09-14 NVIDIA 공식 페이지에서 JetPack 7.2.1, Jetson Linux 39.2.1, Ubuntu 24.04, kernel 6.8, CUDA 13.2.1, cuDNN 9.20.0, TensorRT 10.16.2, VPI 4.1.3과 Jetson Orin Family 지원을 확인했다.
- Orin Nano quick-start 문서에서 JetPack 7.2.1 설치가 USB의 Jetson ISO 방식이며, 구형 firmware에는 JetPack 6.x-generation UEFI/QSPI update path가 필요함을 확인했다.
- NVIDIA는 재현 가능한 Jetson AI/CUDA 환경 분리를 위해 Docker 사용 경로를 제공한다.
- 실제 대여 장비의 SKU·RAM·저장장치·firmware와 PyTorch/Ultralytics/container 호환성은 확인하지 않았다. 공식 지원 표는 프로젝트 모델의 동작·성능 증거가 아니다.

### Environment / Verification commands

- 환경: Windows, PowerShell, 기준 작업공간 `00_Development_Github`
- 원격 동기화: `git pull --ff-only`
- 문서 확인: `Get-Content`, `rg`
- 공식 근거: NVIDIA JetPack downloads, Orin Nano quick start, Docker setup
- Git commit: 이 기록을 포함하는 commit

### Next action

1. Increment A의 pure core와 replay 계약을 구현한다.
2. Orin 수령 즉시 SKU·RAM·storage·firmware·JetPack 설치 상태를 기록한다.
3. dataset annotation을 audit한 뒤 detector topology와 JetPack 7.2.1 ML runtime을 고정한다.

## 2026-09-07 - MVP Research Specification 확정

상태: MVP 범위·연구 설계 `DECISION`, 구현·실기기 결과 `PLANNED`

### Goal / Why

- 10월 구현과 11월 ablation·논문 결과가 같은 이벤트 정의와 평가 규칙을 따르도록 MVP 범위를 고정한다.
- 단순 weapon presence가 아니라 person-associated knife event를 다루되, 실제 폭력 의도·행동 판별을 주장하지 않는 경계를 명시한다.

### Scope / Changed files

- `mvp-research-specification.md`를 새로 만들고, README, AGENTS, project plan, architecture, open decisions, verification, research plan을 갱신했다.
- 모델 실행, Jetson 설정, threshold 선택, 촬영, annotation, 성능 측정은 수행하지 않았다.

### Decisions

- MVP weapon class는 `knife`만이다. 추가 class는 stretch다.
- bounding-box geometry 기반 person–knife association, K-of-N temporal confirmation, `CLEAR/CANDIDATE/CONFIRMED/COOLDOWN` 상태 머신을 채택한다.
- `CONFIRMED` 진입은 GPIO LED/Buzzer, event metadata, snapshot 1장을 발생시킨다. event clip은 stretch다.
- controlled scenario와 수동 event annotation을 사용한다. distance는 필수, lighting은 선택이다.
- B0 detection-only, B1 temporal-only, B2 spatial-only, B3 spatial+temporal ablation을 핵심 비교로 채택한다.
- stretch 우선순위는 Orin benchmark, TensorRT/FP16, tracking, dashboard, event clip, 추가 class, enclosure/PCB 순서다.

### Evidence / Limitations

- 사용자와의 프로젝트 방향 논의에서 선택된 MVP 범위를 문서화했다.
- K/N, confidence threshold, normalized-distance threshold, expanded-bbox ratio, cooldown, model/runtime, annotation matching rule, development/test split과 정량 목표는 아직 측정 근거가 없어 확정하지 않았다.
- GPT-6 Astra는 코딩·문서·분석 작업의 보조로 활용하되, 실기기·촬영·하드웨어 검증 일정의 단축 근거로 사용하지 않는다.

### Environment / Verification commands

- 환경: Windows, PowerShell, 기준 작업공간 `00_Development_Github`
- 문서 확인: `Get-Content`, `rg`
- 변경 검증: `git diff --check`, `git status --short`
- Git commit: 이 기록을 포함하는 commit

### Next action

1. Nano hardware와 legacy baseline의 실제 실행 가능성을 진단한다.
2. 첫 controlled scenario 샘플로 annotation matching rule과 tuning/test split을 확정한다.
3. baseline 결과를 근거로 model/runtime·threshold·K/N 후보를 결정한다.

## 2026-09-07 - Master Plan과 장기 기록 체계 정비

상태: 문서 기반 `IMPLEMENTED`, MVP 세부 기능 `PROPOSAL`

### Goal / Why

- 12월 최종 데모·보고서·졸업논문까지 프로젝트 방향과 증거 흐름이 흔들리지 않도록 최상위 계획과 문서 역할을 고정한다.
- 10월 31일을 단순 데모가 아닌 반복 가능한 정량 실험 착수 시점으로 운영한다.

### Scope / Changed files

- `docs/project-plan.md`를 추가하고 README, AGENTS, architecture, open decisions, verification, documentation governance, research plan을 정합화했다.
- 2026-08-27 주제 탐색 회의와 2026-09-01 OT의 공개 가능한 결정 근거를 `meeting-decisions/`에 요약했다.
- 기능 구현, 모델 학습, MVP 확정, Jetson 설정 변경은 수행하지 않았다.

### Decisions and judgment

- 균형형 MVP 후보는 가장 유력하지만 팀 결정 전까지 `PROPOSAL`로 유지한다.
- tracking, movement, dashboard, clip, Orin 비교는 기본적으로 stretch goal로 분리했다.
- 근거 없는 오경보 30% 감소·recall 5%p 이내 같은 예시 수치는 목표로 채택하지 않았다.
- 프로젝트 목적·범위·일정의 기존 기준 역할을 `research-or-product-plan.md`에서 `project-plan.md`로 이전하고, 전자는 연구·실험 보조 문서로 재정의했다.

### Evidence / Limitations

- 2026-08-27 회의록, 2026-09-01 OT 기록, 2026-09-04 회의록과 저장소의 기존 문서를 대조했다.
- Nano 실기기, legacy model, GPIO, 카메라, 성능은 이번 작업에서 실행하거나 측정하지 않았다.

### Environment / Verification commands

- 환경: Windows, PowerShell, 기준 작업공간 `00_Development_Github`
- 문서·상태 검색: `rg`, `Get-Content`
- 변경 검증: `git diff --check`, `git status --short`
- 원격 기준 확인: `git fetch origin`, `git rev-list --left-right --count main...origin/main`
- Git commit: 이 기록을 포함하는 commit

### Next action

1. Nano와 legacy baseline의 실행 가능성을 진단한다.
2. 사건 정답 규칙과 안전한 controlled scenario를 작성한다.
3. 측정 결과와 일정에 근거해 균형형 MVP를 승인 또는 축소한다.

## 2026-09-07 - 기준 개발 작업공간을 Development_Github로 전환

상태: `IMPLEMENTED` (로컬 Git 연결·동기화 정책), 원격 변경 감시 `NOT ADOPTED`

### 변경

- `Development_Github`를 팀의 기준 개발 작업공간으로 지정하고, `edge-threat-response` 원격 `main` 및 기존 Crime_Prediction submodule 기준 commit에 연결했다.
- 작업 시작 시 `git pull --ff-only`, 의도적 commit 후 자동 push를 적용하는 Git hook 정책을 추가했다.
- 원격 변경을 무조건 자동 pull하는 파일 감시는 작업 중인 변경을 덮어쓰거나 충돌을 숨길 수 있어 채택하지 않았다.

### 검증

- 원격 `origin/main`을 fetch하고 mixed reset으로 working tree를 변경하지 않은 채 index·HEAD를 동기화했다.
- `git status --short`가 비어 있고, submodule이 `5e2286971b0e7a54ede4caa3baa03fe168edc5b8`에 있음을 확인했다.

### 한계

- 자동 push는 의도적으로 commit한 변경에만 적용된다. 작업 중이거나 충돌 가능성이 있는 원격 변경은 자동으로 가져오지 않는다.

## 2026-09-04 - 기존 MIDAS 프로젝트 분석과 발전 방향 기록

상태: `VERIFIED` (문서·산출물 검토), `PROPOSAL` (2026-2 발전 방향)

### 배경

- 2025-2 MIDAS 프로젝트는 Jetson Nano, YOLO 기반 흉기 탐지, GPIO LED·부저 경보, WebSocket 기반 웹 UI를 결합한 프로토타입으로 진행되었다.
- 2026-2 종합설계과제(1)에서는 이를 단순 객체 탐지기가 아닌 상황 인지형 엣지 보안 시스템으로 발전시키고자 한다.

### 확인한 기존 산출물

- 최종 발표자료: `N:\Own\01_YU\프로젝트 및 활동\2025-2_MIDAS\2026-1_MIDAS_MSP_발표자료.pdf` (내용상 2025-11-25 최종 발표)
- 활동 정리: `N:\Own\01_YU\프로젝트 및 활동\2025-2_MIDAS\MIDAS_MSP 활동정리.txt`
- Jetson 프로토타입 코드: `N:\Own\01_YU\프로젝트 및 활동\2025-2_MIDAS\jetson\jetson_knife_detector.py`

### 확인된 사실

- 기존 발표자료는 사람/흉기 탐지, Jetson Nano 추론, LED·부저 경보, WebSocket 기반 모니터링 UI를 목표·성과로 제시한다.
- 발표자료에는 Precision 96.2%, Recall 85.1%, mAP50 93.7%가 제시되어 있다. 데이터셋 분할, 평가 조건, 재현 명령은 현재 작업공간에 확보되지 않아 2026-2 기준으로는 재검증이 필요하다.
- 보관된 프로토타입 코드에는 Jetson 환경 제약과 충돌 가능한 import 순서 및 pandas 의존 결과 처리가 남아 있다. 해당 파일만으로 실기기 정상 동작을 보장할 수 없다.
- Jetson Nano의 부팅·팬·카메라·GPIO 현재 상태와 원본 모델·전체 소스는 아직 확인하지 않았다.

### 제안된 변화

- 단일 프레임 탐지 후 즉시 경보하는 구조를 연속 프레임·상태 머신 기반 경보로 변경한다.
- 사람·흉기의 위치 관계, 추적 ID, 이동 방향, 지속 시간으로 위협 점수를 계산한다.
- 경보 이벤트에 전후 영상 클립, 메타데이터, 시스템 자원 로그를 연결한다.
- Nano를 기준 플랫폼으로 복구·측정하고, Orin Nano 확보 시 동일 기준으로 비교한다.

### 검증

- 기존 폴더의 문서, 최종 발표 PDF 17페이지, 중간보고서 PDF 2페이지, Jetson 관련 텍스트·Python 파일을 검토했다.
- 코드 실행, Jetson 부팅, 모델 추론, GPIO, 웹 UI, 성능 수치 재현은 수행하지 않았다.

### 남은 작업

- 기존 원본 코드·모델·설정·의존성의 소재를 확인하고 Git 저장소로 정리한다.
- Jetson Nano 복구 여부와 최소 실행 환경을 실기기에서 확인한다.
- 개발 대상과 확장축을 `open-decisions.md`의 기준으로 확정한다.

## 2026-09-04 - 기존 MIDAS 자산 선별 및 baseline 보존

상태: `IMPLEMENTED` (선별·보존), 실기기 재현 `PLANNED`

### 배경

- 기존 MIDAS 폴더에는 실행 코드, 환경 메모, 발표·행정 문서, 사진, 접근 정보가 혼재되어 있었다.
- 새 공개 Git 저장소에는 재현 가능한 개발 근거만 포함하고, 민감·행정·대용량 자료는 제외해야 한다.

### 변경

- 카메라·YOLO·GPIO 프로토타입, WebSocket 스트리밍 초안, Jetson 환경 정보, 재플래시 가이드, 활동 정리를 `legacy/2025-2-midas/`에 원본 형식으로 보존했다.
- SSH 접근 정보, 모델·영상, 사진, 발표 자료, 행정 문서와 타 프로젝트 후보는 Git에 포함하지 않았다.
- 세부 목록과 예외 사유를 `docs/legacy-asset-selection.md`에 기록했다.

### 검증

- 원본 폴더의 파일 목록과 텍스트 기반 소스·환경 문서를 대조하여, 보존 파일 5개가 민감 접근 정보·모델·영상·행정 문서를 포함하지 않음을 확인했다.
- 보존한 코드는 실행하지 않았다. 현재 Jetson 장비, 모델 파일, 라이브러리 의존성은 미확인이다.

### 남은 작업

- Jetson Nano의 실제 장비 상태와 원본 모델·프로젝트 전체 소스의 추가 소재를 확인한다.
- legacy 코드의 기능을 새 모듈 구조로 이식하기 전, 재현 가능한 baseline 실행 조건을 확정한다.

## 2026-09-04 - Crime_Prediction 원본 저장소 연결

상태: `IMPLEMENTED` (원본 참조 고정), 실행 재현 `PLANNED`

### 배경

- 기존 MIDAS 폴더에는 모델을 호출하는 코드와 환경 메모만 있었으며, 핵심 가중치·데이터셋·학습 코드는 확인되지 않았다.
- `YEOUL0520/Crime_Prediction` 공개 저장소에서 사람·칼 탐지 모델, 학습 데이터셋, 학습 코드, 웹 프로토타입을 확인했다.

### 변경

- 원본 저장소 commit `5e2286971b0e7a54ede4caa3baa03fe168edc5b8`을 `legacy/2025-2-midas/Crime_Prediction` Git submodule로 고정했다.
- 약 460 MB의 원본 데이터셋·모델을 현재 공개 저장소에 중복 복제하지 않았다.

### 검증

- 원본 저장소의 트리와 README, 학습·보조 Python 파일을 확인했다.
- 원본에는 14,760개 파일, 약 460 MB의 데이터가 있으며, `customknife_v1.1.pt`를 포함한 모델 파일이 존재한다.
- 현재 Jetson Nano에서 원본 모델 또는 코드 실행은 수행하지 않았다.

### 남은 작업

- 원본 모델의 클래스·데이터셋 분할·학습 조건·라이선스를 확인한다.
- 원본 학습 스크립트의 API 키처럼 보이는 값을 원본 소유자가 폐기·재발급하도록 요청하고, 새 구현에서는 환경변수로 관리한다.

## 2026-09-04 - 팀 회의 결정 반영

상태: `DECISION`, 일부 외부 의존성 `PLANNED`

### 결정

- 프로젝트 방향을 상황 인지형 Edge AI 기반 흉기 위협 대응 시스템으로 확정했다.
- 팀 공유 기준 저장소로 `edge-threat-response`를 사용한다.
- Orin Nano 대여 요청을 진행하고, 확보 시 Nano와 비교 실험에 활용한다.
- 고성능 카메라와 하드웨어 가속·안정화 장비를 예산 우선 검토 대상으로 정했다.
- 정기 회의는 매주 목요일 18:00이며, MVP 목표 시점은 2026-10-31 이전이다.

### 영향

- 기능별 MVP 완료 기준과 장비 구매 목록을 2026-10-31 시연 목표에 맞춰 분해해야 한다.
- Orin 대여 승인, 정확한 구매 품목, Tracking·Threat Score·Web Dashboard의 MVP 포함 여부는 아직 확정되지 않았다.

### 기록

- 결정사항 요약은 `docs/meeting-decisions/2026-09-04.md`에 남겼다.
- 원본 회의록은 공개 저장소에 넣지 않고 로컬 수업 자료로 유지한다.
