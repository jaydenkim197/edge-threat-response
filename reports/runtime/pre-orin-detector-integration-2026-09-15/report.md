# Pre-Orin Detector / Video / Snapshot Integration Report

상태: `PASSED` — 개발 PC 통합 smoke 전용, detector 성능·Orin 검증 아님

## Scope

- lazy Ultralytics backend와 model-local→canonical class remap
- COCO YOLO26n person + legacy `customknife_v1.1.pt` knife composite adapter
- 한 required component가 실패하면 detections를 버리고 `detector_error`로 기록하는 fail-closed 경계
- OpenCV image/video frame source
- canonical detection JSONL과 component latency
- 동일 detection JSONL의 B0~B3 replay
- B3 `CONFIRMED` 진입 시 실제 frame snapshot 저장
- input/config/model file hash provenance

## Environment and input

- Windows, Python 3.11.9, Ryzen 5 4600H, CUDA unavailable
- torch 2.14.0+cpu, Ultralytics 8.4.152, OpenCV 5.0.0.93
- person weight SHA-256: `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`
- legacy knife weight SHA-256: `187b95e7f403182e45fab21b6c027ee2c4f649de3e4f0991f7609886013a45d0`
- visual-review sample 한 장을 3 frame으로 반복 인코딩한 synthetic integration video
- smoke-only threshold: person 0.5, knife 0.4, expanded ratio 0.25, K=2/N=3

## Result

- 3 frames 모두 `valid`, canonical detections 9개
- detection JSONL SHA-256: `0736dd18756be49be088c65628f96a1df52f21b40490e04405270ae1c4a32639`
- B3 event: frame 1에서 1회, actual snapshot 1장, action error 0
- 같은 JSONL replay event frame: B0=0, B1=1, B2=0, B3=1
- cold model load가 포함된 첫 frame 6,210.685 ms, 3-frame median inference 106.694 ms

latency는 CPU cold start, 짧은 반복 입력과 development 설정의 결과라 FPS·배포 성능 근거가 아니다. 입력은 학습 source에서 선택해 반복한 양성 장면이므로 정확도 평가 자료도 아니다. 실제 Baseline v1 weight, 독립 영상, Orin runtime과 controlled scenario 검증은 남아 있다.

Raw video, detections, decisions, events와 snapshot은 Git에서 제외된 `runs/runtime/snapshot-positive-cpu-smoke-v2/`와 `runs/replay/detector-integration-cpu-smoke-v2/`에 있다.
