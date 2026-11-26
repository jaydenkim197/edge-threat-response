# P430 야간 실행 대기열

2026-11-26 KST · PC11~14 및 연구실 서버에 로컬 Worker 배포. Windows에서 별도 결과 동기화 프로세스를 실행한다. [초기 Track A 연구 계획](p430-phase2-optimization-plan.md) · [설치·장비 배정](training-resource-schedule.md)

## 실행과 결과 위치

- [등록 목록](../configs/training/p430-overnight-queue.json)이 실험 ID, 실행 노드, 종류, 선행 조건, 건너뛰기 조건, 대조 기준, 필요한 승인 파일을 정한다. `gpu:true`는 해당 호스트의 GPU가 필요하다는 뜻이다. Windows 4대는 각 RTX 3060, 연구실 일반 학습은 RTX 3090 #2로 고정했고 초기 서버 동시 부하는 한 작업이다. 다른 사용자가 자원을 쓰면 작업을 대기시킨다.
- 서버별 사용자 홈 `etr-p430-overnight-20261126`에서 `python tools/p430_overnight_queue.py worker <queue-root>`를 실행한다. 설치된 학습 venv와 프로젝트 `PYTHONPATH`를 사용한다. Windows CIM 및 Linux `nohup`으로 분리 실행했다. 스케줄러가 실제 호출하는 명령은 `python -u tools/p430_followup_actions.py <attempt>/task.json <attempt>`다. `existing` 항목은 실행 대신 완료 영수증을 확인한다.
- Worker의 `status.json`과 Windows 중계 작업의 `runs/p430-overnight-20261126/shared.json`에 현재 상태를 기록한다. `jobs/<ID>/attempt-<번호>/`에 입력 명세, stdout/stderr, 종료 기록, 결과가 남는다. 학습 출력 경로는 같은 attempt의 `work.json`에 기록한다. 기존 실행과 모든 GPU 잠금을 공유하고 Worker와 중계 각각의 단일 인스턴스 잠금도 사용한다.
- 같은 호스트에서 A → B → C 순으로 최초 `READY`를 고른다. 실행 중인 작업은 완료될 때까지 유지한다. Windows 중계의 `python tools/p430_overnight_queue.py sync <queue-root>`가 호스트 간 결과를 전달하고, n/s/m/P2가 끝나면 결과 영수증 및 예측 파일 SHA-256을 확인한 뒤 PC13에 앙상블 입력을 전달한다. 데이터 본체와 독립 최종 영상은 결과 동기화 범위에서 제외한다.
- Codex 세션이나 원격 SSH가 종료돼도 제출된 프로세스와 로컬에서 판단 가능한 다음 작업은 유지된다. 새 호스트 간 결과 교환에는 중계 Windows의 전원과 네트워크 경로가 필요하다. 원격 Worker는 마지막 수신 기록을 보존한다. 장비 간 빈 슬롯으로 작업을 옮기는 기능은 구현 범위 밖이며, 각 실험은 지정한 적합 노드에서 진행한다.
- `pause.request`가 있으면 현재 하위 작업은 마치고 다음 작업을 기다린다. 재시작 시 결과와 종료 영수증을 확인하고 아직 실행 중인 하위 프로세스는 기다린다. 학습 폴더가 만들어지기 전의 실행 중단은 한 차례 재실행할 수 있다. 학습 도중 자체 프로세스가 종료된 경우와 OOM은 부분 출력과 오류를 보존한다. optimizer 상태로 이어서 진행하는 복구는 후속이다. EMA 분석은 첫 시도의 영수증 파싱 오류를 수정해 재실행했으며 원래 로그를 보존했다.

## Track A 등록 현황

11월 26일 23:35 KST 무렵의 실행 상태다. 아래 항목은 모두 등록됐다. `READY`는 승인된 입력과 선행 조건이 충족됐다는 뜻이며, 같은 GPU에 선행 작업이 있으면 기다린다. 기본 개선 판정은 고정 개발셋에서 음성 오탐 ≤1/147, 작은 칼 TP 감소 ≤1, 전체 TP 감소 ≤2이며, 작은 칼 TP +2 이상 또는 전체 TP +3 이상이다. 임계값은 tune에서만 선택한다. 아래 조건을 통과해도 실제 실기기 및 독립 평가에서 재확인한다.

