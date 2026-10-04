# 웹 검수 연결 결과 — 2026-10-04

765개 표본 중 309개 판정을 읽어 **미승인 실사 후보 180개(양성 152 / 음성 28)**를 연결했다. 합성 36개·외부 평가 21개는 별도로 구분했다. **학습 승인 0개이며 학습은 실행하지 않았다.** 운영 사이트·이미지·판정·배정·history는 변경하지 않았다.

## 실행 근거

- 코드: `8cd14d95229dc57f82ce2ea3bc88cf139f2f9648`.
- 환경: PC13 Windows, Python 3.12.4. 로컬 Python 3.11.9와 PC13 모두 전체 113 tests 및 compileall 통과.
- Snapshot: 2026-10-04 22:17:41 KST, UTC `13:17:41.002287`–`13:17:41.724454`.
- 입력: 운영 config의 ready source 7개, 초기/추가 immutable pack 8개. ACF는 원본 대기 상태로 제외.
- Config SHA-256: `c48414ac83b3b49ab2b8ff7554d8a368c61b4c458aa3ccccadf99721cfae2348`.
- Policy SHA-256: `37b7acbde9e10f37a816305a3aefef18f15d883eb0b787865e73bf2146ffdb62`.
- 명령: repository root에서 `python -m edge_threat_response.dataset.review_candidates --config data/review/team-server/config.json --policy configs/datasets/review-candidate-policy.json --output-dir data/work/review-candidates/20261004-v1` (`PYTHONPATH=src`, `.venv-ml` Python).
- 원시 산출물: PC13의 ignored `data/work/review-candidates/20261004-v1/`. Manifest, 실사 후보, 보류 목록, 중복 목록, summary, 보고서 6개 파일. Git에는 이 aggregate 보고만 보관한다.

## 현재 pack 범위의 판정

| Source | 준비 | 판정 | 정상 | 문제/모름 | 실사 후보 | 별도 처리 |
|---|---:|---:|---:|---:|---:|---|
| SOHAS | 200 | 98 | 84 | 14 | 84 | 양성 56 / 음성 28 |
| DaSCI 고유 후보 | 93 | 71 | 71 | 0 | 71 | 양성 71 |
| Legacy | 128 | 26 | 25 | 1 | 25 | 양성 25, legacy/보강 후보일 뿐 채택 아님 |
| Simuletic | 114 | 42 | 36 | 6 | 0 | 합성 후보 36 |
| US Mock Attack | 100 | 25 | 21 | 4 | 0 | 외부 평가 후보 21 |
| Dangerous Items | 100 | 30 | 24 | 6 | 0 | 정상 24개도 knife mapping 미확정으로 보류 |
| Open Images | 30 | 17 | 16 | 1 | 0 | 정상 16개도 원본 validation 표본이라 train 전환 보류 |
| 합계 | **765** | **309** | **277** | **32** | **180** | **학습 승인 0** |

미검수 456개, 보류 72개(판정 문제/모름 32 + mapping 24 + 원 split 16)다. 현재 pack 간 exact SHA-256 중복은 0그룹이다. 이는 전체 raw source 또는 유사 중복이 없다는 뜻이 아니다.

## 보존·승인 경계

SQLite `mode=ro`/`query_only`로 8개 pack과 team registry를 읽었다. pack fingerprint·이미지 SHA-256·CSV/evidence 정렬·bbox 범위·registry offset/count를 검증했고, 각 pack의 DB writes는 0이다. 저장된 전체 765개 manifest 행이 `training_approved=false`임을 재확인했다. 검수자 이름·credential·자유 메모는 출력 목록에 포함하지 않는다. 실제 판정 DB를 직접 수정하지 않고 global sample ID와 version/hash만 연결한다.

정상 판정은 두 질문을 만족한 **표본 후보**다. source 전체 품질·본인 인증·knife 부재의 객관적 진실·좌표 규약·권리·학습 채택을 증명하지 않는다. bbox area는 진단값이고 최종 small-knife cutoff가 아니다. 각 DB에는 일관된 read transaction을 쓰지만 live DB 전체의 한 시점 atomic snapshot은 아니며, 사람이 검수하면 새 run ID로 재집계해야 한다.

## 다음 gate

1. SOHAS의 보류 14개를 검수 사이트 담당 작업에서 재확인한다. 이번 집계가 판정을 대신 수정하지 않는다.
2. SOHAS source 전체의 권리·VOC 좌표 규약·annotation audit·near duplicate·촬영/session group과 공통 holdout 격리를 확인한다.
3. 승인 범위를 고정한 뒤 VOC→YOLO materialization과 group-aware split을 연결한다. 이 후보 JSONL을 학습 runner에 직접 넣지 않는다.
4. Dangerous mapping, Open Images 별도 train 표본, 합성/외부 평가 역할은 각각 별도 gate로 유지한다. R1/H1 full training은 승인 manifest가 생긴 뒤 수행한다.

사용·오류·출력 계약은 [검수 기준](../../../docs/dataset-evaluation-criteria.md#6-웹-판정--미승인-학습-후보-snapshot)을 따른다.
