# RAW 원본 학습 착수 기록

2026-11-05 사용자 승인에 따라 사람 검수를 기다리지 않는 원본 주석 예비 학습을 시작했다. **전체 학습 완료·모델 성능 비교·D* 선정 보고서가 아니다.**

| Source | Train | Val | Test | 합계 |
|---|---:|---:|---:|---:|
| SOHAS | 4,982 | 4 | 0 | 4,986 |
| Dangerous VOC | 1,296 | 1,255 | 1,263 | 3,814 |
| Catargiu corrected | 5,100 | 164 | 160 | 5,424 |
| 합계 | 11,378 | 1,423 | 1,423 | 14,224 |

공개 개발 평가의 보호 proxy group에 연결된 이미지864장과 exact duplicate186장을 제외했다. 첫 loader 검사가 손상 JPEG 누락을 감지해 gradient 시작 전에 중단했다. trainer가 변경한 사본8개와 실패 기록은 보존했고, 원본 해시 기반 새 사본에서 EOF 없는8장을 제외했다. 원본·split·검수 DB는 바꾸지 않았다. proxy group은 실제 세션 독립성 증명이 아니다.

순서: RAW-R1-n → RAW-H1-n → RAW-M1-n → RAW-M1-s. 공통11,392 draws/epoch·batch16·FP32·50epoch·35,600 optimizer updates를 계획한다. 실제 train loader11392/val1423/712batches/accumulate1과 여러 epoch 진행을 확인했다. 작은 pool의 반복 노출량도 기록한다.

학습 source checkout은 `cd60f3b`에 고정했다. 후속 비교는 `7007957` 별도 checkout과 `.venv-evaluation-20261104`를 사용하며, 성공한 queue 뒤에만 시작한다. 새4모델+D0+COCO26n/s+RF-Large를 기존6개 개발셋에서 AP/predict 두 track으로 비교한다. raw val은 source 비율이 편중돼 있고, 기존 개발셋은 이미 공개됐으므로 새로운 CCTV final 세션을 대신하지 못한다.

실제 위치(PC13): `data/processed/raw-real-20261105-v3`, `data/processed/raw-real-20261105-v2-profiles`, `runs/training`, `runs/raw-followup-20261105-v3`. 실패한 초기 queue와 교체 전 후속 launcher 기록도 보존한다. Open Images train·Legacy 추가 확보는 현재 queue에 반입하지 않는다.

execution-snapshot.json은 UTC가 명시된 읽기 전용 상태 snapshot이다. 현재 진행률은 PC13의 queue-state/results.csv를 확인해야 한다. 사람 검수·negative absence·실제 세션 독립성·최종 평가가 확인됐다고 표기하지 않는다.
