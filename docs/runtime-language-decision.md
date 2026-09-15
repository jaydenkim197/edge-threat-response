# Runtime Language Decision

상태: Python-first runtime `DECISION`, Hybrid C++ 전환 `DEFERRED`, Core-only C++ 채택하지 않음

기록일: 2026-09-15

분석 기준: Git commit `3b5337c`, Windows Python 3.11.9, unit test 56개 통과 상태

적용 범위: Jetson Orin Nano production runtime의 구현 언어와 C++ 전환 gate

## 1. 결정 요약

현재 MVP는 Python runtime으로 완성하고 Jetson Orin Nano에서 TensorRT를 포함한 end-to-end benchmark를 먼저 수행한다. C++17 production runtime은 측정된 병목이 아래 전환 조건을 충족할 때만 후속으로 구현한다.

- 학습, dataset, evaluation과 Python reference implementation은 계속 Python으로 유지한다.
- Orin의 첫 통합 경로는 Python camera/detector/runtime/GPIO adapter다.
- TensorRT를 사용할 때도 Python API 또는 검증된 Ultralytics export/runtime 경로를 먼저 측정한다.
- 단순히 C++가 빠를 것이라는 가정만으로 구현 언어를 바꾸지 않는다.
- Spatial/K-of-N/FSM만 C++로 옮기는 Core-only C++는 계산 이득이 거의 없고 언어 경계만 추가하므로 채택하지 않는다.
- C++ 전환이 필요하면 Python reference를 유지하면서 detector, preprocessing/postprocessing, camera, event/snapshot, GPIO까지 포함하는 별도 production runtime으로 구현한다.

## 2. 저장소 기준 사실

첨부 분석 초안의 과거 상태와 달리 `3b5337c`에는 다음이 이미 Python으로 구현되어 있다.

- canonical detection/domain contract
- spatial schema v1/v2
- K-of-N과 4-state machine
- B0~B3 pipeline, deterministic event ID, metadata와 replay
- single/composite detector adapter, class remap, fail-closed component error
- OpenCV 파일 image/video 입력
- 실제 detector detection JSONL 생성
- current-frame snapshot integration
- dataset audit/export/review와 CUDA training handoff
- unit test 56개와 actual Ultralytics CPU integration smoke

다음은 아직 `PLANNED`다.

- CUDA full training과 채택 detector
- Orin native ML runtime과 TensorRT
- live USB/CSI camera
- GPIO LED/Buzzer
- resource benchmark와 controlled experiment

Runtime 관련 Python source는 약 1,841줄이다. Dataset과 training code는 Hybrid C++ 선택 시에도 Python에 남는다.

## 3. 실제 port 범위

### 거의 기계적 port

| 파일 | 현재 책임 | C++ 전환 작업 |
|---|---|---|
| `domain.py` | enum, bbox/detection/event struct와 validation | C++ enum/struct, validation, JSON serialization |
| `spatial.py` | bbox geometry와 person-knife association | 동일 수학 로직과 float parity |
| `temporal.py` | K-of-N history | deque/ring buffer 구현 |
| `state_machine.py` | CLEAR/CANDIDATE/CONFIRMED/COOLDOWN | 동일 transition과 rearm 규칙 |
| `config.py` | schema v1/v2 config validation | JSON parser와 validation |

### 중간 난이도 port

| 파일 | 추가 위험 |
|---|---|
| `pipeline.py` | B0~B3, action failure isolation, SHA-256 event ID와 출력 parity |
| `ports.py` | alarm/recorder/snapshot interface와 장애 격리 |
| `replay.py`, `replay_cli.py` | JSONL schema, CLI, evidence file과 hash |
| `detector.py` | single/composite와 class remap 의미 보존 |
| `media.py` | frame timestamp, 파일 decode와 snapshot |
| `runtime.py`, `detect_cli.py` | orchestration, latency/provenance, config/weight hash |

### 새 구현

- CMake/CTest와 Windows x64·Jetson ARM64 build
- TensorRT engine/context lifecycle
- CUDA buffer, stream, host/device copy와 synchronization
- letterbox/normalization/tensor layout
- output decode와 NMS
- OpenCV/GStreamer live camera와 선택적 zero-copy
- GPIO와 안전한 shutdown
- threading, resource ownership, 장기 실행과 resource monitor

## 4. 선택지 비교

