# Master Project Plan

<!-- s1-synthetic-20261108:begin -->
## S1 학습·공통 평가 완료 — 2026-11-08

**S1의 50 epoch·37,700 update와 동일 7개 개발셋 비교를 완료했다 `VERIFIED`.** PC13에서 20:21 KST에 학습, 20:23에 평가가 종료됐다. M2 실사 11,884장에 합성 176장을 추가한 YOLO26n·640 실험이다. 기존 val/test와 평가 입력은 유지했다.

S1은 M2 대비 SOHAS test Recall 75→85%, DaSCI 56.7→68.0%, 합성 CCTV 12.7→20.6%지만 Open Images는 74.4→69.2%다. **실제 CCTV 확대83장에서는 세 모델 모두 0/31 검출**이다. S1의 CCTV FP4는 M2의7보다 적고 M1의2보다 많다. [S1 대 M1·M2 결과](../reports/evaluation/s1-synthetic-2026-11-08/report.md).

최종 D*는 미확정이다. 다음 주 실제 촬영, 세션별 train/tuning/final 분리, bbox·Holding·사건 GT, T1·HOI를 우선한다. Orin/GPIO와 독립 B0~B4 평가는 남아 있다.
<!-- s1-synthetic-20261108:end -->

<!-- docs-refresh-20261106:begin -->
## 현재 기준 — 2026-11-07

**현재 마일스톤은 공개 데이터 detector 비교와 P430/Orin 시범 연동을 마치고, 목표 CCTV 데이터·실제 HOI 학습·최종 평가를 준비하는 단계다.**

| 구분 | 현재 상태 |
|---|---|
| 일정 | 11/20 모델·설정 동결, 11/25~27 독립 B0~B4 평가, 11/30 개발·평가 마감 `DECISION` |
| RAW detector | 4종 모두 50 epoch·35,600 update 완료. 8개 모델 조건을 같은 6개 개발셋에서 비교 `VERIFIED` ([결과](../reports/evaluation/raw-detector-selection-2026-11-06/report.md)) |
| 다음 학습 | M2 기본·960·증강완화·seed2 **네 모델 모두50epoch/37,150update 완료** `VERIFIED`. PC13의동일9조건×7개개발셋/AP·predict·confidence 분석완료. 새변형CCTV는0/31, 기존M2/960추론은1/31. D*미확정이며촬영후T1·실제HOI를우선한다. [공통 평가·confidence 분석](../reports/evaluation/m2-variants-2026-11-07/report.md) |
| 실기기 | 실제 L4T 39.2.0에서 P430 main/sub → R1/B3를 각각 300 frame 실행하고 snapshot·mock 경보·화면 표시 확인 `VERIFIED` ([증거](../reports/runtime/p430-yolo26n-2026-11-05/report.md)). 계획 버전 39.2.1과의 차이는 별도 관리 |
| HOI/B4 | 코드와 합성 자료의 CPU·CUDA 연결 `VERIFIED`. 실제 Holding 정답·학습·성능 검증은 `PLANNED` ([규격](hoi-annotation-contract.md)) |
| GPU 자원 | PC11/12/13/14 full run 완료·artifact SHA 검증/PC13수집·공통평가완료. 독립단일GPU이며DDP검증은아님. [공통 평가·confidence 분석](../reports/evaluation/m2-variants-2026-11-07/report.md) |
| 공개 후보 감사 | 11/07 CCTV V3: 50장 주석·47장 이미지 검사, 7장 사람 검수 후보 준비. 운영·학습 미반입. 전체 주력 채택은 보류 권장 `PROPOSAL` ([근거](../reports/datasets/roboflow-cctv-v3-2026-11-07/report.md)) |
| 남은 필수 작업 | 자체 촬영과 사건·관계 정답, 새 모델의 Orin 측정, 물리 GPIO, 독립 사건 평가, 장시간 운용·장애 복구 검증 |

신규 제한 자료는 제공 조건과 비공개 접근 환경을 준비한 뒤 반입한다([처리 원칙](research-overview-en.md)). 아래 과거 진행 기록과 초기 일정은 현재 기준과 구분해 보존한다.
<!-- docs-refresh-20261106:end -->

<details>
<summary>2026-11-05~06 진행·권장안 기록 (위 현재 요약을 우선)</summary>

<!-- cctv-candidate-check-20261106:begin -->
## 2026-11-06 — 일정 우선의 후속 학습 권장안 조정

최신권장안은 **별도Q1 full run후순위 → 88장제외를M2(n/640)1개후보에반영 → 실제CCTV자료확보즉시T1·HOI병행**이다(`PROPOSAL`). 앞선Q1 독립학습우선권장안은현일정에서이권장안으로대체한다. 사용자확정/학습실행을뜻하지않는다. 신규Roboflow CCTV V3/499 후보는각최대50장표본의제한조사를권장하며확보대기를M2/T1선행gate로추가하지않는다. Catargiu칼포함자료는이미전체조사/M1에사용돼26,528장을신규자료로세지않는다. Simuletic은별도합성,NTU Fights/VIRAT은현11월필수학습범위에추가하지않는다. 11/20모델동결·11/30마감은유지한다. [원출처대조·현재확보분·권장범위](../reports/datasets/cctv-candidate-check-2026-11-06/report.md).
<!-- cctv-candidate-check-20261106:end -->

<!-- reviewed-next-training-20261106:begin -->
## 2026-11-06 — 검수 대조·확대 CCTV 진단·현재 마일스톤

