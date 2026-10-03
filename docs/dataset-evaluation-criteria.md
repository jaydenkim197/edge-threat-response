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

SOHAS의 2026-10-03 [내부 연구 준비 범위](dataset-source-strategy.md#sohas-내부-연구-준비-범위--2026-10-03)는 제한된 원본 sample 확보·검수와 최종 채택/외부 배포를 분리한다. 두 공개 CC notice와 공식 연구 공개 설명을 보존해 sample 검수는 진행하지만, license 표기 차이 해결·human review·recipe 승인을 완료했다고 간주하지 않는다. 이전의 일괄 보류를 이 명시적 내부 준비 범위로 구체화한다.

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

## 5. SOHAS 로컬 웹 검수

`tools/sohas_review_images.py`가 생성한 원본 이미지·`review.csv`·`image-evidence.jsonl` pack을 `tools/start_review.ps1` 또는 `etr-review --review-dir PATH`로 연다. Python 표준 라이브러리 서버이며 loopback에만 바인딩한다. 이미지/판정의 외부 전송, 로그인·공개 배포, bbox 수정이나 학습 기능은 없다. 현재 100장 pack은 `data/review/sohas-click-review-20261003/`이다.

- 검수자는 실제로 확인하는 사람의 이름/식별자를 직접 입력한다. 기본값은 빈칸이다.
- 2026-10-03 사용자 요청으로 기본 화면은 **두 질문**으로 줄였다. `domain=target_cctv/non_target/unclear`는 CCTV형/그 외/모르겠음이고, `annotation_verdict=ok/problem/unclear`는 정상/문제 있음/모르겠음이다. `review_schema=simple-v2`로 구별한다. 실제 검수자와 두 답이 필수이며 문제 있음은 한 줄 메모가 필요하다. 모르겠음은 추가 메모 없이 보류할 수 있다.
- 정상은 **모든 보이는 칼의 박스 위치와 누락 여부를 확인했다는 통합 답**이다. Knife 라벨 0개 표본에서는 실제 칼이 없음을 뜻한다. 이에 따라 기존 열에는 정상→`good/yes/no`(품질/완전성/제외), 음성 정상→`negative_knife_absence=yes`를 기록한다. 이는 사람이 누른 통합 답의 명시적 의미이며 AI 추정이 아니다.
- 양성 문제 있음은 잘못된 박스 또는 누락을 뜻하지만 어느 쪽인지는 메모로 구별한다. `label_quality=bad`, `bbox_completeness=unclear`, `exclude=uncertain`으로 기록해 자동 삭제하지 않는다. 음성 문제 있음은 실제 칼을 발견한 경우이므로 부재 `no`·완전성 `no`다. 모르겠음은 ambiguous/unclear/uncertain이며 확정 negative가 아니다. Fine-grained minor issue는 이번 UI에서 별도 수집하지 않는다.
- 사람 동반·작은 칼·가림과 독립된 처리 판정은 기본 화면에서 제외한다. 크기는 원본 evidence로 분석하고 필요할 때 특정 오류 구간만 추가 검수한다. ‘그 외’라고 자동 제외하지 않으며 2-question sample review가 전체 source/좌표/학습 승인을 대신하지 않는다. 박스는 계속 원본 XML raw 좌표의 시각화다.
- 기존 상세 CSV enum·판정·이력은 보존하고 일괄 변환하지 않는다. 과거 일반 실사/제품/주방/웹사진은 화면에서 ‘그 외’로 표시하지만 편집 전 원래 값은 그대로다. 재판정한 행만 새 protocol로 저장한다. 수정 전 상세 payload는 history에 남는다. 두 protocol을 합산할 때 coarse verdict와 기존 상세 관찰을 같은 해상도의 정답으로 취급하지 않는다.
- `1/2/3`은 정상/문제 있음/모르겠음, 좌우 화살표는 이전/다음이다. 질문을 중복하는 별도 빠른 판정 버튼은 제거했다.

완성된 판정은 SQLite transaction으로 저장하고 수정마다 검수자·UTC 시간·version·이력을 남긴다. 서로 다른 탭에서 같은 행을 수정하면 오래된 version의 덮어쓰기를 차단한다. 원본 CSV·이미지는 보존하며 CSV 내려받기는 원본 출처 열과 최신 판정을 병합한 별도 파일이다. 라이선스·좌표 확인 열은 이 UI에서 승인할 수 없다. 브라우저 임시 입력과 SQLite 완료 기록을 구분하며 다른 PC/브라우저로 임시 입력이 동기화되지 않는다.

검수 데이터는 ignored 로컬 파일이므로 Git push로 백업되지 않는다. 재개하려면 동일 pack과 `human-review.sqlite3`를 보존한다. 이 단락은 기존 단일 PC 도구의 계약이다. 팀원 공동 검수에는 아래 PC13 중앙 서비스를 사용한다. SOHAS 신규 후보의 준비가 팀원의 Legacy L0 트랙을 대체하지 않는다.

### 팀원 배포 가능 범위

2026-10-04부터 팀원 공동 작업의 기본 경로는 [PC13 중앙 웹 검수 서비스](team-review-deployment.md)다. PC13의 Python/SQLite 서버가 이미지·개인 코드 인증·중복 없는 배정·판정 이력을 관리한다. 팀원은 사이트와 개인 코드만 사용하며 Python·CSV·Git 설치가 필요 없다. 이전 localhost 도구는 기존 기록 확인용으로 보존하되, 중앙 사용 시작 후 그 DB에 새 판정을 병행 기록하지 않는다.

PC13의 루프백 서버와 시작 작업, 외부 HTTPS의 관리자 로그인·이미지 로딩은 검증했다. 팀원 개인 계정의 실제 판정 저장·재접속은 첫 검수 시 확인한다. 인증이 없으면 원본 이미지/API는 반환하지 않으며, 공개 GitHub에는 이미지·DB·접속 코드를 넣지 않는다. 중앙 서비스도 두 질문의 표본 검수만 제공할 뿐 원본 권리, 좌표, 전체 source, 학습 채택을 승인하지 않는다.
