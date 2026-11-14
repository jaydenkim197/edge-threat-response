# 검수 영상 추가 S1 재학습

2026-11-14 16:13 KST, PC13 RTX 3060에서 `s1-video-reviewed-20261114-v1`의 첫 epoch CUDA 배치 실행을 확인했다. 이 실험은 검수된 CCTV 프레임 추가 전후를 동일 S1 학습 설정과 개발 평가셋에서 비교하기 위한 것이다.

- 운영 SQLite를 읽기 전용으로 열어 SQLite backup API로 별도 스냅샷을 만들었다. 후보 1,406장은 최신 CCTV 구간 승인 시각 안이며 최신 프레임 판정이 칼 있음 또는 명시적 칼 없음이다. 사람이 저장한 reviewed_boxes 165개를 YOLO 라벨로 변환했다. 승인 범위 밖 이전 판정 5건, 제외 118장, 보류 98장은 후보에 포함되지 않았다.
- 원본 영상 189개 경로의 SHA-256이 모두 달랐다. 소스 ID와 영상 파일, 확보 목록에 있는 YouTube ID 및 승인 구간 연결을 확인했다. 검수 이미지의 SHA-256·디코드 크기와 박스 범위를 확인했다. 후보 내부 및 기존 S1 데이터에 동일 이미지 SHA 중복 0건. 기존 val/test, 7개 개발 평가셋 및 US Mock 보호 자료의 고유 이미지 3,188장과 동일 SHA, 종횡비를 고려한 dHash 거리 4 이하 및 알려진 계보 키 교차가 0건이었다. 서로 다른 편집본에 포함된 동일 사건을 모두 식별할 수 있는 방법은 아니다.
- 실제 추가 1,406장(양성 161, 음성 1,245), 전체 train 고유 13,466장, epoch당 13,470 draws. 기존 val/test 각 1,423장 목록을 직접 참조하고 목록·정답 라벨·이미지 해시를 확인했다.
- 비교를 위해 S1의 동일 COCO YOLO26n 초기 가중치와 640, 50 epochs, batch 16, FP32, AdamW, seed 20261004를 사용했다. epoch당 842 배치, 전체 계획 42,100 업데이트로 S1의 37,700 업데이트와 차이가 있다. 시작 관측은 1/50 epoch의 12/842 배치이고 완료 epoch와 최종 성능은 후속 결과에 따른다. 학습 뒤 기존 7개 개발 평가셋의 predict/AP 결과를 S1과 비교하도록 실행기에 연결했다.
- 점검: 원본 이미지 검사와 GPU 파일 잠금, 기존 평가 도구를 재사용했다. 실측 환경 torch 2.6.0+cu124, Ultralytics 8.4.152. 데이터 manifest, 추가 이미지 계보 및 라벨 해시, 학습 설정·실행 상태는 PC13의 `C:\Class6\edge-threat-response\data\processed\s1-video-reviewed-20261114-v1` 및 `C:\Class6\edge-threat-response\runs\s1-video-reviewed-20261114-v1`에 있다. 작업 스크립트와 스냅샷은 PC13의 `data/work/s1-video-reviewed-20261114-v1`에 두었다. 원본 영상·검수 DB·파생 프레임은 PC13에 보관한다.
- 추가 manifest SHA-256 `d15dcbafa822b2f4d3cbd7ef1abcd7f7f48440439e8e481d6af076bb59534a61`, 기존 개발 평가 suite SHA-256 `258caf410b16887fe4aedc55366871eff65faed183a143642e308b59eef33bae`. 실행 설정과 작업 스크립트 해시는 PC13 `invocation.json`에 기록했다. 이 실험의 Git 기록은 보고서 이력에서 확인할 수 있다.
