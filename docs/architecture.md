# System Architecture

상태: MVP 논리 구조 `DECISION`, 공통 core·replay·detector/video/snapshot 인터페이스 `IMPLEMENTED`/PC `VERIFIED`, CUDA/Orin·camera/GPIO adapter `PLANNED`. Tracker와 Dashboard는 현재 필수 경로가 아니다.

## 시스템 경계

```text
[Camera]
   -> [Camera Adapter]
   -> [Detector]
   -> [Spatial Association]
   -> [Temporal K-of-N Buffer]
   -> [CLEAR / CANDIDATE / CONFIRMED / COOLDOWN]
      -> [GPIO Alarm]
      -> [Event Recorder / Local Event Store]
      -> [Metrics / Benchmark]

Optional after MVP:
   [Tracker / Motion Analyzer]
   [Dashboard / Event API]
```

## 기준 플랫폼과 실행 경계

- 신규 시스템 배포 기준: Jetson Orin Nano Developer Kit, JetPack 7.2.1 / Jetson Linux 39.2.1.
- 공통 core: Python 3.10~3.12, PyTorch·OpenCV·GPIO 비의존. PC와 Orin에서 같은 단위 테스트를 실행한다.
- detector adapter: JetPack 7.2.1 실제 보드에서 native PyTorch·Ultralytics smoke를 먼저 수행하고 container는 재현성 대안으로 비교한다. 성공 전에는 framework 버전이나 image를 고정하지 않는다.
- hardware adapter: camera, GPIO, `tegrastats` 계열 자원 수집을 core 바깥에 둔다.
- legacy adapter: 2025-2 Nano 코드는 submodule에서 보존하며 신규 package의 runtime 기준으로 사용하지 않는다.

Recorded-detection replay와 PC image/video adapter가 구현돼 있다. Replay는 B0~B3와 상태 전이를 같은 입력에 반복 실행하고, PC video 경로는 실제 frame과 detector를 연결한다. 카메라·GPIO의 Orin 실기기 연결은 후속 검증 대상이다.

## 책임 분리

| 컴포넌트 | 책임 | 플랫폼 의존성 |
|---|---|---|
| Camera Adapter | USB/CSI/영상 파일에서 프레임 획득·복구 | OpenCV image/video PC adapter `IMPLEMENTED`; Jetson camera `PLANNED` |
| Detector | 사람·흉기 bounding box와 confidence 생성 | single/composite·Ultralytics lazy adapter PC `IMPLEMENTED`; CUDA/TensorRT 교체 가능 |
| Tracker | detection에 track ID와 이동 이력 부여 | Stretch goal, 공통 순수 로직 우선 |
| Spatial Association | v1은 nearest person + 정규화 거리 + 확장 bbox, 신규 v2는 nearest person + 확장 bbox 판정과 정규화 거리 진단값 산출 | v1/v2 `IMPLEMENTED`, PC `VERIFIED` |
| Temporal Confirmation | knife/associated source-level boolean history를 K-of-N으로 판단 | 공통 순수 로직, `IMPLEMENTED` |
| Alert State Machine | 확정된 상태 전이와 clear-frame rearm | 공통 순수 로직, `IMPLEMENTED` |
| GPIO Alarm | LED·부저·상태 버튼 제어 | Jetson 전용 |
| Event Recorder | metadata·snapshot 및 선택적 clip·보존 정책 관리 | JSONL+동기 current-frame snapshot PC `IMPLEMENTED`; 보존 정책 `PLANNED` |
| Resource Monitor | CPU/GPU/RAM/온도/전력 수집 | Jetson `tegrastats` 등 |
| Dashboard/Event API | 위험 이벤트의 표시·선택적 전송 | 네트워크·서버 의존 |

## 최소 데이터 계약

### Recorded Detection v1 — `IMPLEMENTED`

- 생산자: 현재 replay adapter, 이후 Detector adapter
- 소비자: Spatial Association과 B0~B3 pipeline
- frame 필드: `frame_index`, `timestamp_s`, `source_id`, `status`, `detections`, 선택적 `error`
- detection 필드: `label`, `confidence`, `bbox_xyxy`, 선택적 `detection_id`
- 금지: 원본 영상 자체, 개인식별정보를 로그 필드에 직접 삽입
- 오류 처리: `valid`, `missing`, `detector_error`를 구분한다. 비정상 frame에는 detection을 허용하지 않고 K-of-N에 false sample을 넣는다.
- 순서 계약: 한 pipeline/replay는 하나의 `source_id`만 허용하고 frame index는 strictly increasing, timestamp는 non-decreasing이어야 한다.

