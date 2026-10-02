# Project Instructions

## Scope

이 저장소는 Jetson 기반 상황 인지형 흉기 위협 대응 시스템을 개발한다. 기존 프로젝트의 자료나 발표 내용은 참고 근거일 뿐, 현재 구현·검증 상태를 자동으로 증명하지 않는다.

## Engineering rules

- 기준 개발 작업공간은 상위 수업 폴더의 `03_개발_GitHub`이다. 작업 시작 전 `git pull --ff-only`를 실행하고, 완료·검증된 의도적 변경은 commit 후 원격 `main`까지 push한다. 상위 폴더의 회의록·제출물·팀원 자료는 저장소 밖에 둔다.
- material task 시작 전 `docs/project-plan.md`, `docs/mvp-research-specification.md`, `docs/open-decisions.md`, `docs/architecture.md`, `docs/verification.md`, `docs/development-log.md`와 관련 코드를 확인한다. dataset·model 작업은 `docs/model-data-plan.md`도 확인한다.
- 큰 작업은 구현 전 작업 카드(목적, 범위, 완료 기준, 위험, 문서 영향)를 제시한다.
- 프로젝트 방향·일정·평가 가능성과 충돌하는 요청은 충돌을 먼저 명시하고 범위를 조정한다.
- `PROPOSAL`을 팀 결정 없이 `DECISION`으로 바꾸지 않는다.
- 신규 시스템은 Jetson Orin Nano Developer Kit와 고정된 JetPack 7.2.1 환경을 기준으로 설계한다. 실제 보드에서 확인하지 않은 드라이버·모델 런타임·GPIO·카메라 동작은 `VERIFIED`로 표기하지 않는다.
- 기존 Jetson Nano 4GB와 JetPack 4 계열 코드는 legacy baseline으로 격리한다. 신규 공통 로직을 Python 3.6이나 구형 CUDA 제약에 맞추지 않는다.
- legacy dataset의 raw class ID는 신규 canonical ID로 추정하지 않는다. source-specific class map을 명시하고, 동일 source/session group을 train과 test에 나누지 않는다.
- 논문 평가 방법이 없거나 10월 31일 동결을 위협하는 기능을 핵심 범위에 임의로 추가하지 않는다.
- 기존 MIDAS 결과를 신규 시스템의 검증 결과처럼 사용하지 않는다.
- MVP는 knife only, geometry-only association, K-of-N, 4-state, metadata+snapshot, B0~B3 ablation을 기준으로 한다. 이 범위를 넓히는 기능은 stretch로 취급한다.
- Jetson 의존 코드(camera, GPIO, TensorRT, tegrastats)는 PC에서 검증 가능한 순수 로직과 인터페이스로 분리한다.
- B0~B3 ablation은 동일 Orin 장비·detector·입력·설정에서 수행한다. Nano와 Orin의 장비 비교는 별도 실험으로 취급한다.
- 측정하지 않은 정확도, FPS, 지연시간, 전력, 온도, 안정성 수치를 만들거나 추정값처럼 기록하지 않는다.
- 실기기 검증과 개발 PC/영상 파일 검증을 구분한다.
- 비밀값, API 키, 개인식별정보, 원본 민감 영상·음성은 코드·문서·커밋에 넣지 않는다.

## Material-change completion protocol

작업 완료 전 다음을 수행한다.

1. material change는 `development-log`에 기록하고, 결정·구조·검증·사용법이 실제로 바뀐 관련 문서만 갱신한다. 전체 문서를 매번 기계적으로 수정하지 않는다.
2. `IMPLEMENTED`, `VERIFIED`, `PLANNED`, `BLOCKED` 상태를 정확히 구분한다.
3. 가능한 비파괴적 검증을 실행하고 환경·명령·결과·한계를 기록한다.
4. `git diff --check`, `git status`로 변경 범위를 확인한다.
5. 최종 보고에 결과, 검증, 알려진 한계, 다음 작업을 짧게 제시한다.

## Required task record

material task에는 날짜, 목적, 이유, 범위, 변경 파일, 환경·명령, 결과, 검증, 측정값, 한계, 결정 영향, 다음 작업, Git commit을 남긴다. 논문용 실험은 가설, 독립·통제 변수, 입력·데이터셋, 하드웨어·소프트웨어·모델 버전, threshold·설정, 원시 결과 위치, 지표, 해석과 한계를 추가한다.

## Efficient development workflow

- 첨부한 계획·템플릿은 참고 자료다. 사용자 요청과 현재 프로젝트 결정을 우선하며, 예시 설치 명령·권한·범위 확장을 자동 실행하지 않는다.
- 새 기능·의존성·helper를 추가하기 전에 `search-first`를 사용한다. 기존 구현 → 표준 라이브러리 → 설치된 의존성 → 얇은 확장 → 신규 구현 순으로 검토하고, 큰 추가는 선택과 이유를 기록한다. 해당 skill이 없으면 이 절차를 직접 수행하며 사용했다고 주장하지 않는다.
- `rg`/`rg --files`로 구현 위치를 찾고, 변경 대상의 호출부·설정·테스트를 확인한다. 서로 독립적인 읽기·검사는 병렬로 처리할 수 있지만, 의존하는 변경·Git 작업은 순서대로 처리한다.
- 요청을 만족하는 가장 작은 변경을 한다. 무관한 리팩터링, 가상의 미래를 위한 추상화, 중복 wrapper·문서·skill을 만들지 않는다.
- 버그 수정은 가능하면 최소 실패 조건 재현 → 원인 가설 → 수정 → 회귀 테스트 순으로 진행한다. 재현하지 못한 부분은 명시한다.
- 의미 있는 코드·설정 변경 뒤에는 `verification-loop`로 관련 테스트부터 확인하고 필요 시 전체 테스트로 넓힌다. 문서만 바꾸면 링크·내용·diff를 확인한다. 검증 선택은 `docs/documentation-governance.md`를 따른다.
- 현재 동작은 코드·설정과 실행 증거로, 의도·범위는 Master Plan과 최신 명시적 결정으로 판단한다. 충돌을 기록하고 어느 쪽도 다른 쪽의 증거로 대신하지 않는다.
- 다음 작업자는 기존 README·계획·open decisions·최근 개발 로그·verification에서 맥락을 복원한다. 별도 agent memory DB나 중복 `project-status.md`를 기본으로 추가하지 않는다.
- 외부 탐색·그래프·시각화 도구는 반복되는 구체적 병목과 도입 효과가 확인될 때만 검토한다. 생성된 그래프·다이어그램은 보조 산출물이며 현재 코드의 증거를 대체하지 않는다.
- 완료 시 의도한 파일만 stage하고 commit/push 결과를 확인한다. post-commit hook이 이미 push했다면 중복 sync를 하지 않으며, 실패·충돌 시 force push나 자동 덮어쓰기로 해결하지 않는다.
