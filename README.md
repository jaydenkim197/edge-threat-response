# Context-Aware Edge Threat Detection System

> 2026-2 종합설계과제(1) - 기존 Jetson Nano 기반 흉기 탐지 프로젝트를 Jetson Orin Nano 환경으로 고도화

## 프로젝트 목적

기존의 단일 프레임 기반 흉기 탐지·GPIO 경보 프로토타입을, **상황 인지형 엣지 위협 대응 시스템**으로 발전시킨다. MVP는 `Person-Associated Knife Event`를 bounding-box 공간 연관성과 K-of-N 시간 조건으로 확인하고, 단계별 경보·사건 기록·성능 검증을 수행한다.

## 현재 상태

- 상태: 프로젝트 방향·MVP 연구 범위 `DECISION`, core·dataset review/export·training handoff·detector/video/snapshot scaffold `IMPLEMENTED`/PC `VERIFIED`, CUDA full training·실기기 `PLANNED`
- 기존 산출물: 2025-2 MIDAS 발표자료, 활동 정리, Jetson Nano 프로토타입 코드
- 구현 저장소: 구성 완료, legacy 전체 소스는 Git submodule로 고정
- 신규 기준 플랫폼: Jetson Orin Nano Developer Kit, JetPack 7.2.1 / Jetson Linux 39.2.1
- 실제 Orin 보드의 SKU·저장장치·펌웨어·카메라·GPIO·ML runtime은 아직 inventory 및 검증 필요
- 기존 Jetson Nano 4GB: 과거 시스템 보존과 선택적 장비 비교를 위한 legacy baseline
- dataset D1: registry, bbox/polygon validation, manifest, exact duplicate·group leakage 검사, split planner를 PC에서 구현·검증
- dataset D2: knife-only YOLO exporter와 deterministic visual-review pack 구현; 7,361장 decode 오류 0, 128장 검수표본 생성, 사람의 품질 판정·외부 source 승인은 남음
- runtime Increment A: geometry association, K-of-N, 4-state machine, B0~B3, mock alarm, JSONL event/replay를 PC에서 구현·검증
- training smoke: YOLO26n CPU 1 epoch와 checkpoint 재로딩을 검증했으나 성능 학습·평가는 아직 수행하지 않음
- pre-Orin Increment B: single/composite detector, canonical class remap, OpenCV image/video, detection JSONL, B0~B3 재생, metadata+actual snapshot을 PC에서 검증
- CUDA handoff: GPU preflight, Baseline v1 development config와 human-gated Colab notebook 준비; full training은 아직 실행하지 않음
- runtime 언어: Python으로 Orin 통합·TensorRT benchmark를 먼저 완료하고, 측정된 Python-side 병목이 전환 gate를 충족할 때만 Hybrid C++ production runtime을 검토
- 성능 수치: 기존 발표자료의 수치는 참고용이며, 이번 프로젝트 기준의 재측정은 아직 수행하지 않음
- 일정 원칙: 2026-10-31까지 정량 실험을 시작할 수 있는 통합·반복 실행 상태 확보

## 목표 시스템

```text
Camera
  -> Person/Weapon Detector
  -> Person–Knife Spatial Association + K-of-N Temporal Confirmation
  -> CLEAR / CANDIDATE / CONFIRMED / COOLDOWN
  -> GPIO Alarm + Event Metadata + Snapshot
```

자세한 구조와 데이터 경계는 [docs/architecture.md](docs/architecture.md)를, 후보와 결정 기준은 [docs/open-decisions.md](docs/open-decisions.md)를 참조한다.

## 문서 안내

