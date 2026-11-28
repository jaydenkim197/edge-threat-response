"""The P430 D1 knife detector's fixed target-area tiling and merge."""

from __future__ import annotations

import math
from typing import Any

from .detector import RawDetection, UltralyticsBackend

REVIEW_WIDTH, REVIEW_HEIGHT = 1920, 1080


def tile_regions(width: int, height: int) -> list[tuple[int, int, int, int]]:
    if width < 768 or height < 640 or (width, height) == (768, 640):
        return []
    return [
        (x, y, x + 768, y + 640)
        for y in (0, height - 640)
        for x in (0, (width - 768) // 2, width - 768)
    ]


def touches_internal_tile_edge(box, region) -> bool:
    a, b, c, d = box
    x1, y1, x2, y2 = region
    return (
        (x1 > 0 and a < 3)
        or (y1 > 0 and b < 3)
        or (x2 < REVIEW_WIDTH and c > x2 - x1 - 3)
        or (y2 < REVIEW_HEIGHT and d > y2 - y1 - 3)
    )


def tile_nms_indices(boxes, scores) -> list[int]:
    if not boxes:
        return []
    import torch
    from torchvision.ops import nms

    return nms(torch.tensor(boxes, dtype=torch.float32), torch.tensor(scores), 0.55).tolist()[:300]


class P430TiledBackend(UltralyticsBackend):
    def __init__(
        self, weights: str, *, predict_arguments: dict[str, object], cuda_graph: bool = False
    ) -> None:
        if predict_arguments.keys() - {"device", "conf", "premerge_conf", "half", "imgsz"}:
            raise ValueError("P430 tile predict_arguments supports device, conf, premerge_conf, half and imgsz.")
        size = predict_arguments.get("imgsz", 640)
        square = type(size) is int and size == 640
        native = isinstance(size, list) and size == [640, 768] and all(type(dimension) is int for dimension in size)
        if not (square or native):
            raise ValueError("P430 tile imgsz must be 640 or [640, 768] (height, width).")
        confidence = predict_arguments.get("conf", .001)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not .001 <= confidence <= 1:
            raise ValueError("P430 tile confidence must be in [0.001, 1].")
        premerge_confidence = predict_arguments.get("premerge_conf", .001)
        if (isinstance(premerge_confidence, bool) or not isinstance(premerge_confidence, (int, float))
                or not .001 <= premerge_confidence <= confidence):
            raise ValueError("P430 tile premerge_conf must be in [0.001, conf].")
        half = predict_arguments.get("half", False)
        if not isinstance(half, bool):
            raise ValueError("P430 tile half must be a boolean.")

        self.output_confidence = float(confidence)
        arguments = {
            "device": predict_arguments.get("device", 0), "imgsz": 640 if square else [640, 768], "rect": False,
            "conf": float(premerge_confidence), "iou": .7, "classes": [0], "max_det": 100,
        }
        if half:
            arguments["half"] = True
        super().__init__(weights, predict_arguments=arguments, cuda_graph=cuda_graph)

    def predict(self, image: Any) -> tuple[RawDetection, ...]:
        shape = getattr(image, "shape", ())
        if shape == (2160, 3840, 3):
            left, top = 960, 540
        elif shape == (REVIEW_HEIGHT, REVIEW_WIDTH, 3):
            left, top = 0, 0
        else:
            raise ValueError("P430 tile input requires a 3840×2160 or 1920×1080 BGR frame.")
        if self._get_model().names != {0: "knife"}:
            raise ValueError("P430 tile requires a knife-only checkpoint.")

        regions = tile_regions(REVIEW_WIDTH, REVIEW_HEIGHT)
        # Ultralytics accepts NumPy tiles in OpenCV's BGR order and converts
        # the batch to RGB. Keep views of the original buffer until preprocessing.
        images = [
            image[top + y1:top + y2, left + x1:left + x2]
            for x1, y1, x2, y2 in regions
        ]
        boxes, scores = [], []
        for region, detections in zip(regions, self.predict_batch(images), strict=True):
            x1, y1, _, _ = region
            for detection in detections:
                box = detection.bbox_xyxy
                score = detection.confidence
                if len(box) != 4 or not all(math.isfinite(value) for value in box) or not 0 <= score <= 1:
                    raise ValueError("Invalid P430 tile prediction.")
                if detection.class_id != 0 or touches_internal_tile_edge(box, region):
                    continue
                a, b, c, d = box
                boxes.append((a + x1, b + y1, c + x1, d + y1))
                scores.append(score)

        predictions = []
        for index in tile_nms_indices(boxes, scores):
            if scores[index] < self.output_confidence:
                continue
            a, b, c, d = boxes[index]
            a, b = max(0., a), max(0., b)
            c, d = min(REVIEW_WIDTH, c), min(REVIEW_HEIGHT, d)
            if c > a and d > b:
                predictions.append(RawDetection(0, scores[index], (left + a, top + b, left + c, top + d)))
        return tuple(predictions)
