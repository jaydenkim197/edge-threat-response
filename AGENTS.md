# Project Instructions

## Scope

이 저장소는 Jetson 기반 상황 인지형 흉기 위협 대응 시스템을 개발한다. 기존 프로젝트의 자료나 발표 내용은 참고 근거일 뿐, 현재 구현·검증 상태를 자동으로 증명하지 않는다.

## Engineering rules

- 기준 개발 작업공간은 `00_Development_Github`이다. 작업 시작 전 `git pull --ff-only`를 실행하고, 완료·검증된 의도적 변경은 commit 후 원격 `main`까지 push한다.
- material task 시작 전 `docs/project-plan.md`, `docs/open-decisions.md`, `docs/architecture.md`, `docs/verification.md`, `docs/development-log.md`와 관련 코드를 확인한다.
- 큰 작업은 구현 전 작업 카드(목적, 범위, 완료 기준, 위험, 문서 영향)를 제시한다.
- 프로젝트 방향·일정·평가 가능성과 충돌하는 요청은 충돌을 먼저 명시하고 범위를 조정한다.
- `PROPOSAL`을 팀 결정 없이 `DECISION`으로 바꾸지 않는다.
- Orin Nano 확보를 전제로 핵심 경로를 설계하지 않는다.
- 논문 평가 방법이 없거나 10월 31일 동결을 위협하는 기능을 핵심 범위에 임의로 추가하지 않는다.
- 기존 MIDAS 결과를 신규 시스템의 검증 결과처럼 사용하지 않는다.
- Jetson 의존 코드(camera, GPIO, TensorRT, tegrastats)는 PC에서 검증 가능한 순수 로직과 인터페이스로 분리한다.
- 측정하지 않은 정확도, FPS, 지연시간, 전력, 온도, 안정성 수치를 만들거나 추정값처럼 기록하지 않는다.
- 실기기 검증과 개발 PC/영상 파일 검증을 구분한다.
- 비밀값, API 키, 개인식별정보, 원본 민감 영상·음성은 코드·문서·커밋에 넣지 않는다.

## Material-change completion protocol

작업 완료 전 다음을 수행한다.

1. 관련 문서를 갱신한다: `development-log`, `open-decisions`, `architecture`, `verification`, README.
2. `IMPLEMENTED`, `VERIFIED`, `PLANNED`, `BLOCKED` 상태를 정확히 구분한다.
3. 가능한 비파괴적 검증을 실행하고 환경·명령·결과·한계를 기록한다.
4. `git diff --check`, `git status`로 변경 범위를 확인한다.
5. 최종 보고에 결과, 검증, 알려진 한계, 다음 작업을 짧게 제시한다.

## Required task record

material task에는 날짜, 목적, 이유, 범위, 변경 파일, 환경·명령, 결과, 검증, 측정값, 한계, 결정 영향, 다음 작업, Git commit을 남긴다. 논문용 실험은 가설, 독립·통제 변수, 입력·데이터셋, 하드웨어·소프트웨어·모델 버전, threshold·설정, 원시 결과 위치, 지표, 해석과 한계를 추가한다.
