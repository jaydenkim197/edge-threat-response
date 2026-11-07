# Open Decisions

<!-- docs-refresh-20261106:begin -->
## 현재 읽는 방법 — 2026-11-07

아래 표는 완료된 실행과 남은 결정을 구분한다. M2 네조건 모두50epoch/37,150update를완료하고같은9조건·7개개발셋·AP/predict/confidence를비교했다([완료·결과](../reports/evaluation/m2-variants-2026-11-07/report.md)). 새3모델의CCTV.25 TP는0/31이고기본M2/960추론만1/31이다. M1·기본M2를T1초기비교기준으로유지하는권장안은PROPOSAL이며새T1학습은아직이다. D*·최종해상도/threshold·앙상블 배포 채택은 미확정이며 T1·실제HOI는 다음 주 촬영 자료 후 진행한다.

실제 촬영 정답, 최종 정량 목표와 threshold, Orin 정식 환경, 제한 자료의 반입 조건이 남아 있다. [현재 마일스톤](project-plan.md), [영문 개요](research-overview-en.md).
<!-- docs-refresh-20261106:end -->

권장안은 확정 전까지 `PROPOSAL`이다. 결정 후 행을 삭제하지 않고 상태와 근거를 갱신하며, `development-log.md`의 해당 기록을 연결한다.

2026-11-06 모델 권장안: 실제완료된RAW4개/공통8모델평가에서 **M1-n을후속주력후보**, 640기준/960조건부추론을권장한다(`PROPOSAL`). M1-s/R1/RF기준선을보존하며n의항상우위·최종D*를선언하지않는다. 다음미결정은M2추가실사recipe의기술검사·목표CCTV train/tuning/final 촬영·Orin M1/960 비용·HOI관계정답이다. 새학습은시작하지않았다. [수치·반례·권장순서](../reports/evaluation/raw-detector-selection-2026-11-06/report.md).

