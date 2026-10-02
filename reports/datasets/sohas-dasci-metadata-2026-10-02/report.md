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
