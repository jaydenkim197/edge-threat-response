# SOHAS–DaSCI 공식 Git metadata 대조

검사일: 2026-10-02  
범위: `ari-dasci/OD-WeaponDetection` `master` commit `48860b990e4d4f57fe100248887fceb248475dc8`의 Git tree 항목. 원본 image 다운로드·decode·학습은 수행하지 않았다.

## 방법

1. 공식 저장소의 [DaSCI image tree](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/56fae9b20a3863051e510d001decd466847e9b60), [SOHAS train image tree](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/e9bd454863bd05af3c534e803609189149dc51e0), [SOHAS test image tree](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/8c1377c477bbd58c25d05f37b7a4c63ede1fcda1)를 GitHub REST API로 조회했다.
2. 각 이미지의 확장자를 뺀 basename을 소문자로 정규화하고 SOHAS train/test 합집합과 DaSCI를 대조했다.
3. 일치한 basename의 Git blob ID까지 비교했다. 같은 blob ID는 해당 저장소에서 같은 파일 바이트를 뜻한다.
4. SOHAS [train XML tree](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/039100e69b289cbb6caedc1d939be879b7c0ee08)와 [test XML tree](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/9b9aed687e6f24e7bc8a88a58dbe67fa33e71de2)의 basename을 이미지와 비교했다.

## 결과

| 항목 | 수 |
|---|---:|
| SOHAS train/test 이미지 | 5,002 / 857, 합계 5,859 |
| DaSCI 이미지 | 2,078 |
| DaSCI–SOHAS 동일 basename·동일 Git blob 이미지 | 1,985 |
| DaSCI에서 SOHAS와 바이트가 다른 후보 | 최대 93 |
| SOHAS XML / image에 대응하지 않는 XML | 5,942 / 83 |

과거 제안의 `1,549 basename overlap → 최대 529 추가`는 이 공식 snapshot의 **이미지 파일**로 재현되지 않는다. 따라서 DaSCI-only와 SOHAS+DaSCI를 신규 detector의 필수 독립 데이터 실험으로 취급하지 않는다. 93장은 perceptual near-duplicate, 라벨 품질, camera/source lineage, 목표 CCTV 적합성을 아직 확인하지 않은 **후보 상한**이다. SOHAS knife-positive·negative 수 및 knife 누락 라벨도 이 metadata 대조만으로 검증되지 않았다.

## 후속 gate

- SOHAS의 README/License 표기 충돌과 실제 적용 권리를 확인한다.
- 원본 image/XML pairing·decode·class map·knife-negative 진위를 표본 검수한다. orphan XML은 이미지와 결합하지 않는다.
- source/camera/session 및 exact/near duplicate를 고려해 split한 뒤, 동일 공통 평가셋에서 신규 detector 후보를 비교한다.

## 후속 검증 — SOHAS YOLO 배포본과 실제 annotation

