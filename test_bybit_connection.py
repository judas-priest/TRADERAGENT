#!/usr/bin/env python3
"""
Script to test ByBit API connection using stored credentials.
Tests API connectivity, authentication, and basic operations.

Usage:
    python test_bybit_connection.py --credentials bybit_main
"""

import argparse
import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cryptography.fernet import Fernet

from bot.api.exchange_client import ExchangeAPIClient
from bot.database.manager import DatabaseManager


async def test_bybit_connection(credentials_name: str):
    """
    Test ByBit connection using stored credentials.

    Args:
        credentials_name: Name of credentials to test
    """
    print("=" * 60)
    print("ByBit API Connection Test")
    print("=" * 60)
    print()

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set!")
        sys.exit(1)

    # Get encryption key
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        print("❌ ENCRYPTION_KEY environment variable not set!")
        sys.exit(1)

    # Initialize database
    print("📊 Connecting to database...")
    db_manager = DatabaseManager(database_url)
    await db_manager.initialize()

    if not await db_manager.health_check():
        print("❌ Database health check failed!")
        sys.exit(1)

    print("✅ Database connected")
    print()

    # Get credentials
    print(f"🔑 Loading credentials '{credentials_name}'...")
    credentials = await db_manager.get_credentials_by_name(credentials_name)

    if not credentials:
        print(f"❌ Credentials '{credentials_name}' not found in database!")
        print()
        print("Available credentials:")
        # This would require a new method to list all credentials
        sys.exit(1)

    print(f"✅ Credentials loaded")
    print(f"   Exchange: {credentials.exchange_id}")
    print(f"   Sandbox: {credentials.is_sandbox}")
    print(f"   Active: {credentials.is_active}")
    print()

    # Decrypt credentials
    print("🔓 Decrypting credentials...")
    fernet = Fernet(encryption_key.encode())
    api_key = fernet.decrypt(credentials.api_key_encrypted.encode()).decode()
    api_secret = fernet.decrypt(credentials.api_secret_encrypted.encode()).decode()
    print("✅ Credentials decrypted")
    print()

    # Initialize exchange client
    print("🔌 Connecting to ByBit API...")
    exchange_client = ExchangeAPIClient(
        exchange_id="bybit",
        api_key=api_key,
        api_secret=api_secret,
        sandbox=credentials.is_sandbox,
    )

    try:
        await exchange_client.initialize()
        print("✅ Exchange client initialized")
        print()

        # Test 1: Fetch markets
        print("=" * 60)
        print("Test 1: Fetch Markets")
        print("=" * 60)
        markets = await exchange_client.fetch_markets()
        print(f"✅ Successfully fetched {len(markets)} markets")

        # Show some popular pairs
        popular_pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        print("\nPopular trading pairs:")
        for symbol in popular_pairs:
            if symbol in markets:
                market = markets[symbol]
                print(f"  • {symbol}: {market.get('active', False)}")
        print()

        # Test 2: Fetch balance
        print("=" * 60)
        print("Test 2: Fetch Balance")
        print("=" * 60)
        balance = await exchange_client.fetch_balance()
        print("✅ Successfully fetched balance")

        # Show non-zero balances
        non_zero = {k: v for k, v in balance["total"].items() if float(v) > 0}
        if non_zero:
            print("\nNon-zero balances:")
            for currency, amount in non_zero.items():
                print(f"  • {currency}: {amount}")
        else:
            print("\nNo non-zero balances (this is normal for testnet)")
        print()

        # Test 3: Fetch ticker
        print("=" * 60)
        print("Test 3: Fetch Ticker (BTC/USDT)")
        print("=" * 60)
        ticker = await exchange_client.fetch_ticker("BTC/USDT")
        print("✅ Successfully fetched ticker")
        print(f"\n  Symbol: {ticker['symbol']}")
        print(f"  Last Price: {ticker.get('last', 'N/A')}")
        print(f"  Bid: {ticker.get('bid', 'N/A')}")
        print(f"  Ask: {ticker.get('ask', 'N/A')}")
        print(f"  24h Volume: {ticker.get('baseVolume', 'N/A')}")
        print()

        # Test 4: Check minimum order sizes
        print("=" * 60)
        print("Test 4: Check Trading Requirements (BTC/USDT)")
        print("=" * 60)
        btc_market = markets.get("BTC/USDT", {})
        limits = btc_market.get("limits", {})
        print("✅ Trading requirements:")
        print(f"\n  Amount limits:")
        print(f"    Min: {limits.get('amount', {}).get('min', 'N/A')}")
        print(f"    Max: {limits.get('amount', {}).get('max', 'N/A')}")
        print(f"\n  Price limits:")
        print(f"    Min: {limits.get('price', {}).get('min', 'N/A')}")
        print(f"    Max: {limits.get('price', {}).get('max', 'N/A')}")
        print(f"\n  Cost limits (in USDT):")
        print(f"    Min: {limits.get('cost', {}).get('min', 'N/A')}")
        print(f"    Max: {limits.get('cost', {}).get('max', 'N/A')}")
        print()

        # Test 5: Fetch open orders (should be empty initially)
        print("=" * 60)
        print("Test 5: Fetch Open Orders")
        print("=" * 60)
        open_orders = await exchange_client.fetch_open_orders("BTC/USDT")
        print(f"✅ Successfully fetched open orders: {len(open_orders)} orders")
        print()

        # Summary
        print("=" * 60)
        print("✅ All Tests Passed!")
        print("=" * 60)
        print()
        print("Your ByBit API connection is working correctly!")
        print()
        print("Next steps:")
        print("1. Configure your bot in configs/bybit_example.yaml")
        print("2. Start with dry_run: true for testing")
        print("3. Monitor the bot logs carefully")
        print("4. Only use real trading after thorough testing")
        print()

    except Exception as e:
        print(f"\n❌ Error testing connection: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup
        await exchange_client.close()
        await db_manager.close()


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test ByBit API connection")
    parser.add_argument(
        "--credentials",
        type=str,
        required=True,
        help="Name of credentials to test (e.g., 'bybit_main')",
    )

    args = parser.parse_args()
    await test_bybit_connection(args.credentials)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user.")
        sys.exit(0)
