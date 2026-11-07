# M2 병렬 실험·앙상블 진단 — 2026-11-07

## 후속 상태 — 2026-11-07

네M2 학습 모두50epoch/37,150updates를 완료했고, PC11·12·14 회수 및 동일9조건·7개개발셋·confidence/해상도2×2 비교도 완료했다. [최신 결과·검증·한계](../../evaluation/m2-variants-2026-11-07/report.md)를 우선한다. 아래는 실행 착수 당시의 기록과 관측으로 보존한다.

사용자가 PC11/12/14의 추가 GPU 활용과 증강·앙상블 검토를 요청했다. **기본 M2는 유지하고 해상도·증강 정책·seed를 분리한 세 후보를 추가해 학습을 시작했다.** 모든 source/partition은 M2와 같으며 새로운 데이터 수집이나 final test 사용은 없다. 코드·설정·관련12tests 및 각 추가 노드13tests·CUDA·실제 loader/batch 진행을 확인했다. 전체50epoch 완료·새 모델 정확도·Orin 실기기 비용은 아직 미검증이다.

## 작업 카드·범위

- 목적: 촬영 전 사용 가능한 GPU로 작은 칼 검출의 해상도/증강 민감도와 seed 변동을 확인한다. 다음 주 촬영/T1·실제 Holding/최종 B0~B4 일정을 대체하지 않는다.
- 기존 코드 재사용: M2 frozen inventory, RAW-M2-n 명시 recipe·hash-bound 승인·실제 loader/update 검증·detached launcher, 공통 detection evaluator와 COCO AP/group bootstrap. 새 의존성·DDP·서비스·자동 OS 업데이트 없음.
- 완료 기준: 같은 데이터·pretrained·나머지 설정과 고정 budget을 확인하고 각 PC에서 CUDA/실제 loader·batch 진행을 관측한다. 전체 완료 후 frozen 개발 자료에서 비교하며 D* 자동 선정이나 Orin 검증으로 승격하지 않는다.
- 위험: 960의12GB 메모리 적합성은 실제 실행으로 확인하며 OOM이면 기록을 보존하고 중단한다. 자동 batch 변경이나 budget/정확도 추정으로 통과 처리하지 않는다. 증강 정책의 세 knob는 하나의 묶음 비교다. seed2개만으로 유의성을 주장하지 않는다.
- 저장: PC13을 원본 저장소로 유지하고 다른 GPU에는 해시 확인한 실행 사본을 둔다. 약2.48GB ZIP을 `scp -3`으로 전달하므로 노트북에 큰 데이터 파일을 저장하지 않는다. 검수 사이트·판정/배정·원본 모델은 변경하지 않는다.

## 고정 실험표

| 장비 | Run | 기본 M2와 다른 항목 | 목적 |
|---|---|---|---|
| PC13 | m2-real-20261107-v1 | 기본 n640, 실행 중 | 공개 데이터 보강 기준 |
| PC11 | m2-res960-20261107-v1, 실행 중 | imgsz640→960 | 작은 칼의 학습 해상도 효과 |
| PC12 | m2-mildaug-20261107-v1, 실행 중 | mosaic1→.5, scale.9→.5, close_mosaic10→20 | 강한 축소/합성을 줄이는 정책의 효과 |
| PC14 | m2-seed2-20261107-v1, 실행 중 | seed20261004→20261107 | 기본 M2의 초기화·학습 난수 변동 |

공통: train11,884/val1,423/test1,423, 동일 초기 COCO YOLO26n SHA `9b09cc8b…`, FP32·batch=nbs16·50epochs·AdamW/lr.001·no warmup/no early stop, **11,888 draws/epoch·743 batches·37,150updates**. image/label/ordered inventory SHA는 동일하다. 해상도가 달라 실제 FLOPs/시간 예산은 같지 않다. 증강·seed는 train에서만 바꾸며 val/test를 증강·재분할하지 않는다. M1과 M2의 데이터 구성/총 update 차이는 [M2 기본 보고서](../m2-real-2026-11-07/report.md)대로 유지한다.

