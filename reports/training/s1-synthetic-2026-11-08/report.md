# S1: ATM·CCTV 합성 보강 실험 — 2026-11-08

사용자는 ATM과 새 CCTV 60장을 자동 검사해 사용 가능한 자료로 S1을 학습하고, M1·M2의 동일 평가셋에서 비교하도록 승인했다. **현재 이 문서는 준비 기록이며, 전체 학습·성능 비교 완료를 뜻하지 않는다.** 실행 상태와 완료 결과는 아래 후속 증거로 갱신한다.

## 준비 완료 — VERIFIED

ATM116장과 CCTV60장 **합성176장(양성161/음성15, knife163개)**이 v2 검사를 통과했다. 실사11,884장과 합쳐 **train12,060 / val1,423 / test1,423**이다. M2 실사 train과 holdout identity·이미지/라벨 hash·순서가 같으며 고유325개 평가 이미지와 train의 exact 교차는0이다. 새 source의 전역 유사/보호 그룹 제외는0, 기존 문제·불확실88장 제외는 유지했다. [준비 수량·입력 해시](preparation-summary.json), [독립 재검산·테스트 로그 SHA](preparation-checks.json).

최종 source adapter와 RAW/followup 회귀25개 통과, 전체210tests 실행(208통과/2선택 비교skip), 기존 평가 환경의 비교12개 통과다. 12,064draws/epoch·754batches·50epoch·**37,700updates**를 계획한다. M2의37,150보다550개(약1.48%) 많다. 아직 전체 학습 완료·새 정확도는 아니다.

## 가설과 통제

고각 합성 칼 자료를 추가하면 공개 실사 학습만 한 M2보다 작은 칼·CCTV 개발 자료에서 검출이 개선되는지 조사한다. 모델은 YOLO26n/640이며 M1·M2와 같은 COCO pretrained checkpoint, seed20261004, AdamW/lr.001, FP32, batch=nbs16, 50epoch, 기존 증강 설정을 사용한다. M2의 best.pt에서 이어서 학습하지 않는다. 실사 M2 자료와 val/test identity·라벨·순서는 유지하고 합성 자료만 train에 추가한다.

합성 자료 수가 늘어나는 만큼 update 수가 달라질 수 있다. 같은 epoch·hyperparameter의 **전체 recipe 개발 비교**이며 같은 연산 예산 또는 합성 데이터만의 엄밀한 인과 효과를 주장하지 않는다. 합성 비율을 임의로 oversampling하지 않는다. 실제 CCTV 촬영/T1·독립 Holding GT·최종 B0~B4 평가는 계속 별도다.

## 원본과 자동 검사

