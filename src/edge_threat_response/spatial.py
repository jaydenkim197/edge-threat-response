from __future__ import annotations

import math

from .domain import AssociationResult, Detection


def associate_person_knives(
    people: tuple[Detection, ...] | list[Detection],
    knives: tuple[Detection, ...] | list[Detection],
    *,
    normalized_distance_threshold: float,
    expanded_person_ratio: float,
) -> tuple[AssociationResult, ...]:
    if (
        not math.isfinite(normalized_distance_threshold)
        or normalized_distance_threshold < 0
    ):
        raise ValueError("Normalized-distance threshold must be finite and non-negative.")
    if not math.isfinite(expanded_person_ratio) or expanded_person_ratio < 0:
        raise ValueError("Expanded-person ratio must be finite and non-negative.")

    results: list[AssociationResult] = []
    for knife in knives:
        if not people:
            results.append(
                AssociationResult(
                    knife=knife,
                    person=None,
                    center_distance=None,
                    normalized_distance=None,
                    center_in_expanded_person=False,
                    associated=False,
                )
            )
            continue

        nearest_person = min(
            enumerate(people),
            key=lambda item: (_center_distance(knife, item[1]), item[0]),
        )[1]
        center_distance = _center_distance(knife, nearest_person)
        normalized_distance = center_distance / nearest_person.bbox.diagonal
        inside = nearest_person.bbox.expand_by_ratio(expanded_person_ratio).contains(
            knife.bbox.center
        )
        results.append(
            AssociationResult(
                knife=knife,
                person=nearest_person,
                center_distance=center_distance,
                normalized_distance=normalized_distance,
                center_in_expanded_person=inside,
                associated=(inside and normalized_distance <= normalized_distance_threshold),
            )
        )
    return tuple(results)


def _center_distance(left: Detection, right: Detection) -> float:
    left_x, left_y = left.bbox.center
    right_x, right_y = right.bbox.center
    return math.hypot(left_x - right_x, left_y - right_y)
