from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import patch

from examples.run_volume_pullback_backtest import run_debug_demo, run_demo, run_latest_signal_scan
from quant.backtest.analyzer import Analyzer
from quant.backtest.debug import BacktestDebugger
from quant.backtest.visualizer import BacktestVisualizer
from quant.common.logging_utils import configure_logging
from quant.backtest.engine import BacktestEngine
from quant.backtest.scheduler import Scheduler
from quant.common.types import OrderSide, OrderStatus, PriceType, SignalType
from quant.data.datasource import AShareDailyDataSource, CsvDataSource, FallbackDataSource, MockDataSource, TushareDailyDataSource
from quant.data.factory import DataSourceFactory
from quant.data.repository import DataRepository
from quant.data.schema import Bar
from quant.execution.account import Account
from quant.execution.broker import FixedCommissionModel, FixedSlippageModel, SimulatedBroker
from quant.execution.order import OrderRequest
from quant.execution.position import Position
from quant.strategy.context import StrategyContext
from quant.strategy.portfolio import FixedSizePositionSizer
from quant.strategy.rule import MaxPositionRiskRule, RiskRuleChain
from quant.strategy.screener import LatestSignalScreener
from quant.strategy.signal import MovingAverageCrossSignalModel, VolumePullbackBreakoutSignalModel
from quant.strategy.strategy import Strategy


def build_bars(symbol: str = "AAPL") -> list[Bar]:
    start = datetime(2024, 1, 1)
    closes = [10, 11, 12, 13, 14, 15]
    return [
        Bar(symbol=symbol, dt=start + timedelta(days=idx), open=close - 0.5, high=close + 0.5, low=close - 1, close=close, volume=1000)
        for idx, close in enumerate(closes)
    ]


def build_volume_pattern_bars(symbol: str = "000001") -> list[Bar]:
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
    return [
        Bar(symbol=symbol, dt=start + timedelta(days=idx), open=open_, high=high, low=low, close=close, volume=volume, amount=close * volume)
        for idx, (open_, close, high, low, volume) in enumerate(payload)
    ]


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_mock_data_source_and_repository_return_expected_values():
    bars = build_bars()
    datasource = MockDataSource({"AAPL": bars})
    repository = DataRepository(datasource)

    assert datasource.get_symbols() == ["AAPL"]
    assert repository.get_symbols() == ["AAPL"]
    assert repository.get_bar("AAPL", bars[2].dt).close == 12
    assert [bar.close for bar in repository.get_window("AAPL", bars[4].dt, 3)] == [12, 13, 14]


def test_ashare_daily_data_source_parses_remote_payload():
    payload = {
        "data": {
            "klines": [
                "2024-01-02,10.00,10.50,10.80,9.90,123456,654321",
                "2024-01-03,10.60,10.90,11.00,10.50,111111,777777",
            ]
        }
    }
    with patch("quant.data.datasource.urlopen", return_value=FakeResponse(payload)):
        datasource = AShareDailyDataSource(symbols=["000001"])
        bars = datasource.get_bars("sz000001")

    assert datasource.get_symbols() == ["000001"]
    assert [bar.symbol for bar in bars] == ["000001", "000001"]
    assert bars[0].close == 10.5
    assert bars[1].volume == 111111.0


def test_ashare_daily_data_source_fetches_current_symbol_list_when_unconfigured():
    payload = {"data": {"diff": [{"f12": "000001"}, {"f12": "600519"}]}}
    with patch("quant.data.datasource.urlopen", return_value=FakeResponse(payload)):
        datasource = AShareDailyDataSource()
        assert datasource.get_symbols() == ["000001", "600519"]


def test_ashare_daily_data_source_uses_configurable_recent_lookback_window():
    payload = {"data": {"klines": ["2024-03-01,10.00,10.50,10.80,9.90,123456,654321"]}}
    captured_urls: list[str] = []

    def fake_urlopen(request):
        captured_urls.append(request.full_url)
        return FakeResponse(payload)

    with patch("quant.data.datasource.urlopen", side_effect=fake_urlopen):
        datasource = AShareDailyDataSource(symbols=["000001"], lookback_months=6)
        bars = datasource.get_bars("000001", end=datetime(2024, 3, 31))

    assert bars[0].close == 10.5
    assert "beg=20230930" in captured_urls[0]
    assert "end=20240331" in captured_urls[0]


