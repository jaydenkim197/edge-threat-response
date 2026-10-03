# 통제 촬영과 사건 단위 평가

상태: 평가기와 가상 replay 연결 `IMPLEMENTED`/PC `VERIFIED`. 촬영·정답 기록 절차는 준비됐으며, 거리값·매칭 허용 오차·반복 횟수·최종 동결은 첫 pilot 촬영 후 확정한다.

## 1. 진행 순서와 파일

촬영 담당자는 [촬영표](../templates/experiments/capture-sheet.md)를 ignored `data/experiments/<experiment-id>/`에 복사해 작성한다. 같은 폴더에 원본 영상·해시·시간축 정보와 수동 [사건 정답](../templates/experiments/ground-truth.template.json)을 보관한다. 이름 대신 참여자/검수자 별칭을 쓰고, 동의·보존 정책은 촬영 전에 확인한다. 학습 데이터셋 웹 검수의 두 질문은 이미지 품질 검수이며 이 사건 시작·종료 annotation을 대신하지 않는다.

1. **Pilot**: 실제 카메라 설치 높이·화각·가시 영역과 모형 knife의 크기/가림을 확인한다. 첫 영상으로 거리 구간과 시작/종료 frame 해석을 맞춘다.
2. **Tuning**: pilot 이후 별도 세션에서 detector threshold, 확장 bbox 비율, K/N, rearm과 매칭 규칙을 고른다. 여기까지는 개발·오류 분석에 사용한다.
3. **Freeze**: 거리·매칭 허용 오차·annotation version, 모델 SHA-256, 입력 규격, 판단 config, metric 코드 commit과 최종평가 세션 목록을 촬영표의 동결 기록에 남긴다.
4. **Final test**: 동결된 동일 detector의 detection JSONL을 세션별로 한 번 생성하고 B0~B3에 재사용한다. 최종 결과를 보고 파라미터를 변경하면 새 실험 버전과 새로운 미사용 평가 세션이 필요하다.

## 2. 촬영 유형

| ID | 안전한 촬영 내용 | 정답·관찰 포인트 |
|---|---|---|
| P1 | 사람이 모형 knife를 들고 정지 | 이동이 없어도 positive. 소지 시작과 종료를 수동 기록 |
| P2 | 들고 정해진 동선을 이동 | 같은 사건이 유지되는 동안 재경보·놓침·지연 확인 |
| P3 | 테이블의 모형 knife를 집고 내려놓음 | 테이블 위 구간은 negative, 집어 든 구간만 positive |
| P4 | 부분 가림; 가능하면 두 사람 중 한 명만 소품을 듦 | 가림·다른 사람 bbox로 인한 오류 확인. 두 사람 조건은 별도 태그로 기록 |
| N1 | 모형 knife만 놓여 있음 | 사건 0개. 사람 없는 칼 탐지의 경보 확인 |
| N2 | 사람이 놓인 knife 근처를 지나감 | 집지 않으면 사건 0개. geometry의 한계를 확인하는 hard negative |
| N3 | 사람이 놓인 knife 옆에 정지 | 집지 않으면 사건 0개. bbox만으로 소지를 증명하지 못함을 평가 |
| N4 | 스마트폰·지갑·카드 등 안전한 유사 소품을 듦 | 실제 knife 사건 0개. 영상에서 검출이 생겼는지는 나중에 확인 |
| N5 | 모형 knife를 계속 든 채 부분 가림/짧은 검출 누락 조건을 만듦 | **Positive robustness trial**. 검출이 끊겨도 같은 실제 사건의 정답을 유지 |

N5라는 기존 ID는 유지하되 N1~N4와 같은 음성으로 집계하지 않는다. N4의 인위적인 false-detection 주입과 N5의 JSONL dropout 주입은 별도 synthetic fault test로 기록한다. 그런 주입을 실제 카메라의 자연 발생 오류로 보고하지 않는다.

P1~P4·N1~N5 각각 Near/Medium/Far를 촬영표에 배치한다. Near/Medium/Far의 미터값과 최소 반복 횟수는 지금 정하지 않는다. Pilot 이후 모든 비교 조건에서 같은 정의를 쓴다. 거리 측정은 **카메라의 수직 투영점에서 사람의 지정 위치까지 바닥면 거리**로 통일하고 카메라 높이·관찰 각도도 기록한다. 조도는 Normal을 기록하며 Low-light는 선택 실험이다. 선택하지 않은 조도에 대한 일반화를 주장하지 않는다.

