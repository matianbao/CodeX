from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Bar:
    symbol: str
    dt: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float = 0.0
    adj_factor: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)


BarSeries = list[Bar]
