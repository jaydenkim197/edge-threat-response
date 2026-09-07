# Master Project Plan

상태: 프로젝트 방향·일정·MVP 연구 범위는 `DECISION`, 정량 목표치와 파라미터는 `PROPOSAL`

이 문서는 프로젝트의 목적, 범위, 일정, 성공 조건을 정의하는 최상위 기준이다. 기술 구조는 `architecture.md`, 미확정 선택은 `open-decisions.md`, 실제 변경은 `development-log.md`, 검증 결과는 `verification.md`에서 관리한다.

## 1. Project Identity

- 프로젝트명: 상황 인지형 Edge AI 흉기 위협 대응 시스템
- 수행 기간: 2026-09-01 ~ 2026-12-11
- 기준 플랫폼: Jetson Nano 4GB
- 기준 저장소: `jaydenkim197/edge-threat-response`
- 개발 동결 목표: 2026-10-31

### 역사적 맥락

이 프로젝트는 2025-2 MIDAS에서 진행한 Jetson Nano 기반 흉기 탐지·GPIO 경보 프로토타입을 발전시킨다. 당시 자료에는 카메라 입력, YOLO 기반 사람·흉기 탐지, Jetson 추론, LED·부저 경보, WebSocket UI가 제시되어 있다.

기존 발표자료의 Precision 96.2%, Recall 85.1%, mAP50 93.7%는 평가 분할·환경·명령이 현재 확보되지 않아 `UNVERIFIED`이다. 이번 프로젝트의 공식 결과로 사용하지 않고, 재현 가능한 baseline을 새로 측정한다.

### 최종 목표

단일 프레임에서 흉기가 탐지되면 곧바로 경보하는 구조를, 선택된 공간·시간 문맥을 이용해 사건 수준의 위협을 판단하고 엣지 장치에서 경보·기록·측정할 수 있는 구조로 발전시킨다. 10월 31일까지 반복 가능한 실험을 시작할 수 있는 통합 상태를 만들고, 11월에는 비교 실험과 분석, 12월 초에는 최종 데모·보고서·졸업논문으로 연결한다.

## 2. Problem Definition

현재 자료로 확인된 한계는 다음과 같다.

- 기존 보존 코드는 single-frame weapon detection과 즉시 GPIO 경보 중심이다.
- 기존 정량 수치는 재현 조건이 부족하여 현재 기준 성능을 증명하지 못한다.
- 사건 단위의 정답 정의, 오경보·누락·경보 지연 평가 절차가 없다.
- Jetson Nano의 현재 부팅, 카메라, GPIO, 모델 호환성과 지속 운용 상태가 미검증이다.
- 상황 문맥을 추가했을 때 실제로 오경보가 줄어드는지는 아직 가설이다.

따라서 이 프로젝트는 단순 모델 교체나 mAP 상승보다, 동일 입력에서 baseline과 context-aware 판단을 비교할 수 있는 시스템·실험 체계를 만드는 데 초점을 둔다.

## 3. Core Research and Engineering Questions

| ID | 질문 | 상태 |
|---|---|---|
| RQ1 | 경량 공간·시간 event-confirmation 계층이 single-frame alert보다 사건 수준 오경보를 줄이는가? | `DECISION` |
| RQ2 | 오경보 감소 과정에서 person-associated knife event recall과 경보 지연은 어떻게 변하는가? | `DECISION` |
| RQ3 | spatial association과 temporal confirmation은 각각 어떤 기여를 하는가? | `DECISION` |
| EQ1 | Jetson Nano에서 탐지·판단·경보·기록을 네트워크 없이 반복 실행할 수 있는가? | `DECISION` |
| EQ2 | Nano의 자원·열·지연 제약 안에서 재현 가능한 실행 조건은 무엇인가? | `PLANNED` |

구체 가설·임계값·정량 목표는 baseline, development/tuning set, holdout test 설계 후 기록한다.

## 4. Scope

### In Scope

