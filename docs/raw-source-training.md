# 미검수 원본 기반 예비 학습

2026-11-05 사용자 결정: 후보 자료의 사람 검수 완료를 기다리지 않고 원본 annotation으로 예비 학습한다. 품질 검수 합격이나 최종 연구 평가 승인을 뜻하지 않는다. 기존 검수 사이트/DB/판정/배정은 이 경로에서 읽거나 수정하지 않는다.

## 작업 카드와 범위

- 목적: 작은 DEV-SOHAS 모델과 비교할 전체 실사 source 기준 및 혼합 후보를 만든다.
- 재사용: source별 YOLO/VOC parser, 이미지 signature, SHA/dHash/family proxy, group split, matched-budget preparation, 기존 training runner.
- 변경: 별도의 `RAW-*` recipe/해시 결합 승인과 fail-stop 순차 GPU queue를 추가한다. 기존 R1/H1/DEV-SOHAS 승인 조건은 유지한다.
- 완료 기준: 무결성·보호 그룹 제외·공통 val/test·동일 update 예산·중복 실행 차단을 확인하고, 실제 실행 상태와 결과를 별도 기록한다.
- 위험: raw annotation 누락, source-coordinate 가정, proxy grouping 오류 및 domain mismatch가 남는다. 이를 사람이 확인한 사실로 승격하지 않는다.

## 최초 조합

SOHAS pinned VOC 전체, Dangerous Items VOC ZIP의 전체 4,000 XML 및 대응 이미지, Catargiu v11 이미지와 corrected label의 knife-positive 대응분을 준비한다. 기존에 풀린 Dangerous Items 표본 폴더만 전체 source로 취급하지 않는다. Catargiu의 미대응/무라벨 이미지를 자동 음성으로 만들지 않는다. source 파일은 수정하지 않고 학습용 사본을 만든다.

11월4일 공개 개발 비교 자료의 이미지와 연결된 conservative proxy group은 새 학습에서 제외한다. 원본의 train/test 표시를 보존하면서 새 group-aware 80/10/10 개발 분할을 만든다. 이 test도 논문 최종 unseen CCTV test를 대신하지 않는다. 이후 source가 추가되면 새 manifest/recipe 버전을 만든다.

순서: **RAW-R1-n → RAW-H1-n → RAW-M1-n → RAW-M1-s**. R1은 SOHAS 양성+원본 주석상 음성, H1은 같은 양성만, M1은 준비된 실사 혼합이다. 네 조건의 val/test는 동일하다. 가장 큰 train pool을 batch 배수로 올림한 draw 수를 공통 예산으로 사용하며 작은 pool은 반복 추출한다. 같은 epoch 수·batch/nbs·no-warmup/no-early-stop·FP32 조건에서 optimizer update 수를 맞춘다. 데이터 recipe의 비교이며 독립 source 하나의 순수 인과효과라고 주장하지 않는다.

640, YOLO26n/s의 각 COCO pretrained checkpoint, AdamW/lr=.001, scale=.9, 50 epochs, batch=nbs=16, seed20261004를 시작점으로 사용한다. 960은 선택한 후보의 후속 비교이며, synthetic은 별도 S1이다. 사람 detector는 공통 고정한다.

## 실행

PC13 저장소에서 `PYTHONPATH=src`, `.venv-ml` 환경을 사용한다. 각 출력은 새 경로여야 한다.

```powershell
python tools/prepare_raw_pc13.py --root . --output-dir data/processed/raw-real-20261105-v1
python -m edge_threat_response.raw_training prepare --plan configs/training/raw-real.pc13.json --inventory data/processed/raw-real-20261105-v1/inventory.jsonl --checkpoint-n yolo26n.pt --checkpoint-s models/pretrained/yolo26s.pt --output-dir data/processed/raw-real-20261105-v1-profiles --authorization-reference user-directive-20261105
powershell -NoProfile -ExecutionPolicy RemoteSigned -File tools/start_raw_training.ps1 -Queue data/processed/raw-real-20261105-v1-profiles/queue.json
```

실제 checkpoint 경로는 확보된 고정 파일을 지정한다. launcher는 숨김 worker를 만들고 SSH 종료 후에도 실행한다. `runs/launch-<suite-id>/`의 stdout/stderr/exit code와 `runs/training/<suite-id>-queue-state.json`으로 확인한다. 실패하면 다음 학습을 시작하지 않는다. 기존 run/queue 상태를 덮어쓰지 않으며 stale lock도 자동 삭제하지 않는다.

각 invocation은 입력 config/data/list/manifest/pretrained 해시와 환경·commit·weight/metric을 기록한다. `human_review_complete=false`, `negative_absence_verified=false`, `final_evaluation_allowed=false`를 유지한다. 이미지/라벨 bytes가 바뀌면 실행을 거부한다.

RAW 실행은 실제 train/validation loader 수·batch·accumulate를 확인하고, 학습 중 자동 batch 변경·누락을 거부한다. 고정 FP32/accumulate=1에서 완료 batch마다 update를 세어 계획과 대조하고 종료 후 입력 해시를 다시 확인한다.

## 상태

미검수 예비 승인·동일 예산·변조 거부·queue 실패 중단·VOC 의미 검사와 기존 training 회귀를 PC에서 자동 검증했다(신규4+기존14 tests). 실제 전체 source 준비·CUDA 학습·최종 detector 선정은 이 기록 작성 시점에는 아직 검증 전이다. 실제 결과는 후속 실행 보고서에 남긴다.
