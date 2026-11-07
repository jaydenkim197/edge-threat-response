# Context-Aware Edge Threat Detection System - Development Log

이 문서는 제품, 기술 구조, 운영, 검증 및 연구 설계의 material change를 시간순으로 보존한다. 과거 항목은 삭제하지 않으며, 대체된 내용은 후속 항목에서 연결한다.

<!-- m2-real-20261107:begin -->
## 2026-11-07 — 확보 자료로 M2 단일 후보 준비·실행 지원

- 사용자 확인: 촬영은 다음 주, Roboflow 추가 접근 정보 없음. 이미 확보한 Open Images로 계속한다. 목적은 촬영 전 M2 공개 데이터 후보1개 준비이며 Q1 별도 full run·신규 source 대규모 탐색·검수 사이트 변경은 하지 않는다.
- search-first: 기존 parser/signature/proxy graph/RAW 승인·runner·평가를 재사용해 frozen holdout을 재분할하지 않는 follow-up 사본 경로와 RAW-M2-n 명시 선택만 추가했다. runtime root를 분리해 운영 checkout 대신 격리 worktree에서 실행한다. 의존성·driver 변경 없음.
- 결과: M1 train11,378-문제·불확실88+OItrain594=11,884, val/test 각1,423 identity/bytes/순서 보존. 보호263개 포함 기존source15,545+US100+새594 전이적 proxy 검사 완료. 새 자료의 추가 보호/기존 그룹 제외는0이다. 원본·모델·운영 DB를 수정하지 않았다.
- verification-loop: PC13 ML 전체201tests(199통과/2 optional skip), 평가환경 관련8+reference1 통과, 데이터 전체 hash/strict decode/bbox/copy·입력 전후 hash·holdout 보존, compileall·PS parser 통과. 코드/데이터 준비 VERIFIED이며 전체 학습/평가·새 Orin 성능은 아직 PLANNED다.
- 설정·해석: 동일 pretrained n/640·50epoch·batch16·기존 optimizer/증강/seed. M2는37,150updates로 M1의35,600과 달라 순수 데이터 효과/동일연산예산으로 주장하지 않는다. 실제 완료 상태와 source commit은 후속 invocation에 기록한다.
- 문서·증거·다음: [M2 보고서](../reports/training/m2-real-2026-11-07/report.md), raw-source-training·verification·설정 갱신. 다음은 CUDA preflight→M2 한 번 실행→동일 개발셋 비교, 다음 주 촬영/T1·실제 HOI·Orin/GPIO/독립 평가. 이 작업 파일만 commit/push하고 다른 채팅의 미커밋 문서는 보존한다.
<!-- m2-real-20261107:end -->

<!-- label-first-workflow-20261107:begin -->
## 2026-11-07 — 라벨 자동 추출·검수 사이트 중심 운영 확정

- 사용자 결정 `DECISION`: 앞으로 제공 라벨로 칼 이미지·bbox를 추출하고 무결성·좌표·중복·분할을 코드로 검사한다. 이미지별 AI 판정을 기본 작업으로 삼지 않으며, 필요한 장면·라벨 품질 판단은 검수 사이트의 기존 두 질문으로 받는다.
- 적용: AGENTS·데이터 검수 기준·source 전략·현재 작업표에 반영했다. 기존 RAW 예비 사용 허용·출처 조건·보호 평가 그룹·Holding/event GT는 유지한다. V3 7장 팩은 추가 검수 표본이며 전체 사용 가능량이나 전체 source 학습 승인으로 해석하지 않는다.
- 다음: 남은 후보 파일/라벨 확보와 자동 추출, 기존 train 문제·불확실 88장 제외 및 추가분 중복 검사를 거쳐 M2 manifest·설정을 준비한다. 별도 검수는 사이트 담당에게 넘기고 P430 촬영·라벨 준비는 병행·우선한다. 새 recipe·전체 학습은 이번 작업에서 실행하지 않았다.
- 검증: 문서 내용·내부 링크·Git diff를 점검하며 제품 코드·데이터·운영 DB 변경과 새 제품 테스트는 없다. 해당 문서 블록만 commit/push하고 타 채팅 미커밋 변경을 보존한다. commit은 본 Git 이력으로 추적한다.
<!-- label-first-workflow-20261107:end -->

<!-- roboflow-cctv-v3-20261107:begin -->
## 2026-11-07 — CCTV V3 표본 감사 완료·선별 7장 인계

- 목적·범위: 사용자 요청의 후보 조사가 일정과 맞는지 확인하고 V3 최대 50장으로 조사했다. 공개 원본 전체 확보를 M2/T1 선행 조건으로 추가하지 않았다. 중단 전 수집 자료를 재확인해 PC13에 보관하고 검수 후보 준비까지 마쳤다. ACF 요청 메일 11/06 20:58 발송은 사용자 확인으로 기록하며 원본·회신은 아직 없다.
- search-first: 기존 image_signature/similarity_pairs, proxy_components, prepare_team_review.write_pack, ReviewStore를 재사용했다. 브라우저의 공개 Raw Data와 관측된 이미지 자산으로 50장 주석·47장 이미지 약 5MB를 확보했다. SDK·새 학습 importer·제품 코드·모델 변경 없이 일회성 감사 worker로 조합했다.
- 결과·해석: 칼 40장/44 boxes, 목표 고각 유사 1장·다른 고정 실내 6장이다. 15,645개 참조에서 exact byte 0이지만 유사 후보 14장·보호 그룹 직접 연결 4장이고 같은 실내 장면의 원 train/valid 교차도 있다. 전체 V3를 M2 주력으로 쓰는 것은 보류 권장 `PROPOSAL`, 7장만 사람 검수 후보로 준비했다. AI 사전 분류와 source co-occurrence를 사람 판정/Holding 정답으로 쓰지 않는다.
- verification-loop: 47장 decode/치수/hash/knife 좌표, 두 팩의 실제 loader·빈 reviewer·격리 reviews/history 0, 기존 테스트 5+7=12개 통과. 참조·운영 config hash 동일, 운영 사이트·DB·배정·이력·학습 manifest·weight 변경과 학습 실행은 없다. 검증 보고서·CSV·worker·원시 경로는 [감사 기록](../reports/datasets/roboflow-cctv-v3-2026-11-07/report.md)에 남겼다.
- 다음·한계: [사이트 인계](handoffs/2026-11-07-roboflow-cctv-v3-review.md)의 7장 팩만 등록 검토 대상이다. 사람 검수·공개 등록/모바일 QA·원 이미지 출처·정확한 session·완전한 중복 보호는 별도다. ②/③ 표본 검사는 아직 미실행이며 실제 P430 촬영·T1/HOI가 우선이다. 관련 문서·보고서만 선택 commit/push하고 기존 타 채팅 미커밋을 보존한다. commit은 본 Git 이력으로 추적한다.
<!-- roboflow-cctv-v3-20261107:end -->

<!-- docs-refresh-20261106:begin -->
## 2026-11-06 — GitHub 주요 문서 최신화

- 목적·범위: 사용자 요청으로 나머지 GitHub 문서를 점검하고, 현재 계획·구현·실행 증거에 맞춰 주요 문서 22개를 갱신했다. 파일별 목록·이유는 [점검 보고서](../reports/documentation/current-docs-audit-2026-11-06/report.md)에 기록했다. 코드·학습·장비·검수 판정 변경은 범위 밖이다.
- 정정: 10/31을 대체된 과거 목표로 구분하고 11/20 동결·11/30 마감과 B0~B4 범위를 맞췄다. RAW 4종·GPU 환경·P430 연동 완료와 실제 HOI·물리 GPIO·최종 평가 미완료를 분리했다. 960 추론을 재학습으로 읽지 않게 했고, 실제 L4T 39.2.0과 계획 39.2.1을 구분했다. M2/T1은 권장안·실행 지원 준비 단계이며 자동 실행 가능한 recipe로 표기하지 않았다.
- 데이터·운영: 20:35:57 KST 읽기 전용 집계는 준비 3,625 / 판정 2,673 / 정상 2,527 / 보류 146이다. 운영 DB·배정·이력은 변경하지 않았다. 새 주소·두 질문·자기신고 이름 방식과 제한 자료의 비공개 반입 조건을 정리했다. 검수 정상과 실제 Holding 정답은 구분한다.
- 검증·한계: verification-loop에 따라 문서의 사실·링크·형식·집계·diff를 점검하고 [결과](../reports/documentation/current-docs-audit-2026-11-06/checks.json)를 남긴다. 새 제품 테스트·학습·하드웨어 검증을 주장하지 않는다. 날짜별 보고서·회의 기록과 타 채팅 미커밋 변경은 보존하며 관련 문서만 선택 commit/push한다. commit은 본 Git 이력으로 추적한다.
- 다음: 현재 작업표에 따라 M2 recipe 준비와 실제 CCTV 촬영·관계/사건 정답 확보를 병행한 뒤 T1·HOI, Orin/GPIO, 독립 평가로 진행한다. 이번 갱신 자체가 새 후보 채택이나 범위 확정은 아니다.
<!-- docs-refresh-20261106:end -->

<!-- review-assignment-timeout-20261106:begin -->
## 2026-11-06 — 미완료 배정 15분 미활동 회수

- 요청/범위: 사용자승인으로기존판정을보존하고방치된미완료배정만해제하며재발을방지한다. 원인은배정영구유지/활동시각부재였다. 사진·질문·검수정답·학습입력은변경하지않는다.
- search-first/구현: 기존SQLite·assignment·release·version충돌·localStorage draft를재사용했다. 기존assignments3열은유지하고활동table을추가했다. visible화면의새활동heartbeat30초, 미활동15분,60초worker+요청시회수를사용한다. 완료판정/version/history·완료소유권은제외하고save와claim은Team write lock으로직렬화한다. 만료draft보존/모바일하단새배정/마지막이미지이동도보완했다.
- verification-loop: PC13격리archive+정확한변경overlay에서관련20tests통과,전체193개실행OK(skip2),JS syntax통과. 새회귀는실제DB시각을과거로조정해만료·회수·heartbeat·migration·이전소유자쓰기거부·완료판정보존과실제thread저장/claim경합을검사한다. 운영DBQA판정은쓰지않는다.
- 상태/다음: 운영배포와초기방치배정회수는별도일관백업·전후table/hash확인후진행한다. isolated raw/fixture/log는PC13 ignored `data/review/assignment-timeout-20261106-v1/`, `data/work/assignment-timeout-qa-20261106/`다. 최종browser·운영결과는후속기록으로연결한다. 본코드와문서의commit은Git이력으로추적한다.
- 배포완료: code8a6ed6c·consistent backup후미완료8개만회수했다(SOHAS1/Simuletic1/Mock1/Catargiu3/ATM2). 기존2,673판정/version/history·완료배정·계정/registry/config를보존했다. 공개900초정책·두mobile크기의만료/재배정/draft복원/쓰기차단검증과QA/터널정리·운영Running을확인했다. [최종보고](../reports/runtime/review-assignment-timeout-2026-11-06/report.md).
<!-- review-assignment-timeout-20261106:end -->

<!-- english-research-overview-20261106:begin -->
## 2026-11-06 — 데이터 요청용 영어 진입 문서·README 상태 갱신

- 목적/범위: 데이터 제공 연구자가 프로젝트·검증 증거·자료 처리 원칙을 확인하도록 README 한국어 제목 바로 아래 English summary와 `docs/research-overview-en.md`를 작성한다. 전체 한국어 문서 번역·메일 발송·검수 서버/인증/데이터 변경은 범위 밖이다.
- 사실 대조: RAW4종50epoch 완료/공통개발평가, P430→Orin 실제R1/B3 main·sub각300frame/mock경보/모니터확인, 합성HOI/B4 연결과 실제관계학습·GPIO·독립final 미완료를 기존 보고서/코드와 대조했다. English summary에서B0~B4/3m는목표설정/개발결과와최종성능을구분하고제공받은연락처를명시했다.
- 데이터 정책: 고정legacy submodule에이미지/checkpoint가있고standalone LICENSE파일을찾지못했으며, 운영config의reviewer_login=name을비밀값없이읽기전용확인했다. 따라서전자료재배포권한확보나제한자료인증구현을주장하지않는다. 신규제한자료의제공조건·비공개저장/공개endpoint미반입·재배포허가·보존/동의·source/session보호원칙을영어로기록했다. 이는새제한자료처리요건이며private서비스구현완료를뜻하지않는다.
- README 한국어도최신학습·P430검증·Dangerous VOC매핑/RAW와정식검수recipe 구분을갱신했다. legacy는선택submodule참조/별도권리확인으로안내한다. 작업중타채팅의hostname복구commit865c5d6이반영된README검수URL은보존했다.
- 검증/한계: 제공초안의간결한영문형식을따랐으며검증보고서·코드·고정submodule tree/config와상태를대조했다. 문서내부링크/anchor·fence·표/heading·diff·공개범위/비밀값을확인한다. 코드변경이없어제품테스트/하드웨어시험은재실행하지않는다. 실제새dataset반입/저장접근통제/메일발송을수행했다고보고하지않는다.
- 결과/Git: README·영문소개·이로그의추가블록만stage/commit/push하고타채팅미커밋은보존한다. 후속은사용자가메일에서공개repo/영문소개링크를참조하고제공자의조건확정후별도private반입을준비하는것이다. commit식별자는본Git이력으로추적한다.
<!-- english-research-overview-20261106:end -->

<!-- review-hostname-recovery-20261106:begin -->
## 2026-11-06 — 검수 사이트 DNS/Funnel/app 주소 복구

- 요청/원인: 사용자의 사이트 접속 실패를 재현했다. PC13 SSH/task/8770은 정상이지만 기존 URL은 DNS 실패, 실제 Tailscale DNSName/CertDomains는pc13, Funnel/app public_url은예전이름이었다. Host를지정한local200으로앱장애와구분했다.
- 변경/보존: consistent DB/config backup·Funnel export후기존8770을새domain에연결하고public_url만변경/앱task만재시작했다. 기존3,625자료/2,673판정/계정/배정/history/registry의전후전체count/hash와session secret이일치했다. backend보안조건·dataset·질문·학습run·Windows/Tailscale장치명은변경하지않았다. 사용자는새주소유지를선택했다.
- verification-loop: 실제config admin/catalog/batch image smoke·team_review13 tests·새Host local200·public ingress IP 지정HTTPS200/TLS verify0·Edge Chromium Android/iPhone크기의새주소login/질문2/정렬/old/new이미지/overflow0을확인했다. Claim차단/review POST차단으로운영QA판정/배정0이다. 실제휴대폰재설치는미검증이다.
- 기록/다음: [복구보고](../reports/runtime/review-hostname-recovery-2026-11-06/report.md), README·운영안내의현재링크를수정했다. 원시backup/보존비교는PC13 ignored `data/review/hostname-recovery-20261106-v1/`다. 옛홈화면아이콘/즐겨찾기는새주소로교체한다. 장치명변경시DNS/Funnel/public_url동기확인필요. commit은본Git이력으로추적한다.
<!-- review-hostname-recovery-20261106:end -->

<!-- cctv-candidate-check-20261106:begin -->
## 2026-11-06 — 신규 CCTV 후보 원출처 확인·일정 우선 권장안

- 목적/범위: 사용자전달후보의실제수량/버전/주석역할과기존확보분을대조한다. 완료기준은원출처확인·현재코드/기록근거·새학습범위제안이며다운로드/운영DB/검수판정/기존split/학습queue변경은범위밖이다.
- 확인: Roboflow CCTV V3 overview2614/11class와exportv1증강4424·grayscale416/class변환을구분했다. CCTV499는v8버전목록을확인했지만v8직접fetch실패로v1설정을옮겨단정하지않았다. Catargiu26528은v11+NoGun v5의4class전체이고기존전체knife조사5429/M1 Catargiu준비5424/train5100과크게겹친다.
- 역할: Simuletic114/6초영상은합성,NTU Fights는싸움구간GT,VIRAT약8.5h는Ground release2.0 일반활동자료다. knife/Holding/완전음성으로자동변환하지않는다. 실제CCTV비율/새원본중복/라벨은미검증이다.
- 결정영향: 일정우선권장안을별도Q1학습후순위/88정제M2흡수·M2 n640하나·CCTV확보즉시T1/HOI우선으로구체화했다(PROPOSAL,사용자확정아님). 신규Roboflow각최대50표본조사는후속제안이며M2/T1선행gate가아니다. 새import는기존opened셋과확대US Mock83전체를보호해야한다.
- 기록/검증: [보고서](../reports/datasets/cctv-candidate-check-2026-11-06/report.md)에공식URL·프로젝트기록·전처리/버전/검사미실행경계를기록했다. 기존importer재사용가능성을확인했으며새코드/의존성/원본반입은없다. 문서링크/사실/수치/diff검증후관련블록만commit/push하고타채팅미커밋은보존한다. 제품테스트/실제샘플검사/학습통과를주장하지않는다. commit은Git이력으로추적한다.
<!-- cctv-candidate-check-20261106:end -->

<!-- pc11-pc12-cuda-ready-20261106:begin -->
## 2026-11-06 — PC11·PC12 격리 CUDA 학습 환경·검증 완료

- 목적/범위: 사용자요청으로두PC를PC14와같이설정/검증한다. 완료기준은독립clone/venv·Python3.12.4/43패키지버전일치·각32tests·CUDA실제학습/재로딩이며기존전역Python/driver/다른폴더/검수DB/실제dataset은변경하지않는다.
- search-first 재사용: 기존PC14 bootstrap/검증절차·PC13requirements·CUDA/HOI smoke도구를사용했다. PC11 ProgramData Anaconda/PC12 사용자Anaconda의기존3.12.4를확인해venv를구성하고cb5cb700 checkout을고정했다. PC14freeze에서프로젝트항목을분리한43버전목록으로설치했고새SSH에서모든버전/commit/repo clean을대조했다. MinGit공식SHA검증/사용자PATH백업추가,YOLO cache선생성도수행했다.
- PC11복구: pip가대용량wheel다운로드에서진행되지않아각해당자식프로세스만확인후중단/로그보존했다. 공식URL urllib다운로드2,532,302,369bytes와공식index SHA3313061c…를확인해로컬wheel로설치완료했다. 근본정체원인은확정하지않았다. clone/전역환경/다른작업을초기화하지않았다.
- verification-loop 결과: PC11 training15/1.782s+RAW10/0.649s+HOI7/0.168s, PC12 15/1.947s+10/0.731s+7/0.168s 모두통과. 두PC모두pip check/compile/CLI·CUDA유한gradient·YOLO FP32/AMP합성8train/4val/1epoch/validation/checkpoint재로딩·합성HOI G/VG CUDA추론/B4연결을통과했다. HOI학습은도구의CPU경로이며실제HOI CUDA학습/정확도/Orin성능으로주장하지않는다.
- 증거/한계/다음: [보고서](../reports/training/pc11-pc12-cuda-readiness-2026-11-06/report.md)에각PC state/freeze/43버전대조/테스트로그/원시경로를보관했다. 다음은실험별manifest·weight/config/SHA를보존한데이터전송/preflight다. 실제corpus학습·DDP·장시간안정성은미실행/미검증이다. 제품코드변경없음,문서수치/링크/JSON/diff를검증하고관련블록만commit/push한다. 타채팅미커밋은보존하며commit은본Git이력으로추적한다.
<!-- pc11-pc12-cuda-ready-20261106:end -->

<!-- pc14-cuda-ready-20261106:begin -->
## 2026-11-06 — PC14 격리 CUDA 학습 환경과 PC11·12 연결 복구

- 목적/범위: 사용자요청으로PC14만학습환경을설치하고PC11/12공개키등록명령을재제공했다. 완료기준은격리clone/venv·driver/전역Python보존·CUDA forward/backward·YOLO checkpoint재로딩·관련테스트다. 전체학습/실제데이터반입은범위밖이다.
- search-first로기존PC13pin/requirements·training smoke·HOI도구를확인해REUSE했다. 기존경로없음을확인한PC14 `C:\Class6\edge-threat-response`에clone/source cb5cb700고정,공식SHA검증MinGit2.51.2/venv/PyTorch2.6.0+cu124/Ultralytics8.4.152등동일주요버전을설치했다. 기존전역Anaconda/driver는유지했고사용자PATH는백업후Git경로만추가했다.
- verification-loop: pip check/compile/CLI·training15+RAW10+HOI7=32tests통과. 실제CUDA FP32/AMP 합성8train/4val/1epoch학습·validation·best/last생성·재추론및G/VG합성CPU학습후CUDA추론/B4연결을검증했다. 이는실제HOI CUDA학습/정확도검증이아니다. 초기CWD Ultralytics설정/폰트2파일만확인해hash보존으로ignored runs내이동했고새configdir의CUDA재추론/repo clean을확인했다.
- 사용자PC11/12등록완료회신후각BatchMode SSH·whoami조회성공. 둘다i9-13900/RAM31.75GiB/RTX3060 12288MiB·driver610.88, C여유196.23/179.42GiB다. 기본python은WindowsApps경로이므로실제interpreter설치판정은보류한다. 두PC학습환경은설치하지않았다. 로컬SSH config는백업후pc11/12/14 alias를추가했다.
- 기록/한계: 설치/검증state·freeze·테스트로그·JSON·원시경로를 [보고서](../reports/training/pc14-cuda-readiness-2026-11-06/report.md)에보존했다. 실제dataset/검수DB/split/full training은변경/실행하지않았고다음은Q1 manifest·run별전송/preflight다. 문서블록만stage하고타채팅미커밋을보존/검증/commit·push한다. Git commit은본이력으로추적한다.
<!-- pc14-cuda-ready-20261106:end -->

<!-- gpu-host-connections-20261106:begin -->
## 2026-11-06 — PC11·PC12·PC14 원격 연결 확인

- 목적/범위: 사용자 확보 장치의 Tailscale/SSH와 접속된 호스트의 기본 GPU 환경만 읽기 전용 점검한다. 사용자 첨부의 명령은 실행 증거로 읽었으며 설치 지시로 재실행하지 않았다.
- 방법: Tailscale 상태, 지정 기존 개인키의 `BatchMode=yes`/`IdentitiesOnly=yes` SSH, PC14 `whoami`·CIM·`nvidia-smi --query-gpu`·Python package metadata를 조회했다. PC11/12의 새 host key는 첫 접속으로 등록했으며 인증은거부됐다.
- 결과: PC14 키인증/원격명령 VERIFIED. RTX3060 12GB/i9-13900/RAM31.75GiB/C여유143.41GiB/driver560.94/Python3.12.4. 기본환경에torch/torchvision/ultralytics/OpenCV는없고git은PATH미검출. PC11(100.120.195.40)/PC12(100.78.203.54)는네트워크·SSH응답은정상이나키인증미완료로하드웨어조회불가다.
- 다음: PC11/12 각각관리자PowerShell에서사용자가PC14와같은공개키를등록한뒤재시험. PC14는별도학습환경/GPU kernel/격리workspace검증이남으며설치/학습을시작하지않았다. CUDA학습가능/3대동시학습준비완료로승격하지않는다.
- 문서/검증/Git: 실제관측을verification과본로그에기록하고추가블록만stage/문서diff검증/commit·push한다. 타채팅미커밋은보존한다. 구현코드변경이없어제품테스트는재실행하지않는다. commit은본Git이력으로추적한다.
<!-- gpu-host-connections-20261106:end -->

<!-- reviewed-next-training-20261106:begin -->
## 2026-11-06 — 검수 완료 자료 대조와 다음 학습·마일스톤 검토

- 목적: 늘어난 검수가 실제 신규 train인지 확인하고 다음 학습 순서를 정한다. 범위는 읽기 전용 운영 감사·기존 inventory/source group 대조·확대 CCTV 개발 평가·관련 문서다. 완료 기준은 재현 가능한 수량/역할·실제 평가·상태/한계 기록이며 운영 DB/배정/원본/기존split은 수정하지 않는다.
- PC13 `.venv-ml` 감사로 준비3,625/완료2,673/정상2,527/보류146 확인. 기존M1과같은라벨정상1,805/보류88, 새실사39(양성5/음성34)는직접보호검사통과하나전이적승인은남았다. 원본학습11,378에서88을보류한Q1-clean-n11,290장을제안하며새39추가와정제효과를혼동하지않는다.
- source e295586/평가venv의 기존비교CLI로5조건×US Mock83장/31GT/52음성 평가를완료했다. v1은suite정책누락으로inference전에거부돼보존/v2기존정책으로passed. M1-n640 0TP/FP2,960 1TP/FP2, D0 1TP/FP83, RF-Large1TP/FP0, M1-s0TP/FP0이다. 0.001까지threshold캐시재계산도했으나실용적CCTV recall/FP는확보못했다.
- 결정영향: Q1정제→별도공개실사M2→목표CCTV T1안은PROPOSAL, 새학습미실행이다. 현재마일스톤은baseline비교완료/목표데이터준비이며실제HOI학습·D*·GPIO·독립B0~B4평가는남는다. 11/9~12촬영부터11/30마감일정은유지한다. 사용자가추가촬영영상/Holding관계라벨은아직없다고확인했으므로11/9~12촬영·라벨링을다음현장마일스톤으로유지한다.
- 검증/기록: 일회성audit/evaluation source·집계·CSV·환경/모델hash·threshold진단을 [보고서](../reports/datasets/reviewed-next-training-2026-11-06/report.md)에보관했다. 제품코드/의존성변경없으며문서수치/링크/hash/diff를확인한다. 기존186tests는이번재실행으로보고하지않는다. Git은의도한보고서/문서블록만commit/push하며타채팅미커밋을보존한다. commit은본Git이력으로추적한다.
<!-- reviewed-next-training-20261106:end -->

<!-- raw-results-20261106:begin -->
## 2026-11-06 — 공통 비교 완료·M1-n 권장·960 추론 진단

- 네RAW50epoch가11/06 08:28KST까지완료됐고invocation별실제35600 updates·loader/batch·checkpointSHA를확인했다. 실패한후속AP의모델/예측/상태162개hash를보존하고새출력에서집계·predict8모델×6개/263장비교를완료했다. 복구e295586의PC13평가환경전체186 tests/22.970초/skip0 통과를확인했다. 검수DB/원본/기존split/학습checkout은변경하지않았다.
- 실제predict SOHAS dev23에서D0 AP50/R35.7/35.0→M1-n88.3/80.0%, M1-s85.2/70.0%다. DaSCI related92의M1-n AP50은76.4%다. US CCTV8GT는M1-n/s0/8로목표domain문제가남고Open Images는RF-Large가더좋다. AP/predict track을혼합하거나source평균으로최종승자를선언하지않았다.
- 재학습없이같은M1 checkpoint로960추론2모델×6개를추가검증했다. M1-n SOHAS small TP13→14/16·DaSCI59→71/88이나US0/8 유지/Open Images AP감소다. 후속주력은n/M1, 640기준선·960조건부추론·M1 vs 추가실사M2/목표CCTV적응을권장한다(PROPOSAL). 새학습·D*동결·Orin교체는하지않았다.
- 결과CSV/프로토콜/환경/선정곡선/학습CSV/원본보존hash와PNG/SVG/PDF정량그림을 [보고서](../reports/evaluation/raw-detector-selection-2026-11-06/report.md)에내보냈다. raw예측/로그는PC13두run에남겼다. 단일seed·opened자료·DaSCI1연관group·synthetic분리·US8GT·이미지지표/사건지표차이를기록했다.
- PC14는사용자제공사진과tailnet에서동일장치온라인·Windows SSH22응답을확인했다. 현재키의pc14사용자로그인은거부돼실제Windows계정/공개키등록을요청했다. GPU/환경/학습은미확인이다. 키포함현장안내는Git밖의수업폴더 `261106_PC14_원격접속_준비.md`에보관했고비밀번호를요청하지않았다. 모델관련문서만갱신하고타채팅의미커밋변경은보존했다. 문서commit은본Git이력으로추적한다.
<!-- raw-results-20261106:end -->

