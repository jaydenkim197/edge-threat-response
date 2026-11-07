# CCTV V3 제한 표본 검수 — 2026-11-07

**CCTV V3 전체를 다음 M2 학습의 주력으로 채택하는 것은 보류하고, 관련성 있는 7장만 사람 검수 후보로 남긴다(`PROPOSAL`).** 50장 주석 중 47장 이미지를 확보·검사했다. 확보분의 칼 포함 이미지는 40장이지만 목표 고각 CCTV와 가까운 사례는 1장이며, 별도 고정 실내 시연 영상 6장이 작은 칼 보강 후보였다. 7장은 시각적으로 두 장면 계열이며 7개의 독립 촬영 세션이 아니다.

현재 계획과 맞는 작업은 이 정도의 제한 조사다. 원본 전체 확보나 세 후보의 검수 완료를 M2·P430 촬영의 선행 조건으로 추가하지 않는다. 11/20 모델 동결·11/30 마감은 유지한다. 이번 작업에서 학습과 운영 검수 사이트 등록은 수행하지 않았다.

## 1. 확보 범위와 버전

대상은 [Weapon Detection CCTV V3](https://universe.roboflow.com/weapon-detection-cctv/weapon-detection-cctv-v3-dataset)다. 공식 overview의 등록량은 2,614장이다. [공개 export v1](https://universe.roboflow.com/weapon-detection-cctv/weapon-detection-cctv-v3-dataset/dataset/1)은 4,424장(train 3,620 / valid 540 / test 264), 416×416 stretch·흑백·8개 class remap/3개 drop·출력 2개 증강을 표시한다. 이 두 수를 독립 원본 또는 칼 이미지 수로 세지 않는다.

일반 파일 요청은 노트북과 PC13에서 403이었다. 공개 브라우저의 Images → 이미지 상세 → Raw Data와 이미 관측된 `original.jpg` 자산을 통해 수집했다. 로그인·계정 생성·대량 export·유료 API는 사용하지 않았다. 공개 UI의 전체 열람 제한을 우회하지 않았다.

| 항목 | 실제 확보·검사 |
|---|---:|
| 원본 주석을 읽은 이미지 ID | 50 |
| 다운로드·decode·치수·SHA-256 확인 | 47장 / 5,190,473 bytes |
| 원본 파일 미확보 | 3장 |
| 확보 이미지 중 칼 라벨 포함 | 40장 / 44 boxes |
| 칼과 person 라벨 동시 존재 | 34장 — Holding 정답은 아님 |
| 칼 면적이 이미지의 2% 이하인 이미지 | 30장 — 개발용 normalized-area 기준, 거리·COCO small 정의가 아님 |
| 준비한 전체 칼 검토용 팩 | 40장, 운영 미등록 |
| 사이트 담당에게 넘길 선별 팩 | 7장, 운영 미등록·사람 검수 대기 |

처음 공개 혼합 목록 10장과, `class:knife` 필터의 추가 40장을 선택했다. 편의·목적 표본이므로 50장 비율을 전체 2,614장 분포로 일반화하지 않는다. 같은 UI에 `knife`, `Knife`, `weapon`이 구분돼 있으며 `weapon`을 칼로 자동 변환하지 않았다. 표본은 소문자 knife 필터를 사용했다. 첫 10장의 총기 비중을 보고 데이터셋 전체가 총기뿐이라고 결론 내리지 않았다.

`original.jpg`는 Roboflow 프로젝트에 올라온 이미지라는 뜻이다. 최초 카메라 원본이나 무증강 자료임을 보증하지 않는다. 실제 확보본 23장이 이미 416×416이며, 현재 브라우저 주석이 2023년 생성 export v1과 동일한지도 미확인이다. v1의 최종 YOLO class map은 확보하지 않았다. 원본 전체를 학습하려면 버전·클래스 의미·변환을 별도로 확인해야 한다.

## 2. 실제 장면 검토 — AI 사전 검토

47장 contact sheet와 원본, 유사 pair 비교 화면을 확인했다. 아래는 AI가 제안한 용도 분류이며 운영 사이트의 사람 판정이나 Holding 라벨이 아니다. 모든 이미지의 실제 CCTV 출처·설치 높이는 미검증이다.

| 장면 유형 | 이미지 | 이번 처리 |
|---|---:|---|
| 고각 주차장 CCTV와 유사한 구도 | 1 | 사람의 손 주변 작은 칼 라벨을 사람이 재확인할 후보 |
| 같은 실내·같은 인물의 고정 영상 작은 칼 시연 | 6 | 근접 제품사진과 다른 보강 후보. 약 3 m 고각이라고 주장하지 않음 |
| 낮은 위치에서 올려다보는 사무실 시연 | 16 | 기존 Catargiu와 같은 장면 계열·보호 그룹 연결 우려로 보류 |
| 위 사무실의 손·칼 close-up | 5 | 목표 고각·원거리와 차이가 크고 같은 장면 계열이므로 보류 |
| 제품·stock·웹·무술·리뷰 영상 등 다른 칼 장면 | 12 | 목표 domain 보강 우선순위 낮음. SOHAS 재사용 사례 포함 |
| 총기 또는 의미가 넓은 weapon 표본 | 7 | 칼 양성이나 완전한 음성으로 자동 전환하지 않음 |

사람과 칼의 동시 bbox가 있어도 `Holding` 관계 정답은 제공되지 않는다. 작은 칼의 박스가 손 부근에 있는지, 실제 칼인지, 다른 칼 누락이 없는지는 사람의 원본 확인이 필요하다. blade 위주 박스와 전체 칼 경계의 정의도 서로 일치한다고 확정하지 않았다. 원 주석·사진은 수정하지 않았다.

## 3. 기존 자료·증강·분할 위험

기존 코드의 `image_signature`와 `similarity_pairs`를 재사용했다. **15,645개 참조**(SOHAS 5,858 / Dangerous 4,000 / Catargiu 5,424 / 기존 보호 개발셋 263 / US Mock 검수 원본 100)와 대조했다. SOHAS 5,859장 전체, Catargiu 모든 원본, US Mock 실제 5,149 frame 전체를 검사한 것은 아니다. US 100장 참조에는 이미 열어본 83장 개발셋 전부가 포함된다.

| 검사 | 결과·해석 |
|---|---|
| SHA-256 exact byte 중복 | 참조와 0장. 재인코딩·resize 중복이 없다는 뜻은 아님 |
| 기존 dHash≤4 + aspect 조건 | 7장에 참조 유사 후보 존재 |
| aspect가 바뀐 stretch 후보까지 포함한 dHash≤4 | 14장에 참조 유사 후보 존재. 자동 중복 확정·삭제 기준이 아님 |
| AI의 pair 화면 확인 | 10장은 같은 SOHAS 이미지의 resize/재인코딩으로 보임. 4장은 Catargiu와 같은 장면·가까운 프레임 후보 |
| 기존 val/test·보호 proxy group 직접 연결 | 4장. 해당 사무실 장면 계열 전체도 보수적으로 보류 |
| US Mock 검수 100장과 직접 exact/dHash≤4 후보 | 0장. 전체 US 원본과의 중복 부재 증거는 아님 |
| 표본 내부 유사 pair | 14쌍, 그중 원래 train↔valid 교차 2쌍 |

공개 원본 목록에서 같은 방·같은 인물의 `frame*.jpg`가 train과 valid에 섞여 있음을 화면과 주석에서 확인했다. 따라서 제공 split을 신규 독립 평가용으로 그대로 복사하지 않는다. 6장 실내 후보는 하나의 보수적 scene proxy로 묶고, 정확한 recording session은 미확정으로 둔다.

선별 7장은 이번 exact/dHash≤4 검사에서 직접 연결되지 않았고, 참조 중 최소 dHash 거리는 12~16이었다. 추가로 가까운 10개 참조의 aspect-normalized grayscale 비교 화면도 확인했다. 이것은 다른 촬영·미검사 프레임·crop·flip·증강본까지 배제한 완전한 독립성 증명이 아니다. 학습 반입 시 새 source를 포함한 분할·보호 그룹 검사를 다시 수행한다.

## 4. 결정과 다음 적용량

1. **V3 전체 2,614/4,424장을 M2에 바로 넣지 않는다.** 표본에서 고유한 목표 고각 CCTV 자료의 양을 충분히 확인하지 못했고, 기존 source 재사용·같은 장면 반복·클래스 변환 위험이 있다.
2. **선별 7장만 검수 후보로 준비한다.** 게시자 CC BY 4.0 표기와 원 이미지 출처 검증은 별개다. 원본·pack은 PC13에 보관하고 공개 Git에는 이미지·원 주석을 올리지 않는다. 운영 등록은 별도 사이트 작업이다.
3. 사람 검수 결과가 좋아도 7장을 독립적인 대규모 새 데이터셋으로 세지 않는다. M2 소량 보강 여부는 중복·source group·사용 범위와 실제 gap 가치를 확인한 뒤 선택한다. 이번에는 학습·기존 manifest·val/test·weight를 변경하지 않았다.
4. ② BaranGuclu 499장과 ③ Person Weapon Knife Detection 7,946장은 아직 실제 표본 검사를 하지 않았다. 같은 제한 조사 원칙을 적용하되 이들 확보를 M2/T1의 선행 gate로 추가하지 않는다. `weapon` 의미와 기존 source 중복을 먼저 본다.
5. 자체 P430 촬영·bbox/Holding/event 정답은 계속 우선이다. ACF 요청 메일은 **사용자가 11/06 20:58 발송 확인**을 전달한 상태이며 원본·회신은 아직 확보하지 않았다. 이 작업에서 메일함을 독립 확인한 것은 아니다.

현재 위치는 **① 제한 표본 기술 검사 완료 → 7장 사람 검수 후보 인계 준비**다. 세 후보 전체 검수 완료, M2 학습 완료, 실제 Holding 학습 또는 독립 사건 성능 완료로 승격하지 않는다.

## 5. 검수 사이트 준비와 검증

- 선별 팩: `C:\Class6\edge-threat-response\data\review\prepared-candidates-20261107\roboflow-cctv-v3-target-shortlist`.
- CSV+evidence pack hash: `29309739de304388ee8124b0d268234de4bbe041c1f6646ca170baa002094d32`.
- 기존 `prepare_team_review.write_pack`을 재사용했고, 별도 QA DB에서 기존 `ReviewStore`의 실제 로드를 통과했다. 이미지 hash·번호·행 정렬·빈 reviewer를 검증했다. QA의 reviews/history는 각각 0이며 운영 ReviewStore는 생성하지 않았다.
- PC13의 기존 `test_image_screening.py` **5개**, `test_review_web.py` **7개**가 통과했다([기록](checks.json)). 새 후보의 운영 등록·모바일 UI 검증은 아직 하지 않았다.
- 원 source signature·pair·inventory와 운영 config의 전후 hash가 동일하다. 운영 이미지·판정·배정·이력에 쓰기 동작을 하지 않았고 학습 실행도 없다. 실행 중인 서비스는 중단·재배포하지 않았다.
- PC13 인계 메모: `C:\Class6\edge-threat-response\data\handoffs\261107_CCTV-V3_검수사이트인계.md`.
- [사이트 담당 인계](../../../docs/handoffs/2026-11-07-roboflow-cctv-v3-review.md). 40장 전체 팩은 감사용이며 신규 검수 후보는 7장 팩이다. 공통 두 질문을 유지한다.

## 6. 증거와 재현 한계

[집계](summary.json), [50장 목록·AI 분류](sample-audit.csv), [유사 후보](duplicate-candidates.csv), [참조 범위](reference-scope.json), [7장 팩](shortlist-summary.json), [검증](checks.json)을 보존한다. AI 분류를 사람 검수 DB에 입력하지 않았다.

PC13 원본은 `data/source-audit/roboflow-cctv-v3-20261106/`, 원시 감사·contact/pair sheet·격리 QA는 `data/work/roboflow-cctv-v3-20261107/`에 있다. 수집 ZIP SHA-256은 `3d46ab82c263b6f8429301b6d7b6863c53db49fa11d9d05f0092484ed604149d`다. 실행 source는 PC13 commit `8a6ed6c`이며 공개 Git 문서 HEAD와 구분한다.

[감사 worker](audit-worker.py), [선별 worker](triage-worker.py), [검증 worker](verify-worker.py)는 고정 PC13 입력을 쓰는 일회성 증거다. 범용 Roboflow downloader나 학습 CLI를 새로 만든 것은 아니다. 입력 source와 pack이 있어야 재현 가능하며 기존 출력이 있으면 거부한다. 재실행은 별도 복제 작업공간과 새 출력 경로에서 수행하고 변경 script hash를 기록한다. 관련 문서·보고서만 선택 commit/push하며 타 채팅 미커밋 기록은 보존한다.
