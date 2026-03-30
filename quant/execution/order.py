from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from itertools import count

from quant.common.types import OrderSide, OrderStatus, PriceType

_order_counter = count(1)


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: OrderSide
    qty: int
    price_type: PriceType = PriceType.MARKET
    note: str = ""


@dataclass
class Order:
    symbol: str
    side: OrderSide
    qty: int
    price_type: PriceType
    note: str = ""
    order_id: str = field(default_factory=lambda: f"ORD-{next(_order_counter):05d}")
    status: OrderStatus = OrderStatus.PENDING


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: OrderSide
    qty: int
    price: float
    commission: float
    dt: datetime
    status: OrderStatus
