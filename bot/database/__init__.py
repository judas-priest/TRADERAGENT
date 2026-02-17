"""Database management modules"""

from bot.database.backup import BackupInfo, BackupManager
from bot.database.manager import DatabaseManager
from bot.database.migrations import MigrationInfo, MigrationRunner, MigrationStatus
from bot.database.models import (
    Base,
    Bot,
    BotLog,
    DCAHistory,
    ExchangeCredential,
    GridLevel,
    Order,
    Trade,
)
from bot.database.models_state import BotStateSnapshot
from bot.database.models_v2 import (
    DCADeal,
    DCAOrder,
    DCASignal,
    Position,
    Signal,
    Strategy,
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