같은 upstream commit에서 GPT가 지정한 YOLO 배포본을 별도로 확인했다. [image tree](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/26a662950b9d1f66117ce91e3174288d153ba674?recursive=1)와 [label tree](https://api.github.com/repos/ari-dasci/OD-WeaponDetection/git/trees/d54448f1c4b946514086278d536ea52a9f74c54b?recursive=1)는 각각 5,859개이며 tree 응답은 truncated=false다. DaSCI와 같은 image blob은 여전히 1,985개다. YOLO image 대응 orphan label은 0개다. XML source의 orphan 83개와 혼동하지 않는다.

원격 학습 PC의 `data/source-audit/sohas-upstream/`에 Git partial/sparse clone으로 README·license·YAML·YOLO label과 VOC XML만 받아 읽기 전용 대조했다. image 파일은 checkout하지 않았다. Git metadata를 포함하는 staging이며 데이터 학습·공유 Drive 업로드는 하지 않았다.

| 실제 annotation 관찰 | 결과 |
|---|---:|
| YOLO label 파일 | 5,859 |
| knife class 2가 있는 image label | 2,277 |
| knife annotation이 없는 image 후보 | 3,582 |
| YOLO 전체 object rows | 5,859; 각 image에 한 row |
| 빈 label / 5-token 형식 아닌 row | 0 / 0 |
| image에 대응하는 VOC XML 부재 | 0 |
| 대응 VOC의 knife objects | 2,349 |
| YOLO의 knife objects | 2,277 |
| knife object count가 다른 image | 58 |

예: `knife_108`은 XML knife 2개/YOLO 1개, `knife_1162`는 XML 3개/YOLO 1개다. knife count 총 차이는 72개다. 따라서 **준비된 YOLO label을 그대로 최종 학습에 쓰지 않는다**. VOC의 모든 knife bbox를 재변환하는 경로를 우선 검토하고, 실제 이미지에서 XML과 YOLO의 annotation 완전성·좌표 규칙을 확인해야 한다. 위 숫자는 라벨 내용이며 이미지의 진실을 사람이 확인한 결과가 아니다. 5-token 검사는 class/좌표 범위·bbox 정확도 검증도 아니다.

원격 generated 증거는 `data/source-audit/sohas-label-inventory.json`과 `sohas-voc-yolo-comparison.json`이다. XML 비교는 같은 원래 train/test의 basename으로 짝을 맞추고 모든 object/name의 knife 수와 YOLO raw class 2 row 수를 비교했다. YOLO class map은 공식 `dataset.yaml`의 pistol/smartphone/knife/monedero/billete/tarjeta이며 knife-only 변환 시 raw 2→model-local 0이다.

## GPT의 3개 screening run 제안에 대한 판단

- 동일 모델·입력과 공통 평가셋, 오류 분석, 짧은 screening 후 최종 학습은 타당하다.
- SOHAS/DaSCI를 독립 source로 가정한 세 모델의 일반화 해석은 부적절하다. Combined의 추가 정보는 고유 후보 최대 93장에 제한된다. 다만 DaSCI-only가 소규모 subset 비교로 전혀 무의미하다는 뜻은 아니다.
- source별로 각각 holdout을 떼기 전에 두 source 전체의 exact/near duplicate와 session을 묶어 분할해야 한다. 같은 image가 다른 source의 train에 남으면 공통 평가도 누수다.
- 후보와 threshold를 고르는 자료는 tuning set이며 final test가 아니다. 두 source가 크게 겹치므로 SOHAS↔DaSCI 성능 차이를 독립 domain generalization으로 주장하지 않는다.
- 동일 50 epochs·auto batch·patience만으로 학습 예산이 같아지지 않는다. screening 설정은 전체 annotation·split·dataset size가 확정된 뒤 명시적 optimizer/batch와 step budget·schedule을 함께 정한다.
- 우선 R1/H1, 이후 U1/T1/S1을 조건부로 검토하는 현행 전략을 유지한다. 권리·image/label·human review·split gate를 통과하기 전 학습은 시작하지 않았다.

## Cloud VOC dry-run — 2026-10-02

- 환경: Linux x86_64 Cloud, Python 3.12.14, pure/review `.venv`. 작업 시작에 clean `work` branch를 `git pull --ff-only origin main`으로 `0d9ce87`까지 갱신했다.
- 공식 upstream은 `--filter=blob:none --no-checkout --depth=1` clone 후 README/license/YAML·VOC XML·YOLO label만 non-cone sparse checkout했다. HEAD는 `48860b990e4d4f57fe100248887fceb248475dc8`, staging 59 MB, image checkout 0개다. source checkout `git status --short`는 clean이다.
- 신규 `etr-dataset sohas-voc-audit`는 image Git tree를 기준으로 split-local pairing하고 XML/YOLO bytes의 blob과 SHA-256을 기록한다. 이미지 decode 또는 실제 bbox 품질을 증명하는 검사가 아니다.

```bash
.venv/bin/python -m unittest discover -s tests -q
.venv/bin/etr-dataset sohas-voc-audit --source-root data/source-audit/sohas-upstream --output-dir data/source-audit/sohas-voc-cloud-final
```

| 관찰 | 결과 |
|---|---:|
| 전체 기존+신규 테스트 | 70 passed, 실패/skip 0 |
| paired image Git metadata | 5,859 |
| VOC knife objects / YOLO knife objects | 2,349 / 2,277 |
| knife-positive candidate / negative-unverified | 2,277 / 3,582 |
| knife object count mismatch | 58 images |
| 제외된 orphan XML | 83 |
| XML filename의 대소문자만 다른 항목 | 181 warnings |
| 최종 구조 error / CLI exit | 0 / 0 |
| 원본 이미지 checkout / decode | 0 / 미수행 |
| 검수 대기 초기 표본 | 100 |

초기 점검의 181 filename 불일치를 조사한 결과 전부 `.JPG`/`.jpg` 등 대소문자만 달랐다. split/stem으로 유일하게 짝맞춘 파일에 한해 대소문자 차이를 warning으로 허용하고 raw spelling을 보존했다. 진짜 filename 불일치·중복 pairing은 계속 보류한다. `knife_108`의 2개, `knife_1162`의 3개 객체 보존과 모든 5,859행의 `training_approved=false`, 빈 `reviewer`를 generated JSON으로 검증했다.

원시 출력은 ignored `data/source-audit/sohas-voc-cloud-final/`의 `voc-candidates.jsonl`, `issues.jsonl`, `summary.json`, `review-queue.csv`, `review-sample.csv`다. 원래 split·positive/negative·다중 knife·count mismatch 층별 모집단/선택 수를 summary에 남겼다. 예를 들어 test의 다중 knife 15개를 모두 포함하고 train의 다중 knife는 43개 중 17개를 선택했다. 표본은 사람이 아직 검수하지 않았으며 좌표 미확정 상태의 크기 분포·camera/session 대표성도 증명하지 않는다.

기본 coordinate convention은 `unknown`이고 모든 candidate YOLO lines는 빈 목록이다. 두 명시적 convention의 변환은 synthetic 좌표 fixture에서만 확인했다. 원본 이미지와 convention 근거를 확보하기 전 실제 학습 라벨을 생성하지 않았다. 상세 계약은 [모델·데이터 계획](../../../docs/model-data-plan.md#sohas-voc-source-specific-audit)에 있다. 권리 충돌, negative 진위, 누락 bbox, near duplicate/session grouping, 공통 tuning/final-test 및 R1/H1 승인은 계속 gate다. 실제 full training·Drive 업로드는 수행하지 않았다.

## Windows 학습 PC 재검증 — 2026-10-02

- 로컬→원격 SSH 연결을 확인하고 원격 main을 `0b51dd4`로 fast-forward했다. 기존 GPU 환경을 재사용했으며 전체 70 tests가 원격 0.554 s, 로컬 1.212 s에 통과했다.
- 첫 audit는 `core.autocrlf=true` source checkout의 XML 4,686개에서 `Local source bytes differ from pinned Git blob`로 실패했다. clean Git status는 checkout byte identity를 보장하지 않는다. 실패 출력 `data/source-audit/sohas-voc-pc13-20261002/`와 기존 source를 보존했다.
- 별도 `sohas-upstream-byte-exact/` staging을 clone-local `core.autocrlf=false`로 만들고 같은 upstream commit·label/XML-only sparse checkout을 사용했다. 원본·검사 코드·전역 설정은 수정하지 않았다.
- `etr-dataset sohas-voc-audit --source-root data/source-audit/sohas-upstream-byte-exact --output-dir data/source-audit/sohas-voc-pc13-byte-exact-20261002`: exit 0, error 0, images 5,859 / VOC knife 2,349 / YOLO knife 2,277 / mismatch 58 / orphan 83 / case-only warning 181로 Cloud와 같은 집계다. 100개 review sample이 생성됐다.
- 이미지 checkout 0, coordinate `unknown`, human review pending, training 승인 false 상태다. 실제 학습·Cloud SSH 복구·background job 지속·Drive 업로드는 이번 검사로 검증하지 않았다.