### ThreatEvent v1 — metadata·file-input snapshot `IMPLEMENTED`/PC `VERIFIED`, camera snapshot `PLANNED`

- 생산자: Temporal Confirmation / Alert State Machine
- 소비자: GPIO Alarm, Event Recorder, Dashboard
- 필수 필드: schema/event/run/sequence ID, source, frame index·timestamp, state, B0~B3 policy, reasons, model/config ID, reliable object counts, associated pair count, snapshot status
- 선택 필드: selected association, snapshot path/error
- 보존: 정책 확정 전까지 실제 민감 영상 보존 기간을 결정하지 않음
- 오류 처리: snapshot·event 저장·alarm adapter 실패는 frame result에 별도로 남긴다. event 저장 실패가 alarm 호출을 차단하지 않는다.

### Detector / media adapter — `IMPLEMENTED`, PC `VERIFIED`

- `etr-detect`: OpenCV image/video frame을 single 또는 required-component composite detector에 입력하고 canonical detection JSONL과 component latency를 기록한다.
- model-local class는 adapter config에서 runtime `person`/`knife` 문자열로 remap한다. unmapped model class는 downstream 계약에 내보내지 않는다.
- composite의 required component 하나라도 실패하면 부분 detection을 안전 상태처럼 사용하지 않고 해당 frame 전체를 `detector_error`로 기록한다.
- `etr-run`: current decoded frame을 snapshot port에 동기 binding하고 pipeline의 `CONFIRMED` 진입 시 JPEG 한 장을 저장한다.
- input, detector/pipeline config와 로컬 weight의 path·size·SHA-256을 summary provenance에 기록한다.
- Ultralytics와 OpenCV는 lazy optional dependency라 pure core와 replay test는 ML package 없이 유지된다.

### MVP temporal identity boundary

MVP에는 tracking이 없으므로 프레임 간 동일 person identity를 보장하지 않는다. 각 프레임에서 `associated_person_knife_exists`라는 source-level boolean을 계산하고 K-of-N은 최근 N개 pipeline sample의 신호를 집계한다. `missing`과 `detector_error`도 false sample로 window에 포함한다. 따라서 결과는 특정 개인의 연속 소지를 추적했다는 의미가 아니다.

### B0~B3 실행 의미

| 조건 | confirmation predicate |
|---|---|
| B0 | 현재 frame에 reliable knife detection 존재 |
| B1 | reliable knife presence가 K-of-N 충족 |
| B2 | 현재 frame에 geometry-associated person–knife pair 존재 |
| B3 | geometry association 신호가 K-of-N 충족 |

네 조건은 하나의 pipeline과 event contract를 공유하고 confirmation predicate만 교체한다.

### State transition implementation

- `CLEAR`/`CANDIDATE`에서 mode predicate가 확정되면 `CONFIRMED`로 진입하고 event·alarm action을 한 번만 호출한다.
- 확정 근거가 사라지면 `COOLDOWN`으로 전이하고 alarm을 해제한다.
- `COOLDOWN`에서는 설정된 수의 연속 clear sample을 관측해야 `CLEAR`로 rearm된다. 중간 evidence는 clear streak을 0으로 되돌린다.
- rearm 수치는 config로 주입하며 현재 example 값은 연구 결정이 아니다.

## Offline dataset preparation path

공개 source는 runtime input과 분리된 offline raw storage에서 audit한다. target domain은 약 3 m 높이의 fixed indoor CCTV의 elevated/oblique view이며, training source·external CCTV holdout·synthetic ablation은 같은 recipe나 split에 섞지 않는다. Source별 provenance와 role은 [Dataset Source Strategy](dataset-source-strategy.md), 역할별 채택 gate는 [Dataset Evaluation Criteria](dataset-evaluation-criteria.md)를 따른다. Bbox image set은 detector 평가에 사용하며, 사건 B0~B3 평가에는 시간 순서가 보존된 입력과 event start/end 정답이 필요하다.

```text
[Source Registry + Source-specific Class Map]
  -> [Read-only Image/YOLO Label Audit]
  -> [JSONL Manifest + SHA-256]
  -> [Group / Exact-duplicate Leakage Check]
  -> [Group-aware Split Plan]
  -> human approval
  -> [Selected-source Import / Training]
```

현재 `IMPLEMENTED` 범위는 human approval 전까지다. audit과 split planner는 raw image·label을 수정하거나 복사하지 않는다. source group과 exact duplicate가 연결된 record는 하나의 assignment unit으로 처리해 planned split 사이에 나뉘지 않게 한다.

## 사건 평가·학습 승인 경계

