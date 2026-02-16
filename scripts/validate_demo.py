#!/usr/bin/env python3
"""
Pre-deployment validation for Phase 7.3 Bybit Demo Trading.

Checks all prerequisites before launching the bot:
1. Database connectivity
2. API credentials in database
3. Bybit Demo API connectivity (public + authenticated)
4. Market data availability
5. Configuration file validity
6. Redis connectivity

Usage:
    python scripts/validate_demo.py
    python scripts/validate_demo.py --config configs/phase7_demo.yaml
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class ValidationResult:
    """Track validation results."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results: list[tuple[str, bool, str]] = []

    def ok(self, name: str, detail: str = "") -> None:
        self.passed += 1
        self.results.append((name, True, detail))
        print(f"  [PASS] {name}" + (f" — {detail}" if detail else ""))

    def fail(self, name: str, detail: str = "") -> None:
        self.failed += 1
        self.results.append((name, False, detail))
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))

    def warn(self, name: str, detail: str = "") -> None:
        self.warnings += 1
        print(f"  [WARN] {name}" + (f" — {detail}" if detail else ""))

    @property
    def all_passed(self) -> bool:
        return self.failed == 0


async def check_database(v: ValidationResult) -> "DatabaseManager | None":
    """Check database connectivity and health."""
    print("\n=== 1. Database ===")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        v.fail("DATABASE_URL", "Environment variable not set")
        return None

    v.ok("DATABASE_URL", "Set")

    try:
        from bot.database.manager import DatabaseManager

        db = DatabaseManager(database_url)
        await db.initialize()

        healthy = await db.health_check()
        if healthy:
            v.ok("Database connection", "Healthy")
        else:
            v.fail("Database connection", "Health check failed")
            return None

        return db
    except Exception as e:
        v.fail("Database connection", str(e))
        return None


async def check_credentials(
    v: ValidationResult, db: "DatabaseManager", credentials_name: str = "bybit_demo",
) -> tuple[str, str] | None:
    """Check API credentials in database."""
    print("\n=== 2. API Credentials ===")

    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        v.fail("ENCRYPTION_KEY", "Environment variable not set")
        return None

    v.ok("ENCRYPTION_KEY", "Set")

    try:
        cred = await db.get_credentials_by_name(credentials_name)
        if not cred:
            v.fail(f"Credentials '{credentials_name}'", "Not found in database")
            return None

        v.ok(f"Credentials '{credentials_name}'", f"Found (ID: {cred.id}, sandbox: {cred.is_sandbox})")

        from cryptography.fernet import Fernet

        fernet = Fernet(encryption_key.encode())
        api_key = fernet.decrypt(cred.api_key_encrypted.encode()).decode()
        api_secret = fernet.decrypt(cred.api_secret_encrypted.encode()).decode()

        if not api_key or not api_secret:
            v.fail("Decrypt credentials", "Empty API key or secret after decryption")
            return None

        v.ok("Decrypt credentials", f"API Key: {api_key[:8]}...{api_key[-4:]}")
        return api_key, api_secret

    except Exception as e:
        v.fail("Decrypt credentials", str(e))
        return None


async def check_bybit_api(
    v: ValidationResult, api_key: str, api_secret: str,
) -> bool:
    """Check Bybit Demo API connectivity."""
    print("\n=== 3. Bybit Demo API ===")

    try:
        from bot.api.bybit_direct_client import ByBitDirectClient

        client = ByBitDirectClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=True,
            market_type="linear",
        )
        # Only create session, don't load markets yet
        import aiohttp
        client._session = aiohttp.ClientSession()

        # Test public API: ticker
        ticker = await client.fetch_ticker("BTC/USDT")
        btc_price = ticker.get("last", 0)
        if btc_price > 0:
            v.ok("Public API (ticker)", f"BTC/USDT = ${btc_price:,.2f}")
        else:
            v.fail("Public API (ticker)", "Got zero price")
            await client.close()
            return False

        # Test authenticated API: balance
        balance = await client.fetch_balance()
        usdt_balance = balance.get("total", {}).get("USDT", 0)
        btc_balance = balance.get("total", {}).get("BTC", 0)

        if usdt_balance > 0 or btc_balance > 0:
            v.ok(
                "Authenticated API (balance)",
                f"USDT: {usdt_balance:,.2f}, BTC: {btc_balance:.4f}",
            )
        else:
            v.warn(
                "Authenticated API (balance)",
                "Zero balances (may need to fund demo account)",
            )

        # Health check
        healthy = await client.health_check()
        if healthy:
            v.ok("Health check", "api-demo.bybit.com responding")
        else:
            v.fail("Health check", "Failed")

        await client.close()
        return True

    except Exception as e:
        v.fail("Bybit API", str(e))
        return False