현재 위치는 **공개 데이터 baseline 비교 완료 → 정제·목표 CCTV 적응 준비**다. 검수 snapshot은 3,625장 중 완료2,673/정상2,527이며, 정상1,805장은 이미 M1 train과 동일 라벨이다. 기존 train88장은 문제·불확실 판정이므로 **Q1-clean-n/640, train11,290장**을 다음 공개 데이터 실험 후보로 권장한다(`PROPOSAL`). 신규 실사39장은 별도 반입 후보이며 전이적 그룹 검사가 남아 있다. Q1과 동시에 추가하고 순수 정제 효과로 해석하지 않는다. 기존 포괄적 M2 권장안의 구체화이며 새 학습은 시작하지 않았다.

확대 US CCTV83장/31knife GT의 M1-n/s640 TP는0/31, 같은n weight960은1/31이었다. 따라서 가장 중요한 후속 학습은 **독립 train 세션의 실제 CCTV T1 적응**이다. 11/9~12 촬영·bbox/Holding GT, 11/13~16 YOLO/HOI 학습, 11/20 동결, 11/25~27 독립 B0~B4 평가, 11/30 마감은 유지한다. 사용자는 실제 촬영 영상·Holding 관계 라벨이 아직 없다고 확인했다. HOI 실제 학습·물리GPIO·사건 정확도·D*는 미완료다. P430/기존R1 Orin 실시간 연결 검증을 새 모델 정확도 검증으로 승격하지 않는다. [집계·권장 recipe·마일스톤](../reports/datasets/reviewed-next-training-2026-11-06/report.md).
<!-- reviewed-next-training-20261106:end -->

## 2026-11-06 — RAW 학습 완료와 후속 권장안

네 RAW 모델의50epoch·실제35,600 optimizer updates가 모두 완료됐고, 8개 모델×동일6개 개발셋의 AP/predict 비교 및 M1-n/s의960 추론 진단을 확인했다. 결과와 다음 모델/학습 권장안은 [공통 비교 보고서](../reports/evaluation/raw-detector-selection-2026-11-06/report.md)에 있다.

**후속 주력 후보는 YOLO26n/M1 실사 혼합(`PROPOSAL`)**이다. 640 기준선을 유지하고 960은 조건부 추론 후보로 둔다. 다음 학습은 같은n·예산에서 공개 실사 보강M2와 목표CCTV 적응을 분리해 비교하는 방향을 권장한다. 새 학습은 아직 시작하지 않았다. D* 동결과 실제 CCTV/사건 정확도는 미확정이며, 공개 개발셋의 개선을 독립 final 성능으로 승격하지 않는다. 현재 Orin의 R1 시연weight를 새 M1-n으로 교체한 것은 아니다.

## 2026-11-05 구현·실행 착수

- 검수 완료를 기다리지 않는 원본 주석 `RAW-*` 예비 학습 경로를 별도로 구현했다. 사람 검수 합격·최종 평가 승인을 뜻하지 않는다. 무결성·클래스 매핑·중복/보호 그룹·공통 split·동일 update 예산은 유지한다.
- PC13에서 SOHAS/Dangerous Items/Catargiu **14,224장**을 준비했다. 기존 공개 평가와 연결된 proxy group 및 exact duplicate를 제외했고, trainer가 복구/누락할 JPEG8장은 원본을 보존한 채 새 학습 사본에서 제외했다. R1-n→H1-n→M1-n→M1-s의 순차50epoch queue를 시작했다. 결과·D* 채택은 아직 미확정이다. [실행 규격](raw-source-training.md).
- HOI G/VG 학습·checkpoint·점수 sidecar·B4 replay/평가·영상 snapshot 연결을 가상 자료 PC 및 Orin CUDA에서 확인했다. PC13 checkpoint의 Orin strict load/CUDA 추론과 전체183개 테스트도 통과했다. 실제 Holding 정답과 정확도는 아직 없다. [검증 범위](../reports/runtime/hoi-b4-integration-2026-11-05/report.md). 라벨링 화면은 사이트 담당 채팅에 위임하고 [교환 규격](hoi-annotation-contract.md)을 사용한다.
- Reolink P430과 Orin의 동일LAN에서 인증·main3840×2160/sub640×360 수신과 각각YOLO26n/B3 300frame 통합을 확인했다. 신규RAW-R1-n은 임시 후보이며 최종D*는 미확정이다. Orin 모니터 실시간 박스 표시도 사용자 확인을 받았다. [간단 연결 기록](cctv-local-network-setup.md), [실제 진단·실행](p430-camera-setup.md). 물리GPIO·WAN 제거/자동 복구·새 독립 촬영/정확도는 아직 미검증이다.
- 기존 검수 사이트 데이터/DB/배정은 변경하지 않는다. 실제 추가 source 확보는 현재 queue 입력을 변경하지 않고 후속 recipe로 관리한다. 아래 11월 일정은 유지한다.

</details>

상태: 프로젝트 방향·일정·MVP 연구 범위는 `DECISION`, 정량 목표치와 파라미터는 `PROPOSAL`

이 문서는 프로젝트의 목적, 범위, 일정, 성공 조건을 정의하는 최상위 기준이다. 기술 구조는 `architecture.md`, 미확정 선택은 `open-decisions.md`, 실제 변경은 `development-log.md`, 검증 결과는 `verification.md`에서 관리한다.

## 2026-11-05 — 승인된 11월 YOLO·HOI 병렬 개발 및 평가계획

**결정:** YOLO 개선 + 독립 HOI 학습 + B0~B4 비교 + Orin Nano 실기기 통합·평가를 **2026-11-30까지 완료 목표**로 수행한다. 12월 초는 과제 제출물·발표 정리. 과거 10월31일 MVP 동결 목표는 역사 기록으로 유지한다. 새로운 병렬 개발은 별도의 실험 버전이다. 계획 기한은 성공·검증을 의미하지 않는다.