| 실험 ID | 작업 | 상태 | 배정 | 선행 조건 또는 판정 |
| --- | --- | --- | --- | --- |
| `D1-3408` / `D1-3409` | D1 seed 재현 | COMPLETED | PC11·12 | D0와 동일 데이터·업데이트 |
| `A0` | D1 전체·타일·결합 | COMPLETED | PC13 | 같은 가중치·개발셋 |
| `A-N` / `A-P2` | 640 표준 n·P2 | COMPLETED | PC11·연구실 #2 | COCO 초기값, batch 8, 12 epoch |
| `A-S` / `A-M` | 640 s·m | RUNNING | PC14·PC12 | n과 같은 자료·예산 |
| `A-TILE-GRID` | 512/640 타일과 25/40% 중첩 | COMPLETED | PC13 | D1, 동일 원좌표 비교 |
| `A-TRACE` | 경계·병합·위치·점수 누락 | COMPLETED | PC13 | D1 운영점과 병합 전후 |
| `A-TILE960-EVAL` / `A-ROI` | 네트워크 입력 960 / 고정 ROI 결합 | COMPLETED | PC13 | D1과 같은 타일 또는 같은 화각 |
| `A-EMA` | 256/512/768/1,024 EMA와 후속 저장점 | COMPLETED | PC11 | 두 seed의 완료 평가 |
| `A-EMA-ALL` | epoch별 추가 비교 | SKIPPED | PC11 | 두 seed에서 초기 EMA 선택이 반복됨 |
| `A-LR` | LR0 0.00005 대 0.0001 | RUNNING | PC11 | 초기 EMA 이득 반복, 나머지 조건 동일 |
| `A-MIX30` | 출처 비율 30/30/40 | READY | PC14 | 동일 8,192 draw와 타일 3,932, 먼저 돌아가는 s 완료 대기 |
| `A-MIX70` | 출처 비율 70/20/10 | READY → RUNNING | PC13 | 동일 8,192 draw와 타일 3,932, 독립 작업으로 빈 PC13에 배정 |
| `A-MIX80` | 출처 비율 80/10/10 | PENDING | PC14 | 70/20/10이 D1보다 개선될 때 |
| `A-TILE30` | 동일 부모 타일 30% | READY | PC12 | 48% 대조, m 완료 대기 |
| `A-TILE70` | 동일 부모 타일 70% | PENDING | PC12 | 30% 대조 완료. 5,734개 필요, epoch 최소 6,436개 가능 확인 |
| `A-TILE-TRAIN` | 이긴 타일 크기로 다시 학습 | SKIPPED | PC13 | 타일 재학습 후보가 저오탐 개선 기준 미달 |
| `A-HARDNEG` | 검수된 장소 특화 음성 | PENDING | PC14 | 확인된 P430 train-only 음성 및 동수 교체 승인 |
| `A-HIRES960` / `A-HIRES1280` | 고해상도 학습 | SKIPPED | 연구실 #2 | 동일 타일 960의 이득 기준 미달, 1280의 선행 조건도 불충족 |
| `A-L` / `A-X` | YOLO26l/x 확장 | PENDING | 연구실 #2 | m이 n·s보다 개선, 이어 l이 m보다 개선. 공식 체크포인트 해시 확인 |
| `A-P2-NCTRL` / `A-P2-EXPORT` | 동일 Linux n 대조·P2 변환 | SKIPPED | 연구실 #2 | P2가 음성 오탐 상한을 초과해 승격하지 않음 |
| `A-DISTILL` | 우세 teacher → n 증류 | PENDING | 연구실 #2 | s 또는 m이 개선해야 하며, teacher 호환·기기 비용·체크포인트 승인 필요 |
| `A-ENSEMBLE` | D1+실험 모델 오프라인 결합 | PENDING | PC13 | 공통 dev/tune 결과·예측 SHA 검증 후 실행 |
| `A-SESSION` | 고정 임계값 세션별 민감도 | COMPLETED | PC13 CPU | D1의 기존 두 세션 개발 구간 |
| `A-SESSION-CROSS` | D0부터 양방향 세션 교차 학습 | PENDING | 연구실 #2 | 타 세션 미학습 초기값과 원본 단위 분할 승인 |
| `A-LEGACY` | Legacy/합성 추가 효과 | PENDING | PC14 | 두 출처 혼합 비교 완료 및 고유 자료 권리·분할 승인 |
| `A-ORIN-FILE` | Orin 승인 파일 24장 | COMPLETED | Orin, 연구실 Worker 증거 수신 | D1 고정, 전체·6타일·전체+ROI |
| `A-ORIN-LIVE` | Orin 카메라·사람·판단·경보 포함 | PENDING | Orin, 연구실 Worker | 선정 입력 경로 및 실제 개발 영상·환경 증거 |
| `A-TENSORRT` | Orin TensorRT FP16 | PENDING | Orin, 연구실 Worker | ONNX/TensorRT 런타임, 변환 및 parity. 현재 Python 모듈 미발견 |
| `A-FREEZE` | 배포 후보·판단 규칙 동결 | PENDING | PC13 | 검출·실기기·평가 경계 승인 |

같은 D1의 누락 59건은 낮은 점수 또는 매칭 45, 병합 제거 7, 경계 제거 2, 위치 불일치 4, 남은 겹침 부족 1로 분류했다. Orin D1 파일 추론 p95는 전체 52.7ms, 6타일 153.3ms, 전체+ROI 106.7ms였다. 카메라·사람 검출·경보까지 포함한 지연은 별도로 측정한다.

Track B는 PC13에서 ALT-07과 ALT-12 완료 영수증을 연결했다. PC13의 준비된 A 작업을 소진한 뒤 `B-ALT13`이 자동으로 실행됐다. 보정 결과는 작은 칼 43/58, 전체 77/140, 음성 오탐 0/147로 D1의 작은 칼 47/58, 전체 81/140을 넘지 못했다. ALT-01/02/04는 검수 크롭, 확정된 배경, 대안 아키텍처 런타임이 각각 준비된 뒤 배정한다. Track C `C-HOI`는 승인된 실제 관계 라벨을 기다린다.

11/24 독립 평가 자료는 모든 큐 입력에 들어가지 않는다. 기존 [비교 실험 기록](../reports/training/p430-phase2-2026-11-26/report.md)과 [대안 계획](p430-track-b-alternative-detection-plan.md)은 선행 증거 및 원래 가설을 보존한다.
