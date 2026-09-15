# Legacy Dataset Visual Review Pack Report

상태: 생성·decode `PASSED`, 사람의 품질 판정 `PENDING`

## Purpose and method

group-aware development manifest에서 exact duplicate를 제외한 7,361장을 읽기 전용으로 decode하고, source·planned split·annotation format·normalized bbox area별로 deterministic sample을 생성했다. seed는 `20260915`, stratum당 목표 표본은 12장이다.

normalized bbox area의 `tiny/small/medium/large` 구간은 검수 편의를 위한 그룹이며 학습·탐지 threshold가 아니다. polygon은 원본 점을 보존한 채 contact sheet 표시용 bbox만 계산했다.

## Result

- decode: 7,361/7,361 성공, 오류 0
- 검수 표본: 128장
- contact sheet: 8장
- source: legacy-knife-detection-v1 92장, legacy-new-knife-v3 36장
- planned split: train 71장, val 27장, test 30장
- 표본의 최소 bbox area bucket: tiny 14, small 13, medium 18, large 83
- 표본 annotation: bbox object 106개, polygon object 41개

로컬 산출물은 `data/review/legacy-development-v1/`의 `review.csv`, `contact-sheets/`, `decode-errors.jsonl`, `summary.json`이다. 이미지와 원본 절대 경로가 포함되므로 Git에는 넣지 않는다.

## Preliminary observation and limitation

contact sheet 8페이지 전체를 개발 검증 차원에서 확인했다. 사람과 knife가 함께 보이는 장면도 있으나, 제품사진·단색 배경·주방 작업·손 또는 knife 클로즈업, 워터마크와 저해상도 장면이 다수 포함된다. 같은 인물·배경이 여러 표본과 planned split에서 반복되어 보여 filename/exact-hash group만으로 실제 촬영 session 또는 near-duplicate 분리가 완전하다고 볼 수 없다. 따라서 현재 dataset은 첫 legacy development baseline에는 사용할 수 있지만, 현재 val/test metric을 CCTV 일반화나 person-associated event 성능으로 해석하지 않는다.

이 관찰은 전체 표본의 사람 판정을 대신하지 않는다. 팀은 `review.csv`의 domain, label quality, person co-occurrence, small/distant, occlusion, exclude, reviewer, notes 열을 채우고 학습 승인 또는 제외 규칙을 별도로 결정해야 한다. raw dataset은 변경하지 않았다.

## Reproduction

```text
.venv-ml/Scripts/etr-dataset review-pack --manifest data/work/legacy-development-split/planned-manifest.jsonl --repo-root . --output-dir data/review/legacy-development-v1 --per-stratum 12 --seed 20260915
```
