# CCTV0/31의 추론·평가 경로 진단 — 2026-11-08

**조사한 추론·색상·전처리·좌표 복원·매칭 경로에서0/31을 설명할 구현 오류는 찾지 못했다.** M1/M2/S1의 직접 Ultralytics640 추론은83장 모두 기존 저장 예측과 좌표·confidence가 정확히 일치했다. 정답을 예측으로 넣으면 평가기도31TP·0FP·0FN을 올바르게 계산했다.

현재 관측은 해당 CCTV에서 모델의 올바른 위치 후보와 confidence가 부족하다는 쪽을 지지한다. 단, 이것만으로 학습 데이터·모든 라벨의 의미/정확성·장면 차이의 단일 원인까지 규명한 것은 아니다. 작은 칼과 CCTV 외형/가림/화질에 대한 학습 부족은 후속 통제 실험으로 검증할 가설이다.

## 목적·범위·환경

사용자는 평가83장을 직접 보고 큰 문제는 없어 보인다고 답했다. 다음 단계로 이전에 요청한 GT/예측 중첩과 모델·라벨·전처리·평가 원인 구분을 수행했다. 사람 확인을 새 공식 라벨 승인으로 바꾸지 않는다.

- 고정 입력: 같은 US Mock83장/GT31개, 기존 M1/M2/S1 best.pt. 원 archive 이미지/원 XML과 평가 입력의 대응은 [앞선 전달 검사](../../datasets/cctv-inspection-handoff-2026-11-08/report.md)에서 확인했다.
- source `ebc7f20`의 기존 evaluator/box/domain, 기존 `.venv-evaluation-20261104`, PC13 RTX3060 12GB/torch2.6.0+cu124/Ultralytics8.4.152. 새 설치·재학습·원본/GT/이전 결과/운영 threshold·모델 변경은 없다.
- 기본 조건: FP32/batch1/square640/rect=False/TF32=False/NMS.7/candidate floor.001/knife class0. 기록된 비교와 같은 인자다.
- `search-first`: 기존 평가·GT·raw box contract·Pillow 시각화 방식을 조합한 일회성 [진단 driver](diagnose-driver.py)다. 제품 코드나 새로운 framework를 추가하지 않았다.
- 공식 성능 재평가가 아닌 열린 개발 자료의 원인 진단이다. GT 기반crop 결과는 일반 추론 결과와 구분한다. 목표 P430/Orin/독립 B0~B4 결과가 아니다.

## 1. 직접 추론과 저장 예측

평가 wrapper를 거치지 않고 같은 checkpoint를 Ultralytics YOLO에 직접 로드해 PIL RGB83장을 예측했다. 원시 결과에서 이미지 밖 clipping 뒤 면적0인 box만 기존 canonical adapter와 같은 조건으로 제외하고 비교했다.

| 모델 | 비교 이미지 | 유효 box 좌표 최대 차이 | confidence 최대 차이 | 차이 이미지 |
|---|---:|---:|---:|---:|
| M1 | 83 | 0.0px | 0.0 | 0 |
| M2 | 83 | 0.0px | 0.0 | 0 |
| S1 | 83 | 0.0px | 0.0 | 0 |

세 checkpoint의 names는 모두 `{0: knife}`이고 실제 head는 end2end=False다. class ID를 잘못 평가했거나 cached 이미지/예측의 연결이 어긋난 증거는 없다. source image/hash/프로토콜/checkpoint와 기존 예측 파일의 전후 hash도 유지됐다.

초기 진단 v1은 직접 raw box를 모두 evaluator에 넣어 면적0인 box에서 중단됐다. 기존 제품 adapter는 이미 이런 box를 제외하고 있었으므로 기존0/31 평가 오류가 아니다. v1을 보존하고 진단 adapter만 같은 제외 계약으로 맞춘 v2에서 완료했다. 모든 probe/control 호출을 합친 면적0 box는152개, 최대confidence.00572 미만으로 .1/.25 진단에는 영향을 주지 않았다. 낮은 floor와 clipping에 대한 현상이며 새 학습이나 runtime 수정은 하지 않았다.

## 2. 색상·입력 tensor·좌표 복원

- 각 모델6장, 총18개의 PIL RGB / 파일경로 / BGR array 예측이 모두 일치했다. 해당 이미지의 PIL/OpenCV JPEG decode RGB pixel 차이도0이다.
- 전체83장×3모델에서 실제 predictor preprocess tensor를 독립적인 OpenCV resize/pad/RGB/255 계산과 비교했다. 최대 차이는약5.96×10⁻⁸로 FP32 나눗셈 반올림 수준이다. 이 경로에서 RGB/BGR 역전·정규화 중복·비율 왜곡을 발견하지 못했다.
- 640 입력은 square letterbox다. 예를 들어1920×1080은640×360으로 줄고 위/아래140px padding이 붙는다. GT를 이 좌표로 보냈다가 설치된 공식 scale_boxes로 복원한 최대 오차는약1.14×10⁻¹³px다.
- 실제 입력의 GT31개 중 **26개는 짧은 변<16px**, 2개는<8px다. 이는 저장 이미지/letterbox 기준 크기이며 물리 거리나 유일한 실패 원인을 증명하는 값은 아니다.