| 기준 | A. Python 유지 | B. Hybrid production C++ | C. Core-only C++ |
|---|---|---|---|
| 기존 코드 재사용 | 거의 전부 | Python은 reference, production 재구현 | orchestration은 Python |
| 논리 중복 | 없음 | Python/C++ 이중 구현 | FFI와 상태 동기화 추가 |
| 실기기 위험 | 가장 낮음 | 가장 높음 | 중간 |
| 예상 성능 이득 | 기준 | camera/copy/CPU 병목일 때 가능 | 거의 없음 |
| 일정 적합성 | 높음 | 현재는 낮음 | 이득 대비 낮음 |
| 결정 | 현재 경로 | 조건부 후속 | 채택하지 않음 |

## 5. 안정화 완료 시간 추정

아래 값은 측정 결과가 아니라 추정치다. Codex가 코드를 주로 작성하고 사용자가 실기기 확인을 담당하는 집중 작업시간이며, 항목 간 중복을 제거한 총량이다.

| 선택지 | Best | Likely | Worst reasonable |
|---|---:|---:|---:|
| A. Python | 20~35 h | 45~80 h | 100~160 h |
| B. Hybrid C++ | 55~90 h | 120~210 h | 280~450 h |
| C. Core-only C++ | 30~50 h | 65~115 h | 150~250 h |

Hybrid C++의 likely 추가 비용은 Python 경로 대비 약 75~130시간으로 추정한다. 이 값에는 initial implementation, automated/golden test, Windows verification, Orin/TensorRT/camera/GPIO integration, bug fixing, regression과 문서화가 포함된다.

## 6. 디버깅과 Codex 작업량 추정

| 선택지 | 디버깅 시간 Best/Likely/Worst | Python 대비 Codex 전체 workload | 반복 debugging turn |
|---|---|---:|---:|
| A. Python | 8~15 / 20~40 / 55~90 h | 1x | 1x |
| B. Hybrid C++ | 25~45 / 60~120 / 160~280 h | 2.5~4x | 3~5x |
| C. Core-only C++ | 15~25 / 35~70 / 90~160 h | 1.5~2.2x | 1.7~2.5x |

Codex는 boilerplate, CMake와 test 작성을 줄일 수 있지만 실제 카메라, GPIO, 전원, 냉각, UEFI/QSPI, ARM64 library와 GStreamer 조합을 물리적으로 시험할 수 없다. 따라서 C++ 비용의 주된 원인은 코드 타이핑보다 실기기 로그 수집과 수정·재검증 반복이다.

## 7. C++에서 추가되는 주요 failure mode

| Failure mode | 발생 가능성 | 발견/해결 난이도 | Python 대비 |
|---|---|---|---|
| compile/link/CMake 오류 | 높음 | 낮음~중간 | 크게 증가 |
| OpenCV/TensorRT/CUDA ABI mismatch | 중상 | 높음 | 크게 증가 |
| Windows x64와 ARM64 차이 | 높음 | 높음 | 증가 |
| CUDA buffer·dtype·shape 오류 | 중상 | 높음 | 크게 증가 |
| pointer ownership와 lifetime | 중간 | 높음 | 거의 새 문제 |
| async stream synchronization | 중간 | 매우 높음 | 크게 증가 |
| segmentation fault/use-after-free | 중간 | 높음 | 거의 새 문제 |
| preprocessing/NMS 불일치 | 높음 | 높음 | 직접 재구현 시 증가 |
| GStreamer caps/plugin/camera timestamp | 높음 | 높음 | native 통합 시 증가 |
| GPIO 권한/pinmux/shutdown | 중간 | 중상 | 양쪽에 있으나 C++ adapter 신규 |
| JSON float/order/schema drift | 중간 | 낮음~중간 | port 특유 |
| 장기 실행 leak/race | 중간 | 매우 높음 | 증가 |

전처리와 NMS 불일치는 프로그램이 종료되지 않고 그럴듯한 잘못된 detection을 만들 수 있으므로 compile error보다 더 위험하다.

## 8. Test 재사용 전략

기존 `tests/fixtures/replay/basic.jsonl`, pipeline config와 Python expected output을 cross-language golden oracle로 사용한다.

```text
same config + same detection JSONL
              -> Python reference output
              -> C++ executable output
              -> normalized golden comparison
```

비교 대상은 프레임별 B0~B3 상태, confirmation frame, association, K-of-N count, event sequence/ID, missing/error 처리와 alarm 전이 시점이다. 초기에는 C++ executable + Python golden comparison으로 논리 port를 검증할 수 있다. Production 채택 전에는 CTest 기반 핵심 unit test, PC sanitizer, 반복 replay와 Orin soak test를 추가한다. Golden test만으로 buffer lifetime, memory leak와 CUDA race를 검증할 수는 없다.