현재도 Mosaic·random scale·HSV·좌우반전 증강이 있다. 추가 이미지를 파일로 증식하지 않고 기존 trainer의 augmentation 인자만 바꾼다. [제공자 공식 augmentation 설명](https://docs.ultralytics.com/guides/yolo-data-augmentation/)과 설치된8.4.152 설정·실제 실행을 구분해 기록한다.

## 실행 증거·완료 후 비교

2026-11-07 **12:41 KST**, source `8316b41fc9038f3a85be61414f52f95ecb34da19`의 격리 worktree에서 세 detached worker를 시작했다. PC13의 기존 source06936e8과 `training.py`/`raw_training.py` diff가 없어 학습 코드는 동일하다. 네 장비는 독립 단일GPU 실행이며 DDP 검증이 아니다. 노트북 연결은 종료할 수 있고 학습 PC 전원은 유지해야 한다.

- 공통 archive SHA `f391b243…`(2,482,372,843 bytes) 검증·fresh extraction 후 전체 image/label/inventory hash를 대조했다. inventory SHA `120a05f7…`, checkpoint SHA `9b09cc8b…`는 PC13과 같다. [반입/검사 worker](prepare-node.py)는 고정 PC 경로의 일회성 재현 증거이며 기존 출력이 있으면 재실행하지 않는다.
- 각 PC의 RAW11+profile1+reference1=**13tests**, hash-bound 승인·CUDA preflight를 통과했다. 실제 loader는train11,888/batches743/batch16/val1,423/accumulate1이고 세 장비 모두 첫 epoch의 여러 batch 진행을 확인했다. [PC11](pc11-execution.json), [PC12](pc12-execution.json), [PC14](pc14-execution.json)은 당시 관측 snapshot이며 live 상태를 대신하지 않는다.
- PC11은 먼저960/batch16/FP32 합성16train+2val/1epoch·validation·checkpoint 생성을 통과했다. [최대 메모리 관측](pc11-memory-smoke.json)은 synthetic check다. 실제 학습에서도 batch16 진행을 확인했지만 50epoch 안정성·Orin 비용까지 검증한 것은 아니다. batch는 자동 축소하지 않으며 loader/budget 변경은 거부한다.
- 각 장치의 `runs/training/<suite-id>-raw-m2-n`에 results.csv·weights·invocation이, `runs/launch-<suite-id>`에 stdout/stderr/종료코드가 남는다. source/queue/입력 hash와 실제 update를 확인한 뒤 결과를 PC13에 수집한다. 추가3개 후보의 중앙 수집·공통 비교는 아직 대기이며 PC13 기본M2의 dependent 평가와 구분한다.
- 비교는 고정 source별 AP50/AP50-95, P/R@.25, small recall, negative FP와 paired group 결과를 사용한다. **640-trained/960-trained 각각을640·960 추론에 적용하는2×2**로 학습/추론 해상도 효과를 구분한다. mild/seed는640이 주 비교다. 서로 다른 native validation 해상도의 수치만 보고 우열을 정하지 않는다. 실제 CCTV final 세션은 촬영 뒤 독립 보존한다.

## 기존 M1-n+s 앙상블: 실제 결과

이미 저장된 predict 후보를 같은 source/frame identity로 정렬한 뒤 **후보 pooling + IoU.7 NMS, 겹친 bbox는 최고 confidence 유지**로 합쳤다. WBF·score calibration·모델 재학습은 아니다. 고정 confidence.25/평가IoU.5, AP confidence floor.001, 각 image 최대300boxes다. 멤버의 summary/protocol/checkpoint/prediction/truth hash를 검증하고 기존 공통6개 개발셋과 확대US83을 재계산했다. 기존US21/확대83을 독립 자료로 합산하지 않는다.

| 자료 | M1-n TP/FP | n+s TP/FP | 판단 |
|---|---:|---:|---|
| DaSCI 고유 | 66/23 | 74/42 | Recall68.0→76.3%, FP 증가 |
| Open Images | 8/18 | 12/24 | Recall20.5→30.8%, FP 증가 |
| SOHAS test | 16/1 | 16/2 | Recall80% 동일, FP 증가 |
| US Mock 확대83/31GT | 0/2 | 0/2 | 목표 CCTV 미검출 해결 못함 |

[전체21행 CSV](ensemble-comparison.csv), [원시 입력 hash·실행 state](ensemble-evidence.json), [실행 worker](ensemble-worker.py), [검증한 source bytes](source-files.json). 실행은 PC13의 기존 평가 환경에서 **CPU 기반 캐시 재계산**이며 GPU 추론/Orin 지연/메모리를 측정하지 않았다. 실행 source는 검증용 af3e5e8 worktree+본 작업 patch이고 같은 함수 bytes를 본 Git commit으로 고정한다. 새 입력·예측은 `runs/m1-ensemble-20261107-v1`에 보관한다.

앙상블은 일부 recall/FP trade-off를 보여 주지만 현재 CCTV 성능 개선 근거가 없다. 기본 배포 후보로 자동 채택하지 않고 새 해상도/증강 모델 확보 뒤 필요할 때 같은 기준으로 추가 비교한다. 학습 증강과 추론 시 여러 번 실행하는 TTA는 다른 실험이며, 이번에 TTA 성능·지원 여부를 검증했다고 주장하지 않는다.

## 후속 평가 오류 선제 수정·검증

기존 M2의 선택적 reference에서 공통 집계기가 요구하는 `custom-n-640`이 빠진 것을 발견했다. 기존 학습은 그대로 두고 `waiting_for_training`인 평가 python process tree만 중지했다. v1 로그·상태·출력을 보존하고 source06936e8의 동일 평가기에서 **D0+M1-n+COCO26n+M2**를 실행하도록 새v2 worker를 시작했다. reference/확대suite preflight·새waiting 상태를 확인했다. 이전 execution snapshot의 v1 상태는 당시 관측으로 보존한다.

`reference_cases`에 기준모델 누락을 초기에 거부하는 검증과 회귀 테스트를 추가했다. 수정된 worker/로그는 `runs/m2-preparation-20261107/followup-v2`, 결과는 `runs/m2-followup-20261107-v2`다. 테스트는 공통 비교10+reference1+3개 설정축 검증1=**12개 통과**, compileall 통과다. 실제 앙상블 완료·원시 hash 대조도 통과했다. 새3개 학습은 실행 중이며 전체 완료·비교·Orin 배포는 아직 아니다.

설정: [PC11](../../../configs/training/m2-res960.pc11.json), [PC12](../../../configs/training/m2-mildaug.pc12.json), [PC14](../../../configs/training/m2-seed2.pc14.json). 각 노드가 성공한 뒤 결과/weight/manifest hash를 PC13에서 수집·같은 개발셋 비교한다. 최종 촬영 세션은 열지 않는다. 의도한 코드·설정·관련 문서만 commit/push하고 다른 채팅의 미커밋 문서는 보존한다.
