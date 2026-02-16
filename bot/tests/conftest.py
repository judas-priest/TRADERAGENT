"""Pytest configuration and shared fixtures"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles

from bot.database.models import Base

# SQLite renders BigInteger as BIGINT which breaks autoincrement.
# Override to render as INTEGER so SQLite autoincrement works correctly.
@compiles(BigInteger, "sqlite")
def _compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a fresh in-memory database engine per test for full isolation."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(
    test_db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async with AsyncSession(
        test_db_engine,
        expire_on_commit=False,
    ) as session:
        yield session


@pytest.fixture
def test_config_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test configs"""
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def example_config_yaml(test_config_dir: Path) -> Path:
    """Create an example YAML config file"""
    config_file = test_config_dir / "test_config.yaml"
    config_content = """
database_url: postgresql+asyncpg://test:test@localhost/test
database_pool_size: 5
log_level: INFO
log_to_file: true
log_to_console: true
json_logs: false
encryption_key: dGVzdF9lbmNyeXB0aW9uX2tleV8zMmJ5dGVzX2hlcmU=

bots:
  - version: 1
    name: test_bot
    symbol: BTC/USDT
    strategy: grid
    exchange:
      exchange_id: binance
      credentials_name: test_creds
      sandbox: true
    grid:
      enabled: true
      upper_price: "50000"
      lower_price: "40000"
      grid_levels: 10
      amount_per_grid: "100"
      profit_per_grid: "0.01"
    risk_management:
      max_position_size: "10000"
      min_order_size: "10"
    notifications:
      enabled: false
    dry_run: true
    auto_start: false
"""
    config_file.write_text(config_content)
    return config_file
