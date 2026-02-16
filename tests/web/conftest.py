"""
Test fixtures for Web API tests.
"""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.database.models import Base
from web.backend.app import create_app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """Create in-memory SQLite engine for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
def mock_orchestrator():
    """Create a mock BotOrchestrator."""
    orch = MagicMock()
    orch.get_status.return_value = {
        "bot_name": "test_bot",
        "strategy_type": "grid",
        "symbol": "BTC/USDT",
        "status": "running",
        "dry_run": False,
        "positions": [],
        "metrics": {
            "total_trades": 42,
            "total_pnl": 1234.56,
            "unrealized_pnl": 100.0,
            "active_positions": 2,
            "open_orders": 5,
            "total_fees": 12.34,
            "win_rate": 0.65,
            "winning_trades": 27,
            "losing_trades": 15,
            "uptime_seconds": 3600,
        },
        "config": {"name": "test_bot"},
    }
    orch.start = AsyncMock()
    orch.stop = AsyncMock()
    orch.pause = AsyncMock()
    orch.resume = AsyncMock()
    orch.emergency_stop = AsyncMock()
    return orch


@pytest.fixture
def mock_orchestrators(mock_orchestrator):
    """Create orchestrators dict."""
    return {"test_bot": mock_orchestrator}


@pytest.fixture
def mock_db_manager(db_engine):
    """Create a mock DatabaseManager that uses test engine."""
    from contextlib import asynccontextmanager

    manager = MagicMock()
    manager._engine = db_engine

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def mock_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    manager.session = mock_session
    return manager


@pytest_asyncio.fixture
async def test_app(mock_db_manager, mock_orchestrators):
    """Create test FastAPI application."""
    app = create_app()

    # Override lifespan state
    app.state.db_manager = mock_db_manager
    app.state.orchestrators = mock_orchestrators
    app.state.config_manager = MagicMock()

    return app


@pytest_asyncio.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Create authenticated test client (registers + logs in)."""
    # Register first user (auto-admin)
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )

    # Login
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "testpassword123"},
    )
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
