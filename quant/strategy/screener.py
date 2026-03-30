from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from quant.common.logging_utils import get_logger
from quant.common.types import SignalType
from quant.data.repository import DataRepository
from quant.execution.account import Account

from .context import StrategyContext
from .strategy import Strategy, StrategyDecision

logger = get_logger("strategy.screener")


@dataclass(frozen=True)
class LatestSignalResult:
    symbol: str
    dt: datetime
    signal_type: str
    signal_score: float
    latest_close: float
    order_count: int
    selected: bool
    decision: StrategyDecision


class LatestSignalScreener:
    def __init__(self, repository: DataRepository, strategy: Strategy, window_size: int, account_factory: Callable[[], Account] | None = None) -> None:
        self.repository = repository
        self.strategy = strategy
        self.window_size = window_size
        self.account_factory = account_factory or (lambda: Account(cash=1_000_000))

    def scan(self, symbols: list[str] | None = None, selected_only: bool = True) -> list[LatestSignalResult]:
        universe = symbols or self.repository.get_symbols()
        logger.info("latest_signal_scan_start symbols=%s selected_only=%s", len(universe), selected_only)
        results: list[LatestSignalResult] = []
        for symbol in universe:
            bars = self.repository.get_bars(symbol)
            latest_bar = bars[-1]
            history = bars[-self.window_size :]
            context = StrategyContext(
                symbol=symbol,
                dt=latest_bar.dt,
                current_bar=latest_bar,
                history=history,
                account=self.account_factory(),
            )
            decision = self.strategy.evaluate(context)
            selected = decision.signal.signal_type == SignalType.LONG and bool(decision.order_requests)
            result = LatestSignalResult(
                symbol=symbol,
                dt=latest_bar.dt,
                signal_type=decision.signal.signal_type.value,
                signal_score=decision.signal.score,
                latest_close=latest_bar.close,
                order_count=len(decision.order_requests),
                selected=selected,
                decision=decision,
            )
            if not selected_only or selected:
                results.append(result)
            logger.info(
                "latest_signal_scan_symbol symbol=%s dt=%s signal=%s selected=%s orders=%s",
                symbol,
                latest_bar.dt.strftime("%Y-%m-%d"),
                result.signal_type,
                selected,
                result.order_count,
            )
        ranked = sorted(results, key=lambda item: (not item.selected, -item.signal_score, item.symbol))
        logger.info("latest_signal_scan_done results=%s", len(ranked))
        return ranked
