# Documentation Governance

## 목적

이 문서는 현재 무엇이 사실인지, 어떤 선택이 왜 이루어졌는지, 무엇이 아직 검증되지 않았는지를 빠르게 복원하기 위한 운영 규칙이다.

## 상태 용어

| 상태 | 의미 |
|---|---|
| `PROPOSAL` | 검토 중인 추천안이며 확정되지 않음 |
| `DECISION` | 이후 작업의 기준으로 선택됨 |
| `PLANNED` | 확정됐지만 구현되지 않음 |
| `IMPLEMENTED` | 코드·설정·문서에 반영됨 |
| `VERIFIED` | 명시된 환경과 방법으로 실제 확인됨 |
| `BLOCKED` | 장비·권한·외부 정보 등으로 진행 불가 |
| `DEFERRED` | 의도적으로 후순위로 이동 |
| `SUPERSEDED` | 이후 기록으로 대체됨 |

`IMPLEMENTED`는 `VERIFIED`를 의미하지 않는다. 예를 들어 로컬 테스트 통과와 Jetson 실기기 시험 통과는 별도 증거로 기록한다.

## 문서 역할

| 문서 | 역할 | 갱신 시점 |
|---|---|---|
| `README.md` | 목적, 실행법, 현재 상태의 진입점 | 핵심 상태 변경 시 |
| `project-plan.md` | 목적, 범위, 일정, 성공 조건의 최상위 기준 | 방향·범위·일정 변경 시 |
| `development-log.md` | 변경·결정·검증·한계의 시간순 기록 | material task 종료 전 |
| `open-decisions.md` | 미확정 선택과 결정 기준 | 선택지가 생기거나 확정될 때 |
| `architecture.md` | 현재 시스템 경계와 계약 | 구조·통신·저장 경계 변경 시 |
| `verification.md` | 요구사항별 검증 계획과 증거 | 테스트 계획·결과 변경 시 |
| `research-or-product-plan.md` | 연구 가설, 실험 변수·시나리오·분석의 보조 계획 | MVP·실험 설계 변경 시 |

## Source-of-truth hierarchy

충돌이 있으면 실제 구현·검증 증거, 최신 명시적 결정, 과거 제안 순으로 해석한다. 문서 역할의 우선순위는 `project-plan → open-decisions → architecture → verification → development-log/meeting evidence`이며, README는 이 문서들의 현재 진입점이다. `PROPOSAL`은 구현 의무나 확정 사실로 해석하지 않는다.

## 기록 규칙

- 기존 기록을 조용히 수정하지 않는다. 결정이 바뀌면 새 기록에서 이전 항목을 `SUPERSEDED`로 연결한다.
- 코드·공개 동작·데이터 경계·연구 지표·플랫폼 지원·중요 후보가 바뀌면 같은 작업에서 기록한다.
- 수치에는 측정 환경, 입력 조건, 명령 또는 방법, 날짜를 함께 남긴다.
- 비밀번호, API 키, 개인식별정보, 원본 민감 데이터, 인증서·서명정보는 기록하거나 커밋하지 않는다.
- 실제 수집 전에는 얼굴·영상·위치 등 민감 데이터의 수집 목적, 보존 기간, 접근 권한, 동의·심의 필요성을 문서화한다.

## 작업 카드

```markdown
## 작업: <짧은 이름>

- 목적: <사용자·시스템 관점의 결과>
- 범위: <변경하는 것과 변경하지 않는 경계>
- 완료 기준: <테스트·벤치마크·실기기 검증·문서 증거>
- 위험: <호환성·성능·데이터·안전 위험>
- 문서 영향: <갱신 대상>
```

## Material task record

개발 로그에는 최소 다음을 남긴다.

```text
Date / Goal / Why / Scope / Changed files
Environment / Commands / Result / Verification
Measured values / Known limitations / Decision impact
Next action / Git commit
```

논문·최종보고서에 쓰일 실험은 다음을 추가한다.

```text
Experiment ID / Hypothesis
Independent variable / Controlled variables
Input or dataset / Hardware / Software and model version
Threshold and configuration / Raw result location
Summary metrics / Interpretation / Limitations
```

## Weekly report reuse

- OT 요구에 따라 주간보고서는 최신 주차를 앞에 두는 누적형으로 관리한다.
- 개발 로그와 검증 문서를 1차 근거로 사용하고, 보고서에는 요약·결정·증거 식별자만 옮긴다.
- 팀 사진·원본 영상·개인정보는 공개 저장소에 넣지 않는다. LMS 제출본 또는 통제된 로컬 자료의 위치만 기록한다.
- 주간보고서 작성 때문에 이미 남긴 기술 기록을 다시 복원하지 않도록, material task 종료 시 같은 주에 재사용할 요약을 남긴다.

## Experiment evidence

- 실험마다 고유 ID를 부여하고 고정 Git commit과 config를 연결한다.
- raw result와 민감·대용량 자료는 Git 외부에 보관하고, 저장 위치·checksum 또는 식별자만 기록한다.
- 요약표·그래프가 raw result에서 어떻게 생성됐는지 명령이나 script 버전을 남긴다.
- 재실행으로 값이 바뀌면 기존 결과를 덮어쓰지 않고 run ID로 분리한다.
