# PC11·PC12 CUDA 학습 환경 검증 — 2026-11-06

**PC11·PC12 모두 PC14와 동일한 Python 3.12.4 및 43개 패키지 버전으로 학습 환경을 설치하고 검증했다.** 각 PC에서 관련 테스트 32개와 CUDA forward/backward·YOLO26n FP32/AMP 학습·checkpoint 재로딩·합성 HOI CUDA 추론을 통과했다. 전체 데이터셋 학습·실제 HOI 학습·학습 데이터 전송은 실행하지 않았다.

## 구성과 보존 범위

| 항목 | PC11 | PC12 |
|---|---|---|
| SSH | `pc11@100.120.195.40` | `pc12@100.78.203.54` |
| 장치 | 3153-11 / i9-13900 / RAM31.75GiB | 3153-12 / i9-13900 / RAM31.75GiB |
| GPU / 드라이버 | RTX3060 12GB / 610.88 유지 | RTX3060 12GB / 610.88 유지 |
| 기존 base Python | `C:\ProgramData\anaconda3\python.exe` / 3.12.4 | `C:\Users\PC12\anaconda3\python.exe` / 3.12.4 |
| 새 저장소 / venv | `C:\Class6\edge-threat-response` / `.venv-ml` | 같은 프로젝트 경로 / `.venv-ml` |
| source | `cb5cb7002558e6c3c04273ffdc3154a48fd628ec`, detached HEAD | 동일 commit |
| 설정/테스트 후 Git 상태 | clean | clean |
| 기존 43개 reference 패키지와 버전 대조 | 일치, 추가 패키지 없음(프로젝트 제외) | 일치, 추가 패키지 없음(프로젝트 제외) |

PC11에는 별도 Python3.13도 있었지만 사용하지 않았다. PC12의 기존 `C:\Class6` 자체는 보존하고, 존재하지 않았던 프로젝트/tools 경로만 새로 만들었다. 기존 Python·Anaconda의 전역 패키지·드라이버·다른 workspace·PC13 검수 서버/DB/원본 데이터는 변경하지 않았다. 사용자 PATH는 백업 후 MinGit cmd 경로만 추가했고 새 SSH 세션의 Git provenance를 확인했다.

주요 패키지는 **PyTorch2.6.0+cu124 / torchvision0.21.0+cu124 / Ultralytics8.4.152 / NumPy1.26.4 / OpenCV4.11.0.86 / Pillow12.3.0**다. 이전 [PC14 실제 설치 목록](../pc14-cuda-readiness-2026-11-06/environment-freeze.txt)에서 editable 프로젝트 항목을 분리한 [43개 버전 고정 목록](reference-packages.txt)을 재사용했다. 기준 파일 SHA-256은 `749512e9c79be826f1f1d2f9ef66104f2aa59f181f4375cf3ffba776dd6fc33b`다. clone/source와 프로젝트 버전은 별도로 확인했다.

## 실제 검증

| 검사 | PC11 | PC12 |
|---|---|---|
| `pip check`, `compileall -q src tools`, train/HOI CLI help | 통과 | 통과 |
| `test_training*.py` | 15개 / 1.782s / 통과 | 15개 / 1.947s / 통과 |
| `test_raw_training.py` | 10개 / 0.649s / 통과 | 10개 / 0.731s / 통과 |
| `test_hoi.py` | 7개 / 0.168s / 통과 | 7개 / 0.168s / 통과 |
| CUDA tensor forward/backward·유한 gradient | 통과 | 통과 |
| YOLO FP32 합성 train8/val4·1epoch | 학습/validation/best.pt/last.pt/재로딩 추론 통과 | 동일 검사 통과 |
| YOLO AMP 합성 train8/val4·1epoch | AMP 실제 활성화·학습/저장/재로딩 추론 통과 | 동일 검사 통과 |
| 합성 HOI G/VG·CUDA 추론·B4 연결 | 재로딩 일치·4frame/1event/1snapshot 통과 | 동일 검사 통과 |
| 새 SSH의 Git commit / 패키지 버전 / repo clean | 통과 | 통과 |

총 **각 32개 테스트, 두 PC에서 64회 실행**이다. 제품 전체 테스트 실행을 뜻하지 않는다. 기존 `tools/cuda_training_smoke.py`와 `tools/verify_hoi_smoke.py`를 재사용했다. HOI 도구는 합성 관계 모델을 CPU에서 학습한 뒤 CUDA에서 추론하므로 **실제 HOI CUDA 학습 검증으로 주장하지 않는다**. 검증 동안 프로젝트 GPU lock으로 같은 GPU의 중복 작업을 막았다.

