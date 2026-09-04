# Project Instructions

## Scope

이 저장소는 Jetson 기반 상황 인지형 흉기 위협 대응 시스템을 개발한다. 기존 프로젝트의 자료나 발표 내용은 참고 근거일 뿐, 현재 구현·검증 상태를 자동으로 증명하지 않는다.

## Engineering rules

- 기능 변경 전 관련 코드와 `README.md`, `docs/open-decisions.md`, `docs/development-log.md`를 읽는다.
- 큰 작업은 구현 전 작업 카드(목적, 범위, 완료 기준, 위험, 문서 영향)를 제시한다.
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
