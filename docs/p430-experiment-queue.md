# P430 자동 학습 큐

## 실행 범위

PC11·12는 1차 학습과 2차 개발 검증, PC13·14는 2차 학습과 1차 개발 검증을 담당한다. 이전 외부 CCTV 약 20% 혼합 목록, 초기 YOLO26n, 960·batch 8·seed·약증강을 유지한다. 12 epoch로 줄이고 초기 학습률만 0.00005와 0.00025로 비교한다. 학습을 마치면 매 epoch 체크포인트와 best/last를 SHA-256으로 구분해 기존 박스 평가와 COCO 평가로 점수를 계산한다. 동일 체크포인트의 별칭은 함께 기록한다. 기존 모델의 같은 검증 영상 예측은 저장 해시를 대조해 재사용한다. [기존 검증과 비교 조건](../reports/training/p430-t1-2026-11-20/report.md)

| 장비 | 학습 → 개발 검증 | 초기 학습률 | epoch당 추출 |
| --- | --- | ---: | ---: |
| PC11 | 1차 → 2차 | 0.00005 | 1,056 |
| PC12 | 1차 → 2차 | 0.00025 | 1,056 |
| PC13 | 2차 → 1차 | 0.00005 | 1,312 |
| PC14 | 2차 → 1차 | 0.00025 | 1,312 |

작은 칼 재현율이 기존 가중치보다 **두 촬영 모두** 높고, 각 촬영에서 전체 재현율 하락이 2%p 이하이며 음성 100장당 오탐 프레임이 1장 이하인 학습률만 후속 비교에 들어간다. 두 학습률이 통과하면 두 촬영 중 작은 칼 재현율 개선폭이 더 낮은 값을 기준으로 비교하고, 동률이면 개선폭 합계와 더 낮은 학습률을 차례로 확인한다. 해당 학습률의 두 컴퓨터가 같은 12 epoch·동일 데이터로 약증강을 제거한 조건을 각각 한 번 실행한다. 미통과 시 `SKIPPED`다. 결과 파일에는 confidence, AP50/AP50–95, 작은 칼/전체 재현율, 음성 오탐 비율, 정검출·오탐 박스 수, 가중치 해시와 각 단계 상태가 들어간다. [재사용하는 대안 추론 결과](../reports/evaluation/p430-alternatives-2026-11-21/report.md)

## 조회와 제어

운영 폴더는 네 PC의 `C:\Class6\edge-threat-response\runs\p430-auto-20261121-v1`이다. PC13의 `experiment_status.json`에 전체 상태와 비교 지표를 모은다. 각 PC의 `worker-status.json`에서 해당 PC의 실행 상태를 확인한다. 각 실행의 `attempt-01` 아래에 `invocation.json`, `stdout.log`, `stderr.log`, `progress.json`, `exit.json`과 결과를 보관한다. 전체 학습과 개별 평가는 서로 다른 작업이며 정상 완료한 작업의 해시를 재확인하고 건너뛴다.

```powershell
$etrQueue = 'C:\Class6\edge-threat-response\runs\p430-auto-20261121-v1'
Get-Content "$etrQueue\experiment_status.json"
```

큐를 일시중지하려면 **해당 PC**에서 `pause.request`를 만든다. 진행 중인 단계가 끝난 후 다음 단계를 보류한다. 네 PC 전체를 멈추려면 네 곳에 만든다. 다시 시작할 때 파일을 지우고 해당 PC에서 아래 실행을 호출한다. 기존 프로세스가 여전히 살아 있으면 작업 잠금으로 중복 시작을 막는다. PC 재부팅 후에도 같은 방식으로 재개한다.

```powershell
New-Item -ItemType File "$etrQueue\pause.request" -Force
Remove-Item -LiteralPath "$etrQueue\pause.request"
$env:PYTHONPATH = "$etrQueue\release\src"
$etrPython = 'C:\Class6\edge-threat-response\.venv-ml\Scripts\python.exe'
& $etrPython -m edge_threat_response.p430_queue $etrQueue launch worker $env:USERNAME.ToLower()
```

PC13의 수집기를 다시 띄울 때는 위 Python으로 `-m edge_threat_response.p430_queue $etrQueue launch collect 28770`을 실행한다. 수집기는 루프백에 바인딩하고 Tailscale Serve의 별도 TCP 포트를 통해 각 PC의 인증된 상태만 받는다. 검수 사이트와 분리돼 있다. [Tailscale TCP Serve](https://tailscale.com/docs/reference/tailscale-cli/serve#use-a-tcp-forwarder)

GPU 잠금 경합 또는 비정상 종료로 완료 영수증이 없는 단계는 최대 한 번의 새 시도를 허용한다. 진행 중인 하위 프로세스가 있으면 결과를 기다린다. OOM, 데이터 불일치, 평가 오류는 원래 로그를 보존하고 `FAILED`로 멈춘다. 중단된 단계의 부분 출력은 별도 attempt로 보존한다. 완료된 학습은 평가를 재개할 때 다시 수행하지 않는다.

## 신규 광학 줌 및 HOI 입력

PC13에서 **실제 검수와 개발용 분할 승인 뒤** 원본 폴더에 아래 manifest를 두고 마지막에 approval.json을 원자적으로 옮겨 둔다. approval은 `{"schema_version":1,"approved_development":true,"annotation_origin":"human","manifest_sha256":"<SHA-256>"}` 형식이다. 파일 해시는 `Get-FileHash -Algorithm SHA256`으로 얻는다. 내부 경로와 키는 GitHub에 올리지 않는다.

- **광학 줌**은 `zoom/manifest.json`의 `schema_version=1`, `partition=tuning`, `frames`를 사용한다. 각 프레임은 `image_path`(상대 경로), `image_sha256`, `source_video_sha256`, `pair_group`, `zoom`(1·3·5), `expected_in_view`, `in_view`, `holding_label`, `boxes`(정규화된 YOLO cx/cy/w/h, 0개나 1개)를 담는다. 비교할 원본 프레임은 기존과 같은 중앙 1920×1080으로 준비한다. 배율마다 동등하게 뽑힌 대조 촬영 묶음을 사용한다. 대상 이탈을 별도 집계하고 개발용 Recall·AP50·음성 오탐을 출력한다.
- **HOI**는 `hoi/pairs.jsonl`과 이미지 경로를 함께 준비한다. G와 VG를 기존 학습기로 순서대로 실행하고 검수 원본·결과 해시를 저장한다. [Holding 라벨 규격](hoi-annotation-contract.md)
- 입력이 없을 때 광학 줌은 `WAITING_FOR_DATA`, HOI는 `BLOCKED`다. 개발 지표 집계는 독립 평가·B0~B4 사건 측정·Orin/GPIO 검증과 별개다.

## 검증

표준 라이브러리와 기존 학습·GPU 잠금·박스 평가·HOI 구현을 사용한다. `tests/test_p430_queue.py`에서 양쪽 세션 통과 조건, FP 프레임 단위 상한, 완료 결과 재개와 해시 변경, 오류 후 재실행 방지, 결과 저장을 검사한다.
