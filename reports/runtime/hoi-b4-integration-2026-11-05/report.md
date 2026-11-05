# HOI/B4 연결 검증 — 2026-11-05

G/VG 관계 학습기와 B4를 PC 및 Orin에서 가상 입력으로 연결했다. **실제 Holding 정확도·카메라·GPIO 검증 결과는 아니다.**

| 환경 | 실행 | 결과 |
|---|---|---|
| 로컬 CPU / torch2.14.0 | G/VG 가상1epoch forward/backward·저장/reload·영상 입력 | 통과 |
| PC13 ML / torch2.6.0+cu124 | 같은 CPU smoke, checkpoint 생성 | 통과 |
| PC13 평가 venv | 최신 source 전체183 tests | 23.077초, 모두 통과, skip0 |
| PC13 ML venv | 전체181 tests | 실패0, pycocotools 관련2 skip |
| Orin / torch2.14.1+cu132 | G/VG CUDA 추론·sidecar·B0~B4 replay·snapshot/mock alarm | 통과 |
| Orin | HOI7·RTSP mock2·core/config10·event evaluator8 tests | 27개 모두 통과 |
| PC13 → Orin | PC13에서 생성한 VG checkpoint를 그대로 전송해 strict load/CUDA 추론 | 통과, checkpoint hash 일치 |

영상은 synthetic4frames, detector는 fake다. wiring 확인을 위해 threshold0을 강제했고 event1/snapshot1을 확인했다. 이 수를 event recall/실제 소지 정확도로 사용하지 않는다. ImageNet pretrained visual 학습도 이 smoke에 포함하지 않았다.

구현 source는 `c2daa70`, PC13 CPU smoke/평가환경 정리는 `7007957`이다. Orin에서 기존 current-process THP disable을 적용했으며 OS/드라이버/패키지를 일괄 변경하지 않았다. 환경·source/checkpoint SHA·시간과 한계는 verification.json에 있다. 로컬 실행파일의 개인 경로만 상대 경로로 표시했다.

재현: `PYTHONPATH=src`에서 `python tools/verify_hoi_smoke.py --output-dir <새 ignored 경로>`를 사용한다. Orin CUDA 검증에는 `--inference-device cuda:0`을 추가한다. 가상 CPU 학습과 target CUDA 추론을 구분한다. 실제 관계 라벨은 별도 인계 규격에 따라 수집한다.
