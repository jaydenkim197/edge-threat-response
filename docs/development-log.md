# Context-Aware Edge Threat Detection System - Development Log

이 문서는 제품, 기술 구조, 운영, 검증 및 연구 설계의 material change를 시간순으로 보존한다. 과거 항목은 삭제하지 않으며, 대체된 내용은 후속 항목에서 연결한다.

## 2026-09-15 - Python-first runtime과 조건부 Hybrid C++ gate 확정

상태: runtime 언어 `DECISION`, Hybrid C++ `DEFERRED`, Orin 성능 검증 `PLANNED`

### Goal / Why

- 현재 Python runtime을 C++로 전환할 실제 비용, 디버깅 위험과 기대 성능을 저장소 구현 상태와 일정 기준으로 판단한다.
- C++가 빠를 것이라는 가정만으로 10월 31일 통합 MVP 일정을 위험하게 만들지 않도록 전환 조건을 고정한다.

### Scope / Changed files

- `docs/runtime-language-decision.md`에 source inventory, 세 선택지, 시간·Codex workload·failure mode·test 재사용·성능·일정과 전환 trigger를 기록했다.
- `project-plan`, `architecture`, `implementation-plan`, `open-decisions`, `verification`, `README`에 Python-first 결정과 문서 진입점을 연결했다.
- 코드, CMake와 C++ 구현은 변경하지 않았다.

### Environment / Commands / Result

- 기준 저장소: Git `3b5337c`, `main...origin/main`, 작업 시작 시 clean.
- `src/edge_threat_response/**`, `tests/**`, CLI/config와 필수 계획·검증 문서를 inventory했다.
- `python -m unittest discover -s tests -q`: 56 tests 통과, 0.606 s.
- Runtime 관련 Python source는 13개 파일, 약 1,841줄이다. 이는 port 규모 근거이며 생산성 측정값은 아니다.

### Verification / Measured values / Limitations

- 코드 동작 회귀는 기존 56 tests로 재확인했다. 이번 작업은 문서 분석이므로 C++ build나 Orin 실행을 수행하지 않았다.
- 시간, debugging과 Codex workload 범위는 현재 source 규모와 신규 TensorRT/CUDA/GStreamer/CMake 작업에 기반한 추정치이며 실측 성능이 아니다.
- NVIDIA 공식 TensorRT 문서의 Python/C++ inference parity 설명과 Jetson 설치·GStreamer 문서를 근거로 사용했지만 프로젝트 모델의 Orin 성능은 여전히 `PLANNED`다.

### Decision impact / Next action

- Orin Increment C는 Python으로 먼저 완료하고, direct TensorRT Python을 포함한 고정 조건 benchmark를 수행한다.
- C++17 production runtime은 p95 latency/FPS/memory 목표 미달, Python-side frame budget 25% 이상, Python 최적화 실패와 3주 이상 일정 여유를 모두 충족할 때만 착수한다.
- Spatial/K-of-N/FSM만 C++로 옮기는 Core-only C++는 채택하지 않는다.

### Git

- 분석 기준 commit: `3b5337c`
- 문서 변경 commit: 이 기록을 포함한 Git history

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
