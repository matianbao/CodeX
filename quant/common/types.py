from __future__ import annotations

from enum import Enum


class Frequency(str, Enum):
    DAILY = "1d"
    HOURLY = "1h"
    MINUTE = "1m"


class SignalType(str, Enum):
    LONG = "LONG"
    EXIT = "EXIT"
    HOLD = "HOLD"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class PriceType(str, Enum):
    MARKET = "MARKET"
    CLOSE = "CLOSE"
    OPEN = "OPEN"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