def test_signal_model_position_sizer_and_risk_rule_chain():
    bars = build_bars()
    account = Account(cash=1000)
    context = StrategyContext(symbol="AAPL", dt=bars[-1].dt, current_bar=bars[-1], history=bars[-5:], account=account)

    signal = MovingAverageCrossSignalModel(short_window=2, long_window=4).generate(context)
    assert signal.signal_type == SignalType.LONG
    assert signal.metadata["short_ma"] == 14.5
    assert signal.metadata["long_ma"] == 13.5

    target = FixedSizePositionSizer(fixed_qty=10).size(signal, account, bars[-1].close)
    assert target.qty == 10
    assert target.side == OrderSide.BUY

    adjusted = RiskRuleChain([MaxPositionRiskRule(max_qty=6)]).apply(target, context)
    assert adjusted.qty == 6
    assert adjusted.reason.endswith("capped")


def test_volume_pullback_breakout_signal_generates_long_signal():
    bars = build_volume_pattern_bars()
    account = Account(cash=100000)
    context = StrategyContext(symbol="000001", dt=bars[-1].dt, current_bar=bars[-1], history=bars, account=account)
    signal = VolumePullbackBreakoutSignalModel(
        breakout_lookback=4,
        breakout_volume_multiplier=1.8,
        breakout_return_threshold=0.04,
        pullback_bars=2,
        pullback_volume_ratio=0.7,
        pullback_price_buffer=0.03,
        restart_volume_multiplier=1.2,
    ).generate(context)

    assert signal.signal_type == SignalType.LONG
    assert signal.metadata["breakout_close"] == 11.1
    assert signal.metadata["restart_volume"] == 1500


def test_broker_account_position_and_fill_values():
    bar = build_bars()[-1]
    account = Account(cash=1000)
    broker = SimulatedBroker(
        account=account,
        commission_model=FixedCommissionModel(rate=0.001),
        slippage_model=FixedSlippageModel(ticks=0.1),
    )

    buy_fill = broker.execute(OrderRequest(symbol="AAPL", side=OrderSide.BUY, qty=10, price_type=PriceType.CLOSE), bar)
    assert buy_fill.status == OrderStatus.FILLED
    assert round(buy_fill.price, 2) == 15.10
    assert round(buy_fill.commission, 3) == 0.151
    assert account.get_position_qty("AAPL") == 10

    sell_fill = broker.execute(OrderRequest(symbol="AAPL", side=OrderSide.SELL, qty=4, price_type=PriceType.CLOSE), bar)
    assert sell_fill.status == OrderStatus.FILLED
    assert account.get_position("AAPL").qty == 6
    assert round(account.get_position("AAPL").realized_pnl, 2) == -0.80


def test_position_helpers_and_analyzer_outputs():
    position = Position(symbol="AAPL")
    position.apply_fill(OrderSide.BUY, qty=5, price=10)
    assert position.market_value(12) == 60
    assert position.unrealized_pnl(12) == 10

    metrics = Analyzer().analyze(
        BacktestEngine(
            scheduler=Scheduler([]),
            data_repository=DataRepository(MockDataSource({"AAPL": build_bars()})),
            strategy=Strategy(
                signal_model=MovingAverageCrossSignalModel(short_window=2, long_window=4),
                position_sizer=FixedSizePositionSizer(fixed_qty=1),
            ),
            broker=SimulatedBroker(Account(cash=1000)),
        ).run("AAPL")
    )
    assert set(metrics) == {"total_return", "num_trades", "average_equity", "ending_equity", "max_drawdown"}


