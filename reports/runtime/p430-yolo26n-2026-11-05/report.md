# P430·YOLO26n Orin 연결 검증

**실제 카메라 main/sub에서 YOLO26n/B3 각각300frame 실행과 Orin 모니터 탐지 표시를 확인했다.** 계정 수정으로401을 해결했고 open timeout5→20초 수정으로 디코딩을 연결했다. 원본 실제 사건 정답이 없는 pilot이므로 정확도나 최종detector 채택 결과가 아니다.

| 실제 입력 | Probe | YOLO/B3 | 사건/snapshot | 처리 p95 |
|---|---:|---:|---:|---:|
| sub640×360 | 120frame 통과 | 300valid / error0 | 4 / 4 | 78.07ms |
| main3840×2160 | 60frame 통과 | 300valid / error0 | 2 / 2 | 87.96ms |

처리 p95는 **decode가 완료된 프레임의 inference/판단/actions**이며 camera exposure·decode·대기열·로그 write·물리GPIO를 포함한 end-to-end 지연이 아니다. 두 run은 같은 시각 영상이 아니고 event 수를 서로 정확도 비교하지 않는다. cold model load가 max에 포함됐으며 정식FPS 벤치마크는 아니다. main의 decoded797/dropped496, sub389/dropped88은 queue1의 최신frame 정책과 startup/inference 속도 차이를 포함한다. 이를 네트워크 packet loss로 해석하지 않는다.

별도 탐지 표시기는 Orin X11/DP 모니터에서30frame smoke 후591frame까지 지속 갱신과 활성 창을 확인했고, 사용자도 실제 움직이는 탐지를 확인했다. core8a52fc8 위에 현재 `tools/view_live_detection.py`와 같은 candidate 파일을 복사해 실행했다. 미리보기에는 HOI/FSM/물리GPIO가 없고 영상/프레임을 저장하지 않는다. viewFPS는 표시 루프의 순간 값이며 연구성능 지표가 아니다. 종료 요청 시 원격 접속이 끊겨 Q/Esc를 안내했고 원격 종료 완료는 확인하지 못했다.

원시 위치(Orin): `runs/p430-yolo26n-20261105-v1/`의 `extended-open-diagnostic.json`, `sub-probe-fixed/`, `main-probe-fixed/`, `sub-live-launch.json`, `main-live-launch.json`, `preview-smoke-status.json`, `preview-live-process.json`, `preview-live-status.json`. 실제pipeline 출력은 `runs/p430-live-raw-20261105-183820-042866/`, `runs/p430-live-raw-main-20261105-184044-759258/`에 있다. 마지막 GUI 상태 파일은 계속 갱신될 수 있으며 논문용 고정 run과 구분한다.

검증: core8a52fc8 PC13 `.venv-evaluation-20261104`의184 tests가17.553초/skip0 통과했다(`runs/qa-p430-20261105-evaluation-env.log`). 관련RTSP3 tests·로컬viewer compile/help·실제GUI smoke가 통과했다. 로컬 전체184개는 기존review HTTP Win10053 오류1/skip2(해당7 tests 재시도도 오류1), Orin 전체184개는 Ultralytics corrupt-image path의 선택pi_heif 누락 오류1/skip2로 미통과다. Orin 로그는 `target-full-tests.log`에 남겼고 자동설치·글로벌환경 변경으로 우회하지 않았다.

구성/접속은 [한 장 연결 기록](../../../docs/cctv-local-network-setup.md), 재실행은 [P430 안내](../../../docs/p430-camera-setup.md)를 따른다. 아래는 인증 해결 **이전**의 첫 파일 GPU 배포 기록이다.

## 초기 배포 기록 — 인증 해결 전

**신규 RAW-R1-n의 Orin GPU 파일 입력은 통과했다. 카메라 영상은 인증401로 아직 수신하지 못했다.**

| 항목 | 확인 결과 |
|---|---|
| P430 서비스 | Save 후554/8000/9000 open, RTSP OPTIONS200 |
| 영상 요청 | 기존 비공개 설정의 sub probe2회0frame, 동일TCP Digest DESCRIBE401 |
| 신규 weight | PC13 RAW-R1-n50epoch 완료, 전송 전후SHA 일치 |
| Orin 통합 | COCO26n person+RAW-R1-n knife,640/FP32,53frame valid53, detection59 |
| B3 출력 | event2, snapshot2, mock 경보, action error0, exit0 |
| 실제CCTV/HOI/GPIO | 미검증. 최종detector 선정/정확도/FPS/무기한 운용 결과 아님 |

신규 checkpoint는5,368,446bytes, SHA256 `c8006bf63e7d5ab9a71f89a0794c7d9723dc493970ba34918d51aea2480a7775`다. 기존 person weight SHA는 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`이며 source c2daa70과 기존Orin native venv를 사용했다. process-only THP disable을 적용했다. fixture는 기존 train-derived53frames이므로 detection/이벤트 수를 정확도나 독립 평가로 해석하지 않는다. 첫 model load가 포함돼 이 보고서로 카메라 FPS를 제시하지 않는다.

Orin의 `runs/p430-yolo26n-20261105-v1/`에 config·runner·probe 실패 기록·file smoke·verification.json을 보관했다. 기성 COCO 단일 모델과 RAW composite는 다른 config/model provenance를 사용한다. 인증 성공 후 기존 RTSP probe와300frame runner로 실제 입력을 검증한다. [실행 안내](../../../docs/p430-camera-setup.md).

비공개 파일은 `data/local/p430-connection.json`이며 값·사용자명·비밀번호·인증 헤더·원본 카메라 이미지를 이 보고서에 넣지 않았다. 학습 원본/queue/검수DB·기존 모델·OS/드라이버/네트워크는 변경하지 않았다. 실제Holding 학습 weight가 없으므로 B4를 켜지 않았고 GPIO는mock이다. WAN 제거와 실제 장시간/재연결은 후속 검증이다.
