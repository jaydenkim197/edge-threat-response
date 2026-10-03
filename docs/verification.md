# Verification Matrix

신규 시스템의 판단 core·PC 영상 입력·replay는 개발 PC에서 검증됐지만 Orin 실기기 통합과 성능은 미검증이다. `VERIFIED`는 명령·환경·결과·증거를 확보한 뒤에만 부여한다.

| 요구사항 | 검증 방법 | 환경 | 최근 결과 | 증거 위치 | 상태 |
|---|---|---|---|---|---|
| 이름 선택·모바일 홈 화면 검수 | native form Origin·비관리자 이름 선택·관리자 코드/만료·배정/저장/재접속 tests; Chrome/Android 및 WebKit/iPhone 합성 browser smoke; manifest/icons·installability 검사·PC13 HTTPS 확인 | 개발 PC Python 3.11, PC13 Python 3.12, Chrome Pixel 7 412px, WebKit iPhone 13 390px, 2026-10-04 | 관련 21 tests·JS·compileall、PC13 전체 88 tests 통과; 두 browser 저장/재접속/이어하기/문제 메모 draft 복원 성공; 버튼 46px·가로 overflow 0; 외부 HTTPS 이름 5/5·7개 후보·양 browser 화면/이미지 성공; local/public Chrome installability 오류 0; 실제 새 판정 0건 | `tests/test_team_review.py`, [팀 배포 기록](team-review-deployment.md), ignored `data/review/mobile-qa-20261004/` | PC browser·PC13 외부 HTTPS 이름 선택 `VERIFIED`; 실제 휴대폰 설치·재부팅 복구 `NOT VERIFIED` |
| PC13 팀 데이터셋 중앙 웹 검수 | 8후보 catalog·7개 표본 pack, SOHAS 기존 판정/이력 이관, 로그인/권한/Host·Origin·CSRF/배정/충돌/백업 test, 실제 config의 인증·첫 이미지 smoke, 외부 HTTPS·PC13 시작 작업 확인 | 개발 PC Python 3.11, PC13 Windows Python 3.12, 2026-10-04 | 로컬 84 tests·PC13 관련 5 tests 통과; PC13 이전 6판정·40 history 유지. 외부 `/login` 200·미인증 catalog/image 401, 관리자 HTTPS 로그인 후 7개 후보 catalog와 Dangerous 첫 이미지 200. 개인 계정 5/5 외부 로그인, 7개 준비 후보 공통 `simple-v2` 계약 확인, 새 판정 0건. Dangerous Items knife 임시 매핑, ACF 원본 404 | `tests/test_team_review.py`, `tests/test_provision_team_review.py`, `tools/check_team_review.py`, [배포 기록](team-review-deployment.md), PC13 ignored `data/review/team-server/` | 서버·외부 HTTPS 인증/이미지·개인 로그인 `VERIFIED`; 팀원 판정 저장/재개·재부팅 복구 `NOT VERIFIED`; source 채택 `PLANNED` |
| SOHAS 저장 상태·2-question UI | 실제 DB read-only quick_check/count·SQLite consistent backup, legacy/v2 compatibility·positive/negative mapping tests, 별도 QA browser 저장/다음/재개 | Windows 노트북 / Python 3.11.9, 2026-10-03 | 관찰 시점 실제 5행·history 39건·integrity ok, 수정 전 backup; 전체 79 tests 통과, 화면 질문 2개·별도 QA 1행 저장/재개 성공; 새 8768 서버와 기존 8765 병행 | `tests/test_review_web.py`, ignored 원본 pack의 `backup-before-simple-ui.sqlite3`, 별도 `simple-v2-ui-qa.sqlite3` | 로컬 저장·호환성 `VERIFIED`; 팀 배포/공개 서비스 `NOT VERIFIED` |
| SOHAS 로컬 버튼 검수 UI | store/API validation·재개·입력 보존·version 충돌·Host/Origin/CSRF·CSV export tests, 실제 브라우저 버튼 저장/다음/새로고침/확대/음성 필터, Windows launcher와 wheel build | Windows 노트북 / Python 3.11.9, 2026-10-03 | 전체 76 tests 통과, JS 문법·compileall 통과, 실제 100장 표시; 별도 QA DB 저장/재개 성공, 실제 human DB 0행; launcher 기존 서버 재사용·새 서버 시작 성공, wheel UI 자산 3개 포함 | `tests/test_review_web.py`, `tools/start_review.ps1`, ignored `data/review/sohas-click-review-20261003/`, QA DB | 로컬 UI·저장 `VERIFIED`; 인간 검수·source 채택·학습 `PLANNED` |
| SOHAS 제한된 이미지 검수 pack | pinned 100 image sparse checkout, blob/SHA-256·decode·XML dimension·raw bbox overlay, fixture 및 전체 tests | RTX PC/Pillow, Windows 로컬 테스트, 2026-10-03 | 100 images decode·dimension 검사 통과, 31,100,785 bytes / knife 103 objects / 7 sheets, 전체 72 tests 통과 | `tools/sohas_review_images.py`, `tests/test_sohas_review_images.py`, ignored `data/review/sohas-100-20261003-final/` | sample decode/tooling `VERIFIED`; 인간 검수·좌표·negative·split·학습 `PLANNED` |
| SSH 종료 후 GPU 작업 지속 | 생성 데이터 GPU 작업을 지연 실행, 시작 SSH 종료 후 새 세션에서 exit/summary 확인 | Windows RTX 3060, 2026-10-03 | 단순 Start-Process 방식 실패; Win32_Process CIM 생성 방식은 CUDA/AMP 1 epoch·validation·checkpoint reload 완료, 학습 exit 0, 5.875 s | `docs/training-cuda-handoff.md`, 원격 ignored `runs/pc13-cim-smoke-20261002/` | 단기 연결 종료 `VERIFIED`; full run·재부팅/절전/로그아웃 `PLANNED` |
| Windows SOHAS byte-exact audit | 로컬 SSH, 원격 fast-forward·전체 tests, 별도 autocrlf=false label staging으로 CLI 재실행 | Windows / Python 3.12.4 학습 PC, 2026-10-02 | 70 tests 통과; 초기 XML 4,686개 checkout byte 오류 재현 후 원본 보존·새 staging에서 오류 0, Cloud와 동일 집계·검수 목록 100개 | `reports/datasets/sohas-dasci-metadata-2026-10-02/report.md`, 원격 ignored `data/source-audit/sohas-voc-pc13-byte-exact-20261002/` | label 구조 `VERIFIED`; 이미지·권리·좌표·학습 `PLANNED` |
| SOHAS VOC 승인 전 변환·audit | 다중 knife·좌표 convention·오류/보류·immutability 테스트, 고정 upstream metadata/label dry-run | Cloud Linux x86_64 / Python 3.12.14, 2026-10-02 | 전체 70 tests 통과; image metadata 5,859 / VOC knife 2,349 / YOLO knife 2,277 / count 차이 58 / orphan 83; 100개 검수 대기 표본, image checkout 0 | `tests/test_sohas_voc.py`, `reports/datasets/sohas-dasci-metadata-2026-10-02/report.md`, ignored `data/source-audit/sohas-voc-cloud-final/` | tooling·label 구조 `VERIFIED`; 좌표·시각 검수·권리·split·학습 `PLANNED` |
| SOHAS YOLO–VOC annotation 대조 | 고정 upstream tree·YAML 확인, 원격 label/XML sparse checkout 후 source split/basename으로 knife row/object count 비교 | Windows PowerShell, 2026-10-02, upstream `48860b9` | YOLO image/label 5,859/5,859, DaSCI overlap 1,985 유지; knife YOLO 2,277 vs VOC 2,349, 58 images 불일치 | `reports/datasets/sohas-dasci-metadata-2026-10-02/report.md`, 원격 `data/source-audit/` | annotation 개수 `VERIFIED`; 이미지·좌표·negative·권리·학습 `PLANNED` |
| 원격 RTX 3060 학습 환경 | 격리 venv·pip check·전체 tests·CUDA backward·YOLO26n FP32/AMP 1 epoch·validation·checkpoint reload/infer | Windows, Python 3.12.4, RTX 3060 12 GB, driver 560.94, torch 2.6.0+cu124, 2026-10-02 | pip check 정상; 56 tests 통과; 생성 8 train/4 val에서 두 smoke 통과, AMP 활성화 확인 | `reports/training/pc13-cuda-smoke-2026-10-02/report.md`, 원격 `runs/pc13-cuda-amp-smoke-20261002/` | 학습 plumbing `VERIFIED`; 실제 dataset full run·Orin `PLANNED` |
| 개발 저장소 경로·동기화 경계 | 이동 전후 Git status·remote·submodule 확인, 로컬 import·CLI smoke·단위 테스트 | Windows, 2026-09-29 | `03_개발_GitHub`만 활성 Git; `main`과 `origin/main` 일치, submodule 동일 commit; Python import·CLI help 성공, 56 tests 통과 | `docs/development-log.md`, Git status | `VERIFIED` (로컬 경로·실행), 외부 자동화 경로 `UNVERIFIED` |
| 현행 문서 구조·링크 | 삭제 문서 참조 검색, Markdown 로컬 링크 확인, `git diff --check` | Windows PowerShell, 2026-09-26 | 중복 계획 2개 제거, 문서 19개 로컬 링크 오류 0건; 코드·실험 결과 불변 | `docs/development-log.md`, Git diff | `VERIFIED` (문서 정합성) |
| 기준 저장소·legacy source | Git remote, commit, submodule 상태 확인 | 개발 PC | 저장소 및 고정 submodule 연결 | Git history, `.gitmodules` | `VERIFIED` |
| legacy dataset inventory | image/label·YAML·training script·annotation format·filename group 점검 | 개발 PC, fixed submodule | 7,364 image-label pairs, missing/empty 0, knife-only, bbox 7,613 + polygon 1,447; split 교차 group 확인 | `docs/model-data-plan.md` | `VERIFIED` (구조), 품질·권리 `PLANNED` |
| dataset validator·manifest | synthetic fixture와 legacy read-only audit | Windows, Python 3.11.9 | 13 tests 통과; 7,364 images·9,060 objects 파싱, invalid/missing 0 | `tests/`, `reports/datasets/legacy-2026-09-14/` | `VERIFIED` (구조) |
| group split·leakage 검사 | source/session/exact hash의 split 교차 fixture와 legacy manifest smoke | Windows, Python 3.11.9 | source group·exact duplicate 동시 보존; 기존 split 교차 group 317 탐지 | audit report, split smoke output은 로컬 temp | `VERIFIED` (PC) |
| 개발 PC ML runtime | 격리 venv의 package/GPU inventory | Windows, Python 3.11.9 | `.venv-ml`: torch 2.14.0+cpu, torchvision 0.29.0, Ultralytics 8.4.152, OpenCV 5.0.0.93; CUDA false | training smoke report | `VERIFIED` (PC local) |
| knife-only dataset materialization | 전체 planned manifest export, label·group·hash 재검사 | Windows, development default split | 7,361 images/labels, 9,057 objects, exact duplicate 3장 제거, polygon 1,447건 bbox 변환; bad label/group/hash leakage 0 | local `data/processed`, training smoke report | `VERIFIED` (structure); 연구 split `PROPOSAL` |
| YOLO26n CPU training smoke | 32 train/8 val, 320 px, 1 epoch, batch 4; checkpoint reload/infer | Ryzen 5 4600H CPU | 18.282 s, best/last.pt 생성, 재로딩·1 image inference 성공 | `reports/training/yolo26n-cpu-smoke-2026-09-15/` | `VERIFIED` (plumbing only) |
| Dataset visual-review pack | 전체 decode와 source/split/format/normalized-area stratified sample/contact sheet | Windows, Pillow 12.3.0 | 7,361/7,361 decode 성공, 오류 0; 128장·8 contact sheets | `reports/datasets/legacy-visual-review-v1/`, local `data/review/` | tooling/decode `VERIFIED`; 사람 판정 `PENDING` |
| 공개 source 역할·admission policy | 공식 source page/paper desk review와 target-domain 기준 문서화 | 개발 PC, 2026-09-26 | 약 3 m fixed/elevated indoor CCTV 기준과 training/holdout/synthetic 역할 분리. SOHAS license 표기 충돌·ACF 원 저장소 접근 실패 확인 | `docs/dataset-source-strategy.md`, `docs/dataset-evaluation-criteria.md`, `docs/prior-work-and-dataset-review.md` | 평가 절차 `DECISION`; raw package·권리·sample/dedup audit `PLANNED` |
| SOHAS–DaSCI metadata 중복·보관 위치 | 공식 Git image/XML tree의 basename·blob ID 비교, Google Drive 폴더 목록·보고서 업로드 metadata 재조회 | Windows PowerShell, 2026-10-02; 원본 Git commit `48860b9` | DaSCI 2,078장 중 1,985장 SOHAS와 byte-identical; 93장 byte-unique 후보. SOHAS image 5,859장/XML 5,942개, orphan XML 83개. 팀 Drive 폴더·하위 4개 및 보고서 업로드 확인 | `reports/datasets/sohas-dasci-metadata-2026-10-02/report.md`, `docs/dataset-source-strategy.md`, Drive 보관본 | metadata·Drive 보관 `VERIFIED`; perceptual 중복·이미지 품질·권리·학습 `PLANNED` |
| Pre-Orin adapter/video scaffold | fake detector 단위 test와 actual Ultralytics CPU image/video·JSONL·snapshot integration | 개발 PC, Python 3.11.9 | single/composite remap·fail-closed·3 valid frames·9 detections·B3 event/snapshot 1·action error 0 | `tests/test_detector.py`, `tests/test_runtime.py`, `reports/runtime/pre-orin-detector-integration-2026-09-15/` | `VERIFIED` (PC integration); 성능/Orin `PLANNED` |
| CUDA training handoff | GPU-required preflight, config/notebook JSON validation, evidence contract test | 개발 PC CPU | preflight가 CUDA false를 탐지해 expected exit 2; dataset manifest/config/Git/environment 기록 확인 | `docs/training-cuda-handoff.md`, `configs/training/cuda-baseline-v1.json`, `tests/test_training.py` | tooling `VERIFIED`; CUDA full run `PLANNED` |
| Orin Nano platform inventory | SKU·RAM·firmware·저장장치·JetPack·전원 모드 확인 | Jetson Orin Nano 실기기 | 미수행 | - | `PLANNED` |
| JetPack 7.2.1 설치 | Jetson Linux 39.2.1 부팅과 SDK 구성 확인 | Jetson Orin Nano 실기기 | 공식 지원 환경만 확인, 설치 미수행 | NVIDIA 공식 문서 | `PLANNED` |
| detector runtime smoke test | native GPU access·model load·고정 이미지 추론 후 container 대안 비교 | Orin Nano, 후보 runtime/image | 미수행 | - | `PLANNED` |
| 기존 모델 추론 재현 | 기준 영상/카메라 입력으로 실행 | Orin Nano adapter 또는 격리된 legacy Nano 환경 | 미수행 | - | `PLANNED` |
| GPIO LED·부저 경보 | 정상·경보·복구 상태 수동 시험 | Jetson Orin Nano 실기기 | 미수행 | - | `PLANNED` |
| geometry association | 단위 테스트: v1 distance+bbox와 v2 expanded-bbox-only, 진단 거리, 경계 | 개발 PC, Python 3.11.9 | schema v1 호환과 v2 구현, 관련 test 통과 | `tests/test_spatial.py`, `tests/test_pipeline_config.py` | `VERIFIED` (순수 로직) |
| K-of-N confirmation | 단위 테스트: 조기 확인, dropout, window 만료, 잘못된 K/N | 개발 PC, Python 3.11.9 | 구현, 관련 test 통과 | `tests/test_temporal_state_machine.py` | `VERIFIED` (순수 로직) |
| 4-state machine | 단위 테스트: 전 상태, action 중복 억제, clear rearm | 개발 PC, Python 3.11.9 | 구현, 관련 test 통과 | `tests/test_temporal_state_machine.py`, `tests/test_pipeline.py` | `VERIFIED` (순수 로직) |
| 사건 metadata·snapshot | recorded detection + actual file-input frame, port failure 통합 test | 개발 PC, Python 3.11.9 | metadata·deterministic ID·저장 실패 격리; B3 event에 JPEG snapshot 1장 저장 | `tests/test_pipeline.py`, `tests/test_runtime.py`, integration report | file input `VERIFIED`; camera/보존정책 `PLANNED` |
| B0~B3 ablation | 동일 recorded detection·설정으로 4 policy replay | 개발 PC, Python 3.11.9 | 9 frames에서 최초 event B0=0, B1=1, B2=1, B3=2; mode당 2 events | `tests/test_pipeline.py`, `reports/replay/increment-a-smoke/report.md` | policy/replay `VERIFIED`; 모델·본 실험 `PLANNED` |
| 카메라 복구 | 연결 해제·재연결 fault injection | Jetson 실기기 | 미구현 | - | `PLANNED` |
| 로컬 경보의 오프라인 유지 | 네트워크 차단 상태 시스템 시험 | Jetson 실기기 | 미구현 | - | `PLANNED` |
| 성능·자원 기록 | 고정 입력, 해상도, 런타임으로 benchmark | Orin Nano, 선택적으로 legacy Nano | 미수행 | - | `PLANNED` |
| 개인정보·보존 정책 | 수집 전 정책·기관 요구사항 확인 | 프로젝트 운영 환경 | 미수행 | - | `PLANNED` |

