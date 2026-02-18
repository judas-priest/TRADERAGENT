"""
SQLAlchemy models for the trading bot database.
Defines tables for bots, credentials, orders, trades, and logs.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

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
    min_deposit: Mapped[Decimal] = mapped_column(DECIMAL(20, 8), default=Decimal("100"), nullable=False)
    expected_pnl_pct: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 4), nullable=True)
    recommended_pairs: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON array
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    copy_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
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
