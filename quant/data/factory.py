from __future__ import annotations

from pathlib import Path
from typing import Any

from .datasource import AShareDailyDataSource, CsvDataSource, DataSource, FallbackDataSource, MockDataSource, TushareDailyDataSource
from .schema import Bar


class DataSourceFactory:
    @staticmethod
    def create(kind: str, **kwargs: Any) -> DataSource:
        normalized = kind.lower()
        if normalized == "mock":
            return MockDataSource(kwargs.get("data", {}))
        if normalized == "csv":
            return CsvDataSource(
                base_path=Path(kwargs["base_path"]),
                filename_pattern=kwargs.get("filename_pattern", "{symbol}.csv"),
                datetime_format=kwargs.get("datetime_format", "%Y-%m-%d"),
            )
        if normalized == "ashare":
            return AShareDailyDataSource(symbols=kwargs.get("symbols"), adjust=kwargs.get("adjust", "qfq"))
        if normalized == "tushare":
            return TushareDailyDataSource(token=kwargs["token"], symbols=kwargs.get("symbols"))
        if normalized == "fallback":
            return FallbackDataSource(sources=kwargs["sources"])
        raise ValueError(f"Unsupported datasource kind: {kind}")

    @staticmethod
    def mock_from_bars(symbol: str, bars: list[Bar]) -> DataSource:
        return MockDataSource({symbol: bars})
