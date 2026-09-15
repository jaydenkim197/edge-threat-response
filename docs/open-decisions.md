# Open Decisions

권장안은 확정 전까지 `PROPOSAL`이다. 결정 후 행을 삭제하지 않고 상태와 근거를 갱신하며, `development-log.md`의 해당 기록을 연결한다.

| ID | 우선순위 | 결정 사항 | 현재 권장안 | 선택 기준 / 필요한 증거 | 결정 시점 | 상태 |
|---|---|---|---|---|---|---|
| P0-01 | P0 | Orin Nano 실기기 inventory와 설치 경로 | JetPack 7.2.1 기준, UEFI/QSPI 확인 후 NVMe 우선 검토 | 정확한 SKU·RAM, 장비 수령 여부, firmware, microSD/NVMe, 카메라, GPIO, 냉각 | 실기기 통합 전 | `PLANNED` |
| P0-02 | P0 | 기존 소스의 기준 저장소 | 현재 저장소와 고정된 legacy submodule을 기준으로 사용 | 비밀값·라이선스·재현 환경은 계속 별도 확인 | 완료 | `DECISION` / `IMPLEMENTED` |
| P0-03 | P0 | 2026-2 MVP 기능 | knife only + geometry association + K-of-N + 4-state + GPIO + metadata/snapshot + B0~B3 ablation | core/replay는 PC 검증 완료; detector·snapshot·GPIO는 실기기 증거 필요 | 완료 | `DECISION`; core `IMPLEMENTED` |
| P1-01 | P1 | 상황 인식 범위 | geometry-only association과 K-of-N을 MVP로, tracking·movement는 stretch | B0~B3 결과와 Orin 성능 | 완료 | `DECISION` |
| P1-02 | P1 | 기준 Jetson 플랫폼 | 신규 시스템은 Orin Nano Developer Kit + JetPack 7.2.1, Nano는 legacy/선택 비교 | 사용자의 플랫폼 변경 결정과 NVIDIA 최신 지원 환경 확인 | 완료 | `DECISION`; 실기기 `PLANNED` |
| P1-03 | P1 | 이벤트 전송·대시보드 | 로컬 경보 우선, 위험 이벤트 메타데이터만 서버 전송 | 네트워크 단절 시 동작, 개인정보·저장 정책 | 대시보드 구현 전 | `PROPOSAL` |
| P1-04 | P1 | 영상·개인정보 경계 | 원본 영상 최소 보존, 이벤트 기반 저장, 접근 제어 명시 | 지도교수·기관 정책, 수집 장소·동의 범위 | 실제 수집 전 | `PLANNED` |
| P2-01 | P2 | 멀티카메라·Re-ID | 이번 학기 핵심 범위에서는 제외하고 후속 확장으로 보류 | Orin 성능, 카메라 수, 실험 장소, 일정 | MVP 검증 후 | `DEFERRED` |
| P2-02 | P2 | RGB + IR/Thermal 융합 | 조도 취약성 검증 후 별도 확장 후보로 보류 | 센서 확보, 동기화, 데이터셋, 비용 | MVP 검증 후 | `DEFERRED` |
| P2-03 | P2 | Active Learning | 애매한 탐지 샘플 저장·라벨링은 후속 단계 | 데이터 보안, 라벨링 인력, 재학습 재현성 | MVP 검증 후 | `DEFERRED` |
| P0-04 | P0 | 1차 구매 목록 | Orin용 NVMe·카메라·냉각/전원 안정화 장비를 우선 검토 | 정확한 대여 장비 구성, 보유품, 지원 마감일, 견적 | 구매 전 | `PLANNED` |
| P1-05 | P1 | Web Dashboard 범위 | MVP 이후 선택 기능으로 보류 | MVP 진척, 시연 필요성, 개발 시간 | MVP 기능 확정 시 | `PROPOSAL` |
| P0-05 | P0 | baseline detector 구조·모델·입력 규격 | output은 person/knife로 고정. COCO single-model은 sanity baseline, composite person+knife는 primary implementation proposal, unified 2-class는 person annotation 완전성 확보 시에만 후보 | legacy는 knife-only, CUDA/Orin model smoke, sample 품질, license, Orin latency, 고정 입력·threshold | 실제 detector 검증 전 | contract `DECISION`, topology `PROPOSAL` |
| P0-09 | P0 | JetPack 7.2.1 ML runtime | 실제 Orin에서 native PyTorch·Ultralytics smoke를 먼저 수행하고 container는 재현성 대안으로 비교; 성공한 버전·image digest만 고정 | JetPack 7.2.1 공식 지원과 별개로 Orin Nano 조합의 GPU access, YOLO load/inference, TensorRT와 package conflict 확인 필요 | Orin runtime 통합 전 | `PROPOSAL` |
| P0-06 | P0 | 사건 정답과 controlled scenario | person-associated knife event의 수동 annotation, positive/hard-negative 시나리오, distance 필수·lighting 선택 | matching 허용 구간, 모호 frame, 촬영 장소·동의, 반복 횟수 | 촬영 전 | 방법 `DECISION`, 세부 `PROPOSAL` |
| P0-07 | P0 | 프로젝트 정량 목표치 | Orin baseline 측정 후 false alarm·event recall·latency 목표 결정 | 표본 규모, baseline 분산, 일정, 실제 Orin 결과 | 제안서 목표 확정 전 | `PROPOSAL` |
| P1-06 | P1 | 사건 증거 범위 | MVP는 metadata+snapshot 1장, clip은 stretch | 개인정보, 저장공간, 오류 분석 가치 | 완료 | `DECISION` |
| P1-07 | P1 | 상태 머신 상태·전이 | `CLEAR/CANDIDATE/CONFIRMED/COOLDOWN`; CONFIRMED 진입당 action 1회, 연속 clear sample 뒤 rearm | rearm sample 수는 baseline 후 | 완료 | `DECISION`; PC core `VERIFIED` |
| P0-08 | P0 | threshold tuning과 final evaluation 분리 | development/tuning set으로 파라미터를 선택하고 holdout recording session/scene으로 final evaluation | 촬영 장소·세션 수·표본 규모 | 촬영 전 | `PROPOSAL` |
| P1-08 | P1 | Stretch 우선순위 | TensorRT/FP16 → legacy Nano cross-device 비교 → Tracking → Dashboard → Event clip → 추가 class → enclosure/PCB | Orin이 기준 플랫폼으로 변경되어 기존 Orin benchmark 항목을 기준 검증으로 승격 | 완료 | `DECISION` |
| P0-10 | P0 | 외부 dataset recipe | COCO/Open Images/knife-specific/CCTV 후보는 registry·sample 검수 후 승인된 source만 사용 | small/distant knife, person 동시 annotation, CCTV domain, negatives, license, 중복·leakage | D2 import 전 | `PROPOSAL` |
| P0-11 | P0 | ambiguous annotation rule | 모형 knife·reflection·printed image·극소/가림 객체를 sample review로 결정 | detector claim boundary, 일관성, 팀 annotation 합의 | 직접 수집·재라벨링 전 | `PROPOSAL` |
| P0-12 | P0 | Ultralytics 사용·배포 라이선스 | 저장소 전체 라이선스를 자동 지정하지 않고, 공개 학술 AGPL-3.0 경로와 다른 배포 경로를 모델/runtime 채택 전에 명시적으로 선택 | 공개 범위, model weight·학습 script 공개 여부, 포트폴리오·후속 상용 활용 | Ultralytics dependency·model을 배포하기 전 | `PLANNED` |
