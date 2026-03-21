from __future__ import annotations

from quant.data.repository import DataRepository
from quant.execution.broker import SimulatedBroker
from quant.strategy.context import StrategyContext
from quant.strategy.strategy import Strategy

from .analyzer import Analyzer
from .result import BacktestResult
from .scheduler import Scheduler


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
        result = BacktestResult()
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
            order_requests = self.strategy.generate_order_requests(context)
            for order_request in order_requests:
                result.orders.append(order_request)
                fill = self.broker.execute(order_request, current_bar)
                result.fills.append(fill)
            equity = self.broker.account.total_equity({symbol: current_bar.close})
            result.equity_curve.append((dt, equity))
            positions = {name: position.qty for name, position in self.broker.account.positions.items()}
            result.positions_history.append((dt, positions))
        return result

    def run_with_analysis(self, symbol: str) -> tuple[BacktestResult, dict[str, float]]:
        result = self.run(symbol)
        return result, self.analyzer.analyze(result)
