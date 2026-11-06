# 검수 미완료 배정 회수·15분 미활동 만료 — 2026-11-06

**방치된 미완료 배정 8개를 해제하고 15분 미활동 자동 회수 기능을 PC13에 배포했다. 기존 판정 2,673개와 version/history·완료 소유권·계정·배치 registry는 보존했다.** 검수 자료는 3,625개이며 새로운 질문·판정·학습 자료를 추가하지 않았다.

## 문제와 초기 회수

기존에는 사진을 여는 순간 배정했지만 이탈·미활동 시 반납하지 않았고 배정 시각도 없었다. 다른 팀원은 미완료 사진을 받을 수 없어 전체 검수 수량이 한두 장씩 남았다. 사용자가 기존 판정 보존과 방치 배정 회수를 승인했다.

| Source | 해제한 미완료 배정 |
|---|---:|
| SOHAS | 1 |
| Simuletic | 1 |
| US Mock | 1 |
| Catargiu | 3 |
| Simuletic ATM | 2 |
| 합계 | **8** |

운영 서비스를 정지한 뒤 DB/config consistent backup을 만들고, 실제 미완료 ID·소유자를 다시 대조했다. 기존 활동 timestamp가 없으므로 초기 대상 선정에는 소유자의 가장 최근 저장 판정 시각을 보수적 대리 정보로 사용했다. 최근15분 내 저장 활동이 있는 미완료 소유자는 제외하도록 했으며 이번 대상8개는 모두 해당하지 않았다. 미저장 화면의 과거 클릭·읽기 활동을 복원한 것은 아니다. 사용자 승인된 초기 회수이며 판정을 삭제하거나 완성한 것으로 처리하지 않았다.

회수 후 assignments 전체는 정확히 기존 행에서 위8개만 뺀 집합이다. 다른 모든 기존 테이블의 행 수/hash와 각 source의 준비·판정·보류·history 집계가 전후 동일했다. 신규 운영 판정0, 계정/config 변경0이다.

## 재발 방지 구현

- 코드 commit: `8a6ed6cad2b840304ff80778de013f4d12184acd`. 새 의존성 없이 기존 SQLite·ReviewStore·version 검사·localStorage draft를 재사용했다.
- 기존3열 `assignments`는 유지하고 `assignment_activity(pack,sample,user,last_seen)`를 별도 추가했다. 기존 배정은 새 metadata가 없을 때 migration 시 grace period를 받는다. 이미 저장한 사진의 소유권·수정 기능은 시간으로 회수하지 않는다.
- 화면이 보이고 새 pointer/keyboard/input/scroll 활동이 있을 때만30초마다 heartbeat를 보낸다. 단순 GET·목록 polling은 활동 갱신이 아니다. 화면을 나가거나 닫으면 활동 전송이 멈춘다.
- 서버 마지막 활동 수신 후900초가 지나고 아직 version0인 배정만 회수한다. 서비스 worker가60초마다 확인하며 catalog/items/claim/save/heartbeat 요청 시에도 검사한다. 활동전송·정기검사 간격 때문에 실제 회수 시각에는 짧은 간격 차이가 있다.
- 저장과 배정은 같은 Team DB `BEGIN IMMEDIATE` 소유권 잠금을 잡는다. 저장은 ReviewStore commit까지 잠금을 유지해 회수/다른 claim과의 경합을 막는다. 기존 review version 충돌 검사는 유지한다.
- 만료되거나 다른 사용자에게 넘어간 사진의 옛 화면 저장을 거부한다. 미완성 localStorage draft는 지우지 않는다. 같은 ID가 다시 본인에게 배정되고 저장version이 같으면 복원할 수 있다. 다른 사람이 저장한 최신 판정으로 자동 덮어쓰지 않는다.
- 모바일 하단 버튼은 만료·읽기전용일 때 **다음 미검수 받기**로 동작한다. UI QA 중 기존 desktop 다음 버튼이 mobile에서 숨겨지고 하단 버튼까지 비활성화되는 문제를 재현해 같이 수정했다. 마지막 이미지에서도 새 배정을 요청할 수 있다.
- 남은 사진이 실제로 다른 사람에게 배정 중인 경우 완료라고 표시하지 않고15분 미활동 회수 조건을 설명한다. 질문 두 개와 이름 선택은 그대로다.

## 검증

1. PC13 Python3.12.4의 별도 frozen archive+변경 overlay에서 `test_team_review.py` **20개 통과**. 새 회귀7개는 만료 후 타인 재배정/옛 소유자 쓰기 거부, 타인 claim 전의 만료 저장 거부, heartbeat 갱신과 GET 비갱신, 완료 판정/history 보존, 기존3열 schema migration, catalog 회수/활성 배정 메시지, 실제 두 thread의 save/claim 직렬화를 확인한다. Sleep 대신 DB timestamp를900초 이전으로 조정했다.
2. 전체 **193 tests 실행 OK, 2개 skip**. JS `node --check` 통과. 마지막 UI 보완 이후 Python은 바뀌지 않았고 최종 JS syntax와 browser 검증을 다시 실행했다.
3. 운영 DB의 별도 consistent 복제본 QA에서 Edge Chromium Pixel7/iPhone13 viewport의 만료·재배정·옛 저장 차단·draft 보존·재배정 후 복원/저장·기존 판정 불변·마지막 사진의 하단 다음 버튼을 통과했다. Android에서는 실제30초 interval heartbeat HTTP200도 관찰했다. iPhone 크기 검증 역시 Chromium이며 실제 Safari/실물 폰 검증은 아니다. 새 질문0·가로 overflow0이다.
4. 운영 배포는 ff-only update→consistent backup→additive metadata migration→초기8개만 반납→전후 보존 검사→actual-config admin/catalog/batch image smoke→task 재시작 순서다. 저장 판정2,673개·준비3,625개·메뉴9개를 유지했다.
5. 공개 [검수 사이트](https://pc13.tail37c267.ts.net/)에서도 두 viewport의 이름 선택·900초 정책 응답·공통 두 질문·정렬·old/new 이미지 HTTP200·가로 overflow0을 확인했다. Claim/review/heartbeat를 browser에서 차단하거나 대체해 운영 QA 판정/배정을 남기지 않았다.

## 증거·운영 안내

PC13 ignored `data/review/assignment-timeout-20261106-v1/`에 `before-deploy-backup/`, `released-assignment-rows.json`, `preservation.json`, `after-migration.json`, `browser-qa-result.json`, `public-check-result.json`, `deploy.ps1`을 보관한다. 초기 회수 script는 `data/review/assignment-timeout-operations-20261106.py`, 가상 시각/QA route는 격리된 QA script에만 있다. QA route는 제품 코드에 포함되지 않는다. Full test raw는 `data/work/assignment-timeout-qa-20261106/full-tests.log`, script/hash·개인정보 없는 집계는 [aggregate](aggregate.json)를 따른다.

팀원은 한 번 새로고침하고 검수하면 된다. 배포 전 열린 탭에는 heartbeat가 없으므로 새 코드를 불러와야 한다. 브라우저 저장 공간을 지우면 미저장 draft는 복구할 수 없지만 서버에 저장된 판정은 보존된다. 기능 검증이 새 source/label의 품질·학습 승인이나 실제15분 대기의 실물 폰 실험을 뜻하지 않는다. QA 서버·터널을 정리했고 운영 task Running을 확인했다.
