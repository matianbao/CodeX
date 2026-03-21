from __future__ import annotations

from datetime import datetime, timedelta

from quant.backtest.analyzer import Analyzer
from quant.backtest.engine import BacktestEngine
from quant.backtest.scheduler import Scheduler
from quant.common.types import OrderSide, OrderStatus, PriceType, SignalType
from quant.data.datasource import InMemoryDataSource
from quant.data.repository import DataRepository
from quant.data.schema import Bar
from quant.execution.account import Account
from quant.execution.broker import FixedCommissionModel, FixedSlippageModel, SimulatedBroker
from quant.execution.order import OrderRequest
from quant.execution.position import Position
from quant.strategy.context import StrategyContext
from quant.strategy.portfolio import FixedSizePositionSizer
from quant.strategy.rule import MaxPositionRiskRule, RiskRuleChain
from quant.strategy.signal import MovingAverageCrossSignalModel
from quant.strategy.strategy import Strategy


def build_bars(symbol: str = "AAPL") -> list[Bar]:
    start = datetime(2024, 1, 1)
    closes = [10, 11, 12, 13, 14, 15]
    bars = []
    for idx, close in enumerate(closes):
        dt = start + timedelta(days=idx)
        bars.append(
            Bar(symbol=symbol, dt=dt, open=close - 0.5, high=close + 0.5, low=close - 1, close=close, volume=1000)
        )
    return bars


def test_data_source_and_repository_return_expected_values():
    bars = build_bars()
    datasource = InMemoryDataSource({"AAPL": bars})
    repository = DataRepository(datasource)

    assert datasource.get_symbols() == ["AAPL"]
    assert repository.get_symbols() == ["AAPL"]
    assert repository.get_bar("AAPL", bars[2].dt).close == 12
    window = repository.get_window("AAPL", bars[4].dt, 3)
    assert [bar.close for bar in window] == [12, 13, 14]


def test_signal_model_position_sizer_and_risk_rule_chain():
    bars = build_bars()
    account = Account(cash=1000)
    context = StrategyContext(symbol="AAPL", dt=bars[-1].dt, current_bar=bars[-1], history=bars[-5:], account=account)

    signal_model = MovingAverageCrossSignalModel(short_window=2, long_window=4)
    signal = signal_model.generate(context)
    assert signal.signal_type == SignalType.LONG
    assert signal.metadata["short_ma"] == 14.5
    assert signal.metadata["long_ma"] == 13.5

    target = FixedSizePositionSizer(fixed_qty=10).size(signal, account, bars[-1].close)
    assert target.qty == 10
    assert target.side == OrderSide.BUY

    adjusted = RiskRuleChain([MaxPositionRiskRule(max_qty=6)]).apply(target, context)
    assert adjusted.qty == 6
    assert adjusted.reason.endswith("capped")


def test_broker_account_position_and_fill_values():
    bar = build_bars()[-1]
    account = Account(cash=1000)
    broker = SimulatedBroker(
        account=account,
        commission_model=FixedCommissionModel(rate=0.001),
        slippage_model=FixedSlippageModel(ticks=0.1),
    )

    buy_request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, qty=10, price_type=PriceType.CLOSE)
    buy_fill = broker.execute(buy_request, bar)
    assert buy_fill.status == OrderStatus.FILLED
    assert round(buy_fill.price, 2) == 15.10
    assert round(buy_fill.commission, 3) == 0.151
    assert account.get_position_qty("AAPL") == 10

    sell_request = OrderRequest(symbol="AAPL", side=OrderSide.SELL, qty=4, price_type=PriceType.CLOSE)
    sell_fill = broker.execute(sell_request, bar)
    assert sell_fill.status == OrderStatus.FILLED
    position = account.get_position("AAPL")
    assert position.qty == 6
    assert round(position.realized_pnl, 2) == -0.80


def test_position_helpers_and_analyzer_outputs():
    position = Position(symbol="AAPL")
    position.apply_fill(OrderSide.BUY, qty=5, price=10)
    assert position.market_value(12) == 60
    assert position.unrealized_pnl(12) == 10

    analyzer = Analyzer()
    result_metrics = analyzer.analyze(
        BacktestEngine(
            scheduler=Scheduler([]),
            data_repository=DataRepository(InMemoryDataSource({"AAPL": build_bars()})),
            strategy=Strategy(
                signal_model=MovingAverageCrossSignalModel(short_window=2, long_window=4),
                position_sizer=FixedSizePositionSizer(fixed_qty=1),
            ),
            broker=SimulatedBroker(Account(cash=1000)),
        ).run("AAPL")
    )
    assert set(result_metrics) == {"total_return", "num_trades", "average_equity"}


def test_backtest_engine_runs_end_to_end_and_returns_expected_result_shapes():
    bars = build_bars()
    repository = DataRepository(InMemoryDataSource({"AAPL": bars}))
    scheduler = Scheduler([bar.dt for bar in bars])
    strategy = Strategy(
        signal_model=MovingAverageCrossSignalModel(short_window=2, long_window=4),
        position_sizer=FixedSizePositionSizer(fixed_qty=2),
        risk_rules=RiskRuleChain([MaxPositionRiskRule(max_qty=2)]),
    )
    broker = SimulatedBroker(account=Account(cash=1000), commission_model=FixedCommissionModel(rate=0.0))
    engine = BacktestEngine(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=4)

    result, analysis = engine.run_with_analysis("AAPL")

    assert len(result.equity_curve) == len(bars)
    assert len(result.positions_history) == len(bars)
    assert len(result.orders) == len(result.fills) == 3
    assert analysis["num_trades"] == 3.0
    assert broker.account.get_position_qty("AAPL") == 6
