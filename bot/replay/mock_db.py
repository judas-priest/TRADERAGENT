"""
In-memory SQLite database for replay.

Creates an async SQLite engine (via ``aiosqlite``) with all project tables
so the ``BotOrchestrator`` can save/load state without PostgreSQL.
"""

import tempfile

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.manager import DatabaseManager
from bot.database.models import Base


async def create_mock_db() -> DatabaseManager:
    """
    Build and return a ``DatabaseManager`` backed by a temporary SQLite DB.

    All tables from ``Base.metadata`` (including ``BotStateSnapshot``) are
    created automatically.  The returned manager is fully initialized and
    ready to use.
    """
    # Import models to ensure all tables are registered on Base
    import bot.database.models  # noqa: F401

    # Use a temp file instead of :memory: to avoid StaticPool concurrency issues
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    url = f"sqlite+aiosqlite:///{db_path}"

    # Create a real DatabaseManager (calls __init__ properly)
    db = DatabaseManager(
        database_url=url,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=False,
        echo=False,
    )

    # Create engine and session factory
    engine = create_async_engine(url, echo=False)
    db._engine = engine
    db._session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Store path for cleanup
    db._tmp_db_path = db_path  # type: ignore[attr-defined]

    return db
