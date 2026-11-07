# 상황 인지형 Edge AI 흉기 위협 대응 시스템

## English summary

**Context-Aware Edge AI Threat Response System** is a non-commercial undergraduate capstone at **Yeungnam University, South Korea (Fall 2026)**, investigating whether spatial/temporal context and learned person–knife holding assessment can reduce unnecessary surveillance alerts.

**Target setting:** Jetson Orin Nano + Reolink P430; a planned fixed indoor camera approximately 3 m high, looking downward at an angle. Small and occluded knives are a central challenge.

**Full pipeline (B3/B4):** camera → person/knife detection → spatial association (B3) or learned Holding/Not Holding assessment (B4) → K-of-N temporal confirmation → four-state machine (`CLEAR / CANDIDATE / CONFIRMED / COOLDOWN`) → alarm output, event metadata, and snapshot. Physical GPIO integration remains pending.

**Evaluation plan:** compare detection-only evidence (B0), temporal confirmation (B1), spatial association (B2), their combination (B3), and learned holding plus temporal confirmation (B4). Use the same frozen detector and recordings to measure event precision/recall, false alerts per hour, and alert delay. Evaluate detector improvements separately.

**Scope:** the system does not infer violent intent or criminal behavior. Geometry-based association does not prove physical possession; real-data Holding accuracy is still unverified.

**Status — 6 November 2026:** four exploratory YOLO26n/s training runs and PC comparisons are complete. Live P430 input and YOLO26n/B3 inference have been verified on Orin with a development checkpoint. HOI/B4 has synthetic integration checks; target-camera adaptation, real Holding evaluation, physical GPIO, and independent final evaluation remain pending. Published metrics are development results, not final deployment performance.

**Data handling:** requested third-party data will be used under the provider's agreed terms. Restricted originals and derived images will not be committed to GitHub, redistributed, or added to public review endpoints without explicit permission. Legacy submodule assets require separate permission checks.

[Research overview and data-handling commitments (English)](docs/research-overview-en.md) · [Training and development comparisons](reports/evaluation/raw-detector-selection-2026-11-06/report.md) · [Orin camera verification](reports/runtime/p430-yolo26n-2026-11-05/report.md)

Most detailed engineering records are in Korean. Contact: [22211897@yu.ac.kr](mailto:22211897@yu.ac.kr).

## 한국어 개요

> Context-Aware Edge AI Threat Response System · 2026-2 종합설계과제(1)

Jetson Orin Nano에서 사람과 칼을 탐지하고 **공간·시간 문맥과 학습 기반 소지 관계**로 경보를 판단하는 엣지 AI 시스템을 개발합니다. 같은 영상에서 판단 방법을 비교해 불필요한 경보가 줄어드는지 검증합니다.

## 프로젝트 한눈에 보기

- **무엇을:** 기존 Jetson Nano의 단일 프레임 흉기 탐지·즉시 경보 프로토타입을 상황 인지형 시스템으로 고도화합니다.
- **어떻게:** `person`과 `knife`의 bounding box 공간 연관성, K-of-N 시간 확인, 4-state machine을 결합합니다.
- **무엇과 비교:** 동일 detector·영상에서 B0~B3의 공간·시간 문맥 효과와, 별도로 학습한 Holding 관계 모델 B4를 비교합니다. YOLO26n/s의 데이터 보강 효과는 이 비교와 분리합니다.
- **무엇을 남기나:** Jetson Orin Nano의 GPIO 경보, 사건 metadata·snapshot, 재현 가능한 성능·오류 분석 근거를 만듭니다.
- **주장 범위:** 실제 폭력 의도·범죄·위험행동을 판별하지 않습니다. 사람과 칼의 공간적·시간적 연관성을 근거로 **잠재적 흉기 위협 상황**을 탐지합니다.

## 구현 흐름

```text
Camera
  -> Person/Knife Detector
  -> Spatial Association (B3) / Learned Holding (B4)
  -> K-of-N Temporal Confirmation
  -> CLEAR / CANDIDATE / CONFIRMED / COOLDOWN
  -> GPIO Alarm + Event Metadata + Snapshot
```

## 현재 개발 상태

기준일: **2026-11-06**. 개발 결과와 목표를 구분합니다.

