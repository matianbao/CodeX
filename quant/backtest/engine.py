from __future__ import annotations

from quant.common.logging_utils import get_logger
from quant.data.repository import DataRepository
from quant.execution.broker import SimulatedBroker
from quant.strategy.context import StrategyContext
from quant.strategy.strategy import Strategy

from .analyzer import Analyzer
from .result import BacktestResult
from .scheduler import Scheduler

logger = get_logger("backtest.engine")


class BacktestEngine:
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

    def run(self, symbol: str) -> BacktestResult:
        logger.info("backtest_start symbol=%s", symbol)
        result = BacktestResult()
        for dt in self.scheduler.timeline():
            logger.info("backtest_step symbol=%s dt=%s", symbol, dt.strftime("%Y-%m-%d"))
            current_bar = self.data_repository.get_bar(symbol, dt)
            history = self.data_repository.get_window(symbol, dt, self.window_size)
            context = StrategyContext(
                symbol=symbol,
                dt=dt,
                current_bar=current_bar,
                history=history,
                account=self.broker.account,
            )
            order_requests = self.strategy.generate_order_requests(context)
            for order_request in order_requests:
                result.orders.append(order_request)
                fill = self.broker.execute(order_request, current_bar)
                result.fills.append(fill)
            equity = self.broker.account.total_equity({symbol: current_bar.close})
            result.equity_curve.append((dt, equity))
            positions = {name: position.qty for name, position in self.broker.account.positions.items()}
            result.positions_history.append((dt, positions))
            logger.info("backtest_step_done symbol=%s dt=%s orders=%s fills=%s equity=%s", symbol, dt.strftime("%Y-%m-%d"), len(order_requests), len(result.fills), equity)
        logger.info("backtest_finished symbol=%s total_fills=%s", symbol, len(result.fills))
        return result

    def run_with_analysis(self, symbol: str) -> tuple[BacktestResult, dict[str, float]]:
        result = self.run(symbol)
        analysis = self.analyzer.analyze(result)
        logger.info("analysis_ready symbol=%s metrics=%s", symbol, analysis)
        return result, analysis
