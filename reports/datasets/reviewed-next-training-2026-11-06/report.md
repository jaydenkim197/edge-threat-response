# 검수 현황·다음 학습안·마일스톤 — 2026-11-06

**다음 공개 데이터 학습 후보는 YOLO26n/640의 Q1 정제 실험이다.** 기존 M1 train에서 문제·모르겠음 88장을 제외하고, 같은 초기 pretrained weight·학습 예산으로 비교한다. 별도로 실제 CCTV 학습 세션을 확보해 T1 목표 환경 적응을 진행하는 것이 성능 개선의 우선순위다. 정상 검수 2,527장을 모두 새로운 학습 이미지로 추가하는 방식은 맞지 않는다.

이 문서의 학습안은 `PROPOSAL`이며 새 전체 학습은 실행하지 않았다. 이번 작업은 PC13 운영 검수 자료의 읽기 전용 감사, 기존 학습·보호 그룹과의 대조, 확대 CCTV 개발 평가다. 운영 DB·판정·배정·이미지·기존 split을 수정하는 명령은 실행하지 않았다.

## 1. 실제 검수 현황

감사 snapshot: **2026-11-06 17:31 KST**. 여러 검수 팩의 DB를 각각 읽기 전용 transaction으로 읽었으므로 전 팩에 대한 단일 원자적 snapshot은 아니다. 사이트 사용 중에는 수치가 달라질 수 있다. [집계·팩/판정 해시](audit-summary.json).

| 후보 | 준비 | 검수 완료 | 정상 | 문제·모르겠음 |
|---|---:|---:|---:|---:|
| SOHAS | 1,150 | 1,149 | 1,114 | 35 |
| DaSCI | 93 | 93 | 93 | 0 |
| Simuletic CCTV | 114 | 113 | 106 | 7 |
| US Mock Attack | 100 | 99 | 83 | 16 |
| Dangerous Items | 400 | 150 | 124 | 26 |
| Open Images | 610 | 30 | 29 | 1 |
| Legacy | 128 | 128 | 123 | 5 |
| Catargiu | 793 | 790 | 734 | 56 |
| Simuletic ATM | 237 | 121 | 121 | 0 |
| **합계** | **3,625** | **2,673** | **2,527** | **146** |

미검수는 952장이다. SOHAS 추가 800장은 799장 검수/795장 정상이나, Dangerous 추가 250장과 Open Images **train 표본 580장**은 이 snapshot에서 아직 판정이 없다. Open Images 정상 29장은 기존 외부 평가 표본이므로 train으로 전환하지 않는다. 별도 원본 train 확보량 594장과 웹 검수 표본 580장은 다른 수치다.

## 2. 정상 판정이 곧 새로운 학습 자료는 아니다

SHA-256, 기존 RAW inventory의 split/group, 보호 평가 proxy group, 실제 이미지와 표시 라벨을 대조했다. 기존 train과의 라벨 비교는 원본 주석 해시와 표시 bbox의 픽셀 좌표를 확인했다(허용 오차 0.75px). 정상 판정의 이미지 SHA는 2,527개로 모두 고유하다.

| 구분 | 확인 결과 | 처리 방향 |
|---|---|---|
| 기존 M1 train이며 정상 판정·표시 라벨 일치 | **1,805장**: SOHAS 1,064 / Dangerous 38 / Catargiu 703 | 신규 추가로 세지 않음 |
| 기존 M1 train이며 문제·모르겠음·표시 라벨 일치 | **88장**: SOHAS 33 / Dangerous 2 / Catargiu 53. 문제 49 / 모르겠음 39 | 원본 삭제 없이 새 정제 manifest에서 제외 후보 |
| 새 실사 추가 후보 | **39장**: Dangerous 28 / Catargiu 11. 양성 5 / 칼 부재 확인 음성 34 | 기존 corpus와 직접 연결 검사 통과. 전체 신규 간 전이적 그룹 검사·source/반입 확정은 남음 |
| DaSCI 정상 93장 | 92장은 기존 보호 그룹, 나머지 1장도 직접 보호 연결 | 현재 정책에서 train 추가 0 |
| US Mock 정상 83장 | 외부 CCTV 개발 평가 역할 | train 제외 |
| Open Images 정상 29장 | 기존 외부 평가 역할 | train 제외. 별도 train 원본을 후속 M2 후보로 사용 |
| Legacy 정상 123장 | 팀원 L0 트랙 | 주력 학습으로 자동 병합하지 않음 |
| Simuletic CCTV/ATM | 합성 자료 | 실사 주력에 자동 병합하지 않고 S1 별도 비교 |