- **설계:** 11월30일 개발·평가 마감, YOLO26n/s 데이터 보강 및 B0~B4 비교가 `DECISION`입니다. 최종 detector D*와 실제 Holding 정확도는 아직 확정·검증 전입니다.
- **PC에서 검증됨:** 판단 core, replay·사건 평가기, dataset audit/export/review, detector/video/snapshot, CUDA 학습 경로가 구현·검증되었습니다. PC11·PC12·PC14도 격리 학습 환경과 각32개 관련 테스트·FP32/AMP smoke를 통과했습니다([추가 GPU 환경](reports/training/pc11-pc12-cuda-readiness-2026-11-06/report.md)).
- **학습·개발 평가 완료:** PC13의 RAW-R1-n/H1-n/M1-n/M1-s가 각각50epoch·35,600updates를 완료했습니다. 8모델×동일6개 개발셋 비교와 M1-n/s의960 추론 진단을 기록했습니다. 현재 주력 권장 후보는 **M1-n(`PROPOSAL`)**이며 최종 채택은 아닙니다([결과·한계](reports/evaluation/raw-detector-selection-2026-11-06/report.md)).
- **실제 카메라·Orin에서 검증됨(2026-11-05):** P430 main/sub RTSP 수신, 기존 RAW-R1-n 개발 checkpoint의 YOLO26n/B3 각각300 valid frame, metadata/snapshot·mock alarm, 모니터 실시간 표시를 확인했습니다. 새 M1의 Orin 배포나 실제 사건 정확도·물리 GPIO 검증은 아닙니다([실기기 증거](reports/runtime/p430-yolo26n-2026-11-05/report.md)).
- **현재 어려움:** 확대된 실제 CCTV 개발 표본83장/knife 정답31개에서 M1-n/640의 TP는0, 같은 checkpoint의960 추론은1이었습니다. 작은 칼·가림의 목표 환경 적응이 필요하며 이 표본을 독립 final test로 주장하지 않습니다([확대 평가](reports/datasets/reviewed-next-training-2026-11-06/report.md)).
- **데이터·후속 학습:** 약3m 고정형 실내 CCTV가 목표입니다. 검수 전 원본 주석을 쓴 RAW 예비 학습은 미검수 상태를 보존합니다. M2 YOLO26n/640을 PC13에서 학습 중입니다. 기존 문제·불확실88장 제외+Open Images594장으로 train11,884장이며 val/test는 고정했습니다. 전체 완료·공통 비교는 대기입니다([실행 증거](reports/training/m2-real-2026-11-07/report.md)). 다음 주 촬영 후 T1·실제HOI를 진행합니다. 합성은 별도, US Mock은 외부 개발 평가용입니다([후보·경계](reports/datasets/cctv-candidate-check-2026-11-06/report.md)).
- **HOI/B4:** G/VG 관계 학습기, detector/frame/model hash로 연결한 관계 점수, B4 replay/사건 평가·snapshot 경로를 합성 자료 PC/Orin CUDA에서 검증했습니다. 실제 Holding/Not Holding 관계 정답 수집·학습·정확도는 아직 미검증입니다([규격·인계](docs/hoi-annotation-contract.md)).
- **남은 검증:** 자체 촬영 적응, 실제 HOI 성능, 물리 GPIO, 독립 사건 평가와 실제 배치 조건의 지연·자원·안정성입니다. 실제 Orin L4T39.2.0 환경을 보존하며 TensorRT는 후속 최적화입니다.
- **증거 원칙·일정:** 기존 MIDAS 수치는 재현 조건이 부족해 신규 공식 성능으로 사용하지 않습니다. 2026-11-20 모델·설정 동결 → 11/25~27 독립 CCTV 평가 → **11/30 개발·평가 마감**을 목표로 합니다. 완료 목표는 검증 완료를 의미하지 않습니다.

자세한 구조는 [아키텍처](docs/architecture.md), 연구 범위는 [Master Project Plan](docs/project-plan.md), 검증 증거는 [검증 매트릭스](docs/verification.md)에서 확인할 수 있습니다.

## 문서 안내

- [Research overview (English)](docs/research-overview-en.md): 연구 목적, B0~B4 설계, 현재 검증과 데이터 처리 원칙의 영문 안내

처음 읽는 경우 아래 순서를 권장합니다.

