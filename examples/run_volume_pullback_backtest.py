from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quant.backtest.debug import BacktestDebugger
from quant.backtest.engine import BacktestEngine
from quant.backtest.scheduler import Scheduler
from quant.backtest.visualizer import BacktestVisualizer
from quant.common.logging_utils import configure_logging, get_logger
from quant.data.datasource import MockDataSource
from quant.data.repository import DataRepository
from quant.data.schema import Bar
from quant.execution.account import Account
from quant.execution.broker import FixedCommissionModel, SimulatedBroker
from quant.strategy.portfolio import FixedSizePositionSizer
from quant.strategy.signal import VolumePullbackBreakoutSignalModel
from quant.strategy.strategy import Strategy

logger = get_logger("examples.volume_pullback")


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


def build_demo_components(symbol: str = "000001") -> tuple[str, DataRepository, Scheduler, Strategy, SimulatedBroker]:
    logger.info("build_demo_components symbol=%s", symbol)
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
    logger.info("demo_components_ready symbol=%s timeline=%s", symbol, len(scheduler.timeline()))
    return symbol, repository, scheduler, strategy, broker


def run_demo(output_dir: str | Path = ROOT / "artifacts", enable_logging: bool = True) -> tuple[dict[str, float], list[tuple[str, int]], Path, Path]:
    if enable_logging:
        configure_logging(logging.INFO)
    logger.info("run_demo_start output_dir=%s", output_dir)
    symbol, repository, scheduler, strategy, broker = build_demo_components()
    engine = BacktestEngine(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=8)
    result, analysis = engine.run_with_analysis(symbol)
    fills = [(fill.symbol, fill.qty) for fill in result.fills]
    html_path, svg_path = BacktestVisualizer().save_report(result, analysis, output_dir=output_dir, report_name="volume_pullback_report")
    logger.info("run_demo_finished fills=%s html=%s svg=%s", fills, html_path, svg_path)
    return analysis, fills, html_path, svg_path


def run_debug_demo(print_trace: bool = True, enable_logging: bool = True) -> tuple[dict[str, float], list[dict[str, object]]]:
    if enable_logging:
        configure_logging(logging.INFO)
    logger.info("run_debug_demo_start print_trace=%s", print_trace)
    symbol, repository, scheduler, strategy, broker = build_demo_components()
    debugger = BacktestDebugger(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=8)
    _, analysis, trace_steps = debugger.run(symbol, print_trace=print_trace)
    trace_payload = [
        {
            "dt": step.dt,
            "bar_close": step.bar_close,
            "history_size": step.history_size,
            "signal_type": step.signal_type,
            "signal_score": step.signal_score,
            "raw_target_qty": step.raw_target_qty,
            "final_target_qty": step.final_target_qty,
            "order_count": step.order_count,
            "fills": [(fill.symbol, fill.qty) for fill in step.fills],
            "equity": step.equity,
        }
        for step in trace_steps
    ]
    logger.info("run_debug_demo_finished steps=%s", len(trace_payload))
    return analysis, trace_payload


if __name__ == "__main__":
    analysis, fills, html_path, svg_path = run_demo()
    print("analysis=", analysis)
    print("fills=", fills)
    print("html_report=", html_path)
    print("svg_chart=", svg_path)
    print("\n=== DEBUG TRACE ===")
    debug_analysis, trace_steps = run_debug_demo(print_trace=True)
    print("debug_analysis=", debug_analysis)
    print("trace_steps=", trace_steps)
