# 연구실 GPU 서버 학습 환경 계획

2026-11-26 KST · SSH 및 장비 상태 `VERIFIED` · 환경 구성, 데이터 반입, 실행 `PLANNED`

## 접속·장비 조사

Windows의 기존 SSH alias와 OpenSSH Agent로 `BatchMode=yes` 접속했다. 서버는 Linux Mint 20.3 x86-64, glibc 2.31이며 Threadripper 3960X 24코어/48스레드와 RAM 251 GiB를 장착하고 있다. 조회 당시 가용 RAM은 232 GiB였다. 일반 사용자 홈은 쓰기 가능하고 루트와 같은 NVMe ext4에 있다. `df`의 여유 279 GiB는 해당 파일시스템의 공유 수치다. 계정별 quota는 확인되지 않았다. 별도 HDD와 NVMe 마운트는 초기 운영에서 제외한다. Git 2.25.1, rsync 3.1.3, `nohup`, `flock`, `sha256sum`을 확인했다. `tmux`·`screen`은 PATH에 없고, 사용자 systemd는 조회 시 동작하나 `Linger=no`였다.

| 물리 GPU ID | 사양 | 18:10–18:11 KST 관측 및 배정 |
| --- | --- | --- |
| 0, 5 | RTX 3080 각 10 GiB, Ampere, CC 8.6 | 각 15 MiB, GPU 사용률 0%, CUDA 작업 목록 비어 있음. Track A 사용 대상 |
| 1, 2 | RTX 3090 각 24 GiB | 각각 약 20 GiB 사용 중. 다른 연구 작업에 배정 |
| 3, 4 | GTX 1080 Ti 각 11 GiB, Pascal, CC 6.1 | 각 7 MiB. 사용 권한 확인 대기 |

