# 병렬 개발 연구: 학습 기반 Human-Knife Interaction Detection (B4)

<!-- docs-refresh-20261106:begin -->
## 현재 단계 — 2026-11-06

B4는 11/05 승인된 11월 병렬 개발 범위다. [구현·합성 연결 검증](../reports/runtime/hoi-b4-integration-2026-11-05/report.md)과 실제 Holding 정답·학습·성능을 구분한다. 실제 관계 라벨과 학습 결과는 아직 없으며 공개 knife bbox나 싸움 구간을 Holding 정답으로 치환하지 않는다.

G0와 도구 준비는 완료 기반이다. G2 실제 관계 라벨 → G3 학습 → G4 독립 비교가 남아 있다. [관계 계약](hoi-annotation-contract.md), [현재 작업표](pre-orin-work-plan.md).
<!-- docs-refresh-20261106:end -->

> 상태: **11월 범위/기한 DECISION, G/VG 학습기·B4 연결 IMPLEMENTED / 합성 CPU/Orin CUDA 연결 VERIFIED, 실제 관계 학습·성능 미검증**
> 작성: 2026-11-02 / 사용자 결정 갱신: 2026-11-05  

2026-11-05: [관계 정답 교환 규격·학습기·B4 사용법](hoi-annotation-contract.md)을 구현했다. 실제 관계 라벨은 사이트 담당이 별도로 수집하며 기존 이미지 검수의 두 질문을 소지 정답으로 바꾸지 않는다. 아래 실제 학습·성능 가설과 독립 평가 gate는 그대로 남는다.
> 기존 MVP 완료 이후 검토 제안은 2026-11-05 병렬 착수 결정으로 대체됨.

## 2026-11-05 — 병렬 개발 착수 결정 (기존 제안의 상태 변경)

**확정:** 2026-11-30까지 HOI B4 학습·Orin 통합·독립 평가를 YOLO 데이터/모델 고도화 및 B0~B3 연구와 병렬로 진행한다. 이전의 MVP 완료 이후만 착수한다는 순서 제안은 이 결정으로 대체한다. **실제 모델·학습·성능은 아직 미검증**이다.

- **1차 목표:** Person–Knife pair의 Holding / Not Holding 이진 분류. 불명확한 장면은 uncertain으로 보류하고, Using/공격 의도 판단은 2차 후속 확장.
- **YOLO 의존/HOI 독립:** 같은 YOLO person+knife detections에서 pair/union crop을 만들되 기존 Spatial 결과로 학습 정답을 생성하지 않는다. 실제 holding/not-holding 관계는 수동 GT를 사용한다.
- **최초 모델군:** B4-G(geometry MLP) vs B4-VG(pretrained MobileNetV3-Small image features+geometry MLP). 224/256 union crop 후보. ResNet18, hand-specific 모델은 성능/시간 조건부.
- **훈련 자료:** 자체 약3m CCTV와 스마트폰을 촬영하고 30~60클립·300~600라벨 프레임을 1차 목표로 수집. 공개 HICO-DET/100DOH/Hands23 후보는 실제 holding 라벨·pretrained weight 적합성 확인 후 활용. session·participant·camera 조건별 분리. GT-box 기반 관계 학습·진단과 실제 YOLO detected-box 기반 성능을 따로 기록한다.
- **B3 대비:** 동일 frozen D* YOLO/영상/JSONL·K-of-N·FSM에서 B3=Spatial, B4=HOI 판단만 변경한다. Pair-level P/R/F1, Event P/R/F1·False Alerts/hour·latency, Orin 추가 지연·RAM을 비교한다. B5는 선택.
- **일정:** 11/05–08 규칙·모델 준비, 09–12 촬영·GT, 13–16 1차 학습, 17–20 개선·동결, 21–24 Orin 결합, 25–27 최종 평가, 28–30 결과 고정. 팀원 고정 역할 배정 없음.

## 1. 연구 배경과 목적

현행 시스템은 YOLO 기반 `person` 및 `knife` 탐지 결과에 Bounding Box 기하 규칙(Spatial Association)과 K-of-N 시간 확인(Temporal Confirmation)을 적용합니다.

이 방식은 계산이 단순하고 판단 근거가 명확하지만, **사람과 칼의 공간적 근접성이 실제 칼 소지(Holding)를 보장하지 않는다**는 한계가 있습니다.

