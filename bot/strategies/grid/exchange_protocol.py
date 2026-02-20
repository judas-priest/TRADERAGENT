"""IGridExchange — Protocol for grid strategy exchange adapters.

Defines the interface that both real exchange clients (e.g., Bybit)
and simulated exchanges (e.g., MarketSimulator) must implement
to work with the grid trading strategy.
"""

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IGridExchange(Protocol):
    """Abstraction for exchange operations used by grid strategy."""

    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: Decimal,
        price: Decimal | None = None,
    ) -> dict[str, Any]:
        ...

    async def cancel_order(
        self,
        order_id: str,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        ...

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        ...

    async def fetch_balance(self) -> dict[str, Any]:
        ...