88장에서는 정상/보류의 동일 SHA 충돌이나 기존 학습과 다른 표시 bbox가 발견되지 않았다. 보류가 반드시 잘못된 라벨이라는 뜻은 아니므로 49장 문제와 39장 불확실을 구분해 보존한다.

새 후보 39장은 기존 전체 후보/보호 corpus에 대한 직접 dHash 거리 4 및 Roboflow filename-family 검사에서 보호 연결이 없었다. 신규 이미지끼리 연결한 뒤 기존 그룹으로 이어지는 **전이적 검사까지 완료한 최종 승인량은 아니다**. [수량과 미완료 상태](candidate-counts.json).

실사 주력 SOHAS/Dangerous/Catargiu의 정상 판정 중 `target_cctv` 표시는 **55장**이다. 이 태그만으로 실제 3m 설치·소품·거리 적합성이 검증됐다고 할 수 없다. 해당 3개 source의 domain 미상도 1,274장이다. 검수 표본의 비율을 전체 원본 분포로 일반화하지 않는다. 현재 두 질문 검수는 person bbox나 Holding 관계 정답을 만들지 않는다.

## 3. 확대 CCTV 개발 평가

기존 US Mock 개발 평가 21장에서 검수 정상 **83장 / knife GT 31개 / 음성 52장 / source sequence 16개**로 확대해 동일 입력을 5개 모델 조건에 적용했다. 양성 sequence는 9개다. 기존 열린 21장을 포함하며, 나머지 62장을 이번에 추가 공개했다. 모든 자료는 이제 개발 평가용이며 독립 final test가 아니다.

PC13 RTX 3060, 기존 격리 평가 환경, FP32/batch 1, confidence 0.25, IoU 0.5, normalized small area≤0.02를 사용했다. 31 GT 모두 이 small 정의에 해당한다. YOLO는 실제 predict 기본 후보 처리, RF-DETR는 공식 predict와 native 입력 704다. 이미지·checkpoint·suite hash를 검증했다. M1-n/960은 **640 학습 weight의 추론 해상도 변경**이며 960 재학습이 아니다.

| 모델 조건 | TP / 31 | Recall | 전체 FP boxes | 음성 52장 중 FP 발생 이미지 |
|---|---:|---:|---:|---:|
| 기존 D0 YOLO26n / 640 | 1 | 3.23% | 83 | 34 |
| RAW-M1-n / 640 | 0 | 0% | 2 | 0 |
| RAW-M1-s / 640 | 0 | 0% | 0 | 0 |
| 기성 RF-DETR Large / 704 | 1 | 3.23% | 0 | 0 |
| RAW-M1-n / 960 | 1 | 3.23% | 2 | 1 |

추가로 기존 예측 캐시만 이용해 threshold를 진단했다. M1-n/640은 confidence 0.10에서도 **3/31 TP·14 FP**, 0.001에서도 **3/31 TP·1,032 FP**였다. M1-n/960은 0.001에서 4/31·855 FP였다. 기성 RF-Large는 0.001에서 11/31·369 FP다. 따라서 이 표본에서는 threshold만 낮추는 것으로 실용적인 recall/FP를 확보하지 못했다. 운영 threshold는 변경하지 않았다.

**해석:** 공개 실사 개발셋에서 M1 개선은 확인됐지만 작은 CCTV knife 검출은 여전히 부족하다. 목표 환경 데이터 적응이 필요하다는 근거이며, 라벨 정제나 s 전환만으로 해결된다는 근거는 아니다. 선택된 정상 검수 표본, 단일 seed, sequence 내 연관 프레임, 사전학습 corpus 중복 가능성, source 간 차이가 있으므로 일반 성능·통계적 우월성·사건 오경보 감소로 주장하지 않는다.

- [동일 입력 정량 CSV](cctv-evaluation/comparison.csv), [집계·환경](cctv-evaluation/aggregate.json), [threshold 진단](cctv-evaluation/threshold-diagnostic.json)
- [모델·weight hash](cctv-evaluation/models.json), [suite·입력 hash](cctv-evaluation/suite.json), [이미지 hash·sequence 선택](cctv-evaluation/selection.csv), [완료 상태](cctv-evaluation/state.json)
- PC13 원시 예측·matches·로그: `C:\Class6\edge-threat-response\runs\reviewed-cctv-20261106-v2`
- 원래의 8모델×6개 개발셋 비교는 [이전 보고서](../../evaluation/raw-detector-selection-2026-11-06/report.md)를 유지한다. 이번 5조건 확대 평가가 전체 이전 비교를 대체하지 않는다.

