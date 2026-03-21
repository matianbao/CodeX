from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from quant.common.exceptions import InsufficientCashError, InvalidOrderError
from quant.common.types import OrderSide, OrderStatus, PriceType
from quant.data.schema import Bar

from .account import Account
from .order import Fill, Order, OrderRequest


class CommissionModel(ABC):
    @abstractmethod
    def calculate(self, order: Order, fill_price: float) -> float:
        raise NotImplementedError


class SlippageModel(ABC):
    @abstractmethod
    def adjust(self, side: OrderSide, price: float) -> float:
        raise NotImplementedError


class ExecutionPolicy(ABC):
    @abstractmethod
    def resolve_price(self, order: OrderRequest, market_snapshot: Bar) -> float:
        raise NotImplementedError


class FixedCommissionModel(CommissionModel):
    def __init__(self, rate: float = 0.001) -> None:
        self.rate = rate

    def calculate(self, order: Order, fill_price: float) -> float:
        return order.qty * fill_price * self.rate


class FixedSlippageModel(SlippageModel):
    def __init__(self, ticks: float = 0.0) -> None:
        self.ticks = ticks

    def adjust(self, side: OrderSide, price: float) -> float:
        return price + self.ticks if side == OrderSide.BUY else price - self.ticks


class CloseExecutionPolicy(ExecutionPolicy):
    def resolve_price(self, order: OrderRequest, market_snapshot: Bar) -> float:
        if order.price_type in {PriceType.CLOSE, PriceType.MARKET}:
            return market_snapshot.close
        if order.price_type == PriceType.OPEN:
            return market_snapshot.open
        raise InvalidOrderError(f"Unsupported price_type={order.price_type}")


class SimulatedBroker:
    def __init__(
        self,
        account: Account,
        commission_model: CommissionModel | None = None,
        slippage_model: SlippageModel | None = None,
        execution_policy: ExecutionPolicy | None = None,
    ) -> None:
        self.account = account
        self.commission_model = commission_model or FixedCommissionModel()
        self.slippage_model = slippage_model or FixedSlippageModel()
        self.execution_policy = execution_policy or CloseExecutionPolicy()

    def execute(self, order_request: OrderRequest, market_snapshot: Bar) -> Fill:
        if order_request.qty <= 0:
            raise InvalidOrderError("Order quantity must be positive")

        order = Order(
            symbol=order_request.symbol,
            side=order_request.side,
            qty=order_request.qty,
            price_type=order_request.price_type,
            note=order_request.note,
        )
        raw_price = self.execution_policy.resolve_price(order_request, market_snapshot)
        fill_price = self.slippage_model.adjust(order.side, raw_price)
        commission = self.commission_model.calculate(order, fill_price)

        position = self.account.get_position(order.symbol)
        if order.side == OrderSide.BUY:
            required_cash = fill_price * order.qty + commission
            if required_cash > self.account.cash:
                raise InsufficientCashError(f"Required {required_cash}, available {self.account.cash}")
            self.account.cash -= required_cash
            position.apply_fill(order.side, order.qty, fill_price)
        else:
            if order.qty > position.qty:
                raise InvalidOrderError("Cannot sell more than held quantity")
            self.account.cash += fill_price * order.qty - commission
            position.apply_fill(order.side, order.qty, fill_price)

        order.status = OrderStatus.FILLED
        return Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=fill_price,
            commission=commission,
            dt=market_snapshot.dt,
            status=order.status,
        )
