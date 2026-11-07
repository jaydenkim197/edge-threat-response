# Model and Dataset Readiness Plan

<!-- m2-parallel-20261107:begin -->
## 2026-11-07 — 추가 GPU의 해상도·증강·seed 비교

사용자 요청으로 PC11 n960, PC12 n640+mosaic.5/scale.5/close20, PC14 n640+seed20261107을 **실제 학습 시작**했다. 기본 PC13 M2는 유지하며 동일train11,884/val1,423/test1,423·초기weight·50epoch·batch16·37,150updates를 공유한다. source8316b41이며 학습 코드는 기존06936e8과 동일하다. 각13tests·CUDA·실제로더/다수batch 진행을 확인했고 전체 완료·정확도·Orin 비용은 대기다.

캐시 M1-n+s NMS 앙상블은 일부 source recall 증가와 FP 증가를 보였고 확대US83은여전히0/31TP다. 자동 배포 채택하지 않는다. 완료 후 같은 자료의640/9602×2와source별지표로 비교하고, 실제촬영/T1·HOI를우선한다. [설정·수치·노드별 증거·한계](../reports/training/m2-parallel-2026-11-07/report.md).
<!-- m2-parallel-20261107:end -->

<!-- m2-real-20261107:begin -->
## 2026-11-07 — M2 n/640 실행

M1 train11,378에서 문제·불확실88장 제외, 별도 Open Images train594장/820knife 추가로 **train11,884/val1,423/test1,423**을 준비했다. 기존 holdout identity·image/label bytes·순서는 고정하고 보호263개 포함 source15,545+US Mock100+새594 proxy graph를 검사했다. 운영 검수 DB·기존 모델/학습 입력은 보존한다. 실제 세션 완전성·개별 권리·CCTV 비율·사람검수 완료를 주장하지 않는다.

`RAW-M2-n`을 source06936e8 격리worktree에서 PC13 CUDA로 시작했다. M1과 동일 초기 pretrained n/640·50epoch·batch16·optimizer/증강/seed이며 새37,150updates는 기존35,600과 달라 순수 정제/증량 ablation이 아니다. 실제 loader11,888draws·743batches·val1,423·accumulate1을 확인했다. 완료 후 M1-n/COCO26n과 공통6개 개발셋 AP/predict·확대US83을 비교하는 dependent worker가 대기 중이다. 새 정확도·D*·Orin·독립 final은 미검증이다.

사용자는 다음 주 촬영 예정이라고 확인했다. T1·실제 Holding GT/학습은 그 자료를 확보한 뒤 진행하며 Roboflow 추가 접근 정보 대기를 선행gate로 두지 않는다. [구성·해시·실행·한계](../reports/training/m2-real-2026-11-07/report.md).
<!-- m2-real-20261107:end -->

<!-- docs-refresh-20261106:begin -->
## 현재 데이터·모델 준비 기준 — 2026-11-06

- RAW R1/H1/M1-n/M1-s는 각각 50 epoch·35,600 update를 완료했다. M1-n은 후속 주력 후보이며 최종 D*는 미동결이다([비교 결과](../reports/evaluation/raw-detector-selection-2026-11-06/report.md)).
- RAW 자료는 총 14,224장으로 train 11,378 / val 1,423 / test 1,423이다. Catargiu 검수 표본 793장은 학습 원본 전체 수와 다르다. 검수 정상 1,805장은 이미 M1 train에 있고, 문제·불확실 판정 88장은 후속 정제 대상이다([대조 결과](../reports/datasets/reviewed-next-training-2026-11-06/report.md)).
- 별도 Q1 학습을 후순위로 두고 정제를 M2 n/640에 반영하며, 촬영 자료 확보 시 T1·HOI를 우선하는 안은 `PROPOSAL`이다. 새 M2/T1 데이터 구성과 학습은 미실행이다.
- 이미 열어본 6개 개발셋과 확대 US Mock 83장 전체의 source·유사 그룹은 새 train에서 보호한다. RAW test는 최종 독립 사건 평가를 대신하지 않는다.
- PC13 및 PC11/12/14의 CUDA 환경과 P430/Orin의 R1 연동은 확인했다. 새 M1·T1 모델의 Orin 비용, 실제 HOI, GPIO와 독립 평가는 남아 있다.
- 정식 reviewed, DEV, RAW는 입력과 승인 범위가 다르다. RAW의 사람 검수 전 사용 허용도 기술 검사·사용 조건·분할 보호를 생략한다는 뜻은 아니다. 초기 D2/D3의 검수 대기 조건을 모든 RAW 실행에 다시 적용하지 않는다.
- 신규 제한 자료는 제공 조건과 비공개 접근 환경을 준비한 뒤 반입한다([원칙](research-overview-en.md)).
- 11/07 CCTV V3는 50장 주석·47장 이미지의 제한 감사를 완료했다. 칼 40장 중 고각 유사 1장·다른 고정 실내 6장만 검수 후보로 보관한다. 원래 split의 같은 장면 교차와 기존 source 유사 14장을 확인해 전체 학습 채택은 보류 권장이다. 사람 검수·M2 반입은 아직 없다([근거](../reports/datasets/roboflow-cctv-v3-2026-11-07/report.md)).
<!-- docs-refresh-20261106:end -->