## 2026-10-04 사건 평가·촬영·R1/H1 준비 검증

- **평가기**: 단위/통합 8 tests에서 일대일 매칭·반복/배경 FP·FN·허용 창 경계·음수 지연·ignore 분모·undefined 지표·session/group leakage·replay hash 변조·출력 덮어쓰기 거부를 확인했다. 가상 JSONL→B0~B3→평가에서 B0 TP/FP/FN=1/1/1, B1~B3=2/0/0. 이는 가상 계약 검증이며 모델 성능이 아니다. [가상 보고서](../reports/evaluation/event-evaluator-synthetic-2026-10-04/report.md).
- **촬영 절차**: P1~P4/N1~N5, Near/Medium/Far, inclusive frame/half-open time, source-level GT와 세션/group 분리 양식이 준비됐다. N5는 positive dropout robustness로 정리했다. 실제 촬영·동의·거리·허용 오차·반복 수 동결은 미수행이다.
- **학습 준비**: 기존 training 4 + pair 5 tests에서 공통 양성/val/test·draw budget·pending 승인 차단·batch override·bytes 변조·group split·fake runner evidence/비교를 확인했다. fake fixture는 실제 모델이나 사람 승인 근거가 아니다. 실제 YOLODataset(로컬 Ultralytics 8.4.152)에서도 생성 이미지의 반복 목록 길이를 보존했다(R1 6/5 unique/3 backgrounds, H1 6/2 unique/0 backgrounds). GPU 학습은 실행하지 않았다.
- **개발 PC**: Python 3.11.9에서 `python -m unittest discover -s tests -q` **101 tests 통과**. 실제 CPU/GPU full training·Orin·GPIO 지연은 미검증이다. 원시 runtime 출력은 ignored `runs/event-evaluation-synthetic-v1/`에 있다.
- **PC13**: commit `9833a72`, Python 3.12.4에서도 전체 101 tests·compileall·editable install·pip check·신규 CLI help와 실제 가상 replay→평가가 통과했다. readiness에서 CUDA RTX 3060·로컬 weight가 확인됐으나 승인된 SOHAS materialized manifest 부재를 탐지해 예상 exit 2 / blocked / training_started=false로 종료했다. raw: PC13 ignored `runs/sohas-pair-readiness-20261004/readiness.json`, `runs/event-evaluation-synthetic-v1/`. 실제 GPU full training은 미실행이다.

## Benchmark 최소 기록 항목

- 날짜, Git commit 또는 소스 버전, 장비, JetPack/OS, 전원 모드
- 모델 파일·런타임·정밀도·입력 해상도·입력 영상
- FPS, inference latency, end-to-end alert latency
- CPU/GPU/RAM, 온도, 전력 측정 방법
- 검출·경보 시나리오와 false alarms per hour 산출 방법

## Evidence status rules

- `UNVERIFIED`: 과거 자료나 출처는 있으나 현재 조건에서 재현하지 못함
- `TARGET`: 근거와 승인 절차를 거쳐 정한 목표이며 측정 결과가 아님
- `MEASURED`: 고정된 환경·명령·입력과 raw evidence가 있는 관측값

현재 기존 발표의 Precision 96.2%, Recall 85.1%, mAP50 93.7%는 모두 `UNVERIFIED`이다. 신규 정량 목표는 baseline과 scenario 규모를 확인한 뒤 기록한다.
