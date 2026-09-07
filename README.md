# Context-Aware Edge Threat Detection System

> 2026-2 종합설계과제(1) - 기존 Jetson Nano 기반 흉기 탐지 프로젝트의 고도화

## 프로젝트 목적

기존의 단일 프레임 기반 흉기 탐지·GPIO 경보 프로토타입을, **상황 인지형 엣지 위협 대응 시스템**으로 발전시킨다. MVP는 `Person-Associated Knife Event`를 bounding-box 공간 연관성과 K-of-N 시간 조건으로 확인하고, 단계별 경보·사건 기록·성능 검증을 수행한다.

## 현재 상태

- 상태: 프로젝트 방향·MVP 연구 범위 `DECISION`, 구현·실기기 검증 `PLANNED`
- 기존 산출물: 2025-2 MIDAS 발표자료, 활동 정리, Jetson Nano 프로토타입 코드
- 구현 저장소: 구성 완료, legacy 전체 소스는 Git submodule로 고정
- Jetson Nano 실기기: 정상 부팅·카메라·GPIO 상태를 재확인해야 함
- 성능 수치: 기존 발표자료의 수치는 참고용이며, 이번 프로젝트 기준의 재측정은 아직 수행하지 않음
- 일정 원칙: 2026-10-31까지 정량 실험을 시작할 수 있는 통합·반복 실행 상태 확보

## 목표 시스템

```text
Camera
  -> Person/Weapon Detector
  -> Person–Knife Spatial Association + K-of-N Temporal Confirmation
  -> CLEAR / CANDIDATE / CONFIRMED / COOLDOWN
  -> GPIO Alarm + Event Metadata + Snapshot
```

자세한 구조와 데이터 경계는 [docs/architecture.md](docs/architecture.md)를, 후보와 결정 기준은 [docs/open-decisions.md](docs/open-decisions.md)를 참조한다.

## 문서 안내

- [Master Project Plan](docs/project-plan.md): 목적, 범위, 일정, 성공 조건의 최상위 기준
- [MVP Research Specification](docs/mvp-research-specification.md): 이벤트 정의, 상태·평가·시나리오의 구현 기준
- [개발 기록](docs/development-log.md): 시간순 변경·결정·검증·한계
- [연구·실험 계획](docs/research-or-product-plan.md): 가설과 비교 실험의 보조 계획
- [미결정 사항](docs/open-decisions.md): 확정 전 선택지와 판단 기준
- [아키텍처](docs/architecture.md): 현재 목표 구조와 책임 경계
- [검증 매트릭스](docs/verification.md): 요구사항별 증거와 미검증 항목
- [문서화 운영 규칙](docs/documentation-governance.md): 기록·상태·보안 규칙
- [회의·수업 결정 근거](docs/meeting-decisions/): 주제 선정과 일정 제약의 요약 기록
- [기존 MIDAS 자산 선별 기록](docs/legacy-asset-selection.md): 가져온 baseline과 제외 근거

## Legacy source checkout

2025-2의 전체 모델·데이터셋·학습 소스는 용량과 원본 보존을 위해 Git submodule로 연결한다. 처음 clone할 때는 다음 명령을 사용한다.

```bash
git clone --recurse-submodules https://github.com/jaydenkim197/edge-threat-response.git
```

이미 clone한 경우에는 `git submodule update --init --recursive`를 실행한다. submodule 내부의 legacy 코드와 모델은 신규 시스템 코드로 직접 수정하지 않는다.

## Non-goals (현재 단계)

- 단순히 YOLO 버전만 교체하는 작업
- 고비용 클라우드 의존형 상시 영상 업로드
- 검증 없이 위협 상황을 정확히 판별한다고 주장하는 것
- 민감 영상·개인식별정보를 무분별하게 수집하거나 저장하는 것

## 작업 시작 규칙

각 material task는 목표, 범위, 완료 기준, 위험, 문서 영향을 먼저 정의한다. 구현 후에는 관련 코드·테스트·문서를 함께 갱신하고, 실제 실행한 검증과 한계만 기록한다.

## 개발 작업공간 및 GitHub 동기화

이 저장소의 기준 작업공간은 `00_Development_Github`이다. 다른 상위 수업 폴더의 복사본은 개발 기준으로 사용하지 않는다.

- 작업 시작 전 `git pull --ff-only`로 원격 `main`을 안전하게 반영한다. fast-forward가 불가능하면 임의로 병합하지 않고 원인을 확인한다.
- 의도한 변경만 검토·stage하여 커밋한다. 이 작업공간에서는 commit 직후 `origin/main`으로 자동 push되도록 Git hook을 설정했다.
- GitHub의 변경을 감시하여 무조건 자동 pull하는 방식은 사용하지 않는다. 작업 중인 파일을 덮어쓰거나 충돌을 숨길 수 있기 때문이다.
- 새 clone에서는 `git submodule update --init --recursive` 후 `git config core.hooksPath .githooks`를 한 번 실행해 같은 자동-push 정책을 적용한다.