<details>
<summary>날짜별 모델·데이터 진행 기록 (현재 작업은 위 요약 우선)</summary>

<!-- cctv-candidate-check-20261106:begin -->
## 2026-11-06 — Q1·M2·T1 권장 순서 구체화

Q1별도50epoch보다**88장정제를M2단일n/640 recipe에흡수**하는후속안을권장한다(PROPOSAL). 정제/추가데이터개별인과효과를주장하지않고기존M1대비전체recipe개선으로보고한다. 신규Roboflow CCTV V3/499는각최대50장표본조사후고유한작은knife/혼동음성가치가있을때만추가후보로삼는다. overview수와증강export수·class변환을구분한다. 새샘플/학습실행은아직없다.

Catargiu26,528은4class전체/v11+NoGun v5이며기존v11 knife-positive5,429조사/M1 Catargiu5,424준비/train5,100과크게겹친다. 미사용NoGun조사는가능하지만이름/객체라벨만으로knife음성을확정하지않는다. 새import는확대US Mock83장전체와기존평가그룹을보호한다. 합성/싸움라벨/일반감시영상을knife/Holding정답으로자동변환하지않는다. 공개조사와독립CCTV T1·HOI 촬영/라벨을병행하고자료가준비되면T1을우선한다. [사실·실행경계·한계](../reports/datasets/cctv-candidate-check-2026-11-06/report.md).
<!-- cctv-candidate-check-20261106:end -->

<!-- reviewed-next-training-20261106:begin -->
## 2026-11-06 — 검수 반영 후 다음 recipe 제안

정상2,527장 전체를 신규 train으로 세지 않는다. M1 기존 train/표시라벨 일치 정상1,805장, 보류88장(문제49/불확실39), 새 실사 직접 검사 통과 후보39장(양성5/음성34)이다. **Q1-clean-n**은 기존11,378−88=**11,290장**, 같은 pretrained 초기weight/n/640·50epoch·11,392draws/epoch·35,600updates의 정제 recipe 비교를 권장한다(`PROPOSAL`, 미실행). val/test 각1,423장과 기존 평가 보호그룹은 유지한다. 미검수 RAW 사용 허용은 유지하며 정상만1,805장으로 전체를 축소하지 않는다.

새39장은 전체 신규 간 전이적 그룹/source 검사 후 별도 M2 후보로 보존한다(모두 추가 시 최대11,329장, 확정 아님). Open Images 별도train과 Dangerous 보강은 역할/중복검사 후 판단한다. US Mock83장·Open Images 정상29장·DaSCI 보호연결93장은 train으로 전환하지 않으며 합성은S1/Legacy는L0로 분리한다. 확대 US CCTV31GT에서 M1-n640은0TP,960은1TP여서 자체CCTV T1의 train/tuning/final 세션 분리와 HOI pair GT 준비가 핵심이다. [증거·조건·남은 검사](../reports/datasets/reviewed-next-training-2026-11-06/report.md).
<!-- reviewed-next-training-20261106:end -->

<!-- raw-results-20261106:begin -->
## 2026-11-06 완료 결과와 다음 학습 후보

