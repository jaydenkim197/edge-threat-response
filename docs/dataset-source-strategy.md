# Dataset Source Strategy

상태: target domain·source 역할 분리·채택 gate `DECISION`, 개별 공개 source의 실제 채택·dataset recipe `PROPOSAL`

이 문서는 공개 dataset의 **이미지 수**가 아니라 현장 CCTV 적합성, annotation, 권리, 중복·누수 위험 및 실험 역할을 기준으로 결정한 source 전략이다. 구체 검수 양식과 역할별 gate는 [Dataset Evaluation Criteria](dataset-evaluation-criteria.md)를 따른다. 원본 image, video, annotation 및 model binary는 Git에 넣지 않는다. 학습·평가 채택은 source audit 후 결정한다.

## 1. Target domain — `DECISION`

최종 카메라의 모델·화각·초점거리와 관찰 거리는 아직 미정이다. 그 전까지 dataset 검수와 controlled scenario 설계에 사용할 목표 환경은 다음으로 고정한다.

- 실내 복도·출입구·공용공간을 보는 약 3 m 높이의 **고정형 CCTV**
- 사람을 위에서 아래로 비스듬히 보는 elevated / oblique viewpoint
- 사람과 함께 나타나는 작거나 먼 knife, 손·팔에 의한 부분 가림, 복잡한 배경
- 정확한 pixel-size 기준은 카메라 선정 뒤 다시 측정한다. 현재는 image diagonal 대비 normalized bbox area와 scene/viewpoint tag를 사용한다.

따라서 정면 인물 사진, 제품 사진, 손과 knife의 close-up이 많은 source는 knife appearance 보강에는 쓸 수 있어도 target-domain 성능의 근거가 될 수 없다.

## 2. Dataset roles and application limits — `DECISION`

| 역할 | source | 지금 적용할 양 | 이후 허용 범위 | 이유 |
|---|---|---:|---|---|
| L0 legacy baseline | 기존 MIDAS 7,361장 development export | 신규 1차 recipe에는 0장 | 다른 팀원이 사람 review 후 별도 **legacy-only** baseline run을 담당. 검수 통과 일부의 신규 보강은 별도 L1 후보 | L0의 검수·재현은 핵심 신규 detector 후보의 source audit·학습을 막지 않는다. |
| P1 primary real-world candidate | SOHAS detection | audit 표본만: stratified 100장 | 권리 충돌 해결과 audit 통과 시 첫 public real-data training source 후보 | knife와 smartphone·wallet·card·banknote 등 similar handled object가 있어 hard negative를 다룰 수 있다. |
| P2 knife-diversity candidate | DaSCI / OD-WeaponDetection knife detection | 필요 시 byte-unique 후보 최대 93장 검수 | 실제 visual gap을 메울 때만 SOHAS 보강 실험; 단독·합본 필수 run 아님 | 공식 이미지 파일 기준 2,078장 중 1,985장이 SOHAS와 동일 Git blob이다. 나머지 93장도 near-duplicate·품질·권리 미검증이다. |
| E1 external CCTV test candidate | ACF Knife | 0장 — 논문의 원 저장소가 현재 접근되지 않음 | **Dataset v1 학습에는 0장**. 파일·권리·라벨 확보 시 외부 **이미지** 평가 후보 | 1920×1080 CCTV, small knife 문제와 직접 맞닿아 있다. 영상과 event 정답 확인 전에는 사건 지표를 계산할 수 없다. |
| E2 sequential CCTV test candidate | US Mock Attack | audit 표본만: camera/sequence별 표본 | **Dataset v1 학습에는 0장**. 데이터·시간 순서·event 정답 확인 시 외부 sequence 평가 후보 | 공개 설명상 knife label 수가 적고 연속 frame이라 random image split은 누수 위험이 크다. |
| S1 synthetic viewpoint check | Simuletic CCTV Knife | 필요 시 전체 114장 검수 | primary recipe에는 0장. real-data baseline 이후 별도 synthetic augmentation ablation에만 최대 114장 | target viewpoint에는 가깝지만 synthetic-to-real gap과 작은 표본을 본 결과와 혼동하지 않는다. |
| D1 deferred candidate | Dangerous Items | 0장 | license와 manifest가 확인된 뒤에만 재검토 | small/blur/occlusion 설명은 유망하지만 현재 공개 record의 권리 표시가 충분히 확인되지 않았다. |
| G1 gap-filling candidate | Open Images V7 | 0장 | source audit 후 필요한 visual gap만 제한적으로 선정 | web-image domain이고 image별 license·annotation density 확인이 필요하다. |
| person detector | COCO pretrained model | 별도 custom data import 없음 | person detector sanity/composite adapter의 pretrained source | COCO person pretrained model은 사용 가능하되, COCO knife data를 본 project의 knife training corpus로 자동 채택하지 않는다. |

