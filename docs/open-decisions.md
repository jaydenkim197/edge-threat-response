# Open Decisions

권장안은 확정 전까지 `PROPOSAL`이다. 결정 후 행을 삭제하지 않고 상태와 근거를 갱신하며, `development-log.md`의 해당 기록을 연결한다.

| ID | 우선순위 | 결정 사항 | 현재 권장안 | 선택 기준 / 필요한 증거 | 결정 시점 | 상태 |
|---|---|---|---|---|---|---|
| P0-01 | P0 | Jetson Nano 복구 가능 여부 | 실기기 진단 후 유지 또는 대체 플랫폼 결정 | 부팅, 카메라, GPIO, 냉각, 저장장치 상태 | 구현 시작 전 | `BLOCKED` |
| P0-02 | P0 | 기존 소스의 기준 저장소 | 현재 저장소와 고정된 legacy submodule을 기준으로 사용 | 비밀값·라이선스·재현 환경은 계속 별도 확인 | 완료 | `DECISION` / `IMPLEMENTED` |
| P0-03 | P0 | 2026-2 MVP 기능 | 균형형 후보: baseline + proximity + persistence + 4-state machine + GPIO + metadata/snapshot + benchmark | 10월 31일 Nano 통합 가능성, 기존 대비 차별성, 평가·논문 연결성 | baseline 진단 직후 | 방향 `DECISION`, 기능 `PROPOSAL` |
| P1-01 | P1 | 상황 인식 범위 | MVP는 proximity와 persistence 우선, tracking·movement는 stretch 권장 | 데이터 가용성, ablation 가능성, Nano 성능 영향 | MVP 확정 시 | `PROPOSAL` |
| P1-02 | P1 | Orin Nano 활용 | Nano 기준 결과 확보 후 성능 비교 플랫폼으로 사용. 대여 요청 진행 | 대여 승인, 동일 입력의 FPS·지연·전력·온도 | 실험 설계 전 | `PLANNED` |
| P1-03 | P1 | 이벤트 전송·대시보드 | 로컬 경보 우선, 위험 이벤트 메타데이터만 서버 전송 | 네트워크 단절 시 동작, 개인정보·저장 정책 | 대시보드 구현 전 | `PROPOSAL` |
| P1-04 | P1 | 영상·개인정보 경계 | 원본 영상 최소 보존, 이벤트 기반 저장, 접근 제어 명시 | 지도교수·기관 정책, 수집 장소·동의 범위 | 실제 수집 전 | `PLANNED` |
| P2-01 | P2 | 멀티카메라·Re-ID | 이번 학기 핵심 범위에서는 제외하고 후속 확장으로 보류 | Orin 성능, 카메라 수, 실험 장소, 일정 | MVP 검증 후 | `DEFERRED` |
| P2-02 | P2 | RGB + IR/Thermal 융합 | 조도 취약성 검증 후 별도 확장 후보로 보류 | 센서 확보, 동기화, 데이터셋, 비용 | MVP 검증 후 | `DEFERRED` |
| P2-03 | P2 | Active Learning | 애매한 탐지 샘플 저장·라벨링은 후속 단계 | 데이터 보안, 라벨링 인력, 재학습 재현성 | MVP 검증 후 | `DEFERRED` |
| P0-04 | P0 | 1차 구매 목록 | 고성능 카메라와 하드웨어 가속/안정화 장비를 우선 검토 | Orin 대여 결과, Jetson 상태, 지원 마감일, 견적 | 구매 전 | `PLANNED` |
| P1-05 | P1 | Web Dashboard 범위 | MVP 이후 선택 기능으로 보류 | MVP 진척, 시연 필요성, 개발 시간 | MVP 기능 확정 시 | `PROPOSAL` |
| P0-05 | P0 | baseline 모델·runtime·입력 규격 | legacy 모델 재현 가능성을 먼저 확인하고 불가 시 비교 가능한 대체 baseline 정의 | Nano 호환성, class 정의, license, 고정 입력·threshold | 9월 baseline 복원 전 | `PROPOSAL` |
| P0-06 | P0 | 사건 정답과 controlled scenario | 안전한 모형 소품 기반 시나리오와 event 시작·종료 규칙 정의 | 안전·동의, 반복성, positive/negative 균형 | MVP 확정 전 | `PROPOSAL` |
| P0-07 | P0 | 프로젝트 정량 목표치 | baseline 측정 후 false alarm·event recall·latency 목표 결정 | 표본 규모, baseline 분산, 일정, 실제 Nano 결과 | 제안서 목표 확정 전 | `PROPOSAL` |
| P1-06 | P1 | 사건 증거 범위 | MVP는 metadata+snapshot, clip은 stretch 권장 | 개인정보, 저장공간, 오류 분석 가치 | MVP 확정 시 | `PROPOSAL` |
| P1-07 | P1 | 상태 머신 상태·전이 | `NORMAL/SUSPECTED/ALARM/COOLDOWN` 4-state 후보 | 설명 가능성, 누락 내성, 단위 테스트 가능성 | MVP 확정 시 | `PROPOSAL` |