YOLO 설정/폰트 cache는 `runs/yolo-config/Ultralytics`를 미리 만들고 `YOLO_CONFIG_DIR`로 지정했다. PC14에서 발생했던 CWD cache 생성을 재발시키지 않았고 최종 Git tree가 clean이었다. MinGit2.51.2 공식 archive SHA-256과 pretrained YOLO26n의 PC13 기준 SHA-256도 확인했다. 생성 합성 이미지·checkpoint와 실제 pretrained weight는 Git에 넣지 않았다.

## PC11 다운로드 재시도

PC11의 첫 pip 및 공식 대체 URL pip 다운로드는 큰 wheel을 받는 단계에서 진행되지 않았다. 각 시도의 해당 pip 자식 프로세스만 확인 후 중단하고 원래 상태·로그를 보존했다. 근본 원인은 확정하지 않았다.

공식 PyTorch 주소의 같은 wheel을 표준 `urllib`로 직접 받아 **2,532,302,369bytes**, 공식 wheel index의 SHA-256 **`3313061c1fec4c7310cf47944e84513dcd27b6173b72a349bb7ca68d0ee6e9c0`**을 대조한 뒤 로컬 파일로 설치해 통과했다. 버전/출처를 바꾸거나 TLS/hash 검증을 해제하지 않았다. [최초 상태](pc11/first-attempt-state.json), [두 번째 상태](pc11/retry-attempt-state.json), [직접 다운로드·설치 완료](pc11/bootstrap-state.json)를 구분해 보존한다. 공식 근거는 [PyTorch cu124 wheel index](https://download.pytorch.org/whl/cu124/torch/)다.

이 설치 경로 때문에 PC11의 `pip freeze`는 torch를 `torch @ file:///...whl`로 표기한다. 버전 일치는 freeze 문자열만 비교하지 않고 실제 설치 metadata의 `2.6.0+cu124`, CUDA 실행 결과, 공식 wheel hash로 확인했다. 재설치 시 해당 PC의 임시 파일 경로 대신 위 버전 고정 목록과 공식 CUDA wheel source를 사용한다.

## 증거와 재사용

- PC11: [완료 상태](pc11/verification-state.json), [환경](pc11/environment.json), [패키지 대조](pc11/package-parity.json), [FP32](pc11/fp32-smoke.json), [AMP](pc11/amp-smoke.json), [HOI](pc11/hoi-smoke.json), [freeze](pc11/environment-freeze.txt), [학습15](pc11/training-tests.txt) / [RAW10](pc11/raw-training-tests.txt) / [HOI7](pc11/hoi-tests.txt).
- PC12: [완료 상태](pc12/verification-state.json), [환경](pc12/environment.json), [패키지 대조](pc12/package-parity.json), [FP32](pc12/fp32-smoke.json), [AMP](pc12/amp-smoke.json), [HOI](pc12/hoi-smoke.json), [freeze](pc12/environment-freeze.txt), [학습15](pc12/training-tests.txt) / [RAW10](pc12/raw-training-tests.txt) / [HOI7](pc12/hoi-tests.txt).
- 원시 로그·합성 입력·checkpoint: 각 PC `C:\Class6\edge-threat-response\runs\pc11-cuda-readiness-20261106-v1` 또는 `pc12-cuda-readiness-20261106-v1`.
- 설치 기록: PC11 `C:\Class6\setup-pc11-20261106-direct-v1`(앞선 두 시도도 보존), PC12 `C:\Class6\setup-pc12-20261106-v1`.
- 원격 PowerShell 사용법은 [CUDA 인계 문서](../../../docs/training-cuda-handoff.md), 공통 설정과 기존 PC14 검증은 [PC14 기록](../pc14-cuda-readiness-2026-11-06/report.md)을 따른다. 전역 Python 대신 `.venv-ml\Scripts\python.exe`를 사용한다.

후속은 PC13 기준 manifest·weight/config hash를 보존한 실험별 데이터 cache 전송과 `--preflight-only --require-cuda` 확인이다. 서로 다른 PC에서는 독립 run을 실행할 수 있지만, 여러 PC를 묶은 DDP 학습이나 full corpus의 처리량·메모리·장시간 안정성을 이번 smoke로 검증한 것은 아니다. PC14와 두 PC의 드라이버는 다르므로 실제 모델 비교 시 장치/드라이버도 run별 기록한다. source/환경/검수 데이터 경계는 유지하며 제품 기능 코드는 변경하지 않았다. 문서 commit/push 식별자는 이 기록을 추가한 Git 이력으로 추적한다.