- 칼이 책상 위에 있는데 사람이 가까이 있는 경우에도 두 Bounding Box의 관계가 조건을 충족할 수 있습니다.
- 실제로 칼을 들고 있어도 칼의 크기, 손에 의한 가림, 높은 카메라 시점 때문에 소지 관계를 놓칠 수 있습니다.
- K-of-N은 최근 판정의 일관성을 확인하지만 손과 칼의 접촉이나 동일 객체의 연속성을 직접 추론하지 않습니다.

**11월 병렬 연구 질문:** 같은 객체탐지 결과를 사용할 때, 사람과 칼의 이미지 특징 및 위치 정보를 학습하는 경량 관계 분류기가 기존 규칙 기반 공간 판단보다 **칼 소지 여부를 정확하게 구분**하고, 사건 탐지율과 지연을 과도하게 희생하지 않으면서 오경보를 감소시킬 수 있는가?

이 연구에서 구분하려는 개념은 다음과 같습니다.

| 개념 | 의미 | 연구에서의 역할 |
|---|---|---|
| Proximity | 사람과 칼의 공간적 근접성 | 기존 BBox 규칙의 주요 단서 |
| Contact | 손과 칼 사이의 물리적 접촉 | 학습에 활용할 수 있는 보조 정보 |
| Grasp | 손으로 칼을 잡는 형태 또는 상태 | 추후 특징·보조 라벨 후보 |
| Holding | 특정 사람이 칼을 실제로 들고 있거나 소지하는 상태 | **B4의 우선 분류 목표** |

접촉은 소지와 동의어가 아닙니다. 이 연구는 범죄 의도나 공격 행동을 판정하는 모델을 목표로 하지 않습니다.

## 2. 현행 연구와 후속 연구의 경계

| 구분 | B0~B3 기준선 | 11월 병렬 B4 |
|---|---|---|
| 객체탐지 | Person + Knife YOLO | 동일 detector 출력 재사용 |
| 관계 판단 | 확장 Person BBox에 Knife 중심점 포함 여부 | **학습 기반 Holding / Not Holding 분류** |
| 시간 판단 | K-of-N | 첫 비교에서는 동일 K-of-N 유지 |
| 경보 처리 | 기존 4-state FSM | 기존 FSM 그대로 재사용 |
| 비교 목적 | B0~B3: 공간·시간 규칙의 효과 | **B3 vs B4: 학습된 관계 특징의 추가 효과** |
| 현재 상태 | 소프트웨어와 파일 영상 처리 경로 검증, 실카메라 정식 평가는 미완료 | G/VG학습기·sidecar/replay/snapshot구현/합성검증;실제GT·성능미완료 |

**2026-11-05 우선순위 변경:** HOI 자료·학습을 기존 B0~B3 검증과 병렬 진행한다. 기존 MVP의 실제 카메라/GPIO·event 정량 평가도 유지하고, 11월30일까지 양 트랙의 개발·평가 완료를 목표로 한다.

## 3. 제안 모델: 경량 CNN + Geometry MLP

전면적인 End-to-End HOI 모델 학습 대신, 기존 YOLO 출력 뒤에 **경량 관계 분류기**를 추가하는 2단계 구조를 우선 제안합니다.

```text
Camera / Recorded Video
    -> Existing YOLO Person + Knife Detection
    -> Person-Knife Candidate Pair Generation
         |-> Union Crop (person + knife 영역) -> Lightweight CNN -> Visual Features
         |-> Normalized BBox / relative position / size -> Small MLP -> Geometry Features
    -> Feature Fusion
    -> Relation Classifier: P(Holding | Person, Knife)
    -> Threshold -> K-of-N Temporal Confirmation
    -> Existing FSM -> Alarm / Metadata / Snapshot
```

- **Visual branch:** 사람과 칼을 포함하는 영상 영역에서 손, 칼 손잡이, 주변 배치 등 이미지 특징을 추출합니다. MobileNet 계열의 경량 CNN은 검토 후보이지 확정된 모델이 아닙니다.
- **Geometry branch:** 두 객체의 정규화 좌표, 크기 비율, 상대 중심점과 같은 특징을 작은 MLP에 입력합니다.
- **Fusion:** 두 특징을 결합해 사람-칼 쌍의 `holding` 가능성을 예측합니다.
- **Temporal / FSM:** 초기 실험에서는 현재 K-of-N과 FSM을 유지해 **관계 판단기의 변경 효과**를 분리합니다.

**유의할 점:** BBox 좌표만 입력하는 MLP는 보이지 않는 손-물체 접촉 정보를 생성할 수 없습니다. 또한 1프레임 CNN은 실제 시간적 동작을 학습하지 않으므로, Video HOI, Tracking, Pose Estimation은 별도의 확장으로 구분합니다.

