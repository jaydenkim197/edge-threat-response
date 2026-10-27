# Orin 파일 운용 준비 점검 — 2026-10-27

카메라·GPIO 없이 확인 가능한 파일 경로의 오류 처리, 통신 없는 실행, 제한 시간 반복 실행을 점검한다. 실제 촬영 정확도나 최종 연구 benchmark를 대신하지 않는다. 모델·입력·L4T39.2.0 pilot 환경은 [최초 native smoke](../orin-native-smoke-2026-10-27/report.md)와 같다.

## 목적·통제 조건

- 작업 요청: 카메라·GPIO 확보 전 Orin에서 할 수 있는 작업을 계속 진행한다.
- 완료 기준: 기존 결과 보호·중단 시 완료 로그·실패 집계의 회귀 검사, 실제 GPU offline file smoke, 600초 반복 및 자원 기록, 문서·Git 반영.
- 장비: Orin Nano Super/p3767-0005, 약8GB RAM/swap0, NVMe, 기존25W mode1. Ubuntu24.04.4/L4T39.2.0/kernel6.8.12-1021-tegra, torch2.14.1+cu132/vision0.29.1+cu132/Ultralytics8.4.152/NumPy1.26.4/OpenCV4.11.0.86.
- source: base `cf67450`의 격리 QA archive에 이번 runtime/CLI/pipeline/test/tool 변경을 덧씌웠다. 실행 source byte hash를 aggregate에 보관한다. QA archive는 `src/tests/tools/configs`를 포함하며 실제 운영 checkout은 측정 중 수정하지 않았다. 최종 source commit은 이 보고서의 Git history로 추적한다.
- 고정 모델: COCO person YOLO26n와 DEV-SOHAS AdamW+scale.9 knife best.pt. 두 component CUDA0/640, person conf.5/knife.25, class0만 사용, IoU.7, half=False.
- 입력: train 이미지3개+blank로 만든 53frame FFV1/640×640/10fps montage. 실제 연속 행동이 아니다. SHA·모델 SHA는 aggregate와 최초 보고서에 있다.
- 판단: B3 expanded bbox alpha.25, K2/N3, rearm clear2. 개발 fixture 설정이며 연구 threshold 동결이 아니다.
- 예상 제어: B0 event frames8/18/32/39, B1 9/19/40, B2 18/32/39, B3 19/40. 정답 사건 성능 지표가 아닌 고정 입력의 제어 회귀 조건이다.

## 수정한 결함과 검증

수정 전 관련 회귀 테스트가 실제 실패함을 확인한 뒤 기존 runtime/port/CLI를 확장했다. 별도 추론 엔진이나 신규 의존성은 추가하지 않았다.

| 결함 | 변경 | 검증 |
|---|---|---|
| 같은 output을 재사용하면 기존 기록이 잘리거나 섞임 | 새/빈 output만 허용하고 frame 입력 전에 거부 | detection/live 양쪽에서 기존 bytes와 source 미소비 확인 |
| detection/decision/latency 전체를 EOF까지 RAM에 보관 | 완료 frame마다 JSONL write+flush | generator가 다음 frame 전에 log를 읽고 예외를 내도록 하여 앞선 row 보존·성공 summary 부재 확인 |
| snapshot port가 `failed`를 반환하면 오류 집계에서 빠짐 | 반환 실패도 action error에 포함 | metadata와 mock alarm은 남고 오류1건 집계 |
| 누락된 weight가 backend로 넘어감 | CLI 모델 생성 전 local file 확인 | 두 CLI 모두 exit2, backend 호출0/output 생성0 |
| 모든 frame이 detector error여도 CLI 성공 | 유효 frame0이면 exit2 | 두 CLI의 오류 summary와 exit2 확인 |
| max_frames가 입력을 한 frame 더 소비 | `islice`로 제한 | max1에서 source 소비1 확인 |

local Python3.12.14의 관련15 tests, 실제 Orin Python3.12.3의 전체148 tests(13.035s), 신규/변경 tool compileall을 통과했다. 실제 Orin의 두 CLI에도 기존 output/누락 weight를 각각 입력하여 모두 exit2, 기존7개 파일 hash 불변, 누락 weight output 생성0을 확인했다. artificial fault injection은 실제 카메라 단절·디스크 full·정전 실험이 아니다.

runtime은 mean/median/nearest-rank p95/max 및 `frame_processing_ms`를 추가한다. 후자는 decoded frame부터 inference·canonical 변환·판단·동기 actions까지이며 decode와 진단 JSONL 쓰기를 제외한다. 정확한 percentile을 위한 scalar latency 목록과 mock alarm 이력은 여전히 실행 길이에 비례한다. 이 변경으로 무기한 constant-memory 운용을 보장하지 않는다.

## 통신 격리 실기기 결과

`unshare --net`으로 자식 실행 공간만 격리하고 일반 사용자 권한으로 실제 CLI를 실행했다. interface는 loopback만 있고 외부 TEST-NET 주소 connect는 kernel `ENETUNREACH`였다. host network namespace와 Tailscale/SSH는 그대로 유지했고 시험 후 BatchMode 재접속을 확인했다.

