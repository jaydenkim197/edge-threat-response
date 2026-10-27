# Orin 원격 접속과 native runtime — 2026-10-27

현재 보드의 native GPU·파일 영상 경로를 검증했다. **실제 환경은 L4T39.2.0이며 프로젝트 기준39.2.1과 다르다.** 이 절차는 현재 장비의 pilot 재현용이고 정식 플랫폼 변경 결정이 아니다. OS·firmware·드라이버·전력 모드를 자동 변경하지 않는다.

## 접속·위치

- 개발 노트북: `ssh etr-orin`. 노트북의 사용자 SSH config에 전용 키를 연결했고 실제 BatchMode 접속을 확인했다. 키·비밀번호·네트워크 주소는 Git에 넣지 않는다. 다른 PC에서는 별도 접속 설정이 필요하다.
- Orin 작업공간: `$HOME/edge-threat-response`, 격리 Python: `.venv-orin/bin/python`.
- 학습 원본과 대용량 검수 자료는 PC13에 보관한다. Orin에는 실행 코드·가상환경·개발 weight2개·약4.6MB 시험 영상만 옮겼다. legacy submodule 전체와 학습 dataset은 clone하지 않았다.

## 확인된 실제 환경

| 항목 | 관측 |
|---|---|
| device tree | Orin Nano Engineering Reference Developer Kit Super, p3767-0005/p3768-0000 |
| RAM | MemTotal7,665,092kB, 약8GB, swap0 |
| 저장장치 | NVMe238.5GiB, root filesystem233GiB |
| OS/kernel | Ubuntu24.04.4 / 6.8.12-1021-tegra / aarch64 |
| L4T / BIOS | 39.2.0 / 39.2.0-gcid-45755727 |
| system driver/CUDA toolkit | 595.78 / 13.2.2 |
| power mode | 25W, ID1 — 조회만 수행 |
| pilot Python/framework | 3.12.3 / torch2.14.1+cu132 / torchvision0.29.1+cu132 |
| application | Ultralytics8.4.152 / NumPy1.26.4 / OpenCV4.11.0.86 |

이 보드에는 `nvidia-jetpack` meta package와 점검한 TensorRT package가 없었다. L4T·CUDA가 있다는 이유로 JetPack 전체 구성 또는 TensorRT 동작을 확인했다고 기록하지 않는다. venv의 CUDA/cuDNN wheel은 시스템 JetPack package와도 구분한다. 실제 최종 조합은 [실측 기록](../reports/runtime/orin-native-smoke-2026-10-27/report.md)을 따른다.

## 격리 환경 설치 기록

최초에는 system Python의 pip를 이용해 ensurepip/apt 설치 없이 새 venv에 pip를 넣었다. 기존 환경이 있으면 아래 생성 명령을 덮어쓰지 않는다.

```bash
python3 -m venv --without-pip .venv-orin
python3 -m pip --python .venv-orin install pip==24.0
.venv-orin/bin/python -m pip install torch==2.14.1+cu132 torchvision==0.29.1+cu132 \
  --index-url https://download.pytorch.org/whl/cu132
.venv-orin/bin/python -m pip install numpy==1.26.4 opencv-python==4.11.0.86 ultralytics==8.4.152
.venv-orin/bin/python -m pip install --no-deps -e .
.venv-orin/bin/python -m pip check
```

전체 test용으로 Flask3.1.2/Waitress3.0.2도 venv에 설치했지만 Orin에 검수 웹서비스를 배포한 것은 아니다. 해결된 전체 버전은 [pilot lock](../reports/runtime/orin-native-smoke-2026-10-27/requirements-lock.txt)에 있다. 이 lock은 Linux aarch64 관측 결과이며 PC13/다른 JetPack의 공통 요구사항이 아니다. 최신 버전 자동 추종이나 nightly 설치를 하지 않는다.

공식 [NVIDIA CUDA 안내](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/setup_cuda.html)는 native/container 선택과 실제 GPU 검증을 설명한다. [PyTorch2.14.1 CUDA source](https://github.com/pytorch/pytorch/blob/v2.14.1/torch/cuda/__init__.py)는 CUDA13.2 이후 Jetson/SBSA 호환 분기를 포함한다. 이 근거만으로 성공을 주장하지 않고 CUDA matmul·cuDNN convolution·torchvision NMS와 실제 두 detector를 별도로 실행했다.

## 비파괴 inventory·재검증

아래 출력은 매번 새 경로를 사용한다. `inspect_jetson.py`는 network/serial/credential을 수집하지 않고, OS·전력·clock을 변경하지 않는다. `--cuda-smoke`는 실제 GPU 연산을 수행한다.

```bash
.venv-orin/bin/python tools/inspect_jetson.py --cuda-smoke --output runs/<fresh-inventory>.json
PYTHONPATH=src .venv-orin/bin/python tools/verify_orin_file_smoke.py \
  --person models/development-20261026/person-yolo26n.pt \
  --knife models/development-20261026/knife-best.pt \
  --fixture data/integration/pc-video-20261026/train-derived-fixture.avi \
  --inventory runs/<fresh-inventory>.json --output runs/<fresh-file-smoke>
```

파일 smoke는 PC에서 고정한 개발 weight·영상 SHA를 강제한다. 새 모델로 대체할 때는 기존 검증을 승계하지 말고 별도 fixture/설정·증거를 만든다. 이번 성공은 frame53·canonical59·B3 event/snapshot2·action error0이며, 같은 JSONL의 B0~B3가 기대 제어 동작과 일치했다. 실제 사건 정확도·프레임 처리율·GPIO 반응 시간은 아니다.

다음은 플랫폼 patch 기준의 유지/변경 결정, 카메라·GPIO 확보/통합, 실제 촬영과 사건 정답, 정식 benchmark다. 원격 재부팅 후 접속 유지·장시간 운용·TensorRT는 아직 검증하지 않았다.