## 3. 평가 대조와 독립 IoU

- 원 GT31개를 confidence1 예측으로 주입한 oracle 대조는 **31TP·0FP·0FN**이다. 예측이 없는 음성52장도 원래 explicit absence 계약으로 포함했다.
- NumPy로 별도 계산한 box IoU를 설치된 Ultralytics box_iou와 비교했고 차이<10⁻⁶이었다. confidence 순 독립 matching의 TP/FP/FN도 기존 evaluator와 모든 full-frame probe에서 일치했다.
- matching IoU를 .5→.25로 낮춰도 confidence.25의 세 모델은 계속0/31이다. .1로 크게 풀면 M1/M2만 각각1/31이고 S1은0이다. 작은 경계 오차만으로 이번 실패를 설명하기 어렵다. [별도 매칭 진단](relaxed-matching.json).

## 4. 낮은 confidence의 올바른 위치 후보

아래 후보 수는 IoU≥.5를 만족하면서 confidence≥.001인 GT 수다. .001보다 작은 후보까지 존재하지 않는다는 주장은 아니다.

| 모델 | GT31 중 올바른 위치 후보 있음 | confidence≥.1 | confidence≥.25 | 올바른 위치 후보 최대confidence |
|---|---:|---:|---:|---:|
| M1 | 3/31 | 3/31 | 0/31 | 0.2256 |
| M2 | 3/31 | 0/31 | 0/31 | 0.0613 |
| S1 | 6/31 | 2/31 | 0/31 | 0.1533 |

대부분은 올바른 위치에 충분한 후보 자체를 내지 못한다. threshold.25만의 문제가 아니며, 낮추면 잘못된 bbox도 함께 크게 늘어난다. source별 전체 숫자는 [GT 진단 CSV](gt-diagnostics.csv)에 있다.

## 5. 해상도 probe

기존640 학습 checkpoint의 **추론 입력만** 바꿨다. confidence.25/IoU.5이며 각 full-frame 조건은 같은83장/31GT다. 이 열린 자료에서 최종 해상도를 선택하거나 Orin 비용을 주장하지 않는다.

| 모델 | 640 TP/FP | 960 TP/FP | 1280 TP/FP |
|---|---:|---:|---:|
| M1 | 0/31 · 2 | 1/31 · 2 | 2/31 · 2 |
| M2 | 0/31 · 7 | 1/31 · 2 | 0/31 · 6 |
| S1 | 0/31 · 4 | 3/31 · 7 | 0/31 · 6 |

S1은960에서3TP/7FP로 일부 회복하지만1280에서는0TP/6FP다. 단순히 해상도를 높이면 해결된다고 할 수 없다. [전체 probe·confidence별 지표](metrics.csv).

## 6. GT 기반 영역 확대 — 참고 실험

정답 중심을 알고 원본512×512영역을 잘라640으로 넣었다. 양성31장만 사용하고, 좌표는crop 기준으로 변환했다. 위치 정답을 사용했고 배경/문맥도 바뀌므로 실제 배포·동일 full-frame 성능이나 크기만의 인과 효과를 뜻하지 않는다.

confidence.25의 TP/FP는 M1 **1/6**, M2 **3/3**, S1 **0/4**다(각31GT). 확대만으로 일관된 회복이 없었다. 따라서 학습된 특징과 실제 CCTV의 시점·흐림·가림·context 차이도 남는 가설이다. 이를 새로운 모델 선정 근거로 쓰지 않는다.

## 시각 자료와 다음 단계

사용자 바탕화면 `261108_CCTV추론진단`에 같은 번호별 M1/M2/S1 전체 frame·칼 주변 예측·640 입력·GT 기반 ROI를 별도로 보관한다. 초록GT/빨강≥.25/주황.1~.25/청록낮은confidence의GT관련후보다. 원본 사용자 묶음과 모델 입력/기존 평가를 바꾸지 않았다. 이미지·얼굴·ZIP은 Git에 올리지 않는다.

다음 우선순위는 **새 목표 환경 데이터로 T1을 검증할 준비**다. 기존 공개 평가83장을 학습에 반입하지 않는다. 다음 주 P430 촬영에서 선명한 근거리/작은 원거리·가림·일상물체 장면을 확보하고 camera/session을 train/tuning/final로 먼저 분리한다. bbox·Holding·event GT를 각각 준비한 뒤, 기존 모델을 기준으로 T1의 개선 여부를 판단한다. 실시간 운영 입력·detector·threshold·D*는 자동 교체하지 않았다.

검증 범위 밖: 모든 학습 원본의 의미 정확성, 학습/관측 실패 원인의 완전한 분해, 목표 P430 최소 유효 물체 크기, 실제 Holding/Orin/GPIO/독립 final 성능. 조사한 경로의 일치만으로 이 항목들을 검증했다고 주장하지 않는다.

원시 위치: PC13 `data/work/cctv-diagnostics-20261108-v2`; v1 실패 state도 보존했다. [고정입력·model·tensor·좌표·대조 결과](audit.json), [실행 state/driver hash](state.json), [진단 driver](diagnose-driver.py), [시각화 driver](render-driver.py). 실제 실행은 기존 source ebc7f20이며 Git commit은 본 이력으로 추적한다.
