# Verification Matrix

현재 구현 저장소와 실기기가 준비되지 않았으므로, 아래는 검증 계획이다. `VERIFIED`는 명령·환경·결과·증거를 확보한 뒤에만 부여한다.

| 요구사항 | 검증 방법 | 환경 | 최근 결과 | 증거 위치 | 상태 |
|---|---|---|---|---|---|
| 기존 Jetson Nano 부팅 | 전원·HDMI·팬·저장장치 점검 | Jetson Nano 실기기 | 미수행 | - | `BLOCKED` |
| 기존 모델 추론 재현 | 기준 영상/카메라 입력으로 실행 | Jetson Nano, 원본 모델·소스 | 미수행 | - | `PLANNED` |
| GPIO LED·부저 경보 | 정상·경보·복구 상태 수동 시험 | Jetson Nano 실기기 | 미수행 | - | `PLANNED` |
| 연속 프레임 상태 머신 | 단위 테스트: 임계값, 누락, cooldown | 개발 PC | 미구현 | - | `PLANNED` |
| 사건 전후 영상 저장 | 고정 영상 시나리오 통합 테스트 | 개발 PC 및 Jetson | 미구현 | - | `PLANNED` |
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
