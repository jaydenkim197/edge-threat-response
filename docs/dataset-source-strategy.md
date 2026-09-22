# Dataset Source Strategy

상태: target domain·source 역할 분리·채택 gate `DECISION`, 개별 공개 source의 실제 채택·dataset recipe `PROPOSAL`

이 문서는 공개 dataset의 **이미지 수**가 아니라 현장 CCTV 적합성, annotation, 권리, 중복·누수 위험 및 실험 역할을 기준으로 결정한 source 전략이다. 원본 image, video, annotation 및 model binary는 Git에 넣지 않는다. 실제 파일을 내려받거나 학습에 넣는 행위는 이 문서의 audit gate를 통과한 뒤에만 가능하다.

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
| L0 legacy baseline | 기존 MIDAS 7,361장 development export | 0장 — 사람 review 승인 전 학습 금지 | 승인된 legacy만 별도 **legacy-only** baseline run | 현 데이터의 domain mismatch·반복 배경·원본 split leakage를 숨기지 않고 재현 기준으로 남긴다. |
| P1 primary real-world candidate | SOHAS detection | audit 표본만: stratified 100장 | audit 통과 시 첫 public real-data training source 후보 | knife와 smartphone·wallet·card·banknote 등 similar handled object가 있어 hard negative를 다룰 수 있다. |
| P2 knife-diversity candidate | DaSCI / OD-WeaponDetection knife detection | audit 표본만: stratified 100장 | SOHAS와 **별도** source로 먼저 평가; dedup 통과 전 동시 병합 금지 | knife 종류·거리·가림 보강 후보이나 SOHAS와 lineage/중복 가능성을 먼저 확인해야 한다. |
| E1 external CCTV test candidate | ACF Knife | audit 표본만: 접근 가능 범위 | **Dataset v1 학습에는 0장**. source/session 단위 holdout 외부 평가 후보 | 1920×1080 CCTV, small knife 문제와 직접 맞닿아 있다. 먼저 학습에 섞으면 target-domain 일반화 검증이 사라진다. |
| E2 sequential CCTV test candidate | US Mock Attack | audit 표본만: camera/sequence별 표본 | **Dataset v1 학습에는 0장**. camera/sequence 전체를 함께 다루는 보조 외부 평가·scenario 설계 후보 | 공개 설명상 knife label 수가 적고 연속 frame이라 random image split은 누수 위험이 크다. |
| S1 synthetic viewpoint check | Simuletic CCTV Knife | 필요 시 전체 114장 검수 | primary recipe에는 0장. real-data baseline 이후 별도 synthetic augmentation ablation에만 최대 114장 | target viewpoint에는 가깝지만 synthetic-to-real gap과 작은 표본을 본 결과와 혼동하지 않는다. |
| D1 deferred candidate | Dangerous Items | 0장 | license와 manifest가 확인된 뒤에만 재검토 | small/blur/occlusion 설명은 유망하지만 현재 공개 record의 권리 표시가 충분히 확인되지 않았다. |
| G1 gap-filling candidate | Open Images V7 | 0장 | source audit 후 필요한 visual gap만 제한적으로 선정 | web-image domain이고 image별 license·annotation density 확인이 필요하다. |
| person detector | COCO pretrained model | 별도 custom data import 없음 | person detector sanity/composite adapter의 pretrained source | COCO person pretrained model은 사용 가능하되, COCO knife data를 본 project의 knife training corpus로 자동 채택하지 않는다. |

`stratified 100장`은 source 규모가 100장보다 작으면 전체를 뜻한다. 표본은 knife bbox normalized-size 구간, person co-occurrence, viewpoint, occlusion, negative/hard-negative를 가능한 한 고르게 포함한다. 이 수는 **source 채택 심사량**일 뿐, 최종 학습량이나 연구 표본 수가 아니다.

## 3. First usable training recipe

첫 CUDA 학습은 다수 source의 무검수 결합이 아니라 다음 순서로 진행한다.

```text
L0: 승인된 legacy-only baseline
        ↓  (같은 평가 규칙으로 기록)
P1: SOHAS source audit
        ↓  (통과 시)
R1: SOHAS 기반 real-world knife-only candidate run
        ↓  (DaSCI 중복·품질 audit 통과 시에만)
R2: R1 + 선택된 DaSCI 보강 run — 별도 run ID와 dedup report
        ↓
S1: R2 + Simuletic 114장 이하 synthetic ablation — 선택적, 본 결과와 분리
```