## 4. 다음 학습의 순서와 통제 조건

**권장 순서: Q1 정제 기준선 → 별도 실사 M2 보강 → 자체 CCTV T1 적응.** 목표 환경 촬영/라벨 준비는 Q1과 병행하고, 확보되는 즉시 T1 준비를 우선한다. n/s/해상도/새 source를 한 번에 조합하지 않는다. 이 순서는 기존의 포괄적 M2 권장안을 구체화한 `PROPOSAL`이다.

1. **Q1-clean-n:** 기존 M1 train 11,378장에서 88장을 보류한 **11,290장**으로 비교한다. SOHAS 4,949 / Dangerous 1,294 / Catargiu 5,047. 신규 source는 넣지 않아 정제 recipe 차이를 먼저 비교한다. 정상 검수만 남긴 1,805장으로 전체를 축소하면 미검수 기존 train 9,485장의 다양성을 동시에 잃으므로 주력안으로 삼지 않는다. 미검수 RAW 사용 허용은 유지한다.
2. 초기 weight는 M1과 같은 YOLO26n pretrained checkpoint를 사용한다. **M1 best.pt에서 이어 학습하는 실험과 혼동하지 않는다.** 640, batch=nbs 16, FP32, AdamW/lr .001, scale .9, seed 20261004, 50 epoch·11,392 draws/epoch·35,600 실제 updates를 맞춘다. train pool 크기가 달라 반복 노출 분포가 조금 달라지므로 완벽한 라벨 품질 인과효과가 아닌 통제된 recipe 비교로 해석한다.
3. 기존 val/test 각 1,423장, opened benchmark와 그 보호 그룹은 유지한다. Q1 비교 완료 기준은 같은 source별 평가에서 recall/FP/작은 칼 오류를 기존 M1과 비교하고 checkpoint/config/manifest/log hash를 보존하는 것이다. Q1의 성능 개선을 미리 가정하지 않는다.
4. **M2-real-n:** 새 실사 39장(양성 5·음성 34)은 전체 전이적 그룹/source 검사를 마친 뒤 별도 추가안으로 관리한다. Q1에 모두 넣으면 최대 **11,329장**이나 확정 수량은 아니다. 이를 Q1에 동시에 넣고 결과를 순수 정제 효과라고 부르지 않는다. 39장만 추가하기 위해 별도 50 epoch를 반드시 돌리지는 않으며, Open Images 별도 train·Dangerous 보강의 실제 gap 기여와 함께 run 필요성을 판단한다.
5. **T1-target-n:** 직접 촬영한 목표 CCTV/스마트폰 train session의 작은 knife·가림·일상 물체 음성을 보강한다. 튜닝·최종평가 세션은 분리한다. 현재 CCTV FN을 해결할 핵심 후보이며 확보 전 성능 향상을 주장하지 않는다. T1이 준비되면 미미한 공개 source 조합 반복보다 우선한다.
6. s/960 재학습은 위 데이터축 비교 후 효과가 있을 때 수행한다. Orin 비용은 별도로 측정한다. HOI는 bbox 검수와 별개로 Holding/Not Holding pair GT를 만들어 B4-G/B4-VG를 학습한다.

검수 작업의 추가 우선순위는 **Open Images train 580장 → Dangerous 추가 250장 → 기존 문제/불확실 재확인**이다. 이는 품질 정보 확보 순서이며 RAW 예비 학습의 인간 검수 필수 gate를 되살리는 결정은 아니다.

## 5. 현재 마일스톤과 남은 일정

현재 위치는 **공개 데이터 detector baseline 비교 완료 → 정제·목표 환경 적응 데이터 준비**다. 실제 CCTV에서 실용적인 knife 성능을 확보하거나 최종 detector D*를 동결한 단계는 아니다.

