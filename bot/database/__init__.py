"""Database management modules"""

from bot.database.backup import BackupInfo, BackupManager
from bot.database.manager import DatabaseManager
from bot.database.migrations import MigrationInfo, MigrationRunner, MigrationStatus
from bot.database.models import (
    Base,
    Bot,
    BotLog,
    BotStateSnapshot,
    DCADeal,
    DCAHistory,
    DCAOrder,
    DCASignal,
    ExchangeCredential,
    GridLevel,
    Order,
    Position,
    Signal,
    Strategy,
    StrategyTemplate,
    Trade,
)

__all__ = [
    "DatabaseManager",
    "Base",
    # v1.0 models
    "Bot",
    "ExchangeCredential",
    "Order",
    "Trade",
    "GridLevel",
    "DCAHistory",
    "StrategyTemplate",
    "BotLog",
    # State persistence
    "BotStateSnapshot",
    # v2.0 models
    "Strategy",
    "Position",
    "Signal",
    "DCADeal",
    "DCAOrder",
    "DCASignal",
    # Utilities
    "MigrationRunner",
    "MigrationInfo",
    "MigrationStatus",
    "BackupManager",
    "BackupInfo",
]
