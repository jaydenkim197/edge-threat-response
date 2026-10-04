# CUDA / Colab Training Handoff

상태: runner·config·preflight·notebook `IMPLEMENTED`, PC contract 및 RTX 3060 synthetic CUDA/AMP smoke `VERIFIED`, 실제 데이터 CUDA full training `PLANNED`

## 목적과 gate

legacy development dataset을 사용하는 아래 Baseline v1 절차는 다른 팀원의 L0 재현 트랙이다. 신규 detector 담당자의 source audit·학습 환경 준비를 막지 않는다. L0 실행은 로컬 `data/review/legacy-development-v1/review.csv`의 표본 검수와 승인을 전제로 한다. 신규 R1/H1 학습은 [Dataset Source Strategy](dataset-source-strategy.md)의 source·label·split 승인 후 별도 config/run ID로 진행한다. legacy config를 그대로 신규 SOHAS recipe로 사용하지 않는다.

`configs/training/cuda-baseline-v1.json`의 epochs, patience, imgsz, batch와 seed는 첫 development baseline용 기본값이다. 연구 최종 파라미터나 모델 채택 결정이 아니다.

## R1/H1 실행 준비 — 2026-10-04

**준비 코드와 승인 차단은 구현됐고, 실제 SOHAS 전체 학습은 아직 시작하지 않았다.** 아래는 신규 detector 트랙이다. 기존 legacy/Colab 절차와 혼용하지 않는다.

- R1: 승인된 SOHAS knife 양성 + 실제 knife 부재를 검수한 음성.
- H1: R1과 **같은 고유 train 양성**만 사용. 음성은 train에서 제외한다.
- 두 조건은 공통 tuning validation과 공통 final-test 목록을 쓴다. 최종 test를 후보 선택이나 threshold 튜닝에 사용하지 않는다.
- 입력은 원본 VOC candidate나 웹 표본 pack이 아니라, 권리·좌표·knife 누락·음성·중복·group split 검토를 끝낸 `materialized-manifest.jsonl`이다. `source_dataset=sohas`, model-local class `0=knife`, 올바른 images/labels 대응 경로가 필요하다. 이 승인된 SOHAS export는 현재 미준비다.

`configs/training/sohas-pair.pc13.json`은 **development 제안값**이다. YOLO26n의 같은 로컬 pretrained weight, 640px, batch/nbs 16, 50 epochs, 명시적 SGD·seed, FP32, warmup 0, early stop 비활성화를 사용한다. batch/해상도/optimizer/augmentation은 pilot 이후 두 조건을 함께 재생성·재승인하며 연구 최종값으로 간주하지 않는다.

데이터량 차이를 통제하기 위해 train 목록을 batch 배수 길이로 맞추고 H1 양성을 균형 반복한다. 같은 epoch마다 같은 sample draw 수와 계획된 optimizer update 수를 사용한다. 고유 이미지 수·반복 횟수는 manifest에 별도 남긴다. 이는 **음성 포함 recipe 비교**이며 음성 하나의 순수 인과효과가 아니다. 실제 완료 epochs·trainer 로그·LR schedule은 실행 후 다시 확인한다. `amp=false`는 초기 budget 통제를 위한 설정이지 Orin 추론 정밀도 결정이 아니다. 로컬 Ultralytics 8.4.152의 실제 YOLODataset에서 합성 입력 반복 목록 길이 보존을 확인했다(R1 6 draws/5 unique/3 backgrounds, H1 6 draws/2 unique/0 backgrounds). 실제 SOHAS loader·학습 검증을 대신하지 않는다.

PC13 저장소에서 먼저 **학습을 하지 않는** readiness를 실행한다. 출력은 항상 새 경로를 사용한다.

```powershell
$env:PYTHONPATH = 'src'
.\.venv-ml\Scripts\python.exe -m edge_threat_response.training_pair check --plan configs/training/sohas-pair.pc13.json --manifest data/processed/sohas-approved-v1/materialized-manifest.jsonl --checkpoint yolo26n.pt --output-dir runs/sohas-pair-readiness-NEW-ID
```

