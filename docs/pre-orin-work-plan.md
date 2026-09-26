# Pre-Orin Work Plan

기준일: 2026-09-26

상태: PC core·replay·dataset tooling·video adapter·CUDA handoff `IMPLEMENTED`/PC `VERIFIED`; legacy 사람 검수·외부 source audit·CUDA full training·Orin 통합 `PLANNED`

이 문서는 Orin Nano를 받기 전의 **남은 작업**을 관리한다. 과거 W1~W6의 상세 구현·측정 이력은 [Development Log](development-log.md)와 [Verification Matrix](verification.md)에 보존한다. 실제 보드가 도착하면 환경·장비 상태를 재확인하고 이 계획을 갱신한다.

## 현재 확인된 기반

- 순수 판단 core, B0~B3 replay, knife-only dataset audit/export/review pack, image/video detector adapter와 snapshot 경로를 PC에서 검증했다.
- legacy 원본은 7,364장이고 exact duplicate 3장을 제거한 development export는 7,361장이다. 기존 split에는 source group 교차가 발견됐다.
- 로컬 CPU에서 YOLO26n 소규모 학습 smoke를 완료했다. 이는 학습 배관 검증이며 detector 품질 근거가 아니다.
- CUDA용 runner·config·GPU preflight·Colab notebook은 준비됐지만 full training은 실행하지 않았다.
- W4 review pack은 128행 CSV와 8개 contact sheet가 준비됐다. 사람 판정과 L0 학습 승인은 아직 없다.
- 선택 detector의 CUDA/Orin 성능, 카메라, GPIO와 TensorRT 동작은 실기기에서 검증되지 않았다.

## 다음 작업과 완료 기준

| 순서 | 작업 | 완료 증거 |
|---:|---|---|
| 1 | Legacy 128장 사람 검수 | [Dataset Evaluation Criteria](dataset-evaluation-criteria.md)에 따라 `review.csv`를 판정하고 source/version·split·bbox-size 구간별 결과와 불확실 사례를 기록 |
| 2 | L0 사용 범위 결정 | 표본 결과에 근거해 legacy 전체/선별/역사적 기준의 역할과 추가 검수 필요성을 결정. `open-decisions.md`에 근거 연결 |
| 3 | 공개 source audit | SOHAS 권리 표기 충돌을 확인하고 접근 가능한 source를 표본·라벨·session·중복 검사. ACF는 원본 접근 가능성부터 확인 |
| 4 | CUDA full-training 준비·실행 | 승인된 dataset recipe와 group-aware manifest, 고정 config·run ID·hash를 남기고 GPU에서 학습. [CUDA handoff](training-cuda-handoff.md) 준수 |
| 5 | Orin 입고 시 inventory·통합 | SKU·전원·저장장치·JetPack 확인 후 native runtime, 모델, camera, GPIO, 자원 측정 순으로 실기기 검증 |

1~3은 보드 없이 진행할 수 있다. 4는 CUDA GPU, 5는 실제 Orin이 필요하다. 공개 source 채택은 [Dataset Source Strategy](dataset-source-strategy.md)의 후보 역할과 [검수 기준](dataset-evaluation-criteria.md)의 gate를 따른다. Detector topology는 [P0-05](open-decisions.md)에 남겨 두며, knife-only 학습 source에 person bbox가 없다는 이유만으로 unified 2-class 데이터에 병합하지 않는다.

## 검증 경계

- Development split 비율·seed, image size, confidence, K/N은 연구 최종값이 아니다.
- PC smoke와 실기기 성능을 별도 기록한다. Orin Nano의 FPS·지연·메모리·온도는 실제 장비에서만 측정한다.
- TensorRT/FP16은 PyTorch 또는 선택 runtime의 기준 성능을 얻은 뒤 필요성과 효과를 판단하는 Stretch다.
- 동일 detector·입력·설정의 B0~B3 사건 비교에는 시간 순서와 수동 event start/end 정답이 필요하다.