<!-- raw-comparison-recovery-fix-20261106:begin -->
## 2026-11-06 — RAW 네 모델 완료·보고 메타데이터 오류 수정

- PC13 재접속 후 R1-n/H1-n/M1-n/M1-s 각각50epoch와queue passed를 확인했다. 후속AP8모델×6개 예측은 완료됐으나 `summarize_detector_comparison.py`의 `models['policy']` KeyError로 집계 단계가 실패한 것을 실제로그에서 재현했다. 모델/평가 입력이나 학습 오류와 구분한다.
- 기존 집계기를 재사용해 선택 보고 메타데이터가 없는 frozen protocol을null/명시flag로 보고한다. 모든 기존truth/model/protocol/prediction hash·fixed metric 재계산 검사는 유지한다. 향후후속 프로토콜에는 원래policy와 AP/predict별 후보convention을 포함한다.
- 새 synthetic end-to-end 집계회귀2개로 metadata유무·원본hash보존·prediction변조 거부를 확인했고, 기존fail-stop queue 회귀1개도 통과했다. 기존AP/실패state는 보존하며 새출력에서 AP집계/남은predict만 복구한다. 실제 모델 선정/최종CCTV 정확도는 아직 확정하지 않았다. code commit으로 수정범위를 추적한다.
<!-- raw-comparison-recovery-fix-20261106:end -->

<!-- p430-live-confirmed-20261105:begin -->
## 2026-11-05 — 실제 CCTV YOLO 통합·로컬 화면 확인

- 인증 수정과 open timeout 수정 후 P430 sub640×360/120frame·main3840×2160/60frame 수신을 통과했다. 각각300frame의 신규RAW-R1-n knife+COCO26n person·640/FP32·B3 실행은 valid300/action error0이다. main event2/snapshot2, sub event4/snapshot4이며 정답 없는 탐색 실행이다. 서로 다른 시간 영상의 정확도·recall 비교나 실제GPIO 검증이 아니다.
- 사용자 요청으로 기존 detector/RTSP를 재사용한 `tools/view_live_detection.py`를 추가했다. Orin X11 `:1`/실제 DP 모니터에서30frame GUI smoke 종료와 무제한 표시의591frame 갱신·Normal/활성 창을 관찰했고 사용자도 움직이는 탐지를 확인했다. 사람green/knifeorange·신뢰도·viewFPS를 표시하며 Q/Esc로 닫는다. 영상/프레임을 저장하지 않으며 HOI/사건 판단/GPIO는 이 창에서 하지 않는다. CLI help/compile은 로컬에서 확인했다.
- core8a52fc8의 PC13 격리 평가env 전체184 tests가17.553초/skip0 통과했다. 관련RTSP3 tests는 로컬 통과다. 로컬 전체는 localhost HTTP Win10053 오류1/skip2, Orin 전체는 UL corrupt-image 경로의 선택 pi_heif 누락 오류1/skip2로 통과가 아니다. 자동 설치나 환경/기존검수 코드를 변경하지 않고 차이를 기록했다.
- 네트워크 간단 기록 `docs/cctv-local-network-setup.md`와 실제 결과/실행/한계를 P430 문서·architecture·Master Plan·verification·배포보고에 반영했다. 비공개 계정과 카메라 영상은 Git에 넣지 않았다. 최신PC13은R1-n50완료/H1-n39진행, M1-n/s대기·후속8모델비교대기이며 실행checkout cd60f3b를 유지했다.
- 사용자 시연 종료 지시 시 Orin Tailscale/직접LAN SSH가 불통이고 노트북은 다른Wi-Fi였다. 직접Q/Esc 종료를 안내했으며 원격으로 종료했다고 기록하지 않는다. PC13은 계속 접속 가능하다. raw 위치·SHA·지연 범위·남은WAN/재부팅/정확도/HOI/GPIO 검증은 [실행 보고](../reports/runtime/p430-yolo26n-2026-11-05/report.md)를 따른다. 본 commit으로 소스·문서 변경을 추적한다.
<!-- p430-live-confirmed-20261105:end -->

## 2026-11-05 - 검수 기회 활용·실사 후보 1,630장 추가

- 목적/범위: 사용자가 가용 검수 인력에 맞춰 유망 후보를 더 공급하도록 요청했다. SOHAS 800개(양성600/주석0 200), Dangerous250개(양성150/주석0 100), 별도 Open Images train580개를 기존 source 아래 새 배치로 추가했다. 작은 칼 후보92개이며 전부 고정 CCTV라고 주장하지 않는다. 신규1,630개는 사람 검수 대기다.
- 재사용/구현: 기존 write_pack·fresh image signature·보수적 dHash4·ReviewStore/BatchReviewStore·consistent backup·additive registry를 재사용했다. backend/UI code·질문·dependency는 변경하지 않았다. PC13 ignored 일회성 운영 script/선정·격리 evidence에 입력·label hash·원 split/group·권리와 미확정 좌표 계약을 남겼다.
- 보호/보존: 현 검수1,995개와 보호signature참조3,973개를 대조하고 배포 직전 재검사했다. 기존 DB/config를 백업하고 registry15행·모든 기존 테이블 hash와 ID/판정/배정을 보존한 채3행만 추가했다. 현재 RAW queue/profile/inventory·과거 DEV split/승인 hashes는 불변이다. 신규 운영 테스트 판정/배정0이며 기존 학습은 유지했다.
- 검증/결과: PC13 Python3.12.4의 team_review13 tests 통과. 복제 DB에서3개 source×2 mobile viewport의 저장·재접속·이어가기·reload·409·필수 메모·기존 판정 불변·질문2·overflow0/버튼46px을 확인했다. 공개HTTPS에서도9개 메뉴/전체3,625개·새 source수량·정렬·old/new 이미지가 통과했다. iPhone 크기도 Edge Chromium이며 실물 Safari 검증은 아니다. 배포 직후 판정1,598/재확인123, 신규판정0의 시점 snapshot을 기록했다.
- 문서/한계/다음: [배포 보고와 aggregate](../reports/datasets/review-expansion-2026-11-05/report.md), 운영 안내 최신 항목을 갱신했다. 새로운 source 채택·정상 판정·관계 label·성능을 검증한 것은 아니다. 사람 검수 후 정상분과 문제/모름을 고정하고 평가 보호 경계를 유지한 다음 recipe를 준비한다. Git commit은 이 항목을 포함한 변경 이력으로 추적한다.

<!-- p430-open-timeout-fix-20261105:begin -->
## 2026-11-05 — P430 인증 해결·초기 open timeout 수정

- 사용자 camera 계정 수정 후 authenticated DESCRIBE200/H264를 확인했다. 기존5초 probe의0frame 실패를 재현했지만 직접20초 진단은6.210초에 열려640×360·30frame를 디코딩했다. 초기 연결 시간이5초보다 긴 것이 현재 실패 원인으로 분리됐다. FPS10은 카메라 광고값이며 실제 추론 처리율이 아니다.
- 기존 RTSPFrameSource의 native open timeout만5→20초로 수정했다. read timeout5초·queue1·worker/credential 계약은 유지하고 새 dependency/adapter를 추가하지 않았다. backend 파라미터와 release를 검증하는 최소 회귀1개를 추가했으며 로컬 관련3 tests 통과·diff check를 확인했다.
- raw 진단은 Orin `runs/p430-yolo26n-20261105-v1/extended-open-diagnostic.json`, 비공개 계정은 기존 mode0600 파일에만 남긴다. 다음은 수정 source의 실제120frame probe와 YOLO26n/B3 제한 실행이다. 본 code commit에 고정한 별도 worktree에서 검증하고 기존 실행/PC13 학습은 보존한다.
<!-- p430-open-timeout-fix-20261105:end -->

<!-- p430-yolo-deployment-20261105:begin -->
## 2026-11-05 — P430 포트 해결·RAW-R1-n Orin 준비

- 사용자 Save·유지 확인 후 Orin에서554/8000/9000 open·RTSP OPTIONS200을 실측했다. 원본 비공개 계정 파일의 sub probe2회는0frame이고 동일 socket Digest DESCRIBE도401이다. 계정/권한 확인을 요청했으며 비밀번호는 출력/수집/커밋하지 않았다. 저장 helper는 숨김2회 입력·percent encoding·mode0600·원자 교체를 사용한다.
- PC13 queue에서RAW-R1-n50epoch 완료·RAW-H1-n19epoch 진행을 확인했다. 완료 weight5,368,446bytes의SHA c8006bf63e7d5ab9a71f89a0794c7d9723dc493970ba34918d51aea2480a7775를 PC13/Orin에서 대조했다. 기존 weight/학습 source를 변경하지 않았다.
- source c2daa70/Orin native venv에서 신규R1 knife+COCO26n person·640/FP32·B3로 기존 train-derived 파일53frame를 실행했다. valid53/detection59/event2/snapshot2/action error0·exit0을 확인했다. 실제 CCTV 정확도/FPS/HOI/GPIO 검증이 아니며 D* 선정 전 임시 배포다. [근거](../reports/runtime/p430-yolo26n-2026-11-05/report.md).
- 기존 adapter/RTSP/CLI/THP 정책을 재사용했고 새 runtime이나 패키지는 도입하지 않았다. Orin ignored 실행 폴더에raw/coco별config·300frame 제한 runner를 준비했다. 다음은 카메라 인증→sub/main decode→제한된 실제YOLO 실시간 실행이며 자동 무기한 서비스는 아직 없다. 변경 파일·실행 위치는 배포 보고와 본 commit에 기록한다.
<!-- p430-yolo-deployment-20261105:end -->

<!-- p430-lan-diagnosis-20261105:begin -->
## 2026-11-05 — P430 실제 LAN·서비스 진단

- 사용자 인수인계를 현재 장비에서 재검증했다. Orin enP8p1s0의192.168.0.10/24, P430192.168.0.4의 직접 경로·장비 MAC 일치·ping2/2를 확인했다. 노트북192.168.0.6과 Orin 양쪽에서9000 open/554·8000·80·443 connection refused이며18:12~18:13 KST 재검사도 같았다. 이는 인증 전 TCP 거부로, 실제 영상/모델 오류로 해석하지 않는다.
- Client 화면의 RTSP554/ONVIF8000 체크를 확인했으나 Save 버튼이 화면 아래로 잘리고 자동 입력 좌표가 맞지 않아 저장을 확인하지 못했다. 사용자의 Save 및 화면 재진입 후 유지 확인을 요청했다. 원격 네트워크/OS/패키지·PC13 학습은 변경하지 않았다. 비공개 카메라 설정은 아직 없고 인증·decode·WAN 제거는 미검증이다.
- 다음: 저장 확인→554 재검사→비공개 계정 설정→기존 RTSP probe로 sub/main 수신 검증. 설치된 rtspsrc/NVIDIA decoder를 확인했으며 코드나 decoder를 새로 작성하지 않았다. [세팅·실측](p430-camera-setup.md). 본 문서 commit으로 진단을 추적한다.
<!-- p430-lan-diagnosis-20261105:end -->

<!-- november-integration-evidence-20261105:begin -->
## 2026-11-05 — 실행 재확인·Orin B4 검증·추가 source 확보

- 토큰 중단 후 PC13 R1 학습/대기 queue가 계속 실행 중임을 확인했다. 학습 checkout은 cd60f3b로 유지하고 후속 평가/개발 source는 별도 worktree에 격리했다. `.venv-evaluation-20261104`에서 환경 preflight와 최신 source 전체183개 테스트가23.077초에 skip 없이 통과했다. 실행 로그는 PC13 `runs/qa-hoi-b4-20261105/final-183-tests.log`에 보관했다.
- PC/PC13 CPU 가상 G/VG 학습·reload·영상 연결, Orin G/VG CUDA 추론·sidecar/replay/snapshot/mock alarm, target27 tests, PC13 torch2.6 checkpoint→Orin torch2.14 strict load/CUDA 추론을 확인했다. 실제 Holding 정확도·카메라/GPIO·ImageNet visual fine-tuning은 미검증이다. [근거](../reports/runtime/hoi-b4-integration-2026-11-05/report.md).
- Legacy normalized export7361장을 image hash/라벨 검사 후 PC13에 전송하고 archive/추출 image hash를 대조했다. Open Images 공식 train에서 원본 주석·권리 metadata·자동 좌표/그룹/회전 조건에 맞는594장/820boxes를 확보했다(실패0). 현재 queue에는 넣지 않았고 전역 중복/보호 그룹 검사는 후속 recipe에서 한다. 사람 검수 완료를 기다리는 조건을 되살리지 않는다. [추가 확보](../reports/datasets/additional-train-sources-2026-11-05/report.md).
- 후속 비교는 학습 성공 후8개 모델×기존6개 개발셋의 AP/predict 두 track을 자동 생성하도록 대기한다. 실제 전체 학습·새 모델 비교·D* 선정은 완료 전이다. [실행 snapshot](../reports/training/raw-source-suite-2026-11-05/report.md).
- HOI 담당 인계는 PC13 `data/handoffs/20261105_hoi-labeling.md`, source/실행 위치는 같은 폴더의 execution-locations JSON에 보관했다. 공개 검수 사이트 HTTP200을 확인했으며 운영 DB/이미지/판정/배정을 쓰지 않았다. P430은 사용자 답변상 아직 연결 전이다. Git commit은 이 항목을 포함한 변경 이력으로 추적한다.
<!-- november-integration-evidence-20261105:end -->

<!-- hoi-b4-implementation-20261105:begin -->
## 2026-11-05 — RAW 전체 학습 착수·HOI/B4 구현

- 목적/범위: 승인된 11월 계획을 구현한다. 미검수 원본 예비 학습은 RAW 전용이며 기존 human approval과 웹 검수 DB/판정을 변경하지 않는다. 실제 관계 라벨·촬영·카메라/GPIO는 별도 의존사항이다.
- 데이터/실행: SOHAS/Dangerous VOC/Catargiu 원본에서 보호 proxy864·exact duplicate186을 제외해14,232장을 준비했다. 첫 로더 검사가 JPEG 누락을 잡아 gradient 시작 전 중단됐고, trainer가 변경한 사본은 덮어쓰지 않았다. 원본 해시로 검증한 새 사본에서 EOF 없는8장을 제외해14,224장으로 재준비했다. split은 유지했고 train11,378/val1,423/test1,423이다. RAW R1→H1→M1-n→M1-s 각50epoch·11,392 draws/epoch·35,600 updates queue를 PC13에서 시작했다. R1의 실제 loader11392/batch16/accumulate1/712batches와 여러 epoch 완료를 확인했다. 완료·성능 선정은 아직 아니다.
- 구현: G/VG Holding 학습·tuning threshold·checkpoint·GT/predicted pair 진단·해시 결합 sidecar, B4 core/replay/evaluator/영상 snapshot, queue1 RTSP 입력과 비공개 probe를 추가했다. B0~B3 기본 계약은 유지한다. CUDA 학습/후속 평가에 공유 GPU claim을 사용한다. 후속 도구는 학습 성공 후 D0/COCO-n/s/RF-Large와 새4모델을 기존6개 개발셋에서 AP/predict 두 방식으로 비교하며 D*를 자동 채택하지 않는다.
- 검증: PC `.venv-ml`, `PYTHONPATH=src`, `YOLO_AUTOINSTALL=false`, UTF8 unittest 전체181개(2 skip) 통과, compileall/CLI help. skip2는 pycocotools 선택 환경 검사다. CPU 가상 G/VG1epoch forward/backward·저장/reload 동일 예측, 영상4frame→sidecar→B0~B4 replay와 B4 사건1/snapshot1/mock alarm을 확인했다. wiring threshold0을 강제한 가상 시험으로 실제 정확도나 GPIO 검증이 아니다.
- 인계/다음: [HOI 정답 규격](hoi-annotation-contract.md)은 사이트 담당에 위임한다. 사용자가 Reolink P430 영상 출력을 확인했지만 현재 연결 전이다. [P430 연결](p430-camera-setup.md), 실제 관계 정답과 촬영 세션 확보 후 실사 학습·최종 평가를 이어간다. 기존 미커밋 Catargiu 운영 기록은 보존했다. Git commit은 이 항목을 포함한 변경 이력으로 추적한다.
<!-- hoi-b4-implementation-20261105:end -->

<!-- raw-source-implementation-20261105:begin -->
## 2026-11-05 — 미검수 원본 예비 학습 경로 구현

- 목적/결정: 사용자 지시에 따라 후보 자료는 사람 검수 완료를 기다리지 않고 원본 주석으로 개발 예비 학습한다. 최종 평가·검수 합격으로 승격하지 않는다.
- 구현: 기존 parser/signature/group split/training runner를 재사용한 raw source import, RAW-R1-n/H1-n/M1-n/M1-s 동일 draw/update 예산, 해시 결합 raw authorization, 실패 시 중단되는 순차 CUDA queue와 숨김 launcher를 추가했다. 기존 승인 경로와 사이트 DB는 유지한다.
- 검증: PC Python3.11 `.venv-ml`, `PYTHONPATH=src`, 신규 raw5 tests와 기존 training14 tests 통과, compileall/diff 확인. 실제 전체 source/CUDA run은 다음 단계다.
- 한계/다음: 원본 주석 누락·VOC pixel-edge 가정·conservative proxy group 한계가 남는다. 전체 source 준비 후 실제 수량/제외/실행 상태를 기록하고 HOI/B4를 추가한다. [범위·재현](raw-source-training.md). Git commit은 본 항목을 포함한 변경 이력으로 추적한다.
<!-- raw-source-implementation-20261105:end -->

## 2026-11-05 — YOLO·HOI 다중 데이터셋 병렬 개발·11월30일 완료 계획 승인

- 목적/사용자 결정: YOLO 데이터·아키텍처 개선과 독립 HOI Holding/Not Holding 모델을 병렬 개발하고 2026-11-30까지 코드·학습·Orin 통합·B0~B4 평가를 완료 목표로 한다. 기존 B0~B3 연구 유지, 후속 Holoscan5.0 범위 불변, 팀원별 역할은 고정 배정하지 않는다.
- 데이터 변경: SOHAS 외 Dangerous Items·Catargiu·Open Images의 기존 평가와 분리된 train 자료·고유 legacy·DaSCI 후보를 M1 실사 혼합에 검토, 직접 CCTV+스마트폰 T1을 활용한다. Simuletic 합성은 별도 실험, US Mock Attack은 외부 CCTV 평가, ACF 미확보는 보류. HOI HICO-DET/100DOH/Hands23 사용 가능성 검토, YouTube는 권리 확인 전 참고용. 학술 사용도 라이선스·source·재배포·촬영 동의가 자동 면제되지는 않으며 별도 법률 보고서 대신 자료별 간단한 검사를 보존한다.
- 촬영/모델: CCTV P430 추정 모델 실물 확인 및 RTSP·녹화 시험은 사용자 11/05 진행 예정이며 현재 미검증. 약3m 실내·2곳·3~5명·거리3단계/조명2단계·안전 모형 소품, 30~60클립/300~600 frame은 1차 수집 목표. HOI B4-G geometry-only, B4-VG pretrained MobileNetV3-Small+geometry, 1차 Holding, Using 후속. YOLO n/s와 데이터 구성 실험 분리. 640 기준/960 우선 비교, 1280 조건부, HOI crop224/256 후보.
- 일정/검증 gate: 11/05–08 source/설계, 09–12 촬영·검수, 13–16 모델1차 학습, 17–20 조정·동결, 21–24 실기기 통합, 25–27 독립 최종 평가, 28–30 결과 동결. PC13 RTX3060 full GPU 학습은 순차. 동일 frozen D* YOLO JSONL과 K/N/FSM으로 B3 vs B4 event 비교, D0 vs D* detector 개선과 관계 모델 효과 분리, 최종 평가 세션은 개발에 재사용하지 않는다.
- 변경 범위: Master Plan, Dataset Source Strategy, HOI Research, Controlled Experiment Protocol, Open Decisions, Development Log 문서만 수정. 실제 학습/영상 촬영/카메라·GPIO 검증/Orin benchmark를 실행한 것이 아니며 기존 640 Orin 파일 처리율12.1496fps는 camera 성능이 아니다.
- 다음 작업: CCTV 실물 기종·접속·샘플 확인, source별 최소 승인/중복 및 train/tuning/final 경계 확정, 학습용 run ID·GPU 예약과 새 B4 통합 구현 작업. 11/30은 목표이며 성능 개선·일정 달성의 실측 증거는 아니다.

## 2026-11-04 - 기성 모델과 fine-tuned checkpoint의 다중 domain 비교

- 작업 카드/목적: 현재 학습 모델이 학습 전 동일 n과 다른 기성 모델보다 유리한지 동일한 여러 평가셋에서 확인하고 논문용 근거를 보존한다. 범위는 기존 모델·검수 완료 이미지의 read-only 평가, 완료 기준은9개/동일6set의 완전 결과·공통 지표·source/model/config/raw prediction hash·재현 도구·표/그림·검증·commit/push다. 위험은 test 공개/관련 source·소표본·synthetic·후처리 차이를 무시한 학습 효과 과장이다.
- search-first/변경: 기존 source bbox/리뷰 verdict·read-only SQLite snapshot·signature/proxy·JSONL·고정 bbox evaluator를 재사용하고 pycocotools 공통 AP·paired group recall bootstrap과 실험 prepare/run/aggregate/plot 도구를 추가했다. RF/DEIM은 실험 전용 adapter이며 제품 runtime/Orin/site를 변경하지 않는다. dependency는 별도 venv, 데이터/weights/raw는 PC13 ignored 위치에 둔다.
- 데이터/모델: SOHAS val23/test23, human-ok 외부 DaSCI92/US Mock21/Open Images29/Simuletic75, 총263images/241GT. 외부 정상218개 중 보호183개와의 유사 후보1개를 사전 제외했다. DaSCI92개 전부 같은 filename family, synthetic 별도, US Mock8GT, Open Images small0이라는 한계를 고정했다. 기성YOLO n/m/l/x·RF Small/Medium/Large2026·DEIMv2-S와 기존 AdamW+scale.9 n best를 사용하고 재학습/threshold tuning은 하지 않았다.
- 공정성 보완: YOLO default predict는 최고 class만, validator는 multi_label=True로 후보를 생성함을 source와 회귀로 확인했다. default/v2와 per-class/v3를 각각9×6 완전 재실행·분리 보존했다. 후자는 사후 protocol sensitivity이며 사전 등록으로 주장하지 않는다. AP50/AP50–95는 공통 COCO, 고정 P/R은conf.25/IoU.5, native input과 class IDs0/43/49를 명시했다. v1 DEIM의 누락 비학습 scalar 두 개는 고정source와 대조해 복원 후 strict load했다.
- 실행/결과: PC13 RTX3060/Python3.12.4/torch2.6.0+cu124/UL8.4.152/RF1.11.2/pycocotools2.0.11. 같은 n AP50 SOHAS test7.26→35.69%, Open Images84.90→7.85%, DaSCI29.16→24.03%다. RF Large test38.41%가 높지만 고정 recall30%(custom35%)이며 실제 CCTV8GT도1개만 검출했다. 학습 효과가 보편적이라는 근거가 없고 현재 custom을 최종 D*로 승격하지 않는다. RF Large/Small은 추가 Orin 검증용 기성 기준선 후보다.
- 검증/한계: local4 tests/optional3 skip·CLI guard2·compileall, PC13 전체160 tests17.396s·compileall/기존 ML pip check 통과. 마지막 QA의 pi-heif는 실험 venv에만 추가돼 benchmark 환경과 구분했다. source/weight/truth/prediction hash와 실제 FP32를 확인했다. 표와PNG를 육안 확인하고 SVG XML/PDF 구조를 검사했으며 AI sanity에서 Open Images1장의 누락 annotation 가능성을 기록하되 라벨/판정 수정·사후 제외는 하지 않았다. 최종 GT·독립 camera/session·반복 학습·Orin FPS·event 성능은 미검증이다.
- 기록/다음: [보고서·두 protocol의108개 결과·CSV·그림·논문 문단·hash·원시 경로](../reports/evaluation/pretrained-vs-finetuned-2026-11-04/report.md). raw는 PC13 data/work/multi-model-20261104와 runs/pretrained-vs-finetuned-20261104-v2/v3에 있다. model-data-plan/dataset-source-strategy/verification을 갱신한다. 목표 도메인의 새 독립 GT와 강한 기성 기준선의 Orin 비용을 확인한 뒤 추가 학습 가치를 판단한다. Git은 본 항목 도입 commit으로 추적하고 검증 후 main에 push한다. 다른 채팅의 Catargiu/site 변경은 보존·제외한다.

## 2026-11-04 - 최고 정확도 기성 YOLO26과 현재 개발 모델 비교

- 작업 카드/목적: 사용자 요청의 '최고 성능 YOLO를 테스트셋에서 실행'을 PC13 읽기 전용 비교로 수행한다. 완료 기준은 공식 ready checkpoint 확인·현재 모델 동일 조건 재평가·수치/원시 결과 보존·문서·commit/push다. 위험은 전체 COCO 정확도를 knife 성능으로 오인하고 작은 개발셋/공개된 test를 최종 평가로 주장하는 것이다.
- search-first/범위: 기존 TrainingConfig·승인/hash 검증·review bbox parser·canonical JSONL·bbox evaluator·사후 diagnostic helper를 재사용하고 실험 driver `tools/compare_ready_detectors.py`만 추가했다. 새 의존성·학습·배포 모델 변경·사이트/DB 쓰기는 없다. 공식 ready YOLO26 계열의 전체 COCO 최고 정확도 x와 n 대조군을 사용한다.
- 사용자 직접 요청으로 reserved test23장을 열었고 이후 unseen final test가 아님을 기록했다. 원 split을 보존하고 개발 truth에 original_split/purpose를 명시했다. 기존 source/라벨/session/최종 승인 gate를 우회 승인으로 바꾸지 않는다.
- 실행/결과: PC13 RTX3060/Python3.12.4/torch2.6.0+cu124/Ultralytics8.4.152, custom n640/COCO n640/x640/x1280. 공통 FP32/square/batch1, native AP floor.001, 고정 P/R conf.25·IoU.5. test23/20GT AP50은34.43/6.33/19.44/24.98%, TP7/0/1/1, small TP5/0/0/0(16GT). val에서는 x1280 AP50이59.33%로 custom50.17%보다 높아 작은 test의 우열을 일반화하지 않는다. custom recall35%도 실사용 충분성 증거가 아니다.
- 검증: val/test 전4개 case GPU 실행·native AP와 JSONL 평가 완료 및 config/manifest/authorization/split/weight·평가 image/label hash 보존. 로컬 UTF-8 기존 evaluator7 tests·compileall·명시적 test-open guard 통과. v1/v2 YAML train key 누락은 train=[]로 해결했다. v3 child 완료 후 launcher cp949 로그 출력 실패를 따로 기록했다. 전체 suite/Orin 속도·사건 성능은 이번에 검증하지 않았다.
- 판단/다음: 기성 x 즉시 교체 근거 없음·최종 D* 미확정. 검수 승인된 target-domain/small-knife 보강과 제한된 도메인 fine-tuning 비교가 필요하다. 새 source 채택/학습은 이번에 실행하지 않았다. 문서: model-data-plan/verification 및 [비교 보고/aggregate](../reports/evaluation/ready-yolo-comparison-2026-11-04/report.md). 원시는 PC13 ignored runs/ready-detector-comparison-20261104-v3, 실행 base cf67450+hash-bound driver다. Git은 이 항목을 도입한 commit으로 추적하며 검증 후 main push한다. 다른 채팅의 Catargiu/site 미커밋 변경은 보존·제외한다.

