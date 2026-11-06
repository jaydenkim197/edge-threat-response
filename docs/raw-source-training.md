# 미검수 원본 기반 예비 학습

## 2026-11-06 완료·평가 복구

복구 완료: `runs/raw-followup-20261106-recovery-v1`에서 AP와predict 모두 `passed`다. 기존실패state/AP프로토콜·결과162개파일hash를보존하고미실행predict만계산했다. 별도 `runs/raw-resolution-20261106-v1`에서640-trained M1-n/s의960추론을확인했다. [비교표·권장안·재현자료](../reports/evaluation/raw-detector-selection-2026-11-06/report.md). 다음은아직권장안이며재학습·D*선정·Orin모델교체는하지않았다.

PC13의 기존 `runs/watch-raw-training.ps1`은 복구된 평가 상태를 표시하도록 갱신했다. 이전 상태 파일은 그대로 보존하며, 현재 모니터는 학습4/4·평가passed를 표시한다.

PC13 queue의 네 모델이 모두50epoch/`passed`다. 후속AP track의8개 모델×6개 개발셋 예측은 저장됐으나 집계 보고의 선택 메타데이터 `policy` 누락으로 최종 출력에서 중단됐다. 원본 모델/예측/실패state는 보존한다. 집계기는 누락된 선택 메타데이터를 명시적으로null/플래그로 남기고, truth/model/protocol/prediction hash와 fixed metric 재계산 검사는 계속 강제한다. 이후 생성하는 AP/predict 프로토콜에는 해당 track의 후보 convention을 포함한policy를 넣는다.

복구는 새 출력 폴더에서 기존AP 예측을 동일 프로토콜 bytes로 재검증·집계하고, 미실행predict track만 GPU 단독 claim으로 실행한다. 재학습이나 이전 AP 예측 덮어쓰기를 하지 않는다. 복구 완료/모델 방향은 실제 공통 결과를 확인한 후 별도 기록한다.

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

2026-11-05: 전체 원본에서 기술 검사·보호 그룹864·exact duplicate186 제외 후14,232장을 준비했다. 첫 trainer loader가 JPEG 누락을 감지해 gradient 시작 전에 중단됐다. trainer가 변경한 사본8개는 보존하고, 해시가 일치하는 원본에서 만든 새 사본은 JPEG EOF 검사 후14,224장이다. 기존 split은 유지했고 train11,378/val1,423/test1,423이다. 사람 검수를 완료했다고 표기하지 않는다.

실제 실행 ID는 **raw-real-20261105-v2**, 입력은 `data/processed/raw-real-20261105-v3/inventory.jsonl`, profile은 `data/processed/raw-real-20261105-v2-profiles/`이다. 앞의 명령은 새 실행을 만드는 예시이며 기존 경로로 재실행하지 않는다. 각 recipe는11,392 draws/epoch·712 batches·35,600 optimizer updates를 계획한다. R1의 실제 loader 수·batch16·accumulate1 및 여러 epoch 완료를 확인했다. 전체50epoch·네 모델 완료·D* 선정은 아직 아니다.

현재 공통 raw val/test는 source별 비율이 같지 않다(SOHAS val4/test0). 이는 conservative 연결 그룹을 분할하지 않은 결과다. native validation은 원본 주석 기준이며, 기존6개 개발셋의 source별 결과와 새 CCTV final 세션을 함께 확인해야 한다.

`tools/finish_raw_training.py`는 성공한 queue만 이어받아 기존 D0/COCO26n/s/RF-Large와 새4모델을 같은6개 개발셋에서 평가한다. AP와 실제 predict를 별도 track으로 남기며 YOLO는640, RF-Large는 기존704 native protocol이다. 이는 각 준비된 시스템 비교이며, 데이터 효과는 동일 YOLO 크기/640에서 해석한다. 기존 SOHAS val23의 F2 threshold는 임시 개발 값이며 D*를 자동 채택하지 않는다. 실패한 queue·다른 입력 hash·불완전 update는 후속 평가를 시작하지 않는다. 새 source 추가는 현재 queue 파일을 바꾸지 않고 별도 recipe로 준비한다.

후속 비교는 기존 **`.venv-evaluation-20261104/Scripts/python.exe`**로 실행한다. 학습/검수용 `.venv-ml`에 비교용 dependency를 설치하지 않는다. CLI는 기다리기 전에 RF-DETR/pycocotools 등 필요한 패키지를 검사하며 `--preflight-only`로 환경만 확인할 수 있다. 실행 중인 학습 checkout은 유지하고 별도 frozen worktree의 source로 후속 비교를 실행한다.

## 후속 source 확보

`tools/acquire_open_images_train.py --output-dir data/source-audit/open-images-train-20261105 --count 1000`은 공식 V7 다운로드 페이지의 train bbox(V6 공개 파일)·image metadata·class names에서 Knife 양성만 확보한다. 최대1,000장을 normalized area<=.02와 그 외에서 절반씩 deterministic ID hash로 뽑고, 가능한 수가 적으면 나머지에서 보충한다. 개별 license/attribution·원 주석·metadata checksum을 보존한다. GroupOf나 회전 좌표가 미해결인 자료는 제외하며 무라벨 이미지를 음성으로 만들지 않는다.

이 단계는 **확보만** 한다. 사람 검수·전역 중복 검사가 완료됐다고 표시하지 않고, 현재 RAW queue나 기존 Open Images validation 평가 자료에 합치지 않는다. 다음 recipe에서 기존 source/보호 group과 함께 검사한다. [공식 다운로드·형식](https://storage.googleapis.com/openimages/web/download_v7.html).
