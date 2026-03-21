from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from quant.backtest.engine import BacktestEngine
from quant.backtest.scheduler import Scheduler
from quant.data.datasource import MockDataSource
from quant.data.repository import DataRepository
from quant.data.schema import Bar
from quant.execution.account import Account
from quant.execution.broker import FixedCommissionModel, SimulatedBroker
from quant.strategy.portfolio import FixedSizePositionSizer
from quant.strategy.signal import VolumePullbackBreakoutSignalModel
from quant.strategy.strategy import Strategy


def build_mock_bars(symbol: str = "000001") -> list[Bar]:
    start = datetime(2024, 1, 1)
    payload = [
        (10.0, 10.2, 10.3, 9.9, 1000),
        (10.2, 10.3, 10.4, 10.1, 1100),
        (10.3, 10.4, 10.5, 10.2, 1050),
        (10.4, 10.5, 10.6, 10.3, 1000),
        (10.5, 11.1, 11.2, 10.5, 2400),
        (11.05, 10.95, 11.0, 10.9, 1300),
        (10.95, 10.92, 10.98, 10.88, 1100),
        (10.98, 11.25, 11.3, 10.97, 1500),
    ]
    bars = []
    for idx, (open_, close, high, low, volume) in enumerate(payload):
        bars.append(
            Bar(
                symbol=symbol,
                dt=start + timedelta(days=idx),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
                amount=close * volume,
            )
        )
    return bars


def run_demo() -> tuple[dict[str, float], list[tuple[str, int]]]:
    symbol = "000001"
    bars = build_mock_bars(symbol)
    repository = DataRepository(MockDataSource({symbol: bars}))
    scheduler = Scheduler([bar.dt for bar in bars])
    strategy = Strategy(
        signal_model=VolumePullbackBreakoutSignalModel(
            breakout_lookback=4,
            breakout_volume_multiplier=1.8,
            breakout_return_threshold=0.04,
            pullback_bars=2,
            pullback_volume_ratio=0.7,
            pullback_price_buffer=0.03,
            restart_volume_multiplier=1.2,
        ),
        position_sizer=FixedSizePositionSizer(fixed_qty=100),
    )
    broker = SimulatedBroker(account=Account(cash=100000), commission_model=FixedCommissionModel(rate=0.0))
    engine = BacktestEngine(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=8)
    result, analysis = engine.run_with_analysis(symbol)
    fills = [(fill.symbol, fill.qty) for fill in result.fills]
    return analysis, fills


if __name__ == "__main__":
    analysis, fills = run_demo()
    print("analysis=", analysis)
    print("fills=", fills)
