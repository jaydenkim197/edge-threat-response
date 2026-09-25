# 선행연구와 공개 데이터셋 검토

기준일: 2026-09-26

상태: 공개 자료의 문헌·저장소 수준 확인. 원본 데이터 파일·라벨·중복·성능의 프로젝트 검증은 `PLANNED`.

## 결론

우리 연구의 비교 대상은 **같은 detector 출력을 사용하는 B0~B3 사건 판단 방식**이다. 선행연구는 공간 연관, 시간 확인, 작은 객체, 오경보, 엣지 측정의 설계 근거로 사용한다. 특정 논문의 수치나 detector 우위를 현재 시스템 성능으로 옮기지 않는다.

공개 데이터의 우선 역할은 [Dataset Source Strategy](dataset-source-strategy.md), 검사 순서와 판정 양식은 [Dataset Evaluation Criteria](dataset-evaluation-criteria.md)를 따른다. 아래 자료 중 어느 것도 원본 패키지 검수만으로 자동 채택되지 않는다.

## 1. 설계에 직접 연결되는 선행연구

| 자료 | 확인된 접근 | 우리 연구에 적용할 부분 | 적용 경계 |
|---|---|---|---|
| [Improving Armed People Detection (2024)](https://doi.org/10.1109/ACCESS.2024.3442728), [공개 코드](https://github.com/AlonsoJAG/armed_people_detection) | Person·firearm bbox 사이의 center, distance, intersection 기반 heuristic과 학습 분류기를 비교한다. | Geometry association의 관련 연구. 필요하면 bbox-only heuristic을 **별도 비교 조건**으로 재구현한다. | Firearm 소지 판별 결과를 knife 소지 성능으로 옮길 수 없다. 우리 MVP의 bbox 조건은 소지를 증명하지 않는다. |
| [DISARM (2024)](https://www.mdpi.com/2076-3417/14/18/8198), [데이터 공개 페이지](https://deepknowledge-us.github.io/DISARM-dataset/) | Detector 뒤에 저신뢰 예측용 2차 분류기와 bbox 연속성을 쓰는 temporal window를 둔다. 데이터 구성·작은 객체·오탐도 다룬다. | 후처리의 FP/recall/latency trade-off와 ablation 설계 참고. | 우리의 K-of-N boolean window와 동일한 알고리즘이 아니다. 공개 페이지에서 확인되는 것은 **test subset**이며 full training dataset은 자동 확보되지 않는다. |
| [Automatic handgun detection alarm (2018)](https://www.sciencedirect.com/science/article/pii/S0925231217308196) | 다섯 번의 연속 true positive에 기반한 경보와 alarm activation time 지표를 보고한다. | 시간 확인이 선행됐음을 명시하고 event-level 경보 지연 지표를 설계한다. | K-of-N의 누락 내성이 기존 연구보다 우수하다고 선험적으로 주장하지 않는다. |
| [ACF (2022)](https://www.mdpi.com/1424-8220/22/19/7158) | 직접 촬영한 full-HD CCTV의 작은 pistol/knife와 tiling을 다룬다. | CCTV 소형 객체 오류 분석, 외부 이미지 평가 후보. | 논문의 2022년 저장소 링크는 현재 접근되지 않는다. 정확한 카메라 높이·화각이 우리 설치와 같다는 근거도 없다. 원본 영상과 event 정답을 확인하기 전에는 사건 평가셋이 아니다. |
| [Real-time gun detection in CCTV (2020)](https://www.sciencedirect.com/science/article/pii/S0893608020303361), [공개 저장소](https://github.com/Deepknowledge-US/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset) | 대학 CCTV의 mock attack 영상·변환 도구를 제공한다. | Camera/sequence 단위로 보존할 외부 평가 후보와 시나리오 설계 참고. | 주 연구 대상은 gun이다. knife 라벨과 연속 프레임·event 정답의 실제 제공 형태를 확인해야 한다. |
| [WeDePE (2022)](https://www.sciencedirect.com/science/article/pii/S0925231221019159) | Pose의 elbow/wrist 정보로 hand ROI를 얻어 weapon detector를 적용한다. | Geometry association의 오류가 확인되면 검토할 후속 아이디어. | MVP에는 pose model을 추가하지 않는다. |
| [YOLOv26s 비교 (2026)](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2026.1789702/full) | SOHAS를 사용해 여러 YOLO variant를 비교하고 Jetson **Nano**에서 pre/inference/post latency를 나눠 보고한다. | Orin Nano 측정 시 단계별 지연과 end-to-end 지연을 모두 기록하는 방법 참고. | Nano 측정값을 Orin Nano 성능 예측치로 쓰지 않는다. 이 연구의 pistol·smartphone·wallet scenario가 우리 knife 사건 실험을 대신하지 않는다. |

추가 참고: [ODeBiC/SOHAS 논문](https://www.sciencedirect.com/science/article/abs/pii/S0950705120300678)은 비슷하게 손에 든 작은 물체의 구별 문제를 제기한다. [Brightness-guided cold steel 연구](https://www.sciencedirect.com/science/article/pii/S0925231218313365)는 knife 데이터와 영상 조건을 검토할 때 참고한다. 이 방법들의 재현 또는 성능 비교는 현재 MVP 범위가 아니다.

## 2. 공개 데이터의 역할과 확인 상태

| 자료 | 지금 확인된 점 | 우선 역할 | 채택 전에 필요한 확인 |
|---|---|---|---|
| [OD-WeaponDetection의 SOHAS](https://github.com/ari-dasci/OD-WeaponDetection) | Knife와 유사한 handheld object를 포함한 detection source가 공식 저장소에 있다. | 첫 public real-data 학습 **후보** | 원본 package/version, knife 및 negative 라벨 완전성, target-view 표본, 권리 충돌, legacy/DaSCI 중복 |
| [DaSCI Knife detection](https://github.com/ari-dasci/OD-WeaponDetection/tree/master/Knife_detection) | 같은 공식 저장소에서 별도 knife detection 자료로 제공한다. | knife appearance 보강 **후보** | SOHAS와 source lineage·exact/near duplicate, 라벨과 촬영 세션 |
| [ACF Knife 논문](https://www.mdpi.com/1424-8220/22/19/7158) | 실제 CCTV small-weapon 평가와 데이터 설명이 있다. | 외부 **이미지** 평가 후보 | 공개 파일에 접근 가능한지, 권리·원본 라벨·촬영 단위. 영상·event 정답이 없으면 B0~B3 사건 지표 계산 불가 |
| [US Mock Attack](https://github.com/Deepknowledge-US/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset) | 공식 저장소는 학술 이용 조건(CC BY-NC 4.0)을 명시한다. | 외부 CCTV sequence **후보** | knife-positive 분포, negative 장면, 시간 순서·촬영 단위·사건 정답, 원본 데이터 접근 |
| [Simuletic CCTV Knife](https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset) | 114장 공개 synthetic sample을 제시한다. | real-data 학습 뒤 별도 synthetic 보강 실험 후보 | 샘플 중복, 라벨, synthetic/real 성능 차이 |
| [Dangerous Items](https://zenodo.org/records/16422779) | 작은/흐린/가려진 위험물체를 설명하는 범용 자료다. | visual gap 확인 후 재검토 | Zenodo record에서 license 표시가 비어 있어 권리 확인 전 사용 보류 |

SOHAS 저장소의 **README는 CC BY-SA 4.0**, [`License.md` 본문은 CC BY 4.0](https://github.com/ari-dasci/OD-WeaponDetection/blob/master/License.md)으로 서로 다르다. 원본 배포 파일의 적용 범위 또는 제공자의 확인 전에는 하나로 단정하지 않는다.

ACF 논문은 [과거 GitHub 주소](https://github.com/iCUBE-Laboratory/The-Armed-CCTV-Footage)를 데이터 위치로 제시하지만 2026-09-26 확인 시 저장소 접근이 실패했다. 논문의 ACF Knife **3,559 image**와 **3,618 knife label**은 서로 다른 단위이므로 raw manifest를 보기 전 inventory로 사용하지 않는다.

## 3. 연구 비교에 적용하는 방식

1. Detector 데이터 실험(L0, R1, R2, S1)은 source별 run ID·학습 recipe·detector weight를 구분한다. 기존 MIDAS 7,361장 export는 사람 검수 전 L0 학습 승인이 아니다.
2. B0~B3의 공간·시간 계층 비교에서는 **동일 detector, 동일 입력 영상, 동일 설정과 장비**를 사용한다. Detector를 바꾼 효과를 상황 판단의 효과로 해석하지 않는다.
3. 공개 CCTV의 bbox 정답은 detector의 image/frame-level 외부 평가에 쓴다. B0~B3의 event precision/recall/alert latency에는 연속 영상, 양성·음성 사건, event start/end 정답이 필요하다.
4. 최종 target-domain 사건 실험은 직접 촬영한 독립 recording session을 기준으로 설계한다. 실제 카메라·화각·관찰 거리가 정해지면 약 3 m CCTV라는 현재 가정을 측정값으로 갱신한다.

## 4. 다음 검수 순서

1. 로컬 legacy 128장 review pack을 사람이 판정해 L0의 역할과 사용 가능 범위를 정한다.
2. SOHAS의 공식 package/version·권리 충돌을 확인하고 knife positive와 no-knife hard-negative를 구분해 표본 검수한다.
3. DaSCI를 독립 검수한 뒤 SOHAS·legacy와 cross-source exact/near duplicate를 검사한다.
4. ACF와 US Mock Attack의 실제 데이터 접근·권리·정답 형태를 확인해 **이미지 평가** 또는 **사건 평가** 중 가능한 역할만 부여한다.

이 문서는 문헌·저장소 수준의 조사 기록이다. Dataset source의 최종 채택과 실험 성능은 사람 검수, raw manifest, run evidence가 나온 뒤 기록한다.
