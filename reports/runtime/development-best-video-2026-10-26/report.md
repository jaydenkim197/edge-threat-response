# 새 개발 weight의 PC 영상 통합 검증 — 2026-10-26

**새 knife best.pt + COCO person detector가 기존 영상→탐지→B0~B3→경보/metadata/snapshot 경로에 연결되는 것을 PC13에서 검증했다.** 기존 runtime 코드는 수정할 필요가 없었다. 재현 가능한 통합 검증 driver만 추가했다. 결과는 `PASSED / PC INTEGRATION`이며 실제 사건 성능·Orin 검증은 아니다.

사용자가 제공할 촬영 영상이 없다고 확인했으므로, 승인된 SOHAS development **train 이미지3개**와 빈 화면을 조합한 53프레임 영상을 사용했다. 연속 촬영·사람 움직임·거리·카메라 조건을 검증한 것으로 해석하지 않는다. 수치/hash/설정은 [evidence.json](evidence.json)에 있다.

## 환경과 고정 조건

- PC13 Windows / RTX3060 12GB / driver560.94 / Python3.12.4 / torch2.6.0+cu124 / Ultralytics8.4.152 / OpenCV4.11.0.86. 실제 CUDA device0 실행이다.
- Person: local `yolo26n.pt`, raw class0→`person`; SHA-256 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
- Knife: `sohas-reviewed-development-20261026-smallscale-v1/weights/best.pt`, raw class0→`knife`; SHA-256 `d8eff85efff890041d67f9aea80d3d0d7a9530312eb7c2da2baace5e3840c043`.
- 640px, person confidence .5 / knife .25, geometry schema2 expanded ratio .25, K2/N3, clear rearm2. 모두 development integration 설정이며 연구 최종값이 아니다.
- 필요한 local weight의 존재/hash/class 이름을 먼저 확인하며 자동 weight download는 하지 않는다. 기존 학습 run의 hash-bound 승인을 검사하고 val/test 이미지는 추론하지 않는다. 승인 검증에서는 무결성 hash만 읽는다.

## 입력과 기대 경로

driver는 train137개를 고정 confidence로 probe하여 person+knife 연관, person 없는 knife, person 있고 knife 없는 각 범주에서 confidence가 높은1장을 고른다. 모델이 반응하는 이미지를 의도적으로 선택한 **연결 검증 fixture**이며 무작위 성능 표본이 아니다. 사람 판정도 새로 작성하지 않는다.

FFV1 lossless AVI, 640×640, 10fps, 53프레임을 사용했다. 각 프레임에 번호를 넣었으며53개 pixel hash가 서로 다름, encode 전/decode 후 전 프레임 일치, timestamp=frame_index/10을 확인했다. 영상 SHA-256: `b16a569242f37e771f268a6b3d9b1e0ad3c9f98daee85c51d22d0461d2141e6e`.

| frame index | 구성 | 검증 목적 |
|---|---|---|
| 0–3 | blank | CLEAR |
| 4–7 | person / knife 없음 | person만으로 event 생성하지 않음 |
| 8–11 | knife / person 없음 | spatial 유무에 따른 경로 차이 |
| 12–17 | blank | 해제·rearm |
| 18–25 | person+knife 연관 | CONFIRMED·지속 중 경보 중복 억제 |
| 26–31 | blank | cooldown·rearm |
| 32 | person+knife 연관1 frame | K-of-N과 즉시 판단의 차이 |
| 33–38 | blank | window 만료·rearm |
| 39–46 | person+knife 연관 | 재등장 시 새 event |
| 47–52 | blank | alarm 해제 |

## 실행 결과

실제 모델 추론으로 **53/53 valid, canonical detection59개**를 생성했다. 동일 JSONL을 B0~B3 replay에 전달하고 네 조건의 input hash가 같음을 확인했다.

| mode | event frame index | event 수 |
|---|---|---:|
| B0 | 8,18,32,39 | 4 |
| B1 | 9,19,40 | 3 |
| B2 | 18,32,39 | 3 |
| B3 | 19,40 | 2 |

이는 fixture의 기대 제어 동작과 일치한다는 뜻이며, 실환경 오경보를 절반으로 줄였다는 실험이 아니다. 인공 영상의 frame 지연을 실제 GPIO latency로 해석하지 않는다.

