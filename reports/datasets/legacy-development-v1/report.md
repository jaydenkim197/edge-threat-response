# Legacy Knife Development Dataset Export

상태: `PASSED` (구조·재현성), 연구용 최종 split·시각 품질 `PROPOSAL`

## Recipe

- source: fixed legacy audit manifest, 7,364 records / 3,552 groups
- development defaults: train/val/test 70/15/15, seed `20260915`
- class: knife-only model-local `0=knife`, runtime canonical mapping `0→1`
- image placement: hardlink; raw images and labels unchanged
- label conversion: YOLO bbox preserved, YOLO polygon converted to enclosing normalized bbox
- exact SHA-256 duplicate records are retained in the source manifest but emitted once

## Result

| Check | Result |
|---|---:|
| Planned train / val / test | 5,155 / 1,104 / 1,105 |
| Materialized train / val / test | 5,153 / 1,104 / 1,104 |
| Total images and labels | 7,361 / 7,361 |
| Total objects | 9,057 |
| Bbox / polygon-to-bbox | 7,610 / 1,447 |
| Exact duplicate records skipped | 3 |
| Bad output label lines | 0 |
| Groups crossing output splits | 0 |
| Exact hashes crossing output splits | 0 |
| Source image/label hash changes after audit | 0 / 0 |

The planned-manifest SHA-256 is `8811c3a2f99fff428f3a539dc4de964d136055c7854f69722bfa6400fd514101`.

## Interpretation boundary

This export proves that the fixed legacy source can be transformed into a one-class YOLO dataset without source mutation or known group/exact-hash leakage. It does not approve the 70/15/15 split as the final research split, verify visual annotation quality, resolve near-duplicates, or establish detector performance.
