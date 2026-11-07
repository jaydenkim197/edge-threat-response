# CCTV V3 선별 7장 — 검수 사이트 담당 인계

**새로 등록을 검토할 대상은 7장 팩 하나다. 40장 전체 팩과 총기 표본은 추가하지 않는다.** 이번 작업은 파일·주석·hash·loader 호환성 확인까지 완료했으며 운영 사이트에는 아직 등록하지 않았다.

## 파일 위치

- PC13: `C:\Class6\edge-threat-response\data\review\prepared-candidates-20261107\roboflow-cctv-v3-target-shortlist`
- pack 안의 `review.csv` + `image-evidence.jsonl` + `images/`가 필요하다. 7장·7개 칼 bbox다.
- pack hash(CSV bytes+evidence bytes): `29309739de304388ee8124b0d268234de4bbe041c1f6646ca170baa002094d32`
- 원시 검사: `C:\Class6\edge-threat-response\data\work\roboflow-cctv-v3-20261107`
- 별도 감사용 40장 팩: 같은 상위 폴더의 `roboflow-cctv-v3`. **등록 대상 아님.**

## 내용과 검수 안내

같은 실내·같은 사람의 작은 칼 시연 프레임 6장과 고각 주차장 구도 1장이다. 서로 독립된 7개 scene/session은 아니다. 실제 CCTV 출처·설치 높이·Holding 관계 정답은 아직 확인하지 않았다.

기존 **이름 선택 → 장면(CCTV형/그 외/모르겠음) → 칼 라벨(정상/문제 있음/모르겠음)** 두 질문을 그대로 사용한다. 작은 칼인지·손에 든 물체가 칼인지·bbox 누락이 있는지는 원본을 보고 판단한다. 판독이 안 되면 `모르겠음`을 사용한다. AI 사전 분류를 사람 판정으로 저장하지 않는다. 추가 입력 질문이나 개인 접속 코드를 만들 필요는 없다.

| 팩 번호 | 원 감사 번호 | 장면 proxy |
|---|---|---|
| 1 | 3 | 실내 시연 A |
| 2 | 12 | 실내 시연 A |
| 3 | 15 | 고각 주차장 B |
| 4 | 16 | 실내 시연 A |
| 5 | 21 | 실내 시연 A |
| 6 | 25 | 실내 시연 A |
| 7 | 47 | 실내 시연 A |

## 등록을 진행할 때

권장 ID는 `roboflow-cctv-v3-gap`, 표시명은 `CCTV V3 · 소형 칼 후보 7장`, role은 `candidate`다. 출처는 [공식 프로젝트](https://universe.roboflow.com/weapon-detection-cctv/weapon-detection-cctv-v3-dataset)이고 게시자는 CC BY 4.0을 표시한다. 원 이미지 출처·사용 범위는 미확인으로 남기고, 공개 재게시 전 기존 사이트 절차에 따라 표시·범위를 확인한다. 새 접근 권한이나 공개 범위를 이번 메모만으로 확대하지 않는다.

기존 config/DB/판정/배정/수정 이력·pack ID는 보존한다. 새 후보의 pack hash와 7개 이미지 hash를 재확인하고, 일관된 backup·격리 QA 뒤 append한다. 서비스용 검수 DB는 새 팩에 새로 생성되며 현재 팩에는 사람 판정 DB가 없다. 감사 QA DB를 운영으로 옮기지 않는다. 기존 pack을 재생성하거나 CSV/evidence를 덮어쓰지 않는다.

이 팩은 학습 미승인이다. 검수 정상 판정만으로 M2 train에 자동 추가하지 않으며 원 제공 split도 복사하지 않는다. 같은 실내 프레임이 원래 train·valid에 섞여 있어 source/session 보호 검사가 필요하다. 새 source ID는 학습 후보 정책·RAW 실행 ID에 자동 포함되지 않는다.

## 확인한 것과 남은 것

기존 ReviewStore로 7장 로드·hash·빈 reviewer를 확인했고 격리 QA reviews/history는 각각 0이다. 관련 기존 테스트 12개가 통과했다. 운영 등록·HTTPS/모바일 저장·재접속 확인과 실제 사람 판정은 사이트 담당 후속 작업이다.

[검수 근거·한계](../../reports/datasets/roboflow-cctv-v3-2026-11-07/report.md).