| Source | 실제 확보·공급 라벨 | 처리 |
|---|---|---|
| [Simuletic ATM](https://huggingface.co/datasets/Simuletic/CCTV_ATM_Robbery_Detection_Dataset_Gun_Knife/tree/8b110306a80d2faafeb2e4d2e99b029f923bf024) | 기존 PNG237장, knife116장/118boxes | 고정 pack hash와 raw image/YOLO label을 대조한다. class3만 knife0으로 변환한다. gun/offender/victim을 신규 클래스·Holding GT로 바꾸지 않는다. 칼 라벨 없는121장은 음성으로 사용하지 않는다. |
| [새 CCTV 60장](https://zenodo.org/records/23484061) | 고정 ZIP24,005,558bytes, 양성45장/45knife·제작자 명시 hard negative15장 | YOLO0=person/1=knife, COCO1=person/2=knife를 대조했다. 60장·122전체boxes의 두 형식 좌표가 .002px 이내에서 일치한다. source README의 명시적인 칼 부재 설명과 person-only 주석이 일치하는15장만 provider negative 후보로 삼는다. |

새 ZIP은 MD5 `96072c9bd17ce2188ef53e743680018a`, SHA-256 `f1f9a3c41f4add7b5a01e00052e8c4494bcb648a7aa3efe3c2ea7983d5cafd40`이다. CC BY-NC4.0을 고정한 비상업 학술 실험이며 원본을 Git에 재배포하지 않는다. PC13 다운로드가 SSH 대기 제한을 넘겨 획득 worker만 종료했고, 보관 ZIP의 길이·checksum·CRC를 재검증해 새 추출 경로를 만들었다. 개발 PC에서도 같은 ZIP checksum을 확인했다. 기존 원본/서비스/환경을 초기화하지 않았다.

이미지 strict decode/JPEG EOF·EXIF·치수, 모든 원 class/bbox 구조와 유효 좌표, 원 라벨 SHA를 검사한다. 기존 source15,545 signature(보호263 포함), 별도 US Mock100개, OI594, 새 합성을 SHA/dHash≤4/종횡비 변화 proxy/filename family/전이적 연결로 검사한다. 새 연결이 frozen val/test를 잇거나 M2 실사 구성 변경을 요구하면 자동 재분할·삭제하지 않고 중단한다. 시각 품질 전수 검수나 실제 촬영 세션 독립성을 증명하는 절차는 아니다.

### 일반 파일명 충돌과 v2

첫 v1 감사에서 새60장 모두 `knife_숫자.jpg` family가 SOHAS1,250개와 같다는 이유로 제외됐다. 새60장과 기존 source의 직접 exact hash·dHash 후보는 각각0이었다. 서로 다른 출처의 클래스별 단순 번호는 같은 촬영 출처라는 근거가 아니므로, **신규 합성 source의 record ID 파일명 proxy만 source namespace를 붙였다.** 원래 filename/분할/라벨은 annotation provenance에 보존하며 전역 image SHA/dHash/protected 전이 연결 검사는 그대로 유지한다. 기존 source·holdout의 group evidence나 파일을 변경하지 않는다.

새 v2 출력은 별도 경로이고 v1 감사·사본은 보존한다. generic filename 충돌을 분리하면서 exact image hash는 여전히 연결되는 회귀 검증을 추가했다. 이는 모든 중복을 발견했다는 보장이 아니다.

## 구현과 검증

`search-first`: 기존 `parse_yolo_label`, `image_signature`, `prepare_followup`/proxy graph, RAW hash-bound 승인·GPU lock·launcher, 동일 detector evaluator/집계/threshold·paired bootstrap을 조합했다. 얇은 source adapter와 명시적인 `RAW-S1-n` recipe만 추가하며 기본 RAW4종 실행 선택은 바꾸지 않는다. provider negative는 원본의 명시적인 absence evidence가 있어야 하며 human review/negative 검증 완료를 만들지 않는다. 제품 추론·HOI·검수 사이트 코드/DB는 수정하지 않는다.

- PC13 Python3.12.4/torch2.6.0+cu124/Ultralytics8.4.152/RTX3060 12GB, 기존 `.venv-ml`과 `.venv-evaluation-20261104`를 사용한다. 새 설치·업그레이드는 없다.
- namespace 보완 전 ML 전체209tests: 207통과/2선택 비교skip. 해당 비교는 기존 평가 환경에서10+2 tests 모두 통과했다. namespace 보완 후 관련 source/RAW/followup 회귀는 다시 실행한다. 실제 검사 로그는 `runs/s1-20261108`에 보관한다.
- source/라벨 변조·경로 이탈·unknown class/NaN·source별 remapping·명시적 negative와 단순 무라벨의 구분·frozen holdout·보호 그룹·실행 승인·실패 queue 차단을 검사한다.

## 학습 이후 자동 비교

[후속 worker](followup-worker.py)는 PC13의 성공한 S1 queue·실제 optimizer update·best.pt artifact SHA를 확인한 뒤 실행한다. 실패·변조 때는 평가를 시작하지 않는다. SSH/노트북 종료와 분리된 일회성 dependent job이며 반복 서비스나 주기 자동화가 아니다.

- 기존 **동일7개 개발셋/346entries·고유325images**를 고정한다. D0·M1-n·기본M2-n·S1-n을 모두 같은 PC13/640·FP32·batch1·후보 floor.001·NMS IoU.7에서 평가한다.
- default predict와 validator candidate AP 경로를 분리한다. 공통 fixed confidence.25/matching IoU.5의 Precision/Recall/F1/FP, AP50/AP50–95, small recall과 confidence.10~.50/.05step 및 .001/.05 진단을 저장한다.
- 기존 M1/M2 기준21partition×2경로의 fixed/AP50 재현을 확인한다. paired group bootstrap 차이도 기존 구현으로 계산한다. 후속 worker의 비교표·CSV·원시 예측은 `runs/s1-comparison-20261108-v1`에 저장한다.
- 기존 US21과 확대 US83은 겹치므로 합산하지 않는다. 합성 평가와 실사도 합산하지 않는다. 개발셋 성능으로 D*·최종 실제 CCTV/사건 성능·Orin 속도를 확정하지 않는다.

## 원시 경로와 다음 작업

PC13 `C:\Class6\edge-threat-response` 기준:

- 원본 ZIP/고정 metadata: `data/source-audit/simuletic-cctv60-20261108`
- 원본 source spec: `data/work/s1-20261108/sources.json`
- 준비 v2: `data/processed/s1-synthetic-20261108-v2`
- 실행 승인/queue: `data/processed/s1-synthetic-20261108-v2-profiles`
- 로그/검사: `runs/s1-20261108`
- 학습: `runs/training/s1-synthetic-20261108-v2-raw-s1-n`
- 비교: `runs/s1-comparison-20261108-v1`

새 학습 시작·완료, 실제 추가량·draw/update 수, 후속 worker preflight·실행 상태는 관측 후 갱신한다. 새 성능·Orin/GPIO·실제 Holding·독립 final은 아직 미검증이다. Git commit은 본 이력과 invocation의 실행 source로 추적한다. 타 채팅의 미커밋 Catargiu/검수 운영 문서는 보존한다.