### 추가 비교 모델 후보

1. **B3:** 기존 규칙 기반 Spatial Association + K-of-N.
2. **B4-G:** Geometry 특징만 학습하는 경량 분류기 + 동일 K-of-N. 수작업 규칙과 학습된 좌표 경계의 차이를 확인하는 보조 기준선.
3. **B4-VG:** CNN 이미지 특징 + Geometry MLP 결합 + 동일 K-of-N. 11월 비교 모델. 실제 성능은 미검증.
4. **B4-H(조건부):** 사전학습된 Hand-Object Contact / Grasp 특징을 추가한 구조. 작은 손/칼의 가시성과 재사용 가능성을 검증한 후에만 검토합니다.

## 4. 선행연구 활용 계획

### 4.1 100DOH: 손-물체 접촉 정보

- **논문:** Shan et al., *Understanding Human Hands in Contact at Internet Scale*, CVPR 2020.
- **연구 정보:** 손 Bounding Box, 좌우 구분, 접촉 상태 및 접촉 객체의 Bounding Box 추정.
- **활용 가능성:** 손과 칼의 접촉 후보를 나타내는 특징, 관계 라벨 설계, 사전학습된 손-객체 검출기의 feasibility 검토.
- **한계:** 접촉 검출 결과를 곧바로 `Knife Holding`의 정답으로 해석할 수 없으며, 고정형 고각 웹캠 영상에서 성능은 별도로 확인해야 합니다.
- [CVF 논문](https://openaccess.thecvf.com/content_CVPR_2020/html/Shan_Understanding_Human_Hands_in_Contact_at_Internet_Scale_CVPR_2020_paper.html) / [프로젝트 및 공개 모델](https://fouheylab.eecs.umich.edu/~dandans/projects/100DOH/)

### 4.2 Hands23: 손-객체 상호작용 및 Grasp 정보

- **논문:** Cheng et al., *Towards A Richer 2D Understanding of Hands at Scale*, NeurIPS 2023.
- **연구 정보:** 손과 접촉 물체의 위치 및 영역, 접촉 관계, Grasp Type 등.
- **활용 가능성:** `contact`와 `grasp` 정보를 보조 특징 또는 별도 검수 항목으로 사용할 수 있는지 조사합니다.
- **한계:** 공개 모델·데이터를 활용할 수 있는지, 우리 촬영 도메인에서 정확하게 작동하는지, 실제 칼 소지 판단에 유리한지 검증해야 합니다.
- [NeurIPS 논문](https://proceedings.neurips.cc/paper_files/paper/2023/hash/612a7948f3294a02a63d970566ca8536-Abstract-Conference.html) / [프로젝트 페이지](https://fouheylab.eecs.umich.edu/~dandans/projects/hands23/)

선행연구의 방법을 참고하거나 공개 가중치를 실험할 수는 있지만, **논문 방법을 적용했다는 사실만으로 칼 소지 판단이 해결된 것으로 간주하지 않습니다.** 코드·가중치·데이터셋의 이용 조건과 재현 환경도 별도로 확인합니다.

## 5. 학습 데이터 요구사항

기존 Knife Detection의 Bounding Box 라벨만으로는 사람-칼 **관계 분류**를 지도학습할 수 없습니다. 관계 학습에는 각 `person–knife pair`의 명시적 정답이 필요합니다.

### 최소 라벨 설계 후보

| 항목 | 예시 / 의미 |
|---|---|
| `person_bbox`, `knife_bbox` | 탐지 대상 쌍의 위치 |
| `holding_label` | `holding` / `not_holding` / `uncertain` |
| `contact_label` (선택) | `contact` / `no_contact` / `unknown` |
| `source_id`, `session_id`, `leakage_group_id` | 영상 출처 및 독립 평가 그룹 관리 |
| `distance`, `viewpoint`, `occlusion` | 조건별 성능 분석 |

우선 필요한 사례:
- **Positive:** 사람이 안전한 모형 칼을 들고 정지하거나 이동하는 장면.
- **Hard Negative:** 칼이 책상이나 바닥에 놓여 있고 사람이 가까이 있는 장면, 칼을 집기 직전, 다른 사람이 칼을 든 장면, 유사 물체를 든 장면.
- **Uncertain:** 손-칼 관계가 프레임만으로 명확하지 않은 경우. 임의로 양성 또는 음성에 포함하지 않습니다.

같은 녹화의 연속 프레임과 파생 이미지가 학습과 최종 평가에 동시에 포함되지 않도록 **녹화 세션 단위로 분리**합니다. 실제 관계 라벨을 확보하기 어려우면 모델 설계를 먼저 키우지 않습니다.

## 6. 성능 평가와 연구 가설

- **H1:** B4-VG는 동일 YOLO 출력과 같은 K-of-N 조건에서 B3보다 소지하지 않은 칼에 대한 오경보를 감소시킵니다.
- **H2:** 경량 관계 분류기의 추가 연산 비용은 Orin 기반 시스템의 처리량과 경보 지연을 수용 불가능한 수준으로 악화시키지 않습니다.
- **H3(선택):** B4-G 대비 B4-VG의 성능 차이를 통해 **영상 시각 특징 자체의 추가 가치**를 확인할 수 있습니다.

세 가설은 아직 검증되지 않았습니다.

| 평가 수준 | 측정 항목 |
|---|---|
| 관계 분류 수준 | Pair-level Precision / Recall / F1, 혼동행렬, Hard Negative별 오류 |
| 사건 판단 수준 | Event Recall / Precision / F1, False Alerts/hour, Duplicate Alerts, Event-to-Alert Latency |
| Edge 수준 | 관계 모델의 추가 추론시간, 전체 FPS, End-to-End Latency, RAM, 온도 |

**공정한 실험 조건:**
1. B3와 B4에 동일한 녹화 영상 및 **동일 YOLO 예측 출력**을 공급합니다.
2. 첫 비교에서 K/N, FSM, 사건 정답 및 경보 매칭 정책을 동일하게 유지합니다.
3. 관계 분류기의 임계값은 개발·튜닝 데이터로만 정하고, 최종 Holdout 세션에서 다시 조정하지 않습니다.
4. 같은 Recall 수준에서의 오경보율 비교도 추가 검토합니다. 단순한 임계값 조정 효과와 관계 학습의 이득을 구별하기 위해서입니다.
5. Detector가 칼을 미검출한 경우 관계 분류기가 그 칼을 복구하는 것은 아닙니다. **Detector 오류와 Relation Classifier 오류를 분리해 분석**합니다.
6. 결과에는 사건 수, 음성 관찰시간, 독립 세션 수, 조건별 실패 사례 및 불확실성을 함께 기록합니다.

## 7. 착수 조건과 진행 단계

| 단계 | 내용 | 진행 판단 기준 |
|---|---|---|
| **G0 — 병렬 착수** | B0~B3 실기기 검증을 유지하면서 HOI 라벨·학습을 병렬 진행 | source/GT와 GPU 자원 분리, 독립 세션 확보 |
| **G1 — 선행 모델 시험** | 100DOH / Hands23 및 고각 웹캠 영상에서 손·칼 가시성 확인 | 영상에서 관계를 판별할 정도의 시각 정보가 있는지 |
| **G2 — 관계 라벨 확보** | Holding / Not Holding 검수 규칙, Hard Negative, 독립 세션 분할 | 일관된 라벨과 시험 데이터 확보 |
| **G3 — 소형 학습 실험** | B4-G 및 B4-VG 학습, Pair-level 진단 | 영상 특징 추가의 이점이 개발 데이터에서 확인되는지 |
| **G4 — B3 vs B4 평가** | 기존 FSM 통합, 동일 입력 비교, Orin 실측 | Event 성능 개선과 계산 비용을 독립 데이터로 보고 |

### 중단 조건 (No-Go)

- 고정형 촬영 시점에서 손과 칼의 관계를 영상만으로 안정적으로 구분할 수 없는 경우.
- 관계 라벨이 부족하거나 세션 독립성을 확보하기 어려운 경우.
- 현행 B3의 주요 실패 원인이 관계 판단보다 **Knife Detector 미검출**인 경우.
- B0~B3 필수 검증을 누락할 정도로 작업 충돌이 생기는 경우에는 HOI 추가 실험 수를 줄이고 미완료를 명시한다.
- 추가 모델의 계산 비용에 비해 사건 성능 이득이 미미한 경우.

## 8. 최종 정리

**지금 할 일:** 신규 Detector 실사 혼합 개선, 학습 기반 Holding B4 구축, 기존 B0~B3와 동일 영상 비교, Orin 카메라/경보 및 독립 최종 평가를 **11월30일까지** 수행한다.

**후속:** Using/Video HOI, B5, Holoscan 5.0은 필수 범위에서 제외한다. 실제 HOI 성능은 검증 전까지 미확정이다.
