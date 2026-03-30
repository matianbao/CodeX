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

    @property
    def start_equity(self) -> float:
        return self.equity_curve[0][1] if self.equity_curve else 0.0

    @property
    def end_equity(self) -> float:
        return self.equity_curve[-1][1] if self.equity_curve else 0.0

    @property
    def total_return(self) -> float:
        if not self.equity_curve or self.start_equity == 0:
            return 0.0
        return (self.end_equity - self.start_equity) / self.start_equity

    def latest_positions(self) -> dict[str, int]:
        return self.positions_history[-1][1] if self.positions_history else {}