- [Master Project Plan](docs/project-plan.md): 목적, 범위, 일정, 성공 조건의 최상위 기준
- [MVP Research Specification](docs/mvp-research-specification.md): 이벤트 정의, 상태·평가·시나리오의 구현 기준
- [구현 계획](docs/implementation-plan.md): 단계별 구현 범위, 모듈 경계, 착수·종료 조건
- [Runtime 언어 결정](docs/runtime-language-decision.md): Python 유지 근거, C++ 비용·위험과 조건부 전환 gate
- [Orin 도착 전 작업 계획](docs/pre-orin-work-plan.md): CPU 학습 없이 진행할 현재 작업, CUDA·실기기 이후 작업 경계
- [모델·데이터 준비 계획](docs/model-data-plan.md): 데이터 inventory, 라벨·분할 계약, 검증·학습 단계
- [개발 기록](docs/development-log.md): 시간순 변경·결정·검증·한계
- [연구·실험 계획](docs/research-or-product-plan.md): 가설과 비교 실험의 보조 계획
- [미결정 사항](docs/open-decisions.md): 확정 전 선택지와 판단 기준
- [아키텍처](docs/architecture.md): 현재 목표 구조와 책임 경계
- [검증 매트릭스](docs/verification.md): 요구사항별 증거와 미검증 항목
- [문서화 운영 규칙](docs/documentation-governance.md): 기록·상태·보안 규칙
- [회의·수업 결정 근거](docs/meeting-decisions/): 주제 선정과 일정 제약의 요약 기록
- [기존 MIDAS 자산 선별 기록](docs/legacy-asset-selection.md): 가져온 baseline과 제외 근거

## Legacy source checkout

2025-2의 전체 모델·데이터셋·학습 소스는 용량과 원본 보존을 위해 Git submodule로 연결한다. 처음 clone할 때는 다음 명령을 사용한다.

```bash
git clone --recurse-submodules https://github.com/jaydenkim197/edge-threat-response.git
```

이미 clone한 경우에는 `git submodule update --init --recursive`를 실행한다. submodule 내부의 legacy 코드와 모델은 신규 시스템 코드로 직접 수정하지 않는다.

## Dataset audit tooling

Python 3.10 이상에서 editable install 후 실행한다.

```text
python -m pip install -e . --no-deps
python -m unittest discover -s tests -v
etr-dataset audit --registry configs/datasets/legacy.json --repo-root . --output-dir reports/datasets/legacy-2026-09-14 --fail-on never
```

`audit`은 원본 dataset을 수정하지 않고 `manifest.jsonl`, `issues.jsonl`, `summary.json`, `report.md`를 생성한다. 기본 `--fail-on error`는 오류가 있으면 exit code 1을 반환한다. 현재 legacy split에는 알려진 group leakage가 있어 위 재현 명령만 `--fail-on never`를 사용한다.

분할 계획은 실제 파일을 옮기지 않고 manifest의 `planned_split`과 group assignment만 생성한다. 비율과 seed는 연구 결정 후 명시적으로 전달해야 한다.

```text
etr-dataset plan-split --manifest reports/datasets/legacy-2026-09-14/manifest.jsonl --output-dir reports/datasets/local-plan --ratios train=0.7,val=0.15,test=0.15 --seed 12345
```

위 비율은 CLI 형식 예시이며 프로젝트의 확정 split이 아니다. 현재 재현 결과는 [legacy dataset audit report](reports/datasets/legacy-2026-09-14/report.md)에 있다.

계획된 manifest는 knife-only YOLO dataset으로 materialize할 수 있다. raw/source class `0=knife`는 학습 model-local `0=knife`로 유지되고, runtime adapter에서 canonical knife ID `1`로 변환한다.

```text
etr-dataset materialize-knife-yolo --manifest data/work/legacy-development-split/planned-manifest.jsonl --registry configs/datasets/legacy.json --repo-root . --output-dir data/processed/knife-legacy-development-v1 --link-mode hardlink
```

검증된 development export 요약은 [legacy development dataset report](reports/datasets/legacy-development-v1/report.md)에 있다.

사람 검수용 pack은 Pillow가 있는 격리 환경에서 생성한다. contact sheet와 review CSV는 원본 이미지가 포함되므로 로컬 `data/review/`에만 둔다.

```text
.venv-ml/Scripts/python -m pip install -r requirements/review.txt
.venv-ml/Scripts/etr-dataset review-pack --manifest data/work/legacy-development-split/planned-manifest.jsonl --repo-root . --output-dir data/review/legacy-development-v1 --per-stratum 12 --seed 20260915
```

재현 결과는 [legacy visual review report](reports/datasets/legacy-visual-review-v1/report.md)에 있다. `review.csv`의 판정 열을 사람이 채우기 전까지 학습 승인은 완료되지 않은 상태다.

## Detector training smoke

ML 환경은 일반 개발 환경과 분리한다. 아래 profile은 dataset·학습 배관 검사용이며 성능 학습이나 연구 파라미터가 아니다.