async def check_market_data(
    v: ValidationResult, api_key: str, api_secret: str,
) -> None:
    """Check market data availability for all trading pairs."""
    print("\n=== 4. Market Data ===")

    try:
        from bot.api.bybit_direct_client import ByBitDirectClient
        import aiohttp

        client = ByBitDirectClient(
            api_key=api_key,
            api_secret=api_secret,
            testnet=True,
            market_type="linear",
        )
        client._session = aiohttp.ClientSession()

        symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]

        for symbol in symbols:
            try:
                ticker = await client.fetch_ticker(symbol)
                price = ticker.get("last", 0)
                v.ok(f"Ticker {symbol}", f"${price:,.2f}")
            except Exception as e:
                v.fail(f"Ticker {symbol}", str(e))

        # Test OHLCV
        try:
            ohlcv = await client.fetch_ohlcv("BTC/USDT", "1h", limit=10)
            if ohlcv and len(ohlcv) > 0:
                v.ok("OHLCV BTC/USDT 1h", f"{len(ohlcv)} candles")
            else:
                v.fail("OHLCV BTC/USDT 1h", "No data returned")
        except Exception as e:
            v.fail("OHLCV BTC/USDT 1h", str(e))

        # Test order book
        try:
            ob = await client.fetch_order_book("BTC/USDT", limit=5)
            bids = len(ob.get("bids", []))
            asks = len(ob.get("asks", []))
            v.ok("Order book BTC/USDT", f"{bids} bids, {asks} asks")
        except Exception as e:
            v.fail("Order book BTC/USDT", str(e))

        # Test markets
        try:
            markets = await client.fetch_markets()
            target_markets = [s.replace("/", "") for s in symbols]
            found = [
                s for s in symbols
                if s in markets or s.replace("/", "") in [m.get("id") for m in markets.values()]
            ]
            v.ok("Markets", f"{len(markets)} instruments, targets found: {len(found)}/{len(symbols)}")
        except Exception as e:
            v.fail("Markets", str(e))

        await client.close()

    except Exception as e:
        v.fail("Market data", str(e))


async def check_config(v: ValidationResult, config_path: str) -> None:
    """Check configuration file validity."""
    print("\n=== 5. Configuration ===")

    path = Path(config_path)
    if not path.exists():
        v.fail("Config file", f"{config_path} does not exist")
        return

    v.ok("Config file", f"{config_path} exists")

    try:
        from bot.config.manager import ConfigManager

        cm = ConfigManager(path)
        config = cm.load()

        v.ok("Config validation", f"{len(config.bots)} bots configured")

        for bot in config.bots:
            mode = "LIVE-DEMO" if not bot.dry_run and bot.exchange.sandbox else (
                "DRY-RUN" if bot.dry_run else "LIVE-PRODUCTION"
            )
            status = f"{bot.strategy} {bot.symbol} [{mode}]"
            if mode == "LIVE-PRODUCTION":
                v.warn(f"Bot {bot.name}", f"{status} — NOT demo mode!")
            else:
                v.ok(f"Bot {bot.name}", status)

    except Exception as e:
        v.fail("Config validation", str(e))


async def check_redis(v: ValidationResult) -> None:
    """Check Redis connectivity."""
    print("\n=== 6. Redis ===")

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(redis_url)
        await r.ping()
        v.ok("Redis connection", redis_url)
        await r.close()
    except Exception as e:
        v.warn("Redis connection", f"{str(e)} (optional, bot works without it)")


async def main():
    parser = argparse.ArgumentParser(description="Validate Bybit Demo Trading deployment")
    parser.add_argument(
        "--config", default="configs/phase7_demo.yaml",
        help="Path to config file (default: configs/phase7_demo.yaml)",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("  TRADERAGENT Phase 7.3 — Demo Trading Validation")
    print("=" * 70)

    v = ValidationResult()

    # 1. Database
    db = await check_database(v)

    # 2. Credentials — detect name from config
    credentials_name = "bybit_demo"
    try:
        from bot.config.manager import ConfigManager
        cm = ConfigManager(Path(args.config))
        cfg = cm.load()
        if cfg.bots:
            credentials_name = cfg.bots[0].exchange.credentials_name
    except Exception:
        pass

    creds = None
    if db:
        creds = await check_credentials(v, db, credentials_name)

    # 3. Bybit API
    if creds:
        api_key, api_secret = creds
        await check_bybit_api(v, api_key, api_secret)

        # 4. Market data
        await check_market_data(v, api_key, api_secret)

    # 5. Configuration
    await check_config(v, args.config)

    # 6. Redis
    await check_redis(v)

    # Close database
    if db:
        await db.close()

    # Summary
    print("\n" + "=" * 70)
    print(f"  Results: {v.passed} passed, {v.failed} failed, {v.warnings} warnings")
    print("=" * 70)

    if v.all_passed:
        print("\n  All checks passed. Ready to deploy!\n")
        print("  Start with:")
        print(f"    CONFIG_PATH={args.config} python -m bot.main\n")
        return 0
    else:
        print("\n  Some checks failed. Fix issues before deploying.\n")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
