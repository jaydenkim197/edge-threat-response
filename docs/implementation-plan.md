# MVP Implementation Plan

상태: 구현 순서와 모듈 경계 `DECISION`, 모델·런타임·수치 파라미터 `PROPOSAL`

이 문서는 `project-plan.md`와 `mvp-research-specification.md`를 실제 개발 단위로 나눈다. 신규 시스템은 Jetson Orin Nano Developer Kit와 JetPack 7.2.1을 최종 실행 기준으로 삼지만, 실기기 의존성이 없는 판단 로직부터 PC에서 구현한다.

## 1. Implementation principles

- 한 번에 전체 파이프라인을 만들지 않고 검증 가능한 수직·수평 단위로 나눈다.
- domain·spatial·temporal·state machine은 PyTorch, OpenCV, Jetson GPIO를 import하지 않는다.
- detector, frame source, alarm, event recorder, resource monitor는 교체 가능한 adapter로 둔다.
- MVP에는 tracking이 없으므로 K-of-N은 특정 person ID가 아니라 source-level association 신호를 집계한다.
- B0~B3는 별도 코드 복사본이 아니라 동일 pipeline의 confirmation policy로 구현한다.
- threshold와 K/N은 설정으로 주입하고, 초기 development default를 연구 결론이나 최종값으로 표기하지 않는다.

## 2. Increment A — PC pure core and replay — `IMPLEMENTED` / PC `VERIFIED`

가장 먼저 구현한다. 실제 모델·영상·Jetson 없이도 완료할 수 있고 이후 모든 adapter의 기준 계약이 된다.

### 포함

1. `BBox`, `Detection`, `FrameDetections`, `AssociationResult`, `ThreatEvent` domain model
2. nearest-person, normalized distance, expanded-person-box 기반 spatial association
3. reliable knife presence와 associated-pair presence를 위한 K-of-N buffer
4. `CLEAR/CANDIDATE/CONFIRMED/COOLDOWN` state machine
5. B0 detection-only, B1 temporal-only, B2 spatial-only, B3 spatial+temporal policy
6. alarm·event recorder port와 `MockAlarm`, JSONL metadata recorder
7. timestamp와 detection 목록을 읽는 deterministic JSONL replay adapter
8. config validation과 최소 CLI
9. geometry 경계, K/N 경계·dropout, 모든 상태 전이, 중복 경보 방지, B0~B3 차이를 검증하는 단위·통합 테스트

### 제외

- OpenCV video decode와 실제 frame 저장
- PyTorch, Ultralytics, TensorRT와 모델 가중치
- Jetson camera, GPIO, `tegrastats`
- dataset 학습·재학습
- dashboard, tracking, clip

### 완료 기준

- PC에서 하나의 replay fixture로 B0~B3를 반복 실행할 수 있다.
- `CONFIRMED` 진입당 alarm과 event가 정확히 한 번 발생한다.
- 같은 config와 입력은 순서·event ID를 제외한 동일 결과를 만든다.
- snapshot port는 정의하되 frame이 없는 replay에서는 명시적으로 `not_captured`를 기록한다.

2026-09-14 기준 위 항목을 구현했다. `configs/replay/development.example.json`의 수치는 동작 검증용이며 연구 파라미터가 아니다. 9-frame synthetic detection fixture에서 B0/B1/B2/B3 최초 확인 frame이 각각 0/1/1/2로 분리되었고, 전체 38개 test가 통과했다. 실제 detector, 영상 decode, snapshot capture와 Jetson adapter는 포함하지 않았다.

## 3. Parallel data track — D1 `IMPLEMENTED` / PC `VERIFIED`

Increment A와 병렬로 `model-data-plan.md`의 D1을 구현할 수 있다. D1은 legacy inventory, source registry, source-specific class mapping, bbox/polygon validation, JSONL manifest, group-aware split/leakage 검사와 fixture test까지만 포함한다.

