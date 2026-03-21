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


class VolumePullbackBreakoutSignalModel(SignalModel):
    """放量上涨 -> 缩量回踩 -> 启动买入。"""

    def __init__(
        self,
        breakout_lookback: int = 8,
        breakout_volume_multiplier: float = 1.5,
        breakout_return_threshold: float = 0.03,
        pullback_bars: int = 2,
        pullback_volume_ratio: float = 0.8,
        pullback_price_buffer: float = 0.02,
        restart_volume_multiplier: float = 1.1,
        stop_loss_pct: float = 0.03,
    ) -> None:
        self.breakout_lookback = breakout_lookback
        self.breakout_volume_multiplier = breakout_volume_multiplier
        self.breakout_return_threshold = breakout_return_threshold
        self.pullback_bars = pullback_bars
        self.pullback_volume_ratio = pullback_volume_ratio
        self.pullback_price_buffer = pullback_price_buffer
        self.restart_volume_multiplier = restart_volume_multiplier
        self.stop_loss_pct = stop_loss_pct

    def compute_signal(self, context: StrategyContext, history) -> Signal:
        if len(history) < self.breakout_lookback + self.pullback_bars + 2:
            return Signal(symbol=context.symbol, signal_type=SignalType.HOLD, score=0.0)

        current = history[-1]
        pullback_segment = history[-(self.pullback_bars + 1) : -1]
        breakout_candidates = history[: -(self.pullback_bars + 1)]
        breakout_bar = None
        breakout_index = -1
        for idx in range(len(breakout_candidates) - 1, 0, -1):
            bar = breakout_candidates[idx]
            prev_bar = breakout_candidates[idx - 1]
            prior_window = breakout_candidates[max(0, idx - self.breakout_lookback) : idx]
            avg_volume = safe_mean(item.volume for item in prior_window)
            price_change = (bar.close - prev_bar.close) / prev_bar.close if prev_bar.close else 0.0
            is_breakout = (
                avg_volume > 0
                and bar.close > bar.open
                and price_change >= self.breakout_return_threshold
                and bar.volume >= avg_volume * self.breakout_volume_multiplier
            )
            if is_breakout:
                breakout_bar = bar
                breakout_index = idx
                break

        if breakout_bar is None:
            return Signal(symbol=context.symbol, signal_type=SignalType.HOLD, score=0.0)


        if any(bar.close < breakout_bar.close * (1 - self.pullback_price_buffer) for bar in pullback_segment):
            return Signal(
                symbol=context.symbol,
                signal_type=SignalType.EXIT,
                score=-1.0,
                metadata={"reason": "pullback_broken"},
            )

        if any(bar.volume > breakout_bar.volume * self.pullback_volume_ratio for bar in pullback_segment):
            return Signal(symbol=context.symbol, signal_type=SignalType.HOLD, score=0.0, metadata={"reason": "pullback_volume_too_high"})

        restart_price_ok = current.close > max(bar.high for bar in pullback_segment)
        restart_volume_ok = current.volume >= pullback_segment[-1].volume * self.restart_volume_multiplier
        score = (current.close - breakout_bar.close) / breakout_bar.close

        if restart_price_ok and restart_volume_ok:
            return Signal(
                symbol=context.symbol,
                signal_type=SignalType.LONG,
                score=score,
                metadata={
                    "breakout_close": breakout_bar.close,
                    "breakout_volume": breakout_bar.volume,
                    "restart_volume": current.volume,
                },
            )

        position = context.account.get_position(context.symbol)
        stop_price = breakout_bar.close * (1 - self.stop_loss_pct)
        if position.qty > 0 and current.close < stop_price:
            return Signal(symbol=context.symbol, signal_type=SignalType.EXIT, score=-1.0, metadata={"reason": "stop_loss"})

        return Signal(symbol=context.symbol, signal_type=SignalType.HOLD, score=score)