## 3. 세션 단위 분리

- 촬영 전에 각 세션을 `pilot / tuning / final_test` 중 하나로 등록한다. 같은 세션의 모든 원본·crop·augmentation·연속 frame·재인코딩본은 같은 partition에 둔다. 이미지별 무작위 분할은 하지 않는다.
- 연속 촬영을 파일만 나눴거나 같은 녹화의 파생본이면 session ID를 바꿔도 같은 `leakage_group_id`를 유지한다. 평가기는 session 또는 관련 group이 partition을 교차하면 거부한다.
- 촬영 날짜·camera setup·장소·참여자·동선으로 실제 독립성을 확인한다. 가능하면 최종평가 세션은 다른 날 독립적으로 다시 촬영한다. 같은 카메라/장소를 공유했다면 그 한계를 보고한다.
- T1 학습에 쓸 직접 촬영 자료는 별도 `train` 세션으로 사전에 분리한다. 본 사건 평가기의 partition에는 train을 넣지 않는다. 그 자료의 frame이 tuning/final test로 넘어가지 않도록 source manifest에 동일 group을 기록한다.
- 최종평가 정답을 영상만 보고 작성할 수는 있지만, 최종 detector/pipeline 출력이나 성능을 파라미터 선택에 사용하지 않는다.

## 4. 수동 사건 정답

한 영상의 시간 원점과 source ID는 detection JSONL과 동일하게 쓴다. 프레임 번호는 원본 decode의 0-based index다. 재생 프로그램의 1-based 표시를 그대로 복사하지 않는다. 가변 FPS이면 `frame/FPS`로 추정하지 않고 실제 프레임 timestamp를 기록한다.

- `start_frame`: 사람이 모형 knife를 들기 시작한 첫 positive frame.
- `end_frame`: 내려놓거나 연관이 끝나기 직전의 **마지막 positive frame**. 두 frame 번호는 포함 구간이다.
- `start_s`: 첫 positive frame의 영상 timestamp.
- `end_s`: 첫 non-positive frame의 timestamp. 마지막까지 사건이면 원본 영상의 검증된 종료 경계. 시간 구간은 **[start_s, end_s)**다.
- 관찰 `start_s/end_s`는 평가한 원본 영상의 실제 범위다. 마지막 검출 sample 시각이나 PC 실행 시간을 영상 길이로 대체하지 않는다. 샘플링·잘린 입력의 범위와 원본 길이를 대조한다.
- negative 영상도 recording을 등록하고 `events: []`로 명시한다. 그래야 음성 관찰시간과 오경보 분모가 누락되지 않는다.
- 처음 정답을 작성하는 사람이 detector 결과를 보지 않고 기록하고, 경계/모호한 사례는 다른 팀원 한 명이 확인한다. 합의하지 못한 구간은 reason을 남긴 `ignore_intervals`로 두되, positive 구간과 겹치면 평가기가 거부한다. 모호한 시행 전체를 제외하면 수와 이유를 별도 보고한다.
- 순간 detector FN·missing frame·detector error를 이유로 실제 사건 정답을 끊지 않는다. 완전 가림으로 원본에서도 사건을 판단할 수 없으면 pilot에서 annotation 규칙을 먼저 합의한다.
- MVP는 source-level event를 판단한다. 동시에 여러 사람이 소품을 들면 사람이 바뀌더라도 연속 positive 구간을 **하나의 사건**으로 합친다. 개인별 동시 사건을 별도로 넣어 recall을 평가하지 않는다.

정답은 detector bbox로 자동 생성하지 않는다. 특히 N2/N3은 사람이 칼 근처에 있다는 사실만으로 positive로 바꾸지 않는다. 시스템의 `CONFIRMED`는 기하·시간 조건의 확인이며 실제 소지/의도 판별 성공을 뜻하지 않는다.

## 5. 동일 매칭과 지표

[매칭 설정 템플릿](../configs/evaluation/manual.template.json)의 early/late tolerance는 첫 pilot 후 채운다. `null`인 준비 파일은 실행되지 않는다. 가상 검증의 0초 설정은 실제 허용 오차 결정이 아니다.