- R1-n/H1-n/M1-n/M1-s의 실제35600 update를 모두 확인했고, 8모델×6개 개발셋의AP/predict를 분리 평가했다. 권장 후보는 **M1-n**이다(`PROPOSAL`, D* 미확정). SOHAS opened dev23의predict AP50/recall은기존D0 35.7/35.0→M1-n88.3/80.0%다. 같은조건의M1-s는85.2/70.0%이며, 일부val/F2에서는s가좋은조건도 있다.
- 기존640-trained M1-n의960 추론은 SOHAS small TP13→14/16, DaSCI59→71/88로 증가했다. 실제CCTV US8GT는계속0/8이고 Open Images AP는감소했다. 해상도·모델크기만으로field 문제가해결됐다고하지 않는다.
- 다음은 n/640·같은예산의M1 vs 추가실사M2 recipe 비교를 권장한다. 확보한Open Images train594장 등은전역중복/보호그룹·annotation/source를검사한뒤별도recipe로준비한다. 자체CCTV train 적응은새로운run으로분리하며tuning/final session을보호한다. 사람검수완료를RAW선행gate로되살리지않는다. HOI에는별도관계정답이필요하다.
- 960 학습/Orin운영해상도는실제CCTV tuning 이득과Orin지연/메모리확인후결정한다. 현재Orin의R1과새M1은다른checkpoint다. [정량표·raw 위치·통제조건·한계](../reports/evaluation/raw-detector-selection-2026-11-06/report.md). 새학습/교체/최종D*선정은아직실행하지않았다.
<!-- raw-results-20261106:end -->

<!-- hoi-b4-implementation-20261105:begin -->
## 2026-11-05 실행 갱신

사람 검수를 기다리지 않는 RAW 원본 주석 예비 학습을 별도 승인 범위로 구현했다. SOHAS/Dangerous VOC/Catargiu14,224장과 보호 그룹을 고정하고, train11,378/val1,423/test1,423에서 R1/H1/M1-n/M1-s를 같은35,600 update 예산으로 시작했다. 실제 loader 수·변조/누락·공통 평가 목록을 확인한다. 정식 사람 검수나 최종 detector 선택을 뜻하지 않는다. [실행 계약](raw-source-training.md).

M1의 source는 실사 보강을 의도한 공개 source 혼합이며, 미검수이므로 개별 이미지의 실사/CCTV 여부를 확인했다고 주장하지 않는다. 큰 conservative group 때문에 source별 split 비율이 다르고, 새 raw val/test에는 SOHAS가 매우 적다. 따라서 source별 기존 개발 비교와 새 독립 CCTV 평가를 함께 보고해야 한다. source별 최종 성능은 전체 학습 후 확인한다.

HOI는 bbox-only 자료에서 자동 정답을 만들지 않는다. [Holding pair 규격](hoi-annotation-contract.md)의 명시적 human 관계 정답이 필요하며, 현재 학습기/B4는 가상 자료 PC 및 Orin CUDA 연결과 PC13 checkpoint의 Orin strict load를 검증했다. 실제 Holding 정확도는 미검증이다([증거](../reports/runtime/hoi-b4-integration-2026-11-05/report.md)). 원본/weight/판정은 PC13 ignored 경로에 보관하고 Git에는 코드·설정·간결한 증거만 올린다.
<!-- hoi-b4-implementation-20261105:end -->

상태: 데이터 준비 범위·canonical class contract `DECISION`, 외부 dataset 채택·detector topology·학습 설정 `PROPOSAL`

이 문서는 detector 재학습을 성급하게 시작하지 않고, 데이터의 출처·라벨 의미·분할·학습 이력을 재현 가능하게 만들기 위한 기준이다. 실제 대규모 데이터와 model binary는 Git에 넣지 않는다.

2026-10-26: 사용자 승인된 SOHAS183장 개발용 subset의 예비 학습과 오류 분석을 수행했다. 이는 source 전체 채택이나 최종 detector 결정이 아니다. 낮은 성능은 train/val fit 차이와 작은 객체 분포 차이를 동반하며, 고정 split에서 optimizer/LR 및 크기 증강을 제한적으로 비교한다. 후속 결과와 데이터 보강 우선순위는 [개발 모델 오류 분석](../reports/training/development-error-analysis-2026-10-26/report.md)에 기록한다. 기존 R1/H1 gate와 test 보관 원칙은 유지한다.

2026-10-26 추가: [신규 검수304장](../reports/datasets/additional-review-2026-10-26/report.md)을 웹에 배포했다(Catargiu17/ATM 합성237/Dangerous VOC50). 전량 검수 대기·학습 미승인이며 기존 split/승인 파일은 보존했다. Dangerous raw class map은25개 VOC–YOLO 대응 라벨로 지지됐지만 전체 검증을 뜻하지 않는다. 다음은 human review와 source/negative/group gate이며 자동 학습을 시작하지 않는다.

## 2026-11-04 다중 source의 기성 모델 대 fine-tuned 모델 비교