## 2026-11-02 - Orin 약216MiB 증가 원인 분리와 process-only THP 수정

- 작업 카드/요청: camera/GPIO 없이 앞선 VmRSS 증가의 원인을 재현하고 해결한다. 모델·시험 영상·conf/K-N/B0~B3·운영 site/DB·학습/val/test·OS/driver/power는 유지한다. 완료 기준은 Python/native/CUDA/OS 계측 분리, 최소 수정, 같은600초 비교·고정 입력 회귀·문서·commit/push다. 위험은 계측에 의한 실행 양상 변화, THP의 성능 trade-off와 bounded 검사를 장기 안정성으로 과대해석하는 것이다.
- source/search-first: 기존 `profile_orin_file.py`, native runtime/CLI·frozen fixture/weights·실제 CLI 회귀를 재사용하고 표준 ctypes/prctl만 추가했다. 최신 source archive92509ca와 이전 실행 parent93997d6의 core는 동일한 내용을 사용했다. Git pull을 막던 타 작업 문서5개는 backup+clean three-way overlay로 보존했고 이후 원격 문서 추가도 fast-forward했다. runtime/pipeline/detector 판단 코드는 수정하지 않는다.
- 원인 분리: Python trace300초/2,098frame의 tracked peak4.59MB는216MiB 전체를 설명하지 못했다. 반복 중 native/image-lifetime 계측은408초에 수동 중단했으며 성공600초로 집계하지 않았다. 추가 계측을 EOF에만 하는600초에서+155MiB 수준, THP/host/CUDA까지 검사한600.119초/7,515frame에서+211.664MiB를 재현했다. GC43개 수집 후 RSS 불변, malloc_trim 약14.34MiB·CUDA cache 반환 약24MiB, pinned host4bytes→0으로는 주된 증가가 남았다.
- 원인 근거: 실제 kernel THP `[always] madvise never`/max_ptes_none511/2MiB page에서 AnonHugePages 초기403,456→종료972,800KiB와 resident memory가 함께 증가했다. Linux 공식 문서의 sparse 영역 자동 병합과 부합한다. 해당 workload의 지배적 원인은 THP resident inflation으로 좁혔으며 모든 누수 부재를 주장하지 않는다.
- 최소 구현: `jetson_memory.py`는 Linux Orin에서 ML 로드 전 현재 worker의 THP disable flag를 get/set/get(0→1) 확인한다. generic `etr-detect`/`etr-run`과 Orin profiler가 호출하며 provenance에 policy를 남긴다. Windows/non-Orin no-op, 실패 시 모델 생성 전 중단, `--inherit-thp`는 비교용 inherited policy 유지다. 전역 sysfs/boot·driver는 쓰지 않는다. profiler는 두 endpoint의 smaps/전역 policy 불변도 기록한다. 직접 API는 fresh worker에서 같은 preflight를 호출해야 한다.
- 검증/환경: Orin Nano Super/약8GB/NVMe/L4T39.2.0/기존25W, torch2.14.1+cu132/vision0.29.1+cu132/Ultralytics8.4.152/NumPy1.26.4/OpenCV4.11.0.86. local Python3.12.14 UTF-8 mode 관련7 tests, 실제 Orin Python3.12.3 전체153 tests12.955s와 compileall 통과. 최초 local 기본cp1252에서 기존 JSON read test가 실패해 UTF-8 mode로 확인했다. prototype syscall도 실제0→1·global값 불변이다.
- 실측 결과: 수정후600.103초/7,291frame, RSS+11.453MiB(기본값 재현211.664 대비94.59% 억제), AnonHugePages 전후0KiB, event/snapshot275/action error0, 최고57.718°C·기존25W/global THP 전후동일. file 처리율은12.5225→12.1496frames/s(-2.98%), processing mean78.0478→80.4976ms/p9584.5033→86.3092ms였다. 단일 반복의 trade-off이며 camera FPS나 통계적 성능 결론이 아니다.
- 회귀: 공통7,291frame canonical detections 동일·run event ID를 존재 여부로 정규화한 decisions 전행 동일. 별도 실제 CLI valid53/detection59/B3 event·snapshot2/action error0, 같은 JSONL B0~B3 expected4/3/3/2·event frame JPEG·기존 canonical SHA 동일을 확인했다. 같은600초의 event284→275 차이는 처리 frame 수 차이이며 정확도·오경보 개선이 아니다. QA 일부 CRLF source는 raw hash를 보존하고 LF 정규화 후 core와의 동일성도 확인했다.
- 증거/한계/다음: [원인·전후 수치·그림·CSV·aggregate](../reports/runtime/orin-memory-2026-11-02/report.md), raw는 Orin ignored `runs/orin-memory-20261102-v1/`, 진단 script/QA는 `data/work/orin-memory-20261102/`. 이전216MiB 기록은 보존하고 후속 링크로 연결했다. scalar latency/mock 이력의 O(N)와 남은11.45MiB, 실제 camera/GPIO·24h/leak-free·재부팅·정식 runtime 동결은 별도다. 완료 commit은 본 항목의 Git history로 연결한다.

## 2026-10-27 - Orin 파일 운용 오류 수정·통신 격리·600초 반복 점검

- 작업 카드/목적: 사용자 요청에 따라 camera/GPIO 없이 가능한 파일 경로 운용 점검을 진행했다. 범위는 기존 runtime/CLI의 결과 보호·중단 로그·실패 집계, 통신 격리 실제 GPU 파일 실행, 600초 반복과 자원 수집이다. 완료 기준은 최소 실패 재현→수정→관련/전체 tests·실기기 회귀·raw/aggregate·문서·Git 반영이다. OS/driver/firmware/power/clock·학습·검수 사이트/DB·val/test는 변경하지 않는다. 위험은 현재39.2.0 pilot과 계획39.2.1 차이, train montage 과대해석과 메모리 증가다.
- search-first/구현: 기존 canonical runtime/port·OpenCV source·고정 video/weight·Orin file driver를 확장했다. detection/decision/latency 전체 dict 보관 대신 완료 frame JSONL flush, 비어 있지 않은 output 거부, local weight 선검사, all-error CLI exit2, returned snapshot failure 집계, max_frames 초과 source 소비 수정·nearest-rank p95/frame processing 범위를 추가했다. 신규 의존성은 없다. scalar latency/mock alarm 이력은 여전히 실행 길이에 비례한다.
- 변경 파일: runtime/pipeline/detect_cli, 관련 tests3개, Orin smoke tool의 offline-netns 검사와 bounded profile tool, 운영 절차/architecture/Master Plan/open decisions 및 이번 보고서·aggregate. 수정 전 관련 회귀 실패를 확인했다. local Python3.12.14 관련15 tests, 실제 Orin Python3.12.3 전체148 tests13.035s와 tool compileall 통과. 별도 실제 CLI4건은 전부 expected exit2이고 기존7개 output 파일 SHA 불변이다.
- 실기기/명령: basecf67450의 격리 QA archive+overlay, Orin Nano Super/약8GB/NVMe/L4T39.2.0/기존25W, torch2.14.1+cu132/vision0.29.1+cu132/Ultralytics8.4.152. 기존 freeze weight2개/53frame FFV1을 사용했다. `sudo unshare --net -- runuser ... tools/verify_orin_file_smoke.py --offline-netns`는 loopback만/ENETUNREACH와 actual device0 CLI valid53/detection59/B3 event·JPEG2/action error0, same JSONL B0~B3 expected4/3/3/2를 확인했다. 원 host-network run과 detection SHA 동일, host SSH 재접속·원 network 유지다.
- 제한 시간 결과: `tools/profile_orin_file.py --seconds 600`, warmup53 제외600.086s/valid7,375frame/12.2899 file frames/s, B3 event·snapshot278/action error0, inference mean79.0926/p95 85.0422ms, frame-processing mean79.5621/p95 86.4304ms, 최고 관측60.75°C, 최소 MemAvailable5,085,100KiB, 최고 torch CUDA allocated77,524,992bytes. 입력·설정/source SHA와25W 모드 보존, 정상 종료·잔류 profile/tegrastats 없음이다. 파일 처리율은 decode/추론/actions/로그를 포함하고 camera FPS·실제 사건 지연과 다르다.
- 한계/진단: process RSS1,788,572→2,009,448KiB(+215.70MiB)로 원인 미확정이다. 별도 no-ML decode121회/6,413frame/133.746s는73,124→78,088KiB(+4.85MiB)였고 같은 규모 증가는 재현하지 못했다. 전체 경로 attribution·실제 camera 장시간 검사는 남는다. 실험은 train still montage의 제어 회귀이며 실제 event 정확도·GPIO·물리 회선/재부팅 복구·24h/leak-free·TensorRT 증거가 아니다. 라이브러리 half deprecation 경고가 raw에 있으며 설정을 임의 변경하지 않았다.
- 증거/다음: [운용 준비 보고서](../reports/runtime/orin-readiness-2026-10-27/report.md), aggregate에 환경/입력·코드 hash·검증·원시 위치를 기록했다. raw는 Orin ignored `runs/orin-readiness-20261027-v1/`, source/test log는 `data/work/code-qa/orin-readiness-20261027-v1/`. 계획 patch/정식 runtime은 PROPOSAL 유지. 다음은 memory attribution, platform patch 결정, camera/GPIO 확보 후 실제 영상/수동 GT와 동일 D* B0~B3 평가다. 완료 commit은 본 항목의 Git history로 연결한다.

## 2026-10-27 - Orin 최초 원격 접속·native GPU·파일 영상 검증

- 작업 카드/요청: 사용자가 Orin 접속 정보와 계정을 제공했다. SSH→장비/설치 환경→격리 native GPU→기존 새 best.pt 파일 경로를 실제 검증한다. 완료 기준은 key 재접속, GPU kernel/2detector/53frame/동일 JSONL B0~B3/snapshot 원 frame 일치·tests·증거다. OS/firmware/driver/전력 변경, 카메라/GPIO, 새 학습·사이트/DB는 범위 밖이다. 계획39.2.1과 실제39.2.0 불일치를 별도 기록한다.
- 환경/접속: 사용자 authorized_keys에 전용 public key를 추가하고 기존 key/로컬 SSH config를 보존했다. 노트북 alias의 BatchMode 재접속을 확인했다. 비밀값/private endpoint/key는 Git에 넣지 않았다. device-tree Orin Nano Super/p3767-0005, 약8GB/6CPU/swap0, NVMe238.5GiB, Ubuntu24.04.4/kernel6.8.12-1021-tegra, BIOS/L4T39.2.0, driver595.78/system CUDA13.2.2, 기존25W mode1을 관측했다.
- search-first/구현: 기존 canonical adapter·CLI·replay·snapshot 검사/고정PC fixture를 재사용했다. 신규 `tools/inspect_jetson.py`는 제한된 비파괴 inventory와 실제 CUDA matmul/conv/NMS, `tools/verify_orin_file_smoke.py`는 고정 weight/영상 hash와 native CLI/B0~B3/snapshot을 검증한다. `.venv-orin` 격리·Git 제외, submodule 비재귀 clone, PC13에서 모델2개/소량 시험 영상만 전송했다. source dataset은 PC13에 유지한다.
- runtime: 초기torch2.13.0+cu132의 Orin CC8.7 경고/작은 matmul 동작을 관찰했다. PyTorch 공식cu132의2.14.1/vision0.29.1에서 실제 matmul32768·cuDNN conv27·CUDA NMS[0,2]/synchronize 통과, CUDA 경고0이다. Ultralytics8.4.152/NumPy1.26.4/OpenCV4.11.0.86을 고정했다. OS package가 아닌 venv CUDA/cuDNN wheel이며, 점검한 JetPack meta/TensorRT package는 없다. 최초 shell exit 전달 오류도 raw에 보존하고 후속 pip check·kernel·실제 추론으로 성공을 확인했다.
- 실기기 결과: 새knife `d8eff85e…`·person `9b09cc8b…`·PC와동일FFV1 `b16a5692…`를 검사했다. 53/53valid/canonical59, B3 event2/snapshot2/action error0, frame19/40의 decoded image→JPEG bytes 일치. 동일 Orin JSONL의 B0[8,18,32,39]/B1[9,19,40]/B2[18,32,39]/B3[19,40]을 확인했다. full141 tests13.058s·pip check·tool compileall 통과. source base `9ad86e0` + 신규tools, 실행 file-smoke SHA `1976bc970e824bc2bd94b694c920847d288e4b81455f8ab04947c9668db6a531`.
- 기록/영향: [실측·inventory/lock](../reports/runtime/orin-native-smoke-2026-10-27/report.md), [운영 재현](orin-runtime-setup.md), Master Plan/README/architecture/open decisions/통합계획을 갱신했다. 공식JetPack7.2.1 CUDA 구성은10-27 재확인으로13.2.2를 정정했지만 목표L4T39.2.1은 유지한다. raw는 Orin ignored `runs/orin-setup-20261027-v1/`, `runs/orin-file-smoke-20261027-v1/`. commit은 본 항목을 포함한 변경 이력으로 추적한다. 병행 사이트 작업은 별도로 보존한다.
- 한계/다음: 계획 플랫폼/runtime 정식 채택은 아니며 실제39.2.0의 bounded smoke만 VERIFIED다. 학습 이미지 조합은 실제 사건 정확도/오경보/추론 FPS/물리 GPIO 지연의 근거가 아니다. camera node 없음, camera/GPIO·실제 영상/사건 GT·장시간/네트워크 단절·재부팅·TensorRT는 미검증이다. patch 기준 결정과 부품 확보/통합, 검수 승인 후 보강 학습이 남는다.

## 2026-10-26 - Catargiu 전체 조사·ACF 정리·미검수량 정렬

- 작업 카드/사용자 요청: 최초17장은 전체 수량의 상한이 아니므로 Catargiu 원본 전체에서 작은 칼·CCTV 후보를 추가로 찾는다. 현재 진행하지 않는 ACF placeholder를 검수 화면에서 제거하고 미검수량이 많은 순서로 자동 정렬한다. 기존 ID·판정·배정·이력·두 질문과 학습/val/test 경계를 보존하며, source·권리·실제 session gate를 통과했다고 간주하지 않는다.
- 조사/준비: pinned v11 원본24,083장 파일 목록과 수정 라벨을 조사했다. knife-positive5,429장/6,161객체 중 적어도 하나의 knife area≤.02인 이미지는1,331개다. 기존 prefix당6장 제한을 제거하고 전체 SOHAS5,859개 signature cache·현재 검수1,219개 fresh bytes·보호864 signature와 대조했다. 보수적 격리524개 후4,905개에 기존 COCO person pretrained를 GPU로 적용했다. 이는 선별 힌트이지 정답/새 학습이 아니다. 내부 visual component 대표에서 모든 칼 박스가2% 이하인754개와 낮은 시점 카메라형8개를 준비했다. 칼 라벨 없는 source도 조사해 CCTV형14개를 별도 준비했다. 전체776개 검수 대기/학습 미승인이다.
- search-first/변경: 기존 pack builder·signature/proxy·BatchReviewStore·consistent backup·격리 QA를 재사용한다. `/api/catalog`은 `remaining=total-reviewed`로 내림차순 정렬하고 준비되지 않은 항목은 뒤에 둔다. 화면에서 미검수량을 표시하며 cached back 복귀 때 중복 카드 없이 다시 읽는다. config helper는 준비량/registry/배정0인 ACF placeholder를 다시 생성하지 않는다. 원본·연구 근거를 삭제하거나 이미 배포된 source registry를 제거하는 변경이 아니다.
- 검증: PC13 Python3.12.4의 `2ef3501` archive+candidate overlay에서 관련15 tests·전체141 tests/compileall, 로컬 JS syntax 통과. 새 회귀는 총량과 미검수량 순서가 다른 상황·저장 후 순서 변경 및 config 재실행의 ACF 비복원을 검사한다. 새 코드+복제 DB QA에서 Android412/iPhone390px(모두 Edge Chromium)으로 신규 양성/칼 라벨0 배치 저장·필수 메모·재접속·이어가기·409·기존17개 판정 불변·미검수순/ACF 부재/캐시복귀 중복 방지/질문2/버튼46px/overflow0을 확인했다. 운영 테스트 판정0이다.
- 배포 상태: 현재 source 준비와 code/격리 QA까지 완료했다. 검증된 code를 commit/push한 뒤 서비스 정지 구간의 fresh 재검사·DB/config backup·776장 append·ACF placeholder 제거·기존 테이블 hash 보존·공개 HTTPS를 확인한다. 실제 배포 결과와 source 한계는 후속 기록으로 연결한다. raw는 PC13 `data/review/catargiu-full-expansion-20261026/`에 둔다.

## 2026-10-26 - 새 best.pt의 PC 영상 파이프라인 통합 검증

- 작업 카드/요청: Orin 접근·검수 완료를 기다리는 동안 신규 best.pt의 PC 영상 연결을 검증한다. 사용자는 쓸 촬영 영상이 없음을 확인했다. 완료 기준은 새 model/class map·영상 decode·동일 JSONL B0~B3·상태/경보 중복 억제/rearm·metadata/snapshot 원 frame 일치다. 실제 움직임/정확도·Orin·GPIO·source 채택·학습·사이트 DB는 범위 밖이며 조합 영상의 event 수를 논문 효과로 오해하지 않도록 한다.
- search-first/구현: 기존 `build_detector`, `OpenCVFrameSource`, `run_detection_stream`, `run_live_pipeline`, replay CLI와 source/hash 승인 검증을 재사용했다. 신규 `tools/verify_development_video.py`만으로 weight/class 확인→train137 probe→fixture 구성→실제 GPU 추론→결과 assert를 재현한다. 기존 runtime·기본 설정·의존성·운영 사이트는 수정하지 않았다. person.5/knife.25/640/schema2 alpha.25/K2-N3/rearm2는 smoke용이다.
- 실측: PC13 RTX3060/Python3.12.4/torch2.6.0+cu124/Ultralytics8.4.152. knife `d8eff85e…`·person `9b09cc8b…`를 연결했다. train3 이미지와 blank의53frame/10fps/FFV1 영상은 전frame lossless decode, valid53/canonical59다. 동일 JSONL에서 B0 events[8,18,32,39], B1[9,19,40], B2[18,32,39], B3[19,40]. Live B3 event2/snapshot2/action error0·전4상태 통과. frame19/40의 JPEG 재생성 bytes와 저장 snapshot이 일치하고 첫 snapshot frame019를 눈으로 확인했다. 53개 pixel hash가 모두 달라 binding 오류를 검출할 수 있다.
- 오류/CLI: knife component frame21 예외1회는 partial detection을 버리고 valid52/error1·K2/N3 confirmation 유지. 21/22 연속 예외는 valid51/error2·22 cooldown·이후 clear/rearm/재등장 확인. 두 경우event19/40만 발생, snapshot2/action error0. 실제 고장이 아닌 fault injection이다. 별도 `etr-run.exe`도 성공했고 source ID까지 맞춘 detection-only/live API/CLI JSONL hash `4d92ee6524860051e2973ae77b864b6aa68fd8d726041c4451ff4a3be94429da`가 일치했다.
- 검증/기록: 관련6 tests 후 전체138 tests·driver compileall 통과. source base `baf6106` + 신규 driver, 실행 script SHA `3b1b71eb256ab6724bf17e9176233c4bf40f1b93c9b808c4668db3442ab63567`. raw는 PC13 ignored `runs/runtime/best-pc-video-20261026-v1/`, log는 `data/work/code-qa/pc-video-integration-20261026-v1/`. [보고서·evidence](../reports/runtime/development-best-video-2026-10-26/report.md), architecture·verification·Pre-Orin·Master Plan의 PC 상태를 갱신했다. Git commit은 본 항목과 tool을 포함한 변경 이력으로 추적한다.
- 한계/다음: 모델이 반응하는 train fixture를 골랐으므로 실영상/사건 precision·recall/오경보·추론 FPS·GPIO 지연의 근거가 아니다. val/test는 추론하지 않고 승인 무결성 hash만 검사했다. 사이트 신규150장 검수와 source gate 후 실사 보강, 실제 영상/수동 사건 GT·Orin·카메라/GPIO 통합은 남는다. 개발 후보·threshold를 최종 연구 결정으로 승격하지 않았다.

## 2026-10-26 - Catargiu·ATM·Dangerous 추가304장 검수 배포

- 작업 카드/이유: 사용자 승인에 따라 작은 칼·CCTV 후보를 확보하고 중복 검사 후 기존 두 질문 사이트에 추가한다. 저자 메일은 초안만, 나머지 후보는 순서대로 원본/접근성을 확인한다. 완료 기준은 pinned source·실제 sample·보호 경계·백업·격리 QA·기존 DB 보존·공개 접속이다. 원본 권리 해결·학습·기존 val/test 재분할은 범위 밖이다.
- search-first: 기존 source prep/ReviewStore/BatchReviewStore·SQLite backup/hash·두 질문 UI·browser QA를 재사용했다. `configure_team_review.py`는 기존 catalog 밖에 추가된 source와 운영 설정을 재실행 시 보존한다. 기존 bounded RangeReader에 signed query를 유지하는 옵션만 추가하고 관련 회귀2개를 작성했다. 새 framework/의존성/질문은 없다.
- 확보: Catargiu v11+저자 commit `382d925c` 수정 라벨에서 작은 knife75장 확보→보호 filename family33·보호 visual2·기존 visual3 격리→37개 시각 점검 후 제품/게임 등20개 이번 묶음 제외→사람·knife17개. CCTV 시점은 팀 검수 대상이며 확정하지 않았다. ATM pin `8b110306` 원본237/미리보기2개 제외, class3 knife116 images/118objects. knife 파일명3개는 knife 라벨0인 누락 후보다. Dangerous 원본357,834,955 bytes MD5 확인/4,000XML 파싱, 기존100개 중55개 exact image의 overlay가 원본과 일치했고5class×5 paired labels로 raw1=Knife 등 map을 대조했다. 새 작은 칼50개는 semantic Knife에서 직접 준비했다.
- 배포/보존: Catargiu17/ATM237는 새 source, Dangerous50은 기존 IDs0–99 뒤의100–149 배치다. 전체915→1,219장. PC13 `data/review/additional-sources-20261026/`에 preparation/deploy backup·audit·보존 비교·격리 QA·최종 상태를 보관했다. 기존 모든 review/history/metadata·users/assignments row count/hash 동일, registry10행 유지+3행, 새 테스트 판정/배정0. DEV manifest·train/val/test·YAML/config/authorization과 pack 입력도 동일하다. source 원본/큰 파일은 PC13에만 저장했고 로컬에는 작은 QA 자료만 뒀다.
- 검증: 게시304개의 원본·라벨·hash/decode/dimension 및 기존915개/보호864개 signature/proxy를 fresh 재검사했다. 게시된 자료의 exact/보호 충돌0, 신규 source끼리 dHash 후보0. ATM 내부 visual 후보3쌍은 별도 기록한다. 실제 session·모든 crop/flip 중복·negative 진위·좌표 convention은 미검증이다. Windows 긴 경로/CRLF 문제는 원본 Git archive의 blob 대조로 해결했다. 처음 tests-only QA는 configs 부재로 실패했고 tracked archive 격리 환경에서 PC13 Python3.12.4 전체140 tests/compileall 통과했다.
- 웹 검증: 복제 DB에서3개 묶음×Edge Chromium Pixel7/iPhone13 크기 프로필로 자동 저장·필수 메모·재접속·최근 이어가기·reload·충돌409·기존 Dangerous100 판정 불변을 확인했다. 질문2/버튼46px/overflow0이다. 실제 Safari/WebKit·실물 설치는 미검증. 공개 HTTPS 이름 선택·옛/새 image IDs를 읽었고 운영 claim/save는 차단했다. Scheduled task Running, 배포 직후1,219장/466판정을 확인했다.
- 저자/남은 후보: 공식 corresponding author Daniele Berardini 앞으로 비상업 학술용 knife 자료·camera/sequence ID·5인 팀 접근/표시 조건을 묻는 Gmail 미발송 초안을 작성했다. ACF 원 API404 재확인, URBANITE helper22파일의 pin/README를 확보했으나 full RGB/knife bbox 경로는 미확인, AIMs2는 provenance 설명 부재로 보류한다. 기존 Open Images validation·US Mock 평가 역할과 팀원 Legacy 트랙은 유지한다.
- 문서/다음: [상세 source·mapping·검증·원시 경로](../reports/datasets/additional-review-2026-10-26/report.md), source strategy/운영 안내/verification을 갱신한다. 새304개 human review와 권리/라벨/독립성 gate 후에만 실사 보강·합성 별도 ablation을 검토한다. 자동 학습/모델 채택은 하지 않았다. 이 항목 포함 Git commit으로 변경을 추적한다.
- 원본 보관 마감: 공식 브라우저 다운로드로 로컬에 생긴 Catargiu v11 ZIP1,363,496,844 bytes를 PC13으로 전송했다. 양쪽 SHA-256 `e77e054a…8d0ff02` 일치·전체48,170 ZIP entry CRC·게시17개 원본 hash를 확인한 뒤 노트북 중복본을 삭제했다. 이후 준비 script는 PC13 archive를 먼저 읽는다. 제공자 선언 checksum은 없으며 이미 배포한 pack/판정은 수정하지 않았다. QA8795와 SSH tunnel은 종료하고 운영8770을 유지했다.

## 2026-10-26 - SOHAS 작은 칼100장·혼동 음성 후보50장 사이트 배포

- 작업 카드/범위: 사용자 지정 준비 commit `9563fba`와 PC13 `data/review/sohas-gap-20261026-v1/README.md`·`summary.json`을 확인했다. 기존 SOHAS에150장을 append하되 기존 image ID/판정/version/history/계정/배정을 보존하고, 이름 선택·공통 두 질문을 유지한다. 완료 기준은 fresh cross-pack 중복/보호 proxy 재검사·consistent backup·격리 QA 저장/재접속/이어가기/모바일·외부 HTTPS·전후 보존 비교다. 원본 변경·새 질문·학습·기존 val/test 재분할은 범위 밖이다.
- search-first: 기존 `BatchReviewStore`·team registry·`team_review_status.py`의 SQLite backup/테이블 hash·`check_team_review.py`·기존 browser QA 흐름을 재사용했다. 신규 runtime 코드/의존성/사이트 기능 변경 없이 ignored 운영 config에 `20261026-small-positive-v1`(100장, global ID200–299), `20261026-negative-mined-v1`(50장, ID300–349) 두 immutable pack을 연결했다. 기존 prefix ID0–199와 base fingerprint/draft identity는 그대로다.
- 재검사: 운영 config의 전체765개 image bytes를 evidence hash와 대조하고 신규150장 image/source/XML SHA-256·Git blob·decode/dimension/raw bbox·selection lineage를 확인했다. 기존765장과 신규150장 exact 중복0·신규 내부 중복0이다. 원본 integrity/pairs와 DEV-manifest hash를 준비 summary와 비교하고 기존 proxy helper로 다시 계산한 protected val/test group 교차0을 배포 직전에 재확인했다. 실제 camera/session 독립성·원래 좌표 의미·50장 실제 knife 부재는 미검증이다.
- 백업/반영: PC13 ignored `data/review/sohas-gap-deployment-20261026/before-preparation-backup/` 및 서비스 정지 구간의 `before-deploy-backup/`에 SQLite backup API로 DB/config/status를 보관했다. 배포 작업 약4.8초 후 `ETR-Team-Review` Running을 확인했다. 기존 모든 reviews/history/metadata·team users/assignments의 row count/hash가 동일하고 기존 registry8행을 유지한 채2행만 추가했다. 기존 pack/schema/원본은 재생성하지 않았다. 신규 DB reviews/history0을 확인했다. `DEV-manifest`, train/val/test 목록·data YAML·training config·development authorization 및 gap pack 입력 bytes도 그대로다.
- 검증: PC13 Python3.12.4 관련 team12 tests·전체138 tests와 compileall 통과. 실제 원본을 읽되 DB는 전부 복제한 별도 loopback8795 QA에서 테스트 계정만 사용했다. Edge Chromium의 Pixel7(412px)/iPhone13 크기(390px) 프로필에서 새 양성·음성 배치 자동 배정→두 질문 자동 저장→다음→쿠키/임시 입력 복원→최근 검수 이어가기→메모 저장→reload, version409와 기존200개 판정 불변을 확인했다. 가로 overflow0, 버튼46px, 질문2개다. Safari/WebKit·실물 휴대폰 설치는 이번에 시험하지 않았다.
- 공개 접속: 실제 Funnel HTTPS에서 normal HTML form 이름 선택·SOHAS350장/4batch·준비 후보7개·기존/신규 global ID0,100,200,300,349 image200 응답·동일 두 질문과 모바일 두 크기의 overflow0을 확인했다. production QA의 claim/save는 차단했으며 테스트 판정0·테스트 배정0이다. 저장 테스트는 QA DB에만 남겼다.
- 결과/증거: 배포 직후 전체915장/466개 저장 판정, SOHAS350장/199판정/history268·재확인16, 신규150장 판정0이다. 50장은 확정 음성이 아니며 전량 검수 대기/학습 승인 false다. 당시 README/summary/selection/contact sheet는 준비 기록으로 수정하지 않았다. 원시 audit/DB 보존 비교/proposed config/QA DB는 PC13 ignored `data/review/sohas-gap-deployment-20261026/`, 브라우저 결과/화면은 개발 PC 동일 ignored 경로에 둔다. 운영용 일회성 script는 PC13 `data/review/sohas-gap-deployment-20261026-operations.py`에 보관했다. QA 서버/SSH tunnel은 검증 후 종료하고 운영8770만 유지한다.
- 문서/다음: 운영 안내·verification과 본 로그만 commit/push한다. 실제 검수와 별도 source/좌표/negative/group/recipe 승인 후에만 보강 학습을 검토한다. 이번 배포는 모델 선택·새 학습·val/test 이동/재분할을 하지 않았다. commit은 본 항목을 포함한 Git history로 추적한다.