`stratified 100장`은 source 규모가 100장보다 작으면 전체를 뜻한다. 표본은 knife positive와 no-knife negative, source/version·camera/session 및 knife bbox normalized-size 구간을 가능한 범위에서 나누어 뽑는다. 이 수는 **초기 검수 작업량**이며 전체 source의 정확한 구성비, 최종 학습량 또는 연구 표본 수를 보증하지 않는다.

## 3. 신규 detector 후보 recipe — `PROPOSAL`

L0 재현은 팀원의 독립 트랙이다. 신규 knife detector의 첫 공개 source는 SOHAS로 두되, 출처·권리·라벨·group audit 통과 전에는 학습 recipe를 승인하지 않는다. GPU가 여러 대여도 같은 이미지가 대부분인 DaSCI-only와 SOHAS+DaSCI를 필수 run으로 늘리지 않는다.

| Run | Knife 학습 데이터 | 검증하려는 차이 | 실행 조건 |
|---|---|---|---|
| R1 | SOHAS의 audit-passed knife 양성 및 knife 부재를 확인한 음성 | 공개 실사 기준 detector | SOHAS 권리·annotation·group audit 통과 |
| H1 | R1과 **같은 knife 양성**만 사용; 음성 이미지 제외 | 유사 handheld object 음성의 false-positive 억제 효과 | R1과 같은 split·설정·평가셋을 유지할 수 있을 때 병렬 run |
| T1 | R1 + 직접 촬영한 3 m급 CCTV의 **training session** | 목표 설치 시점의 적응 효과 | 카메라·동의·라벨·독립 tuning/test session 확보 후 |
| L1 | R1 + 팀 검수에서 선별한 legacy 이미지 | 기존 자료의 visual gap 보강 효과 | 팀의 128장 결과와 추가 검수로 적합·고유 이미지가 확인될 때만; 필수 아님 |
| U1 | R1 + DaSCI의 실제 고유·적합 이미지 | 작은 칼/가림 등 확인된 visual gap 보강 | 최대 93장 후보의 near-duplicate·품질 검수 후에만; 필수 아님 |
| S1 | R1 + Simuletic 검수 통과분(최대 114장) | synthetic viewpoint 보강 효과 | real-only R1과 동일한 real holdout을 사용할 때만; 선택 실험 |
| G1 | R1 + 한 종류의 gap-filling source | R1/T1 오류 분석에서 확인된 약점 보강 | Dangerous Items의 권리 확인 또는 Open Images의 개별 image 권리·라벨 검수 후; 선택 실험 |

**우선 학습은 R1과 H1**, 이후 카메라 자료가 준비되면 T1을 검토한다. L1/U1/S1/G1은 GPU가 남는다는 이유로 자동 실행하지 않는다. L1은 팀의 legacy 검수 결과가 긍정적일 때만 검토하며 L0 model의 성능과 별개의 데이터 보강 실험이다. 특히 U1의 기여는 93장 후보의 독립성·target relevance가 입증될 때만 평가한다. T1의 데이터량은 프레임 수로 미리 고정하지 않으며, 촬영 전 session·장면·참여자 단위의 train/tuning/final-test 경계를 정한다. L0와 신규 run은 같은 공통 holdout으로 비교하되, L0의 완료가 R1을 지연시키지는 않는다.

