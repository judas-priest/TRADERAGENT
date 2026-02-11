#!/usr/bin/env python3
"""
Quick test for ByBit Demo Trading (Paper Trading)

Demo Trading requirements:
- testnet=True (uses api-demo.bybit.com)
- market_type='linear' (futures only, NOT spot!)
- accountType='UNIFIED'
- Production API keys (NOT testnet keys!)
"""

import asyncio
import hashlib
import hmac
import os
import sys
import time
from pathlib import Path

import aiohttp
from cryptography.fernet import Fernet

sys.path.insert(0, str(Path(__file__).parent))

from bot.database.manager import DatabaseManager


async def test_demo_trading():
    """Test ByBit Demo Trading with correct parameters"""

    print("=" * 70)
    print("ByBit Demo Trading (Paper Trading) Test")
    print("=" * 70)
    print()

    # Get credentials from DB
    database_url = os.getenv("DATABASE_URL")
    encryption_key = os.getenv("ENCRYPTION_KEY")

    print("📊 Loading credentials from database...")
    db = DatabaseManager(database_url)
    await db.initialize()

    cred = await db.get_credentials_by_name("bybit_production")
    fernet = Fernet(encryption_key.encode())
    api_key = fernet.decrypt(cred.api_key_encrypted.encode()).decode()
    api_secret = fernet.decrypt(cred.api_secret_encrypted.encode()).decode()

    print(f"✅ API Key: {api_key[:8]}...{api_key[-4:]}")
    print()

    await db.close()

    # Demo Trading configuration
    print("⚙️  Demo Trading Configuration:")
    print("  • Base URL: https://api-demo.bybit.com")
    print("  • Market Type: linear (futures)")
    print("  • Account Type: UNIFIED")
    print("  • Category: linear (spot NOT supported!)")
    print()

    base_url = "https://api-demo.bybit.com"
    recv_window = 10000

    # Test 1: Public API (no auth)
    print("=" * 70)
    print("Test 1: Public API - Ticker (no authentication)")
    print("=" * 70)

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{base_url}/v5/market/tickers?category=linear&symbol=BTCUSDT"
            async with session.get(url) as response:
                data = await response.json()

                if data.get("retCode") == 0:
                    ticker = data["result"]["list"][0]
                    price = ticker.get("lastPrice")
                    print(f"✅ Public API works!")
                    print(f"   BTC/USDT Price: ${float(price):,.2f}")
                    print()
                else:
                    print(f"❌ Error: {data.get('retMsg')}")
                    print()
    except Exception as e:
        print(f"❌ Failed: {e}")
        print()

    # Test 2: Get Wallet Balance (authenticated)
    print("=" * 70)
    print("Test 2: Wallet Balance (authenticated, UNIFIED account)")
    print("=" * 70)

    try:
        async with aiohttp.ClientSession() as session:
            timestamp = int(time.time() * 1000)
            params = "accountType=UNIFIED"

            # Signature: timestamp + api_key + recv_window + params
            payload = f"{timestamp}{api_key}{recv_window}{params}"
            signature = hmac.new(
                api_secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            headers = {
                "X-BAPI-API-KEY": api_key,
                "X-BAPI-TIMESTAMP": str(timestamp),
                "X-BAPI-SIGN": signature,
                "X-BAPI-SIGN-TYPE": "2",
                "X-BAPI-RECV-WINDOW": str(recv_window),
            }

            url = f"{base_url}/v5/account/wallet-balance?{params}"
            async with session.get(url, headers=headers) as response:
                data = await response.json()

                ret_code = data.get("retCode")
                ret_msg = data.get("retMsg", "Unknown error")

                print(f"Response Code: {ret_code}")
                print(f"Response Message: {ret_msg}")
                print()

                if ret_code == 0:
                    print("✅ Authentication successful!")
                    result = data.get("result", {})
                    account_list = result.get("list", [])

                    if account_list:
                        account = account_list[0]
                        coins = account.get("coin", [])

                        print(f"   Account Type: {account.get('accountType')}")
                        print(f"   Total Equity: ${account.get('totalEquity', '0')}")
                        print(f"   Total Wallet Balance: ${account.get('totalWalletBalance', '0')}")
                        print()

                        if coins:
                            print("   Coin balances:")
                            for coin in coins[:5]:  # Show first 5
                                currency = coin.get("coin")
                                balance = coin.get("walletBalance", "0")
                                available = coin.get("availableToWithdraw", "0")
                                if float(balance) > 0:
                                    print(f"     • {currency}: {balance} (available: {available})")
                        else:
                            print("   ⚠️  No coin balances (normal for new Demo account)")
                        print()

                    print("✅✅✅ SUCCESS! API keys are VALID! ✅✅✅")
                    print()
                    print("Your ByBit Demo Trading is working correctly!")
                    print()
                    return True

                elif ret_code == 10003:
                    print("❌ API key is invalid")
                    print()
                    print("Possible reasons:")
                    print("  1. Wrong API key/secret")
                    print("  2. Keys are for testnet, but should be production keys")
                    print("  3. Keys are deactivated on ByBit")
                    print("  4. Missing permissions")
                    print()
                    return False

                elif ret_code == 10001:
                    print("❌ Illegal parameter")
                    print("   Check if category/accountType is correct")
                    print()
                    return False

                else:
                    print(f"❌ Error code {ret_code}: {ret_msg}")
                    print()
                    return False

    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback

        traceback.print_exc()
        print()
        return False

    # Test 3: Get Positions (futures)
    print("=" * 70)
    print("Test 3: Get Positions (linear futures)")
    print("=" * 70)

    try:
        async with aiohttp.ClientSession() as session:
            timestamp = int(time.time() * 1000)
            params = "category=linear&settleCoin=USDT"

            payload = f"{timestamp}{api_key}{recv_window}{params}"
            signature = hmac.new(
                api_secret.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            headers = {
                "X-BAPI-API-KEY": api_key,
                "X-BAPI-TIMESTAMP": str(timestamp),
                "X-BAPI-SIGN": signature,
                "X-BAPI-SIGN-TYPE": "2",
                "X-BAPI-RECV-WINDOW": str(recv_window),
            }

            url = f"{base_url}/v5/position/list?{params}"
            async with session.get(url, headers=headers) as response:
                data = await response.json()

                if data.get("retCode") == 0:
                    positions = data.get("result", {}).get("list", [])
                    print(f"✅ Fetched {len(positions)} positions")
                    print()
                else:
                    print(f"⚠️  Error: {data.get('retMsg')}")
                    print()

    except Exception as e:
        print(f"❌ Failed: {e}")
        print()


if __name__ == "__main__":
    try:
        result = asyncio.run(test_demo_trading())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted")
        sys.exit(1)
