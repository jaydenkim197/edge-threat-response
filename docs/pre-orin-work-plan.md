# Pre-Orin Work Plan

상태: 작업 순서·class contract `DECISION`, W1~W3·CPU smoke `IMPLEMENTED`/PC `VERIFIED`, 나머지 detector/model/runtime/외부 dataset 채택 `PROPOSAL`

이 문서는 Jetson Orin Nano가 도착하기 전에 개발 PC에서 끝낼 작업과, CUDA GPU 또는 실기기가 있어야 하는 작업을 분리한다. 현재 노트북에서 PyTorch/Ultralytics CPU 학습 smoke를 수행하지 못하더라도 pre-Orin 개발은 중단하지 않는다.

## 1. Verified basis

- 기준 저장소는 `00_Development_Github`, 기준 commit은 계획 작성 직전 `f8acb89`이며 원격 `main`과 일치했다.
- 초기 inventory에서 NVIDIA CUDA GPU와 ML package가 없음을 확인했다. 이후 격리된 `.venv-ml`에 CPU runtime을 설치했으며 일반 개발 Python과 분리했다.
- 순수 로직과 신규 config/export/training contract는 `python -m unittest discover -s tests -v`에서 46 tests가 통과했다.
- legacy dataset 7,364장은 knife-only이고 person annotation이 없으므로 완전한 person annotation 없이 unified 2-class 학습에 사용하지 않는다.
- JetPack 7.2.1은 Orin Nano 공식 지원 기준이지만, 실제 대여 장비에서 PyTorch·Ultralytics·container·TensorRT 조합은 아직 검증되지 않았다.

## 2. Corrections to the proposed approach

1. CPU training smoke는 pre-Orin 완료 조건에서 제외한다. 대신 dataset contract, fake detector, video/frame contract와 replay integration을 ML dependency 없이 검증한다.
2. detector topology는 고정하지 않는다. COCO single-model은 sanity baseline, COCO person + custom knife composite는 primary implementation proposal, unified 2-class는 annotation 완전성 확보 후 후보로 둔다.
3. `70/15/15`, seed, epochs, batch, image size는 development/training default이며 연구 파라미터나 최종 결론이 아니다.
4. 프로젝트 전체 라이선스는 자동으로 AGPL-3.0으로 지정하지 않는다. Ultralytics 사용·모델 공개·배포 범위를 확인하는 P0 결정으로 관리한다.
5. JetPack 7.2.1에서는 actual-board native runtime smoke를 먼저 수행하고, container는 재현성 대안으로 비교한다. 특정 image/tag를 실기기 검증 전에 고정하지 않는다.

## 3. Work now — ordered backlog

| 순서 | ID | 작업 | 완료 기준 |
|---:|---|---|---|
| 1 | W1 | 문서·class contract 정합화 | `IMPLEMENTED` / raw source ID, model-local training ID, runtime canonical label의 경계 정의 |
| 2 | W2 | Spatial association schema v2 | `IMPLEMENTED` / expanded bbox 판정, normalized distance 진단값, v1 replay 호환과 단위 test |
| 3 | W3 | Knife-only dataset exporter | `IMPLEMENTED` / 전체 7,361장 materialize, polygon→bbox, exact duplicate 3장 제거, group/hash leakage 0 |
| 4 | W4 | Dataset visual-review pack | decode/손상 검사, source·객체 크기·annotation 형식별 표본과 review CSV/contact sheet를 생성; 모호 사례를 팀 결정 대상으로 분리 |
| 5 | W5 | Detector/video integration scaffold | ML import 없이 fake backend로 single/composite detector, class remap, 오류 격리, frame source, detection JSONL, B0~B3 replay, snapshot binding을 검증 |
| 6 | W6 | CUDA training handoff package | `IN PROGRESS` / config-driven runner와 CPU smoke evidence 완료; GPU preflight·CUDA profile·Colab 절차는 남음 |
| 7 | W7 | External dataset candidate record | Simuletic은 synthetic smoke-only, DaSCI Knife/SOHAS는 우선 표본 검수 후보, Open Images는 selective subset 후보로 기록; 무검수 대량 병합 금지 |

### W1 class mapping contract

- raw legacy annotation: source-local `0=knife`
- knife-only training dataset/model: model-local `0=knife`
- runtime canonical detection: `person`, `knife` label을 사용하며 registry의 canonical numeric ID는 `0=person`, `1=knife`
- knife detector adapter: model-local `0`을 runtime canonical `knife`/ID `1`로 변환
- unified training dataset은 모든 person과 knife가 완전하게 annotation된 경우에만 `0=person`, `1=knife`를 사용

### W5 execution boundary

- `etr-detect`: 영상/이미지 입력을 한 번 추론해 canonical detection JSONL과 latency/run manifest 생성
- `etr-replay`: 같은 JSONL을 B0~B3에 재사용
- `etr-run`: 실제 frame을 B3에 연결하고 `CONFIRMED` 진입 시 metadata와 snapshot 생성
- actual Ultralytics model load는 CUDA 또는 Orin smoke 전까지 `PLANNED`로 유지

## 4. Explicitly deferred

### CUDA GPU 확보 후

- YOLO26n/YOLO11n CUDA load·train·export smoke
- COCO single-model sanity baseline과 legacy/custom knife weight 확인
- knife-only full training과 validation
- 실제 detector topology, input size와 confidence 후보 축소

### Orin 수령 후

- SKU·RAM·storage·firmware inventory와 JetPack 7.2.1 설치
- native PyTorch/Ultralytics smoke 후 container 비교
- camera, GPIO, offline/failure behavior
- target에서 TensorRT FP16 engine 생성
- FPS, inference/end-to-end latency, RAM, temperature, power 측정
- controlled scenario와 동일 조건 B0~B3 본 실험

## 5. Pre-Orin completion meaning

W1~W7이 완료되면 시스템은 `CODE READY`와 `CONTRACT VERIFIED`로 기록한다. 실제 모델 추론, detector 정확도, Jetson 호환성, snapshot 실영상 품질과 edge 성능은 그 결과만으로 `VERIFIED`라고 표기하지 않는다.

2026-09-15의 CPU smoke는 학습 배관만 검증했다. 32 train/8 val, 1 epoch 결과의 metric은 detector 성능 근거가 아니다.

## References checked on 2026-09-15

- NVIDIA Jetson Orin Nano JetPack 7.2.1 quick start: <https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/quick_start.html>
- NVIDIA JetPack archive/support mapping: <https://developer.nvidia.com/embedded/jetpack-archive>
- Ultralytics supported models: <https://docs.ultralytics.com/models>
- Ultralytics Jetson setup and runtime cautions: <https://docs.ultralytics.com/guides/nvidia-jetson>
- PyTorch Windows install options: <https://pytorch.org/get-started/locally/>
- Ultralytics license choices: <https://www.ultralytics.com/license>
