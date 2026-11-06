# Holding 라벨 수집 인계 — 사이트 담당

<!-- docs-refresh-20261106:begin -->
## 현재 수집·실행 상태 — 2026-11-06

교환 규격, G·VG 학습기와 B4 연결을 구현하고 합성 자료로 CPU·Orin CUDA 연결을 확인했다([증거](../reports/runtime/hoi-b4-integration-2026-11-05/report.md)). 실제 Holding 학습·정확도나 관계 라벨링 웹 화면을 검증한 결과는 아니다.

기존 이미지 검수 결과를 관계 정답으로 전환하지 않는다. 실제 촬영과 pair·event 정답이 필요하며 동시 촬영 그룹을 미리 분리해야 한다. 신규 제한 자료는 공개 이름 선택 사이트에 넣기 전 [비공개 처리 요건](research-overview-en.md)을 준비한다.
<!-- docs-refresh-20261106:end -->

상태: 교환 규격·검증기·G/VG 학습기·B4 연결 `IMPLEMENTED`, 가상 자료 CPU 연결 `VERIFIED`. **실제 관계 정답 수집·학습·정확도는 미검증**이다. 기존 검수 사이트의 이미지·두 질문·판정·배정·DB는 그대로 유지한다. 이 문서는 별도의 HOI 라벨링 기능을 담당 채팅에 인계하는 규격이다.

## 담당 범위와 최소 화면

- 이 채팅: 교환 규격, import 검증, crop/기하 특징, 학습, checkpoint, 동일 detector의 B4 replay/평가.
- 사이트 담당: 영상 프레임 준비, 사람/칼 박스 제안·수정·확인, 관계 판정 저장, 아래 JSONL과 원본 이미지의 export.
- 화면 질문은 **“표시된 사람이 표시된 칼을 실제로 들고 있습니까?”** 하나로 하고 `들고 있음 / 들고 있지 않음 / 판단 어려움`을 제공한다. 박스 수정은 필요한 경우에만 연다. 출처·세션·분할·프레임 정보는 batch에서 미리 채워 검수자가 매번 입력하지 않는다.
- 기존의 `CCTV형/라벨 정상` 판정으로 관계 정답을 만들지 않는다. detector/geometry는 박스 제안에만 사용하며 holding 정답을 자동 확정하지 않는다.

## 판정 의미

- `holding`: 해당 사람이 해당 칼을 실제로 쥐고 있음이 영상에서 분명하다. 정지해 있어도 포함한다.
- `not_holding`: 테이블/바닥의 칼, 집기 직전, 다른 사람이 든 칼 등 해당 사람이 들고 있지 않음이 분명하다.
- `uncertain`: 가림·작은 칼·흐림 등으로 판단할 수 없다. 음성으로 바꾸지 않으며 학습/지표에서 제외한다.
- 칼이 아닌 물체를 칼로 검출한 것은 관계 음성 정답과 구별한다. `invalid_detection` 작업 대기 항목으로 보관하고 관계 학습 export에 포함하지 않는다.
- 관계를 확정하기 전에 사람/칼 두 박스가 실제 대상을 올바르게 포함하는지 확인한다. 수동 작성 또는 사람이 확인/수정한 박스만 `ground_truth`로 export한다. 미확인 detector 박스는 `predicted`이며 GT 학습에 사용할 수 없다.

## 교환 형식 — JSONL schema 1

한 줄이 person–knife pair 한 개다. 문자열 ID는 참여자 실명 대신 별칭을 쓴다. 파일 경로는 export 이미지 루트 기준 상대 경로다. 좌표는 EXIF 회전하지 않은 원본 pixel의 `[x1,y1,x2,y2]`이며 오른쪽/아래는 exclusive다. 좌표 원점은 왼쪽 위다.

```json
{"schema_version":1,"pair_id":"session-a-f00120-person01-knife01","source_id":"p430-cam01","session_id":"capture-20261109-a","leakage_group_id":"recording-a-all-cameras","partition":"train","image_path":"images/capture-a/frame00120.jpg","image_sha256":"<원본 파일 SHA-256 64자리>","frame_index":120,"timestamp_s":6.0,"person_bbox_xyxy":[100,80,420,980],"knife_bbox_xyxy":[360,410,390,490],"holding_label":"holding","boxes_source":"ground_truth","annotation_origin":"human","annotation_version":"holding-v1"}
```

필수 필드와 enum은 위 예시를 따른다. `partition`은 `train / pilot / tuning / final_test`, `holding_label`은 `holding / not_holding / uncertain`, `boxes_source`는 `ground_truth / predicted`다. `annotation_origin=synthetic`은 코드 연결용 가상 자료 전용이며 사람이 검수한 자료처럼 표시하지 않는다.

