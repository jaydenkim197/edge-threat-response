# 사건 평가기 가상 검증 · 2026-10-04

Windows 노트북/Python 3.11.9에서 기존 9-frame detection fixture → 실제 B0~B3 replay → 새 사건 평가기를 실행했다. ground truth는 0.1~0.3 s와 0.7~0.9 s의 **가상** 두 사건이며 early/late tolerance는 이 fixture에서만 0초다. 실제 detector·촬영·Orin 성능은 평가하지 않았다.

| 조건 | TP | FP | FN | Precision | Recall | 평균 판단 지연(s) |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 1 | 1 | 1 | 0.5 | 0.5 | 0.00 |
| B1 | 2 | 0 | 0 | 1.0 | 1.0 | 0.05 |
| B2 | 2 | 0 | 0 | 1.0 | 1.0 | 0.00 |
| B3 | 2 | 0 | 0 | 1.0 | 1.0 | 0.10 |

이 숫자는 알고리즘 산술·파이프 연결 검증이다. 0.9초 표본을 시간당 오경보율로 환산한 값을 실제 운용 성능처럼 보고하지 않는다. 8개 초기 tests로 반복 경보·background FP·FN·ignore 노출시간·미정의 분모·signed early latency·겹친 허용 창·session leakage·provenance 불일치·출력 덮어쓰기 방지를 확인했다.

재현 입력: `tests/fixtures/replay/basic.jsonl`, `tests/fixtures/evaluation/ground-truth.json`, `configs/replay/development-v2.example.json`, `configs/evaluation/synthetic.example.json`. 명령은 [실험 규칙](../../../docs/controlled-experiment-protocol.md#6-실행과-결과-확인)에 있다. 원시 replay/`evaluation.json`/`comparison.csv`는 ignored `runs/event-evaluation-synthetic-v1/`에 보존한다. 구현 commit은 이 보고서를 포함하는 Git 이력과 개발 로그를 따른다.