### 연구별 범위 및 검증

| 트랙 | 필수 작업 | 완료 증거 |
|---|---|---|
| A — YOLO | 기존 YOLO26n(D0) 대비 고유·검수 실사 혼합 데이터 효과와 YOLO26n/s 구조 효과를 **분리** 평가. 작은 칼과 실제 CCTV 일반화 우선 | source/split/config/checkpoint hashes, AP50/AP50-95, small-knife recall, hard-negative FP, Orin 추론 지연 |
| B — HOI | YOLO person·knife의 pair/union crop+geometry를 입력받는 별도 학습 모델. 1차 Holding/Not Holding, uncertain은 보류. Geometry MLP(B4-G)와 사전학습 MobileNetV3-Small+MLP(B4-VG) 비교 | pair-level P/R/F1·혼동행렬, GT-box vs predicted-box 진단, 모델·라벨 출처, Orin 추가 비용 |
| C — 판단 비교 | 동일 detector D*의 **동일 detection JSONL**로 B0~B4 실행. B3=Spatial+Temporal, B4=HOI+동일 Temporal/FSM. B5 결합은 여유 시 선택 | 독립 촬영 세션의 event P/R/F1·False Alerts/hour·판단 지연. Detector D0→D* 효과와 B3→B4 효과는 별도 비교 |
| D — 통합 | 실제 CCTV→YOLO→B3/B4→FSM→GPIO·metadata·snapshot, Edge 성능 및 장애 검증 | 카메라/물리 경보 동작 증거, FPS·p95·drop/queue·CPU/GPU/RAM·온도·실행 환경 기록 |

### 주차별 일정

| 기간 | 모델·데이터 개발 | 통합·실험 / 완료 기준 |
|---|---|---|
| **11/05–11/08** | SOHAS+그 밖의 실사 후보 검수 상태·source 역할 결정, HOI Holding 관계 라벨/네트워크 설계, 실험 프로토콜 동결 준비 | P430 RTSP·Orin pilot은11/05 검증. 원본 연속 녹화·최종 GT는 별도 준비. train/tuning/final session 경계와 안전 촬영·동의 준비 |
| **11/09–11/12** | CCTV/스마트폰 train 촬영 및 YOLO bbox·HOI pair GT 라벨, 중복·source audit, 학습용 manifest 승인 | 약3m 고각 CCTV/정면·측면 휴대폰, 3~5명·실내2곳 이상, Near/Medium/Far·Normal/Low-light. **30~60클립·300~600프레임은 첫 pilot 목표량**, 세션 독립 수 보장은 아님. final은 별도 촬영 |
| **11/13–11/16** | 승인 실사 D0 vs YOLO26n 개선 및 동일 데이터의 YOLO26s, HOI B4-G/B4-VG 1차 학습. PC13 RTX3060에서 GPU 학습은 **순차 예약** | 양 트랙 각각 학습 완료 checkpoint 최소 1개, validation 비교·오류 사례·원시 학습 로그 |
| **11/17–11/20** | 작은 칼 FN/FP·HOI hard-negative 오류 분석, 데이터/증강 보완, 640 vs 960·HOI union crop 224/256 조건부 비교, seed 반복 여유 시 수행 | **11/20 D*와 B4 weight·threshold·config·평가 세션 동결**. 1280 및 ResNet18은 옵션 |
| **11/21–11/24** | 선택 모델 Orin 이식/전처리·후처리 검증 | 실제 CCTV RTSP 또는 저장 영상·GPIO·snapshot 통합 smoke, B0~B4 실행 경로·latency·dropping·메모리 실측. TensorRT는 병목·호환성 확인 후 조건부 |
| **11/25–11/27** | 동결 모델에 대해 새로운 독립 CCTV final session의 bbox/HOI pair/event GT 평가 | 동일 영상·D* JSONL·K/N·FSM 기준의 B0~B4 1회 최종 평가, Event F1·False Alerts/hour·p95·FP/FN 분석. 최종 test로 튜닝 금지 |
| **11/28–11/30** | 코드/weight/config 동결, 오류 해석·성능표·그래프·재현 설정 마무리 | YOLO·HOI·B0~B4·Orin 실측 최종 보고 및 원시 증거 정리. 새 기능 확장 중단 |

### 데이터셋 사용 범위 (SOHAS 단독 학습 아님)

- **실사 기본:** SOHAS R1/H1; 별도 실사 혼합 M1에는 Dangerous Items, Catargiu, Open Images V7의 *기존 평가에서 분리된 학습용 자료*, 중복·권리·검수 통과 legacy/DaSCI 고유분을 후보로 삼는다. 후보 전체를 무조건 합치지는 않는다.
- **목표 도메인 적응:** 직접 CCTV/스마트폰 촬영의 독립 train session(T1)을 사용하고 별도 독립 final session은 보호한다. 기존 11/04 평가 263장은 개발 확인용으로 공개됐으며 최종 unseen test가 아니다.
- **보조/외부:** Simuletic CCTV/ATM은 synthetic augmentation을 실사 baseline과 따로 비교. US Mock Attack은 외부 CCTV 평가 후보. ACF는 원본 미확보로 보류. HICO-DET/100DOH/Hands23은 HOI 관계/손-물체 pretrained 후보; YouTube는 이용 조건 확인 전 참고용.
- **학술 사용:** 별도 법률 보고서는 선행하지 않되 연구 목적만으로 데이터 저작권·라이선스·출처/재배포 제한·촬영 동의가 자동 면제되지는 않는다. source/version/허용범위/중복/annotation을 간단히 확인하고 그 범위 안에서만 학습한다. 원본 민감 영상·이미지·체크포인트를 공개 Git에 업로드하지 않는다.

