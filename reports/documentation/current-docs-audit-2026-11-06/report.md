# GitHub 주요 문서 최신화 점검 — 2026-11-06

**현재 계획과 실행 증거를 대조해 주요 문서 22개를 갱신했다.** 공개 데이터 detector 비교와 P430/Orin 시범 연동은 완료했으며, 실제 CCTV 데이터·Holding 학습·물리 GPIO·독립 사건 평가는 남아 있다. 이번 작업은 문서 수정이며 새 학습이나 실기기 시험을 실행한 것은 아니다.

## 최신화 목록과 반영 내용

| 파일 | 분류 | 갱신 내용 |
|---|---|---|
| [AGENTS.md](../../../AGENTS.md) | 개발 규칙 | 10/31 규칙을 대체된 목표로 구분하고 B4·11월 동결·실제 Orin 환경 차이를 반영 |
| [docs/project-plan.md](../../../docs/project-plan.md) | 계획·상태 | 현재 마일스톤·필수 범위·동결일·B0~B4 비교·카메라 연동 상태를 갱신하고 과거 진행 기록 구분 |
| [docs/open-decisions.md](../../../docs/open-decisions.md) | 계획·상태 | 완료된 RAW·카메라·inventory와 미결정 D*·운영값·GPIO·실제 GT를 표에서 구분 |
| [docs/architecture.md](../../../docs/architecture.md) | 구조 | B4·RTSP·snapshot의 실제 구현, 공통 FSM, LAN 의존성, 장애 복구 설계 요건을 구분 |
| [docs/mvp-research-specification.md](../../../docs/mvp-research-specification.md) | 연구 범위 | B3 geometry와 B4 Holding 범위, source-level K-of-N, 공통 FSM·최종 파라미터 경계 갱신 |
| [docs/pre-orin-work-plan.md](../../../docs/pre-orin-work-plan.md) | 다음 작업 | 장비 도착 전 대기 목록을 M2·촬영·T1·HOI·Orin/GPIO·최종 평가 작업표로 교체 |
| [docs/model-data-plan.md](../../../docs/model-data-plan.md) | 모델·데이터 | 실제 RAW corpus·학습량·검수 표본·후속 recipe와 보호 평가 자료를 구분 |
| [docs/dataset-source-strategy.md](../../../docs/dataset-source-strategy.md) | 모델·데이터 | 현재 source별 사용 역할과 원본·표본 수, 학습 미반입·평가 보호·ACF 미확보 상태 명시 |
| [docs/dataset-evaluation-criteria.md](../../../docs/dataset-evaluation-criteria.md) | 모델·데이터 | reviewed·DEV·RAW 승인 범위와 이미지 품질 검수·Holding 정답의 차이를 반영 |
| [docs/controlled-experiment-protocol.md](../../../docs/controlled-experiment-protocol.md) | 평가 | 원본 연속 영상·실제 정답 미수집, 동시 촬영 그룹, B4 명시 manifest와 최종 평가 조건 명시 |
| [docs/future-research-human-knife-interaction.md](../../../docs/future-research-human-knife-interaction.md) | HOI | B4를 승인된 11월 범위로 반영하고 합성 연결 검증과 실제 관계 학습을 구분 |
| [docs/hoi-annotation-contract.md](../../../docs/hoi-annotation-contract.md) | HOI | 실제 pair·event GT 미수집과 제한 자료 반입 조건 명시 |
| [docs/orin-runtime-setup.md](../../../docs/orin-runtime-setup.md) | 실기기·운영 | P430 시범 연동 완료와 새 모델·물리 GPIO·정식 자원 측정·복구 미검증 구분 |
| [docs/p430-camera-setup.md](../../../docs/p430-camera-setup.md) | 실기기·운영 | 해결된 401·timeout 기록과 현재 촬영·정답·통합 작업 구분 |
| [docs/raw-source-training.md](../../../docs/raw-source-training.md) | 학습 | 기존 4종 완료·복구·960 추론 비교를 반영하고 M2/T1 실행 지원 미준비 명시 |
| [docs/training-cuda-handoff.md](../../../docs/training-cuda-handoff.md) | 학습 | PC11/12/14 검증 완료와 고정 checkout·신규 recipe·전송·preflight 절차 구분 |
| [docs/prior-work-and-dataset-review.md](../../../docs/prior-work-and-dataset-review.md) | 조사 | 문헌 수량과 실제 확보·학습·개발 평가 범위, 신규 CCTV 후보·ACF의 현재 역할 구분 |
| [docs/verification.md](../../../docs/verification.md) | 검증 | 현재 검증 매트릭스를 근거 보고서에 연결하고 과거 미완료·실패 기록과 구분 |
| [docs/team-review-deployment.md](../../../docs/team-review-deployment.md) | 검수 운영 | 복구된 접속 주소·두 질문·조회 시각별 집계·실제 인증과 제한 자료 처리 경계 반영 |
| [docs/documentation-governance.md](../../../docs/documentation-governance.md) | 문서 운영 | 현재 요약·날짜별 증거·영문 소개의 역할과 일관성 유지 규칙 명시 |
| [docs/legacy-asset-selection.md](../../../docs/legacy-asset-selection.md) | 보존·권리 | 고정 submodule의 과거 자료와 신규 자료의 사용·재배포 조건을 구분 |
| [docs/development-log.md](../../../docs/development-log.md) | 이력 | 이번 점검의 범위·근거·검증·한계와 변경 목록 기록 |

