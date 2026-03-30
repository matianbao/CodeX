from __future__ import annotations

from dataclasses import dataclass, field
from pprint import pformat

from quant.common.logging_utils import get_logger
from quant.data.repository import DataRepository
from quant.execution.broker import SimulatedBroker
from quant.execution.order import Fill
from quant.strategy.context import StrategyContext
from quant.strategy.strategy import Strategy

from .analyzer import Analyzer
from .result import BacktestResult
from .scheduler import Scheduler

logger = get_logger("backtest.debug")


@dataclass
class TraceStep:
    dt: str
    bar_close: float
    history_size: int
    signal_type: str
    signal_score: float
    raw_target_qty: int
    final_target_qty: int
    order_count: int
    fills: list[Fill] = field(default_factory=list)
    equity: float = 0.0


class BacktestDebugger:
    def __init__(
        self,
        scheduler: Scheduler,
        data_repository: DataRepository,
        strategy: Strategy,
        broker: SimulatedBroker,
        analyzer: Analyzer | None = None,
        window_size: int = 5,
    ) -> None:
        self.scheduler = scheduler
        self.data_repository = data_repository
        self.strategy = strategy
        self.broker = broker
        self.analyzer = analyzer or Analyzer()
        self.window_size = window_size

    def run(self, symbol: str, print_trace: bool = True) -> tuple[BacktestResult, dict[str, float], list[TraceStep]]:
        logger.info("debugger_start symbol=%s print_trace=%s", symbol, print_trace)
        result = BacktestResult()
        trace_steps: list[TraceStep] = []
        for dt in self.scheduler.timeline():
            current_bar = self.data_repository.get_bar(symbol, dt)
            history = self.data_repository.get_window(symbol, dt, self.window_size)
            context = StrategyContext(
                symbol=symbol,
                dt=dt,
                current_bar=current_bar,
                history=history,
                account=self.broker.account,
            )
            decision = self.strategy.evaluate(context)
            fills: list[Fill] = []
            for order_request in decision.order_requests:
                result.orders.append(order_request)
                fill = self.broker.execute(order_request, current_bar)
                result.fills.append(fill)
                fills.append(fill)
            equity = self.broker.account.total_equity({symbol: current_bar.close})
            result.equity_curve.append((dt, equity))
            positions = {name: position.qty for name, position in self.broker.account.positions.items()}
            result.positions_history.append((dt, positions))
            step = TraceStep(
                dt=dt.strftime("%Y-%m-%d"),
                bar_close=current_bar.close,
                history_size=len(history),
                signal_type=decision.signal.signal_type.value,
                signal_score=decision.signal.score,
                raw_target_qty=decision.raw_target.qty,
                final_target_qty=decision.final_target.qty,
                order_count=len(decision.order_requests),
                fills=fills,
                equity=equity,
            )
            trace_steps.append(step)
            logger.info("trace_step dt=%s signal=%s orders=%s fills=%s equity=%s", step.dt, step.signal_type, step.order_count, len(step.fills), step.equity)
            if print_trace:
                print(pformat(step))
        analysis = self.analyzer.analyze(result)
        logger.info("debugger_finished symbol=%s metrics=%s", symbol, analysis)
        return result, analysis, trace_steps