### 모델·자원·추가 연구 경계

- **해상도:** YOLO640은 Orin 파일입력 **실측 기준선**, 960은 우선 비교 후보, 1280은 960의 이득과 실제 Orin 메모리/지연 여유가 확인된 경우에만. HOI는 4K 전체 프레임이 아닌 원본 영상의 사람-칼 union crop224/256을 후보로 사용. 픽셀수 증가(960=2.25배,1280=4배)가 FPS 저하율과 동일하다고 단정하지 않는다.
- **Orin 실측:** Jetson Orin Nano Super 약8GB/25W의 이전 640 파일 반복 시험 THP-off 처리율12.1496fps는 **실제 CCTV FPS가 아니다**. HOI 추가 후 end-to-end FPS/p95/프레임 누락·대기열·RAM을 재측정해야 한다.
- **분담:** 특정 팀원에게 역할을 사전 고정 배정하지 않는다. 팀은 공동 작업 큐를 사용하고 각 학습 run/검수 기록의 실제 담당 정보만 증거에 기록한다.
- **11월 이외:** Holoscan 5.0은 기존 P2-04 **후속 연구로 유지**한다. Using/Video HOI, B5 융합, 1280·ResNet 확장, Nano 비교 등은 11월 필수 결과를 해치지 않을 때만 검토한다.

## 1. Project Identity

- 프로젝트명: 상황 인지형 Edge AI 흉기 위협 대응 시스템
- 수행 기간: 2026-09-01 ~ 2026-12-11
- 신규 시스템 기준 플랫폼: Jetson Orin Nano Developer Kit
- 계획 소프트웨어 기준: JetPack 7.2.1 / Jetson Linux 39.2.1; 실제 검증은 L4T 39.2.0 native, 정식 환경 동결은 별도
- legacy 기준: Jetson Nano 4GB와 2025-2 MIDAS 보존 환경
- 기준 저장소: `jaydenkim197/edge-threat-response`
- 모델·설정 동결 목표: 2026-11-20
- 개발·평가 마감: 2026-11-30 (과거 2026-10-31 목표는 `SUPERSEDED`)

2026-10-04 당시 사용자 확인(역사 기록): **Orin Nano는 보유 중**이며 원격 접속은 설정하지 않았다. 카메라·GPIO 기기는 아직 확보하지 않았다. 이는 `USER_REPORTED` 장비 준비 상태이며 실제 SKU/RAM·저장장치·부팅 OS/JetPack·firmware·CUDA 동작은 원격/실물 inventory 전까지 미검증이다. 다음 실물 gate는 수령 대기가 아니라 부팅 상태 확인·원격 접속 설정이고, 주변장치 확보 전에도 runtime/image GPU smoke는 접속 후 진행할 수 있다.

2026-10-27 실측 갱신: SSH key 접속, device-tree Orin Nano Super/p3767-0005·약8GB·NVMe·UEFI39.2.0·25W를 확인했다. 실제 L4T39.2.0/CUDA13.2.2의 격리 native 환경에서 실제 GPU kernel과 새 모델의53frame 파일입력/B0~B3/metadata/snapshot/mock alarm을 검증했다. **계획39.2.1과 실제39.2.0은 다르며 기준 변경/OS 업데이트를 승인한 것이 아니다.** 카메라/GPIO·실제 사건 성능·장시간/재부팅은 미검증이다. [실기기 증거](../reports/runtime/orin-native-smoke-2026-10-27/report.md).

주변장치 전 운용 점검: local weight/output 검증·완료 frame 로그 flush·사진 실패 집계를 보완했다. 실제 Orin의 별도 통신 격리 공간에서도 같은 파일의 추론/B0~B3/사진이 통과했으며 host SSH는 유지했다. 제한 시간 반복의 자원 측정과 해석은 [운용 준비 기록](../reports/runtime/orin-readiness-2026-10-27/report.md)을 따른다. 이 작업은 실제 사건 benchmark나 장시간·재부팅 검증, MVP 범위 확대가 아니다.

2026-11-02 메모리 후속: 약216MiB 증가를 THP 자동 병합으로 재현·분리하고, Orin 파일 CLI/profile worker의 process-only THP 정책으로600초 추가 증가를211.664→11.453MiB로 줄였다. 공통7,291frame 탐지·판단과 실제53frame CLI/B0~B3/snapshot 회귀를 통과했다. [실측과 처리율 trade-off](../reports/runtime/orin-memory-2026-11-02/report.md). 실제 카메라/GPIO·무기한 메모리 안정성·정식 runtime 채택은 승격하지 않는다.

### Target deployment and data-domain assumption

- camera는 Reolink P430으로 확인됐으며 실제 설치 화각·거리 실측은 남아 있다. dataset 검수와 controlled scenario는 약 3 m 높이의 고정형 실내 CCTV가 복도·출입구·공용공간을 비스듬히 보는 환경을 기준으로 한다.
- 작은/먼 knife, person co-occurrence, 손·팔 가림과 복잡한 배경을 우선한다. 제품사진·정면 close-up은 보조 appearance data일 수 있으나 target-domain 성능의 근거가 아니다.
- 공개 dataset은 source·license·annotation·duplicate/session leakage audit을 통과한 뒤에만 import한다. source별 학습·외부평가·synthetic 보조 역할은 [Dataset Source Strategy](dataset-source-strategy.md)를 따른다.

### 역사적 맥락