- 2025 MIDAS baseline의 출처·환경·동작을 재구성하고 재측정
- Jetson Nano 로컬 카메라 입력, 탐지, GPIO 경보
- baseline과 proposed 판단을 같은 입력으로 비교하는 실행 경로
- 사건 단위 평가, 성능·자원 측정, 재현 설정과 증거 기록
- 안전한 모형 소품 또는 적법하게 사용할 수 있는 비민감 입력을 이용한 통제 시나리오

### Official MVP - `DECISION`

| 기능 | 목적·가치 | 난이도 / 의존성 | 논문 기여 | 일정 위험 | 상태 |
|---|---|---|---|---|---|
| Person/Knife detection | 공통 인지 입력과 baseline 제공 | 중 / 모델·Jetson 환경 | 비교 기반 | 구형 stack 호환성 | `DECISION` |
| Single-frame baseline | 기존 방식의 재현 가능한 비교군 | 중 / 탐지·GPIO | 필수 비교군 | 원본 환경 불명확 | `PLANNED` |
| Person–knife geometry association | 정규화 거리와 확장 bbox로 공간 문맥 제공 | 중 / bounding box 계약 | context 효과 비교 | 관계 정의 오류 | `DECISION` |
| K-of-N temporal confirmation | 순간 오탐·누락에 대한 시간 문맥 | 중 / 프레임 시간·누락 처리 | context 효과 비교 | 임계값 과적합 | `DECISION` |
| CLEAR/CANDIDATE/CONFIRMED/COOLDOWN | 판단과 action을 분리 | 중 / context 신호 | 설명·재현 가능성 | 상태 조건 복잡화 | `DECISION` |
| GPIO LED/Buzzer | 엣지 대응 데모 | 하 / Jetson GPIO | 공학 통합 | 하드웨어 상태 | `PLANNED` |
| Event metadata + snapshot | 사건 근거와 오류 분석 | 중 / 저장 정책 | 실험 증거 | 개인정보·용량 | `DECISION` |
| B0~B3 benchmark/ablation | baseline·spatial·temporal 기여 비교 | 중 / 시나리오·정답 | 핵심 실험 기반 | 뒤늦은 평가 설계 | `DECISION` |
| FPS·latency·RAM·temperature 기록 | 엣지 실행 가능성 평가 | 중 / 측정 도구 | 성능·제약 분석 | 측정 방법 차이 | `DECISION` |

세부 operational definition, scenario, ablation과 제외 범위는 `mvp-research-specification.md`를 따른다. model·runtime·threshold·K/N·정량 목표는 baseline 이후 결정한다.

### Stretch Goals

- event pre/post clip
- object tracking과 track ID 기반 연속성
- movement/approaching 분석 및 복합 threat score
- TensorRT/FP16 최적화
- Orin Nano 확보 시 동일 workload 비교
- 선택적 로컬 dashboard

### Deferred / Out of Scope for MVP

- cloud 상시 전송, mobile app
- multi-camera, Re-ID, thermal/IR, pose 또는 대형 행동 인식 모델
- active learning과 대규모 신규 데이터셋 학습
- enclosure·PCB·별도 가속기 설계

확장 기능은 핵심 MVP가 실기기에서 통합·반복 검증된 뒤에만 승격한다.

## 5. MVP Decision Rules

MVP는 아래 조건을 모두 만족하는 조합으로 팀이 확정한다.

1. 2026-10-31까지 Jetson Nano에서 통합·검증 가능하다.
2. 기존 single-frame alert와 구조적 차이가 명확하다.
3. 최종 데모에서 판단 이유를 설명할 수 있다.
4. 동일 입력과 정답 기준으로 정량 평가할 수 있다.
5. baseline 대 proposed 또는 ablation 실험으로 논문에 연결된다.
6. Orin Nano 등 미확보 장비에 성공 여부가 종속되지 않는다.
7. 구현뿐 아니라 오류 분석과 반복 실행까지 남은 인력·시간으로 완료 가능하다.

MVP 확정 시 `open-decisions.md`의 관련 항목을 `DECISION`으로 변경하고, 결정 날짜·참여자·제외 범위·완료 조건을 회의 결정 문서와 개발 로그에 남긴다.

## 6. Definition of Done

기능은 아래 여섯 조건을 모두 만족해야 MVP 완료로 인정한다.

