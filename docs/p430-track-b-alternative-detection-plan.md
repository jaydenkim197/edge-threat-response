# Track B — 대안적 객체탐지 연구 실행 계획

2026-11-26 · 상태 **PROPOSAL** · 공통 기준 PC13 D1

## 1. 목적과 첫 실행 순서

PC13 D1의 6타일 검출을 공통 운용 기준으로 삼는다. D1에서 놓친 59개 중 48개는 기존 소형 구간 밖에 있었다. 개발2에서 공유 예정인 **동일 `epoch0.pt`의 전체·타일 예측과 저점수 후보 캐시**를 대조군으로 받아 후보 없음, 점수 부족, 경계 제거·병합, 위치 불일치를 구분한다. 다음으로 후보 재검증(ALT-01)과 고정 배경 점수 보조(ALT-02)를 별도 실험으로 진행한다. 연속 원본의 전체 시간축과 수동 정답을 준비하면서 ALT-03과 ALT-06의 대조군을 만든다. ALT-04는 기존 RF-DETR·DEIMv2 코드를 활용해 독립적으로 진행할 수 있다. [Track A 계획][track-a] · [P430 평가 결과][p430-result]

| 트랙 | 연구 범위 |
| --- | --- |
| Track A | YOLO 최적화 및 공통 D1·저점수 예측 준비 |
| Track B | 대안 객체탐지 방법의 독립 효과 검증. 실행 ID는 `TB-ALT-*` |
| Track C | 독립 Holding/HOI, B0~B4 비교 및 시스템·Orin 검증 |

ALT-10의 공유 특징 연구는 Track C의 관계 정답과 독립 B4를 대조군으로 사용한다. 실험 기준과 배정 수치는 실행 전에 기록하고 동결한다. 11월 30일 제출에 필요한 Track C 검증을 우선하고, 기한까지 검증되지 않은 Track B 결과는 후속 연구로 남긴다. [Master Plan][master] · [MVP 범위][mvp] · [Holding 규격][hoi]

## 2. 조사 결과와 기존 실험의 재사용

### D1 기준점

| 항목 | 확인한 값과 범위 |
| --- | --- |
| 저장소 | D1 조사·재현 근거는 `f35a562`의 탑재 코드를 참조한다. GPU 검증 근거는 `7b31cbd`의 합성 벤치마크와 현재 운영 가이드를 따른다. [합성 벤치마크][gpu-benchmark] |
| 가중치 | PC13 첫 epoch 저장본 `epoch0.pt`, 1,024 미니배치 이후. SHA-256 `212a4b80e44674a3863daf240e127af797ac34f235a6e8356f23936b6348d190`을 PC13에서 직접 대조 |
| 추론 | 4K의 중앙 `[960,540,2880,1620)` → 1920×1080. 768×640 타일 3×2, 원점 x=0·576·1152, y=0·440. `imgsz=640`, batch 6, `rect=False`, 후보 confidence 0.001, 타일 IoU 인자 0.7·상한 100. 내부 경계 3px 필터 후 중앙 크롭 좌표로 돌아와 NMS 0.55·상한 300 |
| 운영점 | tune의 음성 137장 중 오탐 프레임 상한 1장. 소형 TP → 전체 TP → 음성 오탐 감소 → 전체 FP 감소 순으로 선택. PC13 보존 결과의 정확한 confidence `0.28780144453048706`, TP 매칭 IoU 0.50 |
| 개발 확인 287장 | 작은 칼 47/58(81.0%), 전체 81/140(57.9%), 음성 오탐 0/147, 전체 FP 23개, Precision 81/104(77.9%, 매칭 집계로 계산), AP50 61.82%, AP50–95 18.04% |
| 재현 기준 | PC13 `runs/p430-site-20261124-v1/p430-site-20261124-v1-pc13/`의 `train/weights/epoch0.pt`와 `result.json`에서 확인. 보존 결과에 기록된 dev 타일 예측 SHA-256 `3fa3da7d58ca9721213459fd9d8a2d9b677302dd70365c6ba7a577f71d554f12`. 이번 확인은 가중치 파일과 저장 결과 조회까지 수행 |

같은 비교에서 PC14 타일은 49/58·95/140을 검출했지만 음성 12/147장과 전체 FP 102개를 기록했다. PC13의 기존 `full960` 행은 **다른 `last.pt`**에서 나온 값이다. D1의 입력 방식별 효과는 Track A가 동일 `epoch0.pt`로 비교한 결과를 받는다. 0/147은 개발 표본의 관측치다. `AP50 − AP50–95`의 차이는 위치 오차를 점검할 근거이며, 원인은 박스별 매칭을 대조해 판단한다. [P430 평가 결과][p430-result] · [타일 코드][site-code] · [선택·평가 코드][p430-code]

| 이미 확인한 범위 | Track B에서 새로 검증할 범위 |
| --- | --- |
| 11/21 기존 모델에서 1차 전체+사람 영역은 전체 TP 87→114, FP 17→37. 2차에서는 TP 8→6. 손목 크롭 단독은 두 촬영 모두 불리했다. | ALT-01은 후보 크롭 **검증기**의 독립 효과를 본다. 사람 ROI는 두 번째 단계의 보조 단서로만 비교한다. |
| 11/21 실험은 약 1초 간격 예측의 점수 결합. 2차에서 기존 타일 5/316, 타일+과거 점수 상향 4/316이었다. B1/B3는 K-of-N을 사용한다. | ALT-03은 인접 RGB·특징 결합, ALT-06은 동일 후보의 ID 연관. 기존 점수 누적은 참고 대조군으로 재사용한다. |
| 11/04 동일 평가기의 RF-DETR S/M/L, DEIMv2-S 공개 가중치 비교와 11/15 CCTV 다중 모델 평가가 있다. 11/19 P430 24장에서도 RF-DETR을 점검했다. | ALT-04는 동일 P430 학습 목록에 맞춘 대안 아키텍처와 배포 비용을 비교한다. 기존 모델 로딩과 평가 코드부터 재사용한다. |
| 11/22 통합 실험에서 일반 조도·채도 증강, 음성·소형 재표집을 비교했다. 조도·채도 변형의 소형 TP는 1차 9/167, 2차 0/316이었다. | ALT-05는 원본 촬영에서 측정한 열화 조건을 외부 train에 적용한다. ALT-11은 같은 크롭·샘플의 학습 손실만 바꾼다. |
| OWLv2가 2차 1,088장에 419개 초안 박스를 제안했고, Grounding DINO도 검토했다. B4-G/VG 및 sidecar는 합성 자료로 검증했다. | ALT-08은 같은 검수 예산에서 추가로 확인한 오류와 검수 시간을 본다. ALT-10은 실제 관계 정답으로 공유 백본의 효과를 측정한다. |

[P430 대안 비교][alt-prev] · [기성 모델 공통 평가][pretrained] · [외부 CCTV 조합][view-gain] · [통합 학습 결과][integrated] · [2차 검수][second] · [Holding 규격][hoi]

### 장비·자료의 확인 범위