## 2026-10-26 - 낮은 개발 성능의 오류 진단과 제한된 후속 실험

- 작업 카드/사용자 요청: 낮은 성능의 원인을 검증하고 데이터 보강·다음 학습을 진행한다. train/val 예측에서 fit/generalization·confidence·localization 문제를 분리한다. 완료 기준은 고정 split 진단, 시각 점검, 제한된 후속 학습과 동일 기준 비교다. 검수 DB·판정·reserved test·공식 R1/H1 승인은 변경하지 않는다. 위험은 val14 객체의 분산·튜닝 편향, 합성 보강의 domain gap과 source gate 혼동이다.
- search-first: 기존 bbox 평가기·canonical JSONL·승인/hash 검증·training runner·detached launcher를 재사용했다. `training_diagnostics.py`는 train/val만 추론하고 confidence .05/.1/.25/.5와 IoU .25/.5를 비교한다. 개발 GT는 train diagnostic/tuning만 허용한다. `training_refinement.py`는 DEV-SOHAS manifest/세 partition 목록을 보존하고 optimizer+LR(AdamW/.001), 별도 scale=.9 variant만 만든다. source 추가·공식 승인 승격은 하지 않는다.
- 관측: SGD best의 conf=.25/IoU=.5에서 train TP117/FP14/FN10, val TP1/FP0/FN13. val conf=.05에서도 TP4/FP7/FN10이다. val GT14개 중 detected1/low-confidence3/localization1/missed9(.05 floor)이며 단순 confidence 완화는 부족하다. 객체 면적 중앙값 train .06867 vs val .004843, small(.02 이하)26/127 vs11/14다. fit/generalization·크기 분포 차이를 지지하지만 단일 원인의 인과 증명은 아니다.
- 시각 점검: val23개를 4개 AI diagnostic contact sheet로 확인했다. 작은 손-held knife 미검출, 일부 위치 오차·의류/배경 FP가 있다. 기존 사람 판정은 수정하지 않았다. COCO pretrained도 같은 train/val에서 비교했다.
- 검증: PC13 Python3.12.4 격리 source overlay에서 전체136 tests·compileall 통과. 신규6 tests는 개발/최종평가 분리·test image 미열람·예측 identity 오류·오류 분류·split/base bytes 보존·bounded 설정·부모 hash 변조 차단을 검사한다. 최초 .001 예측은 저신뢰도 zero-area 출력으로 evaluator가 거부했다. 진단 sweep 최소값 .05로 예측 floor를 맞춰 재실행했고 실패 산출물도 보존했다.
- 다음: 동일 초기 weight/640/batch16/50epoch/seed/137 train·23 val에서 AdamW/.001 비교, 추가로 같은 AdamW에서 scale=.9만 바꾼 증강 비교. 각450 planned updates이며 같은 val을 재사용하는 탐색이다. DaSCI 정상92장(97 objects 중 small88), Simuletic 정상71장(positive60/negative11, small60/60)은 보강 audit 후보로 아직 병합하지 않는다. 결과·raw 경로는 후속 보고서에 기록한다. Git commit은 본 항목의 변경 이력으로 추적한다.
- 완료 결과: 두 후속50epoch/exit0 학습을 완료했다. best 재검증 mAP50/50–95는 SGD .265761/.102469, AdamW .468685/.184558, AdamW+scale.9 .552030/.207160이다. 고정 conf=.25/IoU=.5 val TP/FP/FN은 1/0/13→5/5/9→6/3/8, small TP는1/11→3/11→4/11이다. 개발용 후보는 마지막 best.pt(hash `d8eff85efff890041d67f9aea80d3d0d7a9530312eb7c2da2baace5e3840c043`)로 기록했다. manifest/pretrained/세 list hash 동일·reserved test 평가0을 확인했다. 공식 D* 채택이나 threshold 동결은 하지 않았다.
- 보강 작업: `dataset/reinforcement_audit.py`로 reviewed DaSCI92/Simuletic71의 fresh byte/dimension/bbox와 보호 group 연결을 검사했다. DaSCI는 후보 filename family 제외 시18개, 포함 시92개가 보호 proxy와 연결됐고 Simuletic은0개다. 실제 중복/session 판정은 아니다. `tools/prepare_gap_review.py`는 기존 source parser/copy renderer를 재사용해 SOHAS 미검수 작은 칼100장+혼동 물체 음성 후보50장 팩을 PC13에 생성했다. 음성512장 실제 GPU probe 후 group/class 균형으로50개를 골랐고 모두 knife prediction≥.05였다. 확정 음성으로 승인하지 않았다. 기존765 review hash/보호 proxy와 선택 교차0·unique150·pinned blob/XML/decode 검증 및 input hash 보존을 확인했다. 새 검수/배정/DB/사이트 write0이다.
- 검증/인계: 신규 proxy-link2 tests를 포함한 PC13 격리 전체138 tests·compileall 통과, 새 팩 실제 생성·표본 sheet 점검 완료. 원시 자료는 `runs/diagnostics-sohas-20261026-*/`, `runs/development-error-analysis-20261026-v1/`, `data/work/reinforcement-audit-20261026-v2/`, `data/review/sohas-gap-20261026-v1/`에 보관한다. 사이트 담당용 한국어 README를 팩에 넣었다. [상세 결과·재현·보강/학습 순서](../reports/training/development-error-analysis-2026-10-26/report.md), aggregate JSON, model-data-plan/source-strategy/CUDA handoff를 갱신했다. 다음은150장 사이트 append·검수/source gate 후 실사 보강 run이며, 현시점 source 추가 학습은 실행하지 않았다.

## 2026-10-26 - 승인된 SOHAS 검수 subset 개발용 예비 학습

- 사용자 결정/작업 카드: 정상 SOHAS183개만의 개발용 예비 학습을 명시적으로 승인했다. Source/review byte·모든 bbox·decode·복사본/label 검증, filename-family+전체 dHash transitive component 분할, 범위와 hash를 묶은 DEV-SOHAS 승인, CUDA 사전검사와 실제 학습 시작 증거를 완료 기준으로 둔다. 공식 R1/H1 승인/논문 성능·source 전체/원 좌표 의미·실제 recording session·외부 재배포는 범위 밖이다.
- search-first: 기존 SOHAS parser/blob 검사·image_signature·group split planner·label parser·copy helper·training runner/preflight를 재사용했다. 신규 exporter는 raw VOC와 review snapshot의 얇은 연결이며 일반 downloader나 framework를 추가하지 않았다. 기존 R1/H1의 7개 gate는 그대로이며 DEV-SOHAS에는 사용자 승인된 제한 scope를 별도로 강제한다.
- 변경: `dataset/development_subset.py`, 기존 `training.py`의 개발 전용 범위 검증·evidence, 신규 tests, CUDA handoff/open decisions/architecture. 원본과 DB는 쓰지 않고 새 copied output만 만든다. Input hash·list·group·negative·review version·공식 승격 거부와 최종 평가 false를 기록한다. 기존 profile에서 640px/batch16/50epochs/FP32/SGD/workers0을 재사용한다.
- 검증: 신규6 tests는 로컬 bundled Python3.12.14에서 통과. Windows 재설치 후 기존 로컬 venv는 옛 Python 경로를 참조해 실행 불가이며 수정/재설치하지 않았다. Bundled 환경의 전체130 tests 시도는 werkzeug 부재1 error/12 skipped로 전체 통과가 아니다. PC13 기존 venv와 분리된 ignored QA tree에서 전체130 tests/compileall 통과했다. 첫 전체 실행은 기존 HTTP fixture의 Windows socket10053으로1 error였고, 해당7 tests 및 전체130을 다시 실행해 통과했다. production 서버/DB는 수정하지 않았다. 실제 데이터 수·학습 시작은 후속 기록으로 연결한다.
- 한계: Proxy group은 실제 session 확인이 아니며 literal pixel-edge 개발 계약은 원 convention 확정이 아니다. 사용자 범위 승인을 원본 미검수 corpus나 공식 결과로 확대하지 않는다. Raw/판정/승인/weight/log는 PC13 ignored 경로에만 둔다. 이 항목 포함 Git commit으로 코드·실행을 추적한다.
- 실제 준비 `b094713`: 183장 전량/161 objects, proxy17개, train137(양성97/음성40)·val23(13/10)·reserved test23(20/3), 제외0으로 materialization 완료. 모든183개 선택 판정의 현재 version/hash가 snapshot과 같음을 재확인했다. CUDA/hash-bound 승인 preflight 통과했다. 첫 이중 encoded launch 시도는 Windows command-line 길이 제한으로 실행 전에 실패했고 launch directory·invocation·trainer0을 확인했다. 반복 가능한 짧은 hidden CIM worker script `tools/start_development_training.ps1`로 보완한다. 기존 run/DB/전원 설정은 바꾸지 않는다.
- 실제 실행 `b390fe9`: Run `sohas-reviewed-development-20261026-v1`, hidden CIM PID18636를 띄운 시작 SSH 종료 후 새 SSH에서 GPU epoch loss·30/50·최종50/50·runner passed·launcher exit0을 확인했다. Duration203.265s, best validation P.5354/R.2143/mAP50 .2658/mAP50-95 .1025로 낮으며 최종 성능이 아니다. Best SHA `83fe8cee46d50c52a2fe0beb12f2fae8531c7ce9d1c0b5d9bc91980925353cc7` 및 last 저장, class0knife reload·GPU composite canonical1 valid frame smoke 통과. Test23장은 미사용이다. Raw는 PC13의 ignored `data/processed/<RunId>/`, `runs/training/`, `runs/launch-<RunId>/`, `runs/development-checkpoint-smoke-20261026-v1/`. [aggregate 보고·한계](../reports/training/sohas-reviewed-development-2026-10-26/report.md). 원본·검수 서비스·시스템 전원 설정은 불변이며 원인 분석 없이 추가 corpus/학습을 자동 확장하지 않는다.

## 2026-10-26 - 검수 완료분 학습 요청과 실제 readiness 확인

- 요청/작업 카드: 사용자가 검수 완료 자료로 학습 실행을 요청했다. 최신 운영 판정의 읽기 전용 집계, GPU/기존 job·weight·승인 입력 확인과 안전한 학습 진입을 범위로 잡았다. 기존 DB·판정·사이트·미검수 원본을 수정하거나 검수 완료를 source 전체 승인으로 확대하지 않는다.
- 재사용/환경: `search-first`로 기존 `dataset.review_candidates`, `training_pair check`, hash-bound approval gate를 확인했다. 새 학습 우회 경로·dependency·설정 완화를 만들지 않았다. PC13 Python3.12.4/torch2.6.0+cu124/CUDA true/RTX3060 12GB, GPU utilization0%·478MiB 관찰, 확인된 Python job은 검수 서비스였다. 로컬 `yolo26n.pt`가 존재한다. 양 저장소 pull/status는 정상·clean이었다.
- 최신 판정: 준비765/판정466/미검수299. SOHAS199/200 중 정상183(knife 양성130/부재53)·문제/모름16, DaSCI92/93 정상92, Legacy26/128 정상25, Simuletic77/114 정상71, US25/100 정상21, Dangerous30/100 정상24, Open Images17/30 정상16. 정상 전체432/문제·모름34이며 source-role/mapping/원 split gate는 유지한다. 실제 recipe를 승인한 집계는 아니다.
- 실제 명령/증거: PC13 repository root에서 `python -m edge_threat_response.dataset.review_candidates --config data/review/team-server/config.json --policy configs/datasets/review-candidate-policy.json --output-dir data/work/review-candidates/20261026-training-v1`; 이어 `python -m edge_threat_response.training_pair check --plan configs/training/sohas-pair.pc13.json --manifest data/processed/sohas-reviewed-v1/materialized-manifest.jsonl --checkpoint yolo26n.pt --output-dir runs/sohas-reviewed-readiness-20261026-v1` (`PYTHONPATH=src`, `.venv-ml` 사용).
- 결과/한계: 집계 exit0, readiness expected exit2/blocked/`missing=approved_materialized_source_manifest`/`training_started=false`. PC13 `data/processed`와 approval 파일은 미준비다. 기존 source 좌표 의미·camera/session group/split 검증을 정상 표본 판정만으로 완료 처리하지 않는다. 사용자 학습 요청은 받았으나 미확인 gate의 사실 여부를 대신하지 않는다. 코드·학습 설정 변경이 없어 unit tests 재실행은 하지 않았다.
- 다음 판단: SOHAS 정상183개만 쓰는 개발용 예비 학습을 공식 R1/H1·최종 연구 평가와 구분하여 먼저 허용할지 사용자에게 제안한다. 이 개발 범위의 좌표 계약·보수적 proxy grouping과 그 한계를 명시적으로 정한 뒤 준비해야 하며, 기존 승인 gate를 조용히 해제하거나 인간 검증으로 위장하지 않는다. full training/평가 수치는 이번 작업에서 생성하지 않았다. Git은 이 기록을 포함하는 commit으로 추적한다.

## 2026-10-04 - 검수와 독립적인 SOHAS 전체 이미지 준비·검출 평가 기반

- 목적/작업 카드: 사용자가 물리 작업·팀 판정이 선행되지 않는 준비를 위임했다. (1) PC13 pinned SOHAS 전체 image 확보·구조/byte/decode 검사, (2) 후보 간 heuristic 유사 pair 진단, (3) 고정 threshold knife bbox·small recall·negative FP 평가기를 완료 기준으로 둔다. 사이트/DB/판정 수정·미승인 source 채택·full training·촬영/Orin은 제외한다. 원본·개인자료 외부 공유를 하지 않는다.
- search-first 선택: 기존 SOHAS parser/blob/inventory·canonical detection parser/BBox·Pillow·JSONL/evidence helpers를 조합했다. 새 dependency/서비스/계정이나 일반 downloader를 추가하지 않았다. screening은 output-only이며 정확/유사 중복·원 split 교차를 분리하고 좌표 compatibility를 approval로 사용하지 않는다. bbox 평가는 confidence-first 일대일 IoU이며 event 평가기와 분리한다.
- 확보: 공식 pinned Git tree API image size 1,861,407,276 bytes·5,859장 확인, PC13 free 약151.7GB에서 기존 byte-exact non-cone staging의 두 image directory만 추가했다. Git sparse-checkout add의 --no-cone 옵션은 지원되지 않아 기존 non-cone 설정 확인 후 옵션 없이 재실행했고 전체5859장을 확보했다. 노트북 전체 복사/Drive 업로드 없음. 새 VOC audit 구조 오류0·knife2349·YOLO2277·불일치58·orphan83·좌표 unknown·approval false를 재확인했다.
- 변경: `dataset/image_screening.py`, `detection_evaluation.py`, fixture/tests와 검수 기준·CUDA handoff. Decode/변조/dimension·출력 보호·exact/visual/low-info/aspect gate·pinned XML identity, bbox TP/FP/FN·small/음성 FP·분모0·status/partition/완전성·missing/error row 거부를 검사한다. 검증/실제 실행 결과와 aggregate 증거는 후속 기록으로 연결한다.
- 실행 증거: `f774a1a`/`b86a5a6`로 양 PC 전체124 tests·compileall 및 PC13 실제 CLI 통과. Full source5859/review765 decode·hash·dimension 오류0. SOHAS exact1쌍/visual5353쌍/원 split 교차1575쌍·두 좌표 규약 모두5859호환·EXIF orientation0 한 장. Cached 교차 비교6424 records(중복 review 사본200생략)에서 exact5쌍/visual5756쌍/cross-source34쌍 확인, 신규 exact4쌍은 SOHAS–Dangerous. 캐시 비교는 새 raw 검사/확정 session이 아니다. synthetic bbox CLI TP2/FP2/FN1·small1/2·negative FP1로 계약 확인. 서비스/DB 수정 없이 public login200. [aggregate 증거](../reports/datasets/image-screening-2026-10-04/report.md), private raw는 PC13 `data/work/image-screening/`와 `runs/detection-evaluation-synthetic-20261004-v1/`.
- 한계/다음: 유사 pair는 동일 scene/session 증명이 아니며 crop/flip 탐지를 보장하지 않는다. 권리 충돌·원 좌표 의미·전체 visual completeness·session/group split·recipe 승인이 남는다. 가상 평가를 모델 품질·실기기 결과로 보고하지 않는다. human gate가 완료된 뒤 source materialization·R1/H1 실행으로 간다. Git은 이 항목 포함 commit으로 추적한다.
- 사용자 최신 장비 확인: 처음 수령 전이라고 답했으나 후속 메시지에서 Orin 보유·원격 미설정·카메라/GPIO 미확보로 정정했다. 최신 직접 확인을 `USER_REPORTED`로 Master Plan/P0-01/pre-Orin에 반영한다. 실제 OS/JetPack·SKU·firmware·CUDA·GPIO 검증으로 승격하지 않는다. 부팅/원격 설정은 물리 작업이 필요하므로 사용자 확인 후 안내한다.

## 2026-10-04 - 웹 판정 read-only snapshot과 학습 후보 연결

- 목적·작업 카드: 검수 사이트의 실제 판정을 학습 준비에 연결하는 1단계를 진행한다. 운영 DB/이미지/배정/history를 쓰지 않고, 초기/추가 batch ID와 image hash를 판정에 연결한 미승인 후보 및 aggregate 보고를 만드는 것이 완료 기준이다. 사이트 UI·배포·실제 학습은 범위 밖이다.
- 선택: `search-first`로 기존 ReviewStore와 팀 registry/판정 해석을 확인했다. constructor는 DB migration을 쓰므로 호출하지 않고 기존 `review_verdict`와 stdlib SQLite read-only transaction을 재사용했다. 별도 service/dependency/계정/CSV 제출을 추가하지 않았다.
- 변경: `dataset/review_candidates.py`, source-role/mapping policy, fixture tests, 검수 기준·architecture·pre-Orin·verification. 현재 ready pack의 bytes/fingerprint/ID/배치 registry를 확인하고 source별 domain/양성·음성·판정과 원 split을 집계한다. 정상 비-CCTV는 자동 제외하지 않는다. 불완전 음성 근거·Dangerous mapping·cross-source exact duplicate는 보류하고 synthetic/external 후보를 실사 train 목록에서 분리한다. 모든 결과는 `training_approved=false`이며 materialized 학습 manifest가 아니다.
- 개발 검증: Windows/Python3.11.9에서 신규 6 tests와 전체113 tests 통과. 원 입력 전체 bytes 보존·SQLite 쓰기 거부·missing DB 비생성·pack hash/registry/image 변조·추가 offset·legacy/v2 해석·negative 충돌·external 중복·출력 덮어쓰기/입력 directory 보호·이름/credential/메모 미출력을 확인했다. 초기 fixture 수정용 SQLite 연결이 닫히지 않아 Windows cleanup 오류가 났으며 테스트 연결을 명시적으로 close해 해결했다. production 코드의 read-only 연결은 처음부터 finally-close였다.
- PC13 실증: 구현 commit `8cd14d9`를 fast-forward 적용한 Python3.12.4에서도 전체113 tests/compileall 통과. 22:17 KST 운영 자료 765개/판정309개를 read-only로 연결해 실사 후보180(양성152/음성28), 합성36, 외부평가21, 보류72(판정32/mapping24/Open Images 원 split16), 미검수456을 기록했다. ready pack 간 exact duplicate는0그룹, 모든765행의 approval=false·8개 pack writes=0을 재확인했다. 사이트/service/판정 DB를 수정·재시작하지 않았다. 원시 `data/work/review-candidates/20261004-v1/`, 공개 [aggregate 증거](../reports/datasets/review-candidates-2026-10-04/report.md).
- 한계·다음: 여러 DB의 snapshot은 DB별 transaction이고 하나의 전역 atomic 시점이 아니다. 전체 source/near duplicate/권리/좌표/group split/recipe 승인과 YOLO export는 남는다. 원시 목록은 PC13 ignored 데이터 공간에 보관하며 human 판정·사이트·DB를 변경하지 않는다. full training은 미실행이며 commit은 이 항목을 포함한 이력으로 추적한다.

## 2026-10-04 - SOHAS 추가 검수 배치와 보존형 연결 구현

- 목적·작업 카드: 사용자가 인계 메모를 기준으로 검수 확대를 요청했다. 공통 두 질문·이름 선택을 유지하고 기존 image/판정/version/history/배정을 보존하면서 SOHAS부터 100장을 추가한다. 완료 기준은 consistent backup·추가형 registry·고정 ID·중복 차단·fixture 저장/재접속·모바일·PC13 배포다. 원본·학습 source 자동 병합과 학습 실행은 제외한다.
- 선택·변경: `search-first`로 기존 ReviewStore·Flask·준비 renderer·SQLite backup을 재사용했다. 별도 새 서비스/의존성 없이 BatchReviewStore와 team registry, stale client 목록 보호, 기존 configure의 batch 보존·check helper의 배치별 이미지 확인을 추가했다. 기존 immutable pack은 그대로이고 새 pack이 동일 source 뒤로 연결된다. 원래 pack hash와 ID를 유지해 draft·session·기존 배정을 보존한다.
- 데이터 준비: SOHAS 고정 `48860b9`, seed 20261004로 source split×knife role×normalized bbox area 구간에서 100장(76 knife positive/24 negative-unverified; train48/test52, 30,987,546 bytes)을 확보했다. 기존 665개 고유 hash와 SHA-256 중복 0. image/XML Git blob·SHA-256·원 경로·split·filename group proxy·selection/audit hash를 새 pack에 보존한다. 원본 VOC 좌표·negative 진위·session/near duplicate·권리·학습 승인은 여전히 별도다.
- 사전 보존: PC13 app 생성 없이 DB read-only integrity/count·SQLite backup API snapshot을 `data/review/team-server/backups/before-expansion-preparation-20261004/`에 보관했다. 당시 완료 판정은 307/665이고 SOHAS는98, 기존 SOHAS history157이다. 실제 판정/메모/이름/DB/raw는 Git에 넣지 않는다.
- 검증: 개발 PC Python3.11에서 전체106 tests·compileall·JS 문법 통과. 기존 판정/history/미완료 배정·기존 cookie·draft hash, 추가형 migration·재정렬/제거/hash duplicate 거부, old/new ID·권한·stale version·전 배치 backup을 fixture에서 확인했다. 합성 확대 fixture의 Chrome/Android412px·WebKit/iPhone390px에서 추가 ID 자동 배정/저장·새로고침·재접속·문제 메모 draft 복원 성공, overflow0·버튼46px. ignored `data/review/expansion-qa-20261004/`에 증거를 둔다. production에 QA 판정은 쓰지 않았다.
- 발견·수정: `git sparse-checkout add`의 지원되지 않는 `--no-cone`를 제거하고 기존 non-cone 설정을 확인하도록 했다. lean CSV에 `image_present`가 없을 때 renderer 오류를 재현해 출력 열을 명시적으로 추가하고 회귀검증했다. 미완성 pack은 공개하지 않고 새 완성 경로로 재실행해 보존했다.
- 상태·다음: 구현/표본 준비·PC browser 검증 완료, 실제 PC13 migration/외부 HTTPS 배포는 후속 기록으로 확인한다. 새 준비량·웹 배포·사람 판정·학습 승인을 혼동하지 않는다. 코드·문서 commit은 본 항목을 포함한 Git 이력으로 추적한다.
- 배포 후속: 구현 `88067d3`를 PC13에 반영했고 전체106 tests·clone DB preflight가 통과했다. 약3초의 서비스 정지 구간에서 `before-expansion-deploy-20261004/` consistent backup 후 config를 연결했다. 기존 모든 DB의 reviews/history/metadata와 team users/assignments의 row count·SHA-256이 정확히 일치했고 registry8행만 추가됐다. 새 batch 판정/history는0이다. 외부 HTTPS의 Chrome/Android·WebKit/iPhone native form 접속과 기존0/새100 ID 이미지 표시, 200장·두 질문·overflow0을 읽기 전용으로 확인했다. production QA 판정/배정은0건. 실제 휴대폰 설치·재부팅은 여전히 미검증이다.
- 집계 보완: 외부 화면 점검에서 SOHAS의 옛 상세 정상 판정2건이 portal/status에서는 held로 집계되고 UI에서는 정상으로 해석되는 차이를 확인했다. 기존 payload/version/history를 변경하지 않고 UI와 같은 legacy/v2 verdict 해석을 재사용해 집계를 맞췄다. 양성·음성 상세 정상 및 v2 unclear의 회귀 test를 추가한다. 이 보완 뒤 실제 실행 결과·배포 commit은 후속 기록으로 확인한다.
- 최종 확인: `f046520` 집계 보완까지 PC13에 배포하고 개발 PC/PC13 전체107 tests 통과. 최종 snapshot은 765장·307판정·32재확인(SOHAS200/98/14), SOHAS 신규100장 판정0이다. 공개 HTTPS 두 모바일 browser의 정상 form 로그인·기존/추가 이미지·동일 질문·가로 overflow0을 다시 확인했다. production QA의 판정·배정0건이며 최종 원시 상태는 PC13 ignored `final-status.json`, browser evidence는 로컬 ignored `public-result.json`에 있다. code/config/raw/DB 경계를 유지하고 docs만 후속 commit/push한다. 이후 후보의 class-map·권리·중복/sequence gate에 따라 추가 배치를 준비하되 검수 확대가 R1/H1 학습 승인을 대신하지 않는다.

## 2026-10-04 - 사이트 담당 채팅용 검수 확대 인계

