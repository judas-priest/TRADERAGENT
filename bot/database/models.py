"""
SQLAlchemy models for the trading bot database.

All models in a single file:
- v1.0: ExchangeCredential, Bot, Order, Trade, GridLevel, DCAHistory, StrategyTemplate, BotLog
- v2.0: Strategy, Position, Signal, DCADeal, DCAOrder, DCASignal
- State: BotStateSnapshot
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DECIMAL,
    BigInteger,
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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""

    pass


class ExchangeCredential(Base):
    """Store encrypted exchange API credentials"""

    __tablename__ = "exchange_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    exchange_id: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    bots: Mapped[list["Bot"]] = relationship("Bot", back_populates="credentials")

    def __repr__(self) -> str:
        return f"<ExchangeCredential(id={self.id}, name={self.name}, exchange={self.exchange_id})>"


class Bot(Base):
    """Store bot configurations and state"""

    __tablename__ = "bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    credentials_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exchange_credentials.id"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy: Mapped[str] = mapped_column(
        Enum("grid", "dca", "hybrid", name="strategy_type"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum("running", "paused", "stopped", "error", name="bot_status"),
        default="stopped",
        nullable=False,
    )
    config_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    config_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    total_invested: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), default=Decimal("0"), nullable=False
    )
    current_profit: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), default=Decimal("0"), nullable=False
    )
    total_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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
    credentials: Mapped["ExchangeCredential"] = relationship(
        "ExchangeCredential", back_populates="bots"
    )
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="bot")
    trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="bot")
    grid_levels: Mapped[list["GridLevel"]] = relationship("GridLevel", back_populates="bot")
    dca_history: Mapped[list["DCAHistory"]] = relationship("DCAHistory", back_populates="bot")
    logs: Mapped[list["BotLog"]] = relationship("BotLog", back_populates="bot")

    # Indexes
    __table_args__ = (
        Index("idx_bot_status", "status"),
        Index("idx_bot_symbol", "symbol"),
    )

    def __repr__(self) -> str:
        return f"<Bot(id={self.id}, name={self.name}, symbol={self.symbol}, status={self.status})>"


class Order(Base):
    """Store order information"""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"), nullable=False)
    exchange_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    order_type: Mapped[str] = mapped_column(
        Enum("limit", "market", name="order_type"), nullable=False
    )
    side: Mapped[str] = mapped_column(Enum("buy", "sell", name="order_side"), nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    filled: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("open", "closed", "canceled", "expired", "rejected", name="order_status"),
        default="open",
        nullable=False,
    )
    grid_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_dca: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    filled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    bot: Mapped["Bot"] = relationship("Bot", back_populates="orders")

    # Indexes
    __table_args__ = (
        Index("idx_order_bot_status", "bot_id", "status"),
        Index("idx_order_exchange_id", "exchange_order_id"),
        Index("idx_order_symbol", "symbol"),
    )

    def __repr__(self) -> str:
        return (
            f"<Order(id={self.id}, exchange_id={self.exchange_order_id}, "
            f"side={self.side}, status={self.status})>"
        )


class Trade(Base):
    """Store executed trade information"""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"), nullable=False)
    exchange_trade_id: Mapped[str] = mapped_column(String(100), nullable=False)
    exchange_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(Enum("buy", "sell", name="trade_side"), nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), default=Decimal("0"), nullable=False)
    fee_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    profit: Mapped[Decimal | None] = mapped_column(DECIMAL(20, 8), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    bot: Mapped["Bot"] = relationship("Bot", back_populates="trades")

    # Indexes
    __table_args__ = (
        Index("idx_trade_bot", "bot_id"),
        Index("idx_trade_exchange_id", "exchange_trade_id"),
        Index("idx_trade_executed_at", "executed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Trade(id={self.id}, exchange_id={self.exchange_trade_id}, "
            f"side={self.side}, amount={self.amount})>"
        )


class GridLevel(Base):
    """Store grid trading levels"""

    __tablename__ = "grid_levels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    buy_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sell_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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
    bot: Mapped["Bot"] = relationship("Bot", back_populates="grid_levels")

    # Indexes
    __table_args__ = (
        Index("idx_grid_bot_level", "bot_id", "level", unique=True),
        Index("idx_grid_bot_active", "bot_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<GridLevel(id={self.id}, bot_id={self.bot_id}, level={self.level}, price={self.price})>"


class DCAHistory(Base):
    """Store DCA (Dollar Cost Averaging) history"""

    __tablename__ = "dca_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"), nullable=False)
    trigger_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    buy_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    average_price: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), nullable=False)
    dca_step: Mapped[int] = mapped_column(Integer, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    bot: Mapped["Bot"] = relationship("Bot", back_populates="dca_history")

    # Indexes
    __table_args__ = (
        Index("idx_dca_bot", "bot_id"),
        Index("idx_dca_executed_at", "executed_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<DCAHistory(id={self.id}, bot_id={self.bot_id}, "
            f"step={self.dca_step}, price={self.buy_price})>"
        )


class StrategyTemplate(Base):
    """Store strategy templates for the marketplace."""

    __tablename__ = "strategy_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    min_deposit: Mapped[Decimal] = mapped_column(
        DECIMAL(20, 8), default=Decimal("100"), nullable=False
    )
    expected_pnl_pct: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 4), nullable=True)
    recommended_pairs: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON array
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    copy_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_template_strategy_type", "strategy_type"),
        Index("idx_template_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<StrategyTemplate(id={self.id}, name={self.name}, type={self.strategy_type})>"


class BotLog(Base):
    """Store bot activity logs"""

    __tablename__ = "bot_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(Integer, ForeignKey("bots.id"), nullable=False)
    level: Mapped[str] = mapped_column(
        Enum("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", name="log_level"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    # Relationships
    bot: Mapped["Bot"] = relationship("Bot", back_populates="logs")

    # Indexes
    __table_args__ = (
        Index("idx_log_bot_level", "bot_id", "level"),
        Index("idx_log_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<BotLog(id={self.id}, bot_id={self.bot_id}, level={self.level})>"


# =============================================================================
# Bot State Snapshot (crash recovery)
# =============================================================================


class BotStateSnapshot(Base):
    """Persisted bot state for crash recovery."""

    __tablename__ = "bot_state_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    bot_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    grid_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    dca_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    trend_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    hybrid_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<BotStateSnapshot(bot_name={self.bot_name}, saved_at={self.saved_at})>"


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
# v2.0 Strategy Instance
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
# v2.0 Position
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
# v2.0 Signal
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
# v2.0 DCA Deal
# =============================================================================


class DCADeal(Base):
    """
    DCA deal tracking - groups multiple DCA orders into a single deal.

    A deal represents a complete DCA cycle: base order + safety orders -> take profit.
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
# v2.0 DCA Order
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
# v2.0 DCA Signal
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