이 프로젝트는 2025-2 MIDAS에서 진행한 Jetson Nano 기반 흉기 탐지·GPIO 경보 프로토타입을 발전시킨다. 당시 자료에는 카메라 입력, YOLO 기반 사람·흉기 탐지, Jetson 추론, LED·부저 경보, WebSocket UI가 제시되어 있다.

기존 발표자료의 Precision 96.2%, Recall 85.1%, mAP50 93.7%는 평가 분할·환경·명령이 현재 확보되지 않아 `UNVERIFIED`이다. 이번 프로젝트의 공식 결과로 사용하지 않고, 재현 가능한 baseline을 새로 측정한다.

### 최종 목표

단일 프레임에서 흉기가 탐지되면 곧바로 경보하는 구조를, 선택된 공간·시간 문맥을 이용해 사건 수준의 위협을 판단하고 엣지 장치에서 경보·기록·측정할 수 있는 구조로 발전시킨다. 11월20일까지 모델·설정을 동결하고 11월25~27일 독립 사건 평가, 11월30일 개발·평가 마감, 12월 초 제출물·발표 정리로 연결한다.

## 2. Problem Definition

현재 자료로 확인된 한계는 다음과 같다.

- 기존 보존 코드는 single-frame weapon detection과 즉시 GPIO 경보 중심이다.
- 기존 정량 수치는 재현 조건이 부족하여 현재 기준 성능을 증명하지 못한다.
- 사건 평가기·annotation 계약은 구현됐지만 실제 독립 촬영의 event/pair 정답과 최종 성능은 아직 없다.
- Orin SKU/NVMe/native 환경과 P430 pilot은 확인했다. 물리 GPIO·정식 모델/환경 동결·지속 운용/독립 사건 성능은 미검증이다.
- 상황 문맥을 추가했을 때 실제로 오경보가 줄어드는지는 아직 가설이다.

따라서 이 프로젝트는 단순 모델 교체나 mAP 상승보다, 동일 입력에서 baseline과 context-aware 판단을 비교할 수 있는 시스템·실험 체계를 만드는 데 초점을 둔다.

## 3. Core Research and Engineering Questions

| ID | 질문 | 상태 |
|---|---|---|
| RQ1 | 경량 공간·시간 event-confirmation 계층이 single-frame alert보다 사건 수준 오경보를 줄이는가? | `DECISION` |
| RQ2 | 오경보 감소 과정에서 person-associated knife event recall과 경보 지연은 어떻게 변하는가? | `DECISION` |
| RQ3 | spatial association과 temporal confirmation은 각각 어떤 기여를 하는가? | `DECISION` |
| RQ4 | 독립 Holding 모델 B4가 geometry 기반 B3 대비 사건 recall·오경보·지연에 어떤 차이를 만드는가? | `DECISION` |
| EQ1 | Jetson Orin Nano에서 외부 인터넷 없이 탐지·판단·경보·기록을 반복 실행할 수 있는가? | `DECISION` |
| EQ2 | Orin Nano의 자원·열·지연 제약 안에서 재현 가능한 실행 조건은 무엇인가? | `PLANNED` |

구체 가설·임계값·정량 목표는 baseline, development/tuning set, holdout test 설계 후 기록한다.

## 4. Scope

### In Scope

- 2025 MIDAS baseline의 출처·환경·동작을 재구성하고 재측정
- Jetson Orin Nano 로컬 카메라 입력, 탐지, GPIO 경보
- baseline과 proposed 판단을 같은 입력으로 비교하는 실행 경로
- 사건 단위 평가, 성능·자원 측정, 재현 설정과 증거 기록
- 안전한 모형 소품 또는 적법하게 사용할 수 있는 비민감 입력을 이용한 통제 시나리오

### 11월 필수 범위 — B0~B4 (`DECISION`)

| 기능 | 목적·가치 | 난이도 / 의존성 | 논문 기여 | 일정 위험 | 상태 |
|---|---|---|---|---|---|
| Person/Knife detection | 공통 인지 입력과 baseline 제공 | 중 / 모델·Jetson 환경 | 비교 기반 | 구형 stack 호환성 | adapter·신규 개발 모델의 PC 영상 통합 `VERIFIED`; R1 camera/Orin pilot `VERIFIED`; 최종 D* `PROPOSAL` |
| Single-frame baseline | 기존 방식의 재현 가능한 비교군 | 중 / 탐지·GPIO | 필수 비교군 | 원본 환경 불명확 | B0 replay `IMPLEMENTED`/PC `VERIFIED`; 실기기 비교 `PLANNED` |
| Person–knife geometry association | nearest person과 확장 bbox로 공간 문맥 제공; 정규화 거리는 진단값 | 중 / bounding box 계약 | context 효과 비교 | 관계 정의 오류 | core `IMPLEMENTED` / PC `VERIFIED` |
| K-of-N temporal confirmation | 순간 오탐·누락에 대한 시간 문맥 | 중 / 프레임 시간·누락 처리 | context 효과 비교 | 임계값 과적합 | core `IMPLEMENTED` / PC `VERIFIED` |
| CLEAR/CANDIDATE/CONFIRMED/COOLDOWN | 판단과 action을 분리 | 중 / context 신호 | 설명·재현 가능성 | 상태 조건 복잡화 | core `IMPLEMENTED` / PC `VERIFIED` |
| Holding HOI / B4 | 공간 규칙과 학습 관계 판단 비교 | 중 / 실제 pair GT | B3 대비 관계 특징 기여 | 라벨·가림·일정 | G/VG·B4 구현/합성 CPU·CUDA `VERIFIED`; 실제 학습·성능 `PLANNED` |
| GPIO LED/Buzzer | 엣지 대응 데모 | 하 / Jetson GPIO | 공학 통합 | 하드웨어 상태 | `PLANNED` |
| Event metadata + snapshot | 사건 근거와 오류 분석 | 중 / 저장 정책 | 실험 증거 | 개인정보·용량 | PC·Orin file/P430 snapshot `VERIFIED`; 보존 정책·실제 사건 평가 `PLANNED` |
| B0~B4 benchmark/ablation | baseline·spatial·temporal 기여 비교 | 중 / 시나리오·정답 | 핵심 실험 기반 | 뒤늦은 평가 설계 | policy/replay/B4 연결 `IMPLEMENTED`·합성 `VERIFIED`; 본 실험 `PLANNED` |
| FPS·latency·RAM·temperature 기록 | 엣지 실행 가능성 평가 | 중 / 측정 도구 | 성능·제약 분석 | 측정 방법 차이 | `DECISION` |