- 사용자 요청: 사이트 이미지/판정 DB 확대는 별도 검수 사이트 채팅에 맡기고 PC13에 실행 가능한 인계 메모를 남긴다.
- 변경: [인계 메모](handoffs/2026-10-04-team-review-expansion.md)에 후보별 확대 순서, 기존 공통 두 질문, pack fingerprint/ID 계약, SQLite 일관 백업·추가형 migration·판정/배정/history 보존, bounded sampling, fixture/외부 HTTPS 검증과 완료 보고를 정리했다. 기존 helper와 최신 source 전략을 참조하며 별도 코드/데이터 형식을 만들지 않았다.
- 검증·범위: 문서 경로·내용·diff를 확인하고 메모를 commit/push 후 PC13 checkout에 반영한다. 이 채팅은 사이트/DB/이미지/서비스를 직접 변경하거나 학습을 실행하지 않는다. 인계 메모 저장과 실제 확대 배포를 구분한다. Git commit은 이 항목을 포함한 이력으로 추적한다.

## 2026-10-04 - 후보 전체 검수와 데이터 확대 작업 추가

- 목적·요청: 사용자가 좋은 자료를 넓게 활용하기 위해 데이터 검수 작업 추가와 후보 전부의 사용 가능성을 질문했다. 검수 pool은 넓히되 무조건 train 병합하지 않고 학습·합성·독립 평가 역할과 기존 승인 gate를 유지하도록 범위를 정리했다.
- 변경: 기존 `dataset-source-strategy.md`에 7개 준비 후보 첫 표본 합계 665장·ACF 대기, source별 추가 검수, 약 100장 단위 확대 제안, 기존 DB/배정/판정 보존과 중복 재배정 방지를 기록했다. `pre-orin-work-plan.md`에 작업을 추가했다. 사용 가능한 고유 실사 보강분을 합친 M1은 후속 `PROPOSAL`이며 R1/H1 첫 승인 학습을 기다리게 하지 않는다. Multi-source runner/승인은 미구현이다.
- 근거: 기존 표본 운영 문서와 SOHAS–DaSCI 1,985장 exact-duplicate audit를 확인했다. 공식 DaSCI 저장소와 Simuletic 카드를 2026-10-04 재확인했으며 공개자료와 학습 승인, real/synthetic을 구분한다. source 수나 단순 image 수만으로 실제 성능 개선을 주장하지 않는다.
- 검증·한계: 문서 변경만 수행하며 관련 경로/내용·diff를 확인한다. 새 image 확보·사이트/DB/서비스 변경·다운로드·학습은 실행하지 않았다. 실제 human review 수와 추가 batch 생성은 PC13 운영 상태를 확인한 후 진행한다. 이 변경의 commit은 본 항목을 포함한 Git history로 추적한다.

## 2026-10-04 - 사건 평가기·통제 촬영·R1/H1 학습 실행 준비

- 목적·이유: 사용자가 지정한 순서로 ①수동 사건 GT에 대한 B0~B3 평가 ②촬영/주석/세션 분리 ③데이터 승인 전 PC13 학습 실행 준비를 진행했다. 중단 뒤 dirty 변경·최근 commit을 확인하고 이어서 검증했다. 데이터 검수 사이트와 실제 full training은 이 작업의 구현 범위가 아니다.
- 선택: 기존 replay/metadata·training runner·manifest/label parser를 재사용하고 stdlib evaluator와 얇은 paired-preparation CLI를 추가했다(`search-first`). 신규 dependency는 없다. 동일 epoch만으로 다른 크기 dataset의 학습량을 통제할 수 없어, R1/H1 train draw 수를 맞추는 H1 positive oversampling을 development 제안으로 구현했다.
- 변경 파일: `evaluation.py`, `evaluate_cli.py`, replay module entry point·pyproject CLI, training/paired preparation, evaluation/training configs, fixture/tests, 촬영·GT·binding templates, controlled-experiment guide, 가상 report 및 관련 README/architecture/계획/verification. metadata+snapshot/GPIO runtime 범위는 변경하지 않았다.
- 결과: 일대일 event TP/FP/FN·중복/배경 FP·영상시간 분모·signed 판단 지연·ignore·partition micro 지표와 raw matching/hash를 기록한다. N5는 실제 positive가 유지되는 dropout robustness로 바로잡았다. frame0-based inclusive annotation과 half-open 시간, session/파생 group 분리, pilot→tuning→freeze→final-test를 정리했다.
- 학습 준비: R1에는 양성+검증된 음성, H1에는 같은 고유 양성만 넣고 common val/test·같은 planned draw/update schedule을 기록한다. 승인 gate·config/manifest/list/checkpoint/image/label bytes 검사에 실패하면 모델 생성 전에 중단한다. 결과 비교는 common tuning validation이지 detector 자동 선정이나 final-test 평가가 아니다. 권리·음성 부재·near duplicate·좌표·split을 코드가 대신 승인하지 않는다.
- 환경·명령·검증: 개발 PC `.venv-ml` Python 3.11.9, `PYTHONPATH=src`, `unittest discover -s tests -q` 101 tests 통과. 평가기 8 tests, training/pair 9 tests 포함. 실제 module replay→evaluation CLI 성공; 가상 TP/FP/FN B0=1/1/1, B1~B3=2/0/0. raw: ignored `runs/event-evaluation-synthetic-v1/`; [요약](../reports/evaluation/event-evaluator-synthetic-2026-10-04/report.md). Ultralytics 8.4.152 YOLODataset의 생성 이미지 목록 확인에서 R1/H1 각 6 draws, 고유 5/2, backgrounds 3/0으로 반복 길이 보존을 확인했다. temp fixture는 정리됐고 원본 데이터는 수정하지 않았다.
- 한계·다음 작업: 위 결과는 배관/산식 검증이다. 실제 거리·matching tolerance·반복 횟수는 첫 pilot 후 확정하고 승인된 SOHAS materialized export가 준비돼야 full training을 시작한다. Orin camera/GPIO·실시간 지연·실제 detector 품질은 미검증이다. 구현 commit은 이 항목을 포함한 Git history로 추적하고 PC13 readiness 증거는 후속 검증에 기록한다.
- PC13 후속 검증: 구현 commit `9833a72`를 clean worktree에 fast-forward하고 Python 3.12.4에서 전체 101 tests·compileall을 통과했다. 기존 격리 환경에 editable package/신규 `etr-evaluate` entry point만 갱신했고 `pip check` 정상, 실제 replay→평가 CLI도 로컬과 같은 가상 결과를 냈다. CUDA RTX 3060와 로컬 `yolo26n.pt`는 있으나 `data/processed/sohas-approved-v1/materialized-manifest.jsonl` 부재로 readiness는 예상 exit 2 / `blocked`, `training_started=false`였다. 원시 readiness는 PC13 ignored `runs/sohas-pair-readiness-20261004/readiness.json`, 가상 평가는 `runs/event-evaluation-synthetic-v1/`에 보존했다. plan SHA-256 `d2a67910fae3d58492e452cf9b380069d5e5b274d88cda2e7375f26857189b25`. 실제 검수 DB/서비스는 재시작하거나 수정하지 않았다. source 검수와 approved export가 다음 gate다.

## 2026-10-04 - 공개 이름 선택과 모바일 홈 화면 검수

- 사용자 결정: 개인 코드 대신 공개 링크에서 본인 이름을 드롭다운으로 선택한다. 이름은 self-declared identity이며 본인 인증의 증거가 아니다. 기존 계정·배정·판정 DB를 보존하고 관리자 기능은 별도 코드 접속으로 유지한다. 이전 개인 코드 사용 안내는 이 기록으로 `SUPERSEDED`다.
- 작업 카드·범위: 기존 Flask/Waitress·두 질문·SQLite를 재사용해 이름 선택, 30일 검수 session, 관리자 8시간 session, 모바일 큰 버튼·메모 조건 표시, manifest/192·512 icon/Apple icon, 설치 안내와 최근 후보 이어하기를 구현한다. 완료 기준은 실제 native form·저장·재접속·임시 입력 복원, install metadata, PC13 HTTPS 접속 확인이다. 이는 데이터 준비 도구이며 Jetson runtime MVP 범위는 변경하지 않는다.
- 변경 파일: `team_review.py`, 공통 웹 UI·install assets, local review asset routing, configure/check helpers, team tests, README·architecture·팀 배포 사용법·verification. 신규 dependency는 runtime에 추가하지 않았다. 브라우저 QA는 기존 bundled Playwright와 격리 WebKit을 사용하고 결과는 ignored `data/review/mobile-qa-20261004/`에 보관한다.
- 발견·수정: 기존 `Referrer-Policy: no-referrer`는 Chrome native form POST에 `Origin: null`을 만들어 server의 Origin guard가 정상 접속을 403으로 막았다. 실제 browser 재현 뒤 `same-origin`으로 수정해 외부 referrer는 보내지 않으면서 내부 form 접속을 허용했다.
- 개발 검증: 관련 21 tests, JS 문법·compileall·diff 확인 통과. 합성 fixture의 Pixel 7/Chrome 412px와 iPhone 13/WebKit 390px에서 이름 선택→자동 배정→두 질문 저장→다음→재접속·recent candidate·문제 메모 draft 복원 모두 통과했다. 가로 overflow 0, 질문 버튼 46px. 지속형 Chrome profile의 manifest/설치 가능성 오류 0. 실제 source에 새 사람 판정은 쓰지 않았다.
- 배포·검증: 구현 commit `26af97f`를 PC13에 반영하고 전체 88 tests 통과. SQLite consistent backup 후 `reviewer_login=name` 전환·시작 작업 재실행. 외부 HTTPS native form의 이름 선택 5/5·7개 준비 후보·Chrome/Android와 WebKit/iPhone 실제 화면/이미지·manifest 및 설치 가능성 오류 0을 확인했다. 전후 SOHAS 기존 판정 6건 및 나머지 pack 0건을 보존했고 실제 데이터 판정은 추가하지 않았다. 본인의 미검수 배정 1건은 재접속 테스트에 사용했다. 결과는 ignored `public-result.json`에 있고 구현 및 후속 배포 기록 커밋으로 보존한다.
- 한계·다음 작업: 실제 iOS/Android 홈 화면 설치·아이콘 실행과 reboot recovery는 물리 장비에서 확인한다. 이름 선택은 본인 인증이 아니므로 검수 provenance에 그 한계를 유지한다.

## 2026-10-04 - 개인 계정 발급과 후보 공통 검수 흐름

- 목적·이유: 다섯 팀원이 데이터셋마다 다른 양식을 익히거나 CSV를 주고받지 않도록, 기존 `simple-v2` 두 질문·자동 배정·자동 저장을 공통 사용한다. 화면은 기존 구현을 재사용하고 source별 특수 양식은 추가하지 않았다.
- 범위·변경: `app.js`의 미저장 임시 입력 키를 로그인한 검수자별로 분리하고, 화면의 SOHAS/XML 전용 문구를 후보 공통 문구로 바꿨다. 일회성 개인 계정 발급 helper와 재발급 방지 테스트를 추가했다. 본인 이름은 로그인으로 자동 입력된다. 원본·기존 판정·연구용 source 승인 규칙은 바꾸지 않았다.
- 운영 결과: PC13에 개인 계정 5개를 발급했다. 코드 파일은 PC13과 관리자 노트북의 ignored `secrets/`에만 두고 커밋하지 않았다. HTTPS 공개 주소에서 5/5 개인 로그인 및 7개 후보의 동일 `simple-v2` 계약을 읽기 전용으로 확인했다. 새 인간 판정은 0건이다.
- 검증: 개발 PC `unittest discover -s tests -q` 84 tests, `node --check` 및 `compileall` 통과; PC13 관련 5 tests 통과; 서비스 재시작 후 외부 인증·계정/후보 계약 확인. `git diff --check` 통과. 변경 파일: 공통 검수 UI, 발급 helper/test, README·팀 배포 사용법·검증 문서. 커밋 `9340e09`, `9e86f50` 및 후속 README 커밋.
- 한계·다음 작업: 실제 팀원이 두 질문을 저장하고 재접속 시 판정이 유지되는지, 재부팅 후 서비스 복구는 아직 미검증이다. 첫 사용자 검수 후 저장·재개를 확인하고, 표본 판단은 source 권리·좌표·중복 gate와 분리한다.

## 2026-10-04 - 팀 검수 사이트의 외부 HTTPS 활성화

- 사용자 tailnet 관리자 승인을 받은 뒤 PC13에서 `tailscale funnel --bg --yes 8770`를 적용했다. Funnel status는 `https://yu-desktop-97msr1i.tail37c267.ts.net/`에서 loopback `127.0.0.1:8770`으로 proxy 중임을 보였다.
- 노트북의 실제 외부 HTTPS 요청에서 로그인 화면 200, 미인증 후보 목록·이미지 401을 확인했다. ignored 파일의 관리자 코드로 HTTPS 세션 로그인 후 7개 준비 후보 목록과 Dangerous 첫 이미지 200/79,893 bytes를 확인했다. 코드는 명령 출력·Git에 기록하지 않았고 실제 사람 판정은 쓰지 않았다.
- 다음 검증은 개인 코드 발급 후 팀원 본인의 첫 판정을 저장하고 새로고침·재접속 시 같은 값을 보는 것이다. 재부팅 후 앱/Funnel 자동 복구는 아직 미검증이다. 데이터셋 표본의 사람 검수와 원본 class/권리·학습 승인은 별도 gate다.

## 2026-10-04 - PC13 중앙 검수 배포·후보 표본 확장

- 사용자 운영 결정: PC13을 상시 켜고 대용량 원본·검수 pack·DB를 해당 PC에 둔다. 팀원은 브라우저와 개인 코드만 사용하고 CSV 수동 회수·각 PC 설치는 요구하지 않는다. GitHub에는 코드/절차만 동기화한다.
- 2026-10-03 구현된 인증 서비스를 PC13에 배치하고 기존 SOHAS SQLite 백업의 인간 판정 6건·수정 이력 40건을 pack hash 검증 뒤 이전했다. 기존 노트북 DB는 보존하지만 중앙 시작 이후 병행 저장하면 분기하므로 사용하지 않는다. 관리자 bootstrap 파일은 ignored secrets에만 두고 실제 판정은 개인 계정으로만 수행하게 바꿨다.
- PC13 `ETR-Team-Review` 부팅 작업이 실행 중이고 앱은 `127.0.0.1:8770`만 수신한다. `tailscale set --unattended=true`를 적용했다. 루프백 `/login` 200, 인증 없는 catalog·이미지 401, backup integrity를 확인했다. 실제 재부팅과 외부 브라우저 저장은 아직 검증하지 않았다.
- SOHAS 100, DaSCI byte-unique 93, Simuletic 114, US Mock Attack 100, Open Images validation 30, Legacy 128, Dangerous Items 100을 PC13 팀 catalog에 준비했다. ACF 원 source 404는 임의 mirror로 대체하지 않는다. Dangerous Items 공식 Zenodo API CC BY 4.0 확인; ZIP에 YAML class map이 없어 3장/클래스 visual probe 결과 `raw ID 1 = knife`를 **표본 화면의 작업 가설**로만 사용한다. 이 가설로 학습·성능 주장하지 않는다. 전체 1.4 GB 직접 다운로드가 지연되어 고정 크기 HTTP Range 45,209,628 bytes로 120 label을 조사하고 100장·임시 knife 19개 표본을 준비했다. 전체 archive checksum은 아직 검증하지 못했다.
- 검증: 신규 팀 service 4 tests 및 개발 PC 전체 83 tests 통과. 실제 PC13 config의 관리자 로그인·7개 pack 목록·각 첫 이미지 200을 읽기 전용 smoke로 확인해 SOHAS 6판정이 유지됐다. 검수 DB/이미지·원본은 ignored, source 채택·라벨 검증·모델 학습은 진행하지 않았다. Tailscale Funnel은 tailnet의 관리자 enable gate를 반환했고 현재 `No serve config`이므로 외부 URL은 아직 `NOT VERIFIED`다. 승인 후 HTTPS 로그인/이미지 차단/팀원 저장·재개를 따로 확인해야 한다. 상세 운영·source별 범위는 [PC13 팀 웹 검수](team-review-deployment.md)에 둔다.

## 2026-10-03 - PC13 중앙 팀 검수 구현 (배포 검증 전)

- 사용자 결정: PC13 상시 운용·팀 웹서비스 운영 가능, 대용량 자료는 PC13에 두고 브라우저만으로 후보 검수한다. CSV 회수·각 PC Python 설치 방식은 채택하지 않는다.
- 작업 카드: 기존 두 질문 UI·SQLite/history를 재사용해 다중 후보, 개인 코드 로그인, 관리자 초대/해제, 미검수 자동 배정, 동시 수정 차단, 백업을 구현한다. 완료 기준은 인증 없는 이미지 차단·권한/CSRF/Host·저장/재개·원격 HTTPS 확인과 기존 인간 판정 보존이다. 학습·source 자동 승인·전체 PC 공유는 제외한다.
- search-first 선택: stdlib 개발 HTTP 서버의 직접 공개 대신 Windows 지원 Flask 3.1.3 + Waitress 3.0.2를 별도 review-server requirements로 채택한다. Core의 무의존성과 로컬 검수 서버는 유지한다. 공식 Flask deployment/waitress 문서를 확인했다.
- 구현: signed Secure/HttpOnly/SameSite cookie, 8시간 세션, 개인 고엔트로피 접속 코드의 scrypt hash, 접근 해제 시 세션 무효화, origin·CSRF·명시적 Host 경계, 계정 기반 reviewer, 배정 중복 방지와 review version 유지. 관리자만 계정을 발급·해제한다. 코드·키·원본·개인 판정은 Git 제외다.
- Source preparation: SOHAS 100 기존 pack, DaSCI byte-unique 93(98 knife), Simuletic 114(99 knife), US camera/positive strata 100(47 knife), Open Images validation 첫 표본 30(40 knife), 기존 legacy 표본 128(147 knife) 준비. 표본은 source 채택이나 전체 구성비의 증거가 아니다. ACF upstream 404 유지. Dangerous Items official Zenodo record는 현재 CC BY 4.0이며 과거 권리 보류를 갱신하지만 다운로드·실제 pack 검증은 진행 중이다.
- PC13의 US 원본 archive 1,485,019,798 bytes와 SHA-256 `558f5baa109abe8fba57b61fa177c75358001f5499f5e78178f4bf7dc9f55e8c`를 확인했다. 원본은 PC13에만 두며 full dataset import/training은 하지 않았다. Simuletic HF snapshot `c71bb6186c9849edf2216909febffb979b89b838`, US HF `07ced721cd90973f66806c0b3ee01e80c439ba90`을 기록한다.
- 검증: Windows Python 3.11 전체 83 tests 통과, compileall/JS check. 신규 테스트에서 Flask trusted Host의 400 거부와 SQLite context manager가 close하지 않는 Windows file-lock을 재현했고 fail-closed assertion·explicit closing으로 수정했다. local pip console 인코딩 경고는 설치 후 import/test로 확인했다.
- 기존 SOHAS human DB 관찰: 6행/history 40건의 consistent migration snapshot 작성, 원본과 실행 중 로컬 탭은 그대로 보존. 원격 import·서비스 자동 실행·Funnel 공개·브라우저 통합은 아직 이 항목 시점 NOT VERIFIED이며 후속 기록으로 갱신한다. 관리자 bootstrap 코드 파일은 ignored secrets에만 생성한다.

## 2026-10-03 - 진행 중 저장 확인·검수 질문 최소화·팀 배포 점검

- 작업 카드: 사용자 요청에 따라 실제 저장을 비파괴적으로 확인하고 중복 UI 항목을 줄인다. 완료 기준은 DB 무결성·백업, 기존 판정 보존, 2-question 저장·재개 테스트와 문서/Git 반영이다. 공개 배포·공유 권한 변경·훈련·사용자 대리 판정은 제외했다. 진행 중 탭/저장을 끊지 않는 것이 주요 위험 통제다.
- 관찰: 실제 API/DB는 100장 중 5행, 수정 history 39건, `quick_check=ok`. read-only DB 연결에서 SQLite backup API로 `backup-before-simple-ui.sqlite3`에 일관된 snapshot을 남겼다. 초기 latest-time 조회 shell quoting 오류는 데이터 변경 없이 실패했고 JSON timestamp read로 재실행했다. 이는 관찰 시점 수치이며 완료된 전체 검수가 아니다. 사용자 이름·판정 내용은 Git/로그에 옮기지 않았다.
- search-first로 기존 CSV/SQLite/version/history를 재사용했다. 기본 입력은 CCTV형/그 외/모르겠음과 라벨 정상/문제 있음/모르겠음 두 질문이다. 품질·박스 완전성·별도 처리 질문과 중복 빠른 버튼·선택적 사람/크기/가림을 제거했다. Normal의 의미에 모든 knife box와 음성 실제 부재 확인을 명시했다. 문제는 메모 후 재확인 후보이고 자동 제외하지 않는다.
- `simple-v2` schema·coarse annotation verdict를 추가해 명시적 통합 답을 기존 export 열에 매핑한다. positive 문제를 누락으로 단정하지 않고 완전성 unclear로 둔다. 상세 기존 enum·판정은 일괄 변환하지 않으며 수정 전 payload는 history에 보존한다. 기존 client 저장 계약도 유지한다. 재검수 아닌 사람 이름 자동 채움/AI 승인 없음.
- 사용 중 서버/탭을 재시작하지 않았다. 새 8768 서버가 동일 DB를 사용하며 기존 8765는 유지한다. launcher 기본을 8768로 변경하고 오래된 서버는 새 UI에서 오류 안내로 차단한다. 기존 창에서 저장 후 새 주소를 사용한다. 두 주소의 browser-local 미완성 draft는 서로 자동 이전되지 않는다.
- verification-loop: 새 3 regression tests 포함 focused 7 tests 및 전체 **79 tests 통과**(1.940 s), compileall·JS 문법 정상. 첫 신규 테스트 삽입 위치 때문에 fixture `original`의 scope 오류가 나와 테스트 위치를 수정해 재검증했다. Computer Use로 별도 QA DB에만 테스트 판정을 입력해 화면 질문 2개, 저장/다음/새로고침 재개를 확인했다. 실제 검수 DB에 QA 값을 쓰지 않았다.
- 배포 판단: 현재 listener 127.0.0.1이며 login/roles/담당 배정·remote HTTPS/backup은 없다. 로컬 pack + Python 배포와 비공개 인증 서비스 경로를 검수 기준에 기록했다. CSRF를 인증으로 오인하거나 정적 호스팅만으로 DB 저장을 제공한다고 주장하지 않는다. 팀원 접속·package 배포·인터넷 공개·Drive 업로드는 미수행이다.
- 변경: review server, JS/HTML, Windows launcher, tests, README·검수 기준·verification·이 로그. raw/DB/backup은 ignored이고 recipe/MVP 불변이다. 다음은 사용자가 간단 UI에서 계속 검수하고 팀 배포 방식/접근 범위를 선택하는 것이다. Git: 이 기록을 포함하는 commit.

## 2026-10-03 - 버튼 기반 로컬 SOHAS 검수 화면

- 요청/작업 카드: CSV 대신 사이트처럼 클릭하며 표본을 확인하도록 원본·raw knife 박스·판정 버튼·이동·자동 저장·CSV export를 구현한다. 완료 기준은 실제 100장 로딩·별도 테스트 DB의 저장/재개와 원본 보존·전체 tests·문서/Git 반영이다. 데이터 채택·인간 대리 판정·실제 학습·공개 배포/Drive 업로드는 범위 밖이다.
- search-first로 기존 review CSV/evidence/VOC/Pillow helper를 재사용하고 원본 보존 output만 얇게 확장했다. 서버/저장은 Python stdlib `http.server`/SQLite, 화면은 HTML/CSS/JS이며 새 framework/dependency를 추가하지 않았다. Windows built-in launcher는 재사용/재개 시 반복 명령을 없애려는 사용자 UI 요구를 지원한다.
- 변경: `review_web.py`, 정적 자산 3개, `etr-review` 및 package-data 설정, source image helper, Windows launcher, store/API tests; README·검수 기준·handoff·verification·이 로그. `domain`/품질/누락/처리 후보/검수자 필수, 음성의 실제 칼 부재 확인, 제외/보류 이유를 검증하며 권리/좌표 승인 입력은 제공하지 않는다.
- 원격에서 기존 sample의 새 `sohas-click-review-20261003/` pack을 생성한 뒤 노트북으로 SCP 복사했다. 원본 100장 31,100,785 bytes와 knife 객체 103개·7 sheets를 보존했다. SQLite와 image/CSV는 ignored로 Git에 올리지 않는다. 기존 pack은 보존한다.
- verification-loop: focused store/API 4 tests 후 전체 **76 tests 통과**(1.873 s 관찰), `compileall`·Node JS 문법 확인. 초기 SQLite connection context가 연결을 닫지 않아 Windows fixture cleanup이 실패한 것을 재현·수정하고 재검증했다. 저장은 transaction+version으로 오래된 탭 덮어쓰기를 차단하고 source hash가 바뀌면 DB 재사용을 거부한다. CSV formula 입력은 export에서만 neutralize한다.
- 실제 브라우저에서는 **별도 QA DB**에 `UI_TEST_NOT_HUMAN` 1행을 저장해 다음 이동·새로고침 후 동일 값 재개·확대·박스 숨기기·음성 필터를 확인했다. browser warn/error 0개. 이는 UI 기능 확인이며 인간 검수 완료가 아니다. 실제 human DB는 0행임을 확인했다.
- 현재 setuptools의 한글 경로 editable wheel `.pth` 생성(cp1252)과 초기 한국어 stdout 오류를 재현했다. startup 메시지를 ASCII로 바꾸고 launcher는 `PYTHONPATH=src`/UTF-8 모듈 실행으로 설치 없이 사용한다. editable install 성공을 주장하지 않는다. 일반 wheel build 성공·정적 자산 포함을 확인했다. Windows launcher 기존 서버 재사용 및 새 포트 시작도 통과했다.
- 한계/영향: loopback 단일 PC 검수 도구이며 공유 계정/원격 다중 사용자/자동 Drive 백업/annotation 수정/학습은 없다. 미완성 입력은 browser-local draft다. Legacy L0와 recipe 승인 상태는 불변. 다음은 사용자가 이 UI에서 100장 검수 → 표본 오류/누락/negative·좌표·촬영 group 확인 → source/split/recipe 결정이다. Git: 이 기록을 포함하는 commit.

## 2026-10-03 - 비상용 내부 연구 범위의 SOHAS 이미지 검수 준비

