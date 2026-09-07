# Verification Matrix

구현 저장소와 legacy source 연결은 준비되었으나 신규 시스템과 실기기는 미검증이다. `VERIFIED`는 명령·환경·결과·증거를 확보한 뒤에만 부여한다.

| 요구사항 | 검증 방법 | 환경 | 최근 결과 | 증거 위치 | 상태 |
|---|---|---|---|---|---|
| 기준 저장소·legacy source | Git remote, commit, submodule 상태 확인 | 개발 PC | 저장소 및 고정 submodule 연결 | Git history, `.gitmodules` | `VERIFIED` |
| 기존 Jetson Nano 부팅 | 전원·HDMI·팬·저장장치 점검 | Jetson Nano 실기기 | 미수행 | - | `BLOCKED` |
| 기존 모델 추론 재현 | 기준 영상/카메라 입력으로 실행 | Jetson Nano, 원본 모델·소스 | 미수행 | - | `PLANNED` |
| GPIO LED·부저 경보 | 정상·경보·복구 상태 수동 시험 | Jetson Nano 실기기 | 미수행 | - | `PLANNED` |
| spatial/temporal context | 단위 테스트: 거리 정규화, 지속성, 누락 | 개발 PC | 범위 미확정·미구현 | - | `PROPOSAL` |
| threat state machine | 단위 테스트: 전이, 임계값, 누락, cooldown | 개발 PC | 상태 미확정·미구현 | - | `PROPOSAL` |
| 사건 metadata·snapshot | 고정 영상 시나리오 통합 테스트 | 개발 PC 및 Jetson | 범위 미확정·미구현 | - | `PROPOSAL` |
| baseline vs proposed | 동일 입력·모델·설정으로 사건 지표 비교 | 개발 PC 및 Jetson | 평가 규칙 미정 | - | `PLANNED` |
| 카메라 복구 | 연결 해제·재연결 fault injection | Jetson 실기기 | 미구현 | - | `PLANNED` |
| 로컬 경보의 오프라인 유지 | 네트워크 차단 상태 시스템 시험 | Jetson 실기기 | 미구현 | - | `PLANNED` |
| 성능·자원 기록 | 고정 입력, 해상도, 런타임으로 benchmark | Nano, 필요 시 Orin Nano | 미수행 | - | `PLANNED` |
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
