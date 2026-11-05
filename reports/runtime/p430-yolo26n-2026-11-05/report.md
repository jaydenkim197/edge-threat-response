# P430·YOLO26n Orin 배포 준비

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