- 실제 `etr-run`: valid53, detection59, B3 event2/snapshot2/action error0/exit0.
- frame19/40의 저장 JPEG가 해당 decoded frame 재인코딩 bytes와 일치한다.
- 같은 JSONL B0~B3가 고정 기대 frame과 일치한다.
- offline detection JSONL SHA `d498b6961edbe6bfb003f2a16fe007fd1f93292c5d228674ea3a7932b46113cd`는 최초 host-network smoke와 같다.
- 이미 로컬에 모델·runtime·설정이 준비된 상태에서의 통신 독립성을 확인했다. cold cache 신규 설치, 물리 회선 복구, camera/GPIO, 재부팅 복구는 검사하지 않았다.

## 600초 반복 파일 결과

53frame warmup 이후 실제600.086초, valid7,375frame을 처리했다. 별도 GPU 작업은 동시에 실행하지 않았다. 다음 수치는 반복 학습 이미지 파일 workload에만 해당한다.

| 관측 | 결과 |
|---|---:|
| warm file 처리율(decode/추론/판단/동기 저장/로그 포함) | 12.2899 frames/s |
| inference mean / p95 | 79.0926 / 85.0422 ms |
| frame processing mean / p95(decode/진단 log write 제외) | 79.5621 / 86.4304 ms |
| B3 event / snapshot / action error | 278 / 278 / 0 |
| 약5초 간격 최고 관측 온도 | 60.75°C |
| 최소 관측 MemAvailable | 5,085,100KiB(약4.85GiB) |
| PyTorch 최고 allocated CUDA memory | 77,524,992bytes(약73.93MiB) |
| process RSS 시작 → 종료 | 1,788,572 → 2,009,448KiB(약+215.70MiB) |
| 전력 모드 전/후 | 25W/ID1 동일 |

반복 번호를 포함한 기대 event frame·snapshot 수와 원본/설정/source byte 보존 검사를 통과했고 정상 종료했다. 종료 후 profile/tegrastats 프로세스가 남지 않음을 확인했다. 자원 sample은 지속적인 모든 순간의 peak를 보장하지 않으며 PyTorch allocated는 GPU/시스템 전체 사용량과 다르다. 상세 수치·hash는 [aggregate](aggregate.json)에 있다.

**메모리 증가 원인은 미확정이다.** RSS가 약216MiB 늘었으므로 이 결과를 leak-free 또는 장기 안정성으로 승격하지 않는다. 추가로 모델·pipeline을 import하지 않는 별도 프로세스에서 같은 파일을121회/6,413frame decode했다. 133.746초의 RSS는73,124→78,088KiB(약+4.85MiB), 후반에는 약78,080KiB였다. 이 별도 조건에서는 같은 규모의 증가를 재현하지 못했지만 전체 경로의 어느 부분이 원인인지는 확정하지 못했다. raw `decode-memory.json`과 진단 script hash는 aggregate에 연결한다. 실제 카메라 경로의 장시간 검사와 전체 경로 memory attribution은 후속 gate다.

## 원시 증거·재현

- Orin ignored root: `runs/orin-readiness-20261027-v1/`.
- offline: `offline-netns-v1/verification.json`, `cli.log`, live JSONL/summary/events/JPEG, 동일 입력 replay.
- 반복: `profile-smoke/`는 사전5초 검사, `profile-600s-v1/`는 본 제한 시간 검사. `profile.json`, `resources.jsonl`(약5초 간격), `tegrastats.log`(1초 간격), `live-b3/`를 보존한다.
- QA: ignored `data/work/code-qa/orin-readiness-20261027-v1/qa.log`, archive source와 overlay. 공개 aggregate는 개인 접속 정보·이미지를 포함하지 않는다.
- 명령·해석: [Orin runtime 운영 절차](../../../docs/orin-runtime-setup.md). `.venv-orin/bin/python -m unittest discover -s tests -q`, `tools/verify_orin_file_smoke.py --offline-netns`, `tools/profile_orin_file.py --seconds 600`을 사용했다. 정확한 입력은 위 frozen 경로·SHA 및 raw provenance로 연결된다.

## 한계·다음 작업

계획L4T39.2.1과 실제39.2.0의 정식 채택은 미결정이다. 이번에 OS/firmware/driver/power/clock, 검수 사이트·DB·학습 데이터·모델·val/test는 변경하지 않았다. 파일 처리율은 camera FPS·실제 사건 recall/precision·GPIO 지연과 다르다. 10분 실행으로 장시간/24시간 안정성을 주장하지 않는다.

다음 gate는 플랫폼 patch 유지/변경 결정, 카메라·GPIO와 설치 조건 확보, 실제 영상 및 수동 사건 정답, 동일 D*에서 B0~B3 정식 평가다. TensorRT는 stretch이며 현재 미설치 상태를 자동 변경하지 않았다. 재부팅·전원 복구 검사는 현장 복구 수단이 준비된 뒤 별도로 수행한다.
