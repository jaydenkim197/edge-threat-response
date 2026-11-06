# PC14 CUDA 학습 환경과 추가 PC 연결 — 2026-11-06

**PC14의 격리 학습 환경 설치와 CUDA 학습 smoke가 통과했다.** PC11·PC12도 공개키 등록 후 실제 SSH 인증·GPU 사양 조회에 성공했다. PC14에서 실제 데이터셋 전체 학습은 시작하지 않았으며, PC11·PC12의 학습 환경은 아직 설치·검증하지 않았다.

## 확인한 장치

| 항목 | PC11 | PC12 | PC14 |
|---|---|---|---|
| Tailscale IP | 100.120.195.40 | 100.78.203.54 | 100.69.149.56 |
| SSH 계정 / hostname | pc11 / 3153-11 | pc12 / 3153-12 | pc14 / DESKTOP-BD5OAMN |
| 공개키 인증·명령 실행 | 통과 | 통과 | 통과 |
| GPU | RTX 3060 12GB | RTX 3060 12GB | RTX 3060 12GB |
| 드라이버 | 610.88 | 610.88 | 560.94 유지 |
| CPU / RAM | i9-13900 / 31.75GiB | i9-13900 / 31.75GiB | i9-13900 / 31.75GiB |
| C 드라이브 여유 snapshot | 196.23GiB | 179.42GiB | 설치 전 143.41GiB |
| 학습 환경 | 미검증 | 미검증 | 아래 CUDA 검증 통과 |

PC11/12의 기본 `python`은 WindowsApps 경로로 확인됐다. 이것만으로 실제 Python interpreter 설치 여부를 단정하지 않는다. Git은 당시 PATH에서 발견되지 않았다. 이전 연결 기록의 PC11/12 키 인증 거부는 사용자 등록 후 **해결**됐다.

## PC14 구성

