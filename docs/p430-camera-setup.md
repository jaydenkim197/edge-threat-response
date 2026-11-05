# P430 연결과 촬영 준비

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

## detector 연결

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
