from __future__ import annotations

from abc import ABC, abstractmethod

from .context import StrategyContext
from .portfolio import TargetPosition


class RiskRule(ABC):
    @abstractmethod
    def apply(self, target: TargetPosition, context: StrategyContext) -> TargetPosition:
        raise NotImplementedError


class NoOpRiskRule(RiskRule):
    def apply(self, target: TargetPosition, context: StrategyContext) -> TargetPosition:
        return target


class MaxPositionRiskRule(RiskRule):
    def __init__(self, max_qty: int) -> None:
        self.max_qty = max_qty

    def apply(self, target: TargetPosition, context: StrategyContext) -> TargetPosition:
        if target.qty <= self.max_qty:
            return target
        return TargetPosition(symbol=target.symbol, qty=self.max_qty, side=target.side, reason=f"{target.reason}|capped")


class RiskRuleChain:
    def __init__(self, rules: list[RiskRule] | None = None) -> None:
        self.rules = rules or [NoOpRiskRule()]

    def apply(self, target: TargetPosition, context: StrategyContext) -> TargetPosition:
        current = target
        for rule in self.rules:
            current = rule.apply(current, context)
        return current