즉, **첫 public training recipe는 SOHAS 단독 후보를 우선 검토**한다. DaSCI, Simuletic, Open Images와 legacy를 처음부터 concatenate하지 않는다. R1/R2/S1 모두 B0~B3의 detector를 바꾸는 실험과 섞지 않고 detector data run으로 별도 기록한다.

SOHAS의 non-knife class는 MVP runtime class를 늘리는 근거가 아니다. knife-only model을 유지하고, audit에서 knife가 없다고 확인된 image만 hard-negative empty-label candidate로 사용할 수 있다. source의 원래 class·annotation은 registry에 보존하며, unified `person + knife` model로 자동 변환하지 않는다.

ACF Knife와 US Mock Attack은 primary training source가 아니라 **외부 CCTV generalization evidence** 후보이다. 사용 가능 권리, raw annotation, camera/location/session metadata가 확인되면 training source와 image·sequence가 겹치지 않도록 source/session 단위 holdout으로 보존한다.

## 4. Mandatory audit gate before import

각 source는 아래 항목을 모두 source registry와 review record에 남겨야 한다.

1. **Origin and rights:** 공식 upstream URL, version/date, download checksum, license text, course research usage 범위와 redistribution restriction.
2. **File and label contract:** image count, decoded count, class map, bbox/polygon format, empty/invalid/orphan labels, annotation completeness.
3. **Target-domain suitability:** elevated CCTV 여부, normalized knife bbox-size distribution, person co-occurrence, occlusion, scene/background, hard negatives.
4. **Leakage and duplicates:** source camera/session/group 추출, exact SHA-256, perceptual-hash near-duplicate 및 filename/source lineage comparison. SOHAS–DaSCI 및 legacy와의 cross-source comparison을 포함한다.
5. **Human review:** 표본별 keep/reject/uncertain 사유와 ambiguous annotation rule. person/knife labels가 모두 필요한 unified model은 별도 completeness audit이 필요하다.
6. **Split and recipe:** raw file을 바꾸지 않는 group-aware split manifest, source contribution, run ID, configuration·manifest hash.

한 항목이라도 불명확하면 `DEFERRED`로 두며, 대량 download·병합·full training·성과 주장으로 넘어가지 않는다. 공용 CCTV/직접 촬영 영상에는 개인식별정보와 동의·보존·접근 권한 정책을 먼저 적용한다.

## 5. Evidence and caveats

- [SOHAS / OD-WeaponDetection 공식 저장소](https://github.com/ari-dasci/OD-WeaponDetection)는 weapon detection dataset과 CC BY-SA 4.0 license를 명시한다. 실제 download package의 version·file manifest·annotation은 아직 audit하지 않았다.
- [ACF 논문](https://pmc.ncbi.nlm.nih.gov/articles/PMC9572610/)은 ACF Knife의 1920×1080 CCTV data와 small-object label 문제를 설명한다. 본문은 3,559장, 표의 한 행은 3,618 labels로 표기하므로 raw manifest가 확인되기 전에는 어느 수치도 project inventory로 쓰지 않는다.
- 같은 논문은 [US Mock Attack source](https://github.com/Deepknowledge-US/US-Real-time-gun-detection-in-CCTV-An-open-problem-dataset)의 5,149 full-HD mock-attack frames와 knife 210 labels를 표기한다. 연속 frame/camera grouping은 raw package에서 다시 확인한다.
- [Simuletic dataset card](https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset)는 114 synthetic CCTV-style person/knife sample과 CC BY 4.0을 제시한다. 이는 real CCTV 성능 근거가 아니다.
- [Open Images V7 facts](https://storage.googleapis.com/openimages/web/factsfigures_v7.html)는 규모·class availability 근거일 뿐, 선택 image의 rights/annotation completeness를 보장하지 않는다.

## 6. Immediate next actions

1. W4의 legacy review CSV를 사람이 판정해 L0 baseline의 사용 가능 범위를 확정한다.
2. SOHAS, DaSCI, ACF, US Mock Attack의 **공식 package/usage terms 접근성**만 확인하고, source별 100장(작으면 전체) audit manifest를 만든다. 아직 training import는 하지 않는다.
3. SOHAS–DaSCI–legacy cross-source exact/perceptual duplicate 검사와 session/source-group report를 만든다.
4. audit 결과로 R1의 실제 source recipe와 external CCTV holdout 가능 여부를 팀이 승인한다.
5. 이후에만 CUDA full training을 run ID·manifest hash·config·artifact hash와 함께 실행한다.