CUDA 또는 입력 부재는 exit 2 / `blocked`, 입력이 있어도 `inputs_present_approval_pending`일 뿐 승인 완료가 아니다. 이 명령은 모델을 로드하거나 다운로드하거나 학습하지 않는다.

승인 가능한 materialized export와 로컬 checkpoint가 준비되면:

```powershell
.\.venv-ml\Scripts\python.exe -m edge_threat_response.training_pair prepare --plan configs/training/sohas-pair.pc13.json --manifest data/processed/sohas-approved-v1/materialized-manifest.jsonl --checkpoint yolo26n.pt --output-dir data/processed/sohas-pair-v1
```

출력은 R1/H1별 data YAML·train 목록·고유-image manifest·training config, 공통 val/test 목록, `pair-preparation.json`, **모든 gate=false인 `approval.pending.json`**이다. prepare 성공은 source 승인이나 학습 성공이 아니다. 원본 이미지는 복사·수정하지 않는다.

담당자가 근거를 확인한 뒤 pending 파일을 별도 `approval.approved.json`으로 복사해 `status=approved`, 승인 ID·검수자 별칭·날짜와 gate를 기록한다. `rights/human_review/labels_coordinates/negative_absence/duplicates_groups/split/recipe`가 전부 승인되어야 한다. 이름·credential 대신 별칭을 사용하고 파일은 ignored 데이터 공간에 둔다. 자동으로 true를 채우지 않는다. 승인 파일은 config/YAML/manifest/초기 weight/세 목록의 SHA-256을 묶으며, runner는 이미지·label bytes와 목록 반복 횟수까지 재검사한다. 승인 후 파일을 바꾸면 다시 승인한다.

승인 뒤 R1 preflight 예시이며 H1도 같은 방식으로 진행한다:

```powershell
$env:CUBLAS_WORKSPACE_CONFIG = ':4096:8'
.\.venv-ml\Scripts\python.exe -m edge_threat_response.training --config data/processed/sohas-pair-v1/R1-training.json --data data/processed/sohas-pair-v1/R1-data.yaml --dataset-manifest data/processed/sohas-pair-v1/R1-manifest.jsonl --approval data/processed/sohas-pair-v1/approval.approved.json --output-dir runs/R1-preflight-NEW-ID --preflight-only --require-cuda
```

실제 실행은 preflight 확인 후 **`--require-cuda`를 유지하고 `--preflight-only`만 제거**한다. 고유 `--run-name`과 output root를 지정하며 batch 단독 override는 금지한다. 장시간 실행은 아래 SSH 종료 지속 방식에 stdout/stderr·exit code를 남기고 기존 GPU job과 중복 launch하지 않는다. 이번 작업에서는 이 실제 실행을 하지 않았다.

완료 후 비교:

```powershell
.\.venv-ml\Scripts\python.exe -m edge_threat_response.training_pair compare --r1 runs/training/R1-NEW-ID-invocation.json --h1 runs/training/H1-NEW-ID-invocation.json --output-dir runs/R1-H1-comparison-NEW-ID
```

비교기는 동일 checkpoint·공통 평가 목록·계획 budget·설정·package 버전을 검사하고 공통 validation 지표 차이를 기록한다. invocation에는 commit/config/manifest/승인 hash, 환경, duration, metrics, checkpoint hash가 남는다. 이 요약만으로 detector를 선정하지 않는다. 같은 tuning 자료에서 small/distant knife recall, threshold를 명시한 hard-negative FP, CCTV 오류와 필요 시 다른 seed를 확인한다. 이후 최종 holdout은 한 번 평가하고, 선택 weight를 동일하게 고정해 B0~B3 사건 실험으로 넘어간다. Orin/GPIO 검증은 별도다.

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