평가기 `etr-evaluate`는 B0~B3의 **CONFIRMED 진입당 metadata 사건**을 경보 후보로 세고, 다음 규칙을 네 조건에 동일하게 적용한다.

1. 예측 시각을 시간순·ID순으로 정렬한다. ignore 구간의 예측은 분자와 분모에서 제외한다.
2. 허용 창 `[truth_start - early, truth_end + late)` 안의 미매칭 정답 중 종료가 가장 빠른 사건에 일대일로 대응한다. 허용 창이 겹쳐도 하나의 경보는 정답 하나에만 대응한다.
3. 매칭 쌍은 TP, 미매칭 정답은 FN, 미매칭 경보는 FP다. 이미 대응한 사건의 허용 창 안의 추가 경보는 `duplicate`; 어떤 허용 창에도 없으면 `background` FP로 구분한다. **반복 경보도 precision의 FP에 포함**한다.
4. Precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2TP/(2TP+FP+FN). 분모가 0이면 `null`(CSV 빈칸)이며 1.0을 임의로 넣지 않는다.
5. 전체 오경보/h는 모든 FP를 scored 영상시간(관찰시간 − ignore)에 나눈다. 별도 background 오경보/negative-hour는 background FP를 모든 허용 창·ignore를 뺀 영상시간에 나눈다. 각 분모를 결과에 함께 남긴다.
6. 매칭된 경보의 `prediction_time - truth_start`를 판단 지연으로 보고한다. 평균·중앙값·선형보간 p95·최대·매칭 수를 기록한다. early 허용 창에서 얻은 음수 지연도 그대로 남긴다. FN은 지연 통계에 들어가지 않으므로 recall과 함께 해석한다.

여러 영상은 partition별 TP/FP/FN과 영상시간을 합친 **micro 지표**로 비교하고 지연은 매칭 쌍 전체를 모아 계산한다. tuning과 final_test를 섞어 단일 성능으로 내지 않는다. 시나리오/세션별 원시 매칭·오류는 `evaluation.json`에 남는다.

이 지연은 **영상 시간축에서의 CONFIRMED 판단 지연**이다. PC replay의 처리시간이나 실제 카메라→GPIO 지연을 뜻하지 않는다. action adapter 오류 수도 함께 보고하며 metadata가 존재한다고 GPIO 동작을 확인한 것으로 보지 않는다. 실제 end-to-end 경보는 Orin에서 별도 측정한다.

## 6. 실행과 결과 확인

가상 데이터로 평가기 자체를 확인하는 명령이다. 로컬 한글 경로에서는 editable install 대신 module 실행을 쓸 수 있다. 출력 폴더가 이미 있으면 새 실험 ID와 manifest의 `replay_dir`로 바꾼다.

```powershell
$env:PYTHONPATH = 'src'
.\.venv-ml\Scripts\python.exe -m edge_threat_response.replay_cli --input tests/fixtures/replay/basic.jsonl --config configs/replay/development-v2.example.json --output-dir runs/event-evaluation-synthetic-v1/replay
.\.venv-ml\Scripts\python.exe -m edge_threat_response.evaluate_cli --ground-truth tests/fixtures/evaluation/ground-truth.json --replay-manifest tests/fixtures/evaluation/replay-manifest.json --policy configs/evaluation/synthetic.example.json --output-dir runs/event-evaluation-synthetic-v1/evaluation
```

실제 촬영에는 작성한 ground truth, 매칭 설정과 [replay 연결표](../templates/experiments/replay-manifest.template.json)를 사용한다. 연결표의 경로는 그 JSON 파일 위치 기준이다. 모든 영상의 B0~B3 `summary.json/events.jsonl`이 있어야 하며, 입력/config SHA-256·source·frame/timestamp·사건 개수·model/version·policy가 맞지 않으면 실패한다. 영상별 run ID는 달라도 판단/model 설정은 동일해야 한다.

`comparison.csv`는 partition×B0~B3 요약, `evaluation.json`은 일대일 대응·반복/배경 FP·FN·ignore·입력 해시의 원시 증거다. evaluator의 fingerprint 확인은 실제 모델 binary의 동일성을 단독 증명하지 않는다. `etr-detect` 실행의 weight SHA-256과 입력 영상 hash를 동결 기록에 함께 둔다. 실제 최종평가에는 policy status `frozen`과 승인된 정답 version을 사용한다.
