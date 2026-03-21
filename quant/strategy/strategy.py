from __future__ import annotations

from dataclasses import dataclass

from quant.common.types import PriceType
from quant.execution.order import OrderRequest

from .context import StrategyContext
from .portfolio import PositionSizer, TargetPosition
from .rule import RiskRuleChain
from .signal import Signal, SignalModel


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
        signal = self.signal_model.generate(context)
        raw_target = self.position_sizer.size(signal, context.account, context.current_bar.close)
        final_target = self.risk_rules.apply(raw_target, context)
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
        return StrategyDecision(
            signal=signal,
            raw_target=raw_target,
            final_target=final_target,
            order_requests=order_requests,
        )

    def generate_order_requests(self, context: StrategyContext) -> list[OrderRequest]:
        return self.evaluate(context).order_requests
