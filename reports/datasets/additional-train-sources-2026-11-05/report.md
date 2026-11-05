# 후속 학습 source 확보

현재 RAW 학습 큐는 변경하지 않고 Legacy와 Open Images train 자료를 PC13에 추가 보관했다. 사람 검수·전역 중복 검사 완료나 새 학습 recipe 채택을 뜻하지 않는다.

| 자료 | 확보 | 확인 | 남은 검사 |
|---|---:|---|---|
| 기존 Legacy development export | 7,361장 | 로컬 image hash·knife-only 라벨 검사, 전송 ZIP SHA 및 PC13 추출 이미지 SHA 일치 | 현재 corpus/보호 그룹과 전역 중복·decoder 검사 |
| Open Images train | 594장 / 820 knife boxes | 공식 train metadata·Knife MID·게시자 CC BY2 metadata·좌표/회전/GroupOf·파일 무결성, 다운로드 실패0 | 전역 중복/그룹·target relevance·개별 권리 재확인 |

Open Images는 최대1,000장을 요청했으며 자동 조건에 맞는 전체 후보가594장이었다. 기존 validation 평가 이미지를 이동하지 않았다. 음성 이미지를 무라벨 여부만으로 생성하지 않았고, image별 attribution·원 bbox row·metadata SHA를 PC13에 보관한다. 모든 이미지가 CCTV라고 주장하지 않는다.

Legacy ZIP은460,986,245bytes이며 기존의 normalized export를 복사했다. 원본/기존 split을 재작성하지 않고 전송 전후 hash를 검증했다. L0 모델을 별도로 학습하지 않았다. source-registry와 materialization manifest를 함께 보관한다.

PC13 위치: `data/source-audit/legacy-development-20261105/export`, `data/source-audit/open-images-train-20261105`. 후속 mixture는 현재 val/test·공개 개발 비교의 보호 그룹까지 함께 검사한 뒤 새로운 recipe로 생성해야 한다. 현재 큐에 파일을 끼워 넣거나 기존 source 승인으로 우회 실행하지 않는다. 사람 검수 완료를 기다려야 하는 gate를 되살린 것은 아니다.

다운로드 규격은 공식 [Open Images V7 페이지](https://storage.googleapis.com/openimages/web/download_v7.html)의 train bbox(V6 공개 파일)/class/image metadata를 사용했다. 출처·체크섬·게시자 권리 표시와 미확인 항목은 summary.json에 기록했다.