사용자 요청으로 기존 best와 기성 YOLO26n/m/l/x·RF-DETR Small/Medium/Large·DEIMv2-S의9개 checkpoint를 동일6개 개발 평가셋(263장/241knife GT)에서 비교했다. 신규 학습은 없으며 source/최종 D* 채택 승인은 추가하지 않았다. [조건·전체 표·CSV·논문용 그림·원시 경로](../reports/evaluation/pretrained-vs-finetuned-2026-11-04/report.md).

공통 COCO evaluator와 클래스별 후보 convention에서 같은 n의 SOHAS test AP50은7.26→35.69%지만 Open Images는84.90→7.85%로 저하됐다. RF Large의 SOHAS test AP50은38.41%이나 고정.25 recall은30%(custom35%)다. 실제 CCTV 표본도8GT뿐이고 RF Large recall12.5%라 배포 충분성을 주장하지 않는다. 현재 custom의 보편적 개선·최종 모델 승격 근거는 없고 RF Large/Small은 후속 Orin 검증용 강한 기성 기준선 `PROPOSAL`이다.

YOLO default predict와 validator의 multi-label 차이를 확인해 default/v2와 per-class/v3 각54개 결과를 분리 보존했다. 이 보고의 AP는 공통 COCO 계산이므로 이전 native AP34.43%와 본35.69%를 모델 향상으로 해석하지 않는다. DaSCI92장은 관련-source, Simuletic75장은 합성, Open Images29장은 small GT0이다. 모든 자료는 개발 비교에 사용됐으며 독립 final holdout이 아니다. 라벨 재확인 항목1개를 남겼고 source/검수 DB·기존 split·weight는 수정하지 않았다.

## 2026-11-04 기성 YOLO 비교와 reserved test 공개 이력

직접 사용자 요청으로 DEV-SOHAS reserved test23장을 개발 모델 비교에 열었다. **이23장은 더 이상 unseen final test가 아니며**, 이후 정식 평가는 별도 독립 holdout이 필요하다. 이전 test 보관 방침은 이 범위에서 `SUPERSEDED`다. 원본 split/manifest/승인 파일은 그대로 보존하고 평가 truth에 개발 비교/원 split을 명시했다. source 전체 채택·좌표/실제 session·최종 평가 승인은 추가하지 않았다.

PC13 CUDA에서 기존 custom n640 / COCO n640 / COCO x640 / COCO x1280을 동일 val23·test23, square/FP32/batch1로 재평가했다. test knife AP50은 각각34.43/6.33/19.44/24.98%, 고정 conf.25·IoU.5 recall35/0/5/5%다. val에서는 x1280 AP50이 더 높아 표본 일반화는 금한다. 기성 x로 즉시 교체할 근거가 없고 custom도 충분하지 않다. 최종 D*는 미확정이며 보강/학습 gate를 유지한다. [조건·수치·hash·한계](../reports/evaluation/ready-yolo-comparison-2026-11-04/report.md).

</details>

## 1. Confirmed legacy inventory

2026-09-14에 고정 submodule `legacy/2025-2-midas/Crime_Prediction`을 읽기 전용으로 점검했다.

| 항목 | 확인 결과 | 상태 |
|---|---|---|
| dataset v1.0 | train 709, valid 237, test 237; 총 1,183 images/labels | `VERIFIED` (파일 inventory) |
| dataset v1.1 | train 5,046, valid 566, test 569; 총 6,181 images/labels | `VERIFIED` (파일 inventory) |
| 전체 image | JPG 7,364장 | `VERIFIED` |
| image-label pairing | basename 기준 missing image 0, missing label 0, empty label file 0 | `VERIFIED` |
| class | 두 dataset 모두 `nc: 1`, `names: ['knife']`; label class ID는 전부 0 | `VERIFIED` |
| annotation | 9,060 object records: bbox 7,613개, polygon 1,447개, 구조상 invalid 0개 | `VERIFIED` (구문 수준) |
| source declaration | Roboflow project/version과 CC BY 4.0이 각 `data.yaml`과 README에 기록됨 | `AVAILABLE`; upstream·개별 image 권리 재확인 필요 |
| split leakage signal | v1.0에서 filename source group 3개가 split을 교차하고, 두 버전을 합치면 317개 group이 split을 교차 | `VERIFIED`; 재분할 필요 |
| weights | `yolo11n.pt`, `customknife_v1.1.pt`, `customyoloknife.pt` 등 존재 | `AVAILABLE`; 학습 lineage·성능 `UNVERIFIED` |
| training code | YOLO11 pretrained weight, 100 epochs, AdamW, 640/960 image size를 사용한 스크립트 존재 | `AVAILABLE`; 완전한 run evidence 없음 |

