"""Minimal quantitative research framework."""

from .backtest.engine import BacktestEngine
from .backtest.result import BacktestResult
from .data.datasource import AShareDailyDataSource
from .data.repository import DataRepository
from .execution.broker import SimulatedBroker
from .strategy.strategy import Strategy

__all__ = [
    "AShareDailyDataSource",
    "BacktestEngine",
    "BacktestResult",
    "DataRepository",
    "SimulatedBroker",
    "Strategy",
]
