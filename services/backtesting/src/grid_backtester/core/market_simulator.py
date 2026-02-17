"""Market simulator for backtesting trading strategies."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

_logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELED = "canceled"


@dataclass
class SimulatedOrder:
    """Simulated exchange order."""

    id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: Decimal
    amount: Decimal
    filled: Decimal = Decimal("0")
    status: OrderStatus = OrderStatus.OPEN
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_filled(self) -> bool:
        return self.filled >= self.amount

    @property
    def remaining(self) -> Decimal:
        return self.amount - self.filled


@dataclass
class SimulatedBalance:
    """Simulated account balance."""

    base: Decimal = Decimal("0")
    quote: Decimal = Decimal("10000")

    def can_buy(self, amount: Decimal, price: Decimal) -> bool:
        cost = amount * price
        return self.quote >= cost

    def can_sell(self, amount: Decimal) -> bool:
        return self.base >= amount

    def execute_buy(self, amount: Decimal, price: Decimal) -> None:
        cost = amount * price
        if not self.can_buy(amount, price):
            raise ValueError(f"Insufficient quote balance: {self.quote} < {cost}")
        self.quote -= cost
        self.base += amount

    def execute_sell(self, amount: Decimal, price: Decimal) -> None:
        if not self.can_sell(amount):
            raise ValueError(f"Insufficient base balance: {self.base} < {amount}")
        self.base -= amount
        self.quote += amount * price


class MarketSimulator:
    """Simulates a cryptocurrency exchange for backtesting."""

    def __init__(
        self,
        symbol: str = "BTC/USDT",
        initial_balance_base: Decimal = Decimal("0"),
        initial_balance_quote: Decimal = Decimal("10000"),
        maker_fee: Decimal = Decimal("0.001"),
        taker_fee: Decimal = Decimal("0.001"),
        slippage: Decimal = Decimal("0.0001"),
    ):
        self.symbol = symbol
        self.balance = SimulatedBalance(base=initial_balance_base, quote=initial_balance_quote)
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        self.slippage = slippage

        self.current_price = Decimal("45000")
        self.orders: dict[str, SimulatedOrder] = {}
        self.order_id_counter = 0
        self.trade_history: list[dict[str, Any]] = []

    async def set_price(self, price: Decimal) -> None:
        """Update current market price."""
        self.current_price = price
        await self._check_limit_orders()

    def get_ticker(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "last": float(self.current_price),
            "bid": float(self.current_price * (Decimal("1") - self.slippage)),
            "ask": float(self.current_price * (Decimal("1") + self.slippage)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_balance(self) -> dict[str, dict[str, float]]:
        base_currency = self.symbol.split("/")[0]
        quote_currency = self.symbol.split("/")[1]

        return {
            base_currency: {
                "free": float(self.balance.base),
                "used": 0.0,
                "total": float(self.balance.base),
            },
            quote_currency: {
                "free": float(self.balance.quote),
                "used": 0.0,
                "total": float(self.balance.quote),
            },
        }

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Decimal | None = None,
    ) -> dict[str, Any]:
        """Create a simulated order."""
        if symbol != self.symbol:
            raise ValueError(f"Invalid symbol: {symbol}")

        self.order_id_counter += 1
        order_id = f"sim_{self.order_id_counter}"

        if order_type == "market":
            execution_price = self._get_execution_price(side)
        elif order_type == "limit":
            if price is None:
                raise ValueError("Limit orders require a price")
            execution_price = price
        else:
            raise ValueError(f"Invalid order type: {order_type}")

        order = SimulatedOrder(
            id=order_id,
            symbol=symbol,
            side=OrderSide(side),
            order_type=OrderType(order_type),
            price=execution_price,
            amount=amount,
        )

        if order_type == "market":
            await self._execute_order(order)
        else:
            self.orders[order_id] = order
            await self._check_limit_orders()

        return self._order_to_dict(order)

    def _get_execution_price(self, side: str) -> Decimal:
        if side == "buy":
            return self.current_price * (Decimal("1") + self.slippage)
        else:
            return self.current_price * (Decimal("1") - self.slippage)

    async def _execute_order(self, order: SimulatedOrder) -> None:
        try:
            if order.side == OrderSide.BUY:
                fee = (
                    order.amount * self.taker_fee
                    if order.order_type == OrderType.MARKET
                    else order.amount * self.maker_fee
                )
                self.balance.execute_buy(order.amount, order.price)
                self.balance.base -= fee

            elif order.side == OrderSide.SELL:
                self.balance.execute_sell(order.amount, order.price)
                fee = (order.amount * order.price) * (
                    self.taker_fee if order.order_type == OrderType.MARKET else self.maker_fee
                )
                self.balance.quote -= fee

            order.filled = order.amount
            order.status = OrderStatus.CLOSED

            self.trade_history.append(
                {
                    "order_id": order.id,
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "price": float(order.price),
                    "amount": float(order.amount),
                    "fee": float(fee) if order.side == OrderSide.BUY else float(fee),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        except ValueError as e:
            order.status = OrderStatus.CANCELED
            raise Exception(f"Order execution failed: {e}") from e

    async def _check_limit_orders(self) -> None:
        orders_to_execute = []

        for _order_id, order in self.orders.items():
            if order.status != OrderStatus.OPEN:
                continue

            should_execute = False

            if order.side == OrderSide.BUY and self.current_price <= order.price:
                should_execute = True
            elif order.side == OrderSide.SELL and self.current_price >= order.price:
                should_execute = True

            if should_execute:
                orders_to_execute.append(order)

        for order in orders_to_execute:
            try:
                await self._execute_order(order)
            except Exception as e:
                _logger.debug("Limit order execution failed: %s", e)

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        if order_id not in self.orders:
            raise ValueError(f"Order not found: {order_id}")

        order = self.orders[order_id]
        if order.status != OrderStatus.OPEN:
            raise ValueError(f"Order is not open: {order_id}")

        order.status = OrderStatus.CANCELED
        return self._order_to_dict(order)

    def get_order(self, order_id: str) -> dict[str, Any]:
        if order_id not in self.orders:
            raise ValueError(f"Order not found: {order_id}")
        return self._order_to_dict(self.orders[order_id])

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        open_orders = [
            order
            for order in self.orders.values()
            if order.status == OrderStatus.OPEN and (symbol is None or order.symbol == symbol)
        ]
        return [self._order_to_dict(order) for order in open_orders]

    def _order_to_dict(self, order: SimulatedOrder) -> dict[str, Any]:
        return {
            "id": order.id,
            "symbol": order.symbol,
            "type": order.order_type.value,
            "side": order.side.value,
            "price": float(order.price),
            "amount": float(order.amount),
            "filled": float(order.filled),
            "remaining": float(order.remaining),
            "status": order.status.value,
            "timestamp": order.timestamp.isoformat(),
        }

    def get_portfolio_value(self) -> Decimal:
        base_value = self.balance.base * self.current_price
        return self.balance.quote + base_value

    def get_trade_history(self) -> list[dict[str, Any]]:
        return self.trade_history.copy()

    def reset(self, initial_balance_quote: Decimal = Decimal("10000")) -> None:
        self.balance = SimulatedBalance(base=Decimal("0"), quote=initial_balance_quote)
        self.orders.clear()
        self.trade_history.clear()
        self.order_id_counter = 0
