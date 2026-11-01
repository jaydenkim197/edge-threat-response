# 후속 연구 제안: 학습 기반 Human-Knife Interaction Detection (B4)

> 상태: **PROPOSAL / DEFERRED**  
> 구분: 현행 B0~B3 MVP 완료 이후 검토할 후속 연구 주제  
> 작성일: 2026-11-02  
> 주의: **B4는 아직 설계 후보입니다. 학습, 구현, 성능 개선이 검증된 상태가 아닙니다.**

## 1. 연구 배경과 목적

현행 시스템은 YOLO 기반 `person` 및 `knife` 탐지 결과에 Bounding Box 기하 규칙(Spatial Association)과 K-of-N 시간 확인(Temporal Confirmation)을 적용합니다.

이 방식은 계산이 단순하고 판단 근거가 명확하지만, **사람과 칼의 공간적 근접성이 실제 칼 소지(Holding)를 보장하지 않는다**는 한계가 있습니다.

- 칼이 책상 위에 있는데 사람이 가까이 있는 경우에도 두 Bounding Box의 관계가 조건을 충족할 수 있습니다.
- 실제로 칼을 들고 있어도 칼의 크기, 손에 의한 가림, 높은 카메라 시점 때문에 소지 관계를 놓칠 수 있습니다.
- K-of-N은 최근 판정의 일관성을 확인하지만 손과 칼의 접촉이나 동일 객체의 연속성을 직접 추론하지 않습니다.

**후속 연구 질문:** 같은 객체탐지 결과를 사용할 때, 사람과 칼의 이미지 특징 및 위치 정보를 학습하는 경량 관계 분류기가 기존 규칙 기반 공간 판단보다 **칼 소지 여부를 정확하게 구분**하고, 사건 탐지율과 지연을 과도하게 희생하지 않으면서 오경보를 감소시킬 수 있는가?

이 연구에서 구분하려는 개념은 다음과 같습니다.

| 개념 | 의미 | 연구에서의 역할 |
|---|---|---|
| Proximity | 사람과 칼의 공간적 근접성 | 기존 BBox 규칙의 주요 단서 |
| Contact | 손과 칼 사이의 물리적 접촉 | 학습에 활용할 수 있는 보조 정보 |
| Grasp | 손으로 칼을 잡는 형태 또는 상태 | 추후 특징·보조 라벨 후보 |
| Holding | 특정 사람이 칼을 실제로 들고 있거나 소지하는 상태 | **B4의 우선 분류 목표** |

접촉은 소지와 동의어가 아닙니다. 이 연구는 범죄 의도나 공격 행동을 판정하는 모델을 목표로 하지 않습니다.

## 2. 현행 연구와 후속 연구의 경계

| 구분 | 현행 MVP | 후속 연구 B4 |
|---|---|---|
| 객체탐지 | Person + Knife YOLO | 동일 detector 출력 재사용 |
| 관계 판단 | 확장 Person BBox에 Knife 중심점 포함 여부 | **학습 기반 Holding / Not Holding 분류** |
| 시간 판단 | K-of-N | 첫 비교에서는 동일 K-of-N 유지 |
| 경보 처리 | 기존 4-state FSM | 기존 FSM 그대로 재사용 |
| 비교 목적 | B0~B3: 공간·시간 규칙의 효과 | **B3 vs B4: 학습된 관계 특징의 추가 효과** |
| 현재 상태 | 소프트웨어와 파일 영상 처리 경로 검증, 실카메라 정식 평가는 미완료 | 아이디어 및 연구 계획만 기록 |

**우선순위:** 실제 카메라 환경, 수동 사건 정답, B0~B3 정량 평가 및 Edge 경보 동작 검증이 우선입니다. B4는 해당 과정이 완료되고 개발 일정에 여유가 생긴 경우에만 검토합니다. B4를 이유로 기존 구현이나 최종 평가를 연기하지 않습니다.

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
3. **B4-VG:** CNN 이미지 특징 + Geometry MLP 결합 + 동일 K-of-N. 핵심 후속 연구 후보.
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
| **G0 — 기존 MVP 완료** | 실카메라 B0~B3 평가, 실제 경보 인터페이스 검증, 오류 분석 | 일정 여유가 있고, 관계 판단의 한계가 실제 결과에서 확인되면 착수 고려 |
| **G1 — 선행 모델 시험** | 100DOH / Hands23 및 고각 웹캠 영상에서 손·칼 가시성 확인 | 영상에서 관계를 판별할 정도의 시각 정보가 있는지 |
| **G2 — 관계 라벨 확보** | Holding / Not Holding 검수 규칙, Hard Negative, 독립 세션 분할 | 일관된 라벨과 시험 데이터 확보 |
| **G3 — 소형 학습 실험** | B4-G 및 B4-VG 학습, Pair-level 진단 | 영상 특징 추가의 이점이 개발 데이터에서 확인되는지 |
| **G4 — B3 vs B4 평가** | 기존 FSM 통합, 동일 입력 비교, Orin 실측 | Event 성능 개선과 계산 비용을 독립 데이터로 보고 |

### 중단 조건 (No-Go)

- 고정형 촬영 시점에서 손과 칼의 관계를 영상만으로 안정적으로 구분할 수 없는 경우.
- 관계 라벨이 부족하거나 세션 독립성을 확보하기 어려운 경우.
- 현행 B3의 주요 실패 원인이 관계 판단보다 **Knife Detector 미검출**인 경우.
- 실제 MVP의 핵심 검증 일정에 영향을 줄 경우.
- 추가 모델의 계산 비용에 비해 사건 성능 이득이 미미한 경우.

## 8. 최종 정리

**지금 할 일:** 신규 Detector 개선, 현행 규칙 기반 B0~B3의 실제 영상 평가, Orin 실시간 처리 및 경보 검증.

**후속 연구로 보존할 일:** 100DOH/Hands23의 손-물체 접촉 및 Grasp 정보가 칼 소지 판단에 도움이 되는지 조사하고, 가능성이 확인되면 경량 CNN + Geometry MLP 기반 B4를 학습하여 규칙 기반 B3와 비교합니다.

이 문서는 **연구 제안**이며, B4의 채택, 구현 일정, 정확도 목표와 실제 성능을 확정하지 않습니다.
