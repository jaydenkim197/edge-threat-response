# Verification Matrix

구현 저장소와 legacy source 연결은 준비되었으나 신규 시스템과 실기기는 미검증이다. `VERIFIED`는 명령·환경·결과·증거를 확보한 뒤에만 부여한다.

| 요구사항 | 검증 방법 | 환경 | 최근 결과 | 증거 위치 | 상태 |
|---|---|---|---|---|---|
| 기준 저장소·legacy source | Git remote, commit, submodule 상태 확인 | 개발 PC | 저장소 및 고정 submodule 연결 | Git history, `.gitmodules` | `VERIFIED` |
| legacy dataset inventory | image/label·YAML·training script·annotation format·filename group 점검 | 개발 PC, fixed submodule | 7,364 image-label pairs, missing/empty 0, knife-only, bbox 7,613 + polygon 1,447; split 교차 group 확인 | `docs/model-data-plan.md` | `VERIFIED` (구조), 품질·권리 `PLANNED` |
| dataset validator·manifest | synthetic fixture와 legacy read-only audit | Windows, Python 3.11.9 | 13 tests 통과; 7,364 images·9,060 objects 파싱, invalid/missing 0 | `tests/`, `reports/datasets/legacy-2026-09-14/` | `VERIFIED` (구조) |
| group split·leakage 검사 | source/session/exact hash의 split 교차 fixture와 legacy manifest smoke | Windows, Python 3.11.9 | source group·exact duplicate 동시 보존; 기존 split 교차 group 317 탐지 | audit report, split smoke output은 로컬 temp | `VERIFIED` (PC) |
| 개발 PC ML runtime | package/GPU inventory | Windows, Python 3.11.9 | NVIDIA CUDA GPU 없음; torch·Ultralytics·OpenCV 미설치. CPU model smoke는 pre-Orin gate에서 제외 | `docs/pre-orin-work-plan.md` | inventory `VERIFIED`; model smoke `DEFERRED` |
| Pre-Orin adapter/video scaffold | fake detector·frame source·JSONL·snapshot integration test | 개발 PC, ML dependency 없음 | 미구현 | - | `PLANNED` |
| Orin Nano platform inventory | SKU·RAM·firmware·저장장치·JetPack·전원 모드 확인 | Jetson Orin Nano 실기기 | 미수행 | - | `PLANNED` |
| JetPack 7.2.1 설치 | Jetson Linux 39.2.1 부팅과 SDK 구성 확인 | Jetson Orin Nano 실기기 | 공식 지원 환경만 확인, 설치 미수행 | NVIDIA 공식 문서 | `PLANNED` |
| detector runtime smoke test | native GPU access·model load·고정 이미지 추론 후 container 대안 비교 | Orin Nano, 후보 runtime/image | 미수행 | - | `PLANNED` |
| 기존 모델 추론 재현 | 기준 영상/카메라 입력으로 실행 | Orin Nano adapter 또는 격리된 legacy Nano 환경 | 미수행 | - | `PLANNED` |
| GPIO LED·부저 경보 | 정상·경보·복구 상태 수동 시험 | Jetson Orin Nano 실기기 | 미수행 | - | `PLANNED` |
| geometry association | 단위 테스트: nearest person, 정규화 거리, 확장 bbox·경계 | 개발 PC, Python 3.11.9 | 구현, 관련 test 통과 | `tests/test_spatial.py` | `VERIFIED` (순수 로직) |
| K-of-N confirmation | 단위 테스트: 조기 확인, dropout, window 만료, 잘못된 K/N | 개발 PC, Python 3.11.9 | 구현, 관련 test 통과 | `tests/test_temporal_state_machine.py` | `VERIFIED` (순수 로직) |
| 4-state machine | 단위 테스트: 전 상태, action 중복 억제, clear rearm | 개발 PC, Python 3.11.9 | 구현, 관련 test 통과 | `tests/test_temporal_state_machine.py`, `tests/test_pipeline.py` | `VERIFIED` (순수 로직) |
| 사건 metadata·snapshot | recorded-detection fixture와 port failure 통합 test | 개발 PC, Python 3.11.9 | metadata JSONL·deterministic ID·저장 실패 시 alarm 유지 검증; replay snapshot은 `not_captured` | `tests/test_pipeline.py`, `reports/replay/increment-a-smoke/` | metadata `VERIFIED`; 실제 snapshot `PLANNED` |
| B0~B3 ablation | 동일 recorded detection·설정으로 4 policy replay | 개발 PC, Python 3.11.9 | 9 frames에서 최초 event B0=0, B1=1, B2=1, B3=2; mode당 2 events | `tests/test_pipeline.py`, `reports/replay/increment-a-smoke/report.md` | policy/replay `VERIFIED`; 모델·본 실험 `PLANNED` |
| 카메라 복구 | 연결 해제·재연결 fault injection | Jetson 실기기 | 미구현 | - | `PLANNED` |
| 로컬 경보의 오프라인 유지 | 네트워크 차단 상태 시스템 시험 | Jetson 실기기 | 미구현 | - | `PLANNED` |
| 성능·자원 기록 | 고정 입력, 해상도, 런타임으로 benchmark | Orin Nano, 선택적으로 legacy Nano | 미수행 | - | `PLANNED` |
| 개인정보·보존 정책 | 수집 전 정책·기관 요구사항 확인 | 프로젝트 운영 환경 | 미수행 | - | `PLANNED` |

## Benchmark 최소 기록 항목

- 날짜, Git commit 또는 소스 버전, 장비, JetPack/OS, 전원 모드
- 모델 파일·런타임·정밀도·입력 해상도·입력 영상
- FPS, inference latency, end-to-end alert latency
- CPU/GPU/RAM, 온도, 전력 측정 방법
- 검출·경보 시나리오와 false alarms per hour 산출 방법

## Evidence status rules

- `UNVERIFIED`: 과거 자료나 출처는 있으나 현재 조건에서 재현하지 못함
- `TARGET`: 근거와 승인 절차를 거쳐 정한 목표이며 측정 결과가 아님
- `MEASURED`: 고정된 환경·명령·입력과 raw evidence가 있는 관측값

현재 기존 발표의 Precision 96.2%, Recall 85.1%, mAP50 93.7%는 모두 `UNVERIFIED`이다. 신규 정량 목표는 baseline과 scenario 규모를 확인한 뒤 기록한다.
