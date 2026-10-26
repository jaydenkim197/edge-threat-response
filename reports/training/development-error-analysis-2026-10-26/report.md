# 개발 모델 오류 분석과 후속 학습 — 2026-10-26

**학습 데이터에는 잘 맞지만 작은 칼이 많은 검증 자료로 일반화하지 못하는 패턴이 주된 문제다.** 같은 split에서 optimizer/LR와 크기 증강을 바꾼 개발 학습2회를 실제 완료했고, mAP50은 26.6%에서55.2%로 올랐다. 개선 모델도 val14개 칼 중 고정 기준에서6개만 찾으므로 최종 detector로 채택하지 않는다. 추가 source를 섞기보다 작은 실사 knife와 혼동 물체를 보강하는 방향으로 간다.

상태: PC13 실제 GPU 실행·train/val 진단 `MEASURED`; 개발용 후보 선택 완료. source 전체/정식 R1/H1/최종 test/Orin/사건 경보 성능은 미검증. 숫자와 input·checkpoint hash는 [aggregate.json](aggregate.json)에 보존했다. 원본 이미지·검수 판정·weight는 공개하지 않는다.

## 1. 무엇이 낮았는가

기존 SGD best를 **conf=.25 / IoU=.5**로 다시 평가했다. 이는 Ultralytics의 best-F1 요약 Precision/Recall과 다른 고정 operating point다.

| 항목 | Train diagnostic | Validation tuning |
|---|---:|---:|
| 이미지 / knife 객체 | 137 / 127 | 23 / 14 |
| TP / FP / FN | 117 / 14 / 10 | 1 / 0 / 13 |
| Recall | 92.1% | 7.1% |
| bbox 면적/image 면적 중앙값 | 6.867% | 0.484% |
| 면적 비율≤.02인 knife | 26/127 | 11/14 |
| 면적 비율<.005인 knife | 3/127 | 7/14 |
| 640px letterbox 환산 짧은 변 중앙값 | 96.97px | 29px |

후단 temporal/spatial 규칙으로 detector의 미검출 칼을 복구할 수는 없다. baseline val에서 confidence를 .05까지 낮춰도 TP4/FP7/FN10이다. 임계값 완화만으로 recall 문제를 해결하면 오검출이 늘어난다. 그렇다고 칼이 전부 해상도 때문에 보이지 않는 것도 아니다. 환산 짧은 변≤8px인 GT는 두 partition 모두0개다.

val의 per-GT 진단은 detected1 / low-confidence3 / localization1 / missed9다. 각 GT와 예측의 최대 IoU를 보는 설명용 분류이며, 지표 표의 일대일 matching을 대체하지 않는다. 예측 floor는 .05다. 네 contact sheet의 실제 이미지/GT/예측을 확인했고 작은 손-held knife 누락, 일부 위치 오차와 의류·배경 FP를 관찰했다. 원래 사람 판정을 수정하지 않았다.

해석은 다음 범위로 제한한다.

- train fit과 val 성능 차이 및 객체 크기 분포 차이가 뚜렷하다. 97개 positive train image는 target-domain 다양성을 충분히 대표하지 않는다.
- SGD는 epoch34 이후 train loss가 감소해도 val mAP가 하락했다. 과적합/불안정과 양립하는 관측이지만, 데이터 수·크기·장면과 optimizer 각각의 인과 기여도를 따로 증명하지 않는다.
- 기존 좌표의 원래 convention은 여전히 미확정이다. 개발용 raw-overlay pixel-edge 계약으로 XML·화면·변환 label을 대조했다. 변환 오류가 주원인이라는 증거는 이번에 발견하지 못했으나 원 convention을 검증한 것은 아니다.
- COCO pretrained knife class도 같은 val에서 conf≥.05/IoU=.5 TP0이었다. pretrained만 연결하면 해결되는 상황은 아니었다. 이 비교는 class43을 knife로 선택한 sanity diagnostic이다.

## 2. 동일 조건 후속 학습2회

가설: 기존 데이터와 split을 유지해도 최적화 regime 및 작은 크기 증강이 낮은 검증 성능을 일부 개선할 수 있다. optimizer 이름만의 효과와 LR 효과는 분리하지 않는다.

공통 조건: PC13 RTX3060 12GB/driver560.94, Python3.12.4, torch2.6.0+cu124, torchvision0.21.0+cu124, Ultralytics8.4.152, YOLO26n COCO pretrained 동일 SHA-256, 640px/batch16/nbs16/50epochs/FP32/workers0, seed20261004. warmup0, patience0, mosaic1/close_mosaic10, 나머지 augmentation 동일. 각450 planned optimizer updates다. test23개는 사용하지 않았다.

