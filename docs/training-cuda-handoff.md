# CUDA / Colab Training Handoff

상태: runner·config·preflight·notebook `IMPLEMENTED`, PC contract 및 RTX 3060 synthetic CUDA/AMP smoke `VERIFIED`, 실제 데이터 CUDA full training `PLANNED`

## 목적과 gate

legacy development dataset을 사용하는 아래 Baseline v1 절차는 다른 팀원의 L0 재현 트랙이다. 신규 detector 담당자의 source audit·학습 환경 준비를 막지 않는다. L0 실행은 로컬 `data/review/legacy-development-v1/review.csv`의 표본 검수와 승인을 전제로 한다. 신규 R1/H1 학습은 [Dataset Source Strategy](dataset-source-strategy.md)의 source·label·split 승인 후 별도 config/run ID로 진행한다. legacy config를 그대로 신규 SOHAS recipe로 사용하지 않는다.

`configs/training/cuda-baseline-v1.json`의 epochs, patience, imgsz, batch와 seed는 첫 development baseline용 기본값이다. 연구 최종 파라미터나 모델 채택 결정이 아니다.

## Windows RTX 3060 원격 학습 PC — 2026-10-02

- 작업 경로: `C:\Class6\edge-threat-response`; Python: `.venv-ml\Scripts\python.exe`.
- RTX 3060 12 GB, i9-13900, RAM 약 32 GB, Python 3.12.4. 설치 전 C 드라이브 여유 약 149.8 GiB.
- NVIDIA driver 560.94를 유지했다. PyTorch 2.6.0+cu124 / torchvision 0.21.0+cu124, Ultralytics 8.4.152, NumPy 1.26.4, OpenCV 4.11.0.86을 격리 환경에 설치했다. 이는 이 학습 PC에서 확인한 조합이며 Orin 환경 고정값이 아니다.
- SSH 접속 주소는 팀이 전달한 값을 사용한다. 계정 키·비밀번호는 저장소에 보관하지 않는다. 다른 PC도 독립 clone/venv를 사용하고, 한 PC의 GPU에서 여러 full run을 동시에 실행하는 것은 기본으로 하지 않는다.

원격 PowerShell에서 실행한다. 전역 Anaconda나 GPU driver를 변경하지 않는다.

```powershell
Set-Location C:\Class6\edge-threat-response
git pull --ff-only
$env:CUBLAS_WORKSPACE_CONFIG = ':4096:8'
.\.venv-ml\Scripts\python.exe -m pip check
.\.venv-ml\Scripts\python.exe -m unittest discover -s tests -q
.\.venv-ml\Scripts\etr-train.exe --help
```

다른 빈 작업공간에서 같은 환경을 재구성할 때:

```powershell
python -m venv .venv-ml
.\.venv-ml\Scripts\python.exe -m pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cu124
.\.venv-ml\Scripts\python.exe -m pip install --no-cache-dir -r configs/training/requirements-pc13.txt
.\.venv-ml\Scripts\python.exe -m pip install -e . --no-deps
.\.venv-ml\Scripts\python.exe tools/cuda_training_smoke.py --output runs/unique-cuda-smoke --amp
```

`requirements-pc13.txt`는 핵심 의존성 pin이며 모든 전이 의존성 lock은 아니다. 실제 전체 설치 목록은 원격 `runs/pc13-cuda-amp-smoke-20261002/environment-freeze.txt`에 보존했다. smoke output 경로는 새 이름을 사용하며 기존 run을 덮어쓰지 않는다. rectangle 8 train/4 val은 비민감 생성 입력이며 knife 품질·성능을 평가하는 데이터가 아니다.

실제 학습은 승인한 dataset과 manifest를 PC 로컬에 둔 후 기존 `etr-train --preflight-only --require-cuda`로 확인하고 시작한다. Windows 초기 설정은 `device=0`, `workers=0`, `cache=false`, 명시적 batch를 사용하고, 최종 batch/해상도/학습 budget은 별도 결정한다. 학습 중 데이터 I/O는 로컬, 승인 데이터·결과의 보관은 팀 Google Drive를 따른다. Drive 연결이나 자동 업로드는 이번에 설정하지 않았다.

검증 증거: [RTX 3060 CUDA smoke](../reports/training/pc13-cuda-smoke-2026-10-02/report.md). 설치 근거: [PyTorch 공식 CUDA wheel 조합](https://pytorch.org/get-started/previous-versions/), [Ultralytics 설치 안내](https://docs.ultralytics.com/quickstart/).

## Colab 절차

`notebooks/baseline-v1-colab.ipynb`를 Colab에서 열고 위에서 아래로 실행한다. notebook의 `REVIEW_APPROVED` 기본값은 `False`이며, review 결과를 팀이 확인한 뒤에만 직접 `True`로 바꾼다.

Notebook은 다음 순서로 동작한다.

1. GPU와 CUDA 접근을 확인한다.
2. 현재 저장소와 고정 submodule을 clone한다.
3. dataset audit → group-aware split → knife-only materialization을 재생성한다.
4. config, data YAML, materialized manifest와 Git commit을 preflight evidence에 기록한다.
5. Google Drive 아래 run directory에 training invocation, checkpoint, metric과 artifact hash를 기록한다.

Colab의 GPU 종류·사용 한도·runtime 지속 시간은 고정되어 있지 않다. `last.pt`와 `*-invocation.json`을 Drive에 보존하고 중단 시 새 run ID로 재개 기록을 남긴다. 기존 run directory를 덮어쓰지 않는다.

## CLI 계약

```text
etr-train \
  --config configs/training/cuda-baseline-v1.json \
  --data data/processed/knife-legacy-development-v1/data.yaml \
  --dataset-manifest data/processed/knife-legacy-development-v1/materialized-manifest.jsonl \
  --output-dir /content/drive/MyDrive/edge-threat-response/runs \
  --preflight-only --require-cuda
```

preflight가 `passed`인 경우에만 `--preflight-only --require-cuda`를 제거해 실제 학습을 시작한다.

## 결과 반입

- `best.pt`와 `last.pt`는 Git에 넣지 않고 통제된 모델 저장 위치에 둔다.
- invocation JSON에 기록된 Git commit, config/dataset manifest hash와 artifact SHA-256을 보존한다.
- Git에는 민감하거나 대용량인 run 원본 대신 검토된 요약 report만 추가한다.
- Baseline v1은 detector pipeline 통합과 외부-data v2 비교 기준이며, controlled scenario의 최종 연구 결과가 아니다.
