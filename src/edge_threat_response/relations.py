"""Pure-Python relation-score contract, bound to unchanged detector output."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Protocol

from .domain import AssociationResult, FrameDetections


class RelationProvider(Protocol):
    def __call__(self, frame: FrameDetections, pairs: tuple[AssociationResult, ...]) -> tuple[float | None, ...]: ...


def frame_fingerprint(frame: FrameDetections) -> str:
    value = {"source_id": frame.source_id, "frame_index": frame.frame_index,
             "timestamp_s": frame.timestamp_s, "status": frame.status.value,
             "detections": [x.to_dict() for x in frame.detections], "error": frame.error}
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def pair_key(pair: AssociationResult) -> str:
    return json.dumps({"person": pair.person.to_dict() if pair.person else None,
                       "knife": pair.knife.to_dict()}, sort_keys=True, allow_nan=False)


def score_row(frame: FrameDetections, pairs: tuple[AssociationResult, ...], scores) -> dict:
    if len(pairs) != len(scores):
        raise ValueError("Relation score count differs from candidate pair count")
    for pair, score in zip(pairs, scores):
        if pair.person is None:
            if score is not None: raise ValueError("A missing person cannot have a holding score")
        elif type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Holding score must be finite and in [0,1]")
    return {"source_id": frame.source_id, "frame_index": frame.frame_index, "timestamp_s": frame.timestamp_s,
            "frame_sha256": frame_fingerprint(frame),
            "pairs": [{"key": pair_key(pair), "holding_score": score} for pair, score in zip(pairs, scores)]}


class CachedRelationScores:
    def __init__(self, path: Path, frames: tuple[FrameDetections, ...], detection_sha256: str):
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8-sig").splitlines() if x.strip()]
        if not rows or rows[0].get("schema_version") != 1 or rows[0].get("type") != "relation_provenance":
            raise ValueError("Relation sidecar provenance header is missing")
        self.provenance = rows[0]
        if self.provenance.get("detections_sha256") != detection_sha256:
            raise ValueError("Relation sidecar binds a different detector JSONL")
        for key in ("classifier_sha256", "image_source_sha256", "pipeline_config_sha256"):
            value = self.provenance.get(key)
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"Relation provenance requires {key}")
        if len(rows) != len(frames) + 1:
            raise ValueError("Relation sidecar must cover every detection frame exactly once")
        self.rows = {}
        for frame, row in zip(frames, rows[1:]):
            if (row.get("frame_sha256") != frame_fingerprint(frame) or row.get("frame_index") != frame.frame_index
                    or row.get("source_id") != frame.source_id or row.get("timestamp_s") != frame.timestamp_s):
                raise ValueError("Relation frame fingerprint/order mismatch")
            self.rows[frame.frame_index] = row

    def __call__(self, frame, pairs):
        row = self.rows.get(frame.frame_index)
        if row is None or row["frame_sha256"] != frame_fingerprint(frame):
            raise ValueError("Relation cache frame is missing or changed")
        expected = [pair_key(p) for p in pairs]
        supplied = row.get("pairs", [])
        if not isinstance(supplied, list) or [p.get("key") for p in supplied] != expected:
            raise ValueError("Relation candidate pairs differ from current policy")
        scores = tuple(p["holding_score"] for p in supplied)
        score_row(frame, pairs, scores)
        return scores
