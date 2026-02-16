"""
Shared fixtures for load & stress tests.

All tests run WITHOUT external services (in-memory SQLite, mock WebSocket, mock exchange).
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from bot.database.models import Base, Bot, ExchangeCredential, Order, Trade
from bot.strategies.base import BaseSignal, SignalDirection
from web.backend.app import create_app
from web.backend.auth.models import User, UserSession  # noqa: F401 — ensure tables exist


# SQLite BigInteger override (same as bot/tests/conftest.py)
@compiles(BigInteger, "sqlite")
def _compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_ohlcv(n: int = 200, base: float = 45000.0) -> pd.DataFrame:
    """Generate synthetic OHLCV DataFrame."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="15min")
    closes = base + np.cumsum(rng.normal(0, 10, n))
    highs = closes + rng.uniform(5, 30, n)
    lows = closes - rng.uniform(5, 30, n)
    opens = closes + rng.normal(0, 5, n)
    volumes = rng.uniform(100, 1000, n)
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )


def make_signal(price: Decimal = Decimal("45000")) -> BaseSignal:
    """Generate a test BaseSignal."""
    return BaseSignal(
        direction=SignalDirection.LONG,
        entry_price=price,
        stop_loss=price - Decimal("500"),
        take_profit=price + Decimal("1000"),
        confidence=0.7,
        timestamp=datetime.now(timezone.utc),
        strategy_type="test",
    )


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_engine():
    """In-memory SQLite async engine for load tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session_factory(db_engine):
    """Session factory for concurrent DB tests."""
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def seed_bot(db_session_factory) -> tuple[int, int]:
    """Create ExchangeCredential + Bot for DB tests. Returns (cred_id, bot_id)."""
    async with db_session_factory() as session:
        cred = ExchangeCredential(
            name="load-test",
            exchange_id="bybit",
            api_key_encrypted="k",
            api_secret_encrypted="s",
        )
        session.add(cred)
        await session.flush()
        await session.refresh(cred)

        bot = Bot(
            name="load-bot",
            credentials_id=cred.id,
            symbol="BTCUSDT",
            strategy="grid",
            config_data="{}",
        )
        session.add(bot)
        await session.flush()
        await session.refresh(bot)
        await session.commit()
        return cred.id, bot.id


# ---------------------------------------------------------------------------
# Mock orchestrator fixtures
# ---------------------------------------------------------------------------


def _make_mock_orchestrator(name: str) -> MagicMock:
    """Create a mock BotOrchestrator for a given bot name."""
    orch = MagicMock()
    orch.get_status.return_value = {
        "bot_name": name,
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
        "config": {"name": name},
    }
    orch.start = AsyncMock()
    orch.stop = AsyncMock()
    orch.pause = AsyncMock()
    orch.resume = AsyncMock()
    orch.emergency_stop = AsyncMock()
    return orch


@pytest.fixture
def mock_orchestrators_10() -> dict[str, MagicMock]:
    """Dictionary of 10 mock orchestrators."""
    return {f"bot_{i}": _make_mock_orchestrator(f"bot_{i}") for i in range(10)}


# ---------------------------------------------------------------------------
# FastAPI app + auth client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_manager(db_engine):
    """Mock DatabaseManager backed by test engine."""
    manager = MagicMock()
    manager._engine = db_engine
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def mock_session():
        async with sf() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    manager.session = mock_session
    return manager


@pytest_asyncio.fixture
async def test_app(mock_db_manager, mock_orchestrators_10):
    """FastAPI app with 10 mock bots for load testing."""
    app = create_app()
    app.state.db_manager = mock_db_manager
    app.state.orchestrators = mock_orchestrators_10
    app.state.config_manager = MagicMock()
    return app


@pytest_asyncio.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    """Unauthenticated test HTTP client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Authenticated test client (register + login)."""
    await client.post(
        "/api/v1/auth/register",
        json={"username": "loadtest", "email": "load@test.com", "password": "testpassword123"},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "loadtest", "password": "testpassword123"},
    )
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