세부 operational definition, scenario, ablation과 제외 범위는 `mvp-research-specification.md`를 따른다. model·runtime·threshold·K/N·정량 목표는 baseline 이후 결정한다.

### Stretch Goals

- event pre/post clip
- object tracking과 track ID 기반 연속성
- movement/approaching 분석 및 복합 threat score
- TensorRT/FP16 최적화
- 후속 연구 후보(`PROPOSAL`): NVIDIA Holoscan 5.0 기반 실시간 영상·AI 파이프라인을 기존 Python 및 TensorRT-only 경로와 비교. 동일 모델/입력/장비에서 GPU 데이터 이동·프레임 적체·end-to-end 지연과 자원 사용의 차이를 검증하며, 기본 B0~B3 연구와 분리한다. 구체 gate는 [P2-04](open-decisions.md)를 따른다.
- 일정과 장비 상태가 허용할 경우 legacy Nano와 Orin Nano의 동일 workload 비교
- 선택적 로컬 dashboard

### Deferred / Out of Scope for MVP

- cloud 상시 전송, mobile app
- multi-camera, Re-ID, thermal/IR, pose 또는 대형 행동 인식 모델
- active learning과 대규모 신규 데이터셋 학습
- enclosure·PCB·별도 가속기 설계

확장 기능은 핵심 MVP가 실기기에서 통합·반복 검증된 뒤에만 승격한다.

## 5. MVP Scope-change Rules

MVP 범위는 [MVP Research Specification](mvp-research-specification.md)에 확정돼 있다. 기능을 승격하거나 범위를 변경할 때는 아래 조건을 다시 확인한다.

1. 2026-11-20 모델·설정 동결과 11월30일 개발·평가 마감을 지킬 수 있다.
2. 기존 single-frame alert와 구조적 차이가 명확하다.
3. 최종 데모에서 판단 이유를 설명할 수 있다.
4. 동일 입력과 정답 기준으로 정량 평가할 수 있다.
5. baseline 대 proposed 또는 ablation 실험으로 논문에 연결된다.
6. 실기기 입고 전에도 공통 판단 로직과 평가 경로를 PC에서 구현·검증할 수 있다.
7. 구현뿐 아니라 오류 분석과 반복 실행까지 남은 인력·시간으로 완료 가능하다.

범위가 실제로 바뀌면 `open-decisions.md`의 관련 항목, 변경 이유·제외 범위·완료 조건과 개발 로그를 함께 갱신한다.

## 6. Definition of Done

기능은 아래 여섯 조건을 모두 만족해야 MVP 완료로 인정한다.

```text
IMPLEMENTED
+ INTEGRATED
+ JETSON VERIFIED
+ REPEATABLE
+ BENCHMARKABLE
+ EVIDENCE RECORDED
```

11월 모델 동결·통합·최종 평가의 완료 판단 항목은 다음과 같다. 기능별 operational definition은 MVP Research Specification을 따른다.

- baseline과 proposed를 같은 버전·입력·설정으로 실행할 수 있다.
- 카메라→탐지→판단→GPIO/기록 전체 경로가 Orin Nano에서 작동한다.
- 외부 인터넷 없이 핵심 경로가 유지된다. RTSP 카메라와 Orin 사이의 로컬 네트워크는 필요하다.
- 설정, 모델 버전, threshold, 실행 명령이 기록된다.
- 사건 정답과 지표 산출 절차가 정의된다.
- 반복 실행 결과와 실패 사례의 증거 위치가 남는다.
- FPS, inference latency, end-to-end alert latency를 측정할 수 있다.
- 가능한 범위에서 RAM과 temperature를 같은 방법으로 기록한다.

## 7. Evaluation Strategy

### 비교 구조

```text
B0: current-frame knife evidence → shared state machine → alarm
B1/B2/B3: temporal / geometry / both → shared state machine → alarm
B4: learned Holding + same temporal policy → shared state machine → alarm
```

B0~B4는 동일 영상·해상도·detector·confidence threshold·장비와 공통 FSM에서 비교한다. B0는 모든 positive frame마다 새 경보를 생성한다는 뜻이 아니다. B4 관계 모델·threshold는 별도 기록하며, context 이외의 조건이 달라지면 별도 실험으로 분리한다.

### 후보 지표

| 범주 | 우선 지표 | 비고 |
|---|---|---|
| Detection | Precision, Recall, F1, 가능 시 mAP | 데이터 분할과 confidence/IoU 기록 |
| Threat/Event | event precision, event recall, F1, false alarms, missed events | 사건 경계와 정답 규칙 선행 |
| Response | detection-to-alert 및 event-start-to-alert latency | 시작점 정의 필수 |
| Edge | FPS, inference latency, end-to-end latency, RAM, temperature | 전원 모드·해상도·runtime 고정 |
| Stability | 연속 실행 시간, 카메라 복구, 네트워크 단절, 저장 실패 | 실기기 fault test |