RTX 3080 두 장의 물리 번호·PCI bus ID·UUID를 대조했고, 18:16 KST 재조회에서도 두 장의 CUDA 작업 목록이 비어 있었다. UUID 원문과 접속 값은 로컬 운영 정보로 관리한다. 드라이버 560.35.05의 `nvidia-smi`는 CUDA 12.6을 보고한다. 시스템 PATH에 `nvcc`가 없었고, Python 3.8.10 및 pip 20.0.2에는 `ensurepip`, torch, Ultralytics가 없었다. Conda와 uv는 PATH와 확인한 일반 설치 경로에서 발견되지 않았다. 프로젝트는 Python ≥3.10이 필요하다. [NVIDIA 드라이버 호환 표](https://docs.nvidia.com/cuda/archive/12.6.3/cuda-toolkit-release-notes/index.html#cuda-toolkit-and-minimum-required-driver-version-for-cuda-minor-version-compatibility) · [NVIDIA GPU별 Compute Capability](https://developer.nvidia.com/cuda/gpus) · [Pascal Compute Capability](https://developer.nvidia.com/cuda/gpus/legacy)

## 사용자 전용 구축과 검증

1. 홈의 사용자 전용 디렉터리에 소스, 가상환경, 읽기 전용 입력 릴리스, 실행 기록을 둔다. 새 작업 폴더는 `umask 077`로 만들고 입력·압축본·예상 체크포인트를 합친 용량을 복사 직전에 확인한다. 시스템 Python·드라이버·공용 마운트는 기존 구성을 사용한다.
2. 서버에서 공개 GitHub 저장소의 `main` 조회에 성공했다. HTTPS로 독립 clone 후 학습 실행 커밋을 detached checkout으로 고정한다. legacy submodule은 필요할 때 별도 범위로 받는다. 코드 출처·커밋, 환경과 큰 데이터는 별도로 관리한다. SSH agent forwarding 없이 기존 로컬 인증 경로를 사용한다.
3. 홈에 공식 릴리스의 uv 또는 관리형 CPython을 검증해 설치하고, Python 3.12를 프로젝트 전용 `.venv`로 고정한다. 우선 PC13과 동일한 torch 2.6.0/cu124, torchvision 0.21.0/cu124, Ultralytics 8.4.152를 사용한다. 서버에서 공식 cu124 wheel 목록과 PyPI에 접속을 확인했다. 바이너리 wheel이 CUDA 런타임을 제공하므로 기존 드라이버로 검증을 시작할 수 있다. `pip check`, import, freeze와 wheel 해시, PC13과 버전 차이를 기록한다. OpenCV GUI 라이브러리 의존 문제가 있어 headless 전환이 필요하면 중복 설치 없이 해당 차이를 기록하고 검증한다. [uv Python 설치](https://docs.astral.sh/uv/guides/install-python/) · [PyTorch 공식 cu124 wheel](https://pytorch.org/get-started/previous-versions/#v260) · [PC CUDA 환경](training-cuda-handoff.md)
4. 3080 한 장씩 UUID를 마스킹해 CUDA 가시 장치 1개·CC 8.6·로컬 `cuda:0`을 확인한다. `nvidia-smi`로 해당 PID가 실제 할당 UUID에 있는지 대조한다. 저장소의 [CUDA smoke](../tools/cuda_training_smoke.py)를 재사용해 합성 입력 forward/backward, validation, 체크포인트 재로딩을 확인한다. 사라진 SSH 세션에서 작업이 계속되고 다른 세션으로 로그를 읽을 수 있는지도 시험한다. 마지막에 두 3080 독립 smoke를 동시에 실행해 가시성·VRAM·I/O를 확인한다. YOLO26n/s 본 실행 배치는 개발 입력으로 메모리 사전 점검을 마친 뒤 정한다. 비교에서 실제 optimizer updates, 유효 batch, 정밀도, seed를 기록한다.
5. GTX 1080 Ti는 Pascal용 커널이 포함된 torch/torchvision wheel 조합으로 검토할 수 있다. 사용 승인 후에만 별도 가상환경에서 `get_arch_list()`와 실제 CUDA 연산·NMS를 확인한다. Tensor Core가 없는 카드이므로 FP32 검증부터 하고 전처리·가벼운 검출 평가를 우선 검토한다. 현재 서버의 학습 성능과 wheel 호환성은 미측정이다. [NVIDIA Pascal 사양](https://developer.nvidia.com/cuda/gpus/legacy) · [PyTorch Pascal용 wheel 안내](https://pytorch.org/blog/pytorch-2-12-release-blog/)

## PC11~14 자료 전달과 검증

PC13을 입력 릴리스와 결과 수집의 기준으로 사용한다. PC11/12/14에만 있는 승인 가중치나 로그는 해당 PC에서 원본 해시를 계산해 PC13 또는 로컬 Windows로 수집한다. Windows에서 PC11~14와 연구실 서버 모두에 SSH가 됐고, 연구실 서버에서 PC13의 기존 SSH endpoint에 직접 연결하는 시험은 거부됐다. 기본 경로는 **PC13 → Windows → 연구실 서버**다. Windows OpenSSH `scp` 또는 `sftp`의 기존 SSH 경로를 사용한다. Windows 여유 공간이 부족하면 작은 단위로 나누거나 중계 경로를 별도로 검증한다.

- 릴리스는 승인된 train과 tune/dev-check를 분할별 디렉터리와 manifest로 내보낸다. 목록에서 지정한 M2, 외부 CCTV, P430의 개발 이미지·라벨, 타일과 parent ID, 출처·그룹·split, 계획·설정, 승인된 초기/비교 가중치, 보호 목록의 해시 메타데이터를 포함한다. 승인된 학습 입력과 별도로 P430의 기존 `tune/dev-check`를 평가 전용으로 배치한다. 11/24 최종 독립 영상·프레임·정답과 기존 평가 보호 자료는 전송 대상에서 제외한다.
- 대용량은 상대 경로로 만든 tar를 분할하거나 파일 묶음별로 전송한다. PC13 `Get-FileHash`의 소스 값과 Windows 및 서버 `sha256sum`을 대조하고, 서버에서는 압축 해제 전 아카이브 목록으로 경로·분할을 확인한 뒤 파일별 SHA-256, 수량, 그룹 교차를 검사한다. 불일치한 반입본은 승인하지 않는다. 회수할 때도 체크포인트·설정·결과의 해시를 서버와 PC13에서 확인한다.
- PC13에서 D0 `c6e5244f649de9722c956e0c861e98975c4334e08cdd9c0a6a74dd53f0e28d0a`, D1 `212a4b80e44674a3863daf240e127af797ac34f235a6e8356f23936b6348d190`, 기존 계획 `8a92eefb8f4bf275d5ace1aae46edb37ad7c6fce02a0484e497fec96deb0a28c`의 파일 해시를 확인했다. 전체 데이터의 서버 수신 검증은 전송 시 수행한다.
- 기존 [P430 실행기](../tools/run_p430_site.py)는 PC11~14 전용 노드명, 데이터 디렉터리 구조, 공용 `gpu0-training.lock`을 사용한다. Linux에서 해당 실행기의 자료 검증·평가 로직을 재사용하려면 서버 입력 경로와 장치별 잠금을 연결하고 공통 추출 순서와 예산을 확인해야 한다. Windows 절대 경로가 있는 YAML·이미지 리스트는 Linux 경로로 재생성한다. 원본 release는 보존하고 변환본과 새 해시를 별도 기록한다.

## GPU 예약·장시간 실행·복구

- 두 트랙에서 동일한 물리 UUID별 `flock`을 공유한다. 한 UUID에는 한 작업을 배정한다. 잠금을 획득한 뒤 `nvidia-smi -i "$GPU_UUID"`에서 허용 ID→전체 UUID와 10 GiB 규격을 확인하고, `--query-compute-apps=pid,used_memory --format=csv,noheader`로 해당 카드의 작업을 재확인한다. UUID 불일치, 다른 작업 점유, 잠금 실패 시 보류한다. `CUDA_VISIBLE_DEVICES=<전체 UUID>`를 해당 프로세스에만 설정하고 trainer에는 `device=0`을 전달한다. 이 잠금은 우리 프로젝트 안의 경쟁을 막는다. 연구실 전체의 독점 예약이 필요한 경우 운영자 일정이나 예약 시스템을 따로 확인한다. [Ultralytics 장치 선택](https://docs.ultralytics.com/reference/utils/torch_utils/#ultralytics.utils.torch_utils.select_device)
- Track A가 3080 두 장을 먼저 사용한다. Track B는 입력 승인 이후 비는 슬롯을 넘겨받는다. 트랙별 run ID·출력·로그·설정 캐시를 분리하고 승인 데이터는 공용 읽기 전용 입력으로 재사용한다. PC11~14의 기존 작업은 그대로 진행한다. 스왑·공용 CPU/I/O 경합을 줄이기 위해 처음에는 작은 worker 수로 동시에 점검한다. 초기 운영은 두 개의 독립 단일 GPU 작업으로 구성한다.
- 사용자 홈에서 `nohup`으로 표준 입력을 닫고 작업별 stdout/stderr를 저장한다. PID, 시작 시각, UUID, 데이터/설정/소스 해시, 상태, 종료 코드를 남긴다. 재접속해 `tail -F`, PID와 시작 시각, `results.csv` 마지막 행, 해당 UUID의 GPU 상태를 함께 확인한다. 연결 해제 유지 시험을 통과한 방식으로만 본 실행에 사용한다. 호스트 재부팅이나 로그아웃 정책으로 종료되면 원인을 남기고, 동일 조건의 optimizer 상태가 들어 있는 최신 학습 체크포인트와 manifest를 검증해 새 시도 ID로 재개한다. optimizer가 빠진 가중치는 새 fine-tuning의 초기값으로만 사용한다. 자동 부팅 재개가 필요하면 연구실 스케줄러나 사용자 서비스 지속 권한을 확인한다.
- 현재 3090을 배정받으려면 소유 작업이 끝나고 연구실 측 사용 허가가 있어야 한다. GTX 1080 Ti 사용, 공유 디스크로의 이동, 장기 디스크 예약도 해당 권한을 확인한 뒤 진행한다. 초기 홈 환경 및 허용된 3080을 대상으로 한 사용자 범위 계획에는 관리자 설정이 필요하지 않다.

[Track A 실험 및 장비 배정](p430-phase2-optimization-plan.md)
