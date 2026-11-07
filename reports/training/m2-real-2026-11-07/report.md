# M2 실사 보강 — 2026-11-07

## 후속 상태 — 2026-11-07

네M2 학습 모두50epoch/37,150updates를 완료했고, PC11·12·14 회수 및 동일9조건·7개개발셋·confidence/해상도2×2 비교도 완료했다. [최신 결과·검증·한계](../../evaluation/m2-variants-2026-11-07/report.md)를 우선한다. 아래는 실행 착수 당시의 기록과 관측으로 보존한다.

**M1 train의 문제·불확실 88장을 제외하고 별도 Open Images train 594장을 추가해 M2 YOLO26n/640 학습을 시작했다.** train 11,884 / val 1,423 / test 1,423이며, 기존 val/test의 이미지·라벨 bytes와 identity 순서를 보존했다. 입력·CUDA·실제 loader 검증은 `VERIFIED`, 실행 경로는 `IMPLEMENTED`다. 전체 학습 완료·새 성능·공통 비교는 아직 대기다.

## 목적·범위·사용자 결정

- 목적: 촬영 대기 기간에 YOLO26n/640의 공개 데이터 보강 후보 한 개를 만든다. 별도 Q1 정제 full run은 생략하고 M2에 반영한다. 자체 촬영은 사용자가 다음 주 진행 예정이라고 확인했다. T1·실제 Holding 학습은 촬영 자료가 있어야 진행한다.
- 제공자가 표시한 `/m/04ctx` Knife bbox만 가져오며 이미지별 AI 판정이나 새로운 사람 검수를 전체 선행 조건으로 추가하지 않는다. 기존의 RAW 예비 사용 허용을 사용하고 사람 검수·원본의 knife 누락 여부·실제 CCTV 비율을 확인한 것으로 표시하지 않는다.
- 나머지 Roboflow 전체 파일/API 접근 정보는 없다고 사용자가 답했다. 기존에 확보한 자료로 계속하며 공개 후보 전체 확보를 일정의 필수 gate로 두지 않는다. ACF 회신/원본은 여전히 미확보다.
- 검수 사이트 앱·DB·배정·판정, 기존 학습 source/weights, 기존 split을 수정하지 않는다. 큰 데이터와 런타임 증거는 PC13에만 둔다.

## 데이터 구성과 보호

| Train source | M1 | 제외 | M2 |
|---|---:|---:|---:|
| SOHAS | 4,982 | 33 | 4,949 |
| Dangerous VOC | 1,296 | 2 | 1,294 |
| Catargiu | 5,100 | 53 | 5,047 |
| Open Images 별도 train | 0 | 0 | 594 |
| 합계 | 11,378 | 88 | **11,884** |

88장은 고정된 11/06 검수 증거에서 `raw_split=train`, 표시 라벨 일치, `verdict!=ok`인 고유 이미지다(문제49·불확실39). 불확실을 확인된 오라벨로 바꾸거나 원본에서 삭제하지 않는다. 별도 39장 추가 후보는 이번 M2에 넣지 않았다.

Open Images 594장/820 boxes의 공식 원 주석과 기존 YOLO label 좌표를 대조했다. 원본 metadata·attribution·acquisition manifest를 PC13에 보존한다. 이미지에 표시된 CC BY 2.0과 annotation CC BY 4.0을 기록하되 개별 권리를 독립 검증했다고 주장하지 않는다. 추가된 것은 knife-positive train 자료이며 새 hard negative 또는 실제 CCTV 전용 자료라는 의미가 아니다.

기존 source signature 15,545개(기존 보호263개 포함), 새 자료594개, US Mock 후보 팩100개 전체를 연결 그래프로 검사했다. SHA-256, dHash≤4, aspect-ratio 변화 proxy, filename family와 전이적 연결을 보수적으로 사용한다. 새 자료에 보호/기존 source 그룹 교차로 인한 제외는 없었고, 기존 train의 추가 보호 그룹 제외도 없었다. 이는 확인된 촬영 세션이나 모든 변형 중복을 보장하지 않는다. 새 연결이 frozen val/test를 잇는 경우 재분할하지 않고 중단한다.