```text
python -m venv .venv-ml
.venv-ml/Scripts/python -m pip install -r requirements/ml-smoke.txt
.venv-ml/Scripts/python -m pip install -e .
.venv-ml/Scripts/etr-train --config configs/training/cpu-smoke.json --data data/processed/knife-legacy-cpu-smoke-v1/data.yaml --output-dir runs/training
```

2026-09-15 실행 결과는 [YOLO26n CPU smoke report](reports/training/yolo26n-cpu-smoke-2026-09-15/report.md)에 기록했다. model weight와 전체 run output은 Git에 포함하지 않는다.

CUDA full-training 인계 절차와 Colab review gate는 [CUDA / Colab training handoff](docs/training-cuda-handoff.md)를 따른다.

## Detector and video integration

`etr-detect`는 image/video를 canonical detection JSONL로 변환한다. `etr-run`은 같은 adapter를 B3 pipeline에 연결해 event metadata와 snapshot을 생성한다. 실제 weight·입력·config의 hash가 summary provenance에 기록된다.

```text
etr-detect --input INPUT.mp4 --detector-config configs/detection/composite.development.example.json --output-dir runs/detection/local
etr-run --input INPUT.mp4 --detector-config configs/detection/composite.development.example.json --pipeline-config configs/replay/development-v2.example.json --output-dir runs/runtime/local
etr-replay --input runs/runtime/local/detections.jsonl --config configs/replay/development-v2.example.json --output-dir runs/replay/local
```

`configs/detection/legacy-composite.cpu-smoke.json`은 보존된 legacy weight의 PC 배관 검증용이고 detector 채택이나 성능 근거가 아니다. 결과는 [pre-Orin integration report](reports/runtime/pre-orin-detector-integration-2026-09-15/report.md)에 있다.

## Detection replay core

Increment A는 영상이나 모델 대신 timestamp와 detection 목록을 가진 JSONL을 입력으로 받는다. 아래 개발용 fixture와 설정으로 B0~B3를 같은 입력에 반복 실행할 수 있다.

```text
python -m pip install -e . --no-deps
etr-replay --input tests/fixtures/replay/basic.jsonl --config configs/replay/development.example.json --output-dir reports/replay/local-run
```

각 mode 폴더에는 frame별 판단, event JSONL, summary가 생성된다. replay에는 원본 frame이 없으므로 event의 snapshot 상태는 `not_captured`다. 예제의 confidence, 거리, bbox 확장, K/N, rearm 값은 계약·CLI 검증용이며 연구 최종값이 아니다. 커밋된 smoke 결과는 [Increment A replay report](reports/replay/increment-a-smoke/report.md)에 정리했다.

## Non-goals (현재 단계)

- 단순히 YOLO 버전만 교체하는 작업
- 고비용 클라우드 의존형 상시 영상 업로드
- 검증 없이 위협 상황을 정확히 판별한다고 주장하는 것
- 민감 영상·개인식별정보를 무분별하게 수집하거나 저장하는 것

## 작업 시작 규칙

각 material task는 목표, 범위, 완료 기준, 위험, 문서 영향을 먼저 정의한다. 구현 후에는 관련 코드·테스트·문서를 함께 갱신하고, 실제 실행한 검증과 한계만 기록한다.

## 개발 작업공간 및 GitHub 동기화

이 저장소의 기준 작업공간은 `00_Development_Github`이다. 다른 상위 수업 폴더의 복사본은 개발 기준으로 사용하지 않는다.

- 작업 시작 전 `git pull --ff-only`로 원격 `main`을 안전하게 반영한다. fast-forward가 불가능하면 임의로 병합하지 않고 원인을 확인한다.
- 의도한 변경만 검토·stage하여 커밋한다. 이 작업공간에서는 commit 직후 `origin/main`으로 자동 push되도록 Git hook을 설정했다.
- GitHub의 변경을 감시하여 무조건 자동 pull하는 방식은 사용하지 않는다. 작업 중인 파일을 덮어쓰거나 충돌을 숨길 수 있기 때문이다.
- 새 clone에서는 `git submodule update --init --recursive` 후 `git config core.hooksPath .githooks`를 한 번 실행해 같은 자동-push 정책을 적용한다.
