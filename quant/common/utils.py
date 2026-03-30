from __future__ import annotations

from statistics import mean
from typing import Iterable


def safe_mean(values: Iterable[float], default: float = 0.0) -> float:
    materialized = list(values)
    return mean(materialized) if materialized else default
