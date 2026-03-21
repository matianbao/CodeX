from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from quant.common.types import SignalType
from quant.common.utils import safe_mean

from .context import StrategyContext


@dataclass(frozen=True)
class Signal:
    symbol: str
    signal_type: SignalType
    score: float = 0.0
    metadata: dict[str, float] = field(default_factory=dict)


class SignalModel(ABC):
    def generate(self, context: StrategyContext) -> Signal:
        history = self.prepare_history(context)
        return self.compute_signal(context, history)

    def prepare_history(self, context: StrategyContext):
        return context.history

    @abstractmethod
    def compute_signal(self, context: StrategyContext, history) -> Signal:
        raise NotImplementedError


class MovingAverageCrossSignalModel(SignalModel):
    def __init__(self, short_window: int = 3, long_window: int = 5) -> None:
        if short_window >= long_window:
            raise ValueError("short_window must be smaller than long_window")
        self.short_window = short_window
        self.long_window = long_window

    def compute_signal(self, context: StrategyContext, history) -> Signal:
        closes = [bar.close for bar in history]
        if len(closes) < self.long_window:
            return Signal(symbol=context.symbol, signal_type=SignalType.HOLD, score=0.0)

        short_ma = safe_mean(closes[-self.short_window :])
        long_ma = safe_mean(closes[-self.long_window :])
        if short_ma > long_ma:
            signal_type = SignalType.LONG
        elif short_ma < long_ma:
            signal_type = SignalType.EXIT
        else:
            signal_type = SignalType.HOLD
        return Signal(
            symbol=context.symbol,
            signal_type=signal_type,
            score=short_ma - long_ma,
            metadata={"short_ma": short_ma, "long_ma": long_ma},
        )