```text
IMPLEMENTED
+ INTEGRATED
+ JETSON VERIFIED
+ REPEATABLE
+ BENCHMARKABLE
+ EVIDENCE RECORDED
```

10월 31일 개발 동결 판단 항목은 다음과 같다. 구체 기능은 MVP 결정 후 확정한다.

- baseline과 proposed를 같은 버전·입력·설정으로 실행할 수 있다.
- 카메라→탐지→판단→GPIO/기록 전체 경로가 Nano에서 작동한다.
- 네트워크 없이 핵심 경로가 유지된다.
- 설정, 모델 버전, threshold, 실행 명령이 기록된다.
- 사건 정답과 지표 산출 절차가 정의된다.
- 반복 실행 결과와 실패 사례의 증거 위치가 남는다.
- FPS, inference latency, end-to-end alert latency를 측정할 수 있다.
- 가능한 범위에서 RAM과 temperature를 같은 방법으로 기록한다.

## 7. Evaluation Strategy

### 비교 구조

```text
Baseline: weapon detection → threshold → immediate alarm

Proposed: detection + selected context
          → threat decision/state machine → alarm
```

두 방식은 동일 영상·해상도·모델·threshold·장비 조건에서 비교한다. context 이외의 조건이 달라지면 별도 실험으로 분리한다.

### 후보 지표

| 범주 | 우선 지표 | 비고 |
|---|---|---|
| Detection | Precision, Recall, F1, 가능 시 mAP | 데이터 분할과 confidence/IoU 기록 |
| Threat/Event | event precision, event recall, F1, false alarms, missed events | 사건 경계와 정답 규칙 선행 |
| Response | detection-to-alert 및 event-start-to-alert latency | 시작점 정의 필수 |
| Edge | FPS, inference latency, end-to-end latency, RAM, temperature | 전원 모드·해상도·runtime 고정 |
| Stability | 연속 실행 시간, 카메라 복구, 네트워크 단절, 저장 실패 | 실기기 fault test |

전력은 신뢰 가능한 측정 장비·방법이 확보될 때만 포함한다. 기존 발표 수치는 `UNVERIFIED`, 새로 설정하는 수치는 `TARGET`, 실제 측정과 검토가 끝난 값만 `MEASURED`로 표기한다.

오경보 30% 감소와 event recall 감소 5%p 이내는 현재 근거 없는 예시이므로 목표로 채택하지 않는다. baseline과 통제 시나리오의 규모를 확인한 뒤 P0 결정으로 정한다.

### 최소 실험군 후보

- 사람이 안전한 모형 흉기를 들고 정지하거나 접근
- 모형 흉기만 놓여 있고 사람이 멀리 있음
- 사람이 놓인 모형 흉기 주변을 지나감
- 순간적 false detection 또는 짧은 검출
- 일부 프레임의 detection 누락

촬영 전 안전 수칙, 참여 동의, 장소, 보존·삭제 정책을 확정한다. 실제 흉기나 위험 행동은 사용하지 않는다.

## 8. Platform Strategy

- Jetson Nano 4GB는 필수 기준 플랫폼이다.
- Jetson Orin Nano는 확보될 경우 비교·확장 플랫폼이며 MVP dependency가 아니다.
- PC/영상 파일 테스트는 순수 로직·반복 실험 준비에 사용하고, Jetson 실기기 검증과 별도로 기록한다.
- Nano의 실제 baseline 측정 전에는 FPS 목표나 TensorRT 필요성을 확정하지 않는다.

## 9. Timeline

| 기간 | 목표 | 종료 증거 |
|---|---|---|
| 9월 전반 | 기존 자료·장비·환경 inventory, Nano 진단, baseline 실행 조건 정리 | 진단 기록, 환경표, blocker |
| 9월 후반 | baseline 복원, MVP spec 확정, scenario·annotation·split 설계 | baseline 증거, spec, 테스트 초안 |
| 10월 전반 | context logic·state machine·logging을 PC 입력에서 구현·검증 | 단위/통합 테스트, 설정 예시 |
| 10월 후반 | Nano 통합, GPIO, benchmark harness, controlled dataset 준비 | 반복 실행과 실기기 증거 |
| 2026-10-31 | practical development freeze / 실험 착수 가능 상태 | DoD 점검표, 고정 commit·config |
| 11월 | benchmark, ablation, 오류 분석, 가능 시 Nano/Orin 비교, 논문·보고서 | 원시 결과, 요약표·그래프, 해석 |
| 12월 초 | 최종 데모·영상·최종보고서·졸업논문 정리 | 제출본과 재현 절차 |

