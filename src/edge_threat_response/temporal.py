from __future__ import annotations

from collections import deque

from .domain import TemporalResult


class KOfNBuffer:
    def __init__(self, *, k: int, n: int) -> None:
        if (
            isinstance(k, bool)
            or isinstance(n, bool)
            or not isinstance(k, int)
            or not isinstance(n, int)
        ):
            raise ValueError("k and n must be integers.")
        if k < 1 or n < 1 or k > n:
            raise ValueError("K-of-N requires 1 <= k <= n.")
        self.k = k
        self.n = n
        self._values: deque[bool] = deque(maxlen=n)

    def update(self, value: bool) -> TemporalResult:
        if not isinstance(value, bool):
            raise TypeError("K-of-N values must be bool.")
        self._values.append(value)
        true_count = sum(self._values)
        return TemporalResult(
            value=value,
            true_count=true_count,
            sample_count=len(self._values),
            k=self.k,
            n=self.n,
            confirmed=true_count >= self.k,
        )

    def reset(self) -> None:
        self._values.clear()

    @property
    def values(self) -> tuple[bool, ...]:
        return tuple(self._values)
