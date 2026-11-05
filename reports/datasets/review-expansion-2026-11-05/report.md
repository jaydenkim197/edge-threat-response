# 검수 후보 1,630장 추가 배포 — 2026-11-05

**기존 팀 검수 사이트에 SOHAS 800장, Dangerous Items 250장, Open Images train 580장을 추가했다. 전체 준비량은 1,995→3,625장이다.** 새 자료는 전량 사람 검수 대기이며 정상 판정·source 채택·추가 학습 완료를 뜻하지 않는다. 기존 질문 두 개와 이름 선택, 미검수량 정렬을 유지했다.

## 목적과 선정 판단

- 사용자 요청: 검수 인력이 가용한 동안 유망한 학습 후보를 사이트에 더 공급한다.
- 이미 확보한 원본과 기존 pack builder·signature·SQLite backup·batch registry를 재사용했다(`search-first`). 새 site 기능·질문·dependency는 추가하지 않았다.
- SOHAS는 칼 appearance와 휴대폰·지갑·지폐·카드 등 일상 물체의 혼동을 검토한다. Dangerous Items는 고유 칼 표본과 주석상 knife 부재 후보를 보강한다.
- Open Images는 새 train source다. 11월4일 비교에 사용한 기존 validation 30장과 역할을 구분한다. 다양한 칼 형태와 일반 이미지에서의 일반화 저하를 검토하는 보강 후보이며 CCTV 자료로 간주하지 않는다.
- 단순 수량 확대보다 검수 가능한 고유 후보 확보를 우선했다. 새로운 이름만 붙인 재배포 source나 기존 평가용 US Mock·DaSCI의 대량 재반입은 하지 않았다.

## 추가 자료

| Source | 추가 | Knife 주석 양성 | Knife 주석 0 | 작은 칼 후보 | 추가 후 전체 |
|---|---:|---:|---:|---:|---:|
| SOHAS | 800 | 600 | 200 | 62 | 1,150 |
| Dangerous Items | 250 | 150 | 100 | 17 | 400 |
| Open Images train | 580 | 580 | 0 | 13 | 610 |
| 합계 | **1,630** | **1,330** | **300** | **92** | 세 source 합계 2,160 |

작은 칼 후보는 **적어도 하나의 knife bbox 면적 / 이미지 면적 ≤0.02**인 이미지다. 이는 선정 태그이며 최종 연구 small-object 정의나 실제 관찰거리 판정이 아니다. 나머지 1,238개 양성은 주로 appearance 보강 후보다. 전체가 고정·고각 CCTV라고 주장하지 않는다. Kitchen·시연·제품·stock 이미지 등이 포함될 수 있어 공통 domain 질문으로 분류한다.

주석 0인 300장은 **확정 음성이 아니다**. 실제 knife 또는 누락 annotation이 있으면 기존 `문제 있음`과 메모로 표시한다. 검수자가 bbox를 수정하는 기능을 추가하지 않았다. HOI Holding 관계 정답도 생성하지 않았다.

새 image bytes는 총 **414,672,537 bytes**이며 PC13에 보관한다. 노트북에는 운영 script·집계·소량 QA screenshot만 보관했다.

## 출처·입력·보호 경계

