"""
Telegram bot for managing and monitoring trading bots.
Provides commands for control and status monitoring.
"""

import asyncio
from typing import Any

import redis.asyncio as redis
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.orchestrator.bot_orchestrator import BotOrchestrator, BotState
from bot.orchestrator.events import EventType, TradingEvent
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class TelegramBot:
    """
    Telegram bot for trading bot management.

    Features:
    - Control commands: /start, /stop, /pause, /resume
    - Status monitoring: /status, /balance, /orders, /pnl
    - Event notifications via Redis Pub/Sub
    - Multi-bot management support
    """

    def __init__(
        self,
        token: str,
        allowed_chat_ids: list[int],
        orchestrators: dict[str, BotOrchestrator],
        redis_url: str = "redis://localhost:6379",
    ):
        """
        Initialize Telegram Bot.

        Args:
            token: Telegram bot token
            allowed_chat_ids: List of allowed chat IDs for security
            orchestrators: Dictionary of bot_name -> BotOrchestrator
            redis_url: Redis connection URL for event subscriptions
        """
        self.token = token
        self.allowed_chat_ids = set(allowed_chat_ids)
        self.orchestrators = orchestrators
        self.redis_url = redis_url

        # Aiogram setup
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.router = Router()

        # Redis for event subscriptions
        self.redis_client: redis.Redis | None = None
        self.event_listener_task: asyncio.Task | None = None

        # Register handlers
        self._register_handlers()

        logger.info(
            "telegram_bot_initialized",
            bot_count=len(orchestrators),
            allowed_chats=len(allowed_chat_ids),
        )

    def _register_handlers(self) -> None:
        """Register command handlers."""
        # Control commands
        self.router.message(CommandStart())(self._cmd_start)
        self.router.message(Command("help"))(self._cmd_help)
        self.router.message(Command("status"))(self._cmd_status)
        self.router.message(Command("start_bot"))(self._cmd_start_bot)
        self.router.message(Command("stop_bot"))(self._cmd_stop_bot)
        self.router.message(Command("pause"))(self._cmd_pause)
        self.router.message(Command("resume"))(self._cmd_resume)

        # Monitoring commands
        self.router.message(Command("balance"))(self._cmd_balance)
        self.router.message(Command("orders"))(self._cmd_orders)
        self.router.message(Command("positions"))(self._cmd_positions)
        self.router.message(Command("pnl"))(self._cmd_pnl)
        self.router.message(Command("list"))(self._cmd_list)
        self.router.message(Command("report"))(self._cmd_report)

        # Strategy commands
        self.router.message(Command("switch_strategy"))(self._cmd_switch_strategy)

        # Multi-pair / portfolio commands (A5)
        self.router.message(Command("scan"))(self._cmd_scan)
        self.router.message(Command("create_bot"))(self._cmd_create_bot)
        self.router.message(Command("delete_bot"))(self._cmd_delete_bot)
        self.router.message(Command("portfolio"))(self._cmd_portfolio)

        # Register router with dispatcher
        self.dp.include_router(self.router)

    def _check_auth(self, message: Message) -> bool:
        """
        Check if user is authorized.

        Args:
            message: Telegram message

        Returns:
            True if authorized, False otherwise
        """
        if message.from_user is None:
            return False

        chat_id = message.chat.id
        if chat_id not in self.allowed_chat_ids:
            logger.warning(
                "unauthorized_access_attempt",
                chat_id=chat_id,
                user_id=message.from_user.id,
            )
            return False
        return True

    async def _cmd_start(self, message: Message) -> None:
        """Handle /start command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        welcome_text = (
            "🤖 *TRADERAGENT Bot Manager*\n\n"
            "Welcome to the trading bot management interface.\n\n"
            "*Available Commands:*\n\n"
            "*Control:*\n"
            "/start\\_bot <name> - Start a trading bot\n"
            "/stop\\_bot <name> - Stop a trading bot\n"
            "/pause <name> - Pause trading bot\n"
            "/resume <name> - Resume trading bot\n"
            "/switch\\_strategy <name> <strategy> - Switch strategy\n\n"
            "*Monitoring:*\n"
            "/status [name] - Bot status (all bots if no name)\n"
            "/balance <name> - Current balance\n"
            "/orders <name> - Open orders\n"
            "/positions <name> - Open positions\n"
            "/pnl <name> - Profit and Loss\n"
            "/report [name] - Performance report\n"
            "/list - List all bots\n\n"
            "*Other:*\n"
            "/help - Show this help message\n"
        )
        await message.answer(welcome_text, parse_mode="Markdown")

    async def _cmd_help(self, message: Message) -> None:
        """Handle /help command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        await self._cmd_start(message)

    async def _cmd_list(self, message: Message) -> None:
        """Handle /list command - list all bots."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        if not self.orchestrators:
            await message.answer("📋 No bots configured")
            return

        response = "📋 *Available Bots:*\n\n"
        for name, orch in self.orchestrators.items():
            state_emoji = self._get_state_emoji(orch.state)
            response += (
                f"{state_emoji} *{name}*\n"
                f"  Symbol: {orch.config.symbol}\n"
                f"  Strategy: {orch.config.strategy}\n"
                f"  State: {orch.state.value}\n\n"
            )

        await message.answer(response, parse_mode="Markdown")

    async def _cmd_status(self, message: Message) -> None:
        """Handle /status command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        # Extract bot name from command
        args = message.text.split() if message.text else []
        bot_name = args[1] if len(args) > 1 else None

        if bot_name:
            # Show status for specific bot
            if bot_name not in self.orchestrators:
                await message.answer(f"❌ Bot '{bot_name}' not found")
                return

            orch = self.orchestrators[bot_name]
            status = await orch.get_status()
            response = self._format_status(status)
            await message.answer(response, parse_mode="Markdown")
        else:
            # Show status for all bots
            if not self.orchestrators:
                await message.answer("📋 No bots configured")
                return

            response = "📊 *Bot Status Summary:*\n\n"
            for name, orch in self.orchestrators.items():
                state_emoji = self._get_state_emoji(orch.state)
                response += f"{state_emoji} *{name}*: {orch.state.value}\n"

            response += "\nUse `/status <bot_name>` for detailed info"
            await message.answer(response, parse_mode="Markdown")

    async def _cmd_start_bot(self, message: Message) -> None:
        """Handle /start_bot command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer("Usage: /start_bot <bot_name>")
            return

        bot_name = args[1]
        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]
        try:
            await orch.start()
            await message.answer(f"✅ Bot '{bot_name}' started successfully")
        except Exception as e:
            logger.error("start_bot_failed", bot_name=bot_name, error=str(e))
            await message.answer(f"❌ Failed to start bot: {str(e)}")

    async def _cmd_stop_bot(self, message: Message) -> None:
        """Handle /stop_bot command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer("Usage: /stop_bot <bot_name>")
            return

        bot_name = args[1]
        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]
        try:
            await orch.stop()
            await message.answer(f"🛑 Bot '{bot_name}' stopped successfully")
        except Exception as e:
            logger.error("stop_bot_failed", bot_name=bot_name, error=str(e))
            await message.answer(f"❌ Failed to stop bot: {str(e)}")

    async def _cmd_pause(self, message: Message) -> None:
        """Handle /pause command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer("Usage: /pause <bot_name>")
            return

        bot_name = args[1]
        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]
        try:
            await orch.pause()
            await message.answer(f"⏸️ Bot '{bot_name}' paused")
        except Exception as e:
            logger.error("pause_bot_failed", bot_name=bot_name, error=str(e))
            await message.answer(f"❌ Failed to pause bot: {str(e)}")

    async def _cmd_resume(self, message: Message) -> None:
        """Handle /resume command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer("Usage: /resume <bot_name>")
            return

        bot_name = args[1]
        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]
        try:
            await orch.resume()
            await message.answer(f"▶️ Bot '{bot_name}' resumed")
        except Exception as e:
            logger.error("resume_bot_failed", bot_name=bot_name, error=str(e))
            await message.answer(f"❌ Failed to resume bot: {str(e)}")

    async def _cmd_balance(self, message: Message) -> None:
        """Handle /balance command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer("Usage: /balance <bot_name>")
            return

        bot_name = args[1]
        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]
        try:
            balance = await orch.exchange.get_balance()
            quote_currency = orch.config.symbol.split("/")[1]
            available = balance.get(quote_currency, 0)

            response = (
                f"💰 *Balance for {bot_name}*\n\n"
                f"Currency: {quote_currency}\n"
                f"Available: {available}\n"
            )

            if orch.risk_manager:
                risk_status = orch.risk_manager.get_risk_status()
                response += (
                    f"\n*Risk Status:*\n"
                    f"Initial Balance: {risk_status['initial_balance']}\n"
                    f"Current Balance: {risk_status['current_balance']}\n"
                )
                if risk_status["drawdown"] is not None:
                    response += f"Drawdown: {float(risk_status['drawdown']):.2%}\n"

            await message.answer(response, parse_mode="Markdown")
        except Exception as e:
            logger.error("balance_fetch_failed", bot_name=bot_name, error=str(e))
            await message.answer(f"❌ Failed to fetch balance: {str(e)}")

    async def _cmd_orders(self, message: Message) -> None:
        """Handle /orders command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer("Usage: /orders <bot_name>")
            return

        bot_name = args[1]
        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]
        try:
            orders = await orch.exchange.fetch_open_orders(orch.config.symbol)

            if not orders:
                await message.answer(f"📋 No open orders for {bot_name}")
                return

            response = f"📋 *Open Orders for {bot_name}*\n\n"
            for order in orders[:10]:  # Limit to 10 orders
                response += (
                    f"ID: `{order['id']}`\n"
                    f"Side: {order['side'].upper()}\n"
                    f"Price: {order['price']}\n"
                    f"Amount: {order['amount']}\n\n"
                )

            if len(orders) > 10:
                response += f"... and {len(orders) - 10} more orders"

            await message.answer(response, parse_mode="Markdown")
        except Exception as e:
            logger.error("orders_fetch_failed", bot_name=bot_name, error=str(e))
            await message.answer(f"❌ Failed to fetch orders: {str(e)}")

    async def _cmd_pnl(self, message: Message) -> None:
        """Handle /pnl command."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer("Usage: /pnl <bot_name>")
            return

        bot_name = args[1]
        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]
        response = f"📊 *P&L for {bot_name}*\n\n"

        # Grid P&L
        if orch.grid_engine:
            grid_status = orch.grid_engine.get_grid_status()
            response += (
                f"*Grid Trading:*\n"
                f"Total Profit: {grid_status['total_profit']}\n"
                f"Buy Count: {grid_status['buy_count']}\n"
                f"Sell Count: {grid_status['sell_count']}\n\n"
            )

        # DCA P&L
        if orch.dca_engine and orch.dca_engine.position and orch.current_price:
            dca_status = orch.dca_engine.get_position_status()
            pnl = orch.dca_engine.position.get_pnl(orch.current_price)
            pnl_pct = orch.dca_engine.position.get_pnl_percentage(orch.current_price)
            response += (
                f"*DCA Position:*\n"
                f"P&L: {pnl}\n"
                f"P&L %: {float(pnl_pct):.2%}\n"
                f"Avg Entry: {dca_status['avg_entry_price']}\n"
                f"Current Price: {orch.current_price}\n\n"
            )

        # Risk Manager P&L
        if orch.risk_manager:
            risk_status = orch.risk_manager.get_risk_status()
            if risk_status["pnl_percentage"] is not None:
                response += f"*Overall:*\n" f"P&L %: {float(risk_status['pnl_percentage']):.2%}\n"

        await message.answer(response, parse_mode="Markdown")

    async def _cmd_positions(self, message: Message) -> None:
        """Handle /positions command — show open positions."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer("Usage: /positions <bot_name>")
            return

        bot_name = args[1]
        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]
        response = f"📊 *Positions for {bot_name}*\n\n"
        has_positions = False

        # DCA positions
        if orch.dca_engine and orch.dca_engine.position:
            has_positions = True
            pos = orch.dca_engine.position
            response += (
                f"*DCA Position:*\n"
                f"Symbol: {orch.config.symbol}\n"
                f"Entry: {pos.avg_entry_price}\n"
                f"Amount: {pos.total_amount}\n"
                f"Steps: {orch.dca_engine.current_step}/{orch.dca_engine.max_steps}\n"
            )
            if orch.current_price:
                pnl = pos.get_pnl(orch.current_price)
                pnl_pct = pos.get_pnl_percentage(orch.current_price)
                response += f"P&L: {pnl} ({float(pnl_pct):.2%})\n"
            response += "\n"

        # Trend-Follower positions
        if orch.trend_follower_strategy:
            active = orch.trend_follower_strategy.position_manager.active_positions
            if active:
                has_positions = True
                response += f"*Trend-Follower ({len(active)} active):*\n"
                for pid, pos in list(active.items())[:5]:
                    response += (
                        f"ID: `{pid[:8]}`\n"
                        f"  Type: {pos.signal_type.value}\n"
                        f"  Entry: {pos.entry_price}\n"
                        f"  Size: {pos.size}\n\n"
                    )
                if len(active) > 5:
                    response += f"... and {len(active) - 5} more positions\n"

        # Grid active orders as proxy for "positions"
        if orch.grid_engine and orch.grid_engine.active_orders:
            has_positions = True
            orders = orch.grid_engine.active_orders
            response += f"*Grid Orders ({len(orders)} active):*\n"
            for _oid, order in list(orders.items())[:5]:
                response += f"  {order.side.upper()} @ {order.price}\n"
            if len(orders) > 5:
                response += f"  ... and {len(orders) - 5} more\n"

        if not has_positions:
            response += "No open positions"

        await message.answer(response, parse_mode="Markdown")

    async def _cmd_report(self, message: Message) -> None:
        """Handle /report command — performance report."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        bot_name = args[1] if len(args) > 1 else None

        if bot_name and bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        targets = {bot_name: self.orchestrators[bot_name]} if bot_name else self.orchestrators

        for name, orch in targets.items():
            response = f"📈 *Performance Report: {name}*\n\n"
            status = await orch.get_status()

            response += f"State: {status['state']}\n" f"Strategy: {status['strategy']}\n"

            if status.get("current_price"):
                response += f"Current Price: {status['current_price']}\n"

            # Grid stats
            if "grid" in status:
                grid = status["grid"]
                response += (
                    f"\n*Grid:*\n"
                    f"Total Profit: {grid.get('total_profit', 0)}\n"
                    f"Buy Count: {grid.get('buy_count', 0)}\n"
                    f"Sell Count: {grid.get('sell_count', 0)}\n"
                )

            # DCA stats
            if "dca" in status:
                dca = status["dca"]
                response += (
                    f"\n*DCA:*\n"
                    f"Position: {'Yes' if dca.get('has_position') else 'No'}\n"
                    f"Steps: {dca.get('current_step', 0)}/{dca.get('max_steps', 0)}\n"
                )

            # Trend-Follower stats
            if "trend_follower" in status:
                tf = status["trend_follower"]
                response += (
                    f"\n*Trend-Follower:*\n" f"Active Positions: {tf.get('active_positions', 0)}\n"
                )
                stats = tf.get("statistics", {})
                if stats:
                    response += (
                        f"Total Trades: {stats.get('total_trades', 0)}\n"
                        f"Win Rate: {stats.get('win_rate', 0):.1%}\n"
                        f"Total P&L: {stats.get('total_pnl', 0)}\n"
                    )

            # Risk status
            if "risk" in status:
                risk = status["risk"]
                response += "\n*Risk:*\n"
                if risk.get("drawdown") is not None:
                    response += f"Drawdown: {float(risk['drawdown']):.2%}\n"
                if risk.get("pnl_percentage") is not None:
                    response += f"P&L: {float(risk['pnl_percentage']):.2%}\n"
                response += f"Halted: {'Yes' if risk.get('is_halted') else 'No'}\n"

            # Market regime
            if "market_regime" in status:
                regime = status["market_regime"]
                response += (
                    f"\n*Market Regime:*\n"
                    f"Regime: {regime.get('regime', 'unknown')}\n"
                    f"Confidence: {regime.get('confidence', 0):.1%}\n"
                )

            # Strategy registry
            if "strategy_registry" in status:
                reg = status["strategy_registry"]
                response += (
                    f"\n*Strategies:*\n"
                    f"Total: {reg.get('total', 0)}\n"
                    f"Active: {reg.get('active', 0)}\n"
                )

            await message.answer(response, parse_mode="Markdown")

    async def _cmd_switch_strategy(self, message: Message) -> None:
        """Handle /switch_strategy command — switch bot strategy."""
        if not self._check_auth(message):
            await message.answer("⛔ Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 3:
            await message.answer(
                "Usage: /switch\\_strategy <bot\\_name> <strategy\\_id>\n\n"
                "Available strategies: grid, dca, trend\\_follower, smc"
            )
            return

        bot_name = args[1]
        strategy_id = args[2]

        if bot_name not in self.orchestrators:
            await message.answer(f"❌ Bot '{bot_name}' not found")
            return

        orch = self.orchestrators[bot_name]

        try:
            # Show current strategies
            registry_status = orch.strategy_registry.get_registry_status()
            active_strategies = registry_status.get("active", 0)

            # Stop all active strategies
            if active_strategies > 0:
                await orch.strategy_registry.stop_all()

            # Register and start new strategy
            orch.register_strategy(
                strategy_id=strategy_id,
                strategy_type=strategy_id,
            )
            await orch.start_strategy(strategy_id)

            await message.answer(
                f"✅ Strategy switched to *{strategy_id}* for bot *{bot_name}*",
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(
                "switch_strategy_failed",
                bot_name=bot_name,
                strategy=strategy_id,
                error=str(e),
            )
            await message.answer(f"❌ Failed to switch strategy: {str(e)}")

    # ------------------------------------------------------------------
    # Multi-pair / Portfolio commands (A5)
    # ------------------------------------------------------------------

    async def _cmd_scan(self, message: Message) -> None:
        """Handle /scan — run market scanner and show top-5 with regime and recommendation."""
        if not self._check_auth(message):
            await message.answer("Unauthorized access")
            return

        # Try to get the scanner from the BotApplication (if injected)
        scanner = getattr(self, "_app", None)
        if scanner:
            scanner = getattr(scanner, "_scanner", None)

        if scanner is None:
            await message.answer(
                "Market scanner is not configured. "
                "Enable auto_trade in config to use /scan."
            )
            return

        await message.answer("Scanning market... please wait.")
        try:
            results = await scanner.scan()
            if not results:
                await message.answer("No pairs found matching scanner criteria.")
                return

            lines = ["Top pairs from market scan:\n"]
            for i, r in enumerate(results[:5], 1):
                confidence = getattr(r, "confidence", 0.0)
                regime = getattr(r, "regime", "unknown")
                recommendation = getattr(r, "recommended_strategy", "N/A")
                symbol = getattr(r, "symbol", "?")
                lines.append(
                    f"{i}. {symbol}\n"
                    f"   Regime: {regime} | Confidence: {confidence:.0%}\n"
                    f"   Recommendation: {recommendation}\n"
                )
            await message.answer("\n".join(lines))
        except Exception as e:
            logger.error("cmd_scan_failed", error=str(e))
            await message.answer(f"Scan failed: {e}")

    async def _cmd_create_bot(self, message: Message) -> None:
        """Handle /create_bot <symbol> <strategy> — create a bot from template."""
        if not self._check_auth(message):
            await message.answer("Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 3:
            await message.answer(
                "Usage: /create_bot <symbol> <strategy>\n\n"
                "Example: /create_bot ETH/USDT hybrid\n"
                "Strategies: grid, dca, hybrid, trend_follower"
            )
            return

        symbol = args[1]
        strategy = args[2].lower()

        app = getattr(self, "_app", None)
        if app is None:
            await message.answer("BotApplication not linked. Cannot create bot dynamically.")
            return

        template_mgr = getattr(app, "_pair_template_manager", None)
        exchange_client = getattr(app, "_main_exchange_client", None)
        main_config = getattr(app, "_main_config", None)

        if not template_mgr or not exchange_client or not main_config or not main_config.bots:
            await message.answer(
                "Auto-trade is not configured. Enable auto_trade in config."
            )
            return

        await message.answer(f"Creating bot for {symbol} ({strategy})...")
        try:
            base_cfg = main_config.bots[0]
            new_cfg = await template_mgr.create_config(
                symbol=symbol,
                strategy=strategy,
                exchange_client=exchange_client,
                base_config=base_cfg,
            )
            orchestrator = await app.add_bot(new_cfg)
            if orchestrator:
                await message.answer(f"Bot '{new_cfg.name}' created and started for {symbol}.")
            else:
                await message.answer(f"Failed to start bot for {symbol}. Check logs.")
        except Exception as e:
            logger.error("cmd_create_bot_failed", symbol=symbol, error=str(e))
            await message.answer(f"Error creating bot: {e}")

    async def _cmd_delete_bot(self, message: Message) -> None:
        """Handle /delete_bot <name> — gracefully stop and remove a bot."""
        if not self._check_auth(message):
            await message.answer("Unauthorized access")
            return

        args = message.text.split() if message.text else []
        if len(args) < 2:
            await message.answer(
                "Usage: /delete_bot <bot_name>\n\n"
                "Use /list to see current bots."
            )
            return

        bot_name = args[1]
        app = getattr(self, "_app", None)

        if app is None:
            await message.answer("BotApplication not linked.")
            return

        if bot_name not in self.orchestrators:
            await message.answer(f"Bot '{bot_name}' not found.")
            return

        await message.answer(f"Stopping and removing bot '{bot_name}'...")
        try:
            await app.remove_bot(bot_name)
            await message.answer(f"Bot '{bot_name}' removed successfully.")
        except Exception as e:
            logger.error("cmd_delete_bot_failed", bot_name=bot_name, error=str(e))
            await message.answer(f"Error removing bot: {e}")

    async def _cmd_portfolio(self, message: Message) -> None:
        """Handle /portfolio — show portfolio P&L, exposure, and capital distribution."""
        if not self._check_auth(message):
            await message.answer("Unauthorized access")
            return

        if not self.orchestrators:
            await message.answer("No active bots.")
            return

        app = getattr(self, "_app", None)
        prm = getattr(app, "_portfolio_risk_manager", None) if app else None

        lines = ["Portfolio Summary\n"]

        total_pnl = 0.0
        for bot_name, orch in self.orchestrators.items():
            try:
                status = orch.get_status()
                symbol = status.get("symbol", "?")
                state = status.get("state", "?")
                lines.append(f"• {bot_name} ({symbol}) — {state}")
            except Exception:
                lines.append(f"• {bot_name} — status unavailable")

        if prm:
            try:
                summary = prm.get_summary()
                lines.append(
                    f"\nCapital Pool:\n"
                    f"  Total: ${summary['total_capital']:,.0f}\n"
                    f"  Allocated: ${summary['pool']['total_allocated']:,.0f} "
                    f"({summary['pool']['utilization_pct']}%)\n"
                    f"  Drawdown: {summary['drawdown_pct']}%\n"
                    f"  Halted: {'YES' if summary['halted'] else 'No'}"
                )
            except Exception as e:
                lines.append(f"\nPortfolio risk manager error: {e}")

        await message.answer("\n".join(lines))

    async def _broadcast(self, text: str) -> None:
        """Send a plain-text message to all allowed chat IDs."""
        for chat_id in self.allowed_chat_ids:
            try:
                await self.bot.send_message(chat_id=chat_id, text=text)
            except Exception as e:
                logger.error("broadcast_failed", chat_id=chat_id, error=str(e))

    async def _listen_to_events(self) -> None:
        """Listen to Redis events and send notifications."""
        logger.info("event_listener_started")

        self.redis_client = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)

        # Subscribe to all bot channels
        pubsub = self.redis_client.pubsub()
        for bot_name in self.orchestrators.keys():
            channel = f"trading_events:{bot_name}"
            await pubsub.subscribe(channel)

        logger.info("subscribed_to_events", bot_count=len(self.orchestrators))

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    event = TradingEvent.from_json(message["data"])
                    await self._handle_event(event)
                except Exception as e:
                    logger.error("event_handling_failed", error=str(e))

        except asyncio.CancelledError:
            logger.info("event_listener_cancelled")
        finally:
            await pubsub.unsubscribe()
            await self.redis_client.aclose()

        logger.info("event_listener_stopped")

    async def _handle_event(self, event: TradingEvent) -> None:
        """
        Handle incoming trading event and send notifications.

        Args:
            event: Trading event
        """
        # Only notify on important events
        important_events = {
            EventType.BOT_STARTED,
            EventType.BOT_STOPPED,
            EventType.BOT_EMERGENCY_STOP,
            EventType.ORDER_FILLED,
            EventType.DCA_TRIGGERED,
            EventType.TAKE_PROFIT_HIT,
            EventType.RISK_LIMIT_HIT,
            EventType.STOP_LOSS_TRIGGERED,
            EventType.ERROR_OCCURRED,
            # v2.0 events
            EventType.REGIME_CHANGED,
            EventType.HYBRID_TRANSITION,
            EventType.HEALTH_DEGRADED,
            EventType.HEALTH_CRITICAL,
            EventType.STRATEGY_ERROR,
        }

        if event.event_type not in important_events:
            return

        # Format notification message
        notification = self._format_event_notification(event)

        # Send to all allowed chats
        for chat_id in self.allowed_chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=notification,
                    parse_mode="Markdown",
                )
            except Exception:
                # Fallback: send without Markdown if parsing fails
                try:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=notification,
                    )
                except Exception as e:
                    logger.error("notification_send_failed", chat_id=chat_id, error=str(e))

    def _format_event_notification(self, event: TradingEvent) -> str:
        """Format event as notification message."""
        emoji_map = {
            EventType.BOT_STARTED: "✅",
            EventType.BOT_STOPPED: "🛑",
            EventType.BOT_EMERGENCY_STOP: "🚨",
            EventType.ORDER_FILLED: "✅",
            EventType.DCA_TRIGGERED: "📉",
            EventType.TAKE_PROFIT_HIT: "💰",
            EventType.RISK_LIMIT_HIT: "⚠️",
            EventType.STOP_LOSS_TRIGGERED: "🛑",
            EventType.ERROR_OCCURRED: "❌",
            # v2.0 events
            EventType.REGIME_CHANGED: "🔄",
            EventType.HYBRID_TRANSITION: "🔀",
            EventType.HEALTH_DEGRADED: "⚠️",
            EventType.HEALTH_CRITICAL: "🚨",
            EventType.STRATEGY_ERROR: "❌",
        }

        emoji = emoji_map.get(event.event_type, "ℹ️")
        title = event.event_type.value.replace("_", " ").title()

        message = f"{emoji} *{title}*\n\n"
        message += f"Bot: {event.bot_name}\n"
        message += f"Time: {event.timestamp}\n"

        if event.data:
            message += "\n*Details:*\n"
            for key, value in event.data.items():
                message += f"{key}: {value}\n"

        return message

    def _format_status(self, status: dict[str, Any]) -> str:
        """Format bot status as message."""
        state_emoji = self._get_state_emoji(BotState(status["state"]))

        message = (
            f"{state_emoji} *Bot Status: {status['bot_name']}*\n\n"
            f"Symbol: {status['symbol']}\n"
            f"Strategy: {status['strategy']}\n"
            f"State: {status['state']}\n"
            f"Dry Run: {'Yes' if status['dry_run'] else 'No'}\n"
        )

        if status.get("current_price"):
            message += f"Current Price: {status['current_price']}\n"

        if "grid" in status:
            grid = status["grid"]
            message += (
                f"\n*Grid Status:*\n"
                f"Active Orders: {grid['active_orders']}\n"
                f"Total Profit: {grid['total_profit']}\n"
            )

        if "dca" in status:
            dca = status["dca"]
            if dca["has_position"]:
                message += (
                    f"\n*DCA Position:*\n"
                    f"Steps: {dca['current_step']}/{dca['max_steps']}\n"
                    f"Avg Entry: {dca['avg_entry_price']}\n"
                )

        if "risk" in status:
            risk = status["risk"]
            message += f"\n*Risk Status:*\n" f"Halted: {'Yes' if risk['halted'] else 'No'}\n"
            if risk["drawdown"]:
                message += f"Drawdown: {float(risk['drawdown']):.2%}\n"

        return message

    @staticmethod
    def _get_state_emoji(state: BotState) -> str:
        """Get emoji for bot state."""
        emoji_map = {
            BotState.STOPPED: "⚫",
            BotState.STARTING: "🟡",
            BotState.RUNNING: "🟢",
            BotState.PAUSED: "🟡",
            BotState.STOPPING: "🟠",
            BotState.EMERGENCY: "🔴",
        }
        return emoji_map.get(state, "⚪")

    async def start(self) -> None:
        """Start the Telegram bot."""
        logger.info("starting_telegram_bot")

        # Start event listener
        self.event_listener_task = asyncio.create_task(self._listen_to_events())

        # Start polling
        await self.dp.start_polling(self.bot)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        logger.info("stopping_telegram_bot")

        # Stop event listener
        if self.event_listener_task:
            self.event_listener_task.cancel()
            try:
                await self.event_listener_task
            except asyncio.CancelledError:
                pass

        # Close bot session
        await self.bot.session.close()

        logger.info("telegram_bot_stopped")
