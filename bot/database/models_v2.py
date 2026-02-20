"""
SQLAlchemy v2.0 models for multi-strategy trading.

Adds tables for unified strategy management, positions, signals,
and DCA-specific deal tracking on top of the existing v1.0 schema.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DECIMAL,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models import Base

# =============================================================================
# v2.0 Enums
# =============================================================================

_strategy_type_v2 = Enum(
    "smc",
    "trend_follower",
    "grid",
    "dca",
    "hybrid",
    name="strategy_type_v2",
)

_strategy_state = Enum(
    "idle",
    "starting",
    "active",
    "paused",
    "stopping",
    "stopped",
    "error",
    name="strategy_state",
)

_signal_direction = Enum("long", "short", name="signal_direction")

_position_status = Enum("open", "closed", name="position_status_v2")

_exit_reason = Enum(
    "take_profit",
    "stop_loss",
    "trailing_stop",
    "breakeven",
    "partial_close",
    "manual",
    "signal_reversed",
    "risk_limit",
    "timeout",
    name="exit_reason",
)

_dca_deal_status = Enum("active", "completed", "cancelled", name="dca_deal_status")

_dca_order_status = Enum("pending", "filled", "cancelled", name="dca_order_status")


# =============================================================================
# Strategy Instance
# =============================================================================


class Strategy(Base):
    """
    Registered strategy instance.

    Tracks configuration, state, and lifetime metrics for each
    strategy managed by BotOrchestrator v2.0.
    """

    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    strategy_type: Mapped[str] = mapped_column(_strategy_type_v2, nullable=False)
    bot_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("bots.id"), nullable=True)
    state: Mapped[str] = mapped_column(_strategy_state, default="idle", nullable=False)
    config_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metrics
    total_signals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    executed_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    profitable_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), default=Decimal("0"), nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    positions: Mapped[list["Position"]] = relationship("Position", back_populates="strategy")
    signals: Mapped[list["Signal"]] = relationship("Signal", back_populates="strategy")
    dca_deals: Mapped[list["DCADeal"]] = relationship("DCADeal", back_populates="strategy")

    __table_args__ = (
        Index("idx_strategy_type", "strategy_type"),
        Index("idx_strategy_state", "state"),
        Index("idx_strategy_bot", "bot_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Strategy(id={self.id}, strategy_id={self.strategy_id}, "
            f"type={self.strategy_type}, state={self.state})>"
        )


# =============================================================================
# Position
# =============================================================================


class Position(Base):
    """
    Unified position tracking across all strategies.

    Records the full lifecycle from open to close with PnL.
    """

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    position_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    strategy_db_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(_signal_direction, nullable=False)
    status: Mapped[str] = mapped_column(_position_status, default="open", nullable=False)

    # Prices
    entry_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    exit_price: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)
    stop_loss: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    take_profit: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)

    # Size and PnL
    size: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    realized_pnl: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)
    fee_total: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), default=Decimal("0"), nullable=False)

    # Exit info
    exit_reason: Mapped[str | None] = mapped_column(_exit_reason, nullable=True)

    # Signal reference
    signal_db_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("signals.id"), nullable=True
    )

    # Timestamps
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="positions")
    signal: Mapped["Signal | None"] = relationship("Signal", back_populates="position")

    __table_args__ = (
        Index("idx_position_strategy", "strategy_db_id"),
        Index("idx_position_status", "status"),
        Index("idx_position_symbol", "symbol"),
        Index("idx_position_opened", "opened_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Position(id={self.id}, position_id={self.position_id}, "
            f"direction={self.direction}, status={self.status})>"
        )


# =============================================================================
# Signal
# =============================================================================


class Signal(Base):
    """
    Signal history from all strategies.

    Records every signal generated, whether acted upon or not.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_db_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(_signal_direction, nullable=False)

    # Signal details
    entry_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    stop_loss: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    take_profit: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    risk_reward_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    signal_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Execution tracking
    was_executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Metadata (JSON)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="signals")
    position: Mapped["Position | None"] = relationship(
        "Position", back_populates="signal", uselist=False
    )

    __table_args__ = (
        Index("idx_signal_strategy", "strategy_db_id"),
        Index("idx_signal_symbol", "symbol"),
        Index("idx_signal_generated", "generated_at"),
        Index("idx_signal_executed", "was_executed"),
    )

    def __repr__(self) -> str:
        return (
            f"<Signal(id={self.id}, direction={self.direction}, "
            f"confidence={self.confidence}, executed={self.was_executed})>"
        )


