# P430 연결과 촬영 준비

## 2026-11-05 실제 LAN 진단

**계정 수정 후:** 카메라 자체 계정으로 다시 저장한 뒤 authenticated DESCRIBE200/H264를 확인했다. 초기5초 제한 probe는0frame였으나,20초 제한 진단은6.210초에 열려640×360/광고FPS10·30frame를 수신했다. 공통 RTSP 수신기의 open timeout만5→20초로 수정하고 read timeout5초·queue1·인증정보 비노출은 유지했다. 광고FPS/초기 버퍼의 빠른 반환은 실제 추론FPS가 아니다. 아래401은 수정 전 기록이다.

**후속 실측:** 사용자가 Save 실행·화면 재진입 후 체크 유지를 확인했고, Orin에서554/8000/9000 open 및 RTSP OPTIONS `200 OK`를 확인했다. 포트 활성화 문제는 해결됐다. 이후 저장된 비공개 계정으로 sub stream decode를 시도했으나0frame이고, 별도 동일 TCP 연결의 Digest 인증 DESCRIBE도 `401 Unauthorized`였다. 현재 남은 gate는 카메라 계정·권한 확인이다. 이것만으로 decoder 불량이나 모델 성능을 판정하지 않는다.

계정 입력은 Orin의 `python3 ~/edge-threat-response/runs/setup-p430-private.py`를 사용한다. 실제 카메라 계정과 비밀번호를 입력하며 SSH/Reolink 클라우드 계정과 구분한다. 별도 카메라 계정이 없다면 사용자명은 기본 `admin`인지 User Management에서 확인한다. 비밀번호는 두 번 숨김 입력하고, URL을 percent-encode해 mode0600 임시 파일을 원자적으로 교체한다. 값은 출력·Git에 넣지 않는다.

RAW-R1-n은 PC13에서50epoch가 완료돼 별도 모델 경로로 복사했다. 전송 SHA 일치와 Orin GPU53frame/B3/mock alarm/snapshot 연결을 확인했으며 최종 D* 채택이나 실제 CCTV 검증이 아니다. [배포 범위·증거](../reports/runtime/p430-yolo26n-2026-11-05/report.md).

아래는 Save 이전 초기 진단이며 현재 포트 상태는 위 후속 실측을 우선한다.

Orin 유선 IP `192.168.0.10/24`에서 P430 `192.168.0.4`로의 직접 경로·ARP의 장비 MAC 일치·ping 2/2를 확인했다. 노트북 `192.168.0.6`과 Orin 양쪽에서 TCP9000은 열려 있고, TCP554/8000/80/443은 연결 거부였다. 따라서 LAN 연결은 확인됐지만 RTSP/ONVIF 서비스·인증·영상 수신은 아직 미검증이다. IP 변화의 원인을 확정하거나 이전 `.2` 검사 결과를 재사용하지 않는다.

