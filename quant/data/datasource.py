from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

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
