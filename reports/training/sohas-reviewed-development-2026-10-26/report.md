# SOHAS 검수 완료분 개발용 예비 학습 — 2026-10-26

**YOLO26n 50 epochs 학습·validation·checkpoint 저장이 완료됐고 launcher exit0을 확인했다.** `best.pt`의 hash 일치·클래스·GPU 재추론과 기존 person+knife composite adapter 연결도 통과했다. 그러나 검증 recall21.4%/mAP50 26.6%로 낮다. 이는 사용자가 승인한 **개발용 예비 모델**이며 최종 detector·공식 R1/H1·CCTV 일반화 성능이 아니다.

## 승인과 데이터 범위

- 사용자는 정상 SOHAS183개만으로 개발용 예비 학습을 먼저 진행하는 제안을 명시적으로 승인했다. Authorization reference: `user-20261026-reviewed-development`.
- 고정 review snapshot: PC13 ignored `data/work/review-candidates/20261026-training-v1/`, SHA-256 `ca9aa15ec35dddd8ecbca6ab9f7d305cd9aa4cbdf8e69c3663a98f6dc252bdd2`.
- 선정: knife 양성130/음성53, 총183 images/161 knife boxes. 미검수·문제/모름·다른 source를 넣지 않았다. 제외0이다. 시작 직전에 선택183개의 최신 DB review version/payload hash가 snapshot과 같음을 read-only 재확인했다.
- Pinned upstream: `ari-dasci/OD-WeaponDetection` commit `48860b990e4d4f57fe100248887fceb248475dc8`. Image/XML blob·review bbox 전체·SHA-256·decode/dimension·model-local `0=knife` label round-trip을 검증했다. 가공 image는 raw와 hardlink하지 않고 복사했다. 원본·검수 DB·사이트는 변경하지 않았다.
- 좌표 계약: `review-overlay-pixel-edges-v1`. 검수 화면 raw xyxy를 개발용 pixel edges로 명시적으로 해석한다. 원본 좌표 의미를 확인했다고 선언하지 않는다.
- 분할: 전체5859개 source의 번호 제거 filename family·exact hash·dHash pair를 연결한 transitive proxy component17개. 미선정 image를 통한 연결도 유지한다. 같은 proxy/hash는 split을 교차하지 않으며 실제 recording session 독립성을 보장하지 않는다. Planner default70/15/15, split seed20261026. 원본 train/test는 보존 필드이며 이번 개발 split과 다르다.

| 개발 partition | Images | Knife 양성 | 음성 |
|---|---:|---:|---:|
| train | 137 | 97 | 40 |
| val / 개발 튜닝 | 23 | 13 | 10 |
| reserved test / 미사용 | 23 | 20 | 3 |

`development-authorization.json`은 config/YAML/manifest/pretrained/train·val·test list hash를 묶는다. 원 좌표 의미·실제 session·공식 source·최종 평가·외부 재배포 승인은 모두 false다. 공식 R1/H1의 7개 gate를 true로 바꾸거나 기존 승인을 우회하지 않았다. DEV-SOHAS의 제한 scope를 별도로 확인하며 formal profile로 전용하면 거부한다.

## 재현 환경과 실행

- Run ID: `sohas-reviewed-development-20261026-v1`, recipe `DEV-SOHAS`, evidence `evaluation_scope=development_only`.
- Preparation code `b094713a4d0d4b57ace707663648f66761b59927`; launch/training code `b390fe98ad65b3ddbc7676b77b22a1d4f4257d59`.
- PC13 Windows11, Intel i9-13900, RTX3060 12GB/driver560.94, Python3.12.4, torch2.6.0+cu124, torchvision0.21.0+cu124, Ultralytics8.4.152, NumPy1.26.4, OpenCV4.11.0.86. Orin 환경 검증이 아니다.
- YOLO26n pretrained SHA-256 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
- 설정: imgsz640, batch/nbs16, epochs50, device0, workers0, cache=false, FP32/amp=false, SGD lr0=.01/lrf=.01/momentum=.937/weight_decay=.0005, warmup0, patience0, training seed20261004. 나머지 augmentation/config 원본은 hash-bound training.json과 invocation에 기록한다. 연구 최종 설정이 아니다.
- 동일 R1/H1 비교를 수행하지 않았다. Train unique137장, epoch당9 batches, 계획450 updates이며 실제 최종50 epoch를 확인했다. Test23장은 평가하지 않았다.
- Config SHA-256 `c4185381fbd5693855af5c9760ea83f9312630533286c73646f169170ac5b663`; dataset manifest `4bff41f710e7ba043aeebab194ba449a9e41f7fab0cde3714963d337321dc1f2`; 개발 승인 파일 `fdce03bf5275dc55b103bfc7bb23b87b13d71409fdf583337006f4d85eff8f48`.