이 데이터는 person label이 없는 knife-only dataset이다. 이를 `person=0, knife=1`인 신규 dataset과 단순 연결하거나, person이 등장하는 image를 person 미표기 상태로 unified 2-class 학습에 넣지 않는다.

## 2. External source findings and roles

| 후보 | 확인된 사실 | 현재 판단 |
|---|---|---|
| SOHAS / OD-WeaponDetection | official repository에 detection data와 similar handled object source가 있다. README의 CC BY-SA 4.0과 `License.md`의 CC BY 4.0 전문이 충돌 | 첫 public real-world source `PROPOSAL`; 실제 적용 권리와 stratified 표본 audit 후 채택 판단 |
| DaSCI / OD-WeaponDetection Knife | 2026-10-02 공식 Git image metadata에서 2,078장 중 1,985장이 SOHAS와 동일 basename·동일 blob; 나머지 최대 93장도 near-duplicate·품질 미검증 | 단독/합본 필수 run 아님. 실제 visual gap을 메우는 고유 이미지일 때만 선택적 보강 `PROPOSAL` |
| ACF Knife | full-HD CCTV·small knife를 다룬 ACF 연구의 source. 논문이 제시한 저장소는 2026-09-26 접근 실패 | Dataset v1 training에는 0장; raw 파일·권리·라벨 확보 시 external **image/frame** holdout 후보 `PROPOSAL` |
| US Mock Attack | 3 CCTV camera의 full-HD mock attack frames를 논문이 기술; knife label 수가 적고 sequential frame | Dataset v1 training에는 0장; 원본 시간 순서·event 정답 확인 시 camera/sequence 사건 평가 후보 `PROPOSAL` |
| COCO | 80-class detection에 `person=0`, `knife=43`; COCO 2017 train 118,287 / val 5,000 | pretrained sanity baseline 후보. CCTV·small-knife 적합성은 sample 검수 필요 |
| Open Images V7 | 약 9M images, 600 boxable classes, 1.9M box-annotated images; boxable class 목록에 Person과 Knife 존재 | 선택적 보강 후보. 2026-10-04 validation의 knife-positive 30장 표본만 웹 검수에 준비했으며, class subset의 라벨 밀도·개별 이미지 권리·동시 person annotation 확인 전 채택하지 않음 |
| Simuletic CCTV knife sample | 114 synthetic CCTV-style images, person/knife YOLO labels, CC BY 4.0 선언 | pipeline smoke/sample 검수용 후보. 본 실험의 주력 real-world dataset으로 사용하지 않음 |

근거:

- COCO class/config: <https://docs.ultralytics.com/datasets/detect/coco>
- Open Images V7 description: <https://storage.googleapis.com/openimages/web/factsfigures_v7.html>
- Open Images boxable class descriptions: <https://storage.googleapis.com/openimages/v5/class-descriptions-boxable.csv>
- Simuletic dataset card: <https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset>
- SOHAS / OD-WeaponDetection official repository: <https://github.com/ari-dasci/OD-WeaponDetection>
- ACF dataset paper and availability reference: <https://pmc.ncbi.nlm.nih.gov/articles/PMC9572610/>

후보라는 이유만으로 dataset을 다운로드·병합하지 않는다. provider 설명의 숫자와 license 표시는 source record이며, 실제 annotation 품질과 프로젝트 적합성 검증을 대신하지 않는다. target domain과 source 역할은 [Dataset Source Strategy](dataset-source-strategy.md), 검사 순서와 legacy review 열 정의는 [Dataset Evaluation Criteria](dataset-evaluation-criteria.md), 문헌 근거는 [선행연구 검토](prior-work-and-dataset-review.md)를 따른다.

## 3. Detection and class contract

- downstream detector output label은 `person`, `knife` 두 개로 제한한다.
- runtime canonical registry에서는 ID `0=person`, `1=knife`를 사용한다. runtime contract의 주 식별자는 문자열 label이며 숫자 ID는 source/model adapter 경계에서만 변환한다.
- raw dataset class ID는 source별 mapping으로 해석한다. legacy raw `0=knife`는 runtime canonical ID `1`에 대응한다.
- knife-only YOLO 학습 dataset과 model output은 model-local `0=knife`를 사용한다. detector adapter가 model-local `0`을 runtime canonical `knife`/ID `1`로 변환한다.
- processed unified 2-class dataset은 모든 식별 가능한 person과 knife annotation이 완전한 경우에만 `0=person`, `1=knife`를 사용한다.
- `holding_knife`, `threat`, `weapon_event`, `knife_on_table`을 detector class로 만들지 않는다.
- person–knife 관계와 사건은 spatial/temporal layer에서 판단한다.
- 두 logical class가 하나의 model file에서 나와야 한다는 결정은 하지 않는다.