- **Live B3:** event2 / JPEG snapshot2 / action error0. CLEAR·CANDIDATE·CONFIRMED·COOLDOWN을 모두 통과했다. activate frame19/40, deactivate27/48이다.
- **Snapshot binding:** frame19/40을 영상에서 재decode하고 같은 JPEG encoder로 생성한 bytes가 저장 snapshot과 완전히 일치했다. 프레임 번호가 달라 잘못된 프레임 저장을 검출할 수 있다. 첫 snapshot의 frame019와 내용도 눈으로 확인했다.
- **CLI:** 기존 `etr-run.exe`에서도53frame/event2/snapshot2/action error0이다. source ID까지 명시해 detection-only·live API·CLI JSONL의 SHA-256이 같음을 확인했다: `4d92ee6524860051e2973ae77b864b6aa68fd8d726041c4451ff4a3be94429da`. CLI는 source ID 생략 시 file stem을 사용하므로 비교 시 같은 ID를 전달한다.
- **Required knife component 오류 주입:** frame21만 예외를 넣으면 valid52/error1이다. person의 부분 결과도 버려 error frame의 detections는 비었고 K2/N3로 CONFIRMED를 유지했다. 21/22 연속 예외는 valid51/error2, 22에서 COOLDOWN 진입, clear rearm 후 재등장에서 다시 확인했다. 두 시험 모두 event19/40만 발생, snapshot2/action error0이다. 실제 runtime 고장을 관측한 것이 아니라 adapter 경계에 의도적으로 예외를 넣은 시험이다.

## 재현과 보관

source base는 `baf61069649ec8bf2b3b20e605ea20616120c1f8` + 신규 driver다. 실제 실행한 LF script SHA-256은 `3b1b71eb256ab6724bf17e9176233c4bf40f1b93c9b808c4668db3442ab63567`이며 본 보고서를 포함한 commit에 driver를 보존한다. 기존 runtime·검수 사이트/DB·학습 설정은 변경하지 않았다.

PC13 raw: `runs/runtime/best-pc-video-20261026-v1/`. detector/pipeline config, fixture 영상, frame recipe/probe, `detection/`, `replay/B0~B3/`, `live-b3/`, `single-error/`, `double-error/`, `cli-b3-source-bound/`, `integration.json`, `cli-verification.json`을 보관한다. 같은 fixture의 별도 실행이므로 event를 합산하지 않는다. 이미지·영상·snapshot·weight는 Git에 넣지 않는다.

```powershell
$env:PYTHONPATH = 'src'
python tools/verify_development_video.py `
  --prepared data/processed/sohas-reviewed-development-20261026-smallscale-v1 `
  --person-weights yolo26n.pt `
  --knife-weights runs/training/sohas-reviewed-development-20261026-smallscale-v1/weights/best.pt `
  --expected-person-sha256 9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef `
  --expected-knife-sha256 d8eff85efff890041d67f9aea80d3d0d7a9530312eb7c2da2baace5e3840c043 `
  --device 0 --output runs/runtime/<fresh-id>
```

fresh output만 허용한다. 이전 출력을 삭제/덮어쓰고 재실행하지 않는다. 별도 CLI 검증은 생성된 detector/pipeline config와 영상을 `etr-run`에 전달하고 `--source-id train-derived-integration`을 명시했다. 다른 checkpoint나 CPU/Orin으로 변경하면 이번 결과를 그대로 승계할 수 없다.

검증: detector3/runtime2/replay CLI1 tests, 전체138 tests, driver compileall 통과. 실제 GPU driver 실행·CLI·lossless decode·snapshot byte 비교도 통과했다. 고정된 runtime의 `half=False` 호환 인수에 deprecated 경고가 있었으나 실행은 성공했고 package를 업데이트하지 않았다.

## 다음 검증 경계

새 best.pt의 PC 연결은 완료했다. 독립 실영상·수동 event 정답에 따른 precision/recall/오경보/지연, Orin runtime, 카메라, GPIO, 네트워크 단절·장시간 안정성, 최종 detector/parameter 고정은 남는다. 신규150장은 계속 검수·별도 승인 대기이며 이번 작업에서 추가 학습하지 않았다.
