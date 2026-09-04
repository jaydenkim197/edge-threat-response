# Legacy Asset Selection - 2025-2 MIDAS

기록일: 2026-09-04  
원본 위치: `N:\Own\01_YU\프로젝트 및 활동\2025-2_MIDAS`

## 포함한 자산

아래 파일은 이번 프로젝트에서 기존 구현을 재현·분석하거나 설계 근거를 복원하는 데 직접 필요해 `legacy/2025-2-midas/`에 원본 형식으로 보존했다. 이 파일들은 현재 시스템의 실행 보증이 아니라 **legacy baseline**이다.

| 원본 파일 | 저장 경로 | 포함 이유 | 상태 |
|---|---|---|---|
| `jetson/jetson_knife_detector.py` | `legacy/2025-2-midas/jetson/jetson_knife_detector.py` | 카메라·YOLO·GPIO 경보의 최소 프로토타입 | `IMPLEMENTED` (보존), 실행 재현 `PLANNED` |
| `jetson/효정 코드.txt` | `legacy/2025-2-midas/jetson/효정 코드.txt` | FastAPI/WebSocket 다중 카메라 스트리밍 초안 | `IMPLEMENTED` (보존), 실행 재현 `PLANNED` |
| `jetson/Jetson_개발정보.txt` | `legacy/2025-2-midas/jetson/Jetson_개발정보.txt` | JetPack, Python, PyTorch, OpenCV와 호환성 제약 | `IMPLEMENTED` (보존), 실기기 재확인 `PLANNED` |
| `jetson/Jetson_nano_flash_reset_guide.txt` | `legacy/2025-2-midas/jetson/Jetson_nano_flash_reset_guide.txt` | Nano 복구 절차의 출발점 | `IMPLEMENTED` (보존), 보드·이미지 호환성 확인 `PLANNED` |
| `MIDAS_MSP 활동정리.txt` | `legacy/2025-2-midas/MIDAS_MSP 활동정리.txt` | 기존 목표·역할·제약의 역사적 근거 | `IMPLEMENTED` (보존) |

## 제외한 자산

| 분류 | 파일 또는 범위 | 제외 이유 | 후속 처리 |
|---|---|---|---|
| 접근 정보 | `jetson/Jetson Access.txt` | SSH 계정·사설 네트워크 IP가 포함됨 | Git에 보관하지 않음 |
| 모델·데이터 | `.pt`, 모델 파일, 원본 영상 | 대용량·재현성·민감 데이터 관리 정책이 미확정 | 모델 카드·획득 절차를 별도 문서화 |
| 발표 산출물 | `MSP_발표자료.pptx`, 최종 발표 PDF, 발표 그룹 리스트 | 팀원 정보·사진·발표용 디자인이 포함되며 코드 재현에 직접 필요하지 않음 | 동의·공개 범위 확정 후 release 또는 `evidence/` 검토 |
| 사진 | 우수상, 구매 물품 사진 | 개인정보·활동 사진이 포함될 수 있고 소스가 아님 | 포트폴리오 사용 시 별도 동의 확인 |
| 행정 문서 | `문서/`의 HWP, PDF, XLSX | 신청·구매·회의비 등 행정 목적이며 개발 기준 소스가 아님 | Git 제외 |
| 타 프로젝트 후보 | `주제 후보 선정.txt`, 타 팀 발표 내용 | 현재 프로젝트의 구현 이력과 직접 관련 없음 | Git 제외 |

## 주의 사항

- legacy 코드에는 현재 Jetson 환경과 충돌할 수 있는 `torch`/`cv2` import 순서와 pandas 의존 결과 처리 등이 남아 있다. 수정하지 않은 역사적 기준으로 보존하며, 신규 구현의 기반 코드로 직접 실행하지 않는다.
- 복구 가이드의 L4T 32.7.3과 개발 정보의 L4T 32.7.6은 다르다. 플래시 전 보드 모델·저장장치·호환 이미지를 반드시 실기기로 검증한다.
- legacy 자산을 토대로 만든 새 코드·설정·테스트는 `app/`, `tests/`, `config/` 등 새 구조에 작성하며, legacy 파일을 덮어쓰지 않는다.