선택 태그는 distance/viewpoint/occlusion/시나리오/박스 제안 출처/메모 정도로 제한한다. 학습을 위해 사용자 실명이나 추가 개인 정보를 export할 필요 없다.

### 누수와 독립성

- 촬영 전에 세션의 용도를 정한다. 같은 녹화의 모든 frame/crop/augmentation/재인코딩은 같은 partition에 둔다.
- 같은 상황을 CCTV와 스마트폰으로 동시에 찍었다면 같은 `leakage_group_id`로 묶는다.
- 같은 파일 해시·source/session·group이 서로 다른 partition에 걸치면 import가 거부된다. pair ID도 고유해야 한다.
- `uncertain`을 많이 제외한 경우 수와 이유를 남긴다. 최종평가 결과를 본 후 정답이나 split을 바꾸지 않는다.
- 사건 start/end 수동 GT는 기존 촬영/사건 양식을 따른다. 관계 프레임 라벨을 사건 정답으로 자동 치환하지 않는다.

## 전달 위치와 검증

PC13의 **새 ignored 경로** `data/hoi/holding-v1/` 아래 `pairs.jsonl`과 `images/`를 둔다. 예시가 `image_path=images/...`이면 `--image-root`는 `data/hoi/holding-v1`이다. 기존 team-server DB/config 파일은 건드리지 않는다.

```powershell
$env:PYTHONPATH='src'
python -X utf8 -m edge_threat_response.hoi validate --pairs data/hoi/holding-v1/pairs.jsonl --image-root data/hoi/holding-v1
```

위 검증을 통과한 뒤 train/tuning의 두 label 및 독립 그룹 수를 확인한다. 이미지 수만으로 학습 적합성이나 일반화 성능을 보증하지 않는다. YOLO 학습이 실행 중이면 HOI CUDA 학습을 동시에 시작하지 않는다.

## 학습과 B4 실행

```powershell
python -X utf8 -m edge_threat_response.hoi train --config configs/hoi/geometry.pc13.json --pairs data/hoi/holding-v1/pairs.jsonl --image-root data/hoi/holding-v1 --output-dir runs/hoi-g-v1
python -X utf8 -m edge_threat_response.hoi train --config configs/hoi/visual-geometry.pc13.json --pairs data/hoi/holding-v1/pairs.jsonl --image-root data/hoi/holding-v1 --output-dir runs/hoi-vg-v1
```

G는 union-relative 8좌표→32→16→1 MLP, VG는 MobileNetV3-Small의 576 visual feature+같은 8좌표→64→1이다. union crop은 여백10%·경계 clamp·비율 유지 letterbox224·ImageNet normalization을 사용한다. VG만 ImageNet 사전학습을 쓴다. AdamW/head .001·visual .0001·weight decay .0001, weighted BCE, batch32, 최대30epoch, tuning F1 기준 patience5, seed20261004다. threshold는 tuning에서 .05~.95(.05 간격)의 F1, recall, 낮은 FP 순으로 선택한다. 256은 별도 config/run으로 비교한다.

```powershell
python -X utf8 -m edge_threat_response.hoi evaluate --pairs data/hoi/holding-v1/pairs.jsonl --image-root data/hoi/holding-v1 --checkpoint runs/hoi-vg-v1/best.pt --partition tuning --boxes-source ground_truth --output-dir runs/hoi-vg-v1-eval-gt
$relationResult = python -X utf8 -m edge_threat_response.hoi score --checkpoint runs/hoi-vg-v1/best.pt --detections runs/video-detect/detections.jsonl --input recordings/pilot.mp4 --pipeline-config configs/replay/development-v2.example.json --output runs/video-relations.jsonl --device cuda:0 | ConvertFrom-Json
python -X utf8 -m edge_threat_response.replay_cli --input runs/video-detect/detections.jsonl --config configs/replay/development-v2.example.json --output-dir runs/video-b0-b4 --modes B0,B1,B2,B3,B4 --relations runs/video-relations.jsonl --relation-threshold $relationResult.threshold
```

score 명령에는 `etr-detect`가 저장한 `summary.json`과 동일한 원본 영상이 필요하다. checkpoint에 저장된 threshold를 명시해 replay한다. 원본 이미지가 없는 detector JSONL만으로 visual HOI를 재구성하지 않는다.

B4는 B3와 같은 nearest-person 후보·K/N·FSM을 사용하고 association의 참/거짓만 Holding score로 교체한다. wrong-person 후보와 detector FN은 관계 분류기 오류와 구분한다. B4-G와 VG는 별도 실험 폴더에서 각각 B4로 비교한다.

사건 평가 replay manifest에는 `modes=["B0","B1","B2","B3","B4"]`와 각 recording의 `relations`, `relation_threshold`, `media`를 추가한다. sidecar의 detector/config/media/classifier hash와 모든 frame/pair 대응을 검증한다. 기존 manifest의 기본 비교는 B0~B3다.
