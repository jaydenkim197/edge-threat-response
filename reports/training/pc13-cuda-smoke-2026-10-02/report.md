# RTX 3060 원격 학습 환경 검증 — 2026-10-02

상태: CUDA/AMP synthetic plumbing `VERIFIED`; 실제 데이터 학습·모델 성능·Orin `NOT VERIFIED`.

## 환경과 변경

- 사용자 지정 SSH PC의 빈 `C:\Class6`를 확인한 뒤 `C:\Class6\edge-threat-response`에 원격 `main`을 clone했다. 기존 파일 삭제·driver 변경·전역 Anaconda package 변경 없음.
- Windows, i9-13900, RTX 3060 12,288 MiB, RAM 34,088,226,816 bytes, driver 560.94, Python 3.12.4.
- `.venv-ml`에 torch 2.6.0+cu124 / torchvision 0.21.0+cu124, Ultralytics 8.4.152, NumPy 1.26.4, OpenCV 4.11.0.86 및 editable project 설치. venv 파일 합계 5,279,471,680 bytes.
- core·runner는 재사용하고 생성 이미지 CUDA smoke helper와 PC별 requirements를 추가했다. 실제 dataset 다운로드·반입·병합·full training은 수행하지 않았다.

## 실행·관찰 결과

| 확인 | 결과 |
|---|---|
| `python -m pip check` | No broken requirements found |
| 원격 `python -m unittest discover -s tests -q` | 56 tests 통과, 0.341 s |
| 로컬 기존 테스트 / helper compile | 56 tests 통과, 2.341 s / py_compile 통과 |
| CUDA tensor forward/backward | 유한 gradient 확인 |
| YOLO26n pretrained load·fine-tune | 8 train / 4 val 생성 rectangle, 320 px, batch 2, workers 0, 1 epoch 성공 |
| FP32 smoke | runner duration 8.765 s, validation·checkpoint·재로딩 추론 성공 |
| AMP smoke | AMP 실제 활성화 확인, runner duration 5.063 s, validation·checkpoint·재로딩 추론 성공 |

초기 FP32 run은 cuBLAS deterministic 경고가 발생했다. helper에서 torch import 전 `CUBLAS_WORKSPACE_CONFIG=:4096:8`를 설정한 후 별도 AMP run에서 해당 경고가 나타나지 않았다. 이는 bitwise 반복 재현성을 입증하는 실험은 아니다.

## 증거와 한계

- 원격 raw evidence: `runs/pc13-cuda-smoke-20261002/` 및 `runs/pc13-cuda-amp-smoke-20261002/`. 후자에는 `preflight.json`, `smoke-config.json`, `smoke-summary.json`, dataset manifest, `runs/training-invocation.json`, `runs/training/results.csv`, `runs/training/weights/{best,last}.pt`, `environment-freeze.txt`가 있다.
- smoke 실행 시 clone 기준 commit `2ed344c`; 변경 helper는 SCP로 반입했고 SHA-256 `569fd2fb7018897e922ea969f52aa33d6315cfdc81979acf9d98432c5f88655c`를 summary에 기록했다. 최종 commit은 이 report와 helper를 포함하는 commit이다.
- AMP best.pt SHA-256 `f14362eeaf713d685f93ec8bef9d76a8fbb32a2f09ab3c2ad4911b5dfa7b1d86`.
- 생성 rectangle을 knife class ID 0으로 학습했으므로 metric 0은 예상 가능한 plumbing 결과이며 실제 knife 성능 자료가 아니다. smoke weight를 후보 detector로 사용하지 않는다.
- 큰 dataset·640 px·실제 batch·장시간 온도·여러 GPU PC·SSH 단절 후 작업 지속·Drive 전송은 미검증이다. 학습용 runtime 확인과 Orin 배포 runtime 확인을 구분한다.

다음 gate: SOHAS source/label/sample audit → 공통 tuning/test·recipe 승인 → 실제 CUDA training preflight와 run.
