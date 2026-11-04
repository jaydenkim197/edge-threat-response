# 2026-11-04 기성 YOLO26 최고 정확도 모델과 개발 best.pt 비교

상태: PC13 CUDA의 아래 이미지 평가 범위 `VERIFIED`. 최종 detector 선정·Orin 성능·실제 사건 성능은 미검증.

## 결론

이번 test23장에서는 현재 fine-tuned YOLO26n이 COCO pretrained YOLO26x보다 높은 knife AP와 고정 threshold 재현율을 보였다. 따라서 **대형 기성 모델로 즉시 교체하는 것은 지지되지 않는다**. 기존 모델도 knife20개 중7개만 맞춰(Recall35%) 실사용 충분성을 보여주지 못했다. validation에서는 x1280의 AP50이 더 높으므로, 대형 모델이 항상 열등하다거나 현재 모델이 최종 우위라는 주장은 하지 않는다.

## 질문과 모델 선정

- 사용자 요청: 낮은 개발 모델 성능을 검증하기 위해 가장 성능 높은 기성 YOLO를 같은 테스트셋에서 실행한다. 새 학습은 하지 않는다.
- [공식 YOLO26 표](https://docs.ultralytics.com/models/yolo26)의 ready COCO checkpoint 중 전체 COCO mAP50–95가 가장 높은 **YOLO26x**를 선택했다(공식 표57.5, one-to-many 정확도 경로). 이는 모든 detector 중 최고 또는 knife-specific 최고라는 뜻이 아니다.
- 비교 변수: 기존 custom n vs COCO n(도메인 fine-tuning 차이), COCO n vs x(크기), x640 vs x1280(입력 해상도). 학습 recipe 효과나 통계적 인과를 이 작은 표본으로 확정하지 않는다.
- YOLO26x는 [공식 assets v8.4.0](https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26x.pt)에서118,667,365bytes 다운로드했다. hash는 아래와 aggregate에 보존한다.

## 평가 데이터와 test 공개 이력

- 고정 DEV-SOHAS183장 중 기존 val23장(knife14개/small11개/음성10장), 기존 reserved test23장(knife20개/small16개/음성3장)을 사용했다. train137장은 이번 평가에 넣지 않았다.
- **2026-11-04 직접 사용자 요청으로 reserved test23장을 열었다. 이후 이23장은 unseen final test가 아니다.** 기존 test 보관 방침은 이 개발 비교 범위에서 대체되며, 이후 정식 평가에는 별도 독립 holdout이 필요하다.
- 원본 split/manifest/승인 파일 bytes는 바꾸지 않았다. 평가 복사본의 truth는 `status=development_authorized`, `partition=tuning`, `original_split=test|val`, `purpose=opened_development_comparison`으로 표시했다. 기존 source 전체/좌표/실제 session/최종 평가 승인을 만들어낸 것이 아니다.
- frozen manifest의 image/label SHA-256, object count를 검증했다. 원본을 수정하지 않고 각 모델 class map에 맞춘 label 복사본만 만들었다. custom knife=0, COCO knife=43, COCO 이름80개를 유지하고 knife class만 평가한다.
- 표본은 SOHAS 개발 proxy group 분할이며 실제 카메라 session 독립성이나 고정3m CCTV 대표성을 확정하지 않는다. test20개 중16개가 normalized area≤.02라는 small 기준에 든다. 이 기준은 물리적 거리가 아니다.

## 통제 조건과 지표

- PC13 RTX3060 12GB, Windows11, Python3.12.4, torch2.6.0+cu124, torchvision0.21.0+cu124, Ultralytics8.4.152, NumPy1.26.4, OpenCV4.11.0.86, CUDA device0.
- 전체 모델: batch1, FP32(`half=False`), square letterbox(`rect=False`), workers0, NMS IoU.7, max_det300, knife class만 평가. `nms=None`으로 현 버전의 one-to-many 기본 경로를 사용하고 실제 predictor `end2end=False`를4개 모두 확인했다.
- **AP50/AP50–95**: native validator, confidence floor.001. 표의 AP는 단일 knife class의 AP다.
- **고정 P/R/TP/FP/FN**: canonical JSONL(confidence floor.05)를 기존 bbox evaluator로 평가, confidence≥.25 / matching IoU≥.5. small=normalized GT area≤.02. 예측0개일 때 precision은 undefined(—)다.
- native `results_dict` P/R은 threshold sweep의 best-F1 지점이다. 표의 고정.25 P/R과 섞지 않는다. x1280 test의 native best-F1 recall.55를 .25 운영 recall로 표시하면 잘못이다(고정.25 recall.05).
- 이전 보고의 custom val AP50 .5520과는 batch/letterbox 등 protocol이 다르므로 직접 대조하지 않는다. **기존 custom도 이번 공통 조건에서 재평가했다.** test 결과로 threshold를 튜닝하지 않았다.

## Test 결과: 23장 / knife20개

| 모델 / 입력 | AP50 | AP50–95 | Precision@.25 | Recall@.25 | TP / FP / FN | small TP / GT |
|---|---:|---:|---:|---:|---|---|
| custom-n-640 | 34.43% | 17.21% | 63.6% | 35.0% | 7 / 4 / 13 | 5 / 16 |
| coco-n-640 | 6.33% | 2.98% | — | 0.0% | 0 / 0 / 20 | 0 / 16 |
| coco-x-640 | 19.44% | 5.79% | 33.3% | 5.0% | 1 / 2 / 19 | 0 / 16 |
| coco-x-1280 | 24.98% | 7.66% | 20.0% | 5.0% | 1 / 4 / 19 | 0 / 16 |

음성3장 중 FP가 발생한 이미지는 custom1장/FP1box, COCO 세 조건0장이다. 표의 전체 FP에는 양성 이미지의 잘못된 box도 포함한다. 음성3장만으로 오경보율을 일반화할 수 없다.

## Validation 결과: 23장 / knife14개

| 모델 / 입력 | AP50 | AP50–95 | Precision@.25 | Recall@.25 | TP / FP / FN | small TP / GT |
|---|---:|---:|---:|---:|---|---|
| custom-n-640 | 50.17% | 21.73% | 66.7% | 42.9% | 6 / 3 / 8 | 4 / 11 |
| coco-n-640 | 29.39% | 17.69% | — | 0.0% | 0 / 0 / 14 | 0 / 11 |
| coco-x-640 | 42.06% | 26.38% | 100.0% | 21.4% | 3 / 0 / 11 | 1 / 11 |
| coco-x-1280 | 59.33% | 26.61% | 100.0% | 28.6% | 4 / 0 / 10 | 2 / 11 |

x1280은 val AP50에서59.33%로 custom50.17%보다 높지만 test에서는24.98% 대34.43%로 역전된다. 표본/장면·객체 분포와 confidence/localization 차이를 포함해 해석해야 하며 크기 하나의 효과로 단정하지 않는다.

## 저장된 예측의 사후 오류 진단

기존 `training_diagnostics.error_categories`와 contact-sheet helper를 재사용했다. 새 모델 추론이나 라벨 수정은 없으며 사람 검수를 대신하지 않는다. .05 이상 저장 예측을 기준으로 GT별 진단한다(정식 일대일 지표는 위 evaluator 표).

| test GT20개 분류 | custom n640 | COCO x1280 |
|---|---:|---:|
| IoU≥.5 / confidence≥.25 | 7 | 1 |
| IoU≥.5이나 .05≤confidence<.25 | 2 | 3 |
| 위 매칭 없이 최대 IoU .25–.5 | 1 | 3 |
| 나머지 미검출 | 10 | 13 |

첫 contact sheet도 확인했다. 일부 칼의 누락·낮은 점수·부분 box가 보이며, custom은 낮은 confidence에서 배경 box도 생성한다. 그러나 전량 annotation이 옳다고 이 자동 진단으로 인증하지 않는다. 낮은 threshold로 일부 recall을 회복할 가능성과 FP 증가는 개발 val에서 별도로 검증해야 한다.

## 재현과 보존 증거

- 실행 source base: `cf674506274a0cc607f15e8e9573e0d5ce941163` + 평가 script overlay. 이 실험은 현재 main 전체를 PC13에 먼저 배포했다는 뜻이 아니다.
- 실행 script SHA-256: `940acdcfca42815c3bf5f652280b57d1f77882bd17aaa182f815e58867fc0d20`. 커밋되는 `tools/compare_ready_detectors.py`와 bytes 동일을 확인했다.
- current custom best SHA-256: `d8eff85efff890041d67f9aea80d3d0d7a9530312eb7c2da2baace5e3840c043`
- COCO n SHA-256: `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`
- COCO x SHA-256: `9fdd44a31c504547ffb81d2c6d9e6dac3493c8eaa8b0398d3f43bae6c7003e92`
- source training config·manifest·authorization·train/val/test list·세 weight hash와 val/test image/label bytes가 실행 전후 동일하다. 새 학습/weight 교체/사이트·DB·배정 수정은 없다.
- 성공 run: PC13 `C:/Class6/edge-threat-response/runs/ready-detector-comparison-20261104-v3/`. `summary.json` 완료 marker, `test-access.json`, val/test truth, case별 native-val·canonical predictions·matches·summary·평가 복사본을 보존한다. 정리된 수치/환경/input hash는 [aggregate.json](aggregate.json)에 있다.
- 로그: PC13 `data/work/ready-detector-comparison-20261104-v3.log`. 이미지/weight/원시 결과는 Git에 넣지 않는다. test contact sheets는 두 case의 `test-ai-diagnostic/`에 보존했다(기존 helper 파일명 `val-page-*`지만 이 폴더의 입력은 opened test).
- v1/v2는 validator YAML의 필수 `train` key 누락으로 중단됐다. 평가 전용 YAML에 `train: []`를 명시해 v3를 완료했다. v3 외부 launcher의 로그 출력은 Windows cp949 Unicode 오류가 났으나, child는 모든4개 case·전후 hash 검사를 마치고 완료 summary를 기록했다. 그 외부 launcher가 exit0였다고 기록하지 않는다.
- 로컬 Python3.12.14 UTF-8 mode: 기존 detection evaluator7 tests·script compileall·명시적 test-open flag 없이 입력/출력 접근 전 거부하는 guard 검증 통과. PC13 실제4개 case의 val/test native AP 및 JSONL 고정 evaluator가 성공했다. 이번에 전체 test suite를 재실행한 것은 아니다.

현재 repo에서 재실행 시 **새 output 경로**를 사용한다:

```powershell
$env:PYTHONUTF8='1'
.venv-ml/Scripts/python.exe tools/compare_ready_detectors.py `
  --prepared data/processed/sohas-reviewed-development-20261026-smallscale-v1 `
  --checkpoint runs/training/sohas-reviewed-development-20261026-smallscale-v1/weights/best.pt `
  --small yolo26n.pt --large models/comparison-20261104/yolo26x.pt `
  --output runs/ready-detector-comparison-NEW-RUN-ID --open-reserved-test
```

## 판단과 다음 범위

기성 x checkpoint의 즉시 교체를 채택하지 않는다. 현재 custom도 충분하지 않으며 최종 D*는 미확정이다. 다음은 **검수·라벨/중복/group gate를 통과한 target-domain 및 small-knife 보강**, 더 큰 모델의 도메인 fine-tuning을 제한된 통제 실험으로 비교하는 방향이 타당하다. 이것은 새 source 자동 승인이나 이번 작업에서 추가 학습을 돌렸다는 뜻이 아니다. confidence 선택은 val에서만 하고 새 독립 평가를 준비한다. 카메라/GPIO·Orin FPS/전력/지연·event B0~B3 성능은 이 이미지 실험으로 검증되지 않았다.
