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

## 2. External source findings

| 후보 | 확인된 사실 | 현재 판단 |
|---|---|---|
| COCO | 80-class detection에 `person=0`, `knife=43`; COCO 2017 train 118,287 / val 5,000 | pretrained sanity baseline 후보. CCTV·small-knife 적합성은 sample 검수 필요 |
| Open Images V7 | 약 9M images, 600 boxable classes, 1.9M box-annotated images; boxable class 목록에 Person과 Knife 존재 | 선택적 보강 후보. class subset의 라벨 밀도·license·동시 person annotation을 확인한 뒤 채택 |
| Simuletic CCTV knife sample | 114 synthetic CCTV-style images, person/knife YOLO labels, CC BY 4.0 선언 | pipeline smoke/sample 검수용 후보. 본 실험의 주력 real-world dataset으로 사용하지 않음 |

근거:

- COCO class/config: <https://docs.ultralytics.com/datasets/detect/coco>
- Open Images V7 description: <https://storage.googleapis.com/openimages/web/factsfigures_v7.html>
- Open Images boxable class descriptions: <https://storage.googleapis.com/openimages/v5/class-descriptions-boxable.csv>
- Simuletic dataset card: <https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset>

후보라는 이유만으로 dataset을 다운로드·병합하지 않는다. provider 설명의 숫자와 license 표시는 source record이며, 실제 annotation 품질과 프로젝트 적합성 검증을 대신하지 않는다.

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

### D2 — exporter `IMPLEMENTED`, visual review/import `PLANNED`

- legacy image decode/손상 검사와 deterministic visual-review pack 생성
- source·객체 크기·annotation 형식별 표본, review CSV와 contact sheet 생성
- 승인된 source에 한해서 metadata/subset importer 구현
- source-specific class mapping과 annotation conversion
- polygon-to-bbox 변환이 필요하면 raw 보존과 deterministic processed export를 분리
- 각 후보 50~100장 표본의 CCTV angle, small/distant knife, person co-occurrence, occlusion, negative/hard-negative 검수 기록
- 최종 dataset recipe와 source/session group split 생성

COCO/Open Images 전용 downloader를 일반화해 미리 만들지 않는다. 채택 source와 공식 접근 방법이 정해진 뒤 얇은 importer만 추가한다.

2026-09-15에 group-aware planned manifest를 knife-only YOLO dataset으로 materialize하는 exporter를 구현했다. model-local class는 `0=knife`이고 runtime adapter mapping은 canonical knife ID `1`이다. development default `70/15/15`, seed `20260915`로 생성한 전체 출력은 exact duplicate 3장을 제외한 7,361장/9,057 objects이며 source group과 exact hash의 split 교차는 0건이다. 이 split과 수치는 연구 최종 결정이 아니다.

### D3 — training runner/CPU smoke `IMPLEMENTED`, CUDA profile `PLANNED`

- YOLO26n primary와 YOLO11n fallback을 development proposal로 둔 config-driven train/evaluate/infer command
- run ID, Git commit, dataset manifest/version, split, seed, model/checkpoint, config, hardware와 command 기록
- Precision, Recall, mAP50, mAP50-95와 per-class metric 자동 수집
- artifact filename, SHA-256, storage reference, evaluation link 기록
- 작은 approved sample의 start-to-finish smoke는 CUDA GPU 또는 Orin 환경에서 실행. 현재 개발 노트북 CPU smoke는 필수 조건에서 제외

사용자 결정으로 2026-09-15에 CPU smoke도 선택적으로 수행했다. YOLO26n, 32 train/8 val, 320 px, 1 epoch, batch 4가 정상 완료되고 checkpoint 재로딩·단일 이미지 inference가 실행됐다. 이는 배관 검증이며 metric 0을 성능 결과로 해석하지 않는다.

### D4 — full training and evaluation

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
5. 실제 데이터 저장 위치와 팀 접근 방식

위 결정 전에도 D1과 시스템 Increment A는 독립적으로 구현할 수 있다.
