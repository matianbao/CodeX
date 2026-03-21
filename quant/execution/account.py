from __future__ import annotations

from dataclasses import dataclass, field

from .position import Position


@dataclass
class Account:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)

    def get_position(self, symbol: str) -> Position:
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        return self.positions[symbol]

    def get_position_qty(self, symbol: str) -> int:
        return self.get_position(symbol).qty

    def market_value(self, prices: dict[str, float]) -> float:
        return sum(position.market_value(prices.get(symbol, position.avg_cost)) for symbol, position in self.positions.items())

    def total_equity(self, prices: dict[str, float]) -> float:
        return self.cash + self.market_value(prices)
