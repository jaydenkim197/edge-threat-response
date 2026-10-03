# Model and Dataset Readiness Plan

상태: 데이터 준비 범위·canonical class contract `DECISION`, 외부 dataset 채택·detector topology·학습 설정 `PROPOSAL`

이 문서는 detector 재학습을 성급하게 시작하지 않고, 데이터의 출처·라벨 의미·분할·학습 이력을 재현 가능하게 만들기 위한 기준이다. 실제 대규모 데이터와 model binary는 Git에 넣지 않는다.

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

### D2 — exporter/review tooling `IMPLEMENTED`, human approval/import `PLANNED`

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

`dataset/sohas.py`와 `etr-dataset sohas-voc-audit`는 승인 전 준비 경로다. 기존 `parse_yolo_label`, `ValidationIssue`, review의 `size_bucket`을 재사용하고 XML은 Python 표준 라이브러리로 읽는다. 추가 의존성이나 일반화된 downloader는 만들지 않는다.

- 입력: 공식 upstream Git commit `48860b990e4d4f57fe100248887fceb248475dc8`. Git tree의 원래 train/test image 목록을 같은 split의 `annotations/xmls` / `annotations_test/xmls`와 basename으로 짝맞춘다. sparse checkout에 이미지가 없어도 metadata pairing은 가능하다. XML·비교용 YOLO label은 로컬 bytes의 Git blob 일치를 검사하고 SHA-256을 출력한다.
- raw map: 공식 YAML의 `0=pistol, 1=smartphone, 2=knife, 3=monedero, 4=billete, 5=tarjeta`. VOC `name=knife` / raw `2` → runtime canonical `1=knife` → model-local `0=knife`. non-knife 객체와 모든 원본 bbox·difficult/truncated 값도 candidate JSON에 보존한다.
- 기본 `--coordinate-convention unknown`: 좌표를 추정하지 않고 변환을 보류한다. `pixel-edges`는 `(xmin+xmax)/(2W)`, `(ymin+ymax)/(2H)`, `(xmax-xmin)/W`, `(ymax-ymin)/H`이며 좌표 범위는 `0≤min<max≤size`다. `voc-1based-inclusive`는 정수 `1≤min≤max≤size`를 검사한 뒤 left/top에서 1을 빼고 right/bottom을 유지한다. 이는 지원 가능한 두 **명시적 입력 계약**이지 SOHAS 전체의 convention 확정이 아니다. 둘 다 `--coordinate-evidence`가 필요하며 실제 원본/이미지에서 확인해야 한다.
- 오류 bbox는 clip·교정·부분 삭제하지 않는다. 하나라도 잘못된 객체가 있거나 pairing/identity가 모호하면 전체 이미지의 변환 초안을 보류한다. 유일하게 짝맞춘 image의 `.JPG`/`.jpg` 차이는 warning으로 기록하고 원래 filename을 보존한다. 이미지 없는 XML 83개는 제외한다.
- 출력: `voc-candidates.jsonl`은 원본 bbox와 선택적 `candidate_yolo_lines`를 가진 별도 검수 형식이다. 학습 `.txt`, data YAML, 자동 split, 표준 materialization manifest를 생성하지 않는다. 기존 `plan-split`/`materialize-knife-yolo`/`review-pack`에 바로 넘기는 입력이 아니다.
- `review-queue.csv`와 `review-sample.csv`는 실제 사람의 판정을 위한 빈 열을 가진다. 원래 split·candidate role·다중 knife·YOLO 개수 차이를 층으로 두고 SHA-256/seed 순서와 round-robin으로 초기 표본을 선택한다. `summary.json`에 각 층의 선택/모집단 수를 남긴다. 좌표 미확정 상태에서는 size stratum을 추정하지 않으며 이미지 확보·좌표 확인 뒤 크기/scene/session 구간 검수를 보완해야 한다.
- knife annotation이 없는 이미지는 항상 `negative_unverified`다. 권리·실제 knife 부재/라벨 완전성·좌표·decode·near duplicate·session grouping·공통 tuning/final-test·recipe 승인 전에는 R1/H1에 반입하지 않는다. `reviewer`는 비워 두며 AI 제안을 사람 판정으로 기록하지 않는다.

실행은 repository root의 활성 Python 환경에서 위 README 명령을 사용한다. 새 출력 디렉터리가 필요하며 exit `0`은 구조 audit 실행 성공, `1`은 기록된 구조 오류, `2`는 입력/실행 오류다. exit `0`도 채택·권리·negative 진위·좌표 검증을 뜻하지 않는다. [Cloud dry-run 근거](../reports/datasets/sohas-dasci-metadata-2026-10-02/report.md#cloud-voc-dry-run--2026-10-02)와 검수 gate를 함께 확인한다.

### D3 — training runner/CPU smoke/CUDA handoff `IMPLEMENTED`, CUDA execution `PLANNED`

- YOLO26n primary와 YOLO11n fallback을 development proposal로 둔 config-driven train/evaluate/infer command
- run ID, Git commit, dataset manifest/version, split, seed, model/checkpoint, config, hardware와 command 기록
- Precision, Recall, mAP50, mAP50-95와 per-class metric 자동 수집
- artifact filename, SHA-256, storage reference, evaluation link 기록
- 작은 approved sample의 start-to-finish smoke는 CUDA GPU 또는 Orin 환경에서 실행. 현재 개발 노트북 CPU smoke는 필수 조건에서 제외

사용자 결정으로 2026-09-15에 CPU smoke도 선택적으로 수행했다. YOLO26n, 32 train/8 val, 320 px, 1 epoch, batch 4가 정상 완료되고 checkpoint 재로딩·단일 이미지 inference가 실행됐다. 이는 배관 검증이며 metric 0을 성능 결과로 해석하지 않는다.

CUDA development profile, GPU-required preflight와 review-gated Colab notebook을 추가했다. training invocation은 Git commit, config/data YAML/dataset manifest hash, 환경, metric과 artifact hash를 기록한다. 로컬 CPU에서 CUDA-required preflight가 의도대로 실패하는 것만 확인했으며 실제 GPU full training은 실행하지 않았다.

### D4 — full training and evaluation

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
