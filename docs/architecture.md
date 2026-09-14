# System Architecture

상태: MVP 논리 구조 `DECISION`, 인터페이스·실기기 구현 `PLANNED`. Tracker와 Dashboard는 현재 필수 경로가 아니다.

## 시스템 경계

```text
[Camera]
   -> [Camera Adapter]
   -> [Detector]
   -> [Spatial Association]
   -> [Temporal K-of-N Buffer]
   -> [CLEAR / CANDIDATE / CONFIRMED / COOLDOWN]
      -> [GPIO Alarm]
      -> [Event Recorder / Local Event Store]
      -> [Metrics / Benchmark]

Optional after MVP:
   [Tracker / Motion Analyzer]
   [Dashboard / Event API]
```

## 기준 플랫폼과 실행 경계

- 신규 시스템 배포 기준: Jetson Orin Nano Developer Kit, JetPack 7.2.1 / Jetson Linux 39.2.1.
- 공통 core: Python 3.10~3.12, PyTorch·OpenCV·GPIO 비의존. PC와 Orin에서 같은 단위 테스트를 실행한다.
- detector adapter: Jetson-compatible NVIDIA container를 우선 검토하되 실제 보드 smoke test 전에는 image와 framework 버전을 고정하지 않는다.
- hardware adapter: camera, GPIO, `tegrastats` 계열 자원 수집을 core 바깥에 둔다.
- legacy adapter: 2025-2 Nano 코드는 submodule에서 보존하며 신규 package의 runtime 기준으로 사용하지 않는다.

처음 구현은 영상 대신 timestamp와 detection 목록을 가진 recorded-detection stream을 입력으로 사용한다. 이 경로에서 B0~B3, 상태 전이, 알람 중복 억제, metadata 생성을 결정론적으로 검증한 뒤 detector와 실제 frame을 연결한다.

## 책임 분리

| 컴포넌트 | 책임 | 플랫폼 의존성 |
|---|---|---|
| Camera Adapter | USB/CSI/영상 파일에서 프레임 획득·복구 | Jetson 카메라 구현 가능 |
| Detector | 사람·흉기 bounding box와 confidence 생성 | PyTorch/TensorRT 교체 가능 |
| Tracker | detection에 track ID와 이동 이력 부여 | Stretch goal, 공통 순수 로직 우선 |
| Spatial Association | nearest person, 정규화 거리, 확장 bbox로 knife-person 연관 산출 | 공통 순수 로직 |
| Temporal Confirmation | associated history를 K-of-N으로 판단 | 공통 순수 로직 |
| Alert State Machine | 확정된 상태 전이와 cooldown | 공통 순수 로직 |
| GPIO Alarm | LED·부저·상태 버튼 제어 | Jetson 전용 |
| Event Recorder | metadata·snapshot 및 선택적 clip·보존 정책 관리 | 저장장치·인코더 의존 |
| Resource Monitor | CPU/GPU/RAM/온도/전력 수집 | Jetson `tegrastats` 등 |
| Dashboard/Event API | 위험 이벤트의 표시·선택적 전송 | 네트워크·서버 의존 |

## 최소 데이터 계약 - `PROPOSAL`

### Detection v1

- 생산자: Detector
- 소비자: Spatial Association, Renderer, 선택적 Tracker
- 필드: `class_id`, `label`, `confidence`, `bbox`, `frame_timestamp`, `source_id`
- 금지: 원본 영상 자체, 개인식별정보를 로그 필드에 직접 삽입
- 오류 처리: 프레임 누락·모델 오류·신뢰도 미달은 명시적인 상태로 전달

### ThreatEvent v1

- 생산자: Temporal Confirmation / Alert State Machine
- 소비자: GPIO Alarm, Event Recorder, Dashboard
- 필수 필드 후보: `event_id`, `timestamp`, `source_id`, `state`, `reasons`, `model_version`, `latency_ms`, `scenario_id`
- 선택 필드 후보: `associated_person_bbox`, `d_norm`, `snapshot_path`
- 보존: 정책 확정 전까지 실제 민감 영상 보존 기간을 결정하지 않음
- 오류 처리: 이벤트 저장·전송 실패는 로컬 경보를 차단하지 않음

### MVP temporal identity boundary

MVP에는 tracking이 없으므로 프레임 간 동일 person identity를 보장하지 않는다. 각 프레임에서 `associated_person_knife_exists`라는 source-level boolean을 계산하고 K-of-N은 이 신호를 집계한다. 따라서 결과는 특정 개인의 연속 소지를 추적했다는 의미가 아니다.

### B0~B3 실행 의미

| 조건 | confirmation predicate |
|---|---|
| B0 | 현재 frame에 reliable knife detection 존재 |
| B1 | reliable knife presence가 K-of-N 충족 |
| B2 | 현재 frame에 geometry-associated person–knife pair 존재 |
| B3 | geometry association 신호가 K-of-N 충족 |

네 조건은 하나의 pipeline과 event contract를 공유하고 confirmation predicate만 교체한다.

## 실패와 fallback

- 카메라 입력이 끊기면 재시도를 수행하고, 복구 실패 상태를 명시한다.
- 네트워크 실패 시 로컬 탐지·GPIO 경보·로컬 이벤트 기록은 유지한다.
- 저장공간 부족 시 보존 정책에 따라 오래된 이벤트부터 회수하되, 정책과 실제 동작을 테스트로 검증한다.
- 모델·추론 오류 시 거짓 안전 상태로 위장하지 않고 상태 LED·로그·대시보드에 장애를 표시한다.

## 데이터 경계 - `PLANNED`

실제 영상 수집 전에 수집 장소, 참여·동의, 보존 기간, 접근 권한, 삭제 절차, 지도기관 요구사항을 확정한다. 이벤트 영상은 원본 민감 데이터로 취급하며, 개발 로그나 Git에 저장하지 않는다.
