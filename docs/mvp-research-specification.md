# MVP Research Specification

상태: 범위·연구 설계 `DECISION`, 임계값·데이터 분할·측정값 `PROPOSAL`

이 문서는 2026-2 MVP의 구현·실험 기준이다. `project-plan.md`의 일정·성공 조건을 구체화하며, 아직 숫자로 정할 수 없는 설정은 확정하지 않는다.

## 1. Claim boundary

### 공식 이벤트 정의

**Person-Associated Knife Event**는 카메라 영상에서 knife가 특정 person과 설정된 bounding-box 기하 조건으로 연관되고, 그 연관이 K-of-N 시간 조건을 충족한 사건이다.

프로젝트의 외부 표현은 **잠재적 흉기 위협 상황 탐지**로 한다. 이 시스템은 실제 폭력 의도, 범죄, 손으로 쥔 상태, 위협 행동을 판별한다고 주장하지 않는다.

### MVP 포함·제외

| 구분 | 범위 | 상태 |
|---|---|---|
| weapon class | `knife`만 | `DECISION` |
| spatial context | bounding-box geometry 기반 person–knife association | `DECISION` |
| temporal context | K-of-N confirmation | `DECISION` |
| response | `CONFIRMED` 진입 시 GPIO LED/Buzzer | `DECISION` |
| evidence | metadata + snapshot 1장 | `DECISION` |
| tracking, movement, pose/hand keypoint, 행동·의도 판별 | MVP 제외 | `DECISION` |
| event clip, dashboard, 추가 weapon class | Stretch | `DECISION` |
| Orin Nano | 동일 workload 비교 플랫폼 | `DECISION`; 대여 여부 `PLANNED` |

## 2. Spatial association

각 reliable knife detection마다 가장 가까운 person을 선택한다. 중심점 거리의 정규화 후보는 다음과 같다.

```text
d_norm(knife, person) = ||c_knife - c_person|| / sqrt(w_person² + h_person²)
```

- `c_*`: bounding box 중심점
- `w_person`, `h_person`: 선택된 person bounding box의 너비·높이

동시에 knife 중심점이 person bounding box를 비율 `α`만큼 확장한 영역 안에 있는지 확인한다. MVP의 associated predicate는 두 기하 신호를 함께 사용한다.

```text
associated = (d_norm <= τ_distance) AND (knife_center in expanded_person_box(α))
```

`α`, `τ_distance`, detector confidence threshold와 association 실패 처리 방식은 baseline 및 development set에서 결정한다. 이 공식은 소지 여부를 증명하지 않으며, bbox 기반 공간 연관만 나타낸다.

## 3. Temporal confirmation and state machine

### K-of-N

최근 `N`개 유효 프레임 중 `K`개 이상에서 `associated`가 참이면 temporal condition을 만족한다. 프레임 누락·detector 미검출은 명시적으로 buffer에 기록한다. `K`, `N`, frame sampling rate는 baseline 후 결정한다.

### State contract

| 상태 | 진입 의미 | 외부 동작 |
|---|---|---|
| `CLEAR` | reliable knife detection이 없거나 직전 event가 종료됨 | GPIO 경보 없음 |
| `CANDIDATE` | knife가 존재하지만 association 또는 temporal 근거가 불충분 | 기록은 diagnostic 수준으로 제한 |
| `CONFIRMED` | association과 K-of-N 조건 충족 | GPIO LED/Buzzer, event metadata, snapshot 1장 |
| `COOLDOWN` | confirmed 후 재경보 억제 구간 | 새 event 전이 규칙에 따라 GPIO 억제 |

`CONFIRMED`는 판단 상태이고, GPIO 경보·기록은 그 상태에 따른 action이다. cooldown 시간, 재진입 조건, event 종료 조건은 측정 전 파라미터다.

## 4. Controlled scenario and annotation

실제 흉기나 위험 행동은 사용하지 않는다. 안전한 모형 소품, 통제된 장소, 참여자 동의가 전제다. 원본 영상과 식별 가능한 사진은 공개 Git에 넣지 않는다.

### 필수 사건 유형

| ID | 유형 | 목적 |
|---|---|---|
| P1 | 사람이 모형 knife를 들고 정지 | 움직임 없는 positive event 검증 |
| P2 | 사람이 모형 knife를 들고 이동 | 시간 지속성 검증 |
| P3 | 테이블의 모형 knife를 집어 듦 | event start 검증 |
| P4 | 부분 가림 또는 두 사람 중 한 명만 knife와 연관 | association 혼동 조건 |
| N1 | knife만 놓여 있음 | unattended-weapon false alert 확인 |
| N2 | 사람이 놓인 knife 근처를 지나감 | proximity hard negative |
| N3 | 사람이 knife 옆에 정지하지만 들지 않음 | candidate와 confirmed 구분 |
| N4 | weapon-like object 또는 짧은 false detection | 순간 오탐 억제 |
| N5 | event 중 일시적 detection dropout | K-of-N 누락 내성 |

거리(Near/Medium/Far)는 필수 환경 변수다. 조도(Normal/Low-light)는 baseline·촬영 여력에 따라 선택하며, 선택하지 않은 조도 일반화는 주장하지 않는다.

### Ground truth

- **Event start**: 사람이 안전한 모형 knife를 들거나 소지하기 시작한 첫 frame.
- **Event end**: knife를 내려놓거나 해당 person–knife association이 명확히 종료된 frame.
- 각 event는 수동 annotation으로 `[start_frame, end_frame]`, scenario ID, 환경 조건, annotation 담당·규칙 버전을 기록한다.

정확한 prediction-to-ground-truth 매칭 허용 구간, ambiguous frame 처리와 annotation 합의 절차는 첫 scenario 샘플을 본 뒤 별도 결정한다.

## 5. Evaluation design

### Ablation conditions

동일 detector, model, 입력 영상, confidence threshold, 해상도, Jetson 조건에서 다음 네 조건을 비교한다.

| ID | 조건 |
|---|---|
| B0 | Detection only → immediate alert |
| B1 | Detection + Temporal K-of-N |
| B2 | Detection + Spatial association |
| B3 | Detection + Spatial + Temporal |

주요 결과는 event precision, event recall, event F1, false alerts, missed events, event-start-to-alert latency다. Edge 결과는 FPS, inference latency, end-to-end latency, RAM, temperature를 같은 방법으로 함께 기록한다.

### Tuning and final evaluation separation

임계값과 K/N은 development/tuning set에서만 선택한다. 최종 평가는 튜닝에 사용하지 않은 recording session 또는 scene을 holdout test set으로 고정해 수행한다. 구체 split 비율·세션 구성은 촬영 가능 조건 확인 후 결정한다.

## 6. Stretch priority

기본 MVP가 `IMPLEMENTED + JETSON VERIFIED + REPEATABLE + BENCHMARKABLE`을 만족한 뒤에만 아래 순서로 검토한다.

1. Orin Nano 동일 workload benchmark
2. TensorRT/FP16 최적화
3. Tracking
4. Simple dashboard
5. Event clip
6. Additional weapon classes
7. Enclosure/PCB

## 7. Remaining parameters

다음은 `DECISION`이 아니다: model/runtime, input resolution, confidence threshold, `α`, `τ_distance`, `K`, `N`, cooldown, camera FPS, sampling rate, final metric targets, alert matching tolerance, tuning/test split. 이 값은 baseline 증거와 experiment record를 근거로 선택한다.
