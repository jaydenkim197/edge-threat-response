# SOHAS 원본 자동 검사와 교차 후보 진단

**SOHAS 5,859장 전체와 웹 후보 765장의 이미지 bytes/decode/dimension 검사를 완료했다.** 정확 중복·원 split 교차 유사 후보가 발견돼 무검수 병합/공식 split 그대로의 독립성 주장은 보류한다. 모든 결과는 미승인이며 실제 학습이나 인간 판정을 수행하지 않았다.

## 실행과 검증

- 날짜: 2026-10-04, PC13 Windows/Python3.12.4. 로컬 Windows/Python3.11.9.
- 원본: 공식 `ari-dasci/OD-WeaponDetection` pinned commit `48860b990e4d4f57fe100248887fceb248475dc8`.
- 코드: full/review screening·가상 bbox CLI는 `f774a1aafd9873901f4a04cf91d54f6de41870b6`; 교차 signature 비교는 `b86a5a65eb492f8f2c9e6b5997ec9387c05e9b85`.
- 양 PC 전체 **124 tests**, compileall 통과. 신규 image screening 5 + bbox 평가 6 tests. synthetic bbox CLI도 PC13에서 실제 실행했다.
- 원본 image Git tree API size 합계와 decoded bytes는 모두 **1,861,407,276 bytes**다. 5,002 train + 857 test. 기존 `core.autocrlf=false` non-cone sparse staging의 두 image folder만 추가했고 기존 raw 파일·검수 pack·DB를 수정하지 않았다. 초기 `sparse-checkout add --no-cone`는 지원되지 않아 기존 non-cone 설정을 확인하고 옵션 없이 실행했다.
- 노트북 전체 복사·Drive 업로드·사이트 restart 없음. 마지막 읽기 전용 점검에서 public `/login` HTTP200, PC13 C 여유 148,066,394,112 bytes를 확인했다.

원시 산출물은 PC13 repository root의 ignored 경로에만 있다:

| 검사 | 원시 위치 | Manifest/input hash |
|---|---|---|
| 새 VOC 구조 audit | `data/source-audit/sohas-voc-full-images-20261004/` | 원본 commit 고정 |
| SOHAS full image screening | `data/work/image-screening/sohas-full-20261004-v1/` | VOC manifest `0dc893b27836677d88a0502c57c417e9b114f8454ee8bff1d00a600b2c981f45` |
| 기존 765개 review-linked image screening | `data/work/image-screening/review-20261004-v1/` | 후보 manifest `0bd947662f5c394ce5d0d941e77982e3f58f550f040a7882cec6949378c90356` |
| 캐시 signature 교차 비교 | `data/work/image-screening/cross-source-20261004-v1/` | full integrity `a51faabbf00099ae617bab7f9b0a7ead54364e770e8d93e25908a24a56e8c845`; review integrity `2dbe142090e3efcc31685d5b3f31446ad2ff67947b68faae0581977acd87fd67` |
| 가상 knife bbox 평가 | `runs/detection-evaluation-synthetic-20261004-v1/` | 입력3개 hash는 summary에 기록 |

Full screening 완료 23:23:34 KST, 교차 비교 완료 23:28:03 KST. Review screening은 22:17 판정 snapshot의 immutable manifest를 사용했으며 이후 human 판정 증가를 반영한 집계가 아니다.

## 원본 구조·decode 결과

- VOC 구조 오류0, knife 객체2,349 / 기존 YOLO knife2,277, knife count 차이58 images, orphan XML83. 이 수치는 실제 이미지 확보 후에도 기존 audit와 일치한다.
- SOHAS image5,859/5,859·review image765/765 decode와 annotation dimension/hash 검사 통과, 개별 오류0. 첫 검사에는 pinned image/XML blob 및 XML SHA-256 일치가 포함된다.
- `pixel-edges`와 `voc-1based-inclusive`는 **각각 5,859개 XML 모두 수치상 호환**한다. 이 검사만으로 원본 좌표 의미를 구분할 수 없다. 공식 pinned 저장소에는 변환 `.py`가 없고 관련 README도 좌표 규약을 명시하지 않아 둘 중 하나를 source의 정답으로 선언하지 않았다.
- EXIF orientation 비기본1장(`orientation=0`). 유효한 회전값이라는 뜻이 아니라 비표준 metadata 확인 대상이다. 자동 회전/라벨 변환하지 않았으며 학습 importer의 EXIF 처리와 좌표 정합성을 확인해야 한다.