웹 검수와 학습 사이의 `dataset/review_candidates.py`는 운영 config/immutable packs/판정 DB를 read-only로 snapshot하고 source·batch·image hash·review version을 연결한다. 서버/ReviewStore constructor는 호출하지 않으며 DB별 transaction·fingerprint·registry를 검사한다. 역할 정책에 따라 실사/합성/외부 평가와 mapping 보류를 분리하고 모든 row의 학습 승인을 false로 유지한다. 이 목록은 승인된 materialized manifest와 다르다. [검수→후보 계약](dataset-evaluation-criteria.md#6-웹-판정--미승인-학습-후보-snapshot)을 따른다.

`evaluation.py`/`etr-evaluate`는 source-level 수동 start/end 정답과 B0~B3 replay metadata를 비교한다. 시간 허용 창의 일대일 대응, 중복/배경 FP, FN, ignore와 영상시간 분모, partition별 micro 지표를 표준 라이브러리로 계산한다. session·관련 group의 partition 교차와 replay 입력/config/frame/version 불일치를 거부한다. 지연은 원본 영상 시간축의 CONFIRMED 판단 지연이며 실제 GPIO 지연이 아니다. 동시 사건은 source-level 합집합으로 주석화한다. [통제 실험 계약](controlled-experiment-protocol.md)을 따른다.

`training_pair.py`는 승인 가능한 SOHAS materialized manifest에서 R1/H1의 동일 양성·공통 val/test와 같은 draw budget 목록을 준비한다. H1은 양성을 반복하며 이미지를 추가 복제하지 않는다. 기존 training runner를 확장해 승인 파일·입력 bytes/hash가 맞지 않으면 모델 로드 전에 차단한다. 자동 권리 판정·사람 검수·raw VOC 반입·full training launch는 하지 않는다. [CUDA handoff](training-cuda-handoff.md)에 development 설정·승인·실행/비교 절차가 있다.

## 팀 데이터셋 검수 도구

학습 전 검수용 웹 도구는 runtime 경보 시스템과 별도로 PC13에서 실행한다. 기존 Flask/Waitress·ReviewStore·SQLite 이력과 공통 두 질문 UI를 재사용한다. 사용자 선택에 따라 공개 이름 드롭다운으로 검수자를 지정하고 30일 session을 유지한다. 이는 본인 인증이 아닌 self-declared identity다. 관리자 route는 별도의 코드와 8시간 session을 사용한다. 이름·raw pack·DB·비밀값은 ignored runtime에 보관한다.

모바일은 같은 웹 페이지에 responsive layout·manifest·Apple touch icon을 추가한다. 홈 화면 start URL에서 브라우저가 보관한 최근 후보를 찾아 서버의 남은 담당 배정을 이어간다. 판정 완료는 PC13 SQLite 응답으로 확인하고, 미완성 입력은 검수자별 localStorage draft로만 보관한다. 원본·판정 오프라인 캐시는 없다. 상세 사용·접근 경계와 검증은 [팀 검수 운영](team-review-deployment.md)을 따른다.

검수 확대는 immutable pack을 `review_batches`로 같은 후보 뒤에 연결한다. 기존 pack의 CSV/evidence/images/판정 DB는 수정하지 않는다. `BatchReviewStore`는 기존 global ID를 유지하고 새 pack의 local ID를 고정 offset으로 변환해 각 원래 DB에 저장한다. team DB의 추가형 `review_batches` registry가 batch ID·offset·count·fingerprint의 기존 prefix를 검증하며 재정렬·제거·다른 pack 대입을 거부한다. 원래 pack hash를 draft identity로 유지하고 catalog에 파일 경로는 노출하지 않는다. 기존 탭은 원래 ID의 저장이 가능하며, 새 범위에 진입할 때 client 목록을 갱신한다. 이전 JS 탭에는 범위 밖 ID를 배정하지 않는다.

## 실패와 fallback

- 카메라 입력이 끊기면 재시도를 수행하고, 복구 실패 상태를 명시한다.
- 네트워크 실패 시 로컬 탐지·GPIO 경보·로컬 이벤트 기록은 유지한다.
- 저장공간 부족 시 보존 정책에 따라 오래된 이벤트부터 회수하되, 정책과 실제 동작을 테스트로 검증한다.
- 모델·추론 오류 시 거짓 안전 상태로 위장하지 않고 상태 LED·로그·대시보드에 장애를 표시한다.

## 데이터 경계 - `PLANNED`

실제 영상 수집 전에 수집 장소, 참여·동의, 보존 기간, 접근 권한, 삭제 절차, 지도기관 요구사항을 확정한다. 이벤트 영상은 원본 민감 데이터로 취급하며, 개발 로그나 Git에 저장하지 않는다.