- 사용자 clarification: 상용 목적이 아닌 수업 연구이며 작업 진행을 요청했고 `C:\Class6` 보존도 확인했다. 메일 회신을 모든 데이터 확보의 필수 조건으로 둔 이전 설명을 수정한다. 공식 연구진의 public research 설명 및 CC BY/CC BY-SA의 복제·변형 허용을 확인해 제한된 로컬 sample 검수는 진행하고 외부 공개 조건은 분리한다. license 차이 해결·학습 채택을 주장하지 않는다.
- 작업 카드: 기존 100개 표본의 원본 확보·decode/hash/dimension 확인·raw knife overlay·빈 human CSV를 완료 기준으로 둔다. 전체 다운로드·학습·외부 공유·AI 판정의 human 대체는 제외하며 10 GB 한도를 유지한다.
- search-first로 기존 SOHAS pinned inventory/blob 검사/VOC parser·Pillow를 재사용했다. 기존 legacy review-pack은 knife annotation 없는 negative 및 미확정 VOC 좌표를 입력으로 못 받으므로 작은 source-specific `tools/sohas_review_images.py`를 추가했다. 학습 label/manifest export나 downloader를 새로 만들지 않았다.
- remote `git sparse-checkout add --stdin`에 기존 sample의 image path 100개만 전달해 원본을 확보했다. helper의 실제 실행 결과 100개 decode·blob·dimension 확인 성공, 총 31,100,785 bytes, knife 객체 103개, 7 contact sheets. 첫 생성 CSV의 image_present는 이전 audit 시점 값이라 최종 helper에서 현재 True로 갱신하고 `sohas-100-20261003-final/`로 별도 재생성했다. reviewer는 빈칸, training 승인 false다.
- 노트북에는 작은 pack만 SCP로 복사했다. 첫 sheet를 육안 개발 확인해 caption/overlay가 표시되는 것을 확인했다. 제품/클로즈업·워터마크·반복 촬영 장면도 보여 무검수 전체 승인하지 않는다. 사람의 100장 판정 또는 coordinate convention 확정으로 기록하지 않는다.
- verification-loop: 신규 fixture 2개 통과, 전체 72 tests 통과(0.822 s), helper actual integration 성공. 초기 단일 테스트 module 경로 호출은 tests가 package가 아니어서 실패했고 `unittest discover -s tests -p test_sohas_review_images.py`로 올바르게 재실행했다. initial SCP cwd 누락은 경로를 지정해 재실행했으며 원본 삭제 없음.
- 변경: helper/test, source strategy/evaluation criteria/handoff/verification/이 로그. 코드·문서만 Git에 넣고 raw/pack은 ignored. source/model recipe는 미승인이고 메일·Drive 업로드·실제 학습은 수행하지 않았다. 다음은 인간 표본 검수·좌표 근거·negative 누락·near duplicate/session split이다. Git: 이 기록을 포함하는 commit.

## 2026-10-03 - 외장 저장장치 없는 데이터 준비·권리 확인 초안

- 사용자 요청: SOHAS 준비를 진행하고 필요한 정보를 요청하되 GPU PC/노트북에 외장 저장장치를 상시 연결하지 않는 저장 방식을 정한다.
- 범위/완료 기준: 내장 디스크 여유·기존 ignore·공식 pinned license/contact를 확인하고 기존 전략/report에 작업 위치·백업 경계·권리 확인 초안을 추가한다. 신규 source 채택·메일 발송·전체 image 다운로드·학습은 제외했다.
- Windows `Get-PSDrive C` 관찰: 학습 PC 144.5 GiB, 노트북 16.4 GiB 여유. GPU PC의 기존 `data/`와 `runs/`를 사용하고 노트북은 코드·소형 검수 pack 위주로 둔다. Drive 실제 연결/업로드는 미수행이며 로컬 dataset 10 GB 한도와 권리 gate를 유지한다.
- 고정 upstream의 README CC BY-SA 4.0과 License.md CC BY 4.0 및 공개 기관 연락처를 재확인했다. 사용 조건·제한 공유 백업·weight 공개·VOC 좌표·group metadata를 묻는 영문 메일 초안을 기존 SOHAS report에 작성했다. 외부 연락을 보내지 않았다.
- package 크기 측정을 위해 partial clone에서 `git ls-tree -r -l`을 시도했으나 lazy blob fetch/auto maintenance가 유발되어 해당 크기 조회 프로세스만 중단했다. 파일 삭제·원본 변경 없이 보존했으며 체크아웃된 이미지 0개를 확인했다. Git cache 일부 반입은 있었으므로 metadata만 읽었다고 주장하지 않는다. 이 조회의 0 count/size 출력은 유효한 package 용량이 아니며 사용하지 않는다. 이후 크기 조회는 공식 tree API의 size 등 blob fetch 없는 방식으로 수행한다.
- 변경: dataset-source-strategy, 기존 SOHAS report, 이 로그. verification-loop 기준 문서 diff/ignore를 확인하며 코드 변경이 없어 코드 테스트는 생략한다. recipe 승인 상태 불변.
- 필요한 사용자 정보: `C:\Class6`의 기간 중 보존/초기화 정책, 권리 확인 메일 발송 담당. 다음은 회신 근거 또는 명확한 공식 사용 조건 확보 후 이미지 검수다. Git: 이 기록을 포함하는 commit.

## 2026-10-03 - 남은 사용량으로 SSH 독립 GPU 실행 검증

상태: 단기 SSH 종료 후 CUDA 작업 지속 `VERIFIED`; 실제 데이터 학습·장시간 안정성 `PLANNED`.

- 목적/범위/완료 기준: 사용자가 남은 Plus 사용량을 효율적으로 배분해 작업하도록 요청했다. 긴 학습 전에 연결 종료 시 작업이 유지되는지 확인하는 범위로 한정했다. 기존 생성 데이터 helper를 재사용하고 exit code·summary·checkpoint 증거와 문서/Git 기록을 완료 기준으로 잡았다. source/recipe 승인 우회나 실제 full training은 제외했다.
- search-first로 기존 helper와 Windows built-in을 선택하고 verification-loop로 실제 시작 SSH 종료와 새 연결 확인을 수행했다. 새 의존성/helper/서비스/예약 작업은 설치하지 않았다.
- 기존 `Start-Process`+20초 지연 방식은 시작 SSH 종료 뒤 프로세스/summary/exit code가 남지 않았다. ignored `runs/pc13-detached-smoke-20261002/`는 실패 증거로 보존했다.
- CIM `Win32_Process.Create`로 hidden PowerShell을 생성(ReturnValue 0, PID 12068), 15초 지연 후 생성 CUDA/AMP helper 실행. 시작 SSH는 학습 전에 종료됐다. 이후 새 SSH에서 exit-code 0 및 summary passed를 읽었다. 생성 8 train/4 val·1 epoch·validation·best/last·reload GPU inference 통과, runner duration 5.875 s. 확인 명령 exit 1은 이미 종료된 launcher PID 조회 때문이며 학습 exit와 별개다.
- 원격 Windows/RTX 3060/torch 2.6.0+cu124 환경, 실행 소스 commit `1c176ae`. raw evidence는 `runs/pc13-cim-smoke-20261002/`; helper hash는 summary에 보존했다. 코드 변경 없이 handoff·verification·이 로그만 갱신했다.
- 한계/결정 영향: 재부팅/절전/로그아웃·장시간 학습·재시작·Drive 업로드·모델 품질은 미검증. R1/H1 승인과 image/rights/coordinate/group gate는 유지한다. 다음은 dataset 권리 및 표본 검수이고, 사용량을 소진하기 위한 새 기능은 추가하지 않는다. Git: 이 기록을 포함하는 commit.

## 2026-10-02 - 로컬 SSH 작업 재개와 Windows SOHAS byte-exact audit

상태: 로컬→학습 PC SSH·Windows label audit `VERIFIED`; 실제 이미지/권리/좌표/recipe 승인·full training `PLANNED`.

- 목적/범위/완료 기준: 사용자의 연결 복구 후 작업 재개 요청에 따라 Cloud 변경을 pull하고 기존 audit를 원격에서 재현한다. 기존 staging 보존, 테스트·실제 audit·검수 목록 생성·문서 기록을 완료 기준으로 잡았다. 위험은 Windows checkout 변환과 미승인 source 반입이며 학습 gate를 유지했다.
- `search-first`와 `verification-loop`를 적용해 기존 VOC CLI를 재사용했다. source/helper/dependency 추가 없이 clone-local 설정만 사용했다. 변경 문서는 이 로그·verification·training-cuda-handoff·SOHAS metadata report다.
- Windows/Python 3.12.4 원격 repo를 `0b51dd4`까지 fast-forward했다. 전체 70 tests는 원격 0.554 s, 로컬 1.212 s에 통과했다.
- 첫 실제 audit는 XML 4,686개 blob 불일치로 exit 1. upstream clone의 `core.autocrlf=true`를 확인했고, byte 검증을 완화하지 않았다. 기존 source/output은 보존하고 새 `data/source-audit/sohas-upstream-byte-exact/`를 `git clone --config core.autocrlf=false --filter=blob:none --no-checkout`으로 준비했다. upstream `48860b9`, 같은 label/XML-only sparse checkout이며 전역 설정·이미지를 변경/다운로드하지 않았다.
- CLI 정상 출력 `data/source-audit/sohas-voc-pc13-byte-exact-20261002/`: exit 0, 구조 오류 0; metadata 5,859 / VOC knife 2,349 / YOLO knife 2,277 / mismatch 58 / orphan 83 / case-only warning 181. 100개 review sample·전체 queue를 생성했다.
- 한계/결정 영향: 이미지 0, 좌표 `unknown`, 사람 검수 pending, 학습 승인 false. R1/H1은 기존 PROPOSAL을 유지한다. Cloud 연결·SSH 종료 후 job 지속·Drive 업로드·실제 full training은 미검증이다.
- 다음: 사용 권리 근거 확인 → 승인된 이미지 표본/좌표 검수 → near duplicate/session grouping 및 공통 tuning/test → recipe 승인 후 CUDA 학습. Git: 이 기록을 포함하는 commit.

## 2026-10-02 - Cloud 장시간 작업 인계와 SOHAS VOC 승인 전 준비

상태: source-specific 변환·audit `IMPLEMENTED`, synthetic 좌표 계약·Cloud label dry-run `VERIFIED`; 실제 이미지/좌표/권리/recipe 승인·full training `PLANNED`; Cloud→학습 PC SSH `BLOCKED`.

### Goal / Why / Scope / Changed files

- 사용자의 로컬 채팅 인계를 받아 이 Cloud에서 bounded dataset 준비·검증을 수행한다. 준비된 YOLO label의 72개 knife 객체 누락 차이를 그대로 학습에 반영하지 않기 위해 VOC의 모든 knife 객체를 보존한다.
- 작업 카드: 목적은 source-specific 변환/audit 및 검수 대기 파일 준비; 범위는 raw read-only metadata/label과 pure Python; 완료 기준은 기존+오류경로 테스트, 실제 dry-run, 관련 문서 및 commit/push; 위험은 좌표 convention·negative 누락·권리·group 미확정이다. full training, 이미지 source 채택, Drive 업로드, 네트워크/방화벽 변경은 이번 작업 범위 밖이다.
- `rg`로 기존 dataset tooling을 검색해 `parse_yolo_label`, `ValidationIssue`, review `size_bucket`을 재사용했다. 이 Cloud에는 별도 search-first/verification-loop skill이 제공되지 않아 AGENTS의 절차를 직접 따랐다. XML·Git inventory·CSV 처리는 표준 라이브러리를 사용하며 추가 dependency는 없다.
- 변경: `src/edge_threat_response/dataset/sohas.py`, CLI, `tests/test_sohas_voc.py`; README, model-data-plan, dataset-source-strategy, verification, 기존 SOHAS metadata report, training-cuda-handoff, 이 로그. 원본·generated 출력·model/venv는 Git에 넣지 않는다.
- 사용자에게 명시적으로 위임된 코드 작업이며 onboarding의 설치 작업과 구분한다. 기존 clean checkout을 그대로 사용하고 새 worktree는 만들지 않았다.

### Environment / Commands / Result / Verification

- Linux x86_64 Cloud / Python 3.12.14, 기존 pure/review `.venv`. `work` branch에서 clean 상태를 확인하고 `git pull --ff-only origin main`으로 `0d9ce87`까지 반영했다. `/dev/nvidia*`와 `nvidia-smi`가 없으므로 CUDA GPU를 확인하지 못했으며 CPU full training을 실행하지 않았다.
- 환경 config read는 onboarding draft의 존재를 확인할 뿐 publication 상태를 제공하지 않았다. 현재 shell/코드 실행은 확인했지만 published 환경·새 task restoration·장시간 프로세스 수명을 확인했다고 주장하지 않는다. 설정 초안 저장은 publication이 아니다.
- 원격 SSH는 BatchMode/5초 timeout/1회 연결/StrictHostKeyChecking=yes로 안전하게 확인했다. 초기 system SSH include의 ownership/permission 오류 후, 파일을 수정하지 않고 관련 없는 systemd local-host 설정을 제외하는 `-F /dev/null`로 다시 확인했다. 사용자가 제공한 사설 PC 주소의 TCP/22가 `Connection refused`를 반환했으며 인증 전에 실패했다. raw key 추출·복사, Tailscale 설치, 방화벽/포트 개방 또는 로컬 노트북 우회 실행을 하지 않았다.
- 공식 upstream의 pinned partial/sparse clone은 ignored `data/source-audit/sohas-upstream/`에 59 MB이며 XML·YOLO label·README/license/YAML만 checkout했다. 이미지 0개, source status clean. Git regular-file executable mode도 포함하는 inventory로 image metadata 5,859개를 사용하고 source bytes의 blob/SHA-256을 확인했다.
- `.venv/bin/python -m unittest discover -s tests -q`: 기존 56 + 신규 14 = **70 passed**, 실패/skip 0. 신규 테스트는 모든 knife bbox와 raw map, 두 좌표 convention, unknown 보류, malformed/entity/filename/dimension/unknown-class/범위 오류, 부분-label 차단, input immutability, pinned inventory, orphan/negative 대기, CLI exit 및 표본 재현성을 확인한다.
- `.venv/bin/etr-dataset sohas-voc-audit --source-root data/source-audit/sohas-upstream --output-dir data/source-audit/sohas-voc-cloud-final`: exit 0, VOC knife 2,349 / YOLO 2,277, count mismatch 58 images, orphan XML 83, filename 대소문자 warning 181. 초기 엄격 filename 검사에서 나온 181 항목은 모두 대소문자만 다른 것을 확인한 뒤 unique pairing의 case-only warning으로 처리했다. 다른 identity 오류는 계속 보류한다.
- `voc-candidates.jsonl`에 `knife_108`의 2개/`knife_1162`의 3개 객체가 보존되고, 모든 행이 미승인·빈 reviewer·변환 lines 없음임을 assertion으로 확인했다. 전체 review queue 및 seed 20261002의 100개 층화 sample CSV를 생성하고 층별 n/N을 summary에 기록했다. 원시 출력은 ignored `data/source-audit/sohas-voc-cloud-final/`이다.
- 최종 코드로 `sohas-voc-cloud-repeat/`에 다시 실행해 exit 0과 기존 candidate JSONL·sample CSV의 byte-identical 재현성을 확인했다. 문서 로컬 링크·`git diff --check`를 확인하고 최종 status에서 의도한 code/test/docs만 변경됐음을 검토했다.
- 단위 테스트의 explicit-convention geometry는 synthetic 계약 증거다. SOHAS convention 자체는 미확정이며 기본 `unknown`으로 실제 training label·split·학습을 생성하지 않았다. 이미지 decode/시각적 bbox 완전성·negative 진위는 미수행이다.

### Decision impact / Next action / Git

- R1/H1 우선 제안과 gate를 유지한다. 다음은 권리·좌표 근거 확인, 승인된 이미지 검수, near duplicate/session grouping, 공통 tuning/final-test 및 명시적 batch/optimizer-step 예산 결정이다. 100개 sample은 전체 source 승인이 아니다.
- 원격 GPU 작업에는 Cloud에서 사설/Tailscale 대상까지의 지원되는 네트워크 경로와 PC SSH service/접근 정책이 필요하다. TCP 연결이 가능해진 뒤 기존 SSH 인증을 재확인한다. 기존 PC CUDA smoke 근거는 유효하지만 이 Cloud의 연결·background 지속성을 증명하지 않는다.
- Git: 이 기록을 포함하는 commit. 의도한 code/test/docs만 stage하며 non-force push 결과를 확인한다.

## 2026-10-02 - 3개 screening 제안 검토와 SOHAS 실제 라벨 대조

상태: upstream metadata·실제 label/XML object count `VERIFIED`; recipe 채택·변환·human review·학습 `PLANNED`/기존 `PROPOSAL` 유지.

- 목적: 사용자가 전달한 SOHAS/DaSCI/Combined 3연속 screening 제안을 현재 증거로 평가하고 안전한 준비 작업을 진행한다.
- `search-first`/`verification-loop`를 사용해 기존 metadata 보고서와 source 정책을 재사용했다. 새로운 모델·다운로더·학습 framework는 추가하지 않았다.
- GPT가 지정한 SOHAS YOLO 배포본의 image/label tree와 YAML을 확인했다. image 5,859장, label 5,859개, orphan label 0; DaSCI exact blob overlap 1,985장으로 기존 결과와 일치했다.
- 원격 PC의 ignored `data/source-audit/sohas-upstream/`에 고정 upstream partial/sparse clone으로 license/README/YAML·YOLO label·VOC XML만 확보했다. image checkout·Drive 공유·실제 학습은 수행하지 않았다.
- PowerShell로 5,859 label을 집계하고 같은 split/basename VOC와 비교했다. knife annotation positive 2,277 / no-knife candidate 3,582; YOLO knife objects 2,277 vs VOC 2,349, 58 images 불일치. label-only negative 진위·bbox 품질은 미검증이다. generated 집계 JSON은 원격 `data/source-audit/`에 있다.
- raw root의 image 확인은 파일 확장자 필터로 0개임을 확인했다. sparse-checkout add의 잘못된 `--no-cone` 옵션은 실패했고, 기존 non-cone 설정에서 옵션 없이 재실행해 XML을 확보했다. 원본 파일을 수정하지 않았다.
- [metadata 보고서](../reports/datasets/sohas-dasci-metadata-2026-10-02/report.md), source strategy와 verification에 결과·해석·한계를 추가했다. 코드 변경이 없어 코드 테스트는 생략하고 링크·diff를 검사한다.
- 판단: 짧은 screening과 공통 tuning/오류 분석은 타당하지만 세 source가 독립적이라는 가정과 YOLO label 즉시 사용은 채택하지 않는다. R1/H1 우선, 고유 DaSCI는 조건부 U1을 유지한다. 다음은 권리 확인·VOC 전체 bbox 변환·표본 검수·cross-source group split이며, 승인 전에 training을 시작하지 않는다.
- Git: 이 기록을 포함하는 commit.

## 2026-10-02 - 원격 RTX 3060 학습 환경 설정

상태: 원격 clone·격리 ML 환경 `IMPLEMENTED`; CUDA/AMP 학습 plumbing `VERIFIED`; 실제 dataset full training `PLANNED`.

### Goal / Why / Scope / Changed files

- 사용자가 제공한 SSH PC에서 비어 있는 `C:\Class6`를 확인하고 `edge-threat-response` clone과 `.venv-ml`을 생성했다. 전역 Anaconda·GPU driver·기존 파일은 변경하지 않았다.
- 기존 runner를 재사용하고 `tools/cuda_training_smoke.py`, `configs/training/requirements-pc13.txt`를 추가했다. `training-cuda-handoff.md`, verification, 이 로그와 [검증 report](../reports/training/pc13-cuda-smoke-2026-10-02/report.md)를 갱신했다.
- legacy 학습 절차는 팀원의 L0 트랙임을 handoff에 명시하고 신규 source audit와 독립적으로 환경을 준비했다. 실제 source 다운로드·병합·학습 승인과 모델 선택은 범위 밖이다.

### Environment / Commands / Result / Limitations

- Windows / Python 3.12.4 / i9-13900 / RAM 약 32 GB / RTX 3060 12 GB / driver 560.94. torch 2.6.0+cu124·torchvision 0.21.0+cu124와 Ultralytics 8.4.152 조합을 설치했다. 상세 pin·재설치 명령은 handoff에 있다.
- `pip check` 정상, 원격 `python -m unittest discover -s tests -q` 56개 통과. 로컬도 56개 통과, helper compile 확인.
- `python tools/cuda_training_smoke.py --output runs/pc13-cuda-smoke-20261002`와 별도 `--amp` run: 8 train/4 val 생성 이미지, 320 px, batch 2, workers 0, 1 epoch에서 forward/backward·loss·validation·best/last.pt·checkpoint reload GPU inference 확인. runner duration 각각 8.765/5.063 s. 실모델 성능·FPS 근거가 아니다.
- 초기 deterministic 경고를 보고 helper에서 torch import 전 cuBLAS workspace 설정을 추가해 AMP run을 검증했다. 반복 동일 결과·큰 batch·장시간 학습·SSH 단절 지속·Drive 업로드·Orin은 미검증이다.
- raw run과 전체 pip freeze는 원격 ignored `runs/`에 보존했다. 생성 데이터·weight·환경은 Git에 넣지 않고 code/config/요약만 sync한다.
- 문서 로컬 링크 4개 오류 0건, `git diff --check` 통과. SCP 반입 helper·requirements의 로컬/원격 SHA-256 일치를 확인했다. 원격 CLI help도 실행됐다.

### Decision impact / Next action / Git

- 실제 GPU 학습 경로는 준비됐지만 source·label·split 승인 gate는 유지한다. 다음은 SOHAS audit과 신규 recipe 승인 후 actual CUDA run이다.
- Commit: 이 기록을 포함하는 commit. 원격에는 의도적으로 반입한 파일만 path-scoped stash로 보존한 뒤 fast-forward한다. 모델·runs·venv는 ignored 상태로 그대로 유지한다.

## 2026-10-02 - 개발 Agent Layer 참고자료의 최소 적용

상태: 작업 규칙·문서 절차 `IMPLEMENTED`; 검증 결과는 아래에 기록. 모델·시스템 기능 변경 없음.

### Goal / Why / Scope

- 사용자가 제공한 baseline ZIP, 문서화 스킬북, Agent Layer 계획에서 현재 프로젝트의 개발 효율에 도움이 되는 기능만 가져온다. 첨부자료의 전체 설치 계획을 사용자 요청으로 해석하지 않는다.
- 기존 구현 우선·최소 변경·실패 재현과 회귀 검증·선택적 문서 갱신을 `AGENTS.md`에 반영했다. `documentation-governance.md`에 작업별 검증·문서 routing과 도입/보류 경계를 기록했다.
- 기존 전역 `search-first`·`verification-loop`를 재사용한다. ZIP의 template나 구버전 skill로 기존 파일을 덮어쓰지 않았다. 별도 프로젝트 status/ADR/skill 파일을 추가하지 않았다.
- Serena·Graphify·Archify·Claude-mem·Headroom·OmniRoute는 설치하지 않았다. 앱 설정·전역 MCP·권한·Git hook·소스·dataset·학습 조건은 변경하지 않았다.

### Environment / Verification / Limitations

- Windows PowerShell, 저장소 `main`. 작업 시작 `git status --short --branch` clean, `git pull --ff-only` already up to date.
- 세 참고자료와 현재 AGENTS·governance·Master Plan·MVP·open decisions·architecture·verification·최근 개발 로그·test 목록을 확인했다. 기존 source와 unittest 경로를 탐색해 새 도구 없이 유지 가능한 절차를 선택했다.
- 검증: PowerShell 정규식으로 변경 Markdown의 로컬 링크 1개를 확인해 오류 0건, `git diff --check` 통과, 최종 diff·status에서 의도한 문서 3개만 변경됨을 확인했다. 문서만 변경하여 코드 테스트·GPU/Orin smoke는 실행하지 않았다. 규칙의 장기적인 시간·토큰 절감 효과는 아직 측정하지 않았다.

### Decision impact / Next action / Git

- 프로젝트 MVP·연구·dataset recipe의 상태는 변경하지 않는다. 다음 material task부터 이 절차를 적용하고 반복 병목이 나타날 때만 추가 도구를 재평가한다.
- 현재 개발 후속 작업은 승인 전 SOHAS source/label/sample audit이며, 팀 legacy 재현과 독립적으로 진행한다.
- Commit: 이 기록을 포함하는 commit.

## 2026-10-02 - 신규 knife detector 후보와 데이터 보관 경계 재정렬

상태: 공식 Git image metadata 중복 `VERIFIED`; 후보 recipe `PROPOSAL`; Google Drive 폴더 `IMPLEMENTED`/목록 확인; raw source·CUDA 학습 `PLANNED`

### Goal / Why

- legacy 재현은 다른 팀원이 담당하고, 신규 detector 담당자는 source audit와 핵심 모델 제작을 독립적으로 진행한다.
- 여러 GPU를 사용할 수 있어도 중복 데이터셋을 조합한 학습을 필수 실험으로 늘리지 않고, hard-negative 효과와 target CCTV 적응 효과를 분리한다.

### Scope / Changed files

