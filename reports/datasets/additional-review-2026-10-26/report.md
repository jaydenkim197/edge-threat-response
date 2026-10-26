# 신규 데이터 확보와 검수 사이트 추가 — 2026-10-26

Catargiu 17장, Simuletic ATM 합성237장, Dangerous Items 작은 칼50장을 기존 사이트에 추가했다. **총304장, 전체1,219장**이며 모두 검수 대기·학습 미승인이다. 이름 선택과 공통 두 질문은 그대로다. 기존466개 판정·배정·수정 이력과 학습용 manifest/val/test는 보존했다.

## 실제 확보·추가량

| 자료 | 원본 확보·검사 | 이번 웹 추가 | 관측·제한 |
|---|---|---:|---|
| [Catargiu](https://github.com/CostiCatargiu/Yolov12_WeaponDetection) / [WeaponDataset v11](https://universe.roboflow.com/gundetectiondataset/weapondataset-oi2g3/dataset/11) | v11 ZIP의 필요한 range만 읽어 작은 knife 후보75장 확보. GitHub 수정 라벨26,528개를 byte-exact 검사하고 knife-positive image5,429개와 파일명을 연결 | **17** | 보호된 filename family proxy33장·보호 visual 후보2장·기존 visual 후보3장, 총38장 격리. 남은37장 중 제품 모음·게임/도해·픽셀 손상 예시20장은 AI 시각 선별로 이번 묶음에서 제외. 사람·knife 동반 후보17장도 정면/훈련/스톡 장면이 섞여 있어 **전부 CCTV가 아니다**. |
| [Simuletic ATM](https://huggingface.co/datasets/Simuletic/CCTV_ATM_Robbery_Detection_Dataset_Gun_Knife) | 원본 PNG237장·대응 YOLO237개, 미리보기2개 제외 | **237** | class3=knife. 실제 knife 라벨은116개 이미지/118객체, zero-knife-annotation121장. `knife` 파일명119장 중3장은 knife 라벨0인 누락 후보이며 확정 음성이 아니다. 합성237장이 독립적인237개 촬영 세션을 뜻하지 않는다. |
| [Dangerous Items VOC v2](https://zenodo.org/records/13786228) | 공식357,834,955-byte ZIP 전체 checksum 확인, XML4,000개 파싱. 기존 원본/증강본 filename identity 제외 후 작은 칼 후보93장 검사 | **50** | VOC semantic `Knife` 이름을 직접 사용.50장/60객체. 기존 Dangerous Items100장 뒤에 별도 배치로 추가했으며 기존 overlay를 수정하지 않았다. |

Catargiu의 `normalized knife area <= .02`, tiny층의 `.0025`는 **검수 표본 선정 조건**이다. 최종 small-object 성능 기준이나 카메라 거리/해상도 규격으로 승격하지 않는다. 첫75장은 전체5,429장 knife 후보의 대표 표본이 아니며, 최종17장에는 tiny6/small11이 있다. 초기 pack summary의 `selection_strata`는 AI 시각 선별 전37장 수치다. 기존 파일을 덮어쓰지 않고 pack에 `published-selection.json`을 추가해 해당 필드의 최종17장 수치를 명시했다. 실제 evidence 재계산 결과와 `final-inventory.json`/공개 aggregate도6/11로 일치하며 이미지·판정·fingerprint는 바꾸지 않았다.

Catargiu는 공개 README의 연구용 제한과 Roboflow의 CC BY 4.0 표기가 함께 남아 있다. 사용자 승인 범위인 비상업 학술용 표본 검수만 진행했으며, 출처 권리·재배포·학습 채택 gate를 해결했다고 간주하지 않는다. ATM은 고정 dataset card의 CC BY-NC 4.0, Dangerous 원본은 공식 API의 CC BY 4.0을 기록했다. 총기·offender/victim 라벨을 신규 MVP 클래스나 행동 정답으로 사용하지 않는다.

## 버전과 원본 증거

- Catargiu 수정 라벨 commit: `382d925c0d4ce054c0368ac2778c93b94654954d`. 원본 v11 export의 knife ID0과 저자 수정 class0을 확인했다. export의 `other`와 수정 라벨의 `no_weapon`은 이름 차이를 보존했으며 자동 negative class로 합치지 않았다. 중복된 `data.yaml` ZIP entry는 두 내용이 byte-identical임을 검사했다. 최초 sparse checkout의 Windows 긴 파일명/줄바꿈 문제는 원본 Git archive와 `core.autocrlf=false`로 해결하고 각 라벨의 Git blob을 검증했다. 표본은 먼저 bounded range로 준비했다. 이후 브라우저에서 완료된 공식 ZIP1,363,496,844 bytes를 PC13 `catargiu-v11-yolov8.zip`으로 옮겼고, 양쪽 SHA-256 `e77e054afbec588212bc1e6c0300c21c356d4acb6d774a3f6c2d965288d0ff02` 일치·48,170개 entry CRC·게시17개 image hash를 검증한 뒤 로컬 중복본을 정리했다. 제공자 선언 checksum이 있다는 뜻은 아니다. 준비 range의 마지막 실행6,725,400 bytes는 cache된 원본을 재사용한 재실행 수치로 전체 누적 전송량이 아니다. 이후 원본 검사는 PC13 archive를 우선 사용한다.
- ATM revision: `8b110306a80d2faafeb2e4d2e99b029f923bf024`.237개 image bytes 합267,681,593. 파일별 metadata size/LFS SHA-256(있는 경우), decode·dimension·라벨 class·bbox를 검사했다. image/label hash·원 경로·filename variant proxy와 synthetic 여부를 evidence에 남겼다.
- Dangerous VOC archive: 제공자 MD5 `d162fd620d33e2a330c089f3b6f0babb` 일치, 측정 SHA-256 `9c6749a3e36b6935fc468de9b1fb639b16c4caef2c21f5328a44ff210d3e1aa8`. 2025 YOLO 전체 archive checksum은 여전히 미검증이다.
- 원본과 큰 파일은 **PC13** `C:\Class6\edge-threat-response\data\source-audit\additional-sources-20261026\`에 보관한다. GitHub에는 원본·개인 판정·세션키·인증된 다운로드 URL을 넣지 않는다. 로컬에는 소량의 검증 화면/축소 sheet만 보관했다.

## Dangerous Items 클래스 대조

2024 VOC와 [2025 YOLO](https://zenodo.org/records/16422779)를 이름만으로 동일시하지 않았다. 기존 검수100장 중 **55장**은 VOC 원본과 image SHA-256이 같았고, 그55장의 기존 knife overlay는 원본 Knife bbox와1.01px 이내로 일치했다. 나머지45장은 증강본 또는 byte-identity 미확인 자료다.

그중 단일 semantic class 이미지에서 클래스별5쌍씩 **25쌍**의 실제 YOLO 라벨과 VOC 이름을 대조했다.

| YOLO raw ID | VOC 이름 | 대응 근거 |
|---:|---|---:|
| 0 | Machete | 5쌍 |
| 1 | Knife | 5쌍 |
| 2 | Baseball Bat | 5쌍 |
| 3 | Rifle | 5쌍 |
| 4 | Gun | 5쌍 |

이는 `1=Knife` 작업 가설을 **대응 표본의 원본 라벨로 지지**한다. source YAML이나 전체8,478장 검증을 대신하지 않으며, source/session 독립성과 학습 승인은 남는다. 이번50장은 이 숫자 추정 대신 VOC `Knife` 이름에서 직접 가져왔다.

## 중복·보호 경계

- 준비와 배포 직전에 현재915개 검수 image bytes를 다시 확인하고 신규304장·원본·라벨 hash/decode/dimension을 검사했다. 기존 자료와 신규 자료 사이 및 신규 자료 내부 exact 중복0이다. 신규 source끼리도 dHash<=4 후보0을 별도 확인했다.
- 기존 SOHAS full integrity/pairs에서 proxy component를 다시 계산해 reserved val/test group에 연결되는864개 signature를 대조했다. Catargiu는 v11의 stretch resize 때문에 aspect-ratio 조건을 빼고 dHash<=4를 보수적으로 사용하고, 원 파일명 family의 보호 proxy도 확인했다. ATM/Dangerous는 기존 aspect-ratio gate와 dHash<=4를 사용했다. 게시된304장에는 해당 보호 충돌이 없다.
- ATM 내부 visual 후보3쌍은 같은 synthetic 변형일 수 있어 기록하고 유지했다. Catargiu의 선별 전37장에도 내부 visual 후보1쌍이 있었으나 최종17장에는 그 쌍이 포함되지 않는다. 유사 후보를 독립 세션으로 간주하지 않는다.
- Exact/dHash/filename proxy는 모든 crop/flip/재인코딩/동영상 인접 프레임을 찾는 검사가 아니다. **실제 camera/session 독립성은 미검증**이다. 이 단계에서는 검수만 추가했고 학습·평가에 편입하지 않았다.

## 백업·QA·배포

PC13 `data/review/additional-candidates-20261026/`의 세 immutable pack을 연결했다. Catargiu/ATM은 별도 source, Dangerous는 기존 source의 `20261026-voc-small-v1` 배치이며 기존 IDs0–99에 이어100–149(화면101–150)다.

`data/review/additional-sources-20261026/{before-preparation-backup,before-deploy-backup}/`에 SQLite backup API로 config/DB/status를 보관했다. 서비스 정지 구간에서 fresh audit 후 atomic config 교체·registry migration을 수행했다. 기존 모든 DB의 reviews/history/metadata 및 team users/assignments의 row count/hash가 같고, 기존 registry10행 유지+3행 추가다. 신규 reviews/history/배정은0이며 DEV manifest·train/val/test 목록·YAML·training config·authorization과 pack input bytes도 보존했다. 최초 PS 파일 호출은 execution policy로 실행 전 거부됐고, 이후 해당 프로세스에서만 스크립트를 실행했다. 시스템 정책을 영구 변경하지 않았다.

- 신규 helper 회귀2 tests 및 **전체140 tests**, compileall 통과: PC13 Windows/Python3.12.4, source `6917937` archive + 변경 helper/test overlay. 처음 tests만 복사한 QA는 configs/fixture 부재로 실패했고, 전체 tracked archive의 격리 환경에서 다시 통과했다.
- 새 source를 config helper 재실행 때 지우지 않도록 보존하고, signed URL query를 변경하지 않는 선택지를 기존 bounded RangeReader에 추가했다. 신규 프레임워크/의존성/질문은 없다.
- DB를 모두 복제한 loopback8795 QA:3개 추가 묶음×Android412px/iPhone390px 프로필에서 이름 선택→두 질문 저장→다음→필수 메모→재접속/최근 이어가기→reload, stale version409를 검증했다. 가로 overflow0, 버튼46px. **Edge Chromium**으로 검사했으며 실제 Safari/WebKit·실물 홈 화면 설치 검증은 아니다.
- 운영 Funnel HTTPS에서도 새/기존 image ID·질문2개·모바일 화면을 확인했다. 운영 QA에서는 claim/save를 차단해 테스트 판정·배정0이다. `ETR-Team-Review` Running,9개 준비/총10개 source(ACF blocked),1,219장/466판정 snapshot을 확인했다.

원시 준비·선별·mapping·audit·backup·migration·QA 결과는 PC13 `data/review/additional-sources-20261026/`; 일회성 준비/배포 스크립트는 `data/review/{prepare_additional_sources,filter_catargiu,dangerous_mapping,operations_additional_sources,final_inventory_additional_sources}.py`에 남겼다. 브라우저 QA 스크립트/결과/화면은 개발 PC의 `data/review/additional-sources-20261026/`에도 있다. source/pack에 raw pointer·hash가 있어 다음 작업에서 실제 입력을 다시 대조할 수 있다.

## 저자 요청과 나머지 후보

[Berardini 등의 indoor CCTV 논문](https://link.springer.com/article/10.1007/s11042-023-16231-x)은 privacy 때문에 데이터를 공개하지 않고 reasonable request를 받는다. 공식 corresponding author Daniele Berardini를 확인하고 **Gmail 미발송 초안만 생성**했다. knife 영상/원본 프레임·bbox 계약·camera/sequence ID·5인 팀 접근·팀 검수 도구와 보고서 표시 조건을 묻는다. 원본을 public GitHub에 올리지 않는 방안을 제안했으며 기관 승인이나 데이터 이용 계약을 이미 확보했다고 쓰지 않았다. 상대방의 회신은 아직 없다.

| 남은 후보 | 이번 확인 | 다음 순서 |
|---|---|---|
| [ACF 원 저장소](https://github.com/iCUBE-Laboratory/The-Armed-CCTV-Footage) | 공식 API404 재확인 | 공식 원본/대체 배포의 출처가 확인될 때만 확보. US Mock Attack을 ACF라는 이름으로 재포장한 자료는 채택하지 않음 |
| [URBANITE](https://github.com/Vicomtech/Urbanite) | commit `e792b271193990ec37c0b773ccd506fc966687e8`,22개 helper/문서 파일. full RGB와 knife별 2D annotation 접근 경로를 확인하지 못함 | 배포 경로와 knife class/bbox 계약 확인 전 대규모 다운로드·변환 보류. 행동 class PanicHit을 knife bbox 정답으로 추정하지 않음 |
| [AIMs2 CCTV Weapon Detect](https://universe.roboflow.com/aims2-cctv-dataset/cctv-weapon-detect) | 공개2,005장/3클래스/CC BY 4.0 표기지만 원 촬영·재배포 설명 없음 | 원 source 추적이 먼저. CCTV라는 제목만으로 검수·학습 pool을 늘리지 않음 |
| Open Images | 기존30장 그대로 | 이번 표본 결과와 실사 gap이 남을 때 train source의 필요한 부분만 별도 조사. 기존 validation 자료를 몰래 학습으로 이동하지 않음 |
| 기존 DaSCI / US Mock / Legacy | 역할·기존 판정 유지 | DaSCI protected proxy 문제 해결 전 병합 금지. US Mock은 외부 평가 후보, Legacy는 팀원 L0 트랙 |

다음 행동은 새304장 검수 → label/negative/권리/실제 group 확인 → 실사 보강 후보 선정이다. 합성은 별도 ablation으로 다루며, 검수 완료만으로 자동 학습하거나 기존 val/test를 재분할하지 않는다. Catargiu 수량을 늘리는 것보다 중복과 domain mismatch를 제거하는 것이 우선이다.
