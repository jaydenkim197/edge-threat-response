# Increment A Replay Smoke Report

- Date: 2026-09-14
- Environment: Windows, Python 3.11.9, `edge-threat-response 0.1.0` editable install
- Input: `tests/fixtures/replay/basic.jsonl` (synthetic detections, 9 frames)
- Config: `configs/replay/development.example.json`
- Input/config SHA-256: recorded in `summary.json`
- Command: `etr-replay --input tests/fixtures/replay/basic.jsonl --config configs/replay/development.example.json --output-dir reports/replay/increment-a-smoke`
- Action errors: 0

| Mode | Confirmation rule | Event frames | Event count |
|---|---|---:|---:|
| B0 | current reliable knife | 0, 7 | 2 |
| B1 | reliable knife K-of-N | 1, 8 | 2 |
| B2 | current person–knife association | 1, 7 | 2 |
| B3 | association K-of-N | 2, 8 | 2 |

The fixture checks distinct B0–B3 confirmation timing, one event per `CONFIRMED` entry, dropout handling, cooldown, and rearm. Replay has no image frame, so snapshots are recorded as `not_captured`.

This is a deterministic software smoke test, not detector accuracy, event-level research evidence, or Jetson verification. The example thresholds, K/N, and rearm count are not final project parameters.
