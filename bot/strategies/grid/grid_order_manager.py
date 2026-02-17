"""
GridOrderManager — Manages grid order lifecycle for TRADERAGENT v2.0.

Responsibilities:
- Place initial grid orders via ExchangeAPIClient
- Handle order fills and place automatic counter-orders
- Process partial fills
- Rebalance grid on price movement
- Track profit/loss per grid cycle
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any

import structlog

from .grid_calculator import (
    GridCalculator,
    GridConfig,
    GridLevel,
    GridSpacing,
)

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums & Data Structures
# =============================================================================


class OrderStatus(str, Enum):
    """Grid order lifecycle status."""

    PENDING = "pending"  # created, not yet placed
    OPEN = "open"  # placed on exchange
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class GridOrderState:
    """
    Tracks the state of a single grid order throughout its lifecycle.

    Links GridLevel (calculator output) to exchange order state.
    """

    id: str  # internal unique ID
    grid_level: GridLevel
    exchange_order_id: str | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_amount: Decimal = Decimal("0")
    filled_price: Decimal = Decimal("0")
    remaining_amount: Decimal = Decimal("0")
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)

    @property
    def fill_pct(self) -> float:
        if self.grid_level.amount == 0:
            return 0.0
        return float(self.filled_amount / self.grid_level.amount) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "exchange_order_id": self.exchange_order_id,
            "status": self.status.value,
            "side": self.grid_level.side,
            "price": str(self.grid_level.price),
            "amount": str(self.grid_level.amount),
            "filled_amount": str(self.filled_amount),
            "filled_price": str(self.filled_price),
            "fill_pct": round(self.fill_pct, 2),
        }


@dataclass
class GridCycle:
    """Tracks a buy→sell or sell→buy cycle for profit calculation."""

    cycle_id: str
    buy_order_id: str
    sell_order_id: str | None = None
    buy_price: Decimal = Decimal("0")
    sell_price: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")
    profit: Decimal = Decimal("0")
    completed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# Grid Order Manager
# =============================================================================


class GridOrderManager:
    """
    Manages grid order placement, fills, counter-orders, and rebalancing.

    Uses ExchangeAPIClient (via async callback interface) for exchange operations
    to keep the manager testable without real API calls.

    Lifecycle:
        1. initialize_grid(config, current_price) — calculate & place initial orders
        2. on_order_update(exchange_data) — handle fill/partial events
        3. rebalance(current_price, config) — adjust grid on price movement
        4. cancel_all() — shutdown
    """

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol

        # Order tracking
        self._orders: dict[str, GridOrderState] = {}  # internal_id -> state
        self._exchange_to_internal: dict[str, str] = {}  # exchange_id -> internal_id

        # Profit tracking
        self._cycles: list[GridCycle] = []
        self._total_realized_pnl = Decimal("0")

        # Statistics
        self._total_orders_placed = 0
        self._total_fills = 0
        self._partial_fills = 0
        self._failed_orders = 0

        # Current grid config
        self._config: GridConfig | None = None
        self._current_levels: list[Decimal] = []

        logger.info("GridOrderManager created", symbol=symbol)

    # =================================================================
    # Initialization
    # =================================================================

    def calculate_initial_orders(
        self, config: GridConfig, current_price: Decimal
    ) -> list[GridOrderState]:
        """
        Calculate initial grid orders without placing them.

        Args:
            config: Grid configuration.
            current_price: Current market price.

        Returns:
            List of GridOrderState objects in PENDING status.
        """
        config.validate()
        self._config = config

        grid_levels = GridCalculator.calculate_full_grid(config, current_price)
        self._current_levels = GridCalculator.calculate_levels(
            config.upper_price, config.lower_price, config.num_levels, config.spacing
        )

        order_states = []
        for gl in grid_levels:
            state = GridOrderState(
                id=self._generate_id(),
                grid_level=gl,
                remaining_amount=gl.amount,
            )
            self._orders[state.id] = state
            order_states.append(state)

        logger.info(
            "Initial grid orders calculated",
            total=len(order_states),
            buys=sum(1 for o in order_states if o.grid_level.side == "buy"),
            sells=sum(1 for o in order_states if o.grid_level.side == "sell"),
        )

        return order_states

    def register_exchange_order(
        self, internal_id: str, exchange_order_id: str
    ) -> None:
        """
        Register an exchange order ID after successful placement.

        Args:
            internal_id: Internal GridOrderState ID.
            exchange_order_id: Exchange-assigned order ID.
        """
        if internal_id not in self._orders:
            logger.warning("Unknown internal order", internal_id=internal_id)
            return

        state = self._orders[internal_id]
        state.exchange_order_id = exchange_order_id
        state.status = OrderStatus.OPEN
        state.updated_at = datetime.now(timezone.utc)
        self._exchange_to_internal[exchange_order_id] = internal_id
        self._total_orders_placed += 1

        logger.debug(
            "Order registered",
            internal_id=internal_id,
            exchange_id=exchange_order_id,
            side=state.grid_level.side,
            price=str(state.grid_level.price),
        )

    def mark_order_failed(self, internal_id: str, reason: str = "") -> None:
        """Mark an order as failed (e.g., exchange rejected it)."""
        if internal_id not in self._orders:
            return
        state = self._orders[internal_id]
        state.status = OrderStatus.FAILED
        state.updated_at = datetime.now(timezone.utc)
        self._failed_orders += 1
        logger.warning(
            "Order marked as failed",
            internal_id=internal_id,
            reason=reason,
        )

    # =================================================================
    # Order Fill Handling
    # =================================================================

    def on_order_filled(
        self,
        exchange_order_id: str,
        filled_price: Decimal,
        filled_amount: Decimal,
    ) -> GridOrderState | None:
        """
        Handle a fully filled order and generate a counter-order.

        Args:
            exchange_order_id: Exchange order ID that was filled.
            filled_price: Price at which the order was filled.
            filled_amount: Amount that was filled.

        Returns:
            New GridOrderState for the counter-order (PENDING), or None.
        """
        internal_id = self._exchange_to_internal.get(exchange_order_id)
        if not internal_id:
            logger.warning("Unknown exchange order filled", exchange_id=exchange_order_id)
            return None

        state = self._orders[internal_id]
        state.status = OrderStatus.FILLED
        state.filled_amount = filled_amount
        state.filled_price = filled_price
        state.remaining_amount = Decimal("0")
        state.updated_at = datetime.now(timezone.utc)
        self._total_fills += 1

        logger.info(
            "Order fully filled",
            exchange_id=exchange_order_id,
            side=state.grid_level.side,
            price=str(filled_price),
            amount=str(filled_amount),
        )

        # Generate counter-order
        counter = self._create_counter_order(state, filled_price, filled_amount)

        # Track profit cycle
        self._track_cycle(state, counter)

        return counter

    def on_order_partially_filled(
        self,
        exchange_order_id: str,
        filled_price: Decimal,
        filled_amount: Decimal,
        remaining_amount: Decimal,
    ) -> None:
        """
        Handle a partial fill event.

        Updates order state but does NOT generate a counter-order yet.
        Counter-order is created only when fully filled.

        Args:
            exchange_order_id: Exchange order ID.
            filled_price: Average fill price so far.
            filled_amount: Total filled amount so far.
            remaining_amount: Amount still pending.
        """
        internal_id = self._exchange_to_internal.get(exchange_order_id)
        if not internal_id:
            logger.warning("Unknown exchange order partial fill", exchange_id=exchange_order_id)
            return

        state = self._orders[internal_id]
        state.status = OrderStatus.PARTIALLY_FILLED
        state.filled_amount = filled_amount
        state.filled_price = filled_price
        state.remaining_amount = remaining_amount
        state.updated_at = datetime.now(timezone.utc)
        self._partial_fills += 1

        logger.info(
            "Order partially filled",
            exchange_id=exchange_order_id,
            side=state.grid_level.side,
            filled=str(filled_amount),
            remaining=str(remaining_amount),
            fill_pct=round(state.fill_pct, 2),
        )

    # =================================================================
    # Counter-Order Logic
    # =================================================================

    def _create_counter_order(
        self,
        filled_order: GridOrderState,
        filled_price: Decimal,
        filled_amount: Decimal,
    ) -> GridOrderState:
        """
        Create a counter-order after a fill.

        Buy fill → Sell counter-order (at price + profit margin)
        Sell fill → Buy counter-order (at price - profit margin)
        """
        profit_margin = self._config.profit_per_grid if self._config else Decimal("0.005")

        if filled_order.grid_level.side == "buy":
            counter_price = filled_price * (Decimal("1") + profit_margin)
            counter_side = "sell"
            counter_amount = filled_amount  # sell what was bought
        else:
            counter_price = filled_price * (Decimal("1") - profit_margin)
            counter_side = "buy"
            # Buy with same quote value
            counter_amount = (filled_amount * filled_price / counter_price).quantize(
                Decimal("0.001"), rounding=ROUND_HALF_UP
            )

        counter_price = counter_price.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        counter_level = GridLevel(
            index=filled_order.grid_level.index,
            price=counter_price,
            side=counter_side,
            amount=counter_amount,
        )

        counter_state = GridOrderState(
            id=self._generate_id(),
            grid_level=counter_level,
            remaining_amount=counter_amount,
        )
        self._orders[counter_state.id] = counter_state

        logger.info(
            "Counter-order created",
            original_side=filled_order.grid_level.side,
            counter_side=counter_side,
            counter_price=str(counter_price),
            counter_amount=str(counter_amount),
        )

        return counter_state

    # =================================================================
    # Profit Tracking
    # =================================================================

    def _track_cycle(
        self,
        filled_order: GridOrderState,
        counter_order: GridOrderState,
    ) -> None:
        """Track buy→sell profit cycle."""
        if filled_order.grid_level.side == "buy":
            # Buy filled, sell counter pending — cycle starts
            cycle = GridCycle(
                cycle_id=self._generate_id(),
                buy_order_id=filled_order.id,
                sell_order_id=counter_order.id,
                buy_price=filled_order.filled_price,
                amount=filled_order.filled_amount,
            )
            self._cycles.append(cycle)
        elif filled_order.grid_level.side == "sell":
            # Sell filled — find matching open cycle to complete
            for cycle in reversed(self._cycles):
                if not cycle.completed and cycle.sell_order_id is not None:
                    # Check if THIS sell is the counter from a previous buy
                    if cycle.sell_order_id == filled_order.id:
                        cycle.sell_price = filled_order.filled_price
                        cycle.profit = (
                            (cycle.sell_price - cycle.buy_price) * cycle.amount
                        )
                        cycle.completed = True
                        self._total_realized_pnl += cycle.profit

                        logger.info(
                            "Grid cycle completed",
                            buy_price=str(cycle.buy_price),
                            sell_price=str(cycle.sell_price),
                            profit=str(cycle.profit),
                        )
                        break
            else:
                # Sell filled without matching buy cycle (initial sell)
                cycle = GridCycle(
                    cycle_id=self._generate_id(),
                    buy_order_id=counter_order.id,  # buy counter pending
                    sell_order_id=filled_order.id,
                    sell_price=filled_order.filled_price,
                    amount=filled_order.filled_amount,
                )
                self._cycles.append(cycle)

    # =================================================================
    # Rebalancing
    # =================================================================

    def get_orders_to_cancel(self) -> list[GridOrderState]:
        """Get all active orders that should be cancelled for rebalancing."""
        return [o for o in self._orders.values() if o.is_active]

    def mark_order_cancelled(self, internal_id: str) -> None:
        """Mark an order as cancelled after exchange cancellation."""
        if internal_id not in self._orders:
            return
        state = self._orders[internal_id]
        if state.exchange_order_id:
            self._exchange_to_internal.pop(state.exchange_order_id, None)
        state.status = OrderStatus.CANCELLED
        state.updated_at = datetime.now(timezone.utc)

    def rebalance(
        self,
        new_config: GridConfig,
        current_price: Decimal,
    ) -> tuple[list[GridOrderState], list[GridOrderState]]:
        """
        Rebalance the grid with a new configuration.

        Returns orders to cancel and new orders to place.

        Args:
            new_config: Updated grid configuration.
            current_price: Current market price.

        Returns:
            Tuple of (orders_to_cancel, new_orders_to_place).
        """
        orders_to_cancel = self.get_orders_to_cancel()

        # Mark cancelled
        for o in orders_to_cancel:
            o.status = OrderStatus.CANCELLED
            o.updated_at = datetime.now(timezone.utc)
            if o.exchange_order_id:
                self._exchange_to_internal.pop(o.exchange_order_id, None)

        # Calculate new grid
        new_orders = self.calculate_initial_orders(new_config, current_price)

        logger.info(
            "Grid rebalanced",
            cancelled=len(orders_to_cancel),
            new_orders=len(new_orders),
            current_price=str(current_price),
        )

        return orders_to_cancel, new_orders

    # =================================================================
    # Query Methods
    # =================================================================

    @property
    def active_orders(self) -> list[GridOrderState]:
        """Get all active (open or partially filled) orders."""
        return [o for o in self._orders.values() if o.is_active]

    @property
    def filled_orders(self) -> list[GridOrderState]:
        """Get all filled orders."""
        return [o for o in self._orders.values() if o.status == OrderStatus.FILLED]

    @property
    def pending_orders(self) -> list[GridOrderState]:
        """Get all pending (not yet placed) orders."""
        return [o for o in self._orders.values() if o.status == OrderStatus.PENDING]

    @property
    def total_realized_pnl(self) -> Decimal:
        """Total realized profit/loss from completed cycles."""
        return self._total_realized_pnl

    @property
    def completed_cycles(self) -> list[GridCycle]:
        """Get completed buy→sell cycles."""
        return [c for c in self._cycles if c.completed]

    def get_order_by_exchange_id(self, exchange_order_id: str) -> GridOrderState | None:
        """Look up order state by exchange order ID."""
        internal_id = self._exchange_to_internal.get(exchange_order_id)
        if internal_id:
            return self._orders.get(internal_id)
        return None

    def get_statistics(self) -> dict[str, Any]:
        """Get comprehensive order manager statistics."""
        active = self.active_orders
        buy_active = sum(1 for o in active if o.grid_level.side == "buy")
        sell_active = sum(1 for o in active if o.grid_level.side == "sell")

        return {
            "symbol": self.symbol,
            "total_orders": len(self._orders),
            "active_orders": len(active),
            "active_buys": buy_active,
            "active_sells": sell_active,
            "filled_orders": len(self.filled_orders),
            "pending_orders": len(self.pending_orders),
            "failed_orders": self._failed_orders,
            "total_orders_placed": self._total_orders_placed,
            "total_fills": self._total_fills,
            "partial_fills": self._partial_fills,
            "completed_cycles": len(self.completed_cycles),
            "total_realized_pnl": str(self._total_realized_pnl),
            "grid_config": {
                "spacing": self._config.spacing.value if self._config else None,
                "num_levels": self._config.num_levels if self._config else None,
            },
        }

    # =================================================================
    # Private Helpers
    # =================================================================

    @staticmethod
    def _generate_id() -> str:
        return str(uuid.uuid4())[:12]
