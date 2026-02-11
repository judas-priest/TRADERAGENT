#!/usr/bin/env python3
"""
Script to add ByBit API credentials to the database.
Encrypts and stores API keys securely in PostgreSQL.

Usage:
    python add_bybit_credentials.py

Prerequisites:
    - PostgreSQL database running
    - DATABASE_URL environment variable set
    - ENCRYPTION_KEY environment variable set
"""

import asyncio
import base64
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from cryptography.fernet import Fernet

from bot.database.manager import DatabaseManager
from bot.database.models import ExchangeCredential


async def generate_encryption_key() -> str:
    """Generate a new encryption key."""
    key = Fernet.generate_key()
    return base64.b64encode(key).decode()


async def add_bybit_credentials(
    db_manager: DatabaseManager,
    encryption_key: str,
    name: str,
    api_key: str,
    api_secret: str,
    is_sandbox: bool = True,
) -> ExchangeCredential:
    """
    Add ByBit credentials to database.

    Args:
        db_manager: Database manager instance
        encryption_key: Base64 encoded encryption key
        name: Unique name for these credentials (e.g., 'bybit_main')
        api_key: ByBit API key
        api_secret: ByBit API secret
        is_sandbox: Whether these are testnet credentials

    Returns:
        Created ExchangeCredential object
    """
    # Initialize Fernet cipher
    fernet = Fernet(encryption_key.encode())

    # Encrypt credentials
    api_key_encrypted = fernet.encrypt(api_key.encode()).decode()
    api_secret_encrypted = fernet.encrypt(api_secret.encode()).decode()

    # Check if credentials with this name already exist
    existing = await db_manager.get_credentials_by_name(name)
    if existing:
        print(f"⚠️  Credentials with name '{name}' already exist (ID: {existing.id})")
        response = input("Do you want to update them? (yes/no): ")
        if response.lower() != "yes":
            print("❌ Aborted. No changes made.")
            sys.exit(0)

        # Update existing credentials
        existing.api_key_encrypted = api_key_encrypted
        existing.api_secret_encrypted = api_secret_encrypted
        existing.is_sandbox = is_sandbox
        existing.is_active = True
        await db_manager.update(existing)
        print(f"✅ Credentials '{name}' updated successfully!")
        return existing

    # Create new credentials
    credentials = ExchangeCredential(
        name=name,
        exchange_id="bybit",
        api_key_encrypted=api_key_encrypted,
        api_secret_encrypted=api_secret_encrypted,
        password_encrypted=None,  # ByBit doesn't require password
        is_sandbox=is_sandbox,
        is_active=True,
    )

    # Save to database
    created_credentials = await db_manager.create_credentials(credentials)
    print(f"✅ Credentials '{name}' created successfully!")
    print(f"   ID: {created_credentials.id}")
    print(f"   Exchange: {created_credentials.exchange_id}")
    print(f"   Sandbox: {created_credentials.is_sandbox}")

    return created_credentials


async def main():
    """Main function."""
    print("=" * 60)
    print("ByBit API Credentials Manager")
    print("=" * 60)
    print()

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set!")
        print()
        print("Example:")
        print('export DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/traderagent"')
        sys.exit(1)

    # Get or generate encryption key
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        print("⚠️  ENCRYPTION_KEY environment variable not set!")
        print()
        print("Generating a new encryption key...")
        encryption_key = await generate_encryption_key()
        print(f"✅ Generated encryption key: {encryption_key}")
        print()
        print("⚠️  IMPORTANT: Save this key in your .env file!")
        print(f'ENCRYPTION_KEY={encryption_key}')
        print()

    # Initialize database
    print("📊 Initializing database connection...")
    db_manager = DatabaseManager(database_url)
    await db_manager.initialize()

    # Check database health
    if not await db_manager.health_check():
        print("❌ Database health check failed!")
        sys.exit(1)

    print("✅ Database connection successful!")
    print()

    # Get credentials name
    print("Enter a unique name for these credentials (e.g., 'bybit_main', 'bybit_testnet'):")
    name = input("Name: ").strip()
    if not name:
        print("❌ Name cannot be empty!")
        sys.exit(1)

    # Get API credentials
    print()
    print("Enter your ByBit API credentials:")
    print("(You can get them from https://www.bybit.com/app/user/api-management)")
    print()
    api_key = input("API Key: ").strip()
    if not api_key:
        print("❌ API Key cannot be empty!")
        sys.exit(1)

    api_secret = input("API Secret: ").strip()
    if not api_secret:
        print("❌ API Secret cannot be empty!")
        sys.exit(1)

    # Ask if testnet or mainnet
    print()
    print("Are these testnet or mainnet credentials?")
    print("⚠️  It's HIGHLY recommended to start with testnet!")
    print("1. Testnet (sandbox) - for testing (recommended)")
    print("2. Mainnet - for real trading (use with caution)")
    choice = input("Choice (1 or 2): ").strip()

    is_sandbox = choice == "1"
    if not is_sandbox:
        print()
        print("⚠️  WARNING: You are about to add MAINNET credentials!")
        print("   Make sure you understand the risks of real trading.")
        confirm = input("Type 'YES' to confirm: ").strip()
        if confirm != "YES":
            print("❌ Aborted. Use testnet credentials first.")
            sys.exit(0)

    # Add credentials
    print()
    print("💾 Adding credentials to database...")
    try:
        await add_bybit_credentials(
            db_manager=db_manager,
            encryption_key=encryption_key,
            name=name,
            api_key=api_key,
            api_secret=api_secret,
            is_sandbox=is_sandbox,
        )
    except Exception as e:
        print(f"❌ Error adding credentials: {e}")
        sys.exit(1)

    # Next steps
    print()
    print("=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print()
    print("1. Add this credentials name to your bot config:")
    print(f"   credentials_name: {name}")
    print()
    print("2. Edit your config file (configs/production.yaml):")
    print("   exchange:")
    print("     exchange_id: bybit")
    print(f"     credentials_name: {name}")
    print(f"     sandbox: {str(is_sandbox).lower()}")
    print()
    print("3. Test the connection:")
    print("   python -m pytest bot/tests/testnet/test_exchange_connection.py")
    print()
    print("4. Start the bot:")
    print("   python -m bot.main --config configs/production.yaml")
    print()

    # Close database
    await db_manager.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user.")
        sys.exit(0)