- SOHAS pinned revision `48860b990e4d4f57fe100248887fceb248475dc8`. 원본의 CC-BY/CC-BY-SA 공지 충돌과 연구용 작업 사본이라는 한계를 유지한다. [공식 저장소](https://github.com/ari-dasci/OD-WeaponDetection).
- Dangerous Items VOC archive SHA-256 `9c6749a3e36b6935fc468de9b1fb639b16c4caef2c21f5328a44ff210d3e1aa8`, CC BY 4.0 공지. [공식 record](https://zenodo.org/records/13786228).
- 두 source는 기존 immutable RAW inventory의 **train partition에서만** 추출했다. 현재 RAW val/test와 과거 개발 평가 보호 그룹을 새 검수 후보로 반입하지 않았다. 실제 camera/session 독립성을 새로 입증한 것은 아니다.
- Open Images는 공식 V7 download 페이지가 연결한 train bbox/metadata와 Knife MID `/m/04ctx`를 사용한다. 획득된 594장 중 depiction 주석 13장과 유사 후보 1장을 제외해 580장을 배포했다. 이미지별 저작자·원 출처·CC BY 2.0 metadata와 원 annotation·다운로드 hash를 ignored evidence에 보존한다. 개별 권리를 독립적으로 확인했다는 뜻은 아니다. Annotation은 CC BY 4.0 공지다. [공식 형식·다운로드](https://storage.googleapis.com/openimages/web/download_v7.html).
- Canonical knife-only label을 overlay pixel box로 변환하고 source label/image SHA-256, 원 split·group·coordinate contract를 보존했다. SOHAS/Dangerous의 원 좌표 의미는 `source-pixel-edges-assumed-v1`이며 사람 확인 전 확정하지 않는다.

기존 검수 **1,995개 fresh image signature**와 보호 **3,973개 signature 참조**를 사용했다. 보호 참조는 기존 SOHAS 평가 관련 proxy 864개, RAW val/test 2,846개, 이미 열린 개발 비교 263개이며 서로 중복된 참조가 있을 수 있다. SHA-256과 low-information을 제외한 dHash Hamming distance≤4 후보를 보수적으로 격리했다. 새 배치 내부와 source 간에도 같은 검사를 했다. Open Images는 전체 RAW signature cache와도 비교했다. 배포 직전 재검사에서 선택된 1,630개와 검사 대상 사이 exact/visual conflict는 0이다.

Filename/visual proxy와 dHash는 모든 crop·flip·인접 frame 또는 실제 session 독립성을 증명하지 않는다. 원본 출처·권리·label 정합성과 최종 unseen CCTV 평가는 계속 별도다. 기존 source 전체를 이번 작업에서 사람 검수했다고 표현하지 않는다.

## 배포와 이력 보존

- 기존 각 source 아래 immutable batch `20261105-quality-v1`을 추가했다. 선택 메뉴 수는 기존 9개다.
- 0-based 새 ID: SOHAS **350–1149**, Dangerous **150–399**, Open Images **30–609**. 기존 ID·pack fingerprint는 유지했다.
- 운영 task만 잠시 정지하고 DB/config의 consistent backup을 만든 뒤 config를 원자적으로 교체하고 additive registry를 적용했다. 기존 15개 registry 행을 유지하고 새 3개만 추가했다.
- 기존 모든 DB의 users·assignments·reviews·version·history·metadata 등 테이블의 행 수/hash가 전후 동일하다. Team registry만 3행 추가됐다. 새 pack의 운영 테스트 판정·배정은 0건이다.
- 현재 RAW inventory, queue/profile/승인·list/config, 이전 DEV split/승인 파일의 hash를 배포 전후 비교해 불변을 확인했다. 현재 학습 실행을 중단·재시작하거나 새 자료를 현재 queue에 합치지 않았다.
- 배포 직후 snapshot: 전체 **3,625개 / 판정 1,598개 / 재확인 123개**. 새 1,630개는 이 시점 전부 판정 0이다. 작업 중에도 기존 자료의 사람 검수는 증가했으며 실시간 수치는 사이트를 따른다.

## 검증과 한계

1. 별도 SQLite 복제본에서 3개 새 batch × Android/iPhone 크기의 **6개 browser QA**를 통과했다. 자동 저장·저장 version·필수 메모·storageState 재접속·최근 이어가기·reload·stale write 409·기존 구간 판정 불변을 확인했다.
2. 질문 2개, 최소 버튼 높이 46px, 수평 overflow 0, 실제 overlay 이미지 HTTP 200을 확인하고 source별 screenshot을 검토했다. 이는 **Edge Chromium의 Pixel 7/iPhone 13 viewport**이며 실제 Android/iOS·Safari 또는 홈 화면 설치 검증은 아니다.
3. PC13 `.venv-ml` Python 3.12.4에서 `python -m unittest discover -s tests -p test_team_review.py -v`: **13개 통과**. backend/UI code 변경이 없어 전체 suite를 반복하지 않았다.
4. 운영 catalog·batch 경계의 old/new 이미지 smoke가 통과했다. 공개 HTTPS에서도 두 mobile viewport에서 3,625개·변경 source 수량·미검수량 내림차순·공통 두 질문·기존/신규 이미지 표시를 확인했다. Claim은 browser에서 가로채고 review POST는 차단해 운영 테스트 판정/배정을 남기지 않았다.
5. 데이터 검수 확대는 학습 또는 성능 검증이 아니다. B0~B4·모델 구조·평가 분할·최종 D* 선택은 변경하지 않았다.

## 재현 evidence와 다음 작업

PC13 ignored 작업 폴더: `data/review/quality-expansion-20261105-v1/`.

- `packs/{sohas,dangerous-items,open-images}/`: 이미지·review CSV·원 label/provenance 연결 evidence·summary.
- `selection.jsonl`, `exclusions.jsonl`, `preparation.json`, `deployment-audit.json`: 선정·격리·source/input 해시.
- `before-deploy-backup/`: 변경 전 config·모든 DB consistent backup과 status. 같은 PC 디스크 백업이며 오프사이트 사본은 아니다.
- `preservation.json`, `after-migration.json`, `browser-qa-result.json`, `public-check-result.json`: 보존·QA·배포 근거.
- 실행 script: PC13 `data/review/quality_expansion_20261105.py`, 해당 작업 폴더의 `deploy.ps1`. 운영 일회성 산출물로 원본/DB와 함께 ignored 경로에 보관한다. Script hashes는 [aggregate](aggregate.json)를 따른다.

팀원은 기존 [검수 사이트](https://yu-desktop-97msr1i.tail37c267.ts.net/)를 새로 열거나 후보 목록으로 돌아와 동일 두 질문에 답하면 된다. 이미 열린 오래된 탭에서 새 자료가 안 보이면 새로고침한다. 배치가 많아도 CSV 작성이나 새 질문은 없다.

다음 학습용 snapshot은 정상 판정·재확인 결과를 고정하고 현재 RAW val/test와 기존 개발 평가 보호 경계를 재검사해 별도 recipe로 만든다. 새 검수 결과를 현재 실행 중인 queue의 입력으로 덮어쓰지 않는다. 현 웹의 두 질문은 HOI 관계 정답을 대신하지 않는다.
