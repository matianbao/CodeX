from __future__ import annotations

from datetime import datetime

from quant.common.exceptions import DataNotFoundError
from quant.common.logging_utils import get_logger

from .datasource import DataSource
from .schema import Bar, BarSeries

logger = get_logger("data.repository")


class DataRepository:
    def __init__(self, datasource: DataSource) -> None:
        self._datasource = datasource
        self._cache: dict[str, BarSeries] = {}

    def get_symbols(self) -> list[str]:
        symbols = self._datasource.get_symbols()
        logger.info("get_symbols -> count=%s", len(symbols))
        return symbols

    def get_bars(self, symbol: str) -> BarSeries:
        if symbol not in self._cache:
            logger.info("cache_miss symbol=%s -> loading from datasource", symbol)
            bars = self._datasource.get_bars(symbol)
            if not bars:
                raise DataNotFoundError(f"No bars found for symbol={symbol}")
            self._cache[symbol] = bars
        else:
            logger.info("cache_hit symbol=%s -> bars=%s", symbol, len(self._cache[symbol]))
        return self._cache[symbol]

    def get_bar(self, symbol: str, dt: datetime) -> Bar:
        logger.info("get_bar symbol=%s dt=%s", symbol, dt.strftime("%Y-%m-%d"))
        for bar in self.get_bars(symbol):
            if bar.dt == dt:
                return bar
        raise DataNotFoundError(f"No bar for symbol={symbol} at dt={dt.isoformat()}")

    def get_window(self, symbol: str, dt: datetime, size: int) -> BarSeries:
        logger.info("get_window symbol=%s dt=%s size=%s", symbol, dt.strftime("%Y-%m-%d"), size)
        bars = [bar for bar in self.get_bars(symbol) if bar.dt <= dt]
        if not bars:
            raise DataNotFoundError(f"No history available for symbol={symbol} at dt={dt.isoformat()}")
        window = bars[-size:]
        logger.info("window_ready symbol=%s actual_size=%s", symbol, len(window))
        return window