11월의 새 기능은 실험을 막는 결함 수정 또는 명시적으로 승인된 작은 확장만 허용한다. 핵심 알고리즘 변경 시 실험 버전과 결과를 분리한다.

## 10. Risks and Mitigation

| 위험 | 영향 | 대응 |
|---|---|---|
| Nano 구형 JetPack/Python/CUDA stack | 모델·라이브러리 실행 실패 | 환경 inventory 후 기존 조합 재현, adapter 분리, 변경 최소화 |
| 낮은 inference 성능 | 실시간 데모·지연 목표 실패 | 실제 baseline 측정 후 해상도·모델·precision 최적화 결정 |
| thermal throttling | 장시간 결과 왜곡 | 전원 모드·냉각·온도·warm-up 조건 기록 |
| 카메라/GPIO 호환성 | 통합 지연 | 9월에 독립 smoke test, mock interface 제공 |
| 제한된 데이터·시나리오 | 일반화 주장 제한 | 연구 범위를 controlled scenario로 명시하고 과도한 일반화 금지 |
| 오탐·미탐 trade-off | 안전성과 성능 해석 오류 | event recall·false alarm·latency 동시 보고 |
| 위험한 촬영 | 인적·윤리 위험 | 실제 흉기 금지, 안전한 모형·통제 장소·동의 절차 사용 |
| Orin 대여 실패 | 비교 실험 취소 | Nano만으로 완결되는 설계 유지 |
| 일정 초과 | 실험·논문 시간 부족 | 10월 31일 동결, stretch goal 승격 조건 적용 |
| 문서 부채 | 결과 재현·보고서 작성 실패 | 개발 로그와 검증 증거를 작업 완료 조건에 포함 |

## 11. Documentation and Evidence Strategy

### Source-of-truth hierarchy

1. `project-plan.md`: 목적·범위·일정·성공 기준
2. `open-decisions.md`: 아직 확정되지 않은 선택
3. `architecture.md`: 현재 채택된 기술 구조와 계약
4. `verification.md`: 요구사항별 검증 상태와 증거
5. `development-log.md`: 실제 작업과 변경의 시간순 이력
6. `meeting-decisions/`: 팀 결정의 근거
7. `research-or-product-plan.md`: 연구 가설·실험 설계를 구체화하는 보조 문서

`README.md`는 이 구조의 진입점이며, `AGENTS.md`는 Codex 작업 행동 규칙이다. 둘은 project plan의 범위·결정을 대신하지 않는다.

충돌 시 실제 구현·검증 증거, 최신 명시적 결정, 과거 제안 순으로 해석한다. `PROPOSAL`은 팀 결정 없이 구현 의무가 되지 않는다.

### 기록 흐름

```text
작업 카드
→ 코드/설정/문서 변경
→ 검증 및 증거
→ development-log / verification
→ 주간보고서 누적
→ 실험 기록
→ 최종보고서·졸업논문 재사용
```

주간보고서는 매주 금요일 제출 요구에 맞춰 최신 주차가 앞에 오도록 누적하되, 상세 기술 근거는 개발 로그와 검증 문서를 링크한다. 원본 영상·사진·대용량 결과·개인정보는 Git에 넣지 않고 통제된 로컬 저장 위치와 식별자만 기록한다.

## 12. Immediate Decision Gate

다음 개발 작업은 아래 순서로 진행한다.

1. Nano 하드웨어·소프트웨어·카메라·GPIO 진단
2. legacy 모델과 baseline 실행 가능성 확인
3. 안전한 controlled scenario와 사건 정답 기준 초안 작성
4. 균형형 MVP 기능을 일정·의존성·평가 가능성으로 승인 또는 축소
5. 고정된 MVP와 DoD를 기준으로 구현 작업 분해