| ID | 우선순위 | 결정 사항 | 현재 권장안 | 선택 기준 / 필요한 증거 | 결정 시점 | 상태 |
|---|---|---|---|---|---|---|
| P0-01 | P0 | Orin inventory와 patch 차이 | 실제39.2.0 pilot 보존, 계획39.2.1과 정식 동결 차이는 별도 결정 | inventory/native CUDA/file/P430 검증 완료; 물리GPIO/정식 resource 조건 남음 | 11/20동결 전 | pilot `VERIFIED`; 정식환경 `PROPOSAL` |
| P0-02 | P0 | 기존 소스의 기준 저장소 | 현재 저장소와 고정된 legacy submodule을 기준으로 사용 | 비밀값·라이선스·재현 환경은 계속 별도 확인 | 완료 | `DECISION` / `IMPLEMENTED` |
| P0-03 | P0 | 11월 필수 기능 | knife·geometry/K-of-N/FSM/metadata/snapshot B0~B3 + 독립 Holding B4·GPIO | B0~B4 코드·합성 연결 및 R1/P430 pilot 검증; real HOI·GPIO·독립평가 필요 | 11/05범위 결정 | 범위 `DECISION`; 코드 `IMPLEMENTED`; 최종평가 `PLANNED` |
| P1-01 | P1 | 상황 인식 범위 | B3 geometry+temporal, B4 learned Holding+같은 temporal/FSM. Tracking/movement는 선택 | 실제 관계 GT·사건 지표·Orin 비용 | 11/05범위 확장 반영 | 범위 `DECISION`; real 효과 `PROPOSAL` |
| P1-02 | P1 | 기준 Jetson 플랫폼 | Orin Nano, Nano는 legacy/선택 비교. 계획JetPack7.2.1/39.2.1과 실제39.2.0 native 구분 | file/P430 CUDA pilot 검증, patch차이는P0-01 | 완료/정식동결 별도 | 기준 `DECISION`; camera pilot `VERIFIED`; GPIO `PLANNED` |
| P1-03 | P1 | 이벤트 전송·대시보드 | 로컬 경보 우선, 위험 이벤트 메타데이터만 서버 전송 | 네트워크 단절 시 동작, 개인정보·저장 정책 | 대시보드 구현 전 | `PROPOSAL` |
| P1-04 | P1 | 영상·개인정보 경계 | 원본 영상 최소 보존, 이벤트 기반 저장, 접근 제어 명시 | 지도교수·기관 정책, 수집 장소·동의 범위 | 실제 수집 전 | `PLANNED` |
| P2-01 | P2 | 멀티카메라·Re-ID | 이번 학기 핵심 범위에서는 제외하고 후속 확장으로 보류 | Orin 성능, 카메라 수, 실험 장소, 일정 | MVP 검증 후 | `DEFERRED` |
| P2-02 | P2 | RGB + IR/Thermal 융합 | 조도 취약성 검증 후 별도 확장 후보로 보류 | 센서 확보, 동기화, 데이터셋, 비용 | MVP 검증 후 | `DEFERRED` |
| P2-03 | P2 | Active Learning | 애매한 탐지 샘플 저장·라벨링은 후속 단계 | 데이터 보안, 라벨링 인력, 재학습 재현성 | MVP 검증 후 | `DEFERRED` |
| P0-04 | P0 | 잔여 실물 준비 | Orin/NVMe/P430 연결은 확인. GPIO 부품·배선 및 설치높이/화각 실측 준비 | 실제 물리 경보·촬영세션·전원/냉각 운영 검증 | 통합 전 | 확보된pilot `VERIFIED`; 잔여 `PLANNED` |
| P1-05 | P1 | Web Dashboard 범위 | MVP 이후 선택 기능으로 보류 | MVP 진척, 시연 필요성, 개발 시간 | MVP 기능 확정 시 | `PROPOSAL` |
| P0-05 | P0 | 최종 detector·입력 | composite person+knife pilot 동작, M1-n 주력후보/640기준/960조건부. Unified 2class는 완전한person주석 있을때만 | 공통개발평가 완료; 목표CCTV tuning/Orin지연·RAM/최종threshold 필요 | 11/20동결 | adapter·pilot `VERIFIED`; D* `PROPOSAL` |
| P0-09 | P0 | 정식 Orin ML runtime | 실제39.2.0/native torch2.14.1+cu132·vision0.29.1+cu132/Ultralytics8.4.152 pilot 보존 | kernel/file/P430/THP후속 검증; TensorRT·무기한운영·재부팅·물리GPIO 미검증 | 정식환경 동결 전 | pilot `VERIFIED`; 정식채택 `PROPOSAL` |
| P0-06 | P0 | 사건 정답과 controlled scenario | person-associated knife event의 수동 annotation, positive/hard-negative 시나리오, distance 필수·lighting 선택 | matching 허용 구간, 모호 frame, 촬영 장소·동의, 반복 횟수 | 촬영 전 | 방법 `DECISION`, 세부 `PROPOSAL` |
| P0-07 | P0 | 프로젝트 정량 목표치 | Orin baseline 측정 후 false alarm·event recall·latency 목표 결정 | 표본 규모, baseline 분산, 일정, 실제 Orin 결과 | pilot/11월 모델 동결 전 | `PROPOSAL` |
| P1-06 | P1 | 사건 증거 범위 | MVP는 metadata+snapshot 1장, clip은 stretch | 개인정보, 저장공간, 오류 분석 가치 | 완료 | `DECISION` |
| P1-07 | P1 | 상태 머신 상태·전이 | `CLEAR/CANDIDATE/CONFIRMED/COOLDOWN`; CONFIRMED 진입당 action 1회, 연속 clear sample 뒤 rearm | rearm sample 수는 baseline 후 | 완료 | `DECISION`; PC core `VERIFIED` |
| P0-08 | P0 | tuning/final 분리 | 같은녹화·동시CCTV/스마트폰은동일group, 최종세션은모델/threshold선택에사용하지않음 | 실제촬영세션·규모·수동GT 필요 | 촬영전/11월동결 | 방법 `DECISION`; 실제분리 `PLANNED` |
| P1-08 | P1 | Stretch 우선순위 | TensorRT/FP16 → legacy Nano cross-device 비교 → Tracking → Dashboard → Event clip → 추가 class → enclosure/PCB | Orin이 기준 플랫폼으로 변경되어 기존 Orin benchmark 항목을 기준 검증으로 승격 | 완료 | `DECISION` |
| P0-10 | P0 | 후속 dataset recipe | RAW R1/H1/M1-n/s 완료. Q1별도학습후순위/88정제M2흡수·새실사 제한조사·T1우선 권장. L0는 팀원 별도 | 전체 source/보호그룹(US83포함)·bbox/권리·recipe/hash·새ID지원 필요 | M2/T1 준비 전 | RAW실행 `VERIFIED`; 새recipe `PROPOSAL` |
| P0-11 | P0 | ambiguous annotation rule | 모형 knife·reflection·printed image·극소/가림 객체를 sample review로 결정 | detector claim boundary, 일관성, 팀 annotation 합의 | 직접 수집·재라벨링 전 | `PROPOSAL` |
| P0-12 | P0 | Ultralytics 사용·배포 라이선스 | 저장소 전체 라이선스를 자동 지정하지 않고, 공개 학술 AGPL-3.0 경로와 다른 배포 경로를 모델/runtime 채택 전에 명시적으로 선택 | 공개 범위, model weight·학습 script 공개 여부, 포트폴리오·후속 상용 활용 | Ultralytics dependency·model을 배포하기 전 | `PLANNED` |
| P1-09 | P1 | 검수 완료분의 개발용 예비 학습 | 2026-10-26 사용자가 SOHAS 정상183개만의 개발용 학습을 승인. Review-overlay pixel-edge 변환·보수적 filename/dHash proxy group split·YOLO26n development defaults 사용. 공식 R1/H1·최종 평가·원 좌표/실제 세션 확인·재배포 승인은 아님 | source/review/hash 일치·모든 bbox·negative 근거·proxy group/hash 분할 교차 검사, bound 개발 범위 승인과 GPU preflight | 개발용 한정 승인 | `DECISION`(사용자 승인); 실행 증거 별도 |
| P2-04 | P2 | Holoscan 5.0 도입 효과 후속 연구 | 기존 Python/PyTorch FP32(A), 기존 구조+TensorRT FP16(B), Holoscan 5.0+동일 TensorRT FP16 엔진(C)을 분리 비교한다. B↔C에서 Holoscan 통합의 추가 효과를 평가하며 MVP·B0~B3 핵심 실험은 변경하지 않는다. | 실제 카메라와 동등한 입력·frame/drop 정책, 동일 Orin/전력/모델/엔진, 단계별 지연(mean/p95)/FPS/프레임 누락/CPU·GPU/RAM·RSS 증가 측정 및 canonical detections/event 일치성; L4T39.2.0 대 공식 지원 환경 차이와 TensorRT 의존성·8GB 제약 확인. TensorRT-only 실측에서 추가 병목이 확인될 때 착수 판단 | MVP·실제 사건 평가 완료 후 | 후속 연구 방향 `PROPOSAL`; Holoscan 설치·구현·성능은 미검증 (`PROPOSAL`) |
| P1-10 | P1 | 11월 YOLO·HOI 범위 | 11/30마감, 실제 Holding 모델·B0~B4 독립 비교·Orin/GPIO 통합. 팀원 고정배정 없음 | RAW4개 완료/합성HOI·P430 pilot과 실제final 구분 | 11/05결정 | 범위 `DECISION`; real HOI/final `PLANNED` |
| P1-11 | P1 | YOLO 해상도·HOI ROI | 640기준,640-trained weight의960 추론 비교 완료. 960재학습/운영채택·1280은조건부,HOI224/256후보 | 목표CCTV 이득과 Orin 비용. 960추론을960학습으로표현하지않음 | 11/20동결 | 개발추론 `VERIFIED`; 운영해상도 `PROPOSAL` |
| P1-12 | P1 | 신규 source·HOI label | SOHAS/Dangerous/Catargiu RAW M1 완료, OI별도train·추가실사/M2후보. US83은개발평가보호/합성별도/ACF미확보 | 2질문이미지검수≠Holding GT. 실제pair/event수동정답·동시촬영group 분리 | 촬영/반입 전 | 현재source역할 `DECISION`; 새채택 `PROPOSAL` |
| P1-13 | P1 | Reolink P430 | 인증/main·sub수신·Orin R1/B3 각300frame·모니터표시 검증. RTSP는원본recorder가아님 | 원본연속clip/시간축·3m설치/거리·동의·사건GT·GPIO 남음 | 촬영/통합 전 | 기종 `DECISION`; pilot `VERIFIED`; 정식촬영 `PLANNED` |
