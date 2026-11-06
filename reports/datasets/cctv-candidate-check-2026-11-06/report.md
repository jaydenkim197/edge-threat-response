# 신규 CCTV 후보 재확인과 M2 적용 경계 — 2026-11-06

**신규 Roboflow 두 후보는 제한 표본 조사 대상으로 유지하되, 확보를 기다리며 M2·실제 촬영을 늦추지 않는 안을 권장한다.** Catargiu 26,528장을 전부 새로운 knife 학습 자료로 세거나, fight/general surveillance 라벨을 knife·Holding 정답으로 사용하는 것은 맞지 않는다. 본 문서는 공개 원출처와 기존 프로젝트 기록을 대조한 조사이며, 새 원본 다운로드·이미지 검수·중복 검사·학습을 실행한 기록은 아니다. 개별 채택과 후속 범위는 `PROPOSAL`이다.

## 1. 원출처에서 확인한 사실

| 후보 | 확인 사실 | 프로젝트 판단 |
|---|---|---|
| [Weapon Detection CCTV V3](https://universe.roboflow.com/weapon-detection-cctv/weapon-detection-cctv-v3-dataset) | overview 2,614장/11개 class 표기, Knife/knife·gun/guns·weapon 등이 함께 표시됨. **[공개 export v1](https://universe.roboflow.com/weapon-detection-cctv/weapon-detection-cctv-v3-dataset/dataset/1)은 4,424장**, train3,620/val540/test264, grayscale·416×416 stretch·8개 remap/3개 drop·학습 예제당 출력2의 offline augmentation | 후보 유지. overview class 목록을 export의 class map으로 사용하지 않음. 2,614와4,424를 독립 실사 이미지/knife 수로 해석하지 않음. 원본 해상도·실제 knife/일상물체 비율·provenance 확인 필요 |
| [CCTV / RoboflowBaranGucluProject](https://universe.roboflow.com/roboflowbarangucluproject/cctv-105k1) | overview499장, pistol/knife/rifle, CC BY4.0 표기. [버전 목록](https://universe.roboflow.com/roboflowbarangucluproject/cctv-105k1/dataset/1)에 v8=499와 v1~7의 서로 다른 증강 수량이 있음. 소개 본문은 미작성. v1은1,029장·grayscale·640 stretch·출력3 | 신규 후보 유지. v8 페이지 직접 fetch는 실패했으므로 v1의 전처리를 v8의 확정 설정으로 옮기지 않음. export/data.yaml·실제 샘플 확인 전 채택/실제 CCTV 비율 미확정 |
| [Catargiu](https://github.com/CostiCatargiu/Yolov12_WeaponDetection) | 26,528은 knife/pistol/long_gun/no_weapon **4클래스 전체**. 저자는 WeaponDataset v11+NoGun v5와 수정 labels를 함께 설명하며 출처에 CCTV 외 영화·훈련·웹 이미지도 포함한다고 명시 | 기존과 크게 겹침. v11 칼 포함 자료의 전체 조사와 M1 반입이 이미 있었음. 새 양성 대량 확보 대상으로 다시 시작하지 않음. NoGun 등 미사용 혼동물체는 실제 미확보/knife 부재·중복 여부 확인 후 보조 후보 |
| [Simuletic CCTV Knife](https://huggingface.co/datasets/Simuletic/cctv-knife-detection-dataset) | 무료114 PNG, synthetic, person/knife, CC BY4.0. card는15개 person-only 이미지와99 knife boxes를 설명함. 자동 viewer의213rows는114이미지와 구별해야 함 | 이미 확보한 합성 후보. 새 실사 M2와 분리한 S1 역할 유지. 새 카드 설명을 과거 프로젝트 검수 판정/라벨에 소급 덮어쓰지 않음 |
| [NTU CCTV-Fights](https://rose1.ntu.edu.sg/dataset/cctvFights/) | 전체1,000video 중 CCTV280/non-CCTV720. 정답은 fight 시작·종료 구간. 등록/신청 승인 절차와 이용 조건이 있음 | knife bbox/Holding GT가 아님. 현 M2/B4의 직접 학습 자료로 사용하지 않고 후순위 |
| [VIRAT](https://viratdata.org/) | 약8.5시간은 **Stationary Ground Release2.0**의11 outdoor scenes/12event types 설명에 해당. 다른 release 및 DIVA 주석은 별도 규격이고 ground는 protection agreement 대상 | 일반 영상·오경보 보조 후보. knife 양성/음성·Holding 정답이 자동으로 생기지 않음. 지금 대량 확보·수동 정답 제작을 추가하지 않음 |
| [Simuletic knife 영상](https://simuletic.com/videos/cctv-knife-detection) | 고정 고각 야간 장면의6초/24fps/464×688 생성 영상. 페이지는 초반 칼 가림도 설명함 | 연속 입력 smoke의 선택 후보. 실사 CCTV 정확도 근거나 자동 사건/HOI 정답으로 사용하지 않음 |

Roboflow의 CC BY4.0 표기는 게시자가 표시한 조건이다. 두 후보의 원 이미지 출처·재배포 관계를 이 표기만으로 검증했다고 할 수 없다. 이름에 CCTV가 있어도 CCTV 원거리 knife 비율과 annotation completeness는 원본 조사 전 미확정이다. NTU/VIRAT의 신청·이용 조건은 일정 판단에 반영하며 별도 법률 조사나 구매/신청을 이번 작업에서 수행하지 않았다.

## 2. 기존 Catargiu와 실제로 다른 부분

[기존 확보 기록](../additional-review-2026-10-26/report.md)은 수정 라벨26,528개와 v11 이미지에 대응하는 **knife-positive 5,429장**을 이미 조사했다. 현재 `tools/prepare_raw_pc13.py`도 고정 수정 라벨 commit `382d925c0d4ce054c0368ac2778c93b94654954d`의 모든 라벨을 순회하고 대응 v11 knife 이미지를 반입하며, 검수 표본793장만 학습한 코드가 아니다.

현재 M1 준비량은 Catargiu **5,424장**, 그중 train **5,100장**이다([기존 RAW 규격](../../../docs/raw-source-training.md), [데이터 전략](../../../docs/dataset-source-strategy.md)). 따라서 “현재793장만 확보했으니26,528장을 새로 넣자”는 해석은 잘못이다. 793은 웹 검수 표본 수다. 본 비교는 고정 프로젝트 버전을 기준으로 하며 최신 README 통계가 과거 원본/라벨 버전을 소급 대체하지 않는다.

현재 README는 추가 NoGun v5를 함께 소개한다. 그것을 조사할 수는 있지만, 이름이나 no_weapon 객체 주석만으로 이미지 전체를 knife-negative로 바꾸지 않는다. knife 누락·동시 등장·기존 자료 중복과 source를 먼저 확인한다. 이 가능성을 새로운 knife-positive 수만 장처럼 표현하지 않는다.

## 3. 일정에 맞춘 적용안 — PROPOSAL

1. **Q1 별도 full run은 생략하는 권장안:** 기존 train의 보류88장을 M2 manifest에 반영한다. 앞서 권장했던 독립 Q1 학습은 현 일정에서는 후순위로 대체한다. 정제와 추가 데이터 효과가 합쳐지므로 전체 recipe 개선으로 보고한다. 이는 새 사용자 승인/학습 실행을 의미하지 않는다.
2. **M2는 n/640 후보1개:** 기존 확보 Open Images 별도 train·Dangerous와 새 Roboflow의 검사 통과분을 후보로 본다. 두 Roboflow는 우선 **각 최대50장, 합계100장**의 원본/주석 표본을 확인하는 제한 조사안을 권장한다. 이 수는 성능 표본 수나 대표성 보장이 아니라 조사 범위의 상한이다. 샘플100장을 실제 확보/검수한 상태는 아니다.
3. 목표는 작은 knife·칼을 든 전신·고각 시점·가림·혼동 음성의 **고유한 보강**이다. product/close-up/총기 위주이거나 원본 접근·클래스 매핑이 불명확하면 다음 후보로 조사 범위를 계속 넓히지 않고 보류한다. 신규 확보가 M2의 필수 선행 조건이 되지 않게 한다.
4. 후보 import에는 semantic class map·좌표/무결성·exact/near duplicate·source family/sequence·보호 그룹 검사를 적용한다. 기존6개 opened 개발셋과 **확대 US Mock83장 전체**를 보호 대상으로 포함한다. 예전21장만 참조하는 고정 목록을 새 M2의 충분한 보호 증거로 재사용하지 않는다. 증강·회색조·해상도 변경본은 SHA만으로 원본 독립성이 확인되지 않는다.
5. phone/ruler 라벨이나 empty knife annotation만으로 완전한 음성을 확정하지 않는다. 모든 이미지를 다중 class로 학습해야 하는 것도 아니다. knife-only detector의 source별 변환을 유지하고 배경 음성의 근거를 기록한다. 원본 주석 RAW 예비 학습에 대한 기존 사용자 허용을 사람 전수 검수 필수 gate로 되돌리지 않는다.
6. **T1 촬영과 bbox/Holding GT 준비는 병행·우선**이다. 자료가 준비되면 공개 후보 조사/조합 반복보다 T1와 HOI 학습을 먼저 진행한다. 최종 B0~B4는 동결 detector·같은 영상/판단 조건에서 비교하며 신규 촬영 final 세션을 보호한다. 11/20모델 동결·11/30개발 마감은 그대로다.

## 4. 이번 확인의 범위

- 2026-11-06 공식 게시 페이지/버전 설명, 현재 프로젝트 importer·기존 확보/학습 기록을 대조했다. 참고 문헌의 숫자는 저자/게시자 설명이며 우리의 검출 성능·실제 CCTV 비율로 승격하지 않았다.
- 기존 파이프라인을 확인하는 `search-first` 원칙을 적용했다. 원본 다운로더·새 dataset importer·새 class map·학습 config를 구현하지 않았다. 운영 사이트/DB/원본 이미지/manifest/split/학습 queue도 변경하지 않았다.
- 특히 두 Roboflow의 실제 이미지 비율·knife 크기·라벨 품질·기존 자료 중복률·버전별 최종 class map은 아직 검증하지 않았다. 표본 조사·채택은 후속 제안이다.
- 문서의 링크·수치/조건·현재 코드/기록과의 일치·Git diff를 확인한다. 제품 코드 변경이 없고 dataset 실행 검증을 하지 않았으므로 제품 테스트/샘플 검사/학습 통과를 주장하지 않는다. 관련 문서 블록만 commit/push하며 타 채팅의 미커밋은 보존한다. Git 식별자는 본 보고서를 추가한 실제 이력으로 추적한다.