GPU/hash preflight 통과 후 아래 launcher를 실행했다. Hidden CIM worker가 시작 SSH와 분리되어 실행됐고 새 SSH에서 GPU 학습·epoch loss와 완료를 확인했다. Windows 명령 길이 제한으로 최초 이중 encoded launch는 실행 전 실패했으며 실제 trainer/launch artifact0을 확인한 뒤 짧은 script 방식으로 전환했다.

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File tools/start_development_training.ps1 -RunId sohas-reviewed-development-20261026-v1
```

Launcher PID18636, 생성시각2026-10-26 13:43:37 KST. 같은 ID 재실행은 거부한다. Process별 실행 정책만 사용하며 시스템 policy·전원 설정·예약 작업을 변경하지 않았다. 재부팅/절전 지속이나 자동 resume를 검증한 것은 아니다.

## 관측 결과 — validation만

| 지표 | 관측값 |
|---|---:|
| 완료 epochs | 50 |
| Runner duration | 203.265 s |
| 종료 코드 | 0 |
| Precision | 0.5354 |
| Recall | 0.2143 |
| mAP50 | 0.2658 |
| mAP50–95 | 0.1025 |

위 값은 Ultralytics가 선택한 best checkpoint의 개발 validation 요약이다. Val은23장/knife14 objects로 작으며 독립 CCTV·공통 detector holdout·최종 test 결과가 아니다. Runner duration은 모델 로드·학습·validation을 포함하고 실제 edge latency/FPS가 아니다. 성능 부족 원인을 단일 run만으로 확정할 수 없다. 소규모 학습/검증과 proxy-group/domain 차이 등을 오류 분석해야 하며, 기존 MIDAS의 미검증 발표 수치와 직접 비교하지 않는다.

## Checkpoint와 통합 smoke

- `weights/best.pt`: 5,368,446 bytes, SHA-256 `83fe8cee46d50c52a2fe0beb12f2fae8531c7ce9d1c0b5d9bc91980925353cc7`.
- `weights/last.pt`: 5,368,446 bytes, SHA-256 `631808995bd52cf1bc45ae17cc40412022bc0b75bcaa4d2c1c0d89e99a61e68d`.
- Best hash가 training invocation artifact record와 일치하고 재로딩한 class map이 `{0: knife}`임을 확인했다.
- 실제 train positive image1개에 COCO-pretrained person + 새 knife weight를 기존 composite detector/GPU0로 연결했다. Canonical JSONL1 valid frame·detector error0을 확인했고 input/config/양쪽 weight hash를 기록했다. 이는 통합 smoke이며 정답 대비 성능 평가나 single-frame latency benchmark가 아니다. Test partition을 읽지 않았다.

## 원시 증거 위치 — PC13에만 보관

Repository root `C:\Class6\edge-threat-response` 기준:

- `data/processed/sohas-reviewed-development-20261026-v1/`: copied images·labels·lists·manifest·development authorization·preparation/config·upstream license notices.
- `runs/development-preflight-20261026-v1/preflight.json`.
- `runs/launch-sohas-reviewed-development-20261026-v1/`: launch metadata·stdout/stderr·exit-code0.
- `runs/training/sohas-reviewed-development-20261026-v1-invocation.json` 및 같은 ID 폴더의 results.csv·weights·plots.
- `runs/development-checkpoint-smoke-20261026-v1/`: weight verification·composite config·canonical detection/provenance.

Raw·개인 판정·weight·이미지 plots는 Git/Drive에 올리지 않았다. Git에는 코드와 이 aggregate 보고만 보관한다.

## 검증과 다음 작업

신규6개 unit/integration tests 로컬 Python3.12.14 통과, PC13 Python3.12.4 격리 QA에서 전체130 tests/compileall 통과했다. 첫 기존 HTTP fixture socket10053은 해당7개와 전체130 재실행에서 통과했다. 로컬 bundled 전체 검증은 werkzeug 부재1 error/12 skipped였으며 전체 통과로 기록하지 않는다. Launcher는 PowerShell parser 및 실제 SSH 독립 실행으로 검증했다.

다음은 val 오류/놓친 knife·크기·도메인·라벨을 확인하고 학습량/target-domain 보강 방향을 정하는 것이다. 지금 checkpoint를 최종 모델이나 운영 경보에 배포하지 않는다. 공식 source 좌표·실제 camera/session·권리/recipe와 common holdout gate는 남으며, 추가 run·source 확대와 최종 성능 주장은 별도 근거가 필요하다.