- `dataset-source-strategy.md`에 R1(SOHAS 검수 양성+음성), H1(같은 양성만), T1(R1+직접 촬영 training session)을 우선 후보로, L1(선별 legacy)/U1(고유 DaSCI)/S1/G1을 조건부 보강으로 기록했다. L0 model은 별도 트랙이며 그 데이터의 선별 활용 가능성까지 없애지 않았다. 최종 recipe의 팀 승인 전까지 모두 `PROPOSAL`이다.
- `project-plan.md`, `pre-orin-work-plan.md`, `open-decisions.md`, `model-data-plan.md`, `prior-work-and-dataset-review.md`, `verification.md`, README의 L0 선행 의존과 후보·증거 설명을 정합화했다. 코드·모델·raw data는 바꾸지 않았다.
- 팀 Google Drive의 [모델개발_데이터셋·실험결과](https://drive.google.com/drive/folders/1tBI7EkxKLN41CwHWA60ENXCgOw_0iYiz)에 원본(권리확인 후)/검수·분할명세/학습결과/독립평가 폴더를 만들고 목록으로 확인했다. [metadata 보고서](../reports/datasets/sohas-dasci-metadata-2026-10-02/report.md)만 [Drive 보관본](https://drive.google.com/file/d/1h10H-lSCS81TbUTP8epF0qotx5MVkzDy/view?usp=drivesdk)으로 업로드하고 metadata로 파일·부모 폴더를 재확인했다. 원본·자체 촬영 영상은 업로드하지 않았다. 10 GB 미만 로컬 staging을 허용한다.

### Environment / Evidence / Limitations

- Windows PowerShell과 GitHub REST Git tree metadata. 원본 저장소 `ari-dasci/OD-WeaponDetection`의 `master` commit `48860b990e4d4f57fe100248887fceb248475dc8`에서 SOHAS train/test image 5,002/857장, DaSCI image 2,078장을 집계했다. DaSCI 1,985장은 SOHAS와 basename 및 Git blob ID가 일치하고 93장만 byte-unique 후보이다. SOHAS image 5,859장 대비 XML 5,942개로 orphan XML 83개가 있다.
- Git blob 일치는 바이트 동일성 근거지만, 남은 93장의 perceptual 중복·annotation·target 적합성과 SOHAS negative의 knife 부재는 검증하지 않았다. SOHAS README/License 표기 충돌과 ACF 원 저장소 404도 여전히 남아 있다. 공개 원본 다운로드·공유·학습은 이번 작업에서 수행하지 않았다.

### Decision impact / Next action

- SOHAS 사용 조건과 raw package를 확인하고 source/label/sample audit를 수행한다. 승인 전에는 R1/H1도 학습하지 않는다.
- 공통 tuning/독립 test를 먼저 설계하고 R1/H1을 같은 모델·설정에서 비교한다. 직접 촬영 session이 준비되면 T1을 판단한다. L0 완료는 이 작업을 막지 않는다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-29 - 수업 자료와 개발 저장소 폴더 통합

상태: 로컬 폴더 구조 `IMPLEMENTED`; Git·submodule·Python import·CLI `VERIFIED`; Orin 실기기와 관련 없음

### Goal / Why

- 바탕화면의 수업 자료 폴더를 상위로 두고 개발 저장소를 그 안으로 옮긴다. GitHub 동기화 범위를 개발 저장소로 한정한다.
- 비개발 자료는 날짜·내용 중심 파일명과 역할별 폴더로 정리하되, 개인정보가 포함될 수 있는 채팅·팀원 사진·서명은 저장소 밖에 둔다.

### Scope / Changed files

- 기존 `Desktop/00_Development_Github`을 수업 상위 폴더의 `03_개발_GitHub`으로 이동했다. 저장소 내부 소스·모델·실험 데이터 이름은 바꾸지 않았다.
- 상위 폴더의 오래된 별도 `.git`은 현재 저장소 `main`의 조상 commit `f209940`을 가리켰고, 고유한 추적 변경 없이 파일 이동으로 인한 삭제 상태였다. 삭제하지 않고 `99_이전Git_백업/.git`에 보존했다.
- 상위 폴더의 비개발 자료 46개 중 SHA-256이 정확히 같은 제안서 PDF와 주간보고서 양식 HWP 각 중복본 1개를 제거했다. 나머지 44개를 날짜 접두어와 역할별 폴더로 정리했다. 상위 `260929_폴더안내.md`가 구조·날짜 해석·동기화 범위를 설명한다.
- 이 저장소에서는 `AGENTS.md`, `README.md`, 이 개발 로그와 검증 매트릭스의 경로·상태만 갱신한다.

### Environment / Verification / Limitations

- Windows PowerShell, Git `main`; 이동 전후 `git status --short --branch`는 clean, `origin/main`과 일치. `git pull --ff-only`는 already up to date. 고정된 `Crime_Prediction` submodule commit `5e228697`도 유지됐다.
- 로컬 `.venv-ml` 이동 후 이전 절대 경로의 editable `.pth`와 CLI launcher가 깨졌다. Python 3.11.9·현재 setuptools에서 한글 경로의 `pip install -e .`는 cp1252 `UnicodeEncodeError`로 실패했다. 일반 `pip install . --force-reinstall --no-deps --no-build-isolation`로 launcher를 갱신하고, 로컬 `.pth`에 가상환경 기준 상대 `src` 경로를 먼저 넣어 live source import를 복구했다. 이 `.venv-ml` 변경은 Git에 포함되지 않는다.
- 복구 시험 중 만든 `%LOCALAPPDATA%/edge-threat-response-worktree` junction은 제거 명령이 호스트 정책에 막혀 남아 있다. 실제 파일 복사본은 아니며 새 저장소를 가리키는 로컬 링크다. 개발 경로로 사용하지 않는다.
- 이후 source import와 `etr-dataset --help`, `etr-replay --help`가 실행됐다. `python -m unittest discover -s tests -q`는 56개 전부 통과했고 `git diff --check`도 통과했다. 장비 기능 검증은 이번 파일 정리의 범위가 아니다.

### Decision impact / Next action

- 이후 개발 작업은 새 `03_개발_GitHub` 경로만 사용한다. 기존 절대 경로를 하드코딩한 외부 자동화가 있다면 별도로 갱신해야 한다.
- 구형 가상환경의 설치 문제는 로컬에서 우회 복구했지만, 새 환경의 editable 설치는 경로 인코딩 문제를 확인한 뒤 실행한다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-26 - 중복·과거형 문서 정리

상태: 문서 구조 `IMPLEMENTED`; 내부 참조·변경 범위 검증은 아래 명령 결과로 기록

### Goal / Why

- 현재 MVP와 실행 상태를 빠르게 찾을 수 있도록 중복된 계획 문서와 끝난 단계 중심 문구를 줄인다.
- 과거 결정·실험 증거는 보존하면서 현행 작업 순서가 오래된 초안에 의해 혼동되지 않게 한다.

### Scope / Changed files

- `research-or-product-plan.md`는 확정된 MVP 명세·Project Plan과 내용이 겹치고 MVP에서 제외한 threat score 초안이 남아 있어 삭제했다.
- `implementation-plan.md`은 이미 끝난 Increment A/B와 현재 구조·Pre-Orin 계획을 중복해 삭제했다. 두 파일의 Git 이력은 복구 가능하다.
- 빈 미추적 `C++기반 코드 전환 가능성.txt`를 제거했다. 파일 크기는 0 byte였고 Git에는 추적된 적이 없다.
- `pre-orin-work-plan.md`를 남은 W4 사람 검수·source audit·CUDA 학습·Orin 통합 중심으로 다시 작성했다.
- README, Master Plan, 문서 운영 규칙, architecture, open decisions, verification, 2026-09-04 회의 기록과 legacy asset 기록의 오래된 참조·상태를 정리했다.
- Code, dataset, model, run result와 회의·실험 원본 증거는 변경하지 않았다.

### Environment / Verification / Limitations

- 환경: Windows PowerShell, Git `main`. `git pull --ff-only` → already up to date.
- `rg --files docs`, 문서별 참조 검색, Git status와 파일 크기로 삭제 범위를 확인했다.
- README·AGENTS·docs의 Markdown 문서 19개를 검사했고 로컬 파일 링크 오류는 0건이었다. 삭제 문서의 현행 참조는 없고 과거 개발 로그의 언급만 남겼다.
- `git diff --check`와 변경 범위 확인을 commit 전 실행한다. 문서 전용 작업이어서 code test는 실행하지 않는다.
- 보고서와 과거 회의 요약은 당시의 사실을 보존한다. 현재 상태로 읽어야 하는 부분에는 최신 기준 문서 링크를 추가했다.

### Decision impact / Next action

1. Legacy 128장 사람 검수 및 L0 사용 범위 결정.
2. 권리·라벨·중복 gate를 통과한 공개 source만 추가 평가.
3. 승인된 데이터의 CUDA baseline과 Orin 실기기 통합 증거 확보.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-26 - 선행연구 검토 정정과 역할별 dataset 평가 기준

상태: 문헌·저장소 desk review `VERIFIED` (표기·접근 상태 한정), 평가 절차 `DECISION`, raw package·legacy 사람 판정·source 채택 `PLANNED`

### Goal / Why

- GPT가 작성한 선행연구·dataset 자료의 사실관계와 과장된 점수·채택 표현을 고쳐 연구 근거로 쓸 수 있게 한다.
- 다음 작업인 legacy 128장 사람 검수와 공개 source 표본 검수에 동일한 역할별 판정 기준을 적용한다.

### Scope / Changed files

- `prior-work-and-dataset-review.md`를 재작성해 논문별 확인 사실, 우리 구성요소와의 관계, 적용 한계 및 공개 dataset의 역할을 명시했다.
- `dataset-evaluation-criteria.md`를 추가해 권리·라벨·독립성 gate, training/image/event/synthetic 역할별 질문, legacy `review.csv` 열 정의를 기록했다.
- `dataset-source-strategy.md`, `model-data-plan.md`, `open-decisions.md`, `architecture.md`, `verification.md`, `documentation-governance.md`, README를 정합화했다.
- 코드·raw dataset·검수 CSV·모델과 학습 run은 수정하지 않았다. 기존 C++ 관련 미추적 파일도 변경하지 않았다.

### Evidence / Result

- OD-WeaponDetection 공식 README의 CC BY-SA 4.0 표기와 같은 저장소 `License.md`의 CC BY 4.0 전문이 충돌한다. 실제 적용 범위 확인 전 권리 gate 미통과로 기록했다.
- ACF 논문이 인용한 GitHub 저장소는 2026-09-26 `git ls-remote`에서 repository not found였다. 외부 image 평가 **후보**로 유지하며 사용 가능성을 확정하지 않았다.
- DISARM 공식 페이지에서 현재 공개된 것은 test subset임을 확인했다. DISARM temporal window는 bbox 연속성을 사용하고 우리 K-of-N boolean window와 구현이 다르다.
- local `review.csv` header가 문서의 8개 판정 열과 일치하고 contact sheet 8장이 존재함을 확인했다.
- 선행연구의 근거 없는 100점 순위를 제거하고, 공개 bbox dataset만으로 B0~B3 event metric을 평가할 수 없다는 경계를 추가했다.

### Verification / Limitations

- 검증 환경: Windows PowerShell, 공식 논문·제공자 저장소·dataset card의 공개 페이지와 현재 로컬 저장소.
- `git pull --ff-only` → already up to date. 문서 변경이므로 code test는 실행하지 않았다. `git diff --check`와 내부 링크 검사는 commit 전 실행한다.
- 외부 raw package, bbox 시각 품질, image 중복, 성능, 실제 CCTV event annotation은 확인하지 않았다. 특정 공개 dataset은 아직 `ADOPTED`가 아니다.

### Decision impact / Next action

1. 다음 gate는 legacy 128장의 사람이 하는 visual review다. CSV는 현재 판정 전 상태로 보존한다.
2. 결과를 source/version·split·bbox size 구간으로 집계해 L0의 전체/선별/역사적 기준 중 역할을 결정한다.
3. 이후 SOHAS 권리 충돌과 source package를 확인하고, 통과한 source만 표본·중복 audit으로 진행한다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-22 - Target-CCTV dataset source strategy and admission gates

상태: target domain·source 역할 분리 `DECISION`, individual source import·recipe·full training `PROPOSAL`/`PLANNED`

### Goal / Why

- 공개 dataset의 이미지 수나 설명만으로 source를 합쳐 기존 legacy의 domain mismatch·duplicate·split leakage 문제를 되풀이하지 않는다.
- 최종 설치 환경에 가까운 data를 학습·외부평가·synthetic 보조 실험으로 분리해 detector 성능과 B0~B3 event 판단 실험의 근거를 보존한다.

### Scope / Changed files

- `docs/dataset-source-strategy.md`를 새로 만들어 target CCTV assumption, source별 역할·적용 한계, first recipe 순서, admission audit, 근거와 즉시 작업을 기록했다.
- README, master plan, MVP specification, model/data plan, open decisions, architecture, verification, pre-Orin plan, documentation governance를 해당 기준으로 정합화했다.
- 코드, raw dataset, external download, model weight, training config 및 model run은 변경하지 않았다.

### Decision

- 목표 domain은 약 3 m 높이의 fixed indoor CCTV가 사람을 elevated/oblique angle로 보는 복도·출입구·공용공간이다. 작은/먼 knife, person co-occurrence, 손·팔 occlusion을 우선한다.
- legacy는 사람 review 후 별도의 L0 baseline으로만 사용한다. SOHAS는 첫 public real-world training 후보, DaSCI는 cross-source dedup audit 후 보강 후보로 둔다.
- ACF Knife와 US Mock Attack은 Dataset v1 training에 넣지 않고 external CCTV holdout 후보로 보존한다. Simuletic 114장은 primary recipe에서 제외하며 real-data baseline 뒤 synthetic ablation에만 사용한다.
- publicly described source 수치나 license는 raw package·usage terms·manifest audit 전 project inventory나 성능 근거로 쓰지 않는다.

### Evidence / Verification

- 공식 source page와 ACF peer-reviewed paper를 desk review했다. SOHAS repository는 CC BY-SA 4.0을 명시한다.
- ACF paper는 full-HD CCTV와 small knife 문제를 설명하지만, raw package manifest·license·접근성은 확인하지 않았다. 논문 본문의 ACF Knife image 수와 표의 label 수 표기가 달라 raw manifest가 권위 있는 inventory가 되어야 한다.
- 문서 링크와 상태 표현을 검토했으며, code test는 source code가 변경되지 않아 실행하지 않았다. `git diff --check`는 commit 전 실행한다.

### Limitations / Next action

1. legacy review CSV의 human verdict가 아직 없어 L0 full training도 승인되지 않았다.
2. SOHAS, DaSCI, ACF, US Mock Attack의 raw package·license·source/session metadata와 100장 표본 audit이 남아 있다.
3. SOHAS–DaSCI–legacy exact/perceptual duplicate report가 없으므로 source 병합이나 CUDA full training을 시작하지 않는다.
4. audit 승인 후에만 R1 SOHAS recipe, external CCTV holdout 및 CUDA run을 확정한다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-15 - W4 review pack·W5 detector/video·W6 CUDA handoff 구현

상태: W4 tooling·W5·W6 handoff `IMPLEMENTED`/PC `VERIFIED`, W4 사람 판정·CUDA full training·Orin `PLANNED`

### Goal / Why

- Orin 도착 전 legacy dataset의 시각 검수 근거를 만들고, 새 knife weight가 없어도 image/video→canonical detection→B0~B3→metadata/snapshot 전체 경로를 검증한다.
- 첫 full training을 사람의 data review 뒤 CUDA 환경으로 안전하게 넘기고, run·dataset·artifact provenance를 남긴다.

### Scope / Changed files

- `dataset/review.py`, `etr-dataset review-pack`, review requirement와 test를 추가했다.
- `detector.py`, `media.py`, `runtime.py`, `detect_cli.py`에 lazy Ultralytics single/composite adapter, class remap, fail-closed component error, OpenCV image/video, canonical JSONL, latency/provenance와 current-frame snapshot을 구현했다.
- `etr-detect`, `etr-run`, development/legacy smoke config와 detector/runtime test를 추가했다.
- training runner에 Git commit, dataset manifest, artifact hash와 GPU-required preflight를 추가하고 CUDA development profile, Colab notebook, handoff 문서를 작성했다.
- README, architecture, implementation/pre-Orin/model-data plan, open decisions, verification과 재현 가능한 summary/report를 갱신했다.
- legacy submodule과 raw dataset은 수정하지 않았다. review image/CSV, run output, video, snapshot, weights는 Git에서 제외했다.

### Environment / Commands

- Windows build 26200, Python 3.11.9, AMD Ryzen 5 4600H, CUDA false.
- `.venv-ml`: torch 2.14.0+cpu, torchvision 0.29.0, Ultralytics 8.4.152, OpenCV 5.0.0.93, Pillow 12.3.0.
- W4: `etr-dataset review-pack ... --per-stratum 12 --seed 20260915`.
- W5: 실제 YOLO26n person + legacy `customknife_v1.1.pt` composite로 image와 3-frame video를 `etr-detect`/`etr-run` 실행하고, 생성 detection JSONL을 `etr-replay` B0~B3에 재사용했다.
- W6: CUDA-required local preflight를 실행해 CUDA false를 명시적으로 탐지했다. 실제 full training은 실행하지 않았다.

### Results / Measured evidence

- W4: exact duplicate 제외 7,361장 decode 성공, 오류 0. deterministic sample 128장, contact sheet 8장 생성.
- 표본 구성: source 92/36, split train 71/val 27/test 30, 최소 bbox area bucket tiny 14/small 13/medium 18/large 83.
- 개발자가 contact sheet 8페이지 전체를 확인했으며 사람 동반 장면과 제품·주방·손/knife 클로즈업·워터마크·저해상도 장면이 혼재했다. 같은 인물·배경의 반복은 filename/exact-hash만으로 near-duplicate/session 분리가 완전하지 않을 수 있음을 보여준다. row별 사람 판정은 아직 완료되지 않았다.
- W5 actual PC smoke: 3 valid frames, canonical detections 9개, B3 event frame 1에서 1회, JPEG snapshot 1장, action error 0.
- 같은 detection JSONL의 event frame은 B0=0, B1=1, B2=0, B3=1이었다.
- model cold load가 포함된 첫 frame 6,210.685 ms, 3-frame median inference 106.694 ms. 이 수치는 배포 성능 근거가 아니다.
- W6 local preflight: expected exit 2, `torch.cuda.is_available() == false`; Git/config/data/dataset manifest와 환경 hash evidence 생성 확인.

### Verification / Limitations

- `python -m unittest discover -s tests -v` → 56 tests, all passed.
- `python -m compileall -q src tests` → passed.
- notebook/training/detector JSON parse → passed.
- `git diff --check` → passed.
- review sample은 전체 품질 보증이 아니며 `review.csv`의 사람 판정 전에는 Baseline v1 학습 승인으로 간주하지 않는다.
- legacy 반복 양성 이미지는 정확도·일반화 평가 자료가 아니다. legacy knife weight의 성능 lineage도 `UNVERIFIED`다.
- 실제 CUDA full training, 선택 detector, 독립 영상, Orin runtime/camera/GPIO와 benchmark는 검증하지 않았다.

### Decision impact / Next action

- composite topology는 구현 가능성이 확인됐지만 P0-05의 최종 detector 결정으로 승격하지 않는다.
- 팀이 local `data/review/legacy-development-v1/review.csv`를 검토하고 baseline 학습 승인·제외 규칙을 기록한다.
- 승인 후 Colab notebook으로 legacy Baseline v1을 학습하고 `best.pt`를 동일 W5 pipeline에 경로 교체해 독립 영상 smoke를 수행한다.
- W7은 Baseline v1을 막지 않으며 DaSCI Knife/SOHAS → Open Images selective → Simuletic smoke 순으로 표본 검토한다.

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-15 - Spatial v2·knife exporter·YOLO26n CPU smoke 구현

상태: class mapping·spatial v2·dataset exporter·training runner `IMPLEMENTED`/PC `VERIFIED`, detector 성능·CUDA/Orin `PLANNED`

### Goal / Why

- 실제 detector 연결 전에 신규 spatial 정책과 raw/model-local/runtime class 경계를 코드로 고정한다.
- group-aware knife-only dataset이 실제 YOLO 학습까지 연결되는지 작은 CPU smoke로 확인한다.

### Scope / Changed files

- pipeline config schema v2와 `expanded_bbox_only` spatial policy를 추가하고 schema v1 결과를 호환 보존했다.
- `etr-dataset materialize-knife-yolo` exporter를 추가해 polygon→bbox, knife model-local class 0, hardlink/copy, exact duplicate 제거와 manifest를 구현했다.
- config-driven `etr-train`, CPU smoke config와 고정 ML requirement를 추가했다.
- 관련 config, 단위 test, README, 계획·검증 문서와 재현 가능한 smoke summary/report를 갱신했다.
- raw dataset과 legacy submodule은 수정하지 않았다. generated dataset, venv, runs와 weights는 Git에서 제외했다.

### Environment / Results

- Windows/Python 3.11.9, AMD Ryzen 5 4600H, CUDA false.
- `.venv-ml`: torch 2.14.0+cpu, torchvision 0.29.0, Ultralytics 8.4.152, OpenCV 5.0.0.93.
- development split default 70/15/15, seed 20260915: train 5,155 / val 1,104 / test 1,105 planned.
- exact duplicate 3장 제거 후 전체 materialized output: train 5,153 / val 1,104 / test 1,104, 총 7,361 images/labels와 9,057 objects.
- bbox 7,610건과 polygon→bbox 1,447건. output bad label line 0, cross-split source group 0, exact hash 0.
- audit 이후 source image 7,364장과 대응 label의 SHA-256 변경 0건을 재확인했다.
- smoke: train 32 / val 8, 49 objects, 40 images decode 성공, YOLO26n 320 px/1 epoch/batch 4.
- wrapper 측정 training duration 18.282 s. validation과 best/last checkpoint 생성, best checkpoint 재로딩·단일 이미지 inference 성공.

### Verification / Limitations

- `python -m unittest discover -s tests -v` → 46 tests, all passed.
- smoke의 precision/recall/mAP 0은 1 epoch·극소 표본 결과이며 성능 근거로 사용하지 않는다.
- 전체 materialized split은 development default이고 visual label 품질 검수와 최종 연구 split 승인을 대신하지 않는다.
- YOLO26n 선택, detector topology, threshold, CUDA/Jetson 호환성과 성능은 아직 `PROPOSAL`/`PLANNED`다.

### Next action

1. Dataset visual-review pack과 ambiguous annotation 검토 자료
2. fake backend 기반 detector/video/detection-JSONL/snapshot integration
3. CUDA profile·GPU preflight·Colab/학교 GPU 인계 절차

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-15 - Orin 도착 전 작업 재정렬과 CPU smoke 제외

상태: pre-Orin 작업 순서·class mapping·spatial v2 방향 `DECISION`, 실제 adapter·exporter·학습 `PLANNED`

### Goal / Why

- 외부 GPT 평가를 저장소·개발 PC·공식 플랫폼 정보와 대조하고, 현재 노트북에서 어려운 CPU model smoke가 전체 개발을 막지 않도록 작업 경계를 다시 정한다.
- Jetson 도착 전에는 ML dependency가 없는 계약·데이터 변환·adapter/video 골격을 최대한 끝내고, 실제 model·CUDA·hardware 검증은 증거를 만들 수 있는 환경으로 이관한다.

### Scope / Changed files

- `pre-orin-work-plan.md`를 추가하고 README, implementation plan, model/data plan, MVP specification, architecture, open decisions, verification을 정합화했다.
- 코드, dataset, model, ML package와 Jetson 설정은 변경하지 않았다.

### Verified findings and decisions

- 기준 commit `f8acb89`가 원격 `main`과 일치하고 working tree가 깨끗한 상태에서 시작했다.
- Windows Python 3.11.9 환경에 torch·Ultralytics·OpenCV가 설치되어 있지 않다. 현재 순수 로직은 `unittest` 38개가 통과했다.
- CPU training smoke를 pre-Orin 완료 조건에서 제외하고 fake backend·dataset contract·replay integration으로 대체한다.
- raw class, model-local training class, runtime canonical class를 분리한다. knife-only YOLO는 model-local `0=knife`, runtime은 canonical `knife`/ID `1`이다.
- 신규 spatial schema v2는 expanded bbox만 association gate로 사용하고 normalized distance는 진단값으로 남긴다. 기존 v1은 replay 호환성을 위해 보존한다.
- composite detector는 primary proposal일 뿐 최종 topology가 아니다. split·seed·epoch·batch·image size는 development default다.
- 저장소 전체 AGPL 지정은 수행하지 않고 Ultralytics 사용·배포 정책을 P0-12로 추가했다.
- JetPack 7.2.1 actual-board runtime은 native smoke 우선, container 비교 순서로 수정했다.

### Verification / Limitations

- `git pull --ff-only` → already up to date.
- `python -m unittest discover -s tests -v` → 38 tests, all passed.
- 모델 load, CPU/CUDA training, OpenCV video, snapshot, Orin runtime은 수행하지 않았다.
- 공식 플랫폼 지원은 실제 대여 장비의 모델 호환성과 성능을 증명하지 않는다.

### Next action

1. class/config와 spatial v2의 하위 호환 구현
2. knife-only dataset exporter와 visual-review pack
3. fake detector 기반 detector/video/snapshot integration scaffold
4. CUDA training handoff package와 외부 dataset 후보 기록

### Git

- Commit: 이 기록을 포함하는 commit

## 2026-09-14 - Increment A 판단 core와 B0~B3 replay 구현

상태: pure core·recorded-detection replay `IMPLEMENTED` / 개발 PC `VERIFIED`, detector·영상·snapshot·GPIO·Jetson `PLANNED`

### Goal / Why

- 실제 모델과 Jetson이 준비되기 전에 연구 핵심인 geometry association, K-of-N, 상태 전이와 B0~B3 차이를 결정론적으로 검증한다.
- 향후 detector, camera, snapshot, GPIO adapter가 따를 입력·event·오류 계약을 고정한다.

### Scope / Changed files

- `src/edge_threat_response/`에 domain, config, spatial, temporal, state machine, ports, pipeline, replay loader와 `etr-replay` CLI를 구현했다.
- `configs/replay/development.example.json`과 synthetic detection fixture를 추가했다.
- geometry·K-of-N·전 상태·cooldown/rearm·B0~B3·event 중복 억제·port 실패 격리·replay validation·CLI test를 추가했다.
- 실제 영상 decode, detector, model weight, camera, snapshot 저장, GPIO, Jetson runtime, dataset 학습은 수행하지 않았다.

### Implemented contracts and judgment

- reliable knife마다 중심점이 가장 가까운 person을 선택하고 person bbox diagonal로 거리를 정규화한다. 거리 threshold와 확장 person bbox 포함을 모두 만족해야 associated다.
- knife presence와 associated-pair presence에 별도 K-of-N buffer를 사용한다. `missing`·`detector_error`도 false sample로 window에 포함하고, N개가 차기 전이라도 K개 true이면 확인한다.
- B0는 current knife, B1은 knife K-of-N, B2는 current association, B3는 association K-of-N으로 한 pipeline에서 predicate만 바꾼다.
- `CONFIRMED` 진입당 event·alarm을 한 번만 발생시키고 근거 소실 시 alarm을 해제한다. cooldown은 설정된 연속 clear sample 뒤에만 rearm된다.
- event recorder 실패는 alarm을 차단하지 않는다. snapshot port 실패와 action 오류는 frame evidence에 명시한다.
- tracking이 없으므로 temporal signal은 동일 person이 아닌 source-level boolean이다.

### Environment / Commands / Verification

- 환경: Windows, Python 3.11.9, editable package `edge-threat-response 0.1.0`
- 테스트: `python -m unittest discover -s tests -v` → 38 tests, all passed
- 구문 검사: `python -m compileall -q src tests` → passed
- 설치: `python -m pip install -e .` → passed
- CLI smoke: `etr-replay --input tests/fixtures/replay/basic.jsonl --config configs/replay/development.example.json --output-dir reports/replay/increment-a-smoke` → passed, action error 0
- Git commit: 이 기록을 포함하는 commit

### Measured software-smoke result

- 동일 9-frame synthetic detection 입력에서 최초 event frame: B0=0, B1=1, B2=1, B3=2
- cooldown 후 두 번째 event frame: B0=7, B1=8, B2=7, B3=8
- mode별 event 2개, event recorder/alarm action error 0

### Known limitations / Decision impact

- 이 결과는 detector 정확도, 실제 frame snapshot, GPIO, Jetson 성능 또는 연구 가설을 검증하지 않는다.
- development config의 confidence, distance, bbox expansion, K/N, rearm 수치는 테스트 fixture용이며 최종 파라미터가 아니다.
- frame rate와 시간 간격이 불규칙한 실제 입력에서도 frame-count K-of-N을 쓸지는 baseline에서 sampling contract와 함께 확인해야 한다.
- Increment B는 P0-05 detector topology와 P0-09 runtime 결정 뒤 진행한다.

### Next action

1. D2 sample review로 external/legacy source와 ambiguous annotation rule을 승인한다.
2. Orin Nano 수령 시 hardware/JetPack inventory와 container GPU smoke를 수행한다.
3. detector topology·runtime을 고정한 뒤 video/detector/snapshot adapter를 Increment B로 연결한다.

## 2026-09-14 - D1 dataset audit·manifest·split planning 도구 구현

상태: D1 `IMPLEMENTED`, synthetic/legacy structure `VERIFIED`, 시각 품질·외부 source·학습 `PLANNED`

### Goal / Why

- source별 class 의미를 보존하면서 YOLO bbox/polygon dataset을 일관되게 검사한다.
- 동일 원본 group과 exact duplicate가 train/test에 나뉘는 누수를 실제 학습 전에 탐지·방지한다.

### Scope / Changed files

- `pyproject.toml`과 `src/edge_threat_response/dataset/`에 registry, label parser, audit, manifest, report, group split planner와 CLI를 구현했다.
- `configs/datasets/`에 JSON schema와 legacy v1.0/v1.1 registry를 추가했다.
- `tests/`에 parser·registry·audit·split·CLI fixture test를 추가했다.
- `reports/datasets/legacy-2026-09-14/`에 추적 가능한 summary와 Markdown report를 생성했다. 대용량 manifest와 issues JSONL은 재생성 가능하므로 Git에서 제외했다.
- legacy submodule과 raw image/label은 수정하지 않았다. 외부 다운로드·실제 split 적용·학습은 수행하지 않았다.

### Implemented behavior

- source별 raw→canonical class mapping을 registry load 시 검증한다.
- YOLO normalized bbox와 polygon을 구분하고 class, finite coordinate, boundary, positive extent를 검사한다.
- image/label pairing, empty label, orphan, case-insensitive duplicate stem을 검사한다.
- stable image ID, source/group/split, source/license reference, annotation·class counts, SHA-256을 JSONL manifest로 생성한다.
- original split의 source-group·exact-hash leakage를 탐지한다.
- split planner는 source group과 exact duplicate 연결요소를 하나의 assignment unit으로 배치하며 raw 파일은 이동하지 않는다.
- audit은 CI용 fail-on severity와 알려진 legacy 문제를 inventory할 `--fail-on never`를 분리한다.

### Environment / Commands / Verification

- 환경: Windows, Python 3.11.9, editable package `edge-threat-response 0.1.0`
- 테스트: `python -m unittest discover -s tests -v` → 13 tests, all passed
- 구문 검사: `python -m compileall -q src tests` → passed
- 설치·CLI: `python -m pip install -e . --no-deps`, `etr-dataset --help` → passed
- 전체 audit: `etr-dataset audit --registry configs/datasets/legacy.json --repo-root . --output-dir reports/datasets/legacy-2026-09-14 --fail-on never`
- split smoke: 전체 manifest, development-only ratio 0.70/0.15/0.15, seed 20260914 → 7,364 eligible, 0 excluded, 3,552 groups; raw 파일 변경 없음
- lint: `ruff`는 개발 PC에 설치되어 있지 않아 실행하지 못했다.
- Git commit: 이 기록을 포함하는 commit

### Measured result

- images 7,364, objects 9,060, valid label files 7,364, invalid/missing/empty 0
- annotation: bbox 7,613, polygon 1,447; raw class `0` 9,060건을 canonical knife `1`로 mapping
- unique source groups 3,552, original split crossing groups 317
- exact duplicate image groups 3, exact hashes crossing original splits 0

### Known limitations / Decision impact

- image decode·손상 검사와 시각적 label 품질 검수는 하지 않는다.
- filename grouping은 registry가 지정한 규칙의 결과이며 실제 촬영 session ground truth가 아니다.
- perceptual near-duplicate 검사는 구현하지 않았다.
- smoke-test split 비율과 seed는 연구 결정이 아니며 어떤 학습 dataset에도 적용하지 않았다.
- legacy 기존 split은 최종 detector 평가에 사용하지 않고 승인된 source/session group 기준으로 다시 계획해야 한다.

### Next action

1. 외부·legacy sample의 시각 검수와 ambiguous annotation rule을 팀이 확정한다.
2. 시스템 Increment A의 domain·spatial·temporal·state-machine·B0~B3 core를 구현한다.
3. 승인 source가 정해진 뒤에만 D2 importer와 processed recipe를 추가한다.

## 2026-09-14 - 모델·데이터 준비 구현 범위 확정과 legacy dataset 구조 점검

상태: D1 구현 범위·class contract `DECISION`, 외부 dataset·detector·학습 `PROPOSAL`, legacy 구조 `VERIFIED`

### Goal / Why

- detector 재학습 전에 raw label 의미, provenance, split leakage를 확인해 잘못된 2-class 병합과 평가 누수를 방지한다.
- 시스템 core 개발과 병렬로 진행할 수 있는 최소 dataset tooling만 고정하고 대규모 다운로드·학습은 근거가 생길 때까지 미룬다.

### Scope / Changed files

- `model-data-plan.md`를 추가하고 implementation plan, README, AGENTS, project plan, open decisions, verification, legacy asset 기록을 갱신했다.
- legacy submodule은 읽기 전용으로 조사했으며 dataset·weight·source code를 수정하지 않았다.
- 외부 dataset 다운로드, 신규 코드 구현, model load·학습·추론은 수행하지 않았다.

### Verified findings

- legacy v1.0 1,183장과 v1.1 6,181장, 총 JPG 7,364장과 basename이 일치하는 label을 확인했다. missing image, missing label, empty label file은 0개다.
- 두 dataset은 모두 `knife` 단일 클래스이고 9,060개 annotation의 raw class ID는 전부 0이다.
- annotation은 bbox 7,613개와 polygon 1,447개가 혼재한다.
- filename source group 기준 v1.0 내부 3개 group이 split을 교차하며, 두 version을 합치면 317개 group이 기존 split을 교차한다.
- COCO의 person/knife class, Open Images의 box 규모·Person/Knife class, Simuletic sample의 114장·synthetic·person/knife·CC BY 4.0 선언을 각 공식/제공자 페이지에서 확인했다.

### Decisions and judgment

- detector output은 person/knife 두 logical class로 유지하되 단일 2-class model은 확정하지 않는다.
- raw source class map을 별도로 관리하고 processed dataset에서만 canonical `0=person`, `1=knife`를 사용한다.
- D1은 registry·manifest, bbox/polygon validator, exact duplicate와 group split leakage, report, fixture test까지 구현한다.
- source별 downloader, 실제 병합, training wrapper는 각각 sample 승인과 detector 결정 뒤로 미룬다.
- legacy knife-only data를 재사용할 수 있는 composite person+knife detector를 우선 후보로 두고, unified model은 person annotation 완전성 확보 시에만 검토한다.

### Evidence / Limitations

- 파일 개수·YAML·label token structure·filename group을 자동 집계했다. image 내용, bbox/polygon의 시각적 정확성, upstream source 접근성, 개별 image license는 검수하지 않았다.
- exact image hash와 near-duplicate 검사는 아직 구현·실행하지 않았다.
- provider가 제시한 dataset 설명은 후보 근거이며 프로젝트 적합성이나 성능을 증명하지 않는다.

### Environment / Verification commands

- 환경: Windows, PowerShell, 기준 작업공간 `00_Development_Github`
- 원격 동기화: `git pull --ff-only`
- legacy 조사: `Get-ChildItem`, `Get-Content`, `rg`, label token/group 집계
- 공식 근거: Ultralytics COCO docs, Open Images V7와 boxable class CSV, Hugging Face provider dataset card
- Git commit: 이 기록을 포함하는 commit

### Next action

1. 시스템 Increment A와 dataset D1 중 착수 순서를 정해 작은 단위로 구현한다.
2. D1 결과로 legacy exact duplicate와 split leakage report를 생성한다.
3. 팀이 외부 후보 sample과 ambiguous annotation rule을 검토한 뒤 D2 source를 승인한다.

## 2026-09-14 - 신규 기준 플랫폼을 Jetson Orin Nano로 변경하고 구현 단계를 고정

상태: 플랫폼·구현 순서 `DECISION`, 실기기·ML runtime `PLANNED`

### Goal / Why

- 구형 Jetson Nano 환경에 신규 코드를 맞추지 않고 최신 Jetson Orin Nano 지원 환경을 기준으로 개발한다.
- 실기기와 detector가 준비되기 전에도 연구 핵심인 spatial·temporal·state-machine·B0~B3를 PC에서 검증할 수 있도록 작업을 분리한다.

### Scope / Changed files

- `implementation-plan.md`를 추가하고 README, AGENTS, project plan, MVP specification, architecture, open decisions, verification, research plan을 정합화했다.
- 소스 코드, 모델, dataset, container, Jetson 설정은 변경하지 않았다.

### Decisions

- 신규 기준 플랫폼은 Jetson Orin Nano Developer Kit, 고정 기준 소프트웨어는 JetPack 7.2.1 / Jetson Linux 39.2.1이다.
- 기존 Jetson Nano 4GB는 legacy baseline과 선택적 cross-device 비교용으로 격리한다.
- B0~B3 ablation은 동일 Orin 장비·detector·입력·설정에서 수행하며 Nano/Orin 비교와 섞지 않는다.
- 첫 구현은 platform-neutral pure core, JSONL detection replay, mock alarm·metadata, B0~B3와 테스트다.
- 실제 video/detector는 model/runtime 결정 후, camera/GPIO/resource adapter는 Orin inventory와 runtime smoke test 후 연결한다.
- tracking이 없는 MVP의 K-of-N은 동일 개인이 아니라 source-level association boolean을 집계한다.
- legacy가 person과 knife에 별도 모델을 사용하는 만큼 단일 2-class 재학습은 자동 채택하지 않고 person annotation 완전성을 먼저 확인한다.

### Evidence / Limitations

- 2026-09-14 NVIDIA 공식 페이지에서 JetPack 7.2.1, Jetson Linux 39.2.1, Ubuntu 24.04, kernel 6.8, CUDA 13.2.1, cuDNN 9.20.0, TensorRT 10.16.2, VPI 4.1.3과 Jetson Orin Family 지원을 확인했다.
- Orin Nano quick-start 문서에서 JetPack 7.2.1 설치가 USB의 Jetson ISO 방식이며, 구형 firmware에는 JetPack 6.x-generation UEFI/QSPI update path가 필요함을 확인했다.
- NVIDIA는 재현 가능한 Jetson AI/CUDA 환경 분리를 위해 Docker 사용 경로를 제공한다.
- 실제 대여 장비의 SKU·RAM·저장장치·firmware와 PyTorch/Ultralytics/container 호환성은 확인하지 않았다. 공식 지원 표는 프로젝트 모델의 동작·성능 증거가 아니다.

### Environment / Verification commands

- 환경: Windows, PowerShell, 기준 작업공간 `00_Development_Github`
- 원격 동기화: `git pull --ff-only`
- 문서 확인: `Get-Content`, `rg`
- 공식 근거: NVIDIA JetPack downloads, Orin Nano quick start, Docker setup
- Git commit: 이 기록을 포함하는 commit

### Next action

1. Increment A의 pure core와 replay 계약을 구현한다.
2. Orin 수령 즉시 SKU·RAM·storage·firmware·JetPack 설치 상태를 기록한다.
3. dataset annotation을 audit한 뒤 detector topology와 JetPack 7.2.1 ML runtime을 고정한다.

## 2026-09-07 - MVP Research Specification 확정

상태: MVP 범위·연구 설계 `DECISION`, 구현·실기기 결과 `PLANNED`

### Goal / Why

- 10월 구현과 11월 ablation·논문 결과가 같은 이벤트 정의와 평가 규칙을 따르도록 MVP 범위를 고정한다.
- 단순 weapon presence가 아니라 person-associated knife event를 다루되, 실제 폭력 의도·행동 판별을 주장하지 않는 경계를 명시한다.

### Scope / Changed files

- `mvp-research-specification.md`를 새로 만들고, README, AGENTS, project plan, architecture, open decisions, verification, research plan을 갱신했다.
- 모델 실행, Jetson 설정, threshold 선택, 촬영, annotation, 성능 측정은 수행하지 않았다.

### Decisions

- MVP weapon class는 `knife`만이다. 추가 class는 stretch다.
- bounding-box geometry 기반 person–knife association, K-of-N temporal confirmation, `CLEAR/CANDIDATE/CONFIRMED/COOLDOWN` 상태 머신을 채택한다.
- `CONFIRMED` 진입은 GPIO LED/Buzzer, event metadata, snapshot 1장을 발생시킨다. event clip은 stretch다.
- controlled scenario와 수동 event annotation을 사용한다. distance는 필수, lighting은 선택이다.
- B0 detection-only, B1 temporal-only, B2 spatial-only, B3 spatial+temporal ablation을 핵심 비교로 채택한다.
- stretch 우선순위는 Orin benchmark, TensorRT/FP16, tracking, dashboard, event clip, 추가 class, enclosure/PCB 순서다.

### Evidence / Limitations

- 사용자와의 프로젝트 방향 논의에서 선택된 MVP 범위를 문서화했다.
- K/N, confidence threshold, normalized-distance threshold, expanded-bbox ratio, cooldown, model/runtime, annotation matching rule, development/test split과 정량 목표는 아직 측정 근거가 없어 확정하지 않았다.
- GPT-6 Astra는 코딩·문서·분석 작업의 보조로 활용하되, 실기기·촬영·하드웨어 검증 일정의 단축 근거로 사용하지 않는다.

### Environment / Verification commands

- 환경: Windows, PowerShell, 기준 작업공간 `00_Development_Github`
- 문서 확인: `Get-Content`, `rg`
- 변경 검증: `git diff --check`, `git status --short`
- Git commit: 이 기록을 포함하는 commit

### Next action

1. Nano hardware와 legacy baseline의 실제 실행 가능성을 진단한다.
2. 첫 controlled scenario 샘플로 annotation matching rule과 tuning/test split을 확정한다.
3. baseline 결과를 근거로 model/runtime·threshold·K/N 후보를 결정한다.

## 2026-09-07 - Master Plan과 장기 기록 체계 정비

상태: 문서 기반 `IMPLEMENTED`, MVP 세부 기능 `PROPOSAL`

### Goal / Why

- 12월 최종 데모·보고서·졸업논문까지 프로젝트 방향과 증거 흐름이 흔들리지 않도록 최상위 계획과 문서 역할을 고정한다.
- 10월 31일을 단순 데모가 아닌 반복 가능한 정량 실험 착수 시점으로 운영한다.

### Scope / Changed files

- `docs/project-plan.md`를 추가하고 README, AGENTS, architecture, open decisions, verification, documentation governance, research plan을 정합화했다.
- 2026-08-27 주제 탐색 회의와 2026-09-01 OT의 공개 가능한 결정 근거를 `meeting-decisions/`에 요약했다.
- 기능 구현, 모델 학습, MVP 확정, Jetson 설정 변경은 수행하지 않았다.

### Decisions and judgment

- 균형형 MVP 후보는 가장 유력하지만 팀 결정 전까지 `PROPOSAL`로 유지한다.
- tracking, movement, dashboard, clip, Orin 비교는 기본적으로 stretch goal로 분리했다.
- 근거 없는 오경보 30% 감소·recall 5%p 이내 같은 예시 수치는 목표로 채택하지 않았다.
- 프로젝트 목적·범위·일정의 기존 기준 역할을 `research-or-product-plan.md`에서 `project-plan.md`로 이전하고, 전자는 연구·실험 보조 문서로 재정의했다.

### Evidence / Limitations

- 2026-08-27 회의록, 2026-09-01 OT 기록, 2026-09-04 회의록과 저장소의 기존 문서를 대조했다.
- Nano 실기기, legacy model, GPIO, 카메라, 성능은 이번 작업에서 실행하거나 측정하지 않았다.

### Environment / Verification commands

- 환경: Windows, PowerShell, 기준 작업공간 `00_Development_Github`
- 문서·상태 검색: `rg`, `Get-Content`
- 변경 검증: `git diff --check`, `git status --short`
- 원격 기준 확인: `git fetch origin`, `git rev-list --left-right --count main...origin/main`
- Git commit: 이 기록을 포함하는 commit

### Next action

1. Nano와 legacy baseline의 실행 가능성을 진단한다.
2. 사건 정답 규칙과 안전한 controlled scenario를 작성한다.
3. 측정 결과와 일정에 근거해 균형형 MVP를 승인 또는 축소한다.

## 2026-09-07 - 기준 개발 작업공간을 Development_Github로 전환

상태: `IMPLEMENTED` (로컬 Git 연결·동기화 정책), 원격 변경 감시 `NOT ADOPTED`

### 변경

- `Development_Github`를 팀의 기준 개발 작업공간으로 지정하고, `edge-threat-response` 원격 `main` 및 기존 Crime_Prediction submodule 기준 commit에 연결했다.
- 작업 시작 시 `git pull --ff-only`, 의도적 commit 후 자동 push를 적용하는 Git hook 정책을 추가했다.
- 원격 변경을 무조건 자동 pull하는 파일 감시는 작업 중인 변경을 덮어쓰거나 충돌을 숨길 수 있어 채택하지 않았다.

### 검증

- 원격 `origin/main`을 fetch하고 mixed reset으로 working tree를 변경하지 않은 채 index·HEAD를 동기화했다.
- `git status --short`가 비어 있고, submodule이 `5e2286971b0e7a54ede4caa3baa03fe168edc5b8`에 있음을 확인했다.

### 한계

- 자동 push는 의도적으로 commit한 변경에만 적용된다. 작업 중이거나 충돌 가능성이 있는 원격 변경은 자동으로 가져오지 않는다.

## 2026-09-04 - 기존 MIDAS 프로젝트 분석과 발전 방향 기록

상태: `VERIFIED` (문서·산출물 검토), `PROPOSAL` (2026-2 발전 방향)

### 배경

- 2025-2 MIDAS 프로젝트는 Jetson Nano, YOLO 기반 흉기 탐지, GPIO LED·부저 경보, WebSocket 기반 웹 UI를 결합한 프로토타입으로 진행되었다.
- 2026-2 종합설계과제(1)에서는 이를 단순 객체 탐지기가 아닌 상황 인지형 엣지 보안 시스템으로 발전시키고자 한다.

### 확인한 기존 산출물

- 최종 발표자료: `N:\Own\01_YU\프로젝트 및 활동\2025-2_MIDAS\2026-1_MIDAS_MSP_발표자료.pdf` (내용상 2025-11-25 최종 발표)
- 활동 정리: `N:\Own\01_YU\프로젝트 및 활동\2025-2_MIDAS\MIDAS_MSP 활동정리.txt`
- Jetson 프로토타입 코드: `N:\Own\01_YU\프로젝트 및 활동\2025-2_MIDAS\jetson\jetson_knife_detector.py`

### 확인된 사실

- 기존 발표자료는 사람/흉기 탐지, Jetson Nano 추론, LED·부저 경보, WebSocket 기반 모니터링 UI를 목표·성과로 제시한다.
- 발표자료에는 Precision 96.2%, Recall 85.1%, mAP50 93.7%가 제시되어 있다. 데이터셋 분할, 평가 조건, 재현 명령은 현재 작업공간에 확보되지 않아 2026-2 기준으로는 재검증이 필요하다.
- 보관된 프로토타입 코드에는 Jetson 환경 제약과 충돌 가능한 import 순서 및 pandas 의존 결과 처리가 남아 있다. 해당 파일만으로 실기기 정상 동작을 보장할 수 없다.
- Jetson Nano의 부팅·팬·카메라·GPIO 현재 상태와 원본 모델·전체 소스는 아직 확인하지 않았다.

### 제안된 변화

- 단일 프레임 탐지 후 즉시 경보하는 구조를 연속 프레임·상태 머신 기반 경보로 변경한다.
- 사람·흉기의 위치 관계, 추적 ID, 이동 방향, 지속 시간으로 위협 점수를 계산한다.
- 경보 이벤트에 전후 영상 클립, 메타데이터, 시스템 자원 로그를 연결한다.
- Nano를 기준 플랫폼으로 복구·측정하고, Orin Nano 확보 시 동일 기준으로 비교한다.

### 검증

- 기존 폴더의 문서, 최종 발표 PDF 17페이지, 중간보고서 PDF 2페이지, Jetson 관련 텍스트·Python 파일을 검토했다.
- 코드 실행, Jetson 부팅, 모델 추론, GPIO, 웹 UI, 성능 수치 재현은 수행하지 않았다.

### 남은 작업

- 기존 원본 코드·모델·설정·의존성의 소재를 확인하고 Git 저장소로 정리한다.
- Jetson Nano 복구 여부와 최소 실행 환경을 실기기에서 확인한다.
- 개발 대상과 확장축을 `open-decisions.md`의 기준으로 확정한다.

## 2026-09-04 - 기존 MIDAS 자산 선별 및 baseline 보존

상태: `IMPLEMENTED` (선별·보존), 실기기 재현 `PLANNED`

### 배경

- 기존 MIDAS 폴더에는 실행 코드, 환경 메모, 발표·행정 문서, 사진, 접근 정보가 혼재되어 있었다.
- 새 공개 Git 저장소에는 재현 가능한 개발 근거만 포함하고, 민감·행정·대용량 자료는 제외해야 한다.

### 변경

- 카메라·YOLO·GPIO 프로토타입, WebSocket 스트리밍 초안, Jetson 환경 정보, 재플래시 가이드, 활동 정리를 `legacy/2025-2-midas/`에 원본 형식으로 보존했다.
- SSH 접근 정보, 모델·영상, 사진, 발표 자료, 행정 문서와 타 프로젝트 후보는 Git에 포함하지 않았다.
- 세부 목록과 예외 사유를 `docs/legacy-asset-selection.md`에 기록했다.

### 검증

- 원본 폴더의 파일 목록과 텍스트 기반 소스·환경 문서를 대조하여, 보존 파일 5개가 민감 접근 정보·모델·영상·행정 문서를 포함하지 않음을 확인했다.
- 보존한 코드는 실행하지 않았다. 현재 Jetson 장비, 모델 파일, 라이브러리 의존성은 미확인이다.

### 남은 작업

- Jetson Nano의 실제 장비 상태와 원본 모델·프로젝트 전체 소스의 추가 소재를 확인한다.
- legacy 코드의 기능을 새 모듈 구조로 이식하기 전, 재현 가능한 baseline 실행 조건을 확정한다.

## 2026-09-04 - Crime_Prediction 원본 저장소 연결

상태: `IMPLEMENTED` (원본 참조 고정), 실행 재현 `PLANNED`

### 배경

- 기존 MIDAS 폴더에는 모델을 호출하는 코드와 환경 메모만 있었으며, 핵심 가중치·데이터셋·학습 코드는 확인되지 않았다.
- `YEOUL0520/Crime_Prediction` 공개 저장소에서 사람·칼 탐지 모델, 학습 데이터셋, 학습 코드, 웹 프로토타입을 확인했다.

### 변경

- 원본 저장소 commit `5e2286971b0e7a54ede4caa3baa03fe168edc5b8`을 `legacy/2025-2-midas/Crime_Prediction` Git submodule로 고정했다.
- 약 460 MB의 원본 데이터셋·모델을 현재 공개 저장소에 중복 복제하지 않았다.

### 검증

- 원본 저장소의 트리와 README, 학습·보조 Python 파일을 확인했다.
- 원본에는 14,760개 파일, 약 460 MB의 데이터가 있으며, `customknife_v1.1.pt`를 포함한 모델 파일이 존재한다.
- 현재 Jetson Nano에서 원본 모델 또는 코드 실행은 수행하지 않았다.

### 남은 작업

- 원본 모델의 클래스·데이터셋 분할·학습 조건·라이선스를 확인한다.
- 원본 학습 스크립트의 API 키처럼 보이는 값을 원본 소유자가 폐기·재발급하도록 요청하고, 새 구현에서는 환경변수로 관리한다.

## 2026-09-04 - 팀 회의 결정 반영

상태: `DECISION`, 일부 외부 의존성 `PLANNED`

### 결정

- 프로젝트 방향을 상황 인지형 Edge AI 기반 흉기 위협 대응 시스템으로 확정했다.
- 팀 공유 기준 저장소로 `edge-threat-response`를 사용한다.
- Orin Nano 대여 요청을 진행하고, 확보 시 Nano와 비교 실험에 활용한다.
- 고성능 카메라와 하드웨어 가속·안정화 장비를 예산 우선 검토 대상으로 정했다.
- 정기 회의는 매주 목요일 18:00이며, MVP 목표 시점은 2026-10-31 이전이다.

### 영향

- 기능별 MVP 완료 기준과 장비 구매 목록을 2026-10-31 시연 목표에 맞춰 분해해야 한다.
- Orin 대여 승인, 정확한 구매 품목, Tracking·Threat Score·Web Dashboard의 MVP 포함 여부는 아직 확정되지 않았다.

### 기록

- 결정사항 요약은 `docs/meeting-decisions/2026-09-04.md`에 남겼다.
- 원본 회의록은 공개 저장소에 넣지 않고 로컬 수업 자료로 유지한다.


## 2026-10-29 - Codex baseline 전체 규칙 호환 적용

- Goal / Why: 사용자 요청에 따라 공통 baseline 전체 작업 규칙을 적용하고 프로젝트별 지침을 유지한다.
- Scope / Changes: AGENTS.md에 upstream 전체 규칙과 기존 문서 역할 매핑을 추가했다. 상태·구조·결정·기록은 기존 project-plan/verification/architecture/open-decisions/development-log를 계속 사용한다. 중복 status/ADR 트리는 만들지 않는다.
- Environment / Commands: 새 Windows 노트북의 로컬 저장소, 적용 전 git pull --ff-only 결과 Already up to date. 전역 search-first/verification-loop는 기존 설치를 재사용한다.
- Verification: 원문 보존, upstream 전체 규칙 포함, 기존 문서 매핑과 git diff --check를 적용 보고서에서 검증한다. 문서·작업 규칙 변경이므로 코드 테스트·실기기 시험은 실행하지 않는다.
- Status: 작업 규칙 IMPLEMENTED; 실제 정적 검증 결과는 별도 적용 보고서에 기록한다. 제품 구현·하드웨어 검증 상태와 측정값은 변경하지 않는다.
- Known limitations: 작업 전부터 있던 수정 파일은 보존한다. OneDrive/MYBOX 경로의 콘텐츠 상태는 별도 문제다.
- Decision impact / Next: 기존 MVP·JetPack·팀 결정·Git 정책 유지. 다음 작업부터 병합된 지침을 사용한다.
- Git commit: 이 항목과 AGENTS.md에 대한 Git 이력으로 추적한다.

## 2026-11-02 - Holoscan 5.0 영상 파이프라인 비교 후속 연구 후보 등록

- **목적/배경:** 사용자의 요청으로 NVIDIA Holoscan 5.0 적용 시 영상 처리 경로의 변화와 실측 성능 차이를 후속 연구 주제로 보존한다. 현재 본 연구 RQ1~RQ3(동일 detector 기반 B0~B3 사건 경보 비교)의 범위·일정·구현 상태는 변경하지 않는다.
- **가설(PROPOSAL):** GPU 내 영상 데이터 전달, operator scheduling, bounded buffering 등을 활용하면 기존 Python 기반 실행 경로보다 end-to-end latency의 p95/지터, 프레임 적체 또는 자원 사용량이 개선될 수 있다. 실측 전 효과를 주장하지 않는다. 정확도 향상은 Holoscan의 고유 효과로 가정하지 않는다.
- **비교 실험 설계:** A=현재 Python/OpenCV+Ultralytics/PyTorch FP32; B=기존 Python 파이프라인+TensorRT FP16; C=Holoscan 5.0+**B와 동일한** TensorRT FP16 person/knife 엔진. A↔B는 주로 추론 엔진/정밀도 변화, B↔C는 실행 프레임워크/데이터 경로 변화의 차이를 평가한다. 엔진·전후처리·출력 규약이 같아야 B↔C 해석이 가능하다. 필요 시 TensorRT FP32를 추가 대조군으로 둔다.
- **통제/지표:** 동일 Orin Nano, 전력·clock·냉각, 모델 weight·input resolution·confidence/IoU, 영상 source, 버퍼·drop 정책을 가능한 한 일치시킨다. stage latency(decode/capture, preprocess, inference, postprocess, decision/action), end-to-end mean/p50/p95·지터, 유효 FPS, dropped/stale frames, CPU/GPU 부하, RAM/RSS growth, 온도/전력(계측 가능 시), canonical detection 및 B0~B3 event 동등성을 기록한다. 재현 가능한 고정 영상과 실제 카메라 workload를 구별한다. TensorRT FP16 정밀도 변화가 detection에 영향을 주면 별도로 보고한다.
- **현 기준선:** 2026-10-27 Orin 25W/L4T39.2.0 파일 반복 시험은 600초/7,375 frame/12.2899 file FPS, inference mean79.0926ms/p95 85.0422ms, RSS 증가 약215.70MiB다. 이는 train 이미지 조합 파일 반복이고 camera FPS/실제 event benchmark가 아니다. [측정 근거](../reports/runtime/orin-readiness-2026-10-27/report.md).
- **착수 gate/위험:** MVP의 camera/GPIO·실제 사건 평가 및 별도 TensorRT-only baseline을 먼저 완료한다. SDK 5.0과 실제 L4T39.2.0/JetPack·TensorRT·카메라 어댑터 호환성은 공식 요구사항 및 격리 smoke로 확인해야 한다. 환경 재설치/OS 변경이나 main runtime 전면 교체는 승인하지 않았다. 8GB 메모리·추가 개발 비용·비교 조건 불일치 위험을 고려한다.
- **범위/변경/검증:** 문서상 후속 연구 후보만 추가한다(`docs/project-plan.md`, `docs/open-decisions.md`, 이 로그). Holoscan 설치·코드 변경·Jetson 재시험 없음. 문서의 기존 RQ/MVP/Stretch 상태와 모순이 없는지 확인하며 GitHub 커밋으로 추적한다.
- **상태/다음:** `PROPOSAL`/P2. 기존 시스템과 TensorRT-only 측정 후 연구 착수/보류를 결정한다.
