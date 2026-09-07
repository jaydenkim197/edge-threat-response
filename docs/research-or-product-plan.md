# Research and Experiment Plan

상태: `PLANNED`

2026-09-07부터 프로젝트 목적·범위·일정의 기준 역할은 `project-plan.md`로 이전했다. 이 문서는 MVP 결정 이후 연구 가설, 실험 변수, 시나리오, 분석 절차를 구체화하는 보조 문서다. 아래 후보는 `project-plan.md` 또는 `open-decisions.md`보다 우선하지 않는다.

## 문제 정의

기존 시스템은 흉기 객체가 한 프레임에서 탐지되면 경보하는 프로토타입에 가깝다. 이는 오탐·순간 검출·실제 위험 상황의 구분 부족, 사건 기록 부재, 장시간 운영 안정성 미검증이라는 한계를 가진다.

## 목표

**상황 인지형 Edge AI 흉기 위협 대응 시스템**을 설계·구현·검증한다.

핵심 질문은 다음과 같다.

1. 연속 프레임과 상태 머신을 적용하면 단일 프레임 경보보다 불필요한 경보를 줄일 수 있는가?
2. 선택한 공간·시간 context factor가 사건 수준 판단에 기여하는가?
3. 제한된 엣지 자원에서 정확도뿐 아니라 지연, FPS, 메모리, 온도, 전력, 장시간 안정성을 어떤 균형으로 확보할 수 있는가?

## 초기 연구 비교안 - `PROPOSAL`

```text
Baseline
  -> single-frame weapon detection
  -> immediate alarm

Proposed
  -> 동일 detection
  -> 선택된 spatial / temporal context
  -> threat state machine
  -> alarm + event evidence
```

정확한 context factor, 상태 수, snapshot/clip 범위와 목표 수치는 아직 결정되지 않았다. MVP는 단일 카메라·로컬 우선 동작을 전제로 하며 네트워크가 끊겨도 핵심 경로가 유지되어야 한다.

## 개발 후보

| 후보 | 가치 | 난이도 | 권장 위치 | 상태 |
|---|---|---:|---|---|
| 연속 프레임·상태 머신 경보 | 오탐 억제와 제품 완성도 | 중 | MVP 후보 | `PROPOSAL` |
| 사건 metadata·snapshot | 사후 분석·재현 | 중 | MVP 후보 | `PROPOSAL` |
| benchmark·최소 자원 기록 | 논문 실험 착수 조건 | 중 | MVP 후보 | `PROPOSAL` |
| 사람-흉기 관계·지속 시간 | 상황 인식 차별성 | 중 | MVP 후보 | `PROPOSAL` |
| 객체 추적·움직임·복합 위협 점수 | 문맥 확장 | 상 | Stretch | `PROPOSAL` |
| Nano vs Orin Nano 비교 | 정량적 엣지 최적화 연구 | 중상 | 검증 단계 | `PROPOSAL` |
| Edge-Server 이벤트 대시보드 | 다중 장치 확장성 | 중 | 3차 개발 | `PROPOSAL` |
| 멀티카메라 Re-ID | 시각적 차별성 | 상 | 후속 과제 | `DEFERRED` |
| RGB + IR/Thermal 융합 | 저조도 강건성 연구 | 상 | 후속 과제 | `DEFERRED` |
| Active Learning | 현장 적응·MLOps | 중상 | 후속 과제 | `DEFERRED` |
| Privacy-aware CCTV | 개인정보 최소화 | 중 | 전 단계의 운영 제약 | `PLANNED` |

## 위협 판단 초안 - `PROPOSAL`

위협 점수는 추가 대형 행동 인식 모델보다 경량 탐지와 기하학·시계열 규칙을 우선 결합한다.

```text
weapon confidence
+ hand/weapon 또는 person/weapon proximity
+ person-to-person proximity
+ weapon motion
+ temporal persistence
= threat score
```

현재 권장 상태 후보는 `NORMAL`, `SUSPECTED`, `ALARM`, `COOLDOWN`이다. 상태 수와 의미는 MVP 결정 전까지 확정하지 않으며, 결정된 임계값·가중치·전이 조건은 코드 하드코딩 대신 설정과 실험 기록으로 관리한다.

## 평가 계획 - `PLANNED`

| 범주 | 지표 | 주의 사항 |
|---|---|---|
| 탐지 | Precision, Recall, F1, mAP | 데이터셋·분할·임계값을 기록 |
| 경보 | false alarms per hour, 경보 지연, 누락 사건 | 시나리오와 ground truth를 정의 |
| 성능 | FPS, inference latency, end-to-end latency | 입력 해상도·모델·런타임을 고정 |
| 자원 | CPU/GPU/RAM, 온도, 전력 | 장비·전원 모드·측정 도구 기록 |
| 안정성 | 연속 동작 시간, 카메라/네트워크 복구, 저장공간 회수 | 실기기 시험과 로컬 시험을 구분 |

## 범위 관리

이번 학기의 성공 기준은 모든 후보의 구현이 아니라, 확정된 MVP를 재현 가능하게 만들고 선택한 상황 인식 요소가 사건 수준 결과에 미치는 영향을 검증하는 것이다. 구체적인 범위와 일정은 `project-plan.md`를 따른다.
