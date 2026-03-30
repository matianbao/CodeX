from __future__ import annotations

from dataclasses import dataclass

from quant.common.logging_utils import get_logger
from quant.common.types import PriceType
from quant.execution.order import OrderRequest

from .context import StrategyContext
from .portfolio import PositionSizer, TargetPosition
from .rule import RiskRuleChain
from .signal import Signal, SignalModel

logger = get_logger("strategy.core")


@dataclass(frozen=True)
class StrategyDecision:
    signal: Signal
    raw_target: TargetPosition
    final_target: TargetPosition
    order_requests: list[OrderRequest]


class Strategy:
    def __init__(self, signal_model: SignalModel, position_sizer: PositionSizer, risk_rules: RiskRuleChain | None = None) -> None:
        self.signal_model = signal_model
        self.position_sizer = position_sizer
        self.risk_rules = risk_rules or RiskRuleChain()

    def evaluate(self, context: StrategyContext) -> StrategyDecision:
        logger.info("strategy_start symbol=%s dt=%s", context.symbol, context.dt.strftime("%Y-%m-%d"))
        signal = self.signal_model.generate(context)
        logger.info("signal_generated symbol=%s type=%s score=%s", context.symbol, signal.signal_type.value, signal.score)
        raw_target = self.position_sizer.size(signal, context.account, context.current_bar.close)
        logger.info("raw_target symbol=%s qty=%s side=%s", raw_target.symbol, raw_target.qty, getattr(raw_target.side, 'value', None))
        final_target = self.risk_rules.apply(raw_target, context)
        logger.info("final_target symbol=%s qty=%s side=%s", final_target.symbol, final_target.qty, getattr(final_target.side, 'value', None))
        if final_target.side is None or final_target.qty <= 0:
            order_requests: list[OrderRequest] = []
        else:
            order_requests = [
                OrderRequest(
                    symbol=final_target.symbol,
                    side=final_target.side,
                    qty=final_target.qty,
                    price_type=PriceType.CLOSE,
                    note=final_target.reason,
                )
            ]
        logger.info("orders_created symbol=%s count=%s", context.symbol, len(order_requests))
        return StrategyDecision(
            signal=signal,
            raw_target=raw_target,
            final_target=final_target,
            order_requests=order_requests,
        )

    def generate_order_requests(self, context: StrategyContext) -> list[OrderRequest]:
        return self.evaluate(context).order_requests