1. [Master Project Plan](docs/project-plan.md): 왜 이 프로젝트를 하는지, 무엇을 완료해야 하는지
2. [MVP Research Specification](docs/mvp-research-specification.md): 무엇을 event로 판단하고 어떻게 비교하는지
3. [아키텍처](docs/architecture.md): 실제 시스템 흐름과 모듈 경계

- [Master Project Plan](docs/project-plan.md): 목적, 범위, 일정, 성공 조건의 최상위 기준
- [MVP Research Specification](docs/mvp-research-specification.md): 이벤트 정의, 상태·평가·시나리오의 구현 기준
- [PC 준비·Orin 통합 계획](docs/pre-orin-work-plan.md): 병렬 legacy 재현·source audit·실기기 통합 gate
- [Orin 접속·runtime 재현](docs/orin-runtime-setup.md): 실제 설치 환경·격리 venv·GPU/파일 smoke 절차
- [모델·데이터 준비 계획](docs/model-data-plan.md): 데이터 inventory, 라벨·분할 계약, 검증·학습 단계
- [Dataset Source Strategy](docs/dataset-source-strategy.md): 신규 detector 후보 recipe, 공개 source별 역할, PC13 원본 저장 원칙과 audit gate
- [Dataset Evaluation Criteria](docs/dataset-evaluation-criteria.md): 공개 source와 legacy 128장 검수의 gate·판정 열
- [PC13 팀 웹 검수](docs/team-review-deployment.md): 팀원 접속·후보 표본·관리자 운영·검증 상태
- [선행연구·공개 데이터 검토](docs/prior-work-and-dataset-review.md): 확인된 연구 근거와 자료별 활용 경계
- [개발 기록](docs/development-log.md): 시간순 변경·결정·검증·한계
- [미결정 사항](docs/open-decisions.md): 확정 전 선택지와 판단 기준
- [아키텍처](docs/architecture.md): 현재 목표 구조와 책임 경계
- [검증 매트릭스](docs/verification.md): 요구사항별 증거와 미검증 항목
- [문서화 운영 규칙](docs/documentation-governance.md): 기록·상태·보안 규칙
- [회의·수업 결정 근거](docs/meeting-decisions/): 주제 선정과 일정 제약의 요약 기록
- [기존 MIDAS 자산 선별 기록](docs/legacy-asset-selection.md): 가져온 baseline과 제외 근거

## Legacy source checkout

2025-2의 모델·데이터셋·학습 소스는 별도 upstream Git submodule로 참조합니다. 하위 저장소에는 과거 이미지와 checkpoint가 포함되며, 재사용·재배포 조건은 source별로 확인해야 합니다. 신규 제공 제한 자료의 비공개 처리 원칙과 이 역사적 참조를 구분합니다. 신규 코드만 확인할 때는 일반 clone으로 충분하고, legacy 분석이 필요할 때 아래 명령으로 하위 저장소를 함께 받습니다.

```bash
git clone --recurse-submodules https://github.com/jaydenkim197/edge-threat-response.git
```

이미 clone한 경우에는 `git submodule update --init --recursive`를 실행한다. submodule 내부의 legacy 코드와 모델은 신규 시스템 코드로 직접 수정하지 않는다.

## Dataset audit tooling

Python 3.10 이상에서 설치 후 실행한다. 현재 Windows 개발 PC에서는 한글 상위 경로와 setuptools 조합 때문에 `pip install -e .`가 인코딩 오류로 실패했다. 아래의 일반 설치를 사용하며, 소스 변경 후에는 다시 설치한다. 현재 로컬 `.venv-ml`은 별도로 소스 경로를 연결해 놓았다.

```text
python -m pip install . --no-deps
python -m unittest discover -s tests -v
etr-dataset audit --registry configs/datasets/legacy.json --repo-root . --output-dir reports/datasets/legacy-2026-09-14 --fail-on never
```

`audit`은 원본 dataset을 수정하지 않고 `manifest.jsonl`, `issues.jsonl`, `summary.json`, `report.md`를 생성한다. 기본 `--fail-on error`는 오류가 있으면 exit code 1을 반환한다. 현재 legacy split에는 알려진 group leakage가 있어 위 재현 명령만 `--fail-on never`를 사용한다.

