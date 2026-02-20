"""
SQLAlchemy model for bot state snapshots.
Enables state persistence across restarts.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.models import Base


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
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<BotStateSnapshot(bot_name={self.bot_name}, saved_at={self.saved_at})>"
