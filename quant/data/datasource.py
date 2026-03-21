from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .schema import Bar, BarSeries


class DataSource(ABC):
    @abstractmethod
    def get_bars(self, symbol: str, start: datetime | None = None, end: datetime | None = None) -> BarSeries:
        raise NotImplementedError

    @abstractmethod
    def get_symbols(self) -> list[str]:
        raise NotImplementedError


class InMemoryDataSource(DataSource):
    def __init__(self, data: dict[str, list[Bar]]) -> None:
        self._data = {symbol: sorted(bars, key=lambda bar: bar.dt) for symbol, bars in data.items()}

    def get_bars(self, symbol: str, start: datetime | None = None, end: datetime | None = None) -> BarSeries:
        bars = self._data.get(symbol, [])
        return [
            bar
            for bar in bars
            if (start is None or bar.dt >= start) and (end is None or bar.dt <= end)
        ]

    def get_symbols(self) -> list[str]:
        return sorted(self._data.keys())


class AShareDailyDataSource(DataSource):
    """Fetch A-share daily bars from the Eastmoney kline endpoint."""

    base_url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    def __init__(self, symbols: list[str] | None = None, adjust: str = "qfq") -> None:
        self.symbols = symbols or []
        adjust_map = {"": "0", "none": "0", "qfq": "1", "hfq": "2"}
        if adjust not in adjust_map:
            raise ValueError("adjust must be one of '', 'none', 'qfq', 'hfq'")
        self.adjust = adjust
        self.fqt = adjust_map[adjust]

    def get_symbols(self) -> list[str]:
        return list(self.symbols)

    def get_bars(self, symbol: str, start: datetime | None = None, end: datetime | None = None) -> BarSeries:
        normalized = self._normalize_symbol(symbol)
        secid = self._to_secid(normalized)
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "klt": "101",
            "fqt": self.fqt,
            "secid": secid,
            "beg": start.strftime("%Y%m%d") if start else "19900101",
            "end": end.strftime("%Y%m%d") if end else "20991231",
        }
        url = f"{self.base_url}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))

        raw_bars = payload.get("data", {}).get("klines", [])
        return [self._parse_bar(normalized, item) for item in raw_bars]

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.lower().replace("sh", "").replace("sz", "").replace("bj", "")
        if len(normalized) != 6 or not normalized.isdigit():
            raise ValueError(f"Unsupported A-share symbol: {symbol}")
        return normalized

    @staticmethod
    def _to_secid(symbol: str) -> str:
        market = "1" if symbol.startswith("6") else "0"
        return f"{market}.{symbol}"

    @staticmethod
    def _parse_bar(symbol: str, item: str) -> Bar:
        dt_str, open_, close, high, low, volume, amount, *_ = item.split(",")
        return Bar(
            symbol=symbol,
            dt=datetime.strptime(dt_str, "%Y-%m-%d"),
            open=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=float(volume),
            amount=float(amount),
        )