모든 신규 run의 첫 비교에서는 model family/size, pretrained checkpoint, 입력 규격, optimizer·augmentation, seed, **optimizer step 기준의 학습 예산과 schedule**, 평가 threshold 선택 절차를 동일하게 한다. 데이터량이 다르므로 같은 epoch 수만 강제하지 않는다. H1–R1은 음성 포함 **recipe** 비교이지 음성 이미지 하나의 순수 인과효과 증명은 아니다. 공통 **tuning set**에서 후보와 threshold를 고르고 최종 test는 한 번만 사용한다. Detector 선택 뒤 B0~B3는 그 **동일한 최종 weight·detection JSONL**로 실행한다. R1과 H1의 차이가 작으면 상위 후보를 다른 seed로 재실행해 단일 run 우연성을 확인한다.

SOHAS의 non-knife class는 MVP runtime class를 늘리는 근거가 아니다. knife-only model을 유지하고, audit에서 knife가 없다고 확인된 image만 hard-negative empty-label candidate로 사용할 수 있다. source의 원래 class·annotation은 registry에 보존하며, unified `person + knife` model로 자동 변환하지 않는다.

ACF Knife와 US Mock Attack은 primary training source가 아니라 **외부 CCTV generalization evidence** 후보이다. 사용 가능 권리, raw annotation, camera/location/session metadata가 확인되면 training source와 image·sequence가 겹치지 않도록 source/session 단위 holdout으로 보존한다. Bbox만 확보되면 image/frame-level detector 평가에 한정한다. B0~B3 event 지표에는 연속 영상, positive/negative 사건과 수동 start/end 정답이 추가로 필요하다.

## 4. Mandatory audit gate before import

각 source는 아래 항목을 source registry와 review record에 남긴다. 합격·보류·역할 제한 규칙은 [Dataset Evaluation Criteria](dataset-evaluation-criteria.md)를 따른다.

1. **Origin and rights:** 공식 upstream URL, version/date, download checksum, license text, course research usage 범위와 redistribution restriction.
2. **File and label contract:** image count, decoded count, class map, bbox/polygon format, empty/invalid/orphan labels, annotation completeness.
3. **Target-domain suitability:** elevated CCTV 여부, normalized knife bbox-size distribution, person co-occurrence, occlusion, scene/background, hard negatives.
4. **Leakage and duplicates:** source camera/session/group 추출, exact SHA-256, perceptual-hash near-duplicate 및 filename/source lineage comparison. SOHAS–DaSCI 및 legacy와의 cross-source comparison을 포함한다.
5. **Human review:** 표본별 keep/reject/uncertain 사유와 ambiguous annotation rule. person/knife labels가 모두 필요한 unified model은 별도 completeness audit이 필요하다.
6. **Split and recipe:** raw file을 바꾸지 않는 group-aware split manifest, source contribution, run ID, configuration·manifest hash.

권리 불명확, 라벨 오류, cross-source 중복 미해결 자료는 채택을 보류한다. 촬영 세션이 불명확한 자료는 독립 일반화 평가에 쓰지 않는다. 사건 정답이 없는 자료는 detector의 image/frame 평가까지만 허용한다. 공용 CCTV/직접 촬영 영상에는 개인식별정보와 동의·보존·접근 권한 정책을 먼저 적용한다.

## 5. 데이터 보관 방식