val/test 각1,423장의 이미지 ID·SHA·label SHA·knife 수·순서를 보존했다. 파일 경로는 격리된 새 사본 경로이므로 원래 path list bytes가 동일하다는 뜻은 아니다. [고정 입력·출력 해시와 수량](preparation-summary.json).

## 학습·비교 규칙

- `RAW-M2-n`만 명시적으로 선택한다. 기본 RAW 4종 prepare 동작과 기존 reviewed 승인 gate는 유지한다.
- M1과 같은 초기 COCO YOLO26n checkpoint, 640, 50 epochs, batch=nbs16, AdamW/lr.001, scale.9, seed20261004, FP32, warmup0, early stop 없음. M1 checkpoint에서 이어서 학습하지 않는다.
- 새 train을 batch 배수로 올려 **11,888 draws/epoch · 743 batches · 37,150 updates**를 계획한다. M1은 11,392 draws/epoch · 712 batches · 35,600 updates였다. epoch/나머지 hyperparameter는 같고 update는 약4.35% 늘어난다. 이를 같은 연산 예산이나 순수한 정제/증량 인과 ablation으로 보고하지 않는다. 일정 우선의 전체 recipe 비교다.
- 성공한 queue와 실제 update 수를 확인한 후 M1-n·COCO26n·M2-n을 기존 공통 6개 개발셋에서 AP/predict 두 track으로 비교한다. 고정된 확대 US Mock83장/31GT도 추가 진단한다. 서로 겹치는 기존 US21/확대83을 독립 표본으로 합산하지 않는다.
- 이미 열어본 개발셋의 검출 지표이며 독립 최종 CCTV/사건 성능, Orin 속도, D* 확정을 뜻하지 않는다. 실제 CCTV 적응 T1·Holding/B4·최종 B0~B4는 별도다.

## 구현·검증

`search-first`에 따라 기존 label parser, image signature, similarity screen, proxy components, hash-bound RAW approval/runner/queue와 평가기를 재사용했다. 새 모듈은 frozen holdout을 재분할하지 않는 follow-up materialization만 담당한다. 운영 checkout 대신 PC13의 격리 worktree에서 실행한다. 새 의존성이나 드라이버 변경은 없다.

- PC13 기존 `.venv-ml`: 전체 **201 tests 실행, 199 통과·2 optional comparison skip**. skip된 비교 검증은 기존 `.venv-evaluation-20261104`에서 관련8개 전부 통과했고 새 reference 선택 테스트1개도 통과했다.
- 신규 회귀 테스트: train-only 정제, holdout bytes/순서 보존, 추가 평가/학습 그룹 연결 제외, 확대 보호의 기존 train 제외, val/test bridge 중단, 원본 변경/덮어쓰기 거부, provider class/좌표 변조 거부, M2 단일 recipe/기존 승인 검증, reference checkpoint 해시 고정.
- 실제 데이터 전체 hash·strict image decode/JPEG EOF·bbox 검사/사본 생성, source/evidence 전후 hash 일치 및 frozen holdout identity 검증 통과.
- 로컬 Python3.11 `compileall`, PowerShell launcher parser 통과. PC13 학습 환경은 기존 Python3.12.4/torch2.6.0+cu124/Ultralytics8.4.152/RTX3060 12GB다. 전체 학습 완료·새 성능·Orin 검증은 아직 아니다.

## 실제 실행 상태

**후속 갱신:** 다음 작업에서 공통 집계기의 필수 기준 D0 누락을 발견해 학습은 유지하고 waiting 평가만v2로 교체했다. 현재 결과 경로는 `runs/m2-followup-20261107-v2`, worker 상태는 `runs/m2-preparation-20261107/followup-v2/followup-worker-state.json`이다. 원v1 로그/출력과 아래 첫 snapshot은 보존한다. [수정 근거·회귀 검증·추가GPU 실행](../m2-parallel-2026-11-07/report.md).

