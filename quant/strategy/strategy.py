from __future__ import annotations

from quant.common.types import PriceType
from quant.execution.order import OrderRequest

from .context import StrategyContext
from .portfolio import PositionSizer
from .rule import RiskRuleChain
from .signal import SignalModel


class Strategy:
    def __init__(self, signal_model: SignalModel, position_sizer: PositionSizer, risk_rules: RiskRuleChain | None = None) -> None:
        self.signal_model = signal_model
        self.position_sizer = position_sizer
        self.risk_rules = risk_rules or RiskRuleChain()

    def generate_order_requests(self, context: StrategyContext) -> list[OrderRequest]:
        signal = self.signal_model.generate(context)
        target = self.position_sizer.size(signal, context.account, context.current_bar.close)
        target = self.risk_rules.apply(target, context)
        if target.side is None or target.qty <= 0:
            return []
        return [
            OrderRequest(
                symbol=target.symbol,
                side=target.side,
                qty=target.qty,
                price_type=PriceType.CLOSE,
                note=target.reason,
            )
        ]