def test_backtest_engine_runs_end_to_end_and_returns_expected_result_shapes():
    bars = build_bars()
    repository = DataRepository(MockDataSource({"AAPL": bars}))
    scheduler = Scheduler([bar.dt for bar in bars])
    strategy = Strategy(
        signal_model=MovingAverageCrossSignalModel(short_window=2, long_window=4),
        position_sizer=FixedSizePositionSizer(fixed_qty=2),
        risk_rules=RiskRuleChain([MaxPositionRiskRule(max_qty=2)]),
    )
    broker = SimulatedBroker(account=Account(cash=1000), commission_model=FixedCommissionModel(rate=0.0))
    result, analysis = BacktestEngine(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=4).run_with_analysis("AAPL")

    assert len(result.equity_curve) == len(bars)
    assert len(result.positions_history) == len(bars)
    assert len(result.orders) == len(result.fills) == 3
    assert analysis["num_trades"] == 3.0
    assert result.latest_positions()["AAPL"] == 6


def test_backtest_engine_can_run_volume_pullback_breakout_strategy():
    bars = build_volume_pattern_bars()
    repository = DataRepository(MockDataSource({"000001": bars}))
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
    result, analysis = BacktestEngine(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=8).run_with_analysis("000001")

    assert len(result.orders) == 1
    assert result.orders[0].symbol == "000001"
    assert result.fills[0].qty == 100
    assert analysis["num_trades"] == 1.0
    assert result.total_return >= 0


def test_visualizer_creates_svg_and_html_report(tmp_path):
    bars = build_volume_pattern_bars()
    repository = DataRepository(MockDataSource({"000001": bars}))
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
    result, analysis = BacktestEngine(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=8).run_with_analysis("000001")

    html_path, svg_path = BacktestVisualizer().save_report(result, analysis, tmp_path, report_name="demo_report")

    assert html_path.exists()
    assert svg_path.exists()
    assert "Equity Curve" in html_path.read_text(encoding="utf-8")
    assert "<svg" in svg_path.read_text(encoding="utf-8")


def test_mock_backtest_demo_runs_end_to_end(tmp_path):
    analysis, fills, html_path, svg_path = run_demo(tmp_path)
    assert analysis["num_trades"] == 1.0
    assert fills == [("000001", 100)]
    assert html_path.exists()
    assert svg_path.exists()