- 2026-11-07 12:08 KST에 PC13 detached worker를 시작했다. source commit은 `06936e8721e10278bdcc75e92b4870891f39fed4`, queue SHA-256은 `80c14125237bb712de8a5be7169bfd17b9fad7455a3cd0fea2594e5f56f5ab7c`다. 운영 source checkout은 바꾸지 않았다.
- CUDA preflight `passed`, M1 초기 pretrained SHA `9b09cc8b…`와 전체 학습 인자 일치를 확인했다. 실제 train loader는11,888draws/743batches/batch16/accumulate1, validation은1,423장이다. stdout에서 첫 epoch의 실제 batch 진행과 GPU 연산을 확인했다. 추가로 첫1/50epoch의 train·validation, results.csv 1행 저장과 실제743updates를 확인했다. 전체50epoch 완료를 뜻하지 않는다.
- [관측 snapshot](execution-snapshot.json)은 관측 시점의 상태이며 현재 live 상태를 대신하지 않는다. invocation update counter는 epoch 경계에서 flush하므로 첫 epoch 도중에는0으로 보일 수 있다. 완료 여부는 queue/invocation의 `passed`와 실제37,150updates·완성 weight hash로 확인한다.
- 기존 평가 환경·reference checkpoint·확대CCTV suite hash preflight를 통과한 [후속 worker](followup-worker.py)를 별도 detached 실행했다. 현재 `waiting_for_training`이며, 성공한 queue만 공통6셋 AP/predict → 같은83장 확대CCTV 진단으로 이어간다. 실패 시 state/log를 보존하고 자동 재학습·기존 결과 덮어쓰기는 하지 않는다. 원격 SSH나 노트북 종료와 분리해 실행한다. PC13 전원은 켜져 있어야 한다.
- 첫 launcher 호출은 PC13의 기본 PowerShell execution policy로 script 실행 전에 거부됐다. 기존 실행 절차의 프로세스 한정 `RemoteSigned`로 다시 호출해 성공했다. 전역 실행 정책이나 서비스 설정을 바꾸지 않았다.

## 원시 증거·다음 단계

PC13 기준:

- 데이터: `C:\Class6\edge-threat-response\data\processed\m2-real-20261107-v1`
- 원 Open Images 및 attribution: `data/source-audit/open-images-train-20261105`
- 고정 검수 snapshot: `data/work/reviewed-next-training-20261106/review-evidence-snapshot.jsonl`
- 준비·전체 테스트 log: `runs/m2-preparation-20261107`
- 실행 profile/승인/queue: `data/processed/m2-real-20261107-v1-profiles`
- 학습: `runs/training/m2-real-20261107-v1-raw-m2-n`, queue/invocation JSON은 같은 상위 폴더
- detached launcher: `runs/launch-m2-real-20261107-v1`
- 현재 후속 worker 상태/log: `runs/m2-preparation-20261107/followup-v2/followup-worker-state.json`, 결과: `runs/m2-followup-20261107-v2` 및 `cctv-expanded`. v1은 보존된 과거 대기 작업이다.
- 설정: [m2-real.pc13.json](../../../configs/training/m2-real.pc13.json), 사용법: [RAW 실행 계약](../../../docs/raw-source-training.md)

의도한 코드·설정·보고서·관련 문서만 commit/push한다. 기존 다른 채팅의 Catargiu/검수 사이트 문서 미커밋 변경은 보존한다. 실행 source commit과 queue/weight/결과 hash는 실제 실행 evidence에 기록한다. 다음은 M2 실행·공통 비교 후 개선 여부 판단, 다음 주 촬영·bbox/Holding/event GT 분리, T1/HOI, Orin/GPIO와 독립 최종 평가다.
