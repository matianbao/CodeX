from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Transaction:
    symbol: str
    qty: int
    price: float
    commission: float