## 9. 예상 성능 이점

현재 pipeline에서 병목 가능성이 높은 순서는 detector inference, preprocessing/postprocessing와 host/device copy, camera decode/copy, I/O, 판단 core다. Spatial/K-of-N/FSM은 C++ 전환 이득이 거의 없는 작은 연산이다.

동일 TensorRT engine을 올바르게 사용할 경우 NVIDIA는 Python과 C++ API의 inference time이 거의 동일해야 한다고 설명한다. 차이가 생긴다면 언어 자체보다 Ultralytics/PyTorch 제거, buffer 사전 할당, copy 제거, GStreamer memory 경로와 비동기 I/O의 영향일 가능성이 높다.

| 지표 | C++ 이점 가능성 | 사전 판단 |
|---|---|---|
| TensorRT inference latency | 낮음 | 같은 engine이면 거의 동일 예상 |
| End-to-end latency/FPS | 낮음~중간 | Python-side copy/pre-post/camera가 병목일 때만 의미 있음 |
| RAM/CPU | 중간 | PyTorch/Ultralytics 제거와 native data path가 필요 |
| Startup/jitter | 중간 | 고정 allocation/stream 설계가 잘됐을 때 개선 가능 |
| 장기 안정성 | 불확실 | C++ 자체가 안정성을 보장하지 않음 |
| GPIO·판단 core | 거의 없음 | detector frame budget 대비 매우 작음 |

공식 참고:

- NVIDIA TensorRT performance optimization: <https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/optimization.html>
- NVIDIA TensorRT runtime tutorial: <https://docs.nvidia.com/deeplearning/tensorrt/latest/getting-started/quick-start-runtime-tutorial.html>
- NVIDIA Jetson accelerated GStreamer: <https://docs.nvidia.com/jetson/archives/r39.2.1/DeveloperGuide/SD/Multimedia/AcceleratedGstreamer.html>

## 10. 일정 영향

| 선택지 | 2026-10-31 통합 MVP 기준 |
|---|---|
| A. Python | 감당 가능 |
| B. 지금 C++ | 하지 말아야 함 |
| C. Core-only C++ | 상당한 위험이며 이득 부족 |

9월 말 detector/data baseline, 10월 31일 통합 MVP, 11월 정량 실험 일정에서 지금 Hybrid C++를 시작하면 CUDA full training, detector 선택, Orin 설치, camera/GPIO보다 runtime 재구현이 먼저 critical path가 된다. 장비 도착 뒤 UEFI/QSPI, 저장장치, ML runtime과 카메라 변수가 추가될 수 있으므로 Python 통합 증거를 먼저 확보한다.

## 11. C++ 전환의 정확한 trigger

다음 조건을 모두 충족할 때만 Hybrid C++ 전환을 착수한다.

1. Python camera→TensorRT→판단→GPIO/snapshot 경로가 Orin에서 작동한다.
2. Detector engine, 입력 해상도, batch, 전원 모드, 냉각과 camera pipeline이 고정된다.
3. 30분 이상 실행을 3회 반복해 p50/p95 latency, FPS, RAM, CPU/GPU 사용률과 온도를 기록한다.
4. 확정된 목표에 대해 p95 end-to-end latency가 20% 이상 초과하거나, FPS가 20% 이상 부족하거나, 실행 후 가용 memory headroom이 20% 미만이다.
5. Profiler에서 TensorRT GPU compute가 아니라 Python preprocessing, postprocessing, copy 또는 orchestration이 frame budget의 25% 이상을 차지한다.
6. Buffer 재사용, direct TensorRT Python, 불필요한 copy 제거, logging/snapshot 비동기화를 적용해도 목표를 충족하지 못한다.
7. Python golden output이 고정되어 있고 다음 hard deadline까지 C++ 통합 여유가 최소 3주 남아 있다.

TensorRT engine 자체가 frame time 대부분을 차지한다면 C++ 전환 조건이 아니다. 이때는 model size, input resolution, precision과 single/composite topology를 최적화한다.

## 최종 결정

현재 상태에서는 같은 TensorRT engine의 Python·C++ 추론 성능 차이가 작고 실기기 통합 위험이 아직 측정되지 않았기 때문에 Python runtime 완성 후 Orin benchmark를 거쳐 필요한 경우에만 Hybrid C++로 전환한다.
