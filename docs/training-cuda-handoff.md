# CUDA / Colab Training Handoff

상태: runner·config·preflight·notebook `IMPLEMENTED`/PC contract `VERIFIED`, CUDA full training `PLANNED`

## 목적과 gate

현재 legacy development dataset으로 첫 knife-only Baseline v1을 생성한다. 이 run은 외부 dataset 채택을 기다리지 않지만, 로컬 `data/review/legacy-development-v1/review.csv`의 표본 검수가 완료되고 학습 진행 승인이 기록된 뒤에만 실행한다.

`configs/training/cuda-baseline-v1.json`의 epochs, patience, imgsz, batch와 seed는 첫 development baseline용 기본값이다. 연구 최종 파라미터나 모델 채택 결정이 아니다.

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