- 11/26 18시경 KST에 PC11~14를 SSH로 읽기 전용 조회했다. 네 대 모두 RTX 3060 12,288 MiB, 드라이버 610.88, Python 3.12.4, PyTorch 2.6.0+cu124, Ultralytics 8.4.152, `torch.cuda.is_available()=True`였다. GPU 사용률은 조회 순간 모두 0%. PC11/12/13/14의 사용 VRAM은 810/513/541/0 MiB, C: 여유 공간은 178.1/154.2/128.3/125.7 GiB였다. PC13에는 기존 `p430_queue` 관련 Python 프로세스 4개가 있었다. 기존 운영 큐의 예약과 다음 작업을 확인한 후 슬롯을 받는다. 기존 실사 12 epoch 네 작업 완료는 11/25 기록과 PC13 결과의 `COMPLETED`에서 확인했다. [CUDA 인계][cuda] · [학습 큐][queue] · [완료 결과][p430-result]
- 연구실 GPU **물리 ID 0~5 전부 사용 승인**. RTX 3080 #0·5(각 10 GiB), RTX 3090 #1·2(각 24 GiB), GTX 1080 Ti #3·4(각 11 GiB)에서 CUDA NMS와 YOLO26n FP32 합성 학습 단계를 한 장씩 검증했다. 벤치마크 환경은 CPython 3.12.16, PyTorch 2.6.0+cu124, torchvision 0.21.0+cu124, Ultralytics 8.4.152다. 실데이터 안정 배치와 서버 동시 부하의 검증은 남아 있다. 접속·점유·전원·냉각은 실행 직전에 확인한다. [연구실 GPU 운영 가이드][lab-gpu] · [합성 벤치마크][gpu-benchmark]
- PC13의 11/17·11/19 개발 원본 `incoming/source.mp4`의 SHA-256을 대조했다. 공통 환경의 OpenCV 4.11.0/FFmpeg로 각각 첫 연속 6프레임을 읽었다. 두 영상 모두 약 25.003fps로 표시됐고 상대시각은 0·25·65·105·145·185ms였다. 2차는 3840×2160 HEVC, 1087.451초·27,190프레임 디코딩 이력이 있다. 현재 기본 경로에 `ffprobe`, 공통 `.venv-ml`에 PyAV는 없었다. 연속 실험 전 이전 디코딩 환경 또는 별도 환경에서 전체 구간 PTS·라벨 시각을 대조한다. 1 FPS 프레임은 기존 박스 성능 재현에 사용한다. 사건·Holding 정답 준비는 남아 있다. [1차 원본 기록][first] · [2차 원본·NVDEC 기록][second] · [사건 라벨 규격][event]
- 11/28 노트북에서 해시가 동일한 두 원본의 전체 패킷 PTS와 승인 개발 주석 585장의 시간을 대조했다. 승인 튜닝 298장에서 현재 및 직전 40·80 ms를 실제 디코딩했고, 원래 타일 입력과 같은 중앙 크롭을 검증했다. 수동 사건·Holding 정답의 승인 상태는 그대로다. [후속 PTS 및 Orin 결과](../reports/training/p430-autonomous-2026-11-27/report.md#승인-개발-원본-pts와-인과적-세-프레임-입력)
- Orin Nano 약 8GB·25W, 실제 보드 L4T 39.2.0 native의 이전 CUDA·파일·카메라 시범 검증이 있다. 계획 환경은 JetPack 7.2.1/L4T 39.2.1이다. 개발 tune 프레임 24장에 기존 가중치를 적용한 knife 처리 p95는 전체 960 52.4ms, 6타일 640 156.5ms였다. 카메라, 사람 검출, 사건 판정과 GPIO를 포함한 D1 실측은 남아 있다. 보드의 설치 상태를 기준으로 측정한다. [검증 기록][verify] · [P430 처리 시간][p430-result] · [NVIDIA JetPack Archive](https://developer.nvidia.com/embedded/jetpack-archive)

## 3. 데이터 계보와 평가 분할

| 분할 | 구성과 용도 |
| --- | --- |
| 과거 수치 재현 | PC13의 동일 `plan.json`과 1,901장 중앙 크롭 매니페스트 사용. train 1,154, tune 298, dev-check 287, 경계 완충 162. 같은 두 원본을 시간 차단한 이력은 **개발 재현 및 탐색**으로 표시한다. 이때 이미 고른 D1과 임계값으로 기존 수치와 예측을 대조한다. |
| Track B 신규 학습·튜닝·교차 검증 | 관련 촬영 묶음·원본 영상 SHA를 그룹 키로 삼고 프레임·타일·SR·pseudo-label·배경 샘플·SSL clip을 부모 그룹에 귀속한다. 같은 사건의 동시 촬영, 재인코딩·편집 파생본과 근접 중복은 같은 그룹으로 묶는다. 원본 그룹은 한 fold에서 train/tune/dev-check 중 하나에만 속한다. |
| P430 원본 홀드아웃 | 11/17→11/19 및 역방향 두 fold를 제안한다. tune은 평가 원본과 독립된 승인 개발 그룹을 사용한다. 목표 CCTV tune 그룹을 확보할 수 없으면 별도 승인 외부 개발 그룹에서 운영점을 정하고 도메인 차이를 명시한다. 그래도 독립 tune이 성립하지 않으면 사전 고정된 설정의 탐색 결과만 보고한다. D1은 두 원본을 이미 봤으므로 이 표의 엄격 평가에서는 **평가 원본 미노출로 확인된 초기 가중치에서 양쪽 대조군을 같은 fold로 학습**한다. D1은 역사적 운용 참고치로 병기한다. |
| 개발 학습 자료 | 11/20 검수 인계 1,901장 매니페스트 SHA-256 `f7b49693358f2c3ce7221fa49a3efd9a713b2a2d7c8fcb30a8805ef508e7e90d` PC13에서 일치 확인. 이전 승인 외부 CCTV 1,135장·M2 11,884장 중 fold와 반입 조건을 통과한 자료를 사용한다. 기존 50/30/20 추출 비중은 자격을 통과한 자료로 재현 가능한 경우에 적용하며 실제 표본 수·업데이트를 기록한다. |
| 11/24 독립 최종 영상 | 현재까지 학습·튜닝에 사용하지 않았다. 개발 PC·train/tune 입력 허용 목록에서 제외한다. 학습·SSL·증류·Background Memory·임계값·선택·하이퍼파라미터·개선용 오류 분석에 사용하지 않는다. 최종 평가 담당만 편집본·원본 계보와 정답을 제한 보관하고, 개발 환경에는 차단 확인용 식별자·해시만 제공한다. 동결 뒤 사전 등록된 후보만 1회 최종 평가한다. |

동일성 검사는 source/session/take·원본/이미지/라벨 해시·시간 구간·좌표·중복·명시적 음성·출처별 class map을 비교한다. `knife=0`은 P430 학습용 매핑이다. 외부 모델의 class ID는 모델별 매핑표를 써서 canonical `knife`로 변환한다. 중앙 검수 범위가 명시된 1,184장과 기존 범위 기록이 없는 717장은 별도 민감도 표에 남긴다. 중앙 밖에서 주석이 불완전한 영역은 확인된 음성에서 제외한다. 자료 준비는 1·2차와 승인 외부 데이터로 수행한다. [검수 인계][handoff] · [데이터 계획][model-data] · [데이터 보호 규칙][p430-result]

연속 실험은 원본 PTS/timebase, frame index, 화각과 좌표 이동을 보존한다. 기존 사건 라벨 작업 구간은 11/17 tune 200–340초·dev-check 571–736초, 11/19 tune 206–381초·dev-check 694–838초다. 이는 과거 개발 시간 차단 재현용이며, 그룹 홀드아웃에서는 원본에 배정된 역할을 따른다. 샘플 간 누락·decode 오류를 표시하고 clip 경계에서 기억과 상태를 초기화한다. 구간을 넘는 사건은 잘라서 두 분할에 넣지 않는다. 같은 PTS의 sparse bbox GT와 연속 사건 GT를 각각 연결하며, 시간축 정합을 먼저 확인한다. [P430 수동 라벨 구간][p430-result] · [사건 평가 프로토콜][event]

## 4. 공통 검증 방법과 통과 기준

아래 수치는 **연구 착수 전 합의할 제안 기준**이다. 하드웨어 운영 요구와 표본 수를 확인한 뒤 첫 변형의 dev-check 결과를 보기 전에 고정한다.

| 검증 | 비교·통과 기준 |
| --- | --- |
| 기준 재현 `TB-BASE-00` | D1의 보존 가중치·입력·코드·정밀도·threshold로 TP 81, 소형 TP 47, FP 23, 음성 오탐 0을 재현하고 AP는 보고된 소수점 둘째 자리 퍼센트까지 대조한다. 예측 SHA가 달라지면 정렬·환경·좌표·점수·NMS 차이를 남기고 비교 영향을 해결한다. |
| **D-R** 재현율 / **D-P** 정밀도 | 두 팔 모두 동일 tune 음성 오탐 예산 `floor(0.01 × 확인된 음성 프레임 수)`으로 조정하고 threshold를 고정한다. D-R은 dev 평가에서 전체 또는 small Recall +5%p 이상, 다른 쪽 −2%p 이내, 음성 오탐률·전체 FP가 대조군 이하. D-P는 전체·small Recall 각각 −2%p 이내, 전체 FP ≥20% 감소, 음성 오탐률 증가 없음. D1 역사적 운영점 고정 표도 함께 낸다. |
| **D-L** 위치 / **D-C** 편차 | D-L은 AP50–95 +3%p 이상, 전체·small Recall 각각 −2%p 이내, 음성 오탐률·전체 FP가 대조군 이하. D-C는 사전 지정한 실제 열화/혼동 구간의 Recall +5%p 이상 또는 FP ≥20% 감소, 전체·small Recall −2%p 이내 및 음성 오탐률 증가 없음. 희귀 조건은 수량과 사례를 별도 제시한다. |
| **E** 사건 | 동일 사람 detector, sample clock, 공간·K/N·FSM·rearm·매칭 policy로 평가한다. Event F1 +0.05 또는 missed events 감소와 event recall 유지, 혹은 recall 유지 상태에서 duplicate/오경보율 ≥20% 감소를 진행 조건으로 제안한다. 모든 경우 Event Precision·Recall −2%p 이내, False Alerts/hour 대조군 이하, 공통으로 맞힌 사건의 p95 지연 증가는 샘플 1주기 이내. 절대 시간과 개수도 함께 제시한다. |
| **L** 라벨 / **H** 관계 | L은 같은 검수 예산에서 확인된 신규/수정 정답 수 또는 검수 분당 수율 +20% 이상, 무작위 재감사 오류율 증가 없음. detector 이득은 같은 image ID의 원래/수정 라벨로 재학습하는 별도 팔에서 검증한다. H는 pair F1 +0.05 또는 동일 pair F1(−0.02 이내)에서 Orin p95 개선 ≥10%, detector 전체·small Recall −2%p 이내 및 사건 E 보호 조건 유지. |
| **J** 배포 | 동일 보드·전원·카메라 profile·목표 sample rate로 60초 예열 후 10분×3 개발 반복, 기준과 후보를 같은 입력 순서로 대조한다. 잠정 기준은 3회 무중단, 유효 FPS ≥목표 sample rate의 95%, drop ≤5%, decode 포함 처리 p95 ≤샘플 주기, 안정화 이후 지연·queue·공유 RAM이 누적 증가하지 않을 것. 유리한 detector/사건 지표와 J를 함께 충족하면 Edge 후보로 채택한다. |

박스는 동일 canonical 좌표·일대일 IoU 0.50으로 Precision, Recall, FP boxes, 확인 음성 이미지 FP율을 산출한다. AP50/AP50–95는 임계값을 적용하기 전의 동일 후보 규약과 COCO evaluator로 산출한다. `small` 역사값은 중앙 크롭을 960×540으로 환산한 박스 짧은 변 `<16px` 조건이며, 기존 작은 프레임 집계는 각 양성 1박스인 데이터에서 일치한다. 신규 다중 박스는 GT별로 계산하고 COCO 면적 기반 `AP_s`는 보조 지표로 제출한다. 전체 화면·정지 소지·작은/그 외·경계·조명·양성 내 FP·확인 음성은 분모와 함께 본다. [박스 평가 코드][p430-code] · [공통 COCO 비교][common-code]

사건은 조절용 자료에서 고정한 early/late 허용창으로 CONFIRMED와 GT 사건을 일대일 대응한다. Event Precision·Recall·F1, False Alerts/hour(평가 가능한 영상 시간, 중복 FP 포함), missed·duplicate·background alerts와 지연 p50/p95/최대·매칭 수를 기록한다. 공통으로 맞힌 사건에서의 비교와 전체 매칭 사건 분포를 함께 본다. 배포는 `Effective FPS`, 모델 추론·전체 처리 지연 p50/p95, GPU 할당/예약 메모리·보드 공유 RAM·온도·drop·queue, 카메라/오프라인 입력, 전원·런타임 호환을 기록한다. Replay 시간은 원본 PTS 기준 판단 지연이며 실기기 GPIO 경로의 지연은 별도 계측한다. [사건 평가 프로토콜][event] · [Orin 검증][verify]

동일 영상의 기준/후보를 짝지어 절대 개수·%p·세션별 결과를 표기한다. 독립 그룹이 충분할 때 그룹 단위 paired bootstrap 95% 구간을 제공한다. 그룹이 두 개뿐인 경우 두 fold의 범위와 방향을 공개한다. 탐색 기준을 넘더라도 한 장면에 의존하거나 불확실성이 큰 결과는 후속 확인으로 보내고, 미달·유해 결과와 원인이 불충분한 결과를 구분해 보존한다. 사건이나 음성의 수가 0이면 비율의 정의 가능 여부와 관측 시간을 기록한다.

## 5. 후보별 근거와 실험 매트릭스

각 묶음의 00은 아래 명시한 대조군이다. 추론 실험은 기본적으로 D1 가중치·타일·정밀도를 고정한다. 학습 실험은 두 팔의 원본 ID, train/tune/dev-check, 초기화 출처, 양·음성 수, seed, 실제 optimizer update, 유효 batch와 입력 면적을 맞춘다. 아키텍처 고유 설정 때문에 같게 할 수 없는 항목은 실험 기록에 남긴다. 첫 비교는 seed 3407로 하고, 선택된 학습 팔과 대조군을 3408·3409로 다시 돌린다. 이 seed 조건은 Track B의 비교 제안이다. E와 J는 별도 통과 조건이며 아래 ‘통과’는 실험별 개발 단계 조건을 뜻한다.

### ALT-01 · Cascade Detection

- **근거와 가설.** D1의 FP 23개와 PC14의 높은 TP·FP는 후보를 후단에서 재평가할 이유가 된다. DCR은 Faster R-CNN의 어려운 오탐 크롭을 별도 분류기로 억제했다. Cascade R-CNN은 IoU가 다른 박스 회귀 단계의 참고 사례다. D1의 분류·위치·중복 오류 비중은 아직 모른다. 후단 분류 단계가 해결하는 범위를 먼저 계량한다. [DCR](https://arxiv.org/abs/1810.04002) · [Cascade R-CNN](https://openaccess.thecvf.com/content_cvpr_2018/html/Cai_Cascade_R-CNN_Delving_CVPR_2018_paper.html)
- **실험.** C00=동일 낮은 점수 후보를 가진 D1 단독과 tune 운영점. C01=동일 후보의 bbox+여백 RGB 크롭에 MobileNetV3-Small 재점수화. train은 승인된 원본 그룹에 대해 detector가 실제 생성한 후보를 쓰고 일부 GT 크롭은 별도 표기한다. GT IoU≥0.5는 위치가 유효한 양성 후보, IoU<0.2는 사람 검수 후 혼동 음성 후보로 삼는다. 중간 IoU와 label 불확실성은 진단으로 남긴다. C02=같은 classifier에서 국소 크롭에 사람 문맥 추가. GT-크롭만 학습한 팔과 score-only 대조, 후보 recall oracle을 보고한다. C01 통과 뒤에만 동일 C01 데이터·budget으로 EfficientNet/ConvNeXt/동결 DINO 특징을 비교하거나 PC14를 새 proposal 팔로 올린다.
- **통과·중단.** D-P 또는 D-R. 1차 후보가 전혀 없는 누락은 후단에서 회복할 수 없으므로 후보 oracle의 추가 TP가 D-R에 필요한 수보다 적으면 recall 실험을 멈춘다. 작은 크롭의 정보 부족, GT/예측 크롭 편차, 사람 안의 다른 물체 오탐, 프레임당 후보 수의 p95와 비용을 확인한다.

### ALT-02 · Background-Aware Detection

- **근거와 가설.** P430은 고정형이고 과거 기록은 배경 기억을 제안했다. 반복 배경 오탐이 실제 D1에서 얼마나 되는지는 미확인이다. FG-DINO는 저해상도 고정 카메라에서 전경 정보를 결합해 보행자 검출을 연구했다. 사람 크기의 전경 이득을 작고 정지한 손의 모형에 그대로 적용할 수 없다. [P430 대안 비교][alt-prev] · [FG-DINO, WACVW 2026](https://ieeexplore.ieee.org/abstract/document/11617965/) · [OpenCV MOG2](https://docs.opencv.org/4.x/db/d5c/tutorial_py_bg_subtraction.html)
- **실험.** BG00=RGB D1. BG01=같은 카메라·화각의 train 빈 장면 중앙값 배경으로 후보 주변 차분 통계와 반복 위치를 계산해 제한된 재점수화. BG02=같은 train 구간을 사용한 MOG2 초기 상태를 고정해 차분 생성 방식만 비교. 빈 장면은 ‘칼 없음’ 표기와 별개로 사람·물체·그림자 잔류를 확인한다. 정렬 실패·조도 급변에는 RGB 경로를 사용한다. 움직임 여부만으로 후보를 버리지 않는다. 통과하면 동일 trainer의 RGB+mask 단일 변경을 먼저 비교하고, 조명별 memory와 별도 backbone은 이후 한 변수씩 평가한다.
- **통과·중단.** D-P 또는 반복 배경 slice의 D-C, 정지 소지 Recall 악화 ≤2%p. 같은 구도에서 확인된 빈 train 구간이 없거나, 반복 오탐 근거가 없거나, 정지 소지 손실이 커지면 BG01/02의 효과 판정은 보류한다. 각 촬영의 화각 차이가 크면 그룹 홀드아웃에서 memory 적용 범위를 제한한다.

### ALT-03 · Multi-frame Fusion

- **근거와 가설.** 기존 점수 누적 실험의 간격은 약 1초였다. FGFA는 optical flow로 시점 사이 특징을 정렬했고, 2026년 LSTT는 작은 물체의 짧은·긴 문맥을 다뤘다. P430의 입력은 흐림과 가림, 작은 손 움직임이 함께 발생할 수 있다. 서너 프레임을 평균하면 물체 윤곽이 흐려질 수 있다. [P430 대안 비교][alt-prev] · [FGFA](https://openaccess.thecvf.com/content_iccv_2017/html/Zhu_Flow-Guided_Feature_Aggregation_ICCV_2017_paper.html) · [LSTT, 2026](https://doi.org/10.1016/j.eswa.2025.129631)
- **실험.** MF00=동일 PTS의 RGB D1. MF01=정렬 없는 과거 평균, MF02=현재로 정렬한 과거 프레임을 동일 가중치로 합성, MF03=동일 MF02에 일치도·선명도 가중만 변경. 먼저 현재 및 직전 2개 프레임(약 25fps면 총 범위 약 80ms)을 쓰며 PTS 간격·누락을 기록한다. 늘릴 근거가 있으면 5개(약 160ms), 이어서 9개(약 320ms)를 각각 비교한다. 입력 크롭·타일·K/N은 동일. clip 시작, 시각 gap, 정렬 실패에는 원본을 입력한다. 개발 영상에서 flow 오류·잔상·가림 분해를 확인한 뒤, 동일 RGB backbone의 current-only와 causal 과거 feature aggregation을 비교한다. ConvLSTM, temporal attention, video transformer는 clip 라벨과 단순 feature 기준이 마련된 후 후보로 둔다.
- **통과·중단.** D-R, 사건 적용은 E와 J. 미래 프레임을 참조하거나 현재 PTS의 GT와 맞지 않으면 비교에서 제외한다. 정렬이 작거나 짧게 보이는 양성에서 반복적으로 고스트를 만들면 feature 연구의 근거를 별도로 판단한다.

### ALT-04 · Alternative Architecture

- **근거와 가설.** 기존 RF-DETR·DEIMv2는 기성 가중치를 공통 개발 자료로 비교했다. RT-DETR은 효율적 encoder와 end-to-end 검출을, Deformable DETR은 희소한 다중 축척 attention을, RF-DETR은 백본·설계 규모별 성능과 지연을 다룬다. DEIMv2-S는 DINOv3 계열 특징을 이용한다. 공개 데이터와 데스크톱 GPU의 결과는 P430의 가려진 작은 객체와 Orin 지원을 직접 보여주지 않는다. [기성 비교][pretrained] · [RT-DETR](https://openaccess.thecvf.com/content/CVPR2024/html/Zhao_DETRs_Beat_YOLOs_on_Real-time_Object_Detection_CVPR_2024_paper.html) · [Deformable DETR](https://arxiv.org/abs/2010.04159) · [RF-DETR](https://arxiv.org/abs/2511.09554) · [DEIMv2](https://arxiv.org/abs/2509.20787)
- **실험.** AR00=고정 D1 운용 비교 + 동일 fold의 YOLO26n matched 학습 대조. AR01=기존 검증 설치와 adapter를 활용한 RF-DETR Small, AR02=RT-DETRv2 또는 DEIMv2-S 중 학습·export smoke를 통과한 계열 하나. 준비된 source와 strict checkpoint load를 우선한다. COCO 계열 시작 weight, 같은 P430·외부 부모 순서와 동일 split, YOLO와 같은 6타일 시야로 비교한다. 공통 지원 입력 크기는 최소 실험에서 맞추고, native 크기·후처리 운용 비교표도 별도로 낸다. 기존 D1 운용점과 새 팔의 같은 FPR 예산 운영점을 각각 기록한다. 한 batch 학습, 미니 평가, ONNX export smoke 뒤 초기 예산의 전 구간 또는 matched 12 epoch까지 단계적으로 올린다. 벽시계 예산과 optimizer update는 별도로 기록한다. AR03=Faster R-CNN+FPN 또는 DINO/Deformable DETR 계열의 오프라인 상한으로 하나를 선택한다. [RT-DETR 공식 구현](https://github.com/lyuwenyu/RT-DETR) · [DINO detector](https://arxiv.org/abs/2203.03605) · [Faster R-CNN 원 논문](https://arxiv.org/abs/1506.01497)
- **통과·중단.** D-R 또는 D-L. 같은 원좌표·GT·AP와 모델별 class map, postprocessing 후보 상한·정밀도를 기록한다. matched P430 결과가 불리해도 기성 모델 순위로 올리지 않는다. J를 통과하면 Edge 후보, 미달이면 오프라인 benchmark/교사 후보로 성능을 남긴다. 교차 아키텍처 증류는 Track A의 별도 후속 과제다.

### ALT-05 · CCTV Degradation Modeling

- **근거와 가설.** 기존 조도·채도 증강 효과는 촬영별로 달랐고, 2차 HEVC 원본이 확인됐다. Michaelis 등의 corruption 기준은 깨끗한 영상과 열화 조건의 성능을 함께 비교했다. JPEG·합성 blur가 실제 HEVC, 노출과 센서 신호를 그대로 재현한다고 가정하지 않는다. [통합 학습 결과][integrated] · [Common Corruptions](https://arxiv.org/abs/1907.07484)
- **실험.** DG00=동일 초기 weight·이미지 목록의 기존 recipe. DG01=축소/복원, DG02=실제 연속 자료가 있는 승인 train clip의 HEVC 재인코딩 또는 이미지 전용 자료의 압축 proxy, DG03=motion blur, DG04=노이즈, DG05=노출·명암. train P430에서 짧은 변 분포·명암·블러·블록 신호를 요약한 뒤 해당 열화가 확인되는 1~2개만 먼저 실행한다. 외부 train의 같은 부모·class·샘플링 분량을 유지하고 변환·라벨 valid 여부를 함께 기록한다. 외부 자료를 섞은 비율과 기존 색상 증강을 고정한다. 변환에 의해 GT를 확인할 수 없는 표본은 양쪽 팔에서 같은 규칙으로 처리한다. 단일 변환이 통과하면 DG06에 조합한다.
- **통과·중단.** 실제 P430의 사전 지정 조건에서 D-C 또는 D-R. 합성 열화 지표의 상승만으로 진행하지 않는다. 깨끗한 검증군 악화와 hard-negative 증가, 열화로 생긴 라벨 정보 손실을 확인한다.

### ALT-06 · Tracking-Assisted Detection

- **근거와 가설.** 기존 K-of-N은 source-level 근거를 누적한다. 이전 점수 누적은 같은 ID를 유지한 실험이 아니다. ByteTrack은 낮은 점수 박스를 기존 track에 연관시켜 끊김을 줄였고 주된 benchmark는 다중 보행자 추적이다. P430에서 좁은 칼 박스의 낮은 IoU, 사람 사이 교차, 짧은 노출 때문에 오연관 가능성이 있다. [MVP 시간 판단][mvp] · [ByteTrack 논문](https://www.ecva.net/papers/eccv_2022/papers_ECCV/papers/136820001.pdf)
- **실험.** TR00=동일 person/knife 저점수 후보 cache + 현재 B3. TR01=IoU/시간 간격과 단순 Kalman 예측을 이용해 연관한 **관측 후보**만 evidence에 넣는다. TR02=같은 후보에서 ByteTrack 방식의 낮은 점수 연관만 변경. track ID, score, 관측 유무, ID switch와 경계 reset을 sidecar로 보관하고 기존 replay에 전달 가능한 현재 시점 행만 투영한다. 먼저 knife box를 대상으로 하며, person continuity·appearance·관측 없는 프레임의 track 유지 evidence는 독립 후속 팔이다. B4 비교용 sidecar는 입력 hash가 바뀔 때마다 같은 classifier로 다시 생성한다.
- **통과·중단.** E. 누락·중복과 ID 오연관을 함께 본다. 투영된 track 좌표는 detector raw TP로 합산하지 않는다. 확인된 관측이 끊긴 구간에서 경보가 지속되거나 후보 연결만 개선되고 사건이 악화하면 중단한다. ID 주석이 없으면 사건 결과와 제한된 수동 ID 진단까지만 해석한다.

### ALT-07 · Task-Driven Super Resolution

- **근거와 가설.** 타일은 중앙 크롭 960 대비 모델 앞의 이론상 짧은 변 중앙값을 8.3→13.8px로 키웠다. 이는 원본 영상에 들어 있던 픽셀의 사용 방식 차이다. TDSR은 검출 손실을 SR에 반영해 인위적으로 낮춘 COCO/VOC 조건을 평가했다. P430의 센서·압축으로 손실된 형태가 복원된다는 보장은 없다. [타일 근거][p430-result] · [TDSR](https://arxiv.org/abs/1803.11316) · [EDSR](https://arxiv.org/abs/1707.02921) · [Real-ESRGAN](https://arxiv.org/abs/2107.10833) · [SwinIR](https://arxiv.org/abs/2108.10257)
- **실험.** SR00=원본 D1, SR01=bicubic, SR02=Lanczos, SR03=가급적 비생성 방식 EDSR. 첫 파일럿은 동일 시야의 원본 타일을 2× 축소한 입력을 각 복원 방법에 주고 D1의 같은 letterbox와 좌표 변환을 적용한다. 이 비교는 복원 방식 간 진단이며, 실제 P430 native 영상의 후보는 동일 입력 해상도·시야·운영점에서 별도 측정한다. 일반 크기 확대의 Track A 결과를 재사용한다. 비생성 방식이 기대 수준을 넘으면 사진 복원 후보 SwinIR/Real-ESRGAN을 별도 비교하며, 실제 검출 이득과 가짜 윤곽을 사람이 재점검한다. TDSR은 같은 backbone에서 reconstruction-only vs reconstruction+detector loss를 고정 pair 목록으로 비교한다. 다중 프레임 SR은 ALT-03 정렬 확인 뒤 별도.
- **통과·중단.** 같은 픽셀 예산의 보간과 원본을 대상으로 D-R 또는 D-L, 음성 FP 증가 없음. PSNR/SSIM은 진단으로만 남긴다. 합성 윤곽의 확인된 새 FP 또는 J 미달이 반복되면 실시간 후보에서 내리고 오프라인 결과를 남긴다.

### ALT-08 · Foundation Model Annotation

- **근거와 가설.** P430에서는 OWLv2·Grounding DINO를 이미 사용해 박스 초안을 냈다. Grounding DINO·OWLv2는 개방 어휘 후보를, SAM 2는 box prompt 기반 마스크·시간 추적을 제공한다. 작은 박스에서 두 모델의 동의도 라벨 정답을 보증하지 않는다. [P430 초안 작업][second] · [Grounding DINO](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/06319.pdf) · [OWLv2](https://arxiv.org/abs/2306.09683) · [SAM 2](https://arxiv.org/abs/2408.00714)
- **실험.** FM00=동일 train 그룹의 기존 OWLv2 보조/일반 검수. FM01=OWLv2·Grounding DINO·기존 모델 간 불일치와 D1의 승인 train 후보를 묶어 우선 검수하되, 같은 이미지 수·검수 시간의 무작위 대조군과 블라인드 재감사 표본을 포함한다. FM02=같은 후보에 SAM 2의 box prompt를 붙여 경계 수정 시간을 비교한다. 필요할 때만 승인된 환경에서 DINOv2/3 유사 크롭 묶음이나 SAM 3를 후보 도구로 검토한다. 검수에는 누락·박스 수정·명시적 음성·보류·시간을 남긴다. 새 팩과 매니페스트를 별도 생성하고 기존 검수 결과의 버전 변경은 정식 승인 흐름을 따른다. [SAM 3 공식 구현](https://github.com/facebookresearch/sam3)
- **통과·중단.** L, 채택한 라벨의 detector 실험은 D-R/D-L. 여러 모델이 함께 놓치는 표본을 찾기 위해 모델이 제안하지 않은 검수 표본을 유지한다. 작은 물체의 마스크 불안정, 모델별 prompt 민감도, 사용 조건과 기존 검수자 부담을 측정한다.

### ALT-09 · Self-supervised Learning

- **근거와 가설.** 두 촬영에서 기존 혼합/통합 학습의 향상이 일관되지 않았다. MAE와 VideoMAE는 각각 마스킹으로 이미지·영상 표현을 학습하고, DINOv3는 대규모 이미지 사전학습의 동결 특징 기준을 제공한다. 대규모 사전학습과 두 P430 클립의 추가 적응에는 유효 장면 수 차이가 크다. [통합 결과][integrated] · [MAE](https://openaccess.thecvf.com/content/CVPR2022/html/He_Masked_Autoencoders_Are_Scalable_Vision_Learners_CVPR_2022_paper.html) · [VideoMAE](https://proceedings.neurips.cc/paper_files/paper/2022/hash/416f9cb3276121c42eebb86352a4354a-Abstract.html) · [DINOv3](https://arxiv.org/abs/2508.10104)
- **실험.** SS00=같은 백본·head·supervised recipe와 공개 초기값. SS01=고정 공개 시각 특징의 선형 probe로 train→개발 전이의 근거 확인. SS02=같은 초기값에 승인 train clip으로 MAE 또는 DINO 계열 추가 적응 후 SS00과 같은 labeled head·예산을 적용한다. SS01은 표현 진단으로 기록한다. SS02의 추가 데이터·compute 효과를 분리할 때는 같은 수의 승인 외부 train 장면에서 같은 SSL 예산을 쓴 대조군을 추가한다. 시간 중복을 제거하고 실제 clip/sessions 수를 기록한다. VideoMAE 또는 SimCLR은 이미지 경로와 동일한 목적으로 별개 실행한다. [SimCLR](https://arxiv.org/abs/2002.05709)
- **통과·중단.** D-R 또는 D-C가 원본 단위에서 확인되어야 한다. 학습 복원 손실·probe 상승은 단독 증거로 부족하다. 두 세션의 유사 샘플만으로 배경 특징이 강해지거나, 원본 그룹과 사전학습 데이터의 관계를 확인할 수 없으면 해당 실험을 탐색으로 제한한다.

### ALT-10 · Multi-task Learning

- **근거와 가설.** 기존 B4-G/VG는 검출과 소지 분류를 분리한다. HOI Transformer는 전역 사람–물체 관계를 함께 학습했다. P430에서는 매우 작은 모형, 가까운 비소지 사례, 불확실한 관계가 주요 제약이다. 착수는 train 및 평가 원본의 사람이 검수한 관계 정답 확보에 달려 있다. [Holding 규격][hoi] · [HOI Transformer](https://openaccess.thecvf.com/content/CVPR2021/html/Zou_End-to-End_Human_Object_Interaction_Detection_With_HOI_Transformer_CVPR_2021_paper.html)
- **실험.** MT00=detector-only(관계 손실 λ=0)와 독립 B4-VG. MT01=같은 detector 백본의 특징에서 GT/후보 사람–칼 영역의 특징을 뽑아 Holding head를 붙인다. `L_det + λ L_holding`, 초기 파일럿 λ=0.25 한 점을 비교하고 유효 관계 정답이 없는 프레임은 관계 loss에서 제외한다. 관계 head만 학습한 팔을 두어 공유 백본 업데이트 영향을 분리한다. GT-box와 predicted-box의 pair 점수를 따로 보고하며, label은 Holding/Not Holding, uncertain 제외 규약을 따른다. 통합 실시간 비교에서는 사람 검출 경로를 고정한 실험을 먼저 수행한다.
- **통과·중단.** H, 통합 후보는 E·J도 확인한다. 소지와 인접을 구분할 label 또는 독립 그룹이 부족하면 준비 단계에 둔다. 공동 학습에서 작은 칼 recall 감소나 다중 인원 오귀속이 늘면 독립 B4를 대조군으로 보존한다.

### ALT-11 · Contrastive Learning

- **근거와 가설.** 첨부안은 후보 표에 ALT-11을 포함하고 세부 실험은 정하지 않았다. 일반 혼동 음성 재표집은 세션을 넘어 일관된 이득을 내지 못했다. SupCon은 같은 라벨 임베딩의 유사도와 다른 라벨 분리를 학습한다. 분류 benchmark의 가시성·샘플 규모가 이 프로젝트의 작은 크롭과 다르다. [통합 결과][integrated] · [Supervised Contrastive Learning](https://papers.neurips.cc/paper_files/paper/2020/hash/d89a66c7c80a29b1bdbab0f2a1a94af8-Abstract.html)
- **실험.** CL00=ALT-01 동일 크롭 목록·backbone·head·sampler의 BCE. CL01=BCE+SupCon을 같은 총 업데이트로 학습한다. 검수된 모형과 휴대폰·리모컨·배경 후보 등을 clip/session 균형으로 샘플링하고 라벨이 불확실한 pair는 제외한다. 대비 손실 가중치·온도는 사전 설정 한 점으로 시작한다. 동일 크롭 선정→동일 loss baseline을 확보한 뒤에만 다른 batch 구성이나 detector feature 적용을 수행한다.
- **통과·중단.** 확인된 혼동 유형의 D-C 또는 전체 D-P, 독립 그룹에서 같은 방향. 임베딩 분리나 t-SNE의 외관은 참고로만 남긴다. 인접 프레임 반복과 소품·배경의 상관이 이득을 설명하면 중단한다.

### ALT-12 · Classical Vision Fusion

- **근거와 가설.** 기존 조도 증강의 결과가 조건별로 달라서, 저조도·압축 구간의 검출 비용을 작은 대조 실험으로 확인할 가치가 있다. CLAHE는 지역 명암을, Canny는 경계를, bilateral은 경계를 고려한 평활화를 다룬다. 이미 흐려진 칼을 복원할 수 있다는 근거는 없고, 격자나 압축 잡음을 강조할 수 있다. [통합 결과][integrated] · [OpenCV CLAHE](https://docs.opencv.org/4.x/d6/db6/classcv_1_1CLAHE.html) · [Canny 원 논문](https://pubmed.ncbi.nlm.nih.gov/21869365/) · [OpenCV 필터](https://docs.opencv.org/4.x/d4/d86/group__imgproc__filter.html)
- **실험.** CV00=동일 RGB D1. CV01=L 채널 CLAHE(파일럿 clip limit 2.0, 격자 8×8), CV02=고정 gamma, CV03=bilateral 중 사전 정의한 slice에 해당하는 하나씩 비교한다. 한 팔에서 전처리를 하나만 쓴다. unsharp·Sobel/Canny는 경계 손실로 진단된 경우, wavelet·FFT/DCT는 실제 잡음/주파수 증거가 있을 때 후속으로 예약한다. RGB+edge dual stream은 정적인 전처리의 이득을 확인한 후 동일 가중치 초기화의 RGB 모델과 학습 비교한다.
- **통과·중단.** D-C 또는 D-R에 J를 확인한다. 낮 장면이나 정지한 양성을 손상시키면 범용 경로로 진행하지 않는다. 특정 운영 구간에서만 유효하면 적용 조건과 원본 경로 전환을 별도 검증한다.

### 추가 제안 · ALT-13 위치·크기별 점수 보정

CA00=기존 전역 threshold와 동일 low-score 후보, CA01=tune 원본 그룹에서만 fit한 전역 logistic, CA02=같은 logistic에 박스 크기와 내부 타일 경계 거리 추가. 박스 좌표·후보 집합·가중치를 유지한다. 현 결과에서 작은 객체와 타일 경계의 점수 편향은 미확인이다. confidence와 오류가 위치·크기에 따라 다르게 나타나는 경우에 검증할 가치가 있다. D-P/D-R을 우선 지표로, reliability plot과 Brier score를 보조로 쓴다. 두 개발 원본으로 위치 효과가 촬영 고유 배경인지 판단하기 어려우면 별도 slice 결과만 보존한다. CA01은 ALT-01/02의 재점수 비교에 재사용할 수 있다. [Multivariate Confidence Calibration](https://openaccess.thecvf.com/content_CVPRW_2020/html/w20/Kuppers_Multivariate_Confidence_Calibration_for_Object_Detection_CVPRW_2020_paper.html)

## 6. 단계, 의존성, 자원 예약

| 단계 | 작업과 병렬 실행 | 종료 증거 |
| --- | --- | --- |
| 0 · 기반 | 개발2의 공통 D1 가중치·낮은 점수 후보 캐시를 인계받고 해시와 승인 입력 계보를 확인한다. 같은 가중치 대조군을 재사용해 `TB-BASE-00`을 평가한다. 동시에 CPU에서 원본 PTS와 사건·관계 라벨 범위를 정한다. | `TB-BASE-00` 결과, 공통 캐시·입력 매니페스트, GPU 예약표, 동결 전 지표·정책 |
| 1 · 단일 변수 파일럿 | 저점수 후보 캐시를 읽는 ALT-01·02·13을 병렬 준비. RGB 전처리·보간 ALT-12·07은 동일 샘플로 CPU 준비 후 빈 GPU에서 추론. ALT-04 공식 런타임은 별도 환경에서 한 배치·내보내기부터 시작. 후보 재평가를 기다리는 동안 ALT-08 표본 및 ALT-05 열화 통계를 만든다. | 각 파일럿의 공통 조건·대조·실패 기록, 비용표와 그룹 교차 검증 대상 |
| 2 · 원본·학습 | PTS와 동일 sample clock이 준비되면 ALT-03과 06을 독립 비교. 연속 GT·관계 GT 작업은 그대로 병행한다. ALT-04·05의 학습 팔은 GPU 예약 후 시작. ALT-08의 추가 검수 결과가 나오면 동일 ID로 원본/수정 라벨 재학습. | 원본 단위 결과, 실제 사건 결과(정답 확보 시), 이력/추론 artifact, 각 시험의 통과 여부 |
| 3 · 조건부 확장 | ALT-11은 검수된 ALT-01 크롭이 필요. ALT-09 이미지 SSL은 허용 clip과 독립 동일 백본 대조군부터, VideoMAE는 PTS와 그룹 검사를 마친 후. ALT-10은 실제 Holding GT와 독립 B4 대조가 필요. Task-driven·multi-frame SR은 ALT-07의 보간 대조·ALT-03의 정렬 검증 뒤 필요 시 배정. | 동일 조건의 ablation, 재현 seed, 미달 원인. 다음 단계는 이득을 확인한 방법만 진입 |
| 4 · 통합과 동결 | Track B의 최선 단일 후보를 D1과 Track A 승자 각각에 적용해 2×2 비교. 두 B 기술을 묶으면 기준/각 단독/결합 4개 팔을 비교한다. Track C와 개발 Orin 시험 및 공통 B0~B4 검증 일정을 조정한다. | 박스·사건 지표, Orin J 결과, 개별/결합 영향, 후보·임계값·보호 목록의 freeze 문서 |
| 5 · 독립 평가 | 11/24 자료가 아직 미개봉 상태이며 사전 등록 후보와 평가 범위를 확정한 경우에만 1회 사용한다. 준비 시점이 제출 동결 뒤라면 Track B는 개발 검증 단계로 남긴다. 이미 본 제출에 사용한 영상을 새 후보 선택에 다시 사용하지 않는다. | 동결 SHA, 모드별 제출 결과 및 사용 이력. 미실행이면 제한 사유와 개발 범위 명시 |

처음부터 복합 모델을 만들지 않는다. 타일은 D1에 포함된 공통 입력이다. 배경과 시간 결합은 둘 다 움직임 신호를 사용하므로 개별 이득의 상쇄를 확인한다. Tracking+HOI는 독립 B4 대조가 준비된 뒤에만 비교한다. 오프라인 대형 detector나 teacher는 배포 후보 표와 별도로 보고한다.

### GPU 배정 제안

| 자원 | 예약이 확인된 뒤 첫 사용 | 후속·대기 시 진행 |
| --- | --- | --- |
| 개발 PC CPU | 매니페스트·해시·좌표 대조, 승인된 연속 원본 처리 준비, NumPy/OpenCV 전처리·리포트, cache replay | GT·오류 유형 검수, 분할과 자동 평가. 원본 해시는 권한 있는 PC13에서 점검 |
| PC13 RTX 3060 | 개발2에서 전달할 D1 공통 캐시와 운영점 확인. 기존 결과로 충족되지 않는 부분만 적합한 빈 슬롯에서 재현 | 사람 cache·비교 수집·평가. 검수 운영과 Track A 작업의 점유를 확인 |
| PC14 RTX 3060 | Track A 오류 분석·검수 준비 이후 ALT-01 MobileNet 크롭 학습, ALT-11 재사용 | ALT-02·12 짧은 추론. PC14 고재현율 weight의 사용은 승인된 별도 팔 |
| PC11/12 RTX 3060 | Track A seed 반복 종료·슬롯 인계 이후 ALT-05 일반/열화 학습을 나눠 실행 | 공통 환경으로 이식 가능한 ALT-04 Small smoke 또는 ALT-03 cached 비교 |
| 연구실 RTX 3080 ID 0·5, 각 10 GiB | Track A n/s 우선. 해당 슬롯에 대기 중인 Track A 작업이 없으면 RF-DETR Small·RT-DETRv2 또는 열화 대조 | 10 GiB에서 실데이터 microbatch·peak VRAM 검증 후 비교 팔의 유효 batch를 맞춤 |
| 연구실 RTX 3090 ID 1·2, 각 24 GiB | Track A m·P2·고해상도 우선. 적합한 대기 작업이 없으면 ALT-04 오프라인 detector, ALT-09/10 확장 | 필요한 VRAM을 확인해 단일 GPU부터 사용. DDP는 필요 시 별도 비교 |
| 연구실 GTX 1080 Ti ID 3·4, 각 11 GiB | 적합한 Track A 대기 작업이 없고 부하 상한에 여유가 있을 때 FP32 캐시·경량 추론 또는 평가 | Pascal에서 해당 모델·의존성의 실제 동작과 완료 시간 이득을 확인 |
| Jetson Orin Nano | D1 및 개발 검증 통과 후보 1~2개, 동일 profile에 하나씩 | 파일 입력 → 개발 카메라 stream → B3/B4·경보 경로. 이전 시범 결과와 현재 실측 구분 |

Track B는 **적합한 Track A 대기 작업이 없는 슬롯**을 사용한다. 실행 직전 물리 UUID, 현재 작업·VRAM, 저장 공간·데이터 접근 범위와 전원 회로·PSU·냉각 여유를 확인한다. 단일 카드의 합성 통과 배치는 해당 P430 작업의 안정 배치와 구분한다. 연구실 서버는 통합 자원 계획의 검증된 동시 부하 상한을 따르고, 상한이 확정되기 전에는 한 작업씩 실행한다. 새 런타임은 개발 입력으로 forward/backward, checkpoint save/reload, 평가 및 필요 시 export를 점검한다. 연구실 반입은 PC13 → Windows → 서버의 승인된 읽기 전용 릴리스를 사용한다. 전송 전후 해시를 대조하고 Windows 절대 경로가 있는 목록은 Linux용으로 다시 만든다. [통합 자원 계획][resources] · [연구실 GPU 운영 가이드][lab-gpu]

## 7. 저장소 진입점과 실행 기록

1. **작업 공간.** 연구 착수 시 clean origin/main을 기준으로 예를 들어 `codex/p430-track-b`와 형제 worktree `../etr-p430-track-b`를 생성한다. 기준 commit·Track A 공통 코드 의존성을 기록하고, 공통 코드는 두 트랙이 변경 계획을 맞춘 후 한 쪽에서만 검토 단위로 변경한다. `runs/track-b/<TB-ID>/<attempt>/`와 `data/work/track-b/<dataset-id>/`를 사용한다. 가중치·데이터는 읽기 전용 참조하거나 보호된 위치에 새 복사본을 만들고 SHA를 확인한다. 열화·크롭·라벨 변경은 매니페스트 버전만 추가한다.
2. **박스 경로.** `tools/run_p430_site.py`의 `regions`, `tile_predictions` 및 `p430_evaluation.py`의 `score_predictions`를 먼저 재사용한다. 현재 `run_p430_site.py evaluate`는 실패 복구용 기존 실행 경로에 의존하므로 완료된 D1 폴더에는 재실행하지 않는다. 새 experiment 실행기에서 동일 함수와 입력 검사를 불러 새 폴더에 예측 JSONL·튜닝 결과를 쓴다. AR 계열은 `tools/run_detector_comparison.py`의 canonical adapter와 공통 COCO 평가를 재사용한다. `CanonicalDetector` 및 `MappedDetector` 경계에 연결하는 작업은 실시간 후보에 한해 후속으로 진행한다. [타일 실행기][site-code] · [대안 detector 비교기][comparison-tool] · [detector 계약][detector-code]
3. **Replay 경로.** 이미지별 SHA를 source ID로 쓴 박스 평가 JSONL은 사건 replay 입력과 형태가 다르다. 승인 개발 영상의 PTS에 맞춰 한 source별 오름차순 `frame_index`, `timestamp_s`, 실제 `status`, 사람·칼의 동일 좌표계 `bbox_xyxy`·`detection_id`를 저장한다. 추적·융합의 중간 상태는 별도 sidecar에 기록한다. 이번 비교의 B3는 고정 person output과 고정 판단 설정을 사용한다. B4 사용 시 관계 파일은 각 detector replay SHA·config SHA·media·classifier provenance에 다시 결합한다. 사건 평가 입력은 정답과 replay manifest의 source·hash를 맞춘다. [Replay contract][replay-code] · [평가 도구][eval-code] · [Holding 규격][hoi]
4. **Orin 경로.** 기존 `tools/profile_orin_file.py` 및 `tools/verify_orin_file_smoke.py`부터 활용한다. 동일 power mode·입력·sample clock의 native CUDA 결과부터 기록한다. ONNX는 입력 shape·opset·전후처리와 출력 일치 확인 후 보드의 TensorRT에서 engine을 만든다. FP16·TensorRT는 FP32 비교 후 별도 모드로 측정한다. ARM64 wheel·연산자·plugins·메모리·온도·정밀도 불일치가 남으면 오프라인 후보로 기록한다. [Orin 파일 프로파일러][orin-tool] · [NVIDIA TensorRT 호환성](https://docs.nvidia.com/deeplearning/tensorrt/latest/inference-library/engine-compatibility.html)

### 기존 Replay 명령 예시

새 worktree에서 프로젝트 환경을 준비하고, 변수에 해당 실행의 검증된 파일과 **새 출력 디렉터리**를 넣는다. 아래 두 명령은 현재 CLI를 사용한다. 미래 B3 비교에서 실험 팔당, 녹화당 replay를 한 번 만든 뒤 같은 정책으로 묶어서 평가한다.

```powershell
$env:PYTHONPATH = 'src'
python -X utf8 -m edge_threat_response.replay_cli --input $tbDetections --config $tbFrozenConfig --output-dir $tbReplayOut --modes B3
python -X utf8 -m edge_threat_response.evaluate_cli --ground-truth $tbTruth --replay-manifest $tbManifest --policy $tbFrozenMatchPolicy --output-dir $tbEvalOut
```

`$tbManifest` 파일은 기존 template에서 `modes=["B3"]`와 녹화별 입력/결과 경로를 채운다. B4 비교에는 `--modes B3,B4 --relations <sidecar> --relation-threshold <frozen-threshold>`를 적용하고 manifest에도 B4를 추가한다. 주석 버전/원본·clip SHA와 사전 고정된 early/late 정책을 기록한다. [Replay manifest 예시][manifest] · [사건 정답 양식][truth] · [실행·평가 규약][event]

### 자동 평가·모니터링·복구

- 준비 → CUDA/데이터 점검 → 학습 또는 고정 추론 → tune 선택 → 잠근 dev-check 평가 → 요약 수집을 분리한다. 개발2의 동일 D1 저점수 캐시는 읽기 전용으로 재사용한다. 인계 시 가중치·코드·입력 manifest·전후처리·후보 하한·정밀도와 예측 JSONL SHA를 맞춘다. 필요한 실험 조건이 기존 캐시에 없으면 해당 조건만 별도 실행으로 기록한다. 인접 입력 실험은 PTS 설정과 상태 초기화 정책도 확인한다.
- 중앙 예약표에서 장비·GPU index·트랙·담당·시작/종료와 상태를 관리한다. launch 직전 외부 GPU 점유와 Track A 작업 상태를 다시 본다. Windows 학습기의 `gpu_training_lock`은 worktree가 달라도 같은 물리 GPU의 기존 절대 락 경로를 사용한다. Linux는 Track A와 **같은 물리 UUID별 `flock`**을 확보하고 `CUDA_VISIBLE_DEVICES`로 한 장만 노출해 내부 `device=0`에 연결한다. Linux의 `nohup`은 재접속 후 PID·시작 시각·진행 로그를 확인한 뒤 본 실행에 쓴다. 기존 큐에서 process lock, 영수증과 수집 방식을 재사용하고 PC13 검수·운영 작업의 예약을 존중한다. [연구실 GPU 운영][lab-gpu] · [큐 구현][queue-code] · [학습 락][training-code]
- `invocation.json`, `state.json`, `stdout/stderr.log`, snapshot/epoch, GPU 측정, `metrics.json`, pin된 버전과 SHA를 시도별 저장한다. 성공 marker는 예측 줄 수·source/timebase와 결과 무결성 확인 후 남긴다. 최종 평가 결과와 원본 자료는 개발 자동 집계에서 분리한다. 공개 Git에는 코드, 집계, manifest schema와 비식별 식별자만 올린다.
- 평가만 실패하면 같은 checkpoint·입력 SHA로 새 평가 attempt에서 이어간다. 학습 재개는 checkpoint optimizer/EMA·scheduler·epoch·RNG 상태 및 split/config를 대조한다. 상태가 없으면 새 시도로 기록한다. OOM으로 microbatch/정밀도를 바꾸면 동일 설정 재개의 결과로 합치지 않는다. 종료한 작업도 원인·마지막 완료 단계·로그를 보존한다. `run_p430_site.py`의 실제 학습 종료와 평가 callback 실패 복구 사례를 참조한다. [11/24–25 평가 복구][p430-result]

## 8. 위험, 인계 및 문서 경로

| 위험 | 대응과 완료 증거 |
| --- | --- |
| 최종 영상이 개발용으로 반입 | allowlist에 승인 개발 source만, 차단 해시·원본/편집/동시 촬영 계보 대조. 보호 경계를 통과하지 못한 데이터가 포함된 실행은 중지하고 결과를 선택에서 제외 |
| 조건 분할을 새 세션 일반화로 오인 | 두 원본의 역사 재현과 원본 홀드아웃을 별도 표로 보고. 독립 그룹 수, GT별 TP/FP 수, 원본별 편차 명시 |
| 연속 영상의 시간축·좌표 또는 실제 관계 GT 부족 | PTS와 sparse label 연결 확인, clip 경계 reset, uncertainty 표시, 수동 double check. 사건·관계 GT가 준비되기 전 해당 지표를 보고하지 않음 |
| 조건을 추가하면서 원인 혼합 | Track A의 같은-weight 입력 결과와 공통 음성 목록을 재사용. ALT-05는 측정 열화, ALT-07은 복원, ALT-08은 검수, ALT-11은 loss만 바꾸는 팔로 유지. Track A와의 2×2 전까지 새 기술을 합치지 않음 |
| Orin latency·RAM 또는 export 불일치 | 현재 native 환경으로 기준 측정, 단계별 p95·drop·온도·RAM 기록. ONNX/TensorRT 수치 동등성 및 실제 반복 시험이 끝난 후보만 배포 표에 포함 |
| GPU·일정 충돌과 결과 덮어쓰기 | Track A 대기열, 현재 점유, 전원·냉각 및 서버 동시 부하 상한을 확인한 적합 슬롯을 사용한다. GPU별 공유 락, Track B 고유 ID·새 시도 경로로 충돌을 막는다. 제출이 지연되면 D1을 유지하고 연구·제출 일정을 분리한다. |

연구 결과의 비식별 집계·근거는 `reports/evaluation/p430-track-b-<date>/`, 실기기 검증은 `reports/runtime/`와 `docs/verification.md`에 기록한다. Track B 채택 여부와 실험 상태는 개발 결과가 확보된 뒤 갱신한다. [문서 관리 규칙][docs-governance]

[resources]: training-resource-schedule.md
[master]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/project-plan.md
[mvp]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/mvp-research-specification.md
[track-a]: p430-phase2-optimization-plan.md
[lab-gpu]: lab-gpu-training-plan.md
[gpu-benchmark]: training-gpu-benchmark-2026-11-26.md
[p430-result]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/p430-site-finetuning-rationale.md
[site-code]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/tools/run_p430_site.py
[p430-code]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/src/edge_threat_response/p430_evaluation.py
[alt-prev]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/reports/evaluation/p430-alternatives-2026-11-21/report.md
[pretrained]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/reports/evaluation/pretrained-vs-finetuned-2026-11-04/report.md
[view-gain]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/reports/evaluation/cctv-view-gain-2026-11-15/report.md
[integrated]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/reports/training/p430-integrated-2026-11-22/report.md
[first]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/reports/datasets/p430-capture-review-2026-11-18/report.md
[second]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/reports/datasets/p430-second-review-2026-11-19/report.md
[hoi]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/hoi-annotation-contract.md
[cuda]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/training-cuda-handoff.md
[queue]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/p430-experiment-queue.md
[event]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/controlled-experiment-protocol.md
[verify]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/verification.md
[handoff]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/handoffs/2026-11-20-p430-reviewed-yolo.md
[model-data]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/model-data-plan.md
[common-code]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/src/edge_threat_response/detector_comparison.py
[comparison-tool]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/tools/run_detector_comparison.py
[detector-code]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/src/edge_threat_response/detector.py
[replay-code]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/src/edge_threat_response/replay.py
[eval-code]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/src/edge_threat_response/evaluate_cli.py
[orin-tool]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/tools/profile_orin_file.py
[manifest]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/templates/experiments/replay-manifest.template.json
[truth]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/templates/experiments/ground-truth.template.json
[queue-code]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/src/edge_threat_response/p430_queue.py
[training-code]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/src/edge_threat_response/training.py
[docs-governance]: https://github.com/jaydenkim197/edge-threat-response/blob/f35a562/docs/documentation-governance.md