분할 계획은 실제 파일을 옮기지 않고 manifest의 `planned_split`과 group assignment만 생성한다. 비율과 seed는 연구 결정 후 명시적으로 전달해야 한다.

```text
etr-dataset plan-split --manifest reports/datasets/legacy-2026-09-14/manifest.jsonl --output-dir reports/datasets/local-plan --ratios train=0.7,val=0.15,test=0.15 --seed 12345
```

위 비율은 CLI 형식 예시이며 프로젝트의 확정 split이 아니다. 현재 재현 결과는 [legacy dataset audit report](reports/datasets/legacy-2026-09-14/report.md)에 있다.

계획된 manifest는 knife-only YOLO dataset으로 materialize할 수 있다. raw/source class `0=knife`는 학습 model-local `0=knife`로 유지되고, runtime adapter에서 canonical knife ID `1`로 변환한다.

```text
etr-dataset materialize-knife-yolo --manifest data/work/legacy-development-split/planned-manifest.jsonl --registry configs/datasets/legacy.json --repo-root . --output-dir data/processed/knife-legacy-development-v1 --link-mode hardlink
```

검증된 development export 요약은 [legacy development dataset report](reports/datasets/legacy-development-v1/report.md)에 있다.

사람 검수용 pack은 Pillow가 있는 격리 환경에서 생성한다. contact sheet와 review CSV는 원본 이미지가 포함되므로 로컬 `data/review/`에만 둔다.

```text
.venv-ml/Scripts/python -m pip install -r requirements/review.txt
.venv-ml/Scripts/etr-dataset review-pack --manifest data/work/legacy-development-split/planned-manifest.jsonl --repo-root . --output-dir data/review/legacy-development-v1 --per-stratum 12 --seed 20260915
```

재현 결과는 [legacy visual review report](reports/datasets/legacy-visual-review-v1/report.md)에 있다. `review.csv`의 판정 열을 사람이 채우기 전까지 학습 승인은 완료되지 않은 상태다.

## SOHAS VOC 승인 전 audit

`etr-dataset sohas-voc-audit`는 고정 upstream의 image Git metadata와 XML을 split/basename으로 짝맞추고 모든 knife bbox를 보존한다. 원본이나 학습 dataset을 수정하지 않으며, 준비된 YOLO label을 그대로 채택하지 않는다.

```bash
etr-dataset sohas-voc-audit --source-root data/source-audit/sohas-upstream --output-dir data/source-audit/sohas-voc-review --sample-count 100 --seed 20261002
```