Reolink Client 화면에는 RTSP554/ONVIF8000이 체크돼 있다. Save가 화면 아래 잘려 있고 자동 입력 좌표가 맞지 않아 저장 성공을 확인하지 못했으며, 사용자의 Save 실행·화면 재진입 후 유지 확인을 요청했다. 체크 표시만으로 서비스가 활성화됐다고 판정하지 않는다. 공식 절차는 Device Settings → Network → Advanced → Server Settings에서 설정 후 Save다([제조사 안내](https://support.reolink.com/articles/900000621783-How-to-Configure-Reolink-Ports-Settings/)).

먼저 저장 후 두 장비에서554를 재검사하고, 열리면 비공개 계정 설정으로 sub/main decode를 검증한다. 현재 Orin의 `data/local/p430-connection.json`은 없으며 비밀번호를 추정하거나 SSH 비밀번호를 카메라에 재사용하지 않는다. `rtspsrc`와 `nvv4l2decoder`는 설치돼 있지만 ffprobe·avdec_h264는 발견하지 못했다. 플러그인 존재는 실제 카메라 디코딩 성공을 뜻하지 않는다. 공유기/Orin 네트워크·OS·드라이버와 PC13 학습은 변경하지 않았다. WAN 제거 시험은 LAN SSH 경로와 영상 수신을 확보한 후 별도로 진행한다.

아래는 최초 연결 준비 절차이며 현재 상태는 위 실측을 우선한다.

2026-11-05 사용자가 **Reolink P430의 영상 출력 확인, 당일 네트워크 연결 예정**을 알려왔다. 이는 사용자 확인이며 PC13/Orin의 RTSP 검증 결과는 아니다. P430은 공식 지원 목록에 RTSP 지원 제품으로 기재돼 있다. [Reolink 지원 목록](https://support.reolink.com/articles/900000617826-Which-Reolink-Products-Support-CGI-RTSP-ONVIF/), [RTSP 설정 안내](https://support.reolink.com/articles/900000630706-Introduction-to-RTSP/).

## 연결 확인

1. PC13 또는 Orin에서 접근 가능한 네트워크에 연결하고 카메라 설정에서 RTSP를 활성화한다. 카메라 앱에서 보인다는 사실과 RTSP 접근 가능 여부는 따로 확인한다.
2. PC13의 ignored `data/local/p430-connection.json`에 `rtsp_url`과 별칭 `source_id`를 저장한다. 실제 계정/비밀번호·URL은 채팅·Git·명령행에 붙이지 않는다. 파일 내용은 `{"rtsp_url":"실제 RTSP URL","source_id":"p430-pilot"}` 형식이다.
3. 다음 명령으로 120개 decode frame의 크기·시간축·drop을 확인한다. 출력 폴더는 매번 새 경로로 지정한다.

```powershell
$env:PYTHONPATH='src'
python -X utf8 tools/check_rtsp.py --connection data/local/p430-connection.json --output-dir runs/p430-probe-v1 --max-frames 120
```

검사기는 URL/인증정보와 원본 이미지를 결과에 저장하지 않는다. timeout/연결 오류는 실패로 기록한다. source queue는 최신1개만 유지하며 이전 frame을 버린 수를 기록한다. host decode 완료 시각을 사용하므로 sensor capture나 실제 GPIO 지연으로 해석하지 않는다.

Orin에서는 위 명령을 현재 source worktree의 `tools/check_rtsp.py`와 `.venv-orin/bin/python`으로 실행하며, `OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp'`를 설정한다. 비공개 설정은 `~/edge-threat-response/data/local/p430-connection.json`에 둔다. 계정 수정 후에는 기존 실패 probe를 덮어쓰지 않고 새 출력 경로를 사용한다.

## detector 연결

현재 Orin의 배포 구성은 `runs/p430-yolo26n-20261105-v1/`에 준비돼 있다. 인증·실제 decode가 성공한 뒤 아래 명령으로 제한된300frame 실행을 한다. `--preset raw`는 신규 RAW-R1-n knife+COCO26n person, `--preset coco`는 기성 COCO26n의person/knife다. 각각 다른 pipeline model provenance와 새로운 출력 경로를 사용하며 자동 시작 서비스나 무기한 운용은 아직 설정하지 않았다.

```bash
~/edge-threat-response/.venv-orin/bin/python \
  ~/edge-threat-response/runs/p430-yolo26n-20261105-v1/run-live.py \
  --preset raw --max-frames 300
```

이 실행기는 GUI 영상 표시기가 아니다. detector JSONL·판단·사건 metadata·snapshot을 생성한다. 실제 학습된 HOI checkpoint가 아직 없으므로 B3를 사용하고 GPIO는 mock이다.

비공개 파일을 읽어 현재 프로세스의 환경변수로만 전달한다. 출력이나 Git에 값을 남기지 않는다.

```powershell
$env:P430_RTSP_URL = (Get-Content data/local/p430-connection.json -Raw | ConvertFrom-Json).rtsp_url
python -X utf8 -m edge_threat_response.detect_cli --help
python -X utf8 -m edge_threat_response.detect_cli --rtsp-env P430_RTSP_URL --source-id p430-pilot --max-frames 300 --detector-config configs/detection/composite.development.example.json --output-dir runs/p430-detect-v1
```

detector config의 weight 경로는 실제 고정 파일로 설정해야 한다. 설치된 `etr-detect`도 같은 명령이다. `etr-run`에서는 pipeline config와, B4일 때만 `--relation-checkpoint`를 추가한다. 지금의 GPIO 출력은 mock이며 카메라 연결이 물리 경보 검증을 대신하지 않는다.

## 촬영과 평가

- 카메라 높이·관찰 방향·화각/줌·해상도·코덱·설정 FPS를 실제로 기록한다. 아직 관찰 거리나 small-knife 픽셀 목표를 임의로 정하지 않는다.
- 작은 칼 정보가 사라지지 않도록 원본 녹화는 메인 스트림을 우선 확인한다. 학습 입력640/960과 카메라 원본 해상도는 구분한다.
- **현재 RTSP 입력은 원본 영상 recorder가 아니다.** 카메라/클라이언트의 녹화·export 기능으로 원본 clip과 실제 timestamp를 확보한 뒤 파일 기반 B0~B4 공통 평가를 수행한다. snapshot만으로 연속 사건 평가를 하지 않는다.
- 안전한 모형 소품을 쓰고 참여 동의 후 P1~P4/N1~N5를 촬영한다. train/pilot/tuning/final과 동시 스마트폰 영상의 leakage group을 촬영 전에 정한다.
- 실제 연결 후 카메라 접근·디코딩·파일 녹화·Orin 실행을 각각 검증한다. OS/JetPack/드라이버를 이번 연결 작업에서 일괄 업데이트하지 않는다.
