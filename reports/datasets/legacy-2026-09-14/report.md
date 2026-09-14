# Dataset Audit Report

Generated: `2026-09-14T13:13:09.596184+00:00`
Registry: `configs/datasets/legacy.json`
Image hashing: `True`

## Totals

| Metric | Count |
|---|---:|
| Images | 7364 |
| Objects parsed | 9060 |
| Unique groups | 3552 |
| Empty labels | 0 |
| Invalid/missing labels | 0 |
| Exact duplicate groups | 3 |
| Groups crossing original splits | 317 |
| Exact hashes crossing original splits | 0 |

## Sources

| Source | Images | Objects | Empty | Invalid/missing |
|---|---:|---:|---:|---:|
| legacy-knife-detection-v1 | 6181 | 7613 | 0 | 0 |
| legacy-new-knife-v3 | 1183 | 1447 | 0 | 0 |

## Annotation formats

- `bbox`: 7613
- `polygon`: 1447

## Canonical class distribution

- `1` (`knife`): 9060

## Issues

| Code | Count |
|---|---:|
| `exact_duplicate_image` | 3 |
| `group_split_leakage` | 317 |

### Issue examples

#### `exact_duplicate_image`

- **WARNING** `345e81b61f30d521fac257408fe56c70d71b2efdccc11c4ec404cc523a26b4c5` — Identical image content appears more than once.
- **WARNING** `525adff1b1e526df6be268b53c843a20fa1995f305e74989941d2acfeffe1553` — Identical image content appears more than once.
- **WARNING** `6c386625a79268f21a42f6bfb95242139fa86ce8797c7ac6b01de06442f410c4` — Identical image content appears more than once.

#### `group_split_leakage`

- **ERROR** `legacy-knife:-44-_jpg` — A source/session group crosses original dataset splits.
- **ERROR** `legacy-knife:images-1-_png` — A source/session group crosses original dataset splits.
- **ERROR** `legacy-knife:images-10-_jpg` — A source/session group crosses original dataset splits.
- **ERROR** `legacy-knife:images-100-_jpg` — A source/session group crosses original dataset splits.
- **ERROR** `legacy-knife:images-12-_jpg` — A source/session group crosses original dataset splits.


## Interpretation boundary

This report validates file, label, duplicate, and split-group structure. It does not verify visual annotation quality, dataset suitability, upstream availability, licensing of each image, or model performance.
