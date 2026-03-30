from __future__ import annotations

import csv
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
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


class MockDataSource(InMemoryDataSource):
    """Semantic alias used by tests/examples when data is fully mocked."""


class CsvDataSource(DataSource):
    def __init__(self, base_path: str | Path, filename_pattern: str = "{symbol}.csv", datetime_format: str = "%Y-%m-%d") -> None:
        self.base_path = Path(base_path)
        self.filename_pattern = filename_pattern
        self.datetime_format = datetime_format

    def get_symbols(self) -> list[str]:
        pattern_suffix = self.filename_pattern.split("{symbol}")[-1]
        files = self.base_path.glob(f"*{pattern_suffix}")
        return sorted(file.stem for file in files)

    def get_bars(self, symbol: str, start: datetime | None = None, end: datetime | None = None) -> BarSeries:
        file_path = self.base_path / self.filename_pattern.format(symbol=symbol)
        bars: BarSeries = []
        with file_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                dt = datetime.strptime(row["dt"], self.datetime_format)
                bar = Bar(
                    symbol=row.get("symbol", symbol),
                    dt=dt,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0.0)),
                    amount=float(row.get("amount", 0.0)),
                    adj_factor=float(row.get("adj_factor", 1.0)),
                )
                if (start is None or bar.dt >= start) and (end is None or bar.dt <= end):
                    bars.append(bar)
        return sorted(bars, key=lambda bar: bar.dt)


class FallbackDataSource(DataSource):
    def __init__(self, sources: list[DataSource]) -> None:
        if not sources:
            raise ValueError("sources must not be empty")
        self.sources = sources

    def get_symbols(self) -> list[str]:
        symbols: set[str] = set()
        for source in self.sources:
            symbols.update(source.get_symbols())
        return sorted(symbols)

    def get_bars(self, symbol: str, start: datetime | None = None, end: datetime | None = None) -> BarSeries:
        for source in self.sources:
            bars = source.get_bars(symbol, start=start, end=end)
            if bars:
                return bars
        return []


class AShareDailyDataSource(DataSource):
    """Fetch A-share daily bars and current symbol lists from Eastmoney."""

    base_url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    list_url = "https://push2.eastmoney.com/api/qt/clist/get"

    def __init__(self, symbols: list[str] | None = None, adjust: str = "qfq", lookback_months: int = 3) -> None:
        self.symbols = symbols or []
        self._symbol_cache: list[str] | None = list(self.symbols) if self.symbols else None
        adjust_map = {"": "0", "none": "0", "qfq": "1", "hfq": "2"}
        if adjust not in adjust_map:
            raise ValueError("adjust must be one of '', 'none', 'qfq', 'hfq'")
        if lookback_months <= 0:
            raise ValueError("lookback_months must be positive")
        self.adjust = adjust
        self.fqt = adjust_map[adjust]
        self.lookback_months = lookback_months

    def get_symbols(self) -> list[str]:
        if self._symbol_cache is None:
            self._symbol_cache = self._fetch_current_symbols()
        return list(self._symbol_cache)

    def get_bars(self, symbol: str, start: datetime | None = None, end: datetime | None = None) -> BarSeries:
        normalized = self._normalize_symbol(symbol)
        secid = self._to_secid(normalized)
        resolved_end = end or datetime.utcnow()
        resolved_start = start or self._subtract_months(resolved_end, self.lookback_months)
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "klt": "101",
            "fqt": self.fqt,
            "secid": secid,
            "beg": resolved_start.strftime("%Y%m%d"),
            "end": resolved_end.strftime("%Y%m%d"),
        }
        url = f"{self.base_url}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))

        raw_bars = payload.get("data", {}).get("klines", [])
        return [self._parse_bar(normalized, item) for item in raw_bars]

    def _fetch_current_symbols(self) -> list[str]:
        params = {
            "pn": "1",
            "pz": "5000",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23",
            "fields": "f12",
        }
        url = f"{self.list_url}?{urlencode(params)}"
        request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"})
        with urlopen(request) as response:
            payload = json.loads(response.read().decode("utf-8"))
        diff = payload.get("data", {}).get("diff", [])
        return sorted(str(item.get("f12")) for item in diff if item.get("f12"))


    @staticmethod
    def _subtract_months(dt: datetime, months: int) -> datetime:
        year = dt.year
        month = dt.month - months
        while month <= 0:
            month += 12
            year -= 1
        day = min(dt.day, AShareDailyDataSource._days_in_month(year, month))
        return dt.replace(year=year, month=month, day=day)

    @staticmethod
    def _days_in_month(year: int, month: int) -> int:
        if month == 2:
            leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
            return 29 if leap else 28
        if month in {4, 6, 9, 11}:
            return 30
        return 31

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


class TushareDailyDataSource(DataSource):
    api_url = "http://api.waditu.com"

    def __init__(self, token: str, symbols: list[str] | None = None) -> None:
        self.token = token
        self.symbols = symbols or []

    def get_symbols(self) -> list[str]:
        return list(self.symbols)

    def get_bars(self, symbol: str, start: datetime | None = None, end: datetime | None = None) -> BarSeries:
        ts_code = self._normalize_symbol(symbol)
        payload = {
            "api_name": "daily",
            "token": self.token,
            "params": {
                "ts_code": ts_code,
                "start_date": start.strftime("%Y%m%d") if start else None,
                "end_date": end.strftime("%Y%m%d") if end else None,
            },
            "fields": "ts_code,trade_date,open,high,low,close,vol,amount",
        }
        request = Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))

        rows = result.get("data", {}).get("items", [])
        bars = [self._parse_row(row) for row in rows]
        return sorted(bars, key=lambda bar: bar.dt)


    @staticmethod
    def _subtract_months(dt: datetime, months: int) -> datetime:
        year = dt.year
        month = dt.month - months
        while month <= 0:
            month += 12
            year -= 1
        day = min(dt.day, AShareDailyDataSource._days_in_month(year, month))
        return dt.replace(year=year, month=month, day=day)

    @staticmethod
    def _days_in_month(year: int, month: int) -> int:
        if month == 2:
            leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
            return 29 if leap else 28
        if month in {4, 6, 9, 11}:
            return 30
        return 31

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        upper = symbol.upper()
        if "." in upper:
            return upper
        if len(symbol) != 6 or not symbol.isdigit():
            raise ValueError(f"Unsupported symbol: {symbol}")
        suffix = "SH" if symbol.startswith("6") else "SZ"
        return f"{symbol}.{suffix}"

    @staticmethod
    def _parse_row(row: list[object]) -> Bar:
        ts_code, trade_date, open_, high, low, close, volume, amount = row
        return Bar(
            symbol=str(ts_code).split(".")[0],
            dt=datetime.strptime(str(trade_date), "%Y%m%d"),
            open=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=float(volume),
            amount=float(amount),
        )