외부 dataset downloader, 실제 dataset 병합, training wrapper와 full training은 D1에 포함하지 않는다. 사람의 sample 승인과 detector topology 결정이 각각 D2와 D3의 gate다.

구현 위치는 `src/edge_threat_response/dataset/`, registry는 `configs/datasets/`, 재현 가능한 요약 결과는 `reports/datasets/`다. 실제 legacy audit에서는 7,364 images와 9,060 objects를 파싱했고 label 구조 오류는 없었으나 기존 split을 교차하는 source group 317개를 확인했다.

## 4. Increment B — PC video and detector adapter

ML dependency가 없는 port, fake backend, class remap, frame/video contract와 snapshot binding은 P0-05/P0-09 최종 결정 전에도 진행한다. 실제 Ultralytics model load와 Jetson runtime 검증만 해당 결정 이후 수행한다. 현재 노트북의 CPU training/inference smoke는 Increment B 완료 조건이 아니다.

### 포함

- OpenCV 또는 선택된 media backend의 video-file frame source
- single/composite를 모두 수용하는 person/knife detector adapter와 model-local→runtime canonical class remap
- 실제 frame에서 `CONFIRMED` 전이 시 snapshot 1장 저장
- detector latency와 end-to-end latency 계측 지점
- 고정 영상 smoke/integration test

### 결정 gate

- 단일 person/knife 2-class 모델을 새로 학습할지, legacy person 모델과 knife 모델을 결합할지 dataset audit로 정한다.
- knife 학습 이미지에 존재하는 person이 모두 annotation되지 않았다면 단일 2-class 학습으로 바로 합치지 않는다.
- model file, class map, input size, confidence threshold, license와 hash를 기록한다.
- JetPack 7.2.1 runtime은 native smoke를 먼저 수행하고 container를 대안으로 비교한다.

현재 우선순위와 CUDA·Orin 이후 경계는 `pre-orin-work-plan.md`를 따른다.

## 5. Increment C — Jetson Orin Nano integration

실제 장비 inventory와 JetPack 7.2.1 설치 확인 후 진행한다.

### 포함

1. NVIDIA container runtime과 후보 detector image smoke test
2. image tag뿐 아니라 digest, Python, PyTorch, CUDA, cuDNN, TensorRT, Ultralytics 버전 고정
3. USB/CSI camera adapter와 연결 복구 시험
4. GPIO LED/Buzzer adapter와 mock/hardware parity test
5. RAM·온도·CPU/GPU·FPS·latency resource recorder
6. 네트워크 차단과 저장 실패 시 로컬 경보 유지 시험

### 완료 기준

- 고정 영상과 카메라 입력 모두에서 B0~B3가 같은 event contract로 실행된다.
- Orin 전원 모드, 냉각, 입력, model/runtime, commit, config가 evidence에 남는다.
- 재부팅 후 문서화된 명령으로 반복 실행할 수 있다.

## 6. Increment D — controlled experiment

- 안전한 scenario를 촬영하고 manual event ground truth를 작성한다.
- development/tuning session으로 threshold·K/N을 고른 뒤 holdout session을 고정한다.
- 동일 Orin 조건에서 B0~B3 event metric과 edge metric을 산출한다.
- 실패 사례와 모호 사례를 snapshot·metadata·annotation으로 연결한다.
- legacy Nano 비교는 Orin ablation이 끝난 뒤 가능할 때만 별도 실험으로 수행한다.

## 7. Deferred until evidence exists

- TensorRT/FP16은 먼저 PyTorch/container baseline을 측정한 뒤 필요성과 효과를 판단한다.
- tracking, dashboard, event clip, 추가 weapon class, enclosure/PCB는 MVP DoD 이후에만 착수한다.
- NVIDIA 문서의 예시 container tag는 프로젝트 runtime 결정이 아니다.
- 공식 JetPack 구성 정보는 플랫폼 근거일 뿐, 프로젝트 모델의 호환성·성능 증거가 아니다.
