# 데이터 검수 사이트 담당 채팅 인계 — 후보 확대

작성: 2026-10-04 / 개발 채팅. 작성 시 기준 commit: `7352a2a`.

## 요청과 범위

사용자는 후보 데이터셋의 좋은 자료를 넓게 활용하기 위해 **사이트 검수 이미지 확대와 필요한 판정 DB 변경을 사이트 담당 채팅에서 진행**하도록 요청했다. 기존 공통 두 질문과 이름 선택을 유지하고, PC13에서 원본·표본·판정·배정·이력을 보관한다. 이 메모를 작성한 개발 채팅은 사이트/DB를 수정하지 않았다.

목표는 후보 전체를 검수할 수 있게 하고 고유·유망 자료를 단계적으로 늘리는 것이다. 검수 완료가 학습 승인이라는 뜻은 아니다. 기존 SOHAS R1/H1 첫 학습을 모든 후보 검수 완료까지 지연시키지 않는다. 실사 혼합 M1은 후속 제안이며 여기서는 학습·모델 선정·학습 source 자동 병합을 하지 않는다.

## 먼저 확인할 위치

- 로컬: `C:\Users\sukhe\Desktop\종합설계과제(1) - 이석문\03_개발_GitHub`
- PC13: `ssh pc13@100.66.13.6`, 저장소 `C:\Class6\edge-threat-response`
- 운영 안내: [team-review-deployment.md](../team-review-deployment.md)
- 최신 기준: [후보 전체 검수 계획](../dataset-source-strategy.md#후보-전체-검수와-단계적-확대--2026-10-04-작업-추가), [검수 기준](../dataset-evaluation-criteria.md), [남은 작업](../pre-orin-work-plan.md)
- 코드: `src/edge_threat_response/dataset/team_review.py`, `dataset/review_web.py`, `dataset/web_review/`
- 준비/운영 helper: `tools/prepare_team_review.py`, `tools/configure_team_review.py`, `tools/check_team_review.py`
- 운영 설정: ignored `data/review/team-server/config.json`
- 계정/배정: ignored `data/review/team-server/team.sqlite3`
- 각 검수 pack의 판정/이력: `human-review.sqlite3`

작업 시작 전에 AGENTS와 최신 Git 상태를 확인한다. 다른 채팅의 변경을 일괄 stage하거나 덮어쓰지 않는다. 코드/문서만 GitHub에 올리고 raw image·DB·접속 비밀값은 올리지 않는다.

## 추가할 검수 작업

현재 문서상 준비된 첫 표본은 아래 합계 665장이다. 이는 **준비량**이며 현재 인간 완료 판정 수는 PC13에서 다시 확인해야 한다.

| 후보 | 첫 준비량 | 다음 처리 |
|---|---:|---|
| SOHAS | 100 | 확대 1순위. 기존 표본과 겹치지 않는 약 100장 규모의 새 배치를 준비한다. 원 split/group·knife 양성/부재 후보·작은 bbox 등 가능한 구간을 걸쳐 선정한다. 첫 판정의 문제 구간과 진행률을 확인해 새 배치 공개 시점을 조정한다. |
| Dangerous Items | 100 | 원본 knife class 의미 확인이 먼저다. 임시 raw ID 1 추정을 확정값으로 표시하지 않는다. 공식 근거나 사람 확인으로 매핑이 정리되면 고유 표본 약 100장 추가를 검토한다. 해결되지 않으면 보류 이유를 남기고 다른 후보를 진행한다. |
| Open Images | 30 | 추가 학습 후보는 별도 train source에서 권리/knife annotation을 확인한 고유 표본 약 100장으로 준비한다. 기존 validation 표본의 provenance/역할은 보존한다. 라벨이 없다고 knife 부재로 추정하지 않는다. |
| Legacy | 128 | 팀원의 L0 검수 유지. 첫 결과 이후 고유·작은 칼·사람 동반 등 필요한 구간을 선정해 추가 검수한다. 기존 128장 작업을 중복 배정하지 않는다. |
| DaSCI unique | 93 | 준비된 전체 고유 후보 검수 유지. SOHAS와의 exact duplicate 1,985장은 재반입하지 않고 near-duplicate를 확인한다. 원본 전체를 새 데이터처럼 추가하지 않는다. |
| Simuletic | 114 | 공개 표본 전체 검수 유지. synthetic 표시와 lineage를 보존한다. 114장 밖의 자료를 확보했다고 기록하지 않으며 유료 구매/대량 합성 생성은 하지 않는다. |
| US Mock Attack | 100 | 독립 CCTV 평가용. camera/sequence별 부족한 구간이나 애매한 annotation을 선별 재검수한다. 연속 frame을 대량 중복 추가하거나 train으로 이동하지 않는다. |
| ACF | 0 | 공식 원본 접근·권리·annotation이 확보되면 추가한다. 접근 불가라면 잠금/사유 유지. 출처 불명 재배포로 우회하지 않는다. |

약 100장은 **배치 작업량 제안**이지 연구 표본 수나 필수 최종 수량이 아니다. 첫 결과·실제 가용 자료·팀 처리량에 따라 조정하고 결과를 기록한다. SOHAS 첫 배치부터 안전하게 구현·검증해 순차 확대하며, 준비된 새 배치를 언제 노출할지와 작업량을 보고한다. 전체 source 무제한 다운로드는 하지 않는다. 가능한 기존 checkout/metadata/제한된 sample 준비 helper를 재사용한다.

## 기존 이미지·DB 보존은 필수

1. 변경 전 실제 pack별 이미지/판정/history/배정 건수와 SQLite integrity를 읽기 전용으로 확인한다. 쓰기 중인 DB 파일 단순 복사 대신 기존 SQLite backup API로 일관된 백업을 만들고 복구 경로를 기록한다.
2. 새 batch ID·source revision·원 경로/split/group·image/label hash·선정 seed와 범위를 보존한다. 원본·현재 pack·DB를 삭제/초기화/재생성하지 않는다.
3. 현재 코드의 pack fingerprint/sample ID 계약을 확인한다. **기존 pack에 CSV/images만 덧붙이거나, 다른 hash의 새 pack에 옛 DB를 그대로 붙이지 않는다.** 필요한 추가형 migration 또는 batch 연결을 검증하고 기존 sample ID/계정/판정/version/history/미완료 배정을 보존한다.
4. source+hash의 중복을 확인하여 기존 완료/배정 이미지를 새 미검수처럼 내놓지 않는다. 다른 source에서 같은 이미지가 발견되면 lineage와 기존 판정을 연결하고 중복 작업·중복 학습 계수를 막는다. 의도적 재검수는 재검수로 구별하며 이전 판정을 덮어쓰지 않는다.
5. 새 batch가 늘어도 사용자에게 데이터셋 선택 항목과 질문을 잔뜩 추가하지 않는다. 기존 source 선택 안에서 이어서 검수할 수 있게 한다. UI 질문은 `CCTV형/그 외/모르겠음`, `칼 라벨 정상/문제 있음/모르겠음`; 문제일 때만 메모 필수다. 내부 batch/source 정보는 접어서 보여준다.
6. 정상인 비-CCTV 장면도 appearance 보강 가치가 있을 수 있으므로 자동 제외하지 않는다. 문제/모르겠음은 수정·재검수 queue이며 확정 negative/자동 학습 허용이 아니다. 관리자 승인과 일반 웹 판정을 분리한다.

## 검증과 완료 보고

- fixture에서 기존 판정·history·배정 보존, 새 이미지 배정/자동 저장/재접속, old/new batch ID 충돌·중복 방지, 접근 권한과 stale update 처리를 확인한다. QA 판정은 별도 fixture DB에만 쓴다.
- 관련 자동 테스트와 변경 시 전체 테스트, JS 문법·compileall·diff를 확인한다. 이전 개발 기준은 전체 101 tests였으며 현재 코드의 실제 결과를 새로 기록한다.
- 운영 반영 뒤 읽기 전용 `tools/check_team_review.py`와 공개 HTTPS 브라우저의 **정상 HTML form 이름 선택**, 기존 이미지/새 이미지 표시·모바일 레이아웃을 확인한다. 실제 dataset에 가짜 사람 판정을 쓰지 않는다. 실제 저장 QA가 필요하면 별도 QA pack/DB를 사용한다.
- 서비스 변경/재시작은 준비와 검증 뒤 최소한으로 한다. 사용 중 세션·현재 진행 작업을 고려하고 실패 시 백업/이전 catalog로 되돌릴 수 있게 한다. 과거 로그인 Origin 문제의 `Referrer-Policy: same-origin`을 유지한다.
- 새 표본을 확보했다는 사실, 웹에 배포됐다는 사실, 사람이 판정했다는 사실, 학습이 승인됐다는 사실을 각각 구분한다.
- 완료 보고: 후보별 전후 준비/완료/보류 수, 새 batch와 provenance, 보존 확인·백업 경로·migration, test/외부 접속 결과, commit/push/PC13 HEAD, 미해결 gate. 큰 raw/DB/비밀값은 보고서나 Git에 포함하지 않는다.

이 인계는 사이트 담당 채팅의 작업 범위를 지정하는 메모다. 구현 방식·학습 source 비중·모델 채택을 확정한 결정서가 아니다. 실제로 부족한 권한/정보가 있으면 기존 데이터를 보존한 상태에서 사용자에게 질문한다.