입력은 upstream commit `48860b990e4d4f57fe100248887fceb248475dc8`의 Git checkout이며 XML·YOLO label이 로컬에 있어야 한다. 이미지가 없어도 metadata/label dry-run은 가능하지만 decode·시각 검수는 검증되지 않는다. 출력은 `voc-candidates.jsonl`, `issues.jsonl`, `summary.json`, 전체 `review-queue.csv`와 층화 `review-sample.csv`다. 좌표 convention 기본값 `unknown`은 raw 좌표만 보존하고 YOLO 초안을 만들지 않는다. 명시적인 convention·근거가 있는 변환도 검수 대기 초안이며 학습 승인이 아니다. 준비·좌표 규칙·gate는 [모델·데이터 계획](docs/model-data-plan.md#sohas-voc-source-specific-audit)과 [검증 보고서](reports/datasets/sohas-dasci-metadata-2026-10-02/report.md#cloud-voc-dry-run--2026-10-02)에 있다.

### 버튼으로 이미지 검수하기

팀원 공동 검수는 [PC13 팀 검수 사이트](https://pc13.tail37c267.ts.net/)에서 **본인 이름을 선택**해 시작한다([운영 안내](docs/team-review-deployment.md)). 후보를 고르면 첫 이미지가 자동 배정된다. **모든 후보에서 같은 두 질문**—CCTV형 장면인지, 칼 라벨이 정상인지—만 답하면 자동 저장되며 `문제 있음`일 때만 메모 칸이 나타난다. 아이폰 Safari·안드로이드 Chrome의 **홈 화면에 추가**로 열고 최근 검수를 이어갈 수 있다. CSV·개발 환경은 필요 없다. 모바일 Chrome/WebKit의 합성 fixture 저장·재접속은 검증했으며 실제 휴대폰 설치는 별도 확인한다. 이미지와 판정은 PC13에 저장한다. ACF는 원본 미확보로 현재 활성 목록에서 제외돼 있습니다. Dangerous Items의 VOC semantic class 매핑은 확인해 RAW 예비 학습에 사용했으며, 웹 품질 판정과 정식 dataset 채택은 구분합니다. 현재 이름 선택 방식은 제한 자료의 접근 인증 수단이 아니므로, 새 제한 자료를 공개 검수 화면에 반입하지 않습니다.

아래 명령은 기존 **단일 PC 로컬 SOHAS 검수 도구**가 필요한 경우에만 사용한다. 중앙 서비스 사용을 시작한 뒤 같은 표본을 로컬 DB에서 병행 수정하면 판정이 갈라진다. 현재 로컬 100장 pack은 `data/review/sohas-click-review-20261003/`이며 Git에는 이미지가 포함되지 않는다.

Windows에서는 저장소 안에서 아래 명령을 실행한다. 기존 Python 환경을 사용하며 추가 설치·공개 서버·클라우드 업로드는 필요 없다.

```powershell
.\tools\start_review.ps1
```

브라우저가 열리면 검수자 이름을 입력하고 **CCTV형 장면인지 / 칼 라벨이 정상인지** 두 질문만 답한 뒤 **저장하고 다음**을 누른다. 정상은 박스 위치와 칼 누락을 함께 확인한 판정이고, 칼 라벨 0개 표본에서는 실제 칼이 없음을 뜻한다. 문제 있음은 한 줄 메모를 남기며 모르겠음은 보류한다. 기본 주소는 `http://127.0.0.1:8768`이고 이 PC에서만 접근할 수 있다. 기존 8765 서버는 진행 중 작업을 끊지 않기 위해 남겨뒀으므로 **기존 창의 저장을 마친 뒤 새 주소로 이동**한다. 필수 항목을 채우면 자동 저장되며 확대·박스 숨기기·미검수/음성 필터·CSV 내려받기를 지원한다. PC 재시작 뒤에는 명령을 다시 실행한다. 다른 pack은 `-ReviewDir PATH`, 다른 포트는 `-Port 8770`으로 지정한다.

판정과 수정 이력은 pack 안의 `human-review.sqlite3`에 저장하고 입력 `review.csv`/이미지는 수정하지 않는다. 미완성 입력은 같은 브라우저의 임시 보관본일 뿐 완료 기록이 아니다. 검수 기록은 dataset 채택·좌표 규칙·학습 승인을 자동으로 완료하지 않는다. 상세 규칙은 [검수 기준](docs/dataset-evaluation-criteria.md#5-sohas-로컬-웹-검수)에 있다. 기존 contact-sheet-only legacy pack은 이 화면의 입력 형식과 다르다.

## Detector training smoke

ML 환경은 일반 개발 환경과 분리한다. 아래 profile은 dataset·학습 배관 검사용이며 성능 학습이나 연구 파라미터가 아니다.

```text
python -m venv .venv-ml
.venv-ml/Scripts/python -m pip install -r requirements/ml-smoke.txt
.venv-ml/Scripts/python -m pip install . --no-deps
.venv-ml/Scripts/etr-train --config configs/training/cpu-smoke.json --data data/processed/knife-legacy-cpu-smoke-v1/data.yaml --output-dir runs/training
```

2026-09-15 실행 결과는 [YOLO26n CPU smoke report](reports/training/yolo26n-cpu-smoke-2026-09-15/report.md)에 기록했다. model weight와 전체 run output은 Git에 포함하지 않는다.

CUDA full-training 인계 절차와 Colab review gate는 [CUDA / Colab training handoff](docs/training-cuda-handoff.md)를 따른다.

## Detector and video integration

`etr-detect`는 image/video를 canonical detection JSONL로 변환한다. `etr-run`은 같은 adapter를 B3 pipeline에 연결해 event metadata와 snapshot을 생성한다. 실제 weight·입력·config의 hash가 summary provenance에 기록된다.

```text
etr-detect --input INPUT.mp4 --detector-config configs/detection/composite.development.example.json --output-dir runs/detection/local
etr-run --input INPUT.mp4 --detector-config configs/detection/composite.development.example.json --pipeline-config configs/replay/development-v2.example.json --output-dir runs/runtime/local
etr-replay --input runs/runtime/local/detections.jsonl --config configs/replay/development-v2.example.json --output-dir runs/replay/local
```

`configs/detection/legacy-composite.cpu-smoke.json`은 보존된 legacy weight의 PC 배관 검증용이고 detector 채택이나 성능 근거가 아니다. 결과는 [pre-Orin integration report](reports/runtime/pre-orin-detector-integration-2026-09-15/report.md)에 있다.

## Detection replay core

Increment A는 영상이나 모델 대신 timestamp와 detection 목록을 가진 JSONL을 입력으로 받는다. 아래 개발용 fixture와 설정으로 B0~B3를 같은 입력에 반복 실행할 수 있다.

```text
python -m pip install . --no-deps
etr-replay --input tests/fixtures/replay/basic.jsonl --config configs/replay/development.example.json --output-dir reports/replay/local-run
```

각 mode 폴더에는 frame별 판단, event JSONL, summary가 생성된다. replay에는 원본 frame이 없으므로 event의 snapshot 상태는 `not_captured`다. 예제의 confidence, 거리, bbox 확장, K/N, rearm 값은 계약·CLI 검증용이며 연구 최종값이 아니다. 커밋된 smoke 결과는 [Increment A replay report](reports/replay/increment-a-smoke/report.md)에 정리했다.

## 사건 평가와 촬영 준비

수동 사건 정답과 동일 detection JSONL의 B0~B3 replay를 `etr-evaluate`로 비교한다. 사건 precision/recall/F1, 반복·배경 오경보, 영상 시간축의 판단 지연과 원시 매칭·입력 hash를 기록한다. 구현·가상 검증은 완료됐으며 실제 시스템 성능이나 GPIO 지연을 측정한 결과는 아니다.

[통제 촬영·평가 절차](docs/controlled-experiment-protocol.md)에 실행 명령, P1~P4/N1~N5 촬영표, start/end 정답 양식과 세션별 pilot/tuning/final-test 분리가 있다. 실제 거리·허용 오차·반복 횟수는 첫 pilot 후 확정한다. 정식 검수 recipe의 [R1/H1 학습 준비](docs/training-cuda-handoff.md#r1h1-실행-준비--2026-10-04)와, 사용자 허용으로 진행한 [원본 주석 RAW 예비 학습](docs/raw-source-training.md)은 별도 경로입니다. B4 최종 비교에는 별도로 사람 관계 정답으로 학습한 checkpoint와 [관계 sidecar 규격](docs/hoi-annotation-contract.md)이 필요합니다.

## Non-goals (현재 단계)

- 단순히 YOLO 버전만 교체하는 작업
- 고비용 클라우드 의존형 상시 영상 업로드
- 검증 없이 위협 상황을 정확히 판별한다고 주장하는 것
- 민감 영상·개인식별정보를 무분별하게 수집하거나 저장하는 것

## 작업 시작 규칙

각 material task는 목표, 범위, 완료 기준, 위험, 문서 영향을 먼저 정의한다. 구현 후에는 관련 코드·테스트·문서를 함께 갱신하고, 실제 실행한 검증과 한계만 기록한다.

## 개발 작업공간 및 GitHub 동기화

이 저장소의 기준 작업공간은 상위 수업 폴더 안의 `03_개발_GitHub`이다. 상위 폴더 자체는 Git 저장소가 아니며 회의록·제출물·팀원 사진·서명은 GitHub 동기화 대상이 아니다.

- 작업 시작 전 `git pull --ff-only`로 원격 `main`을 안전하게 반영한다. fast-forward가 불가능하면 임의로 병합하지 않고 원인을 확인한다.
- 의도한 변경만 검토·stage하여 커밋한다. 이 작업공간에서는 commit 직후 `origin/main`으로 자동 push되도록 Git hook을 설정했다.
- GitHub의 변경을 감시하여 무조건 자동 pull하는 방식은 사용하지 않는다. 작업 중인 파일을 덮어쓰거나 충돌을 숨길 수 있기 때문이다.
- 새 clone에서는 `git submodule update --init --recursive` 후 `git config core.hooksPath .githooks`를 한 번 실행해 같은 자동-push 정책을 적용한다.
