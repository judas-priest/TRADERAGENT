"""
Main entry point for TRADERAGENT bot.
Initializes and runs orchestrators and Telegram bot.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

from bot.api.exchange_client import ExchangeAPIClient
from bot.config.manager import ConfigManager
from bot.database.manager import DatabaseManager
from bot.orchestrator.bot_orchestrator import BotOrchestrator
from bot.telegram.bot import TelegramBot
from bot.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


class BotApplication:
    """Main bot application manager."""

    def __init__(self):
        """Initialize bot application."""
        self.config_manager: ConfigManager | None = None
        self.db_manager: DatabaseManager | None = None
        self.orchestrators: dict[str, BotOrchestrator] = {}
        self.telegram_bot: TelegramBot | None = None
        self.running = False

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("initializing_bot_application")

        # Load configuration
        config_path = os.getenv("CONFIG_PATH", "configs/production.yaml")
        logger.info("loading_config", path=config_path)

        self.config_manager = ConfigManager(Path(config_path))
        main_config = self.config_manager.load()

        # Setup logging
        log_level = os.getenv("LOG_LEVEL", main_config.log_level)
        setup_logging(log_level=log_level)

        # Initialize database
        database_url = os.getenv("DATABASE_URL", main_config.database_url)
        logger.info("initializing_database")
        self.db_manager = DatabaseManager(database_url)
        await self.db_manager.initialize()

        # Redis URL
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        # Initialize orchestrators for each bot config
        logger.info("initializing_orchestrators", bot_count=len(main_config.bots))
        for bot_config in main_config.bots:
            logger.info("initializing_bot", bot_name=bot_config.name)

            # Load API credentials from database
            credentials = await self.db_manager.get_credentials_by_name(
                bot_config.exchange.credentials_name
            )
            if not credentials:
                logger.error(
                    "credentials_not_found",
                    bot_name=bot_config.name,
                    credentials_name=bot_config.exchange.credentials_name,
                )
                continue

            # Decrypt credentials
            encryption_key = os.getenv("ENCRYPTION_KEY", main_config.encryption_key)
            from cryptography.fernet import Fernet

            fernet = Fernet(encryption_key.encode())
            api_key = fernet.decrypt(credentials.api_key_encrypted.encode()).decode()
            api_secret = fernet.decrypt(credentials.api_secret_encrypted.encode()).decode()
            password = None
            if credentials.password_encrypted:
                password = fernet.decrypt(credentials.password_encrypted.encode()).decode()

            # Create exchange client
            exchange_client = ExchangeAPIClient(
                exchange_id=bot_config.exchange.exchange_id,
                api_key=api_key,
                api_secret=api_secret,
                password=password,
                sandbox=bot_config.exchange.sandbox,
            )

            # Create orchestrator
            orchestrator = BotOrchestrator(
                bot_config=bot_config,
                exchange_client=exchange_client,
                db_manager=self.db_manager,
                redis_url=redis_url,
            )
            await orchestrator.initialize()

            self.orchestrators[bot_config.name] = orchestrator

            # Auto-start if configured
            if bot_config.auto_start:
                logger.info("auto_starting_bot", bot_name=bot_config.name)
                await orchestrator.start()

        # Initialize Telegram bot if configured
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat_ids = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")

        if telegram_token and telegram_chat_ids:
            logger.info("initializing_telegram_bot")
            allowed_chat_ids = [
                int(chat_id.strip()) for chat_id in telegram_chat_ids.split(",") if chat_id.strip()
            ]

            self.telegram_bot = TelegramBot(
                token=telegram_token,
                allowed_chat_ids=allowed_chat_ids,
                orchestrators=self.orchestrators,
                redis_url=redis_url,
            )
        else:
            logger.warning("telegram_bot_not_configured")

        logger.info("bot_application_initialized")

    async def start(self) -> None:
        """Start the bot application."""
        logger.info("starting_bot_application")
        self.running = True

        try:
            if self.telegram_bot:
                logger.info("starting_telegram_bot")
                await self.telegram_bot.start()
            else:
                # If no Telegram bot, just keep running
                while self.running:
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("bot_application_cancelled")
        except Exception as e:
            logger.error("bot_application_error", error=str(e), exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the bot application."""
        logger.info("stopping_bot_application")
        self.running = False

        # Stop all orchestrators
        for name, orchestrator in self.orchestrators.items():
            logger.info("stopping_orchestrator", bot_name=name)
            try:
                await orchestrator.stop()
                await orchestrator.cleanup()
            except Exception as e:
                logger.error(
                    "orchestrator_stop_failed",
                    bot_name=name,
                    error=str(e),
                )

        # Stop Telegram bot
        if self.telegram_bot:
            logger.info("stopping_telegram_bot")
            try:
                await self.telegram_bot.stop()
            except Exception as e:
                logger.error("telegram_bot_stop_failed", error=str(e))

        # Close database
        if self.db_manager:
            logger.info("closing_database")
            await self.db_manager.close()

        logger.info("bot_application_stopped")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.stop()


async def main() -> None:
    """Main entry point."""
    app = BotApplication()

    # Setup signal handlers
    def signal_handler(sig, frame):
        logger.info("signal_received", signal=sig)
        asyncio.create_task(app.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize application
        await app.initialize()

        # Start application
        await app.start()

    except KeyboardInterrupt:
        logger.info("keyboard_interrupt_received")
    except Exception as e:
        logger.error("application_error", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        await app.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