### Detector topology candidates

1. **COCO pretrained single model**: person/knife 모두 출력하는 zero-training sanity baseline.
2. **Composite detector**: COCO-pretrained person detector + knife-only fine-tuned detector. legacy knife data를 person 재라벨링 없이 활용할 수 있는 우선 실용 후보다.
3. **Unified 2-class detector**: 모든 학습 image의 식별 가능한 person과 knife annotation이 완전할 때만 학습 후보로 승격한다.

최종 topology는 Orin runtime, detection 품질, annotation 비용과 latency를 측정한 뒤 P0-05에서 정한다. B0~B3 context ablation에는 선택된 동일 detector를 사용한다.

## 4. Data implementation scope

### D1 — inventory and validation foundation: `IMPLEMENTED`, PC `VERIFIED`

- machine-readable dataset-source registry schema와 작성 예시
- JSONL image manifest builder: stable image ID, source, original path/reference, source group/session, declared license, raw/canonical class map, split, hash, notes
- YOLO bbox와 polygon label parser·validator
- image/label 짝, invalid class, 좌표 범위, 양수가 아닌 크기, empty label 검사
- source·split별 image/object/class/annotation-format 집계
- SHA-256 exact duplicate 검사
- 동일 source/session/group 및 exact duplicate의 split 교차 검사
- group-aware split planner. 파일 복사·최종 split 적용은 명시적 실행 단계로 분리
- JSON summary와 사람이 읽는 Markdown/text report
- 소형 synthetic fixture를 이용한 단위·CLI smoke test
- legacy v1.0/v1.1 audit report 생성

구현은 `src/edge_threat_response/dataset/`에 있으며 CLI는 `etr-dataset audit`과 `etr-dataset plan-split`이다. 13개 표준 라이브러리 단위·통합 테스트와 전체 legacy read-only audit를 통과했다. 실제 결과는 `reports/datasets/legacy-2026-09-14/`에 보존한다. 이는 label 구조 검증이며 image 내용·시각적 annotation 품질·license 검증이 아니다.

### D2 — exporter/review/import `IMPLEMENTED`, 정식 human 승인과 RAW 예비 허용 구분

- legacy image decode/손상 검사와 deterministic visual-review pack 생성
- source·객체 크기·annotation 형식별 표본, review CSV와 contact sheet 생성
- 승인된 source에 한해서 metadata/subset importer 구현
- source-specific class mapping과 annotation conversion
- polygon-to-bbox 변환이 필요하면 raw 보존과 deterministic processed export를 분리
- 각 후보 50~100장 표본의 CCTV angle, small/distant knife, person co-occurrence, occlusion, negative/hard-negative 검수 기록
- 최종 dataset recipe와 source/session group split 생성

COCO/Open Images 전용 downloader를 일반화해 미리 만들지 않는다. 채택 source와 공식 접근 방법이 정해진 뒤 얇은 importer만 추가한다.

2026-09-15에 group-aware planned manifest를 knife-only YOLO dataset으로 materialize하는 exporter를 구현했다. model-local class는 `0=knife`이고 runtime adapter mapping은 canonical knife ID `1`이다. development default `70/15/15`, seed `20260915`로 생성한 전체 출력은 exact duplicate 3장을 제외한 7,361장/9,057 objects이며 source group과 exact hash의 split 교차는 0건이다. 이 split과 수치는 연구 최종 결정이 아니다.

같은 날 visual-review pack 생성기를 구현하고 7,361장 전체 decode 오류 0, source/split/format/normalized-area별 128장 표본과 contact sheet 8장을 생성했다. 전 페이지 개발 확인에서 제품사진·주방·손/knife 클로즈업·워터마크·저해상도 장면 등 CCTV와 다른 domain 및 반복 인물·배경이 함께 보였다. 현재 split metric은 engineering baseline 외 일반화 근거로 사용하지 않는다. 사람의 CSV 판정이 끝날 때까지 dataset 품질 승인과 ambiguous annotation 규칙은 `PENDING`이다.

#### SOHAS VOC source-specific audit