- Google Drive의 [모델개발_데이터셋·실험결과](https://drive.google.com/drive/folders/1tBI7EkxKLN41CwHWA60ENXCgOw_0iYiz)를 승인된 원본·검수/분할 명세·학습 결과·독립 평가의 보관 위치로 사용한다. 폴더 구조는 확인했으며 현재 공개 원본 dataset은 업로드하지 않았다.
- **10 GB 미만의 작업용 자료는 로컬 staging 가능**하다. 학습은 Drive 직접 경로가 아니라 로컬/학습 PC에 고정된 사본에서 수행하고, 원본 checksum·manifest·run ID·checkpoint hash와 Drive 보관 위치를 기록한다. transient cache와 중복 사본은 Git에 넣지 않는다.
- 사용 권리 미확정 공개자료 및 동의·접근정책 미확정 자체 CCTV 영상은 팀 공유 Drive 폴더에 올리지 않는다. Google Drive 사용은 source 권리, 개인정보, 데이터 독립성 gate를 면제하지 않는다.

## 6. Evidence and caveats

- [SOHAS / OD-WeaponDetection 공식 저장소](https://github.com/ari-dasci/OD-WeaponDetection)의 README는 CC BY-SA 4.0을 적지만 [`License.md`](https://github.com/ari-dasci/OD-WeaponDetection/blob/master/License.md)는 CC BY 4.0 전문이다. 실제 적용 범위를 확인하기 전에는 라이선스를 확정하지 않는다. Download package의 version·file manifest·annotation도 아직 audit하지 않았다.
- 2026-10-02 공식 저장소 `master` commit `48860b990e4d4f57fe100248887fceb248475dc8`의 [DaSCI 이미지 Git tree](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/56fae9b20a3863051e510d001decd466847e9b60)와 [SOHAS train](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/e9bd454863bd05af3c534e803609189149dc51e0)·[test](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/8c1377c477bbd58c25d05f37b7a4c63ede1fcda1)의 image basename·Git blob ID를 비교했다. DaSCI 2,078장 중 1,985장은 SOHAS와 **동일 basename·동일 blob**이고, 나머지 93장은 byte-unique 후보일 뿐 perceptual uniqueness가 아니다. SOHAS는 5,859 image가 있으나 XML은 5,942개로 image 없는 annotation 83개가 남아 raw import에서 제외해야 한다. 방법과 원자료 링크는 [metadata 보고서](../reports/datasets/sohas-dasci-metadata-2026-10-02/report.md)에 남겼다. 이 audit은 image decode·knife label 완전성·group 독립성 검증을 대체하지 않는다.
- [ACF 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC9572610/)은 ACF Knife의 1920×1080 CCTV data와 small-object label 문제를 설명한다. 3,559 image와 3,618 knife label은 서로 다른 단위다. 논문이 제시한 [원 저장소](https://github.com/iCUBE-Laboratory/The-Armed-CCTV-Footage)는 2026-09-26 접근에 실패했으므로 raw inventory와 사용 가능성은 미확인이다.
- 같은 논문은 [US Mock Attack source](https://github.com/Deepknowledge-US/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset)의 5,149 full-HD mock-attack frames와 knife 210 labels를 표기한다. 연속 frame/camera grouping은 raw package에서 다시 확인한다.
- [Simuletic dataset card](https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset)는 114 synthetic CCTV-style person/knife sample과 CC BY 4.0을 제시한다. 이는 real CCTV 성능 근거가 아니다.
- [Open Images V7 facts](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)는 규모·class availability 근거일 뿐, 선택 image의 rights/annotation completeness를 보장하지 않는다.

## 7. Immediate next actions

1. 다른 팀원은 legacy review CSV 128장을 [검수 기준](dataset-evaluation-criteria.md)에 따라 판정하고 L0를 담당한다. 이는 아래 신규 detector 작업의 선행 gate가 아니다.
2. 신규 detector 담당자는 SOHAS의 실제 사용 조건과 원본 package를 확인하고, knife 양성·음성·bbox-size·camera/source-group별 표본을 검수한다. 현재 Drive에는 원본을 올리지 않는다.
3. SOHAS의 image–XML pairing, class map, source-group, 정확·유사 중복을 확인하고 R1/H1에 공통인 group-aware split과 독립 CCTV 평가 후보를 설계한다. DaSCI의 93장 byte-unique 후보는 필요 시 별도 검수한다.
4. audit 결과와 권리 확인으로 R1/H1 recipe를 팀이 승인한 뒤에만 CUDA 학습을 run ID·manifest hash·config·artifact hash와 함께 실행한다.
5. target 카메라가 준비되면 training/tuning/final-test recording session을 먼저 분리해 촬영하고 T1 도입 여부를 판단한다.