전력은 신뢰 가능한 측정 장비·방법이 확보될 때만 포함한다. 기존 발표 수치는 `UNVERIFIED`, 새로 설정하는 수치는 `TARGET`, 실제 측정과 검토가 끝난 값만 `MEASURED`로 표기한다.

오경보 30% 감소와 event recall 감소 5%p 이내는 현재 근거 없는 예시이므로 목표로 채택하지 않는다. baseline과 통제 시나리오의 규모를 확인한 뒤 P0 결정으로 정한다.

Positive P1~P4와 negative/hard-negative N1~N5의 확정된 시나리오는 [MVP Research Specification](mvp-research-specification.md)을 따른다. 촬영 전 참여 동의, 장소, 보존·삭제 정책을 확정한다. 실제 흉기나 위험 행동은 사용하지 않는다.

## 8. Platform Strategy

- 계획 기준은 **Jetson Orin Nano Developer Kit + JetPack 7.2.1 / Jetson Linux 39.2.1**이며 실제 검증 보드는 **L4T 39.2.0 native**다. 이 차이와 실행 환경을 보존하고 정식 동결은 별도로 결정한다. 계획에 맞추려고 자동 업그레이드하지 않는다.
- 아래는 계획 플랫폼의 배포 구성 기록이다. 실제 native pilot과 구분한다. JetPack7.2.1 기준 구성은 Ubuntu24.04, kernel6.8, CUDA13.2.2, cuDNN9.20.0, TensorRT10.16.2, VPI4.1.3이다. 2026-10-27 공식 배포 정보를 재확인해 이전 CUDA13.2.1 표기를 정정했다. 이는 기준 배포 구성이고 실제39.2.0 보드/venv와 구분한다.
- detector용 PyTorch/Ultralytics와 NVIDIA container image는 JetPack 7.2.1 및 실제 보드에서 smoke test한 뒤 고정한다. NVIDIA 문서의 예시 container tag를 프로젝트 의존성으로 그대로 채택하지 않는다.
- 공통 domain·spatial·temporal·state-machine·ablation 로직은 Python 3.10~3.12에서 동작하는 platform-neutral package로 만들고, camera·detector·GPIO·resource monitor를 adapter로 분리한다.
- detector runtime은 실제 L4T 39.2.0의 native PyTorch·Ultralytics 파일·P430 경로를 검증했다. 정식 runtime 동결과 container 채택은 별도 결정이다. 순수 core와 PC replay test는 ML runtime 없이도 실행 가능해야 한다.
- 기존 Jetson Nano 4GB와 구형 JetPack 환경은 legacy 보존·선택적 cross-device 비교 대상이다. 신규 코드를 Python 3.6 또는 JetPack 4 제약에 맞추지 않는다.
- B0~B4는 동일 Orin 장비·detector·입력과 공통 설정에서 비교하며 B4 관계 모델·threshold만 별도 기록한다. Nano 대 Orin 비교는 context ablation과 분리된 하드웨어 실험으로만 수행한다.
- PC/recorded-detection 테스트와 Orin 실기기 검증을 별도 증거로 기록한다. 최종 모델·입력 조건의 Orin 측정 전에는 정식 FPS 목표나 TensorRT 필요성을 확정하지 않는다.

## 9. Timeline — 11월 일정은 위 승인 계획을 우선

아래 9~10월 표는 초기 계획 이력이다. 날짜가 지났다는 이유로 완료를 뜻하지 않는다.

| 기간 | 목표 | 종료 증거 |
|---|---|---|
| 9월 전반 | 기존 자료 inventory, PC core/replay·dataset tooling 구축 | 개발 로그·PC 검증 증거 확보; Orin inventory는 장비 입고 후 |
| 9월 후반 | legacy 128장 사람 검수, 공개 source audit, controlled scenario·split 세부 설계 | 검수 기록·source gate·annotation 규칙 |
| 10월 전반 | 승인된 데이터의 CUDA baseline 학습, Orin 입고 시 runtime·camera·GPIO smoke | 고정 run evidence·장비 inventory·통합 이슈 |
| 10월 후반 | Orin 통합, GPIO, benchmark harness, controlled dataset 준비 | 반복 실행과 실기기 증거 |
| 2026-10-31 | 초기 practical freeze 목표 — `SUPERSEDED` | DoD 점검표, 고정 commit·config |
| 11월 | Orin benchmark·ablation·오류 분석, 가능 시 Nano/Orin 별도 비교, 논문·보고서 | 원시 결과, 요약표·그래프, 해석 |
| 12월 초 | 최종 데모·영상·최종보고서·졸업논문 정리 | 제출본과 재현 절차 |

11월에는 11/05 승인된 YOLO 데이터 개선·독립 HOI/B4 범위를 수행하며 추가 확장은 실험을 막는 결함 수정이나 별도 승인 범위로 제한한다. 핵심 알고리즘 변경 시 실험 버전과 결과를 분리한다.

## 10. Risks and Mitigation

