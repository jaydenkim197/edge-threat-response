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
