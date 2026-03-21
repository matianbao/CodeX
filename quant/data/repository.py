from __future__ import annotations

from datetime import datetime

from quant.common.exceptions import DataNotFoundError

from .datasource import DataSource
from .schema import Bar, BarSeries


class DataRepository:
    def __init__(self, datasource: DataSource) -> None:
        self._datasource = datasource
        self._cache: dict[str, BarSeries] = {}

    def get_symbols(self) -> list[str]:
        return self._datasource.get_symbols()

    def get_bars(self, symbol: str) -> BarSeries:
        if symbol not in self._cache:
            bars = self._datasource.get_bars(symbol)
            if not bars:
                raise DataNotFoundError(f"No bars found for symbol={symbol}")
            self._cache[symbol] = bars
        return self._cache[symbol]

    def get_bar(self, symbol: str, dt: datetime) -> Bar:
        for bar in self.get_bars(symbol):
            if bar.dt == dt:
                return bar
        raise DataNotFoundError(f"No bar for symbol={symbol} at dt={dt.isoformat()}")

    def get_window(self, symbol: str, dt: datetime, size: int) -> BarSeries:
        bars = [bar for bar in self.get_bars(symbol) if bar.dt <= dt]
        if not bars:
            raise DataNotFoundError(f"No history available for symbol={symbol} at dt={dt.isoformat()}")
        return bars[-size:]
