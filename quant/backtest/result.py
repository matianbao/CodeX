from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from quant.execution.order import Fill, OrderRequest


@dataclass
class BacktestResult:
    orders: list[OrderRequest] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)
    positions_history: list[tuple[datetime, dict[str, int]]] = field(default_factory=list)
