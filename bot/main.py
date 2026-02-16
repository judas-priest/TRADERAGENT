"""
Main entry point for TRADERAGENT bot.
Initializes and runs orchestrators, Telegram bot, and monitoring stack.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

from aiohttp import web

from bot.api.exchange_client import ExchangeAPIClient
from bot.config.manager import ConfigManager
from bot.database.manager import DatabaseManager
from bot.monitoring.alert_handler import Alert, AlertHandler
from bot.monitoring.metrics_collector import MetricsCollector
from bot.monitoring.metrics_exporter import MetricsExporter
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
        self.metrics_exporter: MetricsExporter | None = None
        self.metrics_collector: MetricsCollector | None = None
        self.alert_handler: AlertHandler | None = None
        self._alert_server_runner: web.AppRunner | None = None
        self._shutdown_event: asyncio.Event = asyncio.Event()
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
            await exchange_client.initialize()

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

        # Initialize monitoring stack
        metrics_port = int(os.getenv("METRICS_PORT", "9100"))
        alerts_port = int(os.getenv("ALERTS_PORT", "8080"))

        logger.info("initializing_monitoring", metrics_port=metrics_port, alerts_port=alerts_port)
        self.metrics_exporter = MetricsExporter(port=metrics_port)
        self.metrics_collector = MetricsCollector(
            exporter=self.metrics_exporter,
            orchestrators=self.orchestrators,
        )
        self.alert_handler = AlertHandler()

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

            # Bridge: AlertManager → AlertHandler → Telegram
            self._setup_alert_telegram_bridge(allowed_chat_ids)
        else:
            logger.warning("telegram_bot_not_configured")

        logger.info("bot_application_initialized")

    def _setup_alert_telegram_bridge(self, allowed_chat_ids: list[int]) -> None:
        """Register AlertHandler callback that forwards alerts to Telegram."""
        telegram_bot = self.telegram_bot

        async def send_alert_to_telegram(alert: Alert) -> None:
            if not telegram_bot:
                return
            message = alert.format_message()
            for chat_id in allowed_chat_ids:
                try:
                    await telegram_bot.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                    )
                except Exception as e:
                    logger.error(
                        "alert_telegram_send_failed",
                        chat_id=chat_id,
                        error=str(e),
                    )

        self.alert_handler.add_callback(send_alert_to_telegram)
        logger.info("alert_telegram_bridge_configured")

    async def _start_alert_server(self, port: int = 8080) -> None:
        """Start HTTP server for AlertManager webhooks."""
        app = web.Application()
        app.router.add_routes(self.alert_handler.routes)

        self._alert_server_runner = web.AppRunner(app)
        await self._alert_server_runner.setup()
        site = web.TCPSite(self._alert_server_runner, "0.0.0.0", port)
        await site.start()
        logger.info("alert_server_started", port=port)

    async def start(self) -> None:
        """Start the bot application with all components concurrently."""
        logger.info("starting_bot_application")
        self.running = True
        self._shutdown_event.clear()

        try:
            # Start metrics HTTP server (port 9100)
            if self.metrics_exporter:
                await self.metrics_exporter.start()
                logger.info("metrics_exporter_started")

            # Start metrics collection loop
            if self.metrics_collector:
                await self.metrics_collector.start()
                logger.info("metrics_collector_started")

            # Start alert webhook server (port 8080)
            if self.alert_handler:
                alerts_port = int(os.getenv("ALERTS_PORT", "8080"))
                await self._start_alert_server(port=alerts_port)

            # Start Telegram bot (non-blocking) or wait for shutdown
            if self.telegram_bot:
                logger.info("starting_telegram_bot")
                await self.telegram_bot.start()
            else:
                # No Telegram — wait for shutdown signal
                await self._shutdown_event.wait()

        except asyncio.CancelledError:
            logger.info("bot_application_cancelled")
        except Exception as e:
            logger.error("bot_application_error", error=str(e), exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop the bot application."""
        logger.info("stopping_bot_application")
        self.running = False
        self._shutdown_event.set()

        # Stop metrics collector
        if self.metrics_collector:
            logger.info("stopping_metrics_collector")
            try:
                await self.metrics_collector.stop()
            except Exception as e:
                logger.error("metrics_collector_stop_failed", error=str(e))

        # Stop metrics exporter
        if self.metrics_exporter:
            logger.info("stopping_metrics_exporter")
            try:
                await self.metrics_exporter.stop()
            except Exception as e:
                logger.error("metrics_exporter_stop_failed", error=str(e))

        # Stop alert server
        if self._alert_server_runner:
            logger.info("stopping_alert_server")
            try:
                await self._alert_server_runner.cleanup()
                self._alert_server_runner = None
            except Exception as e:
                logger.error("alert_server_stop_failed", error=str(e))

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