def test_csv_data_source_reads_local_file(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    csv_path.write_text(
        "dt,open,high,low,close,volume,amount\n"
        "2024-01-01,10,11,9,10.5,1000,10500\n"
        "2024-01-02,10.5,11.5,10,11,1200,13200\n",
        encoding="utf-8",
    )
    datasource = CsvDataSource(tmp_path)
    bars = datasource.get_bars("AAPL")

    assert datasource.get_symbols() == ["AAPL"]
    assert len(bars) == 2
    assert bars[1].close == 11.0


def test_tushare_daily_data_source_parses_remote_payload():
    payload = {
        "data": {
            "items": [
                ["000001.SZ", "20240102", 10.0, 10.8, 9.9, 10.5, 123456, 654321],
                ["000001.SZ", "20240103", 10.6, 11.0, 10.5, 10.9, 111111, 777777],
            ]
        }
    }
    with patch("quant.data.datasource.urlopen", return_value=FakeResponse(payload)):
        datasource = TushareDailyDataSource(token="demo-token", symbols=["000001.SZ"])
        bars = datasource.get_bars("000001")

    assert datasource.get_symbols() == ["000001.SZ"]
    assert [bar.symbol for bar in bars] == ["000001", "000001"]
    assert bars[0].close == 10.5
    assert bars[1].volume == 111111.0


def test_data_source_factory_creates_expected_types(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    csv_path.write_text("dt,open,high,low,close\n2024-01-01,1,1,1,1\n", encoding="utf-8")

    mock_source = DataSourceFactory.create("mock", data={"AAPL": build_bars()})
    csv_source = DataSourceFactory.create("csv", base_path=tmp_path)
    ashare_source = DataSourceFactory.create("ashare", symbols=["000001"])
    tushare_source = DataSourceFactory.create("tushare", token="demo-token", symbols=["000001.SZ"])

    assert mock_source.get_symbols() == ["AAPL"]
    assert isinstance(csv_source, CsvDataSource)
    assert isinstance(ashare_source, AShareDailyDataSource)
    assert isinstance(tushare_source, TushareDailyDataSource)


def test_fallback_data_source_prefers_first_non_empty_source(tmp_path):
    csv_path = tmp_path / "AAPL.csv"
    csv_path.write_text("dt,open,high,low,close\n2024-01-01,1,2,0.5,1.5\n", encoding="utf-8")
    empty_source = MockDataSource({})
    csv_source = CsvDataSource(tmp_path)
    datasource = FallbackDataSource([empty_source, csv_source])

    bars = datasource.get_bars("AAPL")

    assert datasource.get_symbols() == ["AAPL"]
    assert len(bars) == 1
    assert bars[0].close == 1.5


def test_csv_data_source_runs_full_backtest_pipeline(tmp_path):
    csv_path = tmp_path / "000001.csv"
    rows = [
        "dt,open,high,low,close,volume,amount",
        "2024-01-01,10.0,10.3,9.9,10.2,1000,10200",
        "2024-01-02,10.2,10.4,10.1,10.3,1100,11330",
        "2024-01-03,10.3,10.5,10.2,10.4,1050,10920",
        "2024-01-04,10.4,10.6,10.3,10.5,1000,10500",
        "2024-01-05,10.5,11.2,10.5,11.1,2400,26640",
        "2024-01-06,11.05,11.0,10.9,10.95,1300,14235",
        "2024-01-07,10.95,10.98,10.88,10.92,1100,12012",
        "2024-01-08,10.98,11.3,10.97,11.25,1500,16875",
    ]
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    repository = DataRepository(DataSourceFactory.create("csv", base_path=tmp_path))
    bars = repository.get_bars("000001")
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
    result, analysis = BacktestEngine(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=8).run_with_analysis("000001")

    assert len(result.fills) == 1
    assert result.fills[0].symbol == "000001"
    assert analysis["num_trades"] == 1.0


def test_tushare_data_source_runs_downstream_pipeline_with_mocked_response():
    payload = {
        "data": {
            "items": [
                ["000001.SZ", "20240101", 10.0, 10.3, 9.9, 10.2, 1000, 10200],
                ["000001.SZ", "20240102", 10.2, 10.4, 10.1, 10.3, 1100, 11330],
                ["000001.SZ", "20240103", 10.3, 10.5, 10.2, 10.4, 1050, 10920],
                ["000001.SZ", "20240104", 10.4, 10.6, 10.3, 10.5, 1000, 10500],
                ["000001.SZ", "20240105", 10.5, 11.2, 10.5, 11.1, 2400, 26640],
                ["000001.SZ", "20240106", 11.05, 11.0, 10.9, 10.95, 1300, 14235],
                ["000001.SZ", "20240107", 10.95, 10.98, 10.88, 10.92, 1100, 12012],
                ["000001.SZ", "20240108", 10.98, 11.3, 10.97, 11.25, 1500, 16875],
            ]
        }
    }
    with patch("quant.data.datasource.urlopen", return_value=FakeResponse(payload)):
        repository = DataRepository(TushareDailyDataSource(token="demo-token", symbols=["000001.SZ"]))
        bars = repository.get_bars("000001")
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
        result, analysis = BacktestEngine(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=8).run_with_analysis("000001")

    assert len(result.fills) == 1
    assert result.fills[0].qty == 100
    assert analysis["num_trades"] == 1.0


def test_backtest_debugger_and_debug_demo_expose_intermediate_outputs(capsys):
    bars = build_volume_pattern_bars()
    repository = DataRepository(MockDataSource({"000001": bars}))
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
    debugger = BacktestDebugger(scheduler=scheduler, data_repository=repository, strategy=strategy, broker=broker, window_size=8)

    result, analysis, trace_steps = debugger.run("000001", print_trace=True)
    printed = capsys.readouterr().out
    debug_analysis, debug_steps = run_debug_demo(print_trace=False)

    assert len(trace_steps) == len(bars)
    assert trace_steps[-1].signal_type == "LONG"
    assert trace_steps[-1].order_count == 1
    assert len(result.fills) == 1
    assert analysis["num_trades"] == 1.0
    assert "signal_type='LONG'" in printed
    assert debug_analysis["num_trades"] == 1.0
    assert debug_steps[-1]["fills"] == [("000001", 100)]


def test_logging_covers_key_pipeline_stages(caplog, tmp_path):
    configure_logging()
    with caplog.at_level("INFO"):
        analysis, fills, html_path, svg_path = run_demo(tmp_path, enable_logging=True)

    log_output = "\n".join(record.getMessage() for record in caplog.records)

    assert analysis["num_trades"] == 1.0
    assert fills == [("000001", 100)]
    assert html_path.exists()
    assert svg_path.exists()
    assert "run_demo_start" in log_output
    assert "cache_miss symbol=000001" in log_output
    assert "signal_generated symbol=000001 type=LONG" in log_output
    assert "broker_execute symbol=000001 side=BUY qty=100" in log_output
    assert "backtest_step_done symbol=000001 dt=2024-01-08" in log_output
    assert "report_saved html=" in log_output


def test_latest_signal_screener_returns_symbols_matching_strategy():
    matching = build_volume_pattern_bars("000001")
    non_matching = build_bars("000002")
    repository = DataRepository(MockDataSource({"000001": matching, "000002": non_matching}))
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

    results = LatestSignalScreener(repository=repository, strategy=strategy, window_size=8).scan(selected_only=True)

    assert [item.symbol for item in results] == ["000001"]
    assert results[0].signal_type == "LONG"
    assert results[0].selected is True


def test_run_latest_signal_scan_returns_selected_a_share_symbols():
    symbol_payload = {"data": {"diff": [{"f12": "000001"}, {"f12": "000002"}]}}
    bar_payloads = {
        "000001": {
            "data": {
                "klines": [
                    "2024-01-01,10.0,10.2,10.3,9.9,1000,10200",
                    "2024-01-02,10.2,10.3,10.4,10.1,1100,11330",
                    "2024-01-03,10.3,10.4,10.5,10.2,1050,10920",
                    "2024-01-04,10.4,10.5,10.6,10.3,1000,10500",
                    "2024-01-05,10.5,11.1,11.2,10.5,2400,26640",
                    "2024-01-06,11.05,10.95,11.0,10.9,1300,14235",
                    "2024-01-07,10.95,10.92,10.98,10.88,1100,12012",
                    "2024-01-08,10.98,11.25,11.3,10.97,1500,16875",
                ]
            }
        },
        "000002": {
            "data": {
                "klines": [
                    "2024-01-01,10,10,10,10,1000,10000",
                    "2024-01-02,10,10,10,10,1000,10000",
                    "2024-01-03,10,10,10,10,1000,10000",
                    "2024-01-04,10,10,10,10,1000,10000",
                    "2024-01-05,10,10,10,10,1000,10000",
                    "2024-01-06,10,10,10,10,1000,10000",
                    "2024-01-07,10,10,10,10,1000,10000",
                    "2024-01-08,10,10,10,10,1000,10000",
                ]
            }
        },
    }

    def fake_urlopen(request):
        url = request.full_url
        if "clist/get" in url:
            return FakeResponse(symbol_payload)
        if "secid=0.000001" in url:
            return FakeResponse(bar_payloads["000001"])
        if "secid=0.000002" in url:
            return FakeResponse(bar_payloads["000002"])
        raise AssertionError(url)

    with patch("quant.data.datasource.urlopen", side_effect=fake_urlopen):
        results = run_latest_signal_scan(lookback_months=3, symbols=None, selected_only=True, enable_logging=False)

    assert [item["symbol"] for item in results] == ["000001"]
    assert results[0]["signal_type"] == "LONG"
    assert results[0]["selected"] is True