실제 학습은 승인한 dataset과 manifest를 PC13 내장 디스크에 둔 후 기존 `etr-train --preflight-only --require-cuda`로 확인하고 시작한다. Windows 초기 설정은 `device=0`, `workers=0`, `cache=false`, 명시적 batch를 사용하고, 최종 batch/해상도/학습 budget은 별도 결정한다. 학습 중 데이터 I/O와 run 결과의 기준 위치는 PC13이다. Drive 연결이나 자동 업로드는 설정하지 않았으므로 오프사이트 백업 완료로 간주하지 않는다.

검증 증거: [RTX 3060 CUDA smoke](../reports/training/pc13-cuda-smoke-2026-10-02/report.md). 설치 근거: [PyTorch 공식 CUDA wheel 조합](https://pytorch.org/get-started/previous-versions/), [Ultralytics 설치 안내](https://docs.ultralytics.com/quickstart/).

## Cloud에서 장시간 작업을 이어받는 경우

2026-10-02 Cloud 인계에서 pure/review Python 코드·테스트 실행은 가능했으나 published 환경인지 확인하는 도구/증거는 없었다. onboarding draft 저장을 publication으로 해석하지 않는다. GPU 장치는 확인되지 않았고 실제 full training을 Cloud CPU에서 실행하지 않았다. 사용자가 제공한 학습 PC 사설 주소의 SSH는 짧은 timeout·BatchMode·strict host-key check로 점검했으나 TCP/22 `Connection refused`로 인증 전에 실패했다. 이 결과만으로 PC의 SSH 서비스 상태나 Tailscale/VPN 상태를 확정하지 않는다.

Cloud에서 학습 PC로 접근하려면 지원되는 private network/VPN 경로와 PC SSH 접근 설정이 필요하다. 연결이 복구된 뒤 기존 인증·GPU 점유·repo/config/dataset hash를 확인한다. 키 추출/복사나 별도 Tailscale 설치·방화벽 변경·공개 포트 개방·로컬 노트북 우회 실행을 기본으로 하지 않는다.

실제 recipe 승인이 나면 고유 run ID와 commit/config/dataset hash, stdout/stderr, status/exit code, checkpoints를 보존하고 실행 중인 GPU job과 중복 launch하지 않는다. 로컬 SSH 종료 후 생성 데이터 GPU 작업의 지속성은 아래의 작은 시험으로 확인했지만, full training·재부팅/절전 지속·Drive 인증/업로드는 미검증이다.

### Windows SSH 종료 후 작업 지속 — 2026-10-03

- `Start-Process powershell.exe -WindowStyle Hidden`만 사용한 첫 시험은 SSH 종료 후 사라졌으며 학습 summary/exit code가 생성되지 않았다. 이 PC에서 이를 detached 학습 실행 방법으로 쓰지 않는다.
- 두 번째 시험은 `Invoke-CimMethod -ClassName Win32_Process -MethodName Create`로 `powershell.exe -NoProfile -WindowStyle Hidden -EncodedCommand ...`를 생성했다. 관리자 권한·예약 작업·서비스·방화벽 변경 없이 현재 계정에서 ReturnValue 0으로 실행됐다. 시작 SSH를 종료한 뒤 15초 지연을 거쳐 기존 CUDA smoke helper가 실행됐다.
- 이 방식은 parent SSH 프로세스에 직접 매달리지 않는 실행 경로다. 실제 실행 body에는 repo 절대 경로, 고유 output, stdout/stderr redirect 및 `$LASTEXITCODE` 저장이 필요하다. UTF-16LE Base64는 인코딩일 뿐 비밀정보 보호 기능이 아니다. credential을 body에 넣지 않는다.
- 신규 SSH에서 확인한 `runs/pc13-cim-smoke-20261002/exit-code.txt`는 0, `training/smoke-summary.json`은 passed였다. 생성 8 train/4 val, CUDA/AMP 1 epoch, validation·best/last·checkpoint reload GPU inference 통과, runner duration 5.875 s다. run 이름의 날짜는 시작 시 사용한 식별자이며 완료 확인은 10월 3일이다.
- 원시 stdout/stderr·launcher PID·exit code·training evidence를 같은 ignored run에 보존했다. 첫 실패 run도 보존한다. 새 세션의 확인 명령은 종료된 launcher PID 조회 때문에 shell exit 1이었으나 학습 exit 0·summary passed와 구분했다.
- 이번 시험은 단기 연결 종료만 검증했다. Windows 재부팅·절전·로그아웃·장시간 열 안정성·재시작/자동 resume는 확인하지 않았다. PC 전원이 꺼지면 학습은 계속되지 않는다. 실제 dataset 학습 승인 조건도 그대로다.

## Windows SOHAS staging 주의사항

2026-10-02 로컬→학습 PC SSH 연결과 `0b51dd4`의 VOC audit를 재검증했다. Cloud 연결 복구를 뜻하지는 않는다. 원격 전체 70 tests 및 byte-exact annotation audit가 통과했다.

Windows의 `core.autocrlf=true` checkout은 XML 줄바꿈을 바꾸어 pinned Git blob 검사에 실패할 수 있다. 검사나 원본을 수정하지 않고, **새 staging clone에서만** `git clone --config core.autocrlf=false --filter=blob:none --no-checkout ...`를 사용한 뒤 기존 label/XML-only sparse checkout과 고정 upstream commit checkout을 수행한다. 전역 Git 설정은 변경하지 않는다. 이미지 경로를 sparse checkout에 추가하지 않는다.

원격 정상 staging은 `data/source-audit/sohas-upstream-byte-exact/`, 결과는 `data/source-audit/sohas-voc-pc13-byte-exact-20261002/`다. 초기 실패 staging/output도 원인 증거로 보존했다. `review-sample.csv`는 100개 **라벨 기준 검수 대기 목록**이며 이미지나 완료된 사람 판정이 아니다. 권리·좌표·이미지 검수·group/split 승인은 계속 필요하다.

## SOHAS 이미지 표본 검수 실행

```powershell
.\.venv-ml\Scripts\python.exe tools/sohas_review_images.py --source-root data/source-audit/sohas-upstream-byte-exact --sample-csv data/source-audit/sohas-voc-pc13-byte-exact-20261002/review-sample.csv --output data/review/unique-sohas-review
```

입력 sample CSV의 image paths만 pinned sparse checkout에 추가한 후 실행한다. helper는 다운로드/학습/label export를 하지 않고 기존 source blob 검사·VOC parser와 Pillow를 사용한다. output은 source 밖의 새 디렉터리여야 한다. 원본 dimension과 XML dimension이 다르거나 blob/annotation 검사가 실패하면 중단한다. CSV의 reviewer는 비워 두며 raw bbox overlay를 coordinate convention 승인으로 해석하지 않는다. 본 학습은 검수·split·recipe 승인 이후다.

2026-10-03 이후 helper는 `images/`에 byte-exact 원본과 evidence의 `image_file`/`knife_boxes_xyxy_raw`도 저장한다. 기존 pack을 덮어쓰지 말고 새 output으로 생성한다. 원격에서 생성한 `sohas-click-review-20261003/` pack은 노트북에도 복사됐으며, 로컬 `tools/start_review.ps1`을 실행해 브라우저에서 검수할 수 있다. 이전 contact-sheet-only pack은 웹 입력으로 바로 사용할 수 없다.

표준 CLI는 `etr-review --review-dir PATH`다. 설치하지 않고 실행하려면 저장소에서 `$env:PYTHONPATH = (Join-Path (Get-Location).Path 'src')`를 지정한 뒤 `python -X utf8 -m edge_threat_response.dataset.review_web --review-dir PATH`를 실행한다. Windows launcher가 이를 자동으로 처리한다. 현 로컬 setuptools의 editable install은 한글 경로의 `.pth` 생성에서 cp1252 오류가 났으므로 성공했다고 기록하지 않는다. 일반 wheel build와 정적 UI 자산 포함은 검증됐고 시스템 locale·전역 package는 변경하지 않았다.

웹 서버/판정 저장은 노트북 내부에서만 동작하며 학습 PC의 full training을 시작하지 않는다. 테스트는 `--database`로 별도 DB를 지정하고 실제 사람 판정 DB를 사용하지 않는다. source·좌표·group/split 검토와 recipe 승인 절차는 불변이다.

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

preflight가 `passed`인 경우에만 `--preflight-only`를 제거해 실제 학습을 시작한다. `--require-cuda`는 유지한다.

## 결과 반입

- `best.pt`와 `last.pt`는 Git에 넣지 않고 통제된 모델 저장 위치에 둔다.
- invocation JSON에 기록된 Git commit, config/dataset manifest hash와 artifact SHA-256을 보존한다.
- Git에는 민감하거나 대용량인 run 원본 대신 검토된 요약 report만 추가한다.
- Baseline v1은 detector pipeline 통합과 외부-data v2 비교 기준이며, controlled scenario의 최종 연구 결과가 아니다.

## Knife bbox 후보 평가 — 2026-10-04

`edge_threat_response.detection_evaluation`은 canonical detection JSONL을 source_id/frame_index로 image truth에 연결해 confidence-first greedy IoU 일대일 대응을 계산한다. 같은 truth·policy를 모든 후보에 사용한다. Duplicate detection은 FP이며 confidence 이상 knife만 계산한다. Person은 이 knife-only 평가에서 제외한다. 실제 mAP는 기존 Ultralytics validation을 별도 사용한다.

```powershell
$env:PYTHONPATH = 'src'
.\.venv-ml\Scripts\python.exe -m edge_threat_response.detection_evaluation --ground-truth tests/fixtures/evaluation/detection-truth.json --detections tests/fixtures/evaluation/detection-predictions.jsonl --policy configs/evaluation/detection-synthetic.example.json --output-dir runs/detection-evaluation-synthetic-NEW-ID
```

가상 fixture는 TP2/FP2/FN1·작은 bbox TP1/GT2·음성 image FP1을 확인하는 계약 검사다. 실제 detector 결과가 아니다. 예시 confidence=.5/IoU=.5/normalized area cutoff=.02는 연구 최종값이 아니다. 실제 tuning policy에 명시적으로 선택·기록하고 최종평가 전에 `status=frozen`으로 동결한다.

실제 image truth schema는 fixture 구조를 재사용하되 `status=approved`, `partition=tuning` 또는 `final_test`, image마다 `image_sha256`(SHA-256)·`source_group`·원본 pixel width/height·완전한 `knife_boxes_xyxy`를 기록한다. 음성은 빈 box 배열과 `knife_absence_verified=true`가 필수다. `final_test`는 frozen policy만 받는다. 웹 후보 manifest는 승인 truth가 아니며 그대로 입력할 수 없다. approved/frozen 표시는 선언이지 사용자 신원이나 권리를 자동 인증하는 기능이 아니다.

Prediction이 없거나 중복/추가되거나 missing/detector_error이면 평가를 거부한다. 이는 실행 오류를 silently FN/정상 음성으로 섞는 것을 막는다. 모든 image에 canonical `valid` row(미검출은 detections=[])를 생성하고 입력 failure는 별도 보고·수정한다. 실제 `etr-detect` summary의 input/model/config SHA-256을 함께 보관하며, 이 평가기만으로 동일 모델·동일 image inference를 증명하지 않는다.

출력 `summary.json`에는 micro TP/FP/FN·precision/recall/F1, GT normalized bbox area 기준 small_box_recall, 검증된 음성 image 중 FP가 있는 비율과 FP box/image·분모, 세 입력 hash·commit이 남는다. `image-matches.jsonl`에 TP IoU·FP prediction index·FN GT index를 남긴다. 분모0은 null이다. 작은 bbox는 실제 거리와 동의어가 아니고, image FP는 event 오경보/h 또는 GPIO 지연과 다르다. 본 사건 지표에는 기존 사건 평가기와 수동 start/end 정답을 사용한다.
