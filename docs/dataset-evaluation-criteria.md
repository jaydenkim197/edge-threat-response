# Dataset Evaluation Criteria

상태: source 검수 절차와 역할별 판정 기준 `DECISION`; 실제 source 채택·수치 threshold `PROPOSAL`

이 기준은 knife-only detector와 person–knife 사건 평가에 사용할 자료를 검수한다. 논문의 영향력, raw image 수 또는 단일 총점으로 source를 순위화하지 않는다. [Dataset Source Strategy](dataset-source-strategy.md)의 역할별 후보를 **사용 가능 gate → 표본 관찰 → 역할 승인** 순서로 판단한다.

## 1. Gate: 사용 전에 확인할 조건

| Gate | 확인·기록할 증거 | 불충분할 때의 처리 |
|---|---|---|
| 출처·권리 | 공식 upstream, 파일 version·checksum, 실제 package와 README/license의 적용 범위, 학술 이용·재배포 조건 | 권리 충돌이나 미표시가 해결될 때까지 학습·평가 사용 보류. 공개 링크가 있다는 사실만으로 권리를 추정하지 않는다. |
| 이미지·라벨 계약 | decode, image-label pairing, class map, bbox 정확도·누락, knife가 없는 negative의 진위 | 오류가 확인된 sample은 제외·수정 후보로 분리한다. knife가 미표기된 이미지를 empty-label negative로 사용하지 않는다. |
| 독립성·중복 | source/version lineage, SHA-256 exact match, perceptual near-duplicate, 같은 사람·장면·연속 프레임 | 분할이나 다른 dataset 사이의 중복을 해소하기 전에는 병합 또는 독립 평가에 사용하지 않는다. |
| 분할 가능성 | camera/video/session 또는 대체 group ID, train/validation/test 경계 | 촬영 group이 불명확한 자료는 최종 일반화 평가에서 제외한다. 학습 후보로는 출처·중복이 추적되는 범위에서 별도 심사한다. |
| 사건 평가 가능성 | 시간 순서가 보존된 영상, positive와 hard negative, 수동 event start/end 정답 | bbox만 있으면 image/frame-level detector 평가로 한정한다. Event recall·false alert·latency를 계산했다고 주장하지 않는다. |

첫 세 gate가 통과하지 않으면 채택을 보류한다. 마지막 두 gate는 **역할별** 판단이다. 예를 들어 이미지 학습에는 완전한 사건 정답이 필요하지 않지만, 최종 B0~B3 평가에는 필요하다. 확인 상태는 `LINK_CHECKED`, `PACKAGE_CHECKED`, `SAMPLE_REVIEWED`, `ADOPTED`로 구별해 증거 날짜와 함께 기록한다. 논문에 쓰인 수치와 우리 package inventory를 구별한다.

## 2. 표본에서 기록할 관찰값

Source/version과 group 단위로 표본을 뽑는다. 기존 계획의 **100장**은 첫 검수의 작업량 기준이며 통계적 채택 보증이나 최종 학습 수량이 아니다. Knife-positive와 no-knife negative를 따로 포함하고, 가능한 경우 카메라·세션, 원래 split, knife bbox 크기 구간을 걸쳐 뽑는다. 각 구간의 표본 수와 모집단 수를 함께 기록한다.

| 범주 | 기록할 값 | 해석 |
|---|---|---|
| 장면·관점 | elevated/oblique CCTV, 그 외 real, close-up/product, kitchen, synthetic, unclear; 실내 복도/출입구 여부 | 목표 camera와 얼마나 닮았는지. 정면 close-up을 자동 삭제하지 않는다. |
| Knife 크기 | 원본 image 크기, knife bbox의 normalized width/height/area와 분포 | 카메라·입력 해상도 결정 전 임의의 픽셀 또는 면적 cutoff를 만들지 않는다. |
| Person 관계 | person 동반 여부와 사람이 실제로 knife를 들고 보이는지의 관찰 메모 | Knife-only 모델의 필수 라벨은 knife다. Bbox만으로 소지·위협 의도를 확정하지 않는다. |
| 탐지 난점 | 손·팔 가림, blur/compression, 조도, 복잡한 배경, 유사 물체 | 모델 오류 분석·보강 데이터 선정에 사용한다. |
| 라벨 품질 | good/minor_issue/bad/ambiguous, 이유 및 누락·오표기 | negative 후보의 모든 knife 미표기 여부를 특별히 확인한다. |
| 다양성 | 고유 사람·장면·knife 종류·배경·camera/session 수, 반복 frame/near duplicate | 이미지 수와 독립적인 정보량을 함께 본다. |