2026-10-04 자율 준비 위임 후 PC13의 pinned byte-exact staging에 SOHAS VOC 원본 image 5,859장(공식 tree size 1,861,407,276 bytes)을 확보했다. 노트북/Drive에는 전량 복사하지 않는다. source-specific 전체 image screening과 후보 pack 유사 pair 진단은 [자동 검사 계약](dataset-evaluation-criteria.md#7-사람-검수-전-가능한-이미지-자동-검사)을 따른다. 고정 threshold knife bbox·작은 bbox recall·음성 FP 평가 기반은 [후보 평가](training-cuda-handoff.md#knife-bbox-후보-평가--2026-10-04)에 있다. 확보·구조 검사·가상 평가 성공은 좌표·권리·visual completeness·session group·recipe 채택·실제 학습을 승인하지 않는다.

`dataset/sohas.py`와 `etr-dataset sohas-voc-audit`는 승인 전 준비 경로다. 기존 `parse_yolo_label`, `ValidationIssue`, review의 `size_bucket`을 재사용하고 XML은 Python 표준 라이브러리로 읽는다. 추가 의존성이나 일반화된 downloader는 만들지 않는다.

- 입력: 공식 upstream Git commit `48860b990e4d4f57fe100248887fceb248475dc8`. Git tree의 원래 train/test image 목록을 같은 split의 `annotations/xmls` / `annotations_test/xmls`와 basename으로 짝맞춘다. sparse checkout에 이미지가 없어도 metadata pairing은 가능하다. XML·비교용 YOLO label은 로컬 bytes의 Git blob 일치를 검사하고 SHA-256을 출력한다.
- raw map: 공식 YAML의 `0=pistol, 1=smartphone, 2=knife, 3=monedero, 4=billete, 5=tarjeta`. VOC `name=knife` / raw `2` → runtime canonical `1=knife` → model-local `0=knife`. non-knife 객체와 모든 원본 bbox·difficult/truncated 값도 candidate JSON에 보존한다.
- 기본 `--coordinate-convention unknown`: 좌표를 추정하지 않고 변환을 보류한다. `pixel-edges`는 `(xmin+xmax)/(2W)`, `(ymin+ymax)/(2H)`, `(xmax-xmin)/W`, `(ymax-ymin)/H`이며 좌표 범위는 `0≤min<max≤size`다. `voc-1based-inclusive`는 정수 `1≤min≤max≤size`를 검사한 뒤 left/top에서 1을 빼고 right/bottom을 유지한다. 이는 지원 가능한 두 **명시적 입력 계약**이지 SOHAS 전체의 convention 확정이 아니다. 둘 다 `--coordinate-evidence`가 필요하며 실제 원본/이미지에서 확인해야 한다.
- 오류 bbox는 clip·교정·부분 삭제하지 않는다. 하나라도 잘못된 객체가 있거나 pairing/identity가 모호하면 전체 이미지의 변환 초안을 보류한다. 유일하게 짝맞춘 image의 `.JPG`/`.jpg` 차이는 warning으로 기록하고 원래 filename을 보존한다. 이미지 없는 XML 83개는 제외한다.
- 출력: `voc-candidates.jsonl`은 원본 bbox와 선택적 `candidate_yolo_lines`를 가진 별도 검수 형식이다. 학습 `.txt`, data YAML, 자동 split, 표준 materialization manifest를 생성하지 않는다. 기존 `plan-split`/`materialize-knife-yolo`/`review-pack`에 바로 넘기는 입력이 아니다.
- `review-queue.csv`와 `review-sample.csv`는 실제 사람의 판정을 위한 빈 열을 가진다. 원래 split·candidate role·다중 knife·YOLO 개수 차이를 층으로 두고 SHA-256/seed 순서와 round-robin으로 초기 표본을 선택한다. `summary.json`에 각 층의 선택/모집단 수를 남긴다. 좌표 미확정 상태에서는 size stratum을 추정하지 않으며 이미지 확보·좌표 확인 뒤 크기/scene/session 구간 검수를 보완해야 한다.
- knife annotation이 없는 이미지는 항상 `negative_unverified`다. 권리·실제 knife 부재/라벨 완전성·좌표·decode·near duplicate·session grouping·공통 tuning/final-test·recipe 승인 전에는 R1/H1에 반입하지 않는다. `reviewer`는 비워 두며 AI 제안을 사람 판정으로 기록하지 않는다.

실행은 repository root의 활성 Python 환경에서 위 README 명령을 사용한다. 새 출력 디렉터리가 필요하며 exit `0`은 구조 audit 실행 성공, `1`은 기록된 구조 오류, `2`는 입력/실행 오류다. exit `0`도 채택·권리·negative 진위·좌표 검증을 뜻하지 않는다. [Cloud dry-run 근거](../reports/datasets/sohas-dasci-metadata-2026-10-02/report.md#cloud-voc-dry-run--2026-10-02)와 검수 gate를 함께 확인한다.

### D3 — training runner·CUDA execution `VERIFIED`, 새 recipe는 별도 준비

- YOLO26n primary와 YOLO11n fallback을 development proposal로 둔 config-driven train/evaluate/infer command
- run ID, Git commit, dataset manifest/version, split, seed, model/checkpoint, config, hardware와 command 기록
- Precision, Recall, mAP50, mAP50-95와 per-class metric 자동 수집
- artifact filename, SHA-256, storage reference, evaluation link 기록
- 작은 approved sample의 start-to-finish smoke는 CUDA GPU 또는 Orin 환경에서 실행. 현재 개발 노트북 CPU smoke는 필수 조건에서 제외

사용자 결정으로 2026-09-15에 CPU smoke도 선택적으로 수행했다. YOLO26n, 32 train/8 val, 320 px, 1 epoch, batch 4가 정상 완료되고 checkpoint 재로딩·단일 이미지 inference가 실행됐다. 이는 배관 검증이며 metric 0을 성능 결과로 해석하지 않는다.

CUDA development profile, GPU-required preflight와 review-gated Colab notebook을 추가했다. training invocation은 Git commit, config/data YAML/dataset manifest hash, 환경, metric과 artifact hash를 기록한다. 로컬 CPU에서 CUDA-required preflight가 의도대로 실패하는 것만 확인했으며 실제 GPU full training은 실행하지 않았다.

### D4 — full training and evaluation

2026-10-26 사용자 승인으로 별도 `DEV-SOHAS` 예비 학습50epochs와 checkpoint/composite GPU smoke를 완료했다([실행 보고](../reports/training/sohas-reviewed-development-2026-10-26/report.md)). 정상 SOHAS183개만 사용하고 명시적 review-overlay pixel-edge 개발 좌표·보수적 filename/dHash proxy split·범위/hash-bound 개발 승인을 강제한다. 원 좌표 의미·실제 session·공식 source/최종 평가·외부 재배포 승인은 false이며 아래의 공식 R1/H1 gate와 별개다. Val recall.2143/mAP50 .2658로 낮아 오류 분석·보강이 필요하다. [개발용 실행 계약](training-cuda-handoff.md#2026-10-26-별도-개발용-예비-학습--사용자-승인)을 따른다.

2026-10-04 신규 R1/H1 준비에서는 승인 후보 materialized manifest → 공통 val/test·equal draw train 목록 → hash-bound human approval → CUDA-required runner → tuning 결과 비교까지 구현했다. H1의 양성 반복·batch/nbs·FP32·schedule 설정은 development 제안이며 실제 source 승인이나 학습 완료가 아니다. PC13에 승인된 SOHAS export가 아직 없으므로 full training을 시작하지 않는다. [실행·승인 절차](training-cuda-handoff.md#r1h1-실행-준비--2026-10-04)를 따른다.

- development/tuning data로 학습·threshold 선택
- 고정 holdout에서 detector 평가
- 선택 detector를 Orin pipeline에 연결하고 동일 조건 B0~B3 수행

## 5. Explicitly deferred

- 외부 dataset 전체 다운로드와 무검수 병합
- unified 2-class model의 자동 확정
- 여러 detector family의 전체 학습 benchmark
- perceptual near-duplicate 탐지를 위한 무거운 dependency
- DVC, MLflow, database server 등 별도 MLOps platform
- automatic annotation을 사람이 검수한 ground truth로 간주하는 것
- 기존 발표의 Precision 96.2%, Recall 85.1%, mAP50 93.7% 재사용

## 6. Human decisions required before D2/D3

1. 표본 검수를 통과한 외부 dataset과 실제 사용할 version
2. 모형 knife, reflection, printed knife, 극소 객체와 심한 occlusion의 annotation 규칙
3. 직접 촬영 데이터의 동의·보존·삭제 정책과 source/session ID 규칙
4. detector topology와 primary/fallback model family

대용량 자료는 현재 PC13 내장 디스크에 둔다. 이전의 `10 GB 미만 로컬 staging` 경계는 PC13에 적용하지 않는다. [팀 Google Drive](https://drive.google.com/drive/folders/1tBI7EkxKLN41CwHWA60ENXCgOw_0iYiz)는 별도 백업 후보이며 자동 동기화되지 않는다. source 권리와 자체 촬영물 접근 정책은 외부 공유 전에 확인한다.

위 결정 전에도 D1과 시스템 Increment A는 독립적으로 구현할 수 있다.
