# Dataset audit reports

이 폴더에는 source registry와 고정된 코드로 재생성 가능한 dataset 구조 검증 결과를 둔다.

- `summary.json`, `report.md`: Git에 추적하는 간결한 결과와 해석 경계
- `manifest.jsonl`, `issues.jsonl`: 전체 record를 포함해 크기가 크므로 로컬에서 재생성하고 Git에서는 제외
- `split-plan.json`, `planned-manifest.jsonl`: 팀이 비율·seed를 결정한 뒤 생성하며 raw 파일을 이동하지 않음

현재 결과:

- [legacy-2026-09-14/report.md](legacy-2026-09-14/report.md)
- [legacy-2026-09-14/summary.json](legacy-2026-09-14/summary.json)
- [legacy-development-v1/report.md](legacy-development-v1/report.md)
- [legacy-development-v1/summary.json](legacy-development-v1/summary.json)

재현 명령은 루트 `README.md`를 따른다. report는 파일·label 구조와 leakage를 검증하며 image 내용, annotation의 시각적 정확성, 개별 image license 또는 모델 성능을 증명하지 않는다.
