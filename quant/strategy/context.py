from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from quant.data.schema import Bar, BarSeries
from quant.execution.account import Account


@dataclass(frozen=True)
class StrategyContext:
    symbol: str
    dt: datetime
    current_bar: Bar
    history: BarSeries
    account: Account