optimizer/LR/scale 설정의 의미는 [Ultralytics 공식 학습 설정](https://docs.ultralytics.com/modes/train/)을 참고했다. 실제 사용 버전은 위와 같이 고정했고 문서 권장이 이번 개선의 인과 증거를 대신하지 않는다.

| 개발 run | 변경 | best epoch(CSV) | mAP50 | mAP50–95 | 학습 시간 |
|---|---|---:|---:|---:|---:|
| `sohas-reviewed-development-20261026-v1` | SGD/lr.01/scale.5 | 34 | .265761 | .102469 | 203.265s |
| `sohas-reviewed-development-20261026-adamw-v1` | AdamW/lr.001/scale.5 | 35 | .468685 | .184558 | 212.641s |
| `sohas-reviewed-development-20261026-smallscale-v1` | AdamW/lr.001/**scale.9** | 49 | **.552030** | **.207160** | 218.031s |

표의 mAP는 run 종료 후 best.pt 재검증 값이다. CSV의 최고 epoch 행과 소폭 다르므로 혼용하지 않는다. scale=.9는 random affine scale 범위를 넓힌 것이며 새 실사 영상이 생긴 것은 아니다. 작은 방향과 큰 방향 변환을 모두 포함한다. best49는 수렴이 끝났다는 증거도 아니다.

동일 **conf=.25 / IoU=.5**에서 비교하면:

| 개발 run | val TP/FP/FN | Precision | Recall | small recall | 음성 이미지 FP |
|---|---:|---:|---:|---:|---:|
| SGD | 1 / 0 / 13 | 1.000 | .0714 | 1/11 | 0/10 |
| AdamW | 5 / 5 / 9 | .500 | .3571 | 3/11 | 1/10 |
| AdamW + scale.9 | **6 / 3 / 8** | **.667** | **.4286** | **4/11** | **0/10** |

scale.9의 conf=.05에서는 TP8/FP31/FN6, 음성 이미지 FP7/10이다. confidence를 무작정 낮추지 않는다. 현재 .25는 비교용 development default이며 최종 경보 threshold가 아니다. train은 scale.9에서 TP126/127이므로 generalization gap도 남는다.

**개발용 후보는 scale.9 run의 best.pt로 둔다.** 모델 hash `d8eff85efff890041d67f9aea80d3d0d7a9530312eb7c2da2baace5e3840c043`. 세 run의 manifest·pretrained·train/val/test list hash 동일과 50개 epoch/exit0/invocation passed를 재확인했다. 기준 D* 또는 정식 연구 모델로 확정하지 않았다.

## 3. 어떤 데이터를 얼마나 보강할 것인가

검수 snapshot을 다시 평가하고 raw 이미지 bytes·dimension·bbox 범위를 점검했다. protected val/test의 hash/group만 연결 검사에 쓰며 test 이미지·label을 열거나 점수화하지 않았다.

| 후보 | 관측 | 현재 처리 / 다음 범위 |
|---|---|---|
| **SOHAS 작은 실사 + 혼동 물체** | 기존 검수765장 및 보호 proxy group 제외 후 small positive359장·negative candidate3383장 | **다음 실사 보강의 우선 후보. small100 + 음성50 검수 pack 준비 완료.** 승인 통과분만 train에 추가하고 동일 val/test 유지 |
| DaSCI 정상92장 | knife97개 중 small88; target_cctv 판정1장 | 후보 filename family를 빼도18장이 보호된 SOHAS proxy component와 연결. family까지 합치면92장 모두 연결. 무조건 병합하지 않고 실제 scene/session 연결을 먼저 해소 |
| Simuletic 정상71장 | positive60/negative11, knife60개 모두 small; target_cctv61장; 보호 proxy 연결0 | 좌표·권리·absence·실제 source group 확인 후 **별도 S1 development ablation 최대71장** 제안. 실사 corpus의 대체재로 채택하지 않음 |
| Dangerous Items / Open Images | class mapping 미확정 / 현재 validation 출처·개별 권리 조건 | 이번 학습에는0장. 승인 조건을 해결하기 전 보강하지 않음 |
| US Mock Attack / ACF | 외부 CCTV 평가 역할 / 원본 접근 대기 | 학습0장 유지. target holdout을 학습으로 소비하지 않음 |
| Legacy | 팀원 L0 트랙 | 이번 신규 모델에0장 유지 |

DaSCI92장 전부가 실제 중복이라는 뜻은 아니다. 보수적인 파일명 계열과 dHash/동일 hash 연결이며 heuristic이다. 반대로 연결0도 실제 recording session 독립성의 증거가 아니다. 현재 검수 태그는 카메라 설치·관찰 거리 측정을 대신하지 않는다.

### 준비한150장 검수 pack

PC13의 `data/review/sohas-gap-20261026-v1/`에 있다. 이미지·raw bbox·contact sheet·lineage·새 선택 manifest를 복사했고 **운영 사이트/DB에는 아직 추가하지 않았다.** 추가 pack importer가 기존 판정·배정·sample ID를 보존해 append해야 한다.

- `small-positive/`: 100장. normalized knife area≤.02인 이미지 pool359개에서 proxy group/원 class 조합을 나눠 deterministic sampling했다. 작은 bbox는 실제 원거리라는 뜻이 아니므로 close-up/제품사진도 human scene review로 구분해야 한다.
- `negative-mined/`: 50장. knife annotation이 없는 후보3383장 중512장을 group/class-balanced로 probe하고, 각 bucket에서 현재 모델 confidence가 높은 이미지를 우선했다. 선택50개 모두 knife 예측≥.05가 있었다. 실제 knife 부재는 아직 사람이 확인하지 않았으므로 **오검출 의심 후보**이지 확정 음성/평가 결과가 아니다.
- 기존 검수 이미지 선택0 / 보호 proxy group 선택0 / exact hash 중복0. Pin된 source blob·XML·decode/dimension·150개 결과 생성 검증, input hash 보존을 확인했다. 최초 sheet 각1장을 시각 점검했다. 나머지를 AI 정상 판정으로 채우지 않았다.
- 같은 배경의 영상·제품사진도 포함된다. 기존 val과 실제 camera/session을 공유하는지 추가 확인해야 하며, metadata proxy 통과만으로 formal leakage-free를 주장하지 않는다.

## 4. 다음 학습 순서

1. 준비된150개를 기존 사이트의 같은 두 질문으로 검수하고 source/session·좌표·negative gate를 닫는다. 사이트 배포는 기존 사이트 담당 작업으로 넘긴다. 학습 승인은 별도다.
2. 통과분만 기존 train에 추가한 **SOHAS real-gap development**를 만든다. 추가된 고유 positive/negative·group·draw·optimizer update 예산을 기록하고 현재 scale.9 모델과 같은 tuning val에서 비교한다. 기존 val/test는 성능을 높이려고 재분할하지 않는다.
3. 실사 보강 효과가 확인된 뒤에만 Simuletic 최대71개를 train-only로 넣는 독립된 S1 trial을 설계한다. DaSCI의 애매한 group 경계를 임의로 풀어 먼저 학습하지 않는다.
4. 실제 설치 환경 촬영과 독립 session 평가 후 최종 detector·threshold를 고정하고 동일 D*의 B0~B3 사건 실험으로 이어간다.

현재는 모델 크기·seed·epoch·입력 해상도를 동시에 늘리는 탐색을 하지 않는다. 검증 객체14개에서 한 개가 recall7.14%p를 바꾸므로, 이번 결과는 단일 seed·반복 tuning의 개발 증거다. mAP 개선율을 논문 일반화 성능이나 Orin 실시간 성능으로 주장하지 않는다.

## 5. 재현과 원시 결과

- 두 후속 학습 source commit: `8d57c258c717f732dd65c91380be9028e6a43e37`; 기존 SGD run source는 기존 invocation에 보존. source 추가 audit/tool은 같은 base의 QA overlay에서 실행했고 tested script SHA는 aggregate에 기록했다. 이후 commit이 해당 tool source를 포함한다.
- PC13 `runs/training/<run-id>/`: results.csv, best/last.pt; `runs/training/<run-id>-invocation.json`: 설정·환경·input/artifact hash·시간·지표. `runs/launch-<run-id>/`: detached worker·stdout/stderr·exit0.
- 진단: `runs/diagnostics-sohas-20261026-{sgd-v2,adamw-v1,smallscale-v1,coco-v1}/`. train/val GT·canonical prediction JSONL·일대일 match·per-GT error·val contact sheet·sweep 보존. 초기 .001 floor 실패 산출물도 보존했으며 정상 sweep은 .05 floor다.
- 추가 source audit: `data/work/reinforcement-audit-20261026-v2/`. 새 pack: `data/review/sohas-gap-20261026-v1/`. aggregate/개발용 선택 기록: `runs/development-error-analysis-20261026-v1/`.
- 검증: PC13 격리 source 전체138 tests·compileall 통과. 기존 formal source gate·최종평가 차단을 유지한다. Windows process RemoteSigned만 사용했고 서비스·전원·예약 작업은 바꾸지 않았다. 대용량/이미지는 PC13에만 보관한다.

후속 config/launch/진단의 재현 명령은 [CUDA handoff](../../../docs/training-cuda-handoff.md#고정-split-후속-개발-실험)에 있다. 팩 재생성은 아래 명령에서 output을 **새 경로로 바꿔** 실행한다. 기존 output을 지우거나 덮어쓰지 않는다. source/script/checkpoint bytes를 summary hash와 대조해야 동일 실험이다.

```powershell
python tools/prepare_gap_review.py `
  --source data/source-audit/sohas-upstream-byte-exact `
  --voc data/source-audit/sohas-voc-full-images-20261004/voc-candidates.jsonl `
  --integrity data/work/image-screening/sohas-full-20261004-v1/image-integrity.jsonl `
  --pairs data/work/image-screening/sohas-full-20261004-v1/similarity-pairs.jsonl `
  --review data/work/review-candidates/20261026-training-v1/review-linked-manifest.jsonl `
  --prepared data/processed/sohas-reviewed-development-20261026-smallscale-v1 `
  --checkpoint runs/training/sohas-reviewed-development-20261026-smallscale-v1/weights/best.pt `
  --output data/review/<fresh-gap-pack-id>
```
