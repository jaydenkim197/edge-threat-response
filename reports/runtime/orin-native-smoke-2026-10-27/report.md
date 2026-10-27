# Orin 최초 접속·native GPU·파일 영상 smoke — 2026-10-27

**Orin Nano에서 새 best.pt + COCO person의 GPU 추론과 파일 영상→판단→metadata/JPEG/mock alarm 경로가 실제 동작했다.** CUDA matmul·convolution·NMS, 영상53frame, 동일 JSONL B0~B3, snapshot 원 frame 일치, 전체141 tests를 확인했다. 카메라/GPIO·실제 사건 성능·MVP 전체 완료는 아니다.

상태: **실제 R39.2.0 장비의 bounded smoke `VERIFIED`**. 프로젝트 계획39.2.1과 다르므로 플랫폼/runtime 정식 채택은 하지 않았다. 근거: [inventory](inventory.json), [영상 결과](verification.json), [환경 lock](requirements-lock.txt), [접속·재실행 절차](../../../docs/orin-runtime-setup.md).

## 장비·환경

| 관측 | 값 |
|---|---|
| board/device tree | NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super |
| compatible | p3768-0000+p3767-0005-super / tegra234 |
| RAM·CPU | MemTotal7,665,092kB /6 logical CPU /swap0 |
| OS·kernel | Ubuntu24.04.4 LTS /6.8.12-1021-tegra /aarch64 |
| L4T·UEFI | 39.2.0 /39.2.0-gcid-45755727 |
| storage | NVMe238.5GiB, root233GiB, 최초 가용205GiB |
| driver /system CUDA toolkit | 595.78 /13.2.2 |
| power | 25W, mode1; 변경하지 않음 |
| venv framework | Python3.12.3 /torch2.14.1+cu132 /vision0.29.1+cu132 |
| application | Ultralytics8.4.152 /OpenCV4.11.0.86 /NumPy1.26.4 |

device-tree/BIOS/package 정보이며 physical module 실물 검사는 아니다. `nvidia-jetpack` meta 및 점검한 TensorRT package는 없었다. system package와 venv의 CUDA13.2/cuDNN9.24.0.43 wheel은 별도다. NVIDIA [JetPack7.2.1 공식 구성](https://developer.nvidia.com/embedded/jetpack/downloads)은 L4T39.2.1/CUDA13.2.2이며, 이 보드의39.2.0에 자동 승계하지 않는다.

## 수행과 실제 결과

1. 제공된 계정으로 SSH 접속 후 전용 key를 사용자 authorized_keys에 추가하고 개발 노트북 alias로 BatchMode 재접속을 확인했다. 기존 key를 보존했고 credential·private endpoint는 Git에 저장하지 않았다. OS/firmware/driver/전력/clock/SSH daemon 설정은 바꾸지 않았다.
2. source를 submodule 재귀 다운로드 없이 clone하고 `.venv-orin`을 격리 생성했다. 최초 torch2.13.0+cu132는 availability와 작은 matmul이 동작했지만 Orin CC8.7 지원 경고가 있었다. torch2.14.1+cu132/vision0.29.1+cu132에서 아래 실제 kernel 시험을 통과했고 해당 CUDA 경고는0이었다. 패키지 파일을 수정하거나 경고를 숨기지 않았다.
3. `inspect_jetson.py --cuda-smoke`: Orin GPU/CC8.7, 행렬 곱 결과32768, cuDNN 합성곱 결과27, CUDA NMS retained indices[0,2] 및 synchronize를 검증했다. `torch.cuda.is_available()`만 확인한 결과가 아니다. [PyTorch2.14.1 source](https://github.com/pytorch/pytorch/blob/v2.14.1/torch/cuda/__init__.py)의 CUDA13.2 Jetson/SBSA 분기와 함께 실제 성공을 기록한다.
4. PC13의 기존 weight2개와 고정 FFV1 시험 영상만 SCP로 복사하고 SHA-256이 동일함을 확인했다. dataset 전체·신규 미검수 자료는 옮기거나 학습하지 않았다.
5. native `etr-run`을 device0으로 실제 실행했다. **53/53 valid, canonical detection59, B3 event2/snapshot2/action error0**, event frame19/40이다. 각 decoded event frame을 같은 장비 JPEG encoder로 재생성한 bytes가 저장 snapshot과 일치했다.
6. 동일 Orin detection JSONL의 B0~B3 replay가 아래 기대 frame과 일치했다. PC와 CUDA/framework 버전이 다르므로 prediction byte·속도·정확도 동등성 비교로 해석하지 않는다.

| mode | event frame | 수 |
|---|---|---:|
| B0 | 8,18,32,39 | 4 |
| B1 | 9,19,40 | 3 |
| B2 | 18,32,39 | 3 |
| B3 | 19,40 | 2 |

입력은 학습 이미지3개와 blank를 조합한5.3초/53frame 영상이다. 실제 시간 연속성이 있는 독립 촬영 영상이 아니다. 따라서 event precision/recall, 실제 오경보 감소, FPS·GPIO 지연을 측정한 것이 아니다. 새 knife는 개발용 후보이며 최종 D*로 승격하지 않았다.

## 코드·검증·원시 자료

- source base `9ad86e075b5887567302dd2fe38a8aa4de32e5cd` + 신규 tool2개. `verify_orin_file_smoke.py` 실행 SHA는 `1976bc970e824bc2bd94b694c920847d288e4b81455f8ab04947c9668db6a531`. 기존 snapshot 검증/기대 fixture·runtime·CLI·replay를 재사용했다. 신규 runtime 계층이나 detector를 만들지 않았다.
- 실제 Orin 전체141 tests(13.058s), `pip check`, tool compileall, native kernel/CLI/snapshot/replay 검증 통과. Flask/Waitress는 QA용으로 설치했으며 Orin에 팀 검수 사이트를 배포하지 않았다.
- Orin ignored `runs/orin-setup-20261027-v1/`: 초기/최종 package install log·pip reports·freeze·inventory·CUDA kernel·tests. 첫 설치 wrapper의 shell exit 전달 오류는 보존했고 후속 package install/import/pip check와 실제 추론 성공으로 결과를 확인했다.
- Orin ignored `runs/orin-file-smoke-20261027-v1/`: detector/pipeline config·CLI log·live-b3 metadata/snapshot·동일 JSONL replay·verification. 영상/weight는 `data/integration/pc-video-20261026/`, `models/development-20261026/`에 있다. 프로젝트 비밀값·원본 영상/이미지는 Git에 넣지 않는다.
- 공식 source 참고: [NVIDIA CUDA 검증 안내](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/setup_cuda.html), [PyTorch 공식 설치 안내](https://pytorch.org/get-started/locally/). 원격 사용 정보는 로컬 SSH config로만 관리한다.

## 남은 조건

- L4T39.2.1 기준을 유지해 업데이트할지, 실제39.2.0 pilot을 정식 기준으로 채택할지 결정 필요. 이번 작업은 OS 업데이트·범위 승격 없이 진행했다.
- 카메라 node 없음. 카메라/GPIO 부품·배선·실제 경보는 미검증이다.
- 실제 촬영·수동 사건 정답·튜닝/최종 session 분리·실험 파라미터 동결·baseline/정량 비교가 남는다.
- TensorRT/FP16, 전원/냉각/clock 조건 고정 benchmark, 장시간/네트워크 단절/재부팅 복구는 미검증이다. 짧은 tegrastats 표본을 전력·열 성능으로 일반화하지 않는다.
