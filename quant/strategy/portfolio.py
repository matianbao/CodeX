from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from quant.common.types import OrderSide, SignalType

from .signal import Signal


@dataclass(frozen=True)
class TargetPosition:
    symbol: str
    qty: int
    side: OrderSide | None
    reason: str


class PositionSizer(ABC):
    @abstractmethod
    def size(self, signal: Signal, account, price: float):
        raise NotImplementedError


class FixedSizePositionSizer(PositionSizer):
    def __init__(self, fixed_qty: int) -> None:
        self.fixed_qty = fixed_qty

    def size(self, signal: Signal, account, price: float) -> TargetPosition:
        if signal.signal_type == SignalType.LONG:
            return TargetPosition(symbol=signal.symbol, qty=self.fixed_qty, side=OrderSide.BUY, reason="fixed_size_long")
        if signal.signal_type == SignalType.EXIT:
            current_qty = account.get_position_qty(signal.symbol)
            return TargetPosition(symbol=signal.symbol, qty=current_qty, side=OrderSide.SELL if current_qty else None, reason="exit_signal")
        return TargetPosition(symbol=signal.symbol, qty=0, side=None, reason="hold_signal")
