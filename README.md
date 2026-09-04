# Context-Aware Edge Threat Detection System

> 2026-2 종합설계과제(1) - 기존 Jetson Nano 기반 흉기 탐지 프로젝트의 고도화

## 프로젝트 목적

기존의 단일 프레임 기반 흉기 탐지·GPIO 경보 프로토타입을, **상황 인지형 엣지 위협 대응 시스템**으로 발전시킨다. 시스템은 사람·흉기 탐지, 객체 추적, 시간·공간 문맥 기반 위협 판단, 단계별 경보, 사건 기록 및 성능 검증을 목표로 한다.

## 현재 상태

- 상태: `PROPOSAL` / 초기 기획 및 기존 산출물 분석 완료
- 기존 산출물: 2025-2 MIDAS 발표자료, 활동 정리, Jetson Nano 프로토타입 코드
- 구현 저장소: 아직 구성되지 않음
- Jetson Nano 실기기: 정상 부팅·카메라·GPIO 상태를 재확인해야 함
- 성능 수치: 기존 발표자료의 수치는 참고용이며, 이번 프로젝트 기준의 재측정은 아직 수행하지 않음

## 목표 시스템

```text
Camera
  -> Person/Weapon Detector
  -> Object Tracker
  -> Situation & Threat Analyzer
  -> Alert State Machine
  -> GPIO Alarm / Event Clip / Event Log / Dashboard
```

자세한 구조와 데이터 경계는 [docs/architecture.md](docs/architecture.md)를, 후보와 결정 기준은 [docs/open-decisions.md](docs/open-decisions.md)를 참조한다.

## 문서 안내

- [개발 기록](docs/development-log.md): 시간순 변경·결정·검증·한계
- [연구·제품 계획](docs/research-or-product-plan.md): 문제 정의, 범위, 후보, 평가 계획
- [미결정 사항](docs/open-decisions.md): 확정 전 선택지와 판단 기준
- [아키텍처](docs/architecture.md): 현재 목표 구조와 책임 경계
- [검증 매트릭스](docs/verification.md): 요구사항별 증거와 미검증 항목
- [문서화 운영 규칙](docs/documentation-governance.md): 기록·상태·보안 규칙

## Non-goals (현재 단계)

- 단순히 YOLO 버전만 교체하는 작업
- 고비용 클라우드 의존형 상시 영상 업로드
- 검증 없이 위협 상황을 정확히 판별한다고 주장하는 것
- 민감 영상·개인식별정보를 무분별하게 수집하거나 저장하는 것

## 작업 시작 규칙

각 material task는 목표, 범위, 완료 기준, 위험, 문서 영향을 먼저 정의한다. 구현 후에는 관련 코드·테스트·문서를 함께 갱신하고, 실제 실행한 검증과 한계만 기록한다.