현재 요약과 직접 사용하는 표·실행 안내를 수정했다. 날짜가 붙은 실험 결과·실패 기록은 당시 증거로 보존했다. 과거 계획이 현재 작업처럼 읽히는 곳에는 시점이나 대체 상태를 표시하고, 긴 진행 기록은 접어서 현재 기준이 먼저 보이게 했다.

## 현재 판단에 사용한 근거

- [RAW detector 비교](../../evaluation/raw-detector-selection-2026-11-06/report.md): 4종 각 50 epoch·35,600 update 완료, 8개 모델 조건을 6개 공통 개발셋에서 비교. 640 학습 모델의 960 추론은 960 재학습과 구분한다.
- [검수 판정·후속 학습 대조](../../datasets/reviewed-next-training-2026-11-06/report.md): 정상 1,805장은 이미 M1 train과 동일 라벨이며 기존 train의 문제·불확실 88장은 후속 정제 대상이다. 검수 완료량을 모두 새 학습 자료로 세지 않는다.
- [CCTV 후보와 일정 검토](../../datasets/cctv-candidate-check-2026-11-06/report.md): 별도 Q1 전체 학습 후순위·정제를 반영한 M2 한 후보·촬영 자료 확보 시 T1/HOI 우선은 권장안 `PROPOSAL`이다. 새 데이터 채택이나 학습 실행을 뜻하지 않는다.
- [P430/Orin 시범 연동](../../runtime/p430-yolo26n-2026-11-05/report.md): main/sub의 R1/B3 각 300 frame, metadata·snapshot·mock 경보·화면 표시. 물리 GPIO·최종 사건 성능 증거는 아니다.
- [HOI/B4 연결](../../runtime/hoi-b4-integration-2026-11-05/report.md): 합성 자료 CPU·Orin CUDA 연결을 실제 Holding 학습·정확도로 해석하지 않는다.
- [PC11/12](../../training/pc11-pc12-cuda-readiness-2026-11-06/report.md)·[PC14](../../training/pc14-cuda-readiness-2026-11-06/report.md): CUDA 환경과 합성 학습 검증. 실제 전체 자료 학습·분산 학습·장시간 성능 검증과 구분한다.
- 검수 운영의 읽기 전용 조회: **2026-11-06 20:35:57 KST**, 준비 3,625 / 판정 2,673 / 정상 2,527 / 보류 146 / 미검수 952. [비식별 집계](review-counts.json). 각 DB를 따로 읽은 결과이며 이후 판정은 포함하지 않는다. 운영 이미지·판정·배정·이력은 이번 작업에서 변경하지 않았다.

## 유지한 내용과 남은 경계

- [README](../../../README.md)와 [영문 연구 소개](../../../docs/research-overview-en.md)는 직전 `0580fdf`에서 갱신돼 유지했다. [동일 LAN 구성 안내](../../../docs/cctv-local-network-setup.md)와 날짜별 보고서·회의 기록도 보존했다.
- 최종 detector D*, M2/T1 실행, 실제 촬영·관계 정답·학습, 물리 GPIO, 최종 독립 평가는 미완료다. 기존 RAW runner의 4개 ID에 M2/T1은 자동 포함되지 않는다.
- 실제 보드는 L4T 39.2.0 native이며 계획 39.2.1과 다르다. 이번 문서 수정으로 OS 변경이나 정식 runtime 동결을 승인하지 않는다.
- RTSP 수신은 원본 녹화가 아니다. 외부 인터넷 없이 추론할 수 있는 설계와 카메라 LAN이 필요한 입력 경로를 구분한다. 자동 재연결·재부팅 복구·저장공간 회수는 구현 또는 검증이 남은 요건이다.
- 새 제한 자료는 제공 조건과 비공개 접근을 준비한 뒤 반입한다. 공개 이름 선택 검수는 본인 인증 기능이 아니다. 기존 submodule의 공개 접근을 재배포 허가로 해석하지 않는다.
- 동시에 진행된 검수 사이트 작업의 별도 커밋 `8a6ed6c`·`17343ba`·`b9ffe5a`와 그 문서 블록을 보존했다. 별도 Catargiu 미커밋 기록·보고서는 이번 커밋에서 제외한다.

## 이번 작업의 검증

수정 후보를 기존 HEAD와 대조하고 내부 파일·문서 anchor, Markdown fence·details·표, JSON 집계 합계와 Git diff를 점검한다. 결과는 [검증 기록](checks.json)에 보관한다. 기존 링크 문제는 별도 구분하며 이번 수정으로 생긴 내부 링크 오류는 해소한다.

제품 테스트·전체 학습·카메라/GPIO 시험은 이번 작업에서 다시 실행하지 않았다. 과거 테스트 결과는 해당 원본 보고서의 날짜·환경에 한정한다. 현재 변경의 commit과 push 결과는 Git 이력으로 추적한다.