- 저장소: `C:\Class6\edge-threat-response`. 공개 GitHub clone을 **`cb5cb7002558e6c3c04273ffdc3154a48fd628ec` detached HEAD**로 고정했다. 기존 경로가 없는 것을 확인하고 새로 만들었다. 다른 사용자 자료를 이동하거나 덮어쓰지 않았다.
- Python: 기존 Anaconda Python 3.12.4 기반 **`.venv-ml`**. 전역 Anaconda 패키지·GPU 드라이버는 변경하지 않았다.
- 패키지: **torch 2.6.0+cu124 / torchvision 0.21.0+cu124 / Ultralytics 8.4.152 / NumPy 1.26.4 / OpenCV 4.11.0.86 / Pillow 12.3.0**. PC13의 실제 설치 버전과 기존 `configs/training/requirements-pc13.txt`를 확인해 재사용했다.
- PC14에 Git이 확인되지 않아 `C:\Class6\tools\mingit-2.51.2`에 공식 MinGit을 설치했다. 공식 release asset SHA-256 `8f0a7bc389c0bccc9daf6107cff4efb176348e34b8d787f02a36679a5588e072`을 검증했다. 기존 사용자 PATH를 보존·백업하고 Git cmd 경로만 추가했다. 새 SSH 세션에서 `git --version` 응답을 확인했다.
- 로컬 노트북의 기존 SSH config는 백업 후 `pc11`, `pc12`, `pc14` alias를 추가했다. 각 alias는 기존 전용 키를 지정하며 키 본문·비밀번호를 Git에 기록하지 않았다.
- 초기 YOLO26n pretrained weight는 PC13의 기존 파일을 재사용했다. 5,544,453bytes / SHA-256 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`. 새 학습된 M1 weight가 아니다. 원본 데이터셋·검수 DB·판정은 전송/변경하지 않았다.
- 설치 로그/상태: PC14 `C:\Class6\setup-pc14-20261106-v1`. 원본 검증 로그·생성 합성 입력·checkpoint: `C:\Class6\edge-threat-response\runs\pc14-cuda-readiness-20261106-v1`.

## 실행 검증

| 검사 | 실제 결과 |
|---|---|
| Git provenance / pretrained weight hash | 고정 commit·checkpoint 일치 |
| `pip check` | No broken requirements found |
| `compileall -q src tools` | 통과 |
| `unittest ... -p test_training*.py` | **15 tests 통과**, 1.977s |
| `unittest ... -p test_raw_training.py` | **10 tests 통과**, 0.730s |
| `unittest ... -p test_hoi.py` | **7 tests 통과**, 0.170s |
| `etr-train --help` / `etr-hoi --help` | 모두 통과 |
| CUDA tensor forward/backward | 유한 gradient, 동기화 통과 |
| 기존 `cuda_training_smoke.py`, FP32 | 합성 train8/val4, 1epoch 학습·validation·best.pt/last.pt·checkpoint 재로딩 추론 통과 |
| 동일 도구, `--amp` | 같은 입력·1epoch, **AMP 실제 활성화** 및 checkpoint 재로딩 추론 통과 |
| 기존 `verify_hoi_smoke.py --inference-device cuda:0` | 합성 G/VG 학습·재로딩 일치, CUDA 추론·B4 연결·4frame/1event/1snapshot 통과. HOI 학습은 도구의 CPU 설정이며 **실제 HOI CUDA 학습 검증은 아님** |

제품 전체 테스트 재실행을 뜻하지 않는다. 이번 목적에 해당하는 **32개 테스트**와 실제 CUDA smoke를 실행했다. 합성 입력의 검출 지표·짧은 학습 시간은 실제 칼 정확도·full run 소요·Orin 성능의 근거로 사용하지 않는다.

Ultralytics의 새 config 경로 부모가 생성되기 전 CWD에 `Ultralytics/settings.json`·`Arial.ttf`가 만들어진 것을 발견했다. 두 파일만 있는지 확인하고 해시를 보존해 `runs/yolo-config/Ultralytics`로 이동했다. 실제 GPU 추론을 다시 실행하고 repo clean을 확인했다. 이후 명령에는 `YOLO_CONFIG_DIR` 경로를 미리 만들고 설정한다. 원본 데이터 이동/삭제가 아니다.

## 재사용 방법과 남은 작업

PC14 원격 PowerShell에서:

```powershell
Set-Location C:\Class6\edge-threat-response
$env:YOLO_CONFIG_DIR = 'C:\Class6\edge-threat-response\runs\yolo-config'
$env:YOLO_AUTOINSTALL = 'false'
$env:CUBLAS_WORKSPACE_CONFIG = ':4096:8'
.\.venv-ml\Scripts\python.exe -m pip check
.\.venv-ml\Scripts\etr-train.exe --help
```

freeze된 checkout을 무조건 pull하거나 현재 run 자료를 덮어쓰지 않는다. 새 실험마다 source commit·manifest·config·weight hash와 GPU lock을 기록한다. 한 GPU에서 full run을 동시에 두 개 실행하지 않는다. 실제 데이터는 PC13의 기준 manifest와 보호 split을 유지한 채 별도 run용 cache·전송 검증 후 사용해야 한다.

다음은 Q1 정제 manifest/학습 설정 준비와 실제 데이터 전송·preflight다. 합성 smoke 통과를 실제 corpus의 학습 승인이나 full training 완료로 해석하지 않는다. PC11/12 추가 학습 환경, 실제 사람 Holding 데이터/학습, 실제 CCTV·GPIO·Orin 성능 검증은 별도다.

## 공개 증거와 설치 근거

- [설치 상태](bootstrap-state.json), [검증 상태](verification-state.json), [환경](environment.json), [전체 설치 목록](environment-freeze.txt), [pip check](pip-check.txt)
- [FP32](fp32-smoke.json), [AMP](amp-smoke.json), [HOI](hoi-smoke.json), [캐시 이동·추론 재검증](cache-relocation.json)
- [학습 테스트15개](training-tests.txt), [RAW 테스트10개](raw-training-tests.txt), [HOI 테스트7개](hoi-tests.txt)
- 공식 [PyTorch 이전 버전 설치 조합](https://pytorch.org/get-started/previous-versions/), [MinGit release](https://github.com/git-for-windows/git/releases/tag/v2.51.2.windows.1). 전이 의존성 전체 lock은 아니며 실제 설치 목록을 증거로 보존했다.
- 이번 작업은 기존 PC13 pin·표준 `venv`·기존 smoke 도구를 **재사용**했다. 제품 기능·평가 기준·새 의존성 추상화를 추가하지 않았다. commit/push는 이 보고서를 추가한 Git 이력으로 추적한다.