| 마일스톤 | 현재 상태 | 남은 완료 증거 |
|---|---|---|
| B0~B3 판단·replay·사건 평가기 | `IMPLEMENTED`, PC/가상 정답 및 기존 Orin 파일 입력 검증 | 실제 촬영 event GT의 독립 최종 평가 |
| RAW R1/H1/M1-n/M1-s | `VERIFIED`: 각 50 epoch·35,600 updates, 동일 개발셋 비교 | Q1/M2/T1의 별도 run과 D* 선정 |
| P430→Orin→기존 R1 탐지/B3 | `VERIFIED`: 실제 main/sub 수신·각 300 valid frame·표시 사용자 확인 | 새 M1/T1 모델, 실제 목표 거리 성능·지연·자원·장시간 검증 |
| Q1 정제·새 실사 후보 | 감사 `VERIFIED`, 학습안 `PROPOSAL` | 새 manifest/materialization/학습/공통 비교. 새 39장은 전체 그룹 검사 필요 |
| HOI/B4-G·B4-VG | 코드 `IMPLEMENTED`, 합성·CUDA 경로 검증 | 실제 Holding pair GT, 실제 학습 weight와 관계 정확도 |
| 실제 촬영·독립 final GT | `PLANNED`; 사용자도 실제 촬영 영상·Holding 관계 라벨이 아직 없다고 확인 | 11/9~12 촬영, train/tuning/final 분리·bbox/pair 라벨 |
| 물리 GPIO·B0~B4 최종 사건 비교 | `PLANNED` | 실제 경보·event P/R/F1·false alerts/hour·latency |

기존 일정은 유지한다. **11/5~8** 데이터/HOI 설계 준비, **11/9~12** 촬영·bbox/pair GT, **11/13~16** YOLO·HOI 1차 학습, **11/17~20** 개선·모델/config 동결, **11/21~24** Orin/GPIO 통합, **11/25~27** 독립 최종 평가, **11/28~30** 분석·최종 정리다. RAW detector 학습은 앞서 완료했지만 HOI·독립 촬영·통합 성능까지 일정이 앞당겨졌다는 뜻은 아니다.

## 6. 재현·검증과 한계

- 감사 source는 [audit-worker.py](audit-worker.py), 확대 평가 source는 [evaluation-worker.py](cctv-evaluation/evaluation-worker.py). 이들은 고정 PC13 입력을 사용하는 일회성 증거 스크립트이며 제품 CLI가 아니다. 운영 private config와 원본 corpus가 있어야 재실행 가능하다. DB는 SQLite URI `mode=ro`/명시 transaction으로 읽고 사용자·메모·원 판정 payload는 공개 report에 복사하지 않았다. 원본 snapshot은 PC13 `data/work/reviewed-next-training-20261106`에 보관한다.
- 감사 시 기존 RAW inventory SHA-256은 `95e3cd89c126dad48db9586b4584422cc2e1e1e552678e9c7e4267b29219176d`다. 원본 inventory와 기존 group 재구성 일치·이미지 hash·리뷰 팩 integrity·표시 bbox 비교를 통과했다.
- 평가 source commit은 `e29558681a76b2da82425b3e0ac096616c425eda`. 기존 `run_detector_comparison.py`와 `summarize_detector_comparison.py`를 재사용해 새 출력에서 5조건×83장 평가와 집계를 완료했다. 첫 v1 준비는 suite status/policy 누락으로 inference 전에 거부됐고 보존했다. v2는 정확한 기존 policy로 수정해 통과했다. 제품 코드나 평가 기준을 완화하지 않았다.
- 기본 모델 protocol에 선택적 설명용 `policy` 필드가 없어 집계의 `protocol_metadata_missing=true`를 유지한다. 실제 실행/점수 기준은 suite 및 aggregate의 명시적 `policy`이며 source/checkpoint/truth hash 검사는 통과했다.
- 선택 CSV의 `same_family_as_protected`는 filename-family 플래그의 기본값을 사용한 항목이다. 이 열의 False를 전체 유사도/보호 그룹 미연결 증거로 읽지 않는다. 새 US 이미지 62장 중 27장은 감사에서 기존 보호 그룹과 직접 연결됐으며, 나머지 35장까지 포함해 **83장 전체를 개발 평가 역할로 보호**한다. 이번 평가는 학습 이미지 exact SHA 교차 0을 확인했지만 별도 독립 카메라/촬영 세션의 최종 test를 보장하지 않는다.
- 새 학습·Orin model 교체·운영 threshold 변경은 하지 않았다. 전체 제품 테스트를 이번 문서/일회성 분석만을 위해 다시 실행하지 않았다. 같은 source의 기존 **186 tests 통과**는 이전 검증 기록이며 이번 새 테스트 실행으로 보고하지 않는다. 이번에는 실제 확대 inference·집계, threshold 캐시 재계산, 보고서 수치·링크·해시·diff를 확인했다.
- Git commit/push 식별자는 이 보고서를 추가한 실제 Git 이력으로 추적한다. 다른 개발 채팅의 미커밋 문서·검수 사이트 변경은 포함하지 않는다.
