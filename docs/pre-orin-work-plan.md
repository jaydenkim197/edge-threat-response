# Pre-Orin Work Plan

기준일: 2026-10-04

상태: PC core·replay·dataset tooling·video adapter·CUDA handoff `IMPLEMENTED`/PC `VERIFIED`; legacy 사람 검수·외부 source audit·CUDA full training·Orin 통합 `PLANNED`

이 문서는 Orin Nano를 받기 전의 **남은 작업**을 관리한다. 과거 W1~W6의 상세 구현·측정 이력은 [Development Log](development-log.md)와 [Verification Matrix](verification.md)에 보존한다. 실제 보드가 도착하면 환경·장비 상태를 재확인하고 이 계획을 갱신한다.

## 현재 확인된 기반

- 순수 판단 core, B0~B3 replay, knife-only dataset audit/export/review pack, image/video detector adapter와 snapshot 경로를 PC에서 검증했다.
- legacy 원본은 7,364장이고 exact duplicate 3장을 제거한 development export는 7,361장이다. 기존 split에는 source group 교차가 발견됐다.
- 로컬 CPU에서 YOLO26n 소규모 학습 smoke를 완료했다. 이는 학습 배관 검증이며 detector 품질 근거가 아니다.
- CUDA용 runner·config·GPU preflight·Colab notebook은 준비됐지만 full training은 실행하지 않았다.
- W4 review pack은 128행 CSV와 8개 contact sheet가 준비됐다. 사람 판정과 L0 학습 승인은 아직 없다.
- 선택 detector의 CUDA/Orin 성능, 카메라, GPIO와 TensorRT 동작은 실기기에서 검증되지 않았다.
- 사건 평가기·가상 B0~B3 end-to-end와 촬영/수동 정답/세션 분리 양식을 준비했다. 실제 거리·matching tolerance·반복 규모는 pilot 후 확정한다([통제 실험](controlled-experiment-protocol.md)).
- R1/H1의 공통 평가 목록·matched draw budget·hash-bound approval gate·결과 비교 코드는 준비됐다. 승인된 SOHAS export가 없어 full training은 차단 상태다([학습 준비](training-cuda-handoff.md)).

## 다음 작업과 완료 기준

| 트랙/순서 | 작업 | 완료 증거 |
|---|---|---|
| 팀원 L0-1 | Legacy 128장 사람 검수 | [Dataset Evaluation Criteria](dataset-evaluation-criteria.md)에 따라 `review.csv`를 판정하고 source/version·split·bbox-size 구간별 결과와 불확실 사례를 기록 |
| 팀원 L0-2 | L0 사용 범위·재현 결정 | 표본 결과에 근거해 legacy 전체/선별/역사적 기준의 역할과 추가 검수 필요성을 결정. `open-decisions.md`에 근거 연결 |
| 신규 R-1 | 공개 source audit | SOHAS 권리 표기 충돌·image/XML pairing·양성/음성·group을 확인. DaSCI의 SOHAS와 동일한 1,985장 및 고유 후보 최대 93장을 별도 기록 |
| 신규 R-2 | CUDA full-training 준비·실행 | 승인된 [R1/H1 후보](dataset-source-strategy.md)와 group-aware manifest, 고정 config·run ID·hash를 남기고 GPU에서 학습. [CUDA handoff](training-cuda-handoff.md) 준수 |
| 공통 3 | Orin 입고 시 inventory·통합 | SKU·전원·저장장치·JetPack 확인 후 native runtime, 모델, camera, GPIO, 자원 측정 순으로 실기기 검증 |
| 공통 실험 | Pilot 촬영·주석·동결 | 준비된 촬영표/사건 정답으로 거리·허용 오차·반복 수를 정하고 tuning/final-test 세션을 분리. 가상 평가기 성공을 실제 실험 결과로 취급하지 않음 |

L0와 신규 R 트랙은 병렬이며 L0 검수 완료가 R-1/R-2의 선행 gate가 아니다. R-1은 보드 없이 진행할 수 있고 R-2는 CUDA GPU, 공통 3은 실제 Orin이 필요하다. 공개 source 채택은 [Dataset Source Strategy](dataset-source-strategy.md)의 후보 역할과 [검수 기준](dataset-evaluation-criteria.md)의 gate를 따른다. Detector topology는 [P0-05](open-decisions.md)에 남겨 두며, knife-only 학습 source에 person bbox가 없다는 이유만으로 unified 2-class 데이터에 병합하지 않는다.

## 검증 경계

- Development split 비율·seed, image size, confidence, K/N은 연구 최종값이 아니다.
- PC smoke와 실기기 성능을 별도 기록한다. Orin Nano의 FPS·지연·메모리·온도는 실제 장비에서만 측정한다.
- TensorRT/FP16은 PyTorch 또는 선택 runtime의 기준 성능을 얻은 뒤 필요성과 효과를 판단하는 Stretch다.
- 동일 detector·입력·설정의 B0~B3 사건 비교에는 시간 순서와 수동 event start/end 정답이 필요하다.