# =============================================================================
# DCA Deal
# =============================================================================


class DCADeal(Base):
    """
    DCA deal tracking - groups multiple DCA orders into a single deal.

    A deal represents a complete DCA cycle: base order + safety orders → take profit.
    """

    __tablename__ = "dca_deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_db_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("strategies.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    direction: Mapped[str] = mapped_column(_signal_direction, nullable=False)
    status: Mapped[str] = mapped_column(_dca_deal_status, default="active", nullable=False)

    # Deal metrics
    base_order_size: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    safety_order_size: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    max_safety_orders: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_safety_orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Pricing
    average_entry_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    take_profit_price: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)
    current_price: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)

    # Totals
    total_invested: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), default=Decimal("0"), nullable=False
    )
    total_quantity: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), default=Decimal("0"), nullable=False
    )
    realized_pnl: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)

    # Timestamps
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="dca_deals")
    dca_orders: Mapped[list["DCAOrder"]] = relationship("DCAOrder", back_populates="deal")

    __table_args__ = (
        Index("idx_dca_deal_strategy", "strategy_db_id"),
        Index("idx_dca_deal_status", "status"),
        Index("idx_dca_deal_symbol", "symbol"),
    )

    def __repr__(self) -> str:
        return (
            f"<DCADeal(id={self.id}, symbol={self.symbol}, "
            f"status={self.status}, safety_orders={self.filled_safety_orders}/{self.max_safety_orders})>"
        )


# =============================================================================
# DCA Order
# =============================================================================


class DCAOrder(Base):
    """
    Individual DCA order within a deal (base order or safety order).
    """

    __tablename__ = "dca_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int] = mapped_column(Integer, ForeignKey("dca_deals.id"), nullable=False)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_base_order: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Order details
    side: Mapped[str] = mapped_column(Enum("buy", "sell", name="dca_order_side"), nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    filled_amount: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), default=Decimal("0"), nullable=False
    )
    status: Mapped[str] = mapped_column(_dca_order_status, default="pending", nullable=False)

    # Exchange reference
    exchange_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Deviation from base price (%)
    deviation_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    deal: Mapped["DCADeal"] = relationship("DCADeal", back_populates="dca_orders")

    __table_args__ = (
        Index("idx_dca_order_deal", "deal_id"),
        Index("idx_dca_order_status", "status"),
        Index("idx_dca_order_exchange", "exchange_order_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<DCAOrder(id={self.id}, deal_id={self.deal_id}, "
            f"order_number={self.order_number}, status={self.status})>"
        )


# =============================================================================
# DCA Signal
# =============================================================================


class DCASignal(Base):
    """
    DCA-specific signal that triggers deal creation or safety order placement.
    """

    __tablename__ = "dca_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    deal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("dca_deals.id"), nullable=True)
    signal_type: Mapped[str] = mapped_column(
        Enum("start_deal", "safety_order", "take_profit", "stop_loss", name="dca_signal_type"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(_signal_direction, nullable=False)

    # Signal context
    trigger_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    target_price: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    source_strategy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Execution
    was_executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("idx_dca_signal_deal", "deal_id"),
        Index("idx_dca_signal_type", "signal_type"),
        Index("idx_dca_signal_generated", "generated_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DCASignal(id={self.id}, type={self.signal_type}, "
            f"direction={self.direction}, executed={self.was_executed})>"
        )
