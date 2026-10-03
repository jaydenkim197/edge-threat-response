# 통제 촬영표 · 작성용

이 파일을 `data/experiments/<experiment-id>/`에 복사해 채운다. 실명·원본 영상은 Git에 올리지 않는다.

## 세션 등록 (촬영 전에 작성)

| 항목 | 기록 |
|---|---|
| experiment / session / leakage_group ID | |
| partition | pilot / tuning / final_test 중 하나; T1 학습용이면 별도 train |
| 촬영 날짜·장소 ID·참여자 별칭 | |
| 촬영/정답 담당자 별칭, 동의·접근/보존 정책 기록 위치 | |
| camera/model, 원본 해상도·FPS 또는 VFR, 화각/설정 | |
| 카메라 높이·관찰 각도·바닥 기준점 | |
| Near / Medium / Far 실제 바닥 거리(m) | 미확정 — 첫 pilot 후 기록 |
| lighting / 노출 설정 | Normal 기본 / Low-light 선택 |
| 동일 세션 또는 원본에서 파생한 다른 clip 목록 | |

## 촬영 체크표

숫자를 채우기 전에는 반복 횟수 승인이 아니다. 각 칸에 recording ID와 실제 반복 번호를 기록한다.

| 유형 | Near | Medium | Far | 메모 |
|---|---|---|---|---|
| P1 정지 소지 | | | | |
| P2 이동 소지 | | | | |
| P3 집기/내려놓기 | | | | |
| P4 가림/두 사람 | | | | 두 사람 여부를 분리 태그 |
| N1 knife만 놓임 | | | | 사건 0 |
| N2 근처 통과 | | | | 집지 않으면 사건 0 |
| N3 옆에 정지 | | | | 집지 않으면 사건 0 |
| N4 유사 소품 | | | | 소품 종류 |
| N5 일시 누락 내성 | | | | positive 사건은 유지 |

## Recording와 정답 경계

| recording ID / source ID | 원본 위치·SHA-256 | 관찰 start/end(s) | scenario·거리·조도 | 사건 ID / start_frame / end_frame / start_s / end_s | 경계 확인·모호 구간 |
|---|---|---|---|---|---|
| | | | | negative면 사건 없음 | |

Frame은 0-based 포함 구간, 시간은 [start,end). 원본 decode timestamp로 연결한다. negative도 영상 길이를 기록한다. detector output은 수동 정답을 대신하지 않는다.

## 첫 pilot 후 동결할 값

| 항목 | 확정값·근거·확인 날짜 |
|---|---|
| 거리 구간·반복 횟수 | |
| 가림·극소 객체·경계/모호 구간 판정 규칙과 annotation version | |
| matching policy ID / early·late tolerance / 설정 hash | |
| tuning / final-test session·leakage group 목록과 목록 hash | |
| 최종 weight SHA-256 / detector config·input 해상도/샘플링 | |
| confidence / α / K,N / rearm / pipeline config SHA-256 | |
| evaluation 코드 commit·실행 명령 | |
| 동결 확인자 별칭·날짜, 결과 보관 경로 | |