## 중복·유사 후보

| 범위 | Image records | Exact pairs | Visual 후보 pairs | Cross-source pairs | 원 split 교차 pairs |
|---|---:|---:|---:|---:|---:|
| SOHAS 전체 | 5,859 | 1 | 5,353 | 0 | 1,575 |
| Review pack만 | 765 | 0 | 399 | 3 | 28 |
| SOHAS 전체 + 다른 source 표본 | 6,424 | 5 | 5,756 | 34 | 1,617 |

교차 비교는 먼저 확보한 full source의 서로 다른 파일을 유지하고, review input 중 이미 full source에 있는 SOHAS200개 사본만 source/hash alias로 생략했다. 따라서 5,859+(765−200)=6,424 records다. 같은 source 안의 distinct exact file은 처음 input에서 보존했다. 합계는 **pair 수**이며 image/group 수나 중복률이 아니다.

- SOHAS 정확 중복1쌍은 같은 원 test split 안에 있다. 선택 export에서는 중복 image를 이중 계수하지 말고 두 annotation의 정합성을 확인해야 한다.
- 추가 exact4쌍은 **SOHAS–Dangerous Items** 사이에서 나왔다. 다른 source 이름이라고 독립 데이터로 사용할 수 없다. 현재 Dangerous는 mapping 미확정 gate도 유지한다.
- SOHAS–DaSCI 고유 후보에 유사 장면 후보가 있다. 기존 93장의 byte-unique metadata 결과와 모순되지 않으며, byte uniqueness가 camera/session independence를 증명하지 않는다는 뜻이다.
- 이번 범위에서는 Legacy/US/Open Images/Simuletic과의 교차 pair가 없었다. 해당 source의 전체 raw가 아닌 표본이고 dHash 검출 한계가 있어 “전체 overlap 없음”으로 해석하지 않는다.

유사 후보는 grayscale64-bit dHash distance≤4·aspect ratio10% 범위라는 development heuristic이다. Low-information near 비교는 생략하는데 이번 decoded 자료에서는 해당 image0개였다. 재인코딩·crop·flip·다른 시점·small knife 차이를 완전히 검출하거나 구별하지 못한다. Pair를 사람이 확인하거나 보수적인 분할 계획에서 검토하기 전에는 같은 실제 session·확정 중복으로 취급하지 않는다. 원 split 교차 후보가 많으므로 원 train/test를 독립 성능의 근거로 바로 사용하지 않는다.

## Knife bbox 평가기 검증

Canonical detection JSONL과 synthetic GT2개 image에서 TP2/FP2/FN1, small GT2/TP1, verified-negative image1/FP box1을 계산했다. Duplicate box FP·confidence filtering·person 제외·일대일 IoU·분모0·missing/error 거부를 fixture와 CLI로 검증했다. **이 값은 가상 계약 검사이며 학습된 모델 성능이 아니다.**

실제 평가에는 approved image truth·공통 tuning/미사용 final-test·선택/동결된 confidence/IoU/area cutoff·실제 input/weight/config provenance가 필요하다. 이 도구는 mAP·사건 오경보/h·실기기 지연을 대신하지 않는다. [실행 계약](../../../docs/training-cuda-handoff.md#knife-bbox-후보-평가--2026-10-04).

## 남은 승인·실물 작업

1. Human 판정의 보류·negative completeness·선정 source 범위를 확정한다. 표본 정상 판정을 source 전체 승인으로 확대하지 않는다.
2. SOHAS license notice 충돌·실제 사용/외부 배포 범위, 좌표 의미, EXIF 처리, near pair·camera/session group과 common holdout 격리를 확인한다. 기술 검사는 권리 판정을 대신하지 않는다.
3. 승인된 selection/group/좌표 계약으로 VOC→YOLO materialization과 R1/H1 manifest를 생성한다. approval 파일을 자동으로 승인하지 않고 **full training은 미실행**이다.
4. 카메라/모형 소품/촬영 동의·장소·세션, Orin 수령·접속은 실제 준비 후 진행한다. 공개 bbox 표본을 수동 사건 start/end 정답으로 대신하지 않는다.

검사 명령·안전 경계는 [검수 기준](../../../docs/dataset-evaluation-criteria.md#7-사람-검수-전-가능한-이미지-자동-검사)을 따른다. 코드·aggregate 보고만 Git에 넣고 raw image·hash별 판정·DB·pair 전체는 공개하지 않는다.