| 위험 | 영향 | 대응 |
|---|---|---|
| JetPack 7.2.1과 ML framework 호환성 | detector 설치·실행 실패 | 실제 보드 native smoke 우선, container 대안 비교, 성공한 버전만 고정 |
| Orin 보드 SKU·펌웨어·저장장치 미확인 | 설치·성능·일정 차질 | 장비 수령 즉시 inventory, UEFI/QSPI 경로와 설치 대상을 확인 |
| legacy Nano 구형 stack | 과거 baseline 재현 실패 | 신규 경로와 격리하고 cross-device 비교를 선택 실험으로 유지 |
| 낮은 inference 성능 | 실시간 데모·지연 목표 실패 | 실제 baseline 측정 후 해상도·모델·precision 최적화 결정 |
| thermal throttling | 장시간 결과 왜곡 | 전원 모드·냉각·온도·warm-up 조건 기록 |
| 카메라/GPIO 호환성 | 통합 지연 | Orin 입고 직후 독립 smoke test, PC mock interface 활용 |
| 제한된 데이터·시나리오 | 일반화 주장 제한 | 연구 범위를 controlled scenario로 명시하고 과도한 일반화 금지 |
| 오탐·미탐 trade-off | 안전성과 성능 해석 오류 | event recall·false alarm·latency 동시 보고 |
| 위험한 촬영 | 인적·윤리 위험 | 실제 흉기 금지, 안전한 모형·통제 장소·동의 절차 사용 |
| Orin 사용 일정 지연 | 실기기 통합 지연 | PC core·recorded replay·mock adapter를 먼저 완성하고 hardware adapter를 후속 연결 |
| 일정 초과 | 실험·논문 시간 부족 | 11월20일 모델 동결/11월30일 마감, 선택 실험 수 축소 |
| 문서 부채 | 결과 재현·보고서 작성 실패 | 개발 로그와 검증 증거를 작업 완료 조건에 포함 |

## 11. Documentation and Evidence Strategy

### Source-of-truth hierarchy

1. `project-plan.md`: 목적·범위·일정·성공 기준
2. `mvp-research-specification.md`: 확정된 MVP의 이벤트·평가 기준
3. `open-decisions.md`: 아직 확정되지 않은 선택
4. `architecture.md`: 현재 채택된 기술 구조와 계약
5. `model-data-plan.md`: dataset·model 준비와 provenance·split 기준
6. `pre-orin-work-plan.md`: 실기기 도착 전 남은 작업과 gate
7. `verification.md`: 요구사항별 검증 상태와 증거
8. `development-log.md`: 실제 작업과 변경의 시간순 이력
9. `meeting-decisions/`: 당시 팀 결정의 근거

`README.md`는 이 구조의 진입점이며, `AGENTS.md`는 Codex 작업 행동 규칙이다. 둘은 project plan의 범위·결정을 대신하지 않는다.

충돌 시 실제 구현·검증 증거, 최신 명시적 결정, 과거 제안 순으로 해석한다. `PROPOSAL`은 팀 결정 없이 구현 의무가 되지 않는다.

### 기록 흐름

```text
작업 카드
→ 코드/설정/문서 변경
→ 검증 및 증거
→ development-log / verification
→ 주간보고서 누적
→ 실험 기록
→ 최종보고서·졸업논문 재사용
```

주간보고서는 매주 금요일 제출 요구에 맞춰 최신 주차가 앞에 오도록 누적하되, 상세 기술 근거는 개발 로그와 검증 문서를 링크한다. 원본 영상·사진·대용량 결과·개인정보는 Git에 넣지 않고 통제된 로컬 저장 위치와 식별자만 기록한다.

## 12. Current Work Gate

현재: M2 단일 recipe 기술 준비·실제 촬영/bbox/Holding GT·T1/HOI·GPIO/독립 평가가 남는다. RAW4종과 추가 GPU 환경은 완료됐다. 아래 9~10월 순서는 역사 기록이며 다시 수행할 대기 목록이 아니다.

2026-10-26 갱신: DEV-SOHAS 예비 학습3개와 오류 분석, 새 best.pt + COCO person의 PC13 CUDA 영상/동일 JSONL B0~B3/metadata/snapshot/mock alarm 통합을 검증했다. 검수 사이트는 추가150장 배포 완료이며 학습 승인은 별도다. 다음은 source gate를 통과한 실사 보강과 Orin 접속·실제 영상/사건 정답·카메라/GPIO 통합이다. [PC 통합 증거](../reports/runtime/development-best-video-2026-10-26/report.md)는 train 이미지 조합 smoke이며 실영상 성능·최종 detector·실기기 DoD 완료를 뜻하지 않는다. 아래09-26 항목은 원래의 gate 순서로 보존한다.

2026-09-26 현재, 남은 선행 작업은 아래 순서로 진행한다. 세부 상태는 [Pre-Orin Work Plan](pre-orin-work-plan.md)과 [Verification Matrix](verification.md)를 따른다.

1. 다른 팀원의 legacy 128장 사람 검수·L0 재현과 신규 detector source audit을 **병렬** 진행한다. L0 완료는 신규 detector의 선행 gate가 아니다.
2. 신규 담당자는 공개 source의 권리·표본·중복 audit과 [dataset recipe 후보](dataset-source-strategy.md)를 검토한다.
3. 승인된 신규 recipe의 CUDA 학습·고정 detector evidence 확보
4. Orin Nano 입고 시 SKU·저장장치·JetPack 상태 inventory, runtime·카메라·GPIO 통합
5. controlled scenario의 event 정답을 만들고 동일 조건 B0~B3 benchmark 착수

## 13. Official platform references

- NVIDIA JetPack downloads and release information: <https://developer.nvidia.com/embedded/jetpack/downloads>
- Jetson Orin Nano Developer Kit quick start: <https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/quick_start.html>
- Jetson Orin Nano Docker setup: <https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/setup_docker.html>

위 링크는 2026-09-14에 확인했다. 이후 NVIDIA 최신판이 바뀌더라도 본 프로젝트의 기준은 별도 결정 전까지 JetPack 7.2.1로 유지한다.