표본 결과는 `n/N`을 구간별로 제시한다. 100장의 관찰 비율을 전체 source의 정확한 구성비처럼 단정하지 않는다. 불균형이 크거나 애매한 라벨이 나오면 해당 구간을 추가 검수한다.

## 3. 역할별 채택 질문

| 역할 | 승인 시 확인할 질문 | 결과가 말할 수 있는 범위 |
|---|---|---|
| Primary knife training | 정확한 knife label과 실사 장면·서로 다른 source group·검증된 hard negative가 충분한가? | 해당 recipe로 학습된 detector의 후보 성능 |
| Gap-filling augmentation | 현재 오류 유형(작은 칼·가림·거리·조명 등)을 실제로 보완하는가? Cross-source 중복은 없는가? | 별도 run 간 데이터 보강 효과 |
| External image holdout | 학습과 source·장면이 독립적이고, knife/negative bbox 평가가 가능한가? | 외부 CCTV의 detector 성능. 사건 지표는 포함하지 않음 |
| External event holdout | 시간 순서, recording/session, positive·negative 사건과 수동 event start/end가 있는가? | 동일 detector의 B0~B3 event 지표 |
| Synthetic ablation | synthetic과 real을 구분하고 real-only run·동일 holdout을 유지하는가? | synthetic 추가 효과. 실제 CCTV 성능 주장에는 독립 real test 필요 |

Composite person detector와 knife detector를 쓰는 현재 후보 구조에서는 knife 학습 이미지에 person bbox가 필수는 아니다. Unified 2-class detector를 별도로 선택할 때만 **모든 식별 가능한 person/knife의 annotation completeness**를 요구한다. 이 선택 자체는 [P0-05](open-decisions.md)로 남긴다.

## 4. Legacy 128장 review pack에 적용

로컬 `data/review/legacy-development-v1/review.csv`의 기존 행·열은 보존한다. 사람이 8개 contact sheet와 필요 시 원본 이미지를 보고 아래 열에 입력한다. Contact sheet만으로 작은 bbox·가림이 구분되지 않으면 `unclear` 또는 `uncertain`을 사용한다.

| CSV 열 | 허용 값 | 판정 기준 |
|---|---|---|
| `domain` | `target_cctv / useful_real / closeup_product / kitchen / web_misc / unclear` | 시점과 장면의 용도 분류. `target_cctv`는 실제 목표와 유사하다고 **보이는** 장면이며 촬영 출처를 증명하지 않는다. |
| `label_quality` | `good / minor_issue / bad / ambiguous` | knife 라벨의 위치·범위·실물 여부. 정답 규칙 자체가 불명확하면 `ambiguous`. |
| `person_cooccurrence` | `yes / no / unclear` | 같은 이미지에 식별 가능한 person이 있는가. Person bbox 라벨 존재 여부와 구분한다. |
| `small_or_distant_knife` | `yes / no / unclear` | 장면 맥락상 작거나 멀게 보이는가. 픽셀 threshold를 임의로 고정하지 않는다. |
| `occlusion` | `none / partial / severe` | Knife의 가림 정도. 판정 불가이면 `notes`에 설명한다. |
| `exclude` | `yes / no / uncertain` | 명백한 오라벨·손상 등은 `yes`, 품질이 정상인 close-up은 domain만 분류한 뒤 `no` 가능, 보류는 `uncertain`. |
| `reviewer` | 실제 사람 이름/식별자 | AI 제안만으로 채우지 않는다. |
| `notes` | 자유 서술 | 제외 사유, watermark, 중복 의심, bbox 오류 또는 추가 검토 사유. |

128장 검수 결과는 source/version·split·bbox-size 구간별 `reviewed / bad / ambiguous / exclude / uncertain` 수와 장면 구성으로 집계한다. 이 표본만으로 나머지 7,233장을 일괄 삭제하거나 승인하지 않는다. 필요하면 문제 구간을 추가 검수한 뒤 L0의 전체/선별/역사적 baseline 중 역할을 결정한다.

AI가 먼저 제안하는 경우 별도 초안으로 표시하고 사람이 원본을 확인해 `reviewer`와 최종 판정을 남긴다. 이 절차가 끝나기 전까지 L0 full training 승인은 `PLANNED`다.
