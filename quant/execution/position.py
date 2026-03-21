from __future__ import annotations

from dataclasses import dataclass

from quant.common.types import OrderSide


@dataclass
class Position:
    symbol: str
    qty: int = 0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0

    def apply_fill(self, side: OrderSide, qty: int, price: float) -> None:
        if side == OrderSide.BUY:
            total_cost = self.avg_cost * self.qty + price * qty
            self.qty += qty
            self.avg_cost = total_cost / self.qty if self.qty else 0.0
            return

        if qty > self.qty:
            raise ValueError("Cannot sell more than current quantity")
        self.realized_pnl += (price - self.avg_cost) * qty
        self.qty -= qty
        if self.qty == 0:
            self.avg_cost = 0.0

    def market_value(self, price: float) -> float:
        return self.qty * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.avg_cost) * self.qty
