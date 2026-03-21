"""Minimal quantitative research framework."""

from .backtest.engine import BacktestEngine
from .backtest.result import BacktestResult
from .backtest.visualizer import BacktestVisualizer
from .data.datasource import AShareDailyDataSource, MockDataSource
from .data.repository import DataRepository
from .execution.broker import SimulatedBroker
from .strategy.strategy import Strategy

__all__ = [
    "AShareDailyDataSource",
    "BacktestEngine",
    "BacktestResult",
    "BacktestVisualizer",
    "DataRepository",
    "MockDataSource",
    "SimulatedBroker",
    "Strategy",
]
