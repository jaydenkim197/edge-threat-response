# YOLO26n CPU Training Smoke Report

상태: `PASSED` — 학습 배관 검증 전용, detector 성능 증거 아님

## Purpose

knife-only exporter의 출력이 Ultralytics에서 로드되고 YOLO26n의 forward/backward, loss, validation, checkpoint 저장과 재로딩까지 연결되는지 확인했다.

## Environment

- Windows build 26200, Python 3.11.9
- AMD Ryzen 5 4600H, CUDA unavailable
- torch 2.14.0+cpu, torchvision 0.29.0
- Ultralytics 8.4.152, OpenCV 5.0.0.93
- 격리 환경: `.venv-ml` (Git 제외)

## Dataset and configuration

- group-aware development split에서 train 32장, val 8장 선택
- 40장 image decode 성공, 49 knife objects, background 0
- model-local class `0=knife`; runtime canonical mapping `0→1`
- YOLO26n pretrained, `imgsz=320`, 1 epoch, batch 4, workers 0, CPU
- source `yolo26n.pt` SHA-256: `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`
- seed `20260915`, deterministic true

이 수치는 smoke용 development default이며 최종 연구 설정이 아니다.

## Result

- training duration recorded by wrapper: 18.282 seconds
- dataset scan, forward/backward, loss, validation: passed
- `best.pt` and `last.pt`: created, about 5.3 MB each
- `best.pt` reload and one validation-image inference: passed
- reload image prediction box count: 0
- reported precision/recall/mAP: 0

1 epoch와 극소 표본의 0 metric 및 단일 이미지 0 detection은 성능 결론이 아니다. 이 실행은 코드·데이터·dependency·checkpoint 경로만 검증한다.

## Reproduction

```text
python -m venv .venv-ml
.venv-ml/Scripts/python -m pip install -r requirements/ml-smoke.txt
.venv-ml/Scripts/python -m pip install -e .
.venv-ml/Scripts/etr-train --config configs/training/cpu-smoke.json --data data/processed/knife-legacy-cpu-smoke-v1/data.yaml --output-dir runs/training
```

Raw run, generated dataset and weights are local ignored artifacts. Their storage paths and hashes are in the local invocation manifest; weights are not committed.
