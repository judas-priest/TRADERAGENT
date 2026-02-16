"""
BotOrchestrator - Main coordinator for trading strategies and lifecycle management.

v2.0: Multi-strategy support with market regime detection and health monitoring.
Manages Grid, DCA, SMC, and Trend-Follower engines with dynamic strategy selection.
"""

import asyncio
from decimal import Decimal
from enum import Enum
from typing import Any

import pandas as pd
import redis.asyncio as redis

from bot.api.exchange_client import ExchangeAPIClient
from bot.config.schemas import BotConfig, StrategyType
from bot.core.dca_engine import DCAEngine
from bot.core.grid_engine import GridEngine, GridType
from bot.core.risk_manager import RiskManager
from bot.database.manager import DatabaseManager
from bot.orchestrator.events import EventType, TradingEvent
from bot.orchestrator.health_monitor import HealthMonitor, HealthCheckResult, HealthThresholds
from bot.orchestrator.market_regime import (
    MarketRegimeDetector,
    MarketRegime,
    RecommendedStrategy,
    RegimeAnalysis,
)
from bot.orchestrator.strategy_registry import (
    StrategyInstance,
    StrategyRegistry,
    StrategyState,
)
from bot.strategies.trend_follower import TrendFollowerConfig as TrendFollowerDataclassConfig
from bot.strategies.trend_follower import TrendFollowerStrategy
from bot.strategies.trend_follower.entry_logic import SignalType
from bot.utils.logger import get_logger

logger = get_logger(__name__)


class BotState(str, Enum):
    """Bot lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    EMERGENCY = "emergency"


class BotOrchestrator:
    """
    Main orchestrator for coordinating trading strategies.

    v2.0 Features:
    - Multi-strategy lifecycle management via StrategyRegistry
    - Market regime detection for dynamic strategy selection
    - Health monitoring with auto-restart capabilities
    - Manages lifecycle of Grid, DCA, SMC, and Trend-Follower engines
    - Coordinates strategy execution and conflict resolution
    - Publishes events via Redis Pub/Sub
    - Handles state transitions (Running, Paused, Stopped, Emergency)
    - Integrates risk management across all strategies
    """

    def __init__(
        self,
        bot_config: BotConfig,
        exchange_client: Any,
        db_manager: DatabaseManager,
        redis_url: str = "redis://localhost:6379",
    ):
        """
        Initialize Bot Orchestrator.

        Args:
            bot_config: Bot configuration
            exchange_client: Exchange API client
            db_manager: Database manager
            redis_url: Redis connection URL
        """
        self.config = bot_config
        self.exchange = exchange_client
        self.db = db_manager
        self.redis_url = redis_url

        # State management
        self.state = BotState.STOPPED
        self._state_lock = asyncio.Lock()

        # Redis for event pub/sub
        self.redis_client: redis.Redis | None = None
        self.redis_pubsub: redis.client.PubSub | None = None

        # Trading engines
        self.grid_engine: GridEngine | None = None
        self.dca_engine: DCAEngine | None = None
        self.trend_follower_strategy: TrendFollowerStrategy | None = None
        self.risk_manager: RiskManager | None = None

        # Runtime state
        self._running = False
        self._main_task: asyncio.Task | None = None
        self._price_monitor_task: asyncio.Task | None = None
        self._regime_monitor_task: asyncio.Task | None = None
        self.current_price: Decimal | None = None

        # v2.0: Multi-strategy components
        self.strategy_registry = StrategyRegistry(max_strategies=10)
        self.market_regime_detector = MarketRegimeDetector()
        self.health_monitor = HealthMonitor(
            registry=self.strategy_registry,
            thresholds=HealthThresholds(),
            check_interval=30.0,
        )
        self._current_regime: RegimeAnalysis | None = None
        self._regime_check_interval: float = 60.0  # seconds

        # Set health callbacks
        self.health_monitor.set_unhealthy_callback(self._on_strategy_unhealthy)
        self.health_monitor.set_critical_callback(self._on_strategy_critical)

        logger.info(
            "bot_orchestrator_initialized",
            bot_name=bot_config.name,
            symbol=bot_config.symbol,
            strategy=bot_config.strategy,
            version="2.0",
        )

    async def initialize(self) -> None:
        """Initialize orchestrator and all components."""
        logger.info("initializing_orchestrator", bot_name=self.config.name)

        # Connect to Redis
        self.redis_client = redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
        await self.redis_client.ping()
        logger.info("redis_connected")

        # Initialize risk manager
        if self.config.risk_management:
            self.risk_manager = RiskManager(
                max_position_size=Decimal(str(self.config.risk_management.max_position_size)),
                stop_loss_percentage=(
                    Decimal(str(self.config.risk_management.stop_loss_percentage))
                    if self.config.risk_management.stop_loss_percentage
                    else None
                ),
                max_daily_loss=(
                    Decimal(str(self.config.risk_management.max_daily_loss))
                    if self.config.risk_management.max_daily_loss
                    else None
                ),
                min_order_size=Decimal(str(self.config.risk_management.min_order_size)),
            )

            # Initialize with current balance
            balance = await self.exchange.fetch_balance()
            quote_currency = self.config.symbol.split("/")[1]
            # balance structure: {'free': {'USDT': 100000, ...}, 'total': {...}, 'used': {...}}
            free_balances = balance.get("free", {})
            available_balance = Decimal(str(free_balances.get(quote_currency, 0)))
            self.risk_manager.initialize_balance(available_balance)
            logger.info(
                "risk_manager_initialized",
                initial_balance=str(available_balance),
            )

        # Initialize Grid engine if enabled
        if self.config.strategy in ["grid", "hybrid"] and self.config.grid:
            self.grid_engine = GridEngine(
                symbol=self.config.symbol,
                upper_price=Decimal(str(self.config.grid.upper_price)),
                lower_price=Decimal(str(self.config.grid.lower_price)),
                grid_levels=self.config.grid.grid_levels,
                amount_per_grid=Decimal(str(self.config.grid.amount_per_grid)),
                profit_per_grid=Decimal(str(self.config.grid.profit_per_grid)),
                grid_type=GridType.STATIC,
            )
            logger.info("grid_engine_initialized")

        # Initialize DCA engine if enabled
        if self.config.strategy in ["dca", "hybrid"] and self.config.dca:
            self.dca_engine = DCAEngine(
                symbol=self.config.symbol,
                trigger_percentage=Decimal(str(self.config.dca.trigger_percentage)),
                amount_per_step=Decimal(str(self.config.dca.amount_per_step)),
                max_steps=self.config.dca.max_steps,
                take_profit_percentage=Decimal(str(self.config.dca.take_profit_percentage)),
            )
            logger.info("dca_engine_initialized")

        # Initialize Trend-Follower strategy if enabled
        if self.config.strategy == StrategyType.TREND_FOLLOWER and self.config.trend_follower:
            # Get initial balance for strategy
            balance = await self.exchange.fetch_balance()
            quote_currency = self.config.symbol.split("/")[1]
            free_balances = balance.get("free", {})
            initial_capital = Decimal(str(free_balances.get(quote_currency, 0)))

            # Convert Pydantic TrendFollowerConfig to dataclass TrendFollowerConfig
            pydantic_tf = self.config.trend_follower
            dataclass_config = TrendFollowerDataclassConfig(
                ema_fast_period=pydantic_tf.ema_fast_period,
                ema_slow_period=pydantic_tf.ema_slow_period,
                atr_period=pydantic_tf.atr_period,
                rsi_period=pydantic_tf.rsi_period,
                volume_multiplier=pydantic_tf.volume_multiplier,
                max_atr_filter_pct=pydantic_tf.atr_filter_threshold,
                tp_multipliers=(
                    pydantic_tf.tp_atr_multiplier_sideways,
                    pydantic_tf.tp_atr_multiplier_weak,
                    pydantic_tf.tp_atr_multiplier_strong,
                ),
                sl_multipliers=(
                    pydantic_tf.sl_atr_multiplier_sideways,
                    pydantic_tf.sl_atr_multiplier_trend,
                    pydantic_tf.sl_atr_multiplier_trend,
                ),
                risk_per_trade_pct=pydantic_tf.risk_per_trade_pct,
                max_position_size_usd=pydantic_tf.max_position_size_usd,
                max_daily_loss_usd=pydantic_tf.max_daily_loss_usd,
                max_positions=pydantic_tf.max_positions,
                log_all_signals=pydantic_tf.log_all_signals,
            )
            self.trend_follower_strategy = TrendFollowerStrategy(
                config=dataclass_config,
                initial_capital=initial_capital,
                log_trades=True,
            )
            logger.info(
                "trend_follower_strategy_initialized",
                initial_capital=str(initial_capital),
                ema_fast=self.config.trend_follower.ema_fast_period,
                ema_slow=self.config.trend_follower.ema_slow_period,
            )

        logger.info("orchestrator_initialized", bot_name=self.config.name)

    async def start(self) -> None:
        """Start the bot and begin trading."""
        async with self._state_lock:
            if self.state != BotState.STOPPED:
                logger.warning(
                    "bot_already_running",
                    current_state=self.state,
                )
                return

            logger.info("starting_bot", bot_name=self.config.name)
            self.state = BotState.STARTING

            try:
                # Get current price
                ticker = await self.exchange.fetch_ticker(self.config.symbol)
                self.current_price = Decimal(str(ticker["last"]))
                logger.info("current_price_fetched", price=str(self.current_price))

                # Initialize grid if enabled
                if self.grid_engine:
                    grid_orders = self.grid_engine.initialize_grid(self.current_price)
                    logger.info(
                        "grid_initialized",
                        order_count=len(grid_orders),
                    )

                    # Place grid orders on exchange (if not dry run)
                    if not self.config.dry_run:
                        await self._place_grid_orders(grid_orders)

                    await self._publish_event(
                        EventType.GRID_INITIALIZED,
                        {
                            "order_count": len(grid_orders),
                            "current_price": str(self.current_price),
                        },
                    )

                # Initialize DCA if enabled
                if self.dca_engine:
                    self.dca_engine.reset()
                    logger.info("dca_engine_ready")

                # Start main loop
                self._running = True
                self.state = BotState.RUNNING
                self._main_task = asyncio.create_task(self._main_loop())
                self._price_monitor_task = asyncio.create_task(self._price_monitor())

                # v2.0: Start regime monitor and health monitor
                self._regime_monitor_task = asyncio.create_task(
                    self._regime_monitor_loop()
                )
                await self.health_monitor.start()

                await self._publish_event(
                    EventType.BOT_STARTED,
                    {"strategy": self.config.strategy, "version": "2.0"},
                )

                logger.info("bot_started", bot_name=self.config.name)

            except Exception as e:
                logger.error("bot_start_failed", error=str(e), exc_info=True)
                self.state = BotState.STOPPED
                await self._publish_event(
                    EventType.ERROR_OCCURRED,
                    {"error": str(e), "phase": "start"},
                )
                raise

    async def stop(self) -> None:
        """Stop the bot gracefully."""
        async with self._state_lock:
            if self.state == BotState.STOPPED:
                logger.warning("bot_already_stopped")
                return

            logger.info("stopping_bot", bot_name=self.config.name)
            self.state = BotState.STOPPING
            self._running = False

            # Cancel running tasks
            if self._main_task and not self._main_task.done():
                self._main_task.cancel()
                try:
                    await self._main_task
                except asyncio.CancelledError:
                    pass

            if self._price_monitor_task and not self._price_monitor_task.done():
                self._price_monitor_task.cancel()
                try:
                    await self._price_monitor_task
                except asyncio.CancelledError:
                    pass

            # v2.0: Stop regime monitor
            if self._regime_monitor_task and not self._regime_monitor_task.done():
                self._regime_monitor_task.cancel()
                try:
                    await self._regime_monitor_task
                except asyncio.CancelledError:
                    pass

            # v2.0: Stop health monitor and all strategies
            await self.health_monitor.stop()
            await self.strategy_registry.stop_all()

            # Cancel all open orders (if not dry run)
            if not self.config.dry_run:
                await self._cancel_all_orders()

            self.state = BotState.STOPPED
            await self._publish_event(EventType.BOT_STOPPED, {})

            logger.info("bot_stopped", bot_name=self.config.name)

    async def pause(self) -> None:
        """Pause the bot (stop placing new orders but keep existing ones)."""
        async with self._state_lock:
            if self.state != BotState.RUNNING:
                logger.warning("bot_not_running", current_state=self.state)
                return

            logger.info("pausing_bot", bot_name=self.config.name)
            self.state = BotState.PAUSED
            await self._publish_event(EventType.BOT_PAUSED, {})
            logger.info("bot_paused")

    async def resume(self) -> None:
        """Resume bot from paused state."""
        async with self._state_lock:
            if self.state != BotState.PAUSED:
                logger.warning("bot_not_paused", current_state=self.state)
                return

            logger.info("resuming_bot", bot_name=self.config.name)
            self.state = BotState.RUNNING

            # Resume risk manager if halted
            if self.risk_manager:
                self.risk_manager.resume()

            await self._publish_event(EventType.BOT_RESUMED, {})
            logger.info("bot_resumed")

    async def emergency_stop(self) -> None:
        """Emergency stop - immediate halt and cancel all orders."""
        async with self._state_lock:
            logger.warning("emergency_stop_triggered", bot_name=self.config.name)
            self.state = BotState.EMERGENCY
            self._running = False

            # Cancel all tasks immediately
            if self._main_task:
                self._main_task.cancel()
            if self._price_monitor_task:
                self._price_monitor_task.cancel()

            # Cancel all orders
            if not self.config.dry_run:
                try:
                    await self._cancel_all_orders()
                except Exception as e:
                    logger.error("emergency_cancel_failed", error=str(e))

            await self._publish_event(
                EventType.BOT_EMERGENCY_STOP,
                {"reason": "manual_emergency_stop"},
            )

            logger.warning("emergency_stop_completed")

    async def _main_loop(self) -> None:
        """Main trading loop - processes orders and strategy logic."""
        logger.info("main_loop_started")

        while self._running:
            try:
                # Skip processing if paused
                if self.state == BotState.PAUSED:
                    await asyncio.sleep(1)
                    continue

                # Process grid orders
                if self.grid_engine:
                    await self._process_grid_orders()

                # Process DCA logic
                if self.dca_engine and self.current_price:
                    await self._process_dca_logic()

                # Process Trend-Follower logic
                if self.trend_follower_strategy and self.current_price:
                    await self._process_trend_follower_logic()

                # Update risk manager
                if self.risk_manager:
                    await self._update_risk_manager()

                # Sleep between iterations
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("main_loop_cancelled")
                break
            except Exception as e:
                logger.error("main_loop_error", error=str(e), exc_info=True)
                await self._publish_event(
                    EventType.ERROR_OCCURRED,
                    {"error": str(e), "phase": "main_loop"},
                )
                await asyncio.sleep(5)  # Wait before retrying

        logger.info("main_loop_stopped")

    async def _price_monitor(self) -> None:
        """Monitor price updates and publish events."""
        logger.info("price_monitor_started")

        while self._running:
            try:
                ticker = await self.exchange.fetch_ticker(self.config.symbol)
                new_price = Decimal(str(ticker["last"]))

                if new_price != self.current_price:
                    self.current_price = new_price
                    await self._publish_event(
                        EventType.PRICE_UPDATED,
                        {"price": str(self.current_price)},
                    )

                await asyncio.sleep(5)  # Update every 5 seconds

            except asyncio.CancelledError:
                logger.info("price_monitor_cancelled")
                break
            except Exception as e:
                logger.error("price_monitor_error", error=str(e))
                await asyncio.sleep(5)

        logger.info("price_monitor_stopped")

    async def _process_grid_orders(self) -> None:
        """Process grid order fills and rebalancing."""
        if not self.grid_engine:
            return

        # Check for filled orders (simulation for dry run)
        if self.config.dry_run:
            # In dry run, simulate order fills based on current price
            pass
        else:
            # Fetch actual orders from exchange
            open_orders = await self.exchange.fetch_open_orders(self.config.symbol)
            # Process filled orders
            for order_id, grid_order in list(self.grid_engine.active_orders.items()):
                if order_id not in [o["id"] for o in open_orders]:
                    # Order was filled
                    filled_price = grid_order.price
                    rebalance_order = self.grid_engine.handle_order_filled(order_id, filled_price)

                    await self._publish_event(
                        EventType.ORDER_FILLED,
                        {
                            "order_id": order_id,
                            "price": str(filled_price),
                            "side": grid_order.side,
                        },
                    )

                    if rebalance_order and self.state == BotState.RUNNING:
                        await self._place_single_order(rebalance_order)

    async def _process_dca_logic(self) -> None:
        """Process DCA triggers and take profit logic."""
        if not self.dca_engine or not self.current_price:
            return

        # Update DCA engine with current price
        dca_actions = self.dca_engine.update_price(self.current_price)

        # Handle DCA trigger
        if dca_actions["dca_triggered"] and self.state == BotState.RUNNING:
            # Check risk limits
            if self.risk_manager:
                order_value = self.dca_engine.amount_per_step
                current_position = (
                    self.dca_engine.position.total_amount
                    if self.dca_engine.position
                    else Decimal("0")
                )
                balance = await self._get_available_balance()

                risk_check = self.risk_manager.check_trade(order_value, current_position, balance)
                if not risk_check:
                    logger.warning("dca_blocked_by_risk", reason=risk_check.reason)
                    return

            # Execute DCA step
            success = self.dca_engine.execute_dca_step(self.current_price)
            if success:
                await self._publish_event(
                    EventType.DCA_TRIGGERED,
                    {
                        "price": str(self.current_price),
                        "step": self.dca_engine.current_step,
                        "avg_entry": str(self.dca_engine.position.avg_entry_price),
                    },
                )

                # Place buy order on exchange
                if not self.config.dry_run:
                    await self._place_dca_order()

        # Handle take profit
        if dca_actions["tp_triggered"] and self.state == BotState.RUNNING:
            pnl = self.dca_engine.close_position(self.current_price)
            await self._publish_event(
                EventType.TAKE_PROFIT_HIT,
                {
                    "price": str(self.current_price),
                    "pnl": str(pnl),
                },
            )

            # Close position on exchange
            if not self.config.dry_run:
                await self._close_dca_position()

    async def _update_risk_manager(self) -> None:
        """Update risk manager with current balance and position."""
        if not self.risk_manager:
            return

        # Fetch current balance
        balance = await self._get_available_balance()
        self.risk_manager.update_balance(balance)

        # Check if risk limits triggered emergency stop
        risk_status = self.risk_manager.get_risk_status()
        if risk_status["is_halted"]:
            logger.warning(
                "risk_limit_triggered",
                reason=risk_status["halt_reason"],
            )
            await self.emergency_stop()

    async def _place_grid_orders(self, orders: list) -> None:
        """Place grid orders on exchange."""
        for order in orders:
            await self._place_single_order(order)

    async def _place_single_order(self, order) -> None:
        """Place a single order on exchange."""
        try:
            result = await self.exchange.create_order(
                symbol=self.config.symbol,
                order_type="limit",
                side=order.side,
                amount=float(order.amount),
                price=float(order.price),
            )
            order_id = result["id"]
            if self.grid_engine:
                self.grid_engine.register_order(order, order_id)

            await self._publish_event(
                EventType.ORDER_PLACED,
                {
                    "order_id": order_id,
                    "side": order.side,
                    "price": str(order.price),
                    "amount": str(order.amount),
                },
            )
        except Exception as e:
            logger.error("order_placement_failed", error=str(e))
            await self._publish_event(
                EventType.ORDER_FAILED,
                {"error": str(e), "order": str(order)},
            )

    async def _place_dca_order(self) -> None:
        """Place DCA buy order."""
        if not self.dca_engine or not self.current_price:
            return

        try:
            # amount_per_step is in quote currency (USD), convert to base currency
            base_amount = float(self.dca_engine.amount_per_step / self.current_price)
            result = await self.exchange.create_order(
                symbol=self.config.symbol,
                order_type="market",
                side="buy",
                amount=base_amount,
            )
            logger.info("dca_order_placed", order_id=result["id"], base_amount=base_amount)
        except Exception as e:
            logger.error("dca_order_failed", error=str(e))

    async def _close_dca_position(self) -> None:
        """Close DCA position."""
        if not self.dca_engine or not self.dca_engine.position:
            return

        try:
            # total_amount tracks accumulated amount_per_step values (in USD)
            # Convert to base currency using current price
            base_amount = float(self.dca_engine.position.total_amount / self.current_price)
            result = await self.exchange.create_order(
                symbol=self.config.symbol,
                order_type="market",
                side="sell",
                amount=base_amount,
            )
            logger.info("dca_position_closed", order_id=result["id"], base_amount=base_amount)
        except Exception as e:
            logger.error("dca_close_failed", error=str(e))

    async def _cancel_all_orders(self) -> None:
        """Cancel all open orders."""
        try:
            await self.exchange.cancel_all_orders(self.config.symbol)
            logger.info("all_orders_cancelled")
        except Exception as e:
            logger.error("cancel_orders_failed", error=str(e))

    async def _process_trend_follower_logic(self) -> None:
        """Process Trend-Follower strategy logic."""
        if not self.trend_follower_strategy or not self.current_price:
            return

        try:
            # Fetch OHLCV data for analysis
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol=self.config.symbol,
                timeframe="1h",  # TODO: Make configurable
                limit=100,
            )

            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            # 1. Analyze market
            market_conditions = self.trend_follower_strategy.analyze_market(df)
            logger.debug(
                "trend_follower_market_analyzed",
                phase=market_conditions.phase.value if market_conditions else None,
            )

            # 2. Check for entry signals
            balance = await self._get_available_balance()
            entry_data = self.trend_follower_strategy.check_entry_signal(df, balance)

            if entry_data and self.state == BotState.RUNNING:
                signal, metrics, position_size = entry_data

                # Risk check
                if self.risk_manager:
                    current_position_value = sum(
                        pos.size
                        for pos in self.trend_follower_strategy.position_manager.active_positions.values()
                    )
                    risk_check = self.risk_manager.check_trade(
                        position_size, current_position_value, balance
                    )
                    if not risk_check.approved:
                        logger.warning(
                            "trend_follower_signal_blocked_by_risk", reason=risk_check.reason
                        )
                        return

                # Open position
                position_id = self.trend_follower_strategy.open_position(signal, position_size)

                # Execute order on exchange (if not dry run)
                if not self.config.dry_run:
                    await self._execute_trend_follower_entry(signal, position_size)

                await self._publish_event(
                    EventType.ORDER_PLACED,
                    {
                        "strategy": "trend_follower",
                        "position_id": position_id,
                        "signal_type": signal.signal_type.value,
                        "entry_price": str(signal.entry_price),
                        "position_size": str(position_size),
                        "tp": str(signal.take_profit),
                        "sl": str(signal.stop_loss),
                        "market_phase": market_conditions.phase.value if market_conditions else None,
                    },
                )

                logger.info(
                    "trend_follower_position_opened",
                    position_id=position_id,
                    signal_type=signal.signal_type.value,
                    entry_price=str(signal.entry_price),
                    size=str(position_size),
                )

            # 3. Update existing positions
            active_positions = list(
                self.trend_follower_strategy.position_manager.active_positions.keys()
            )
            for position_id in active_positions:
                exit_reason = self.trend_follower_strategy.update_position(
                    position_id, self.current_price, df
                )

                if exit_reason:
                    # Position was closed
                    position = self.trend_follower_strategy.position_manager.active_positions.get(
                        position_id
                    )

                    if not self.config.dry_run and position:
                        await self._execute_trend_follower_exit(position)

                    await self._publish_event(
                        EventType.ORDER_FILLED,
                        {
                            "strategy": "trend_follower",
                            "position_id": position_id,
                            "exit_reason": exit_reason,
                            "exit_price": str(self.current_price),
                        },
                    )

                    logger.info(
                        "trend_follower_position_closed",
                        position_id=position_id,
                        exit_reason=exit_reason,
                        exit_price=str(self.current_price),
                    )

        except Exception as e:
            logger.error("trend_follower_logic_error", error=str(e), exc_info=True)

    async def _execute_trend_follower_entry(self, signal, position_size: Decimal) -> None:
        """Execute Trend-Follower entry order on exchange."""
        try:
            side = "buy" if signal.signal_type == SignalType.LONG else "sell"

            # Calculate amount in base currency
            amount = float(position_size / signal.entry_price)

            result = await self.exchange.create_order(
                symbol=self.config.symbol,
                order_type="market",
                side=side,
                amount=amount,
            )

            logger.info(
                "trend_follower_entry_executed",
                order_id=result["id"],
                side=side,
                amount=amount,
            )

        except Exception as e:
            logger.error("trend_follower_entry_failed", error=str(e), exc_info=True)
            raise

    async def _execute_trend_follower_exit(self, position) -> None:
        """Execute Trend-Follower exit order on exchange."""
        try:
            # Determine side (opposite of entry)
            side = "sell" if position.signal_type == SignalType.LONG else "buy"

            # Calculate amount in base currency
            amount = float(position.size / position.entry_price)

            result = await self.exchange.create_order(
                symbol=self.config.symbol,
                order_type="market",
                side=side,
                amount=amount,
            )

            logger.info(
                "trend_follower_exit_executed",
                order_id=result["id"],
                side=side,
                amount=amount,
            )

        except Exception as e:
            logger.error("trend_follower_exit_failed", error=str(e), exc_info=True)
            raise

    async def _get_available_balance(self) -> Decimal:
        """Get available balance in quote currency."""
        balance = await self.exchange.fetch_balance()
        quote_currency = self.config.symbol.split("/")[1]
        # balance structure: {'free': {...}, 'total': {...}, 'used': {...}}
        free_balances = balance.get("free", {})
        return Decimal(str(free_balances.get(quote_currency, 0)))

    async def _publish_event(self, event_type: EventType, data: dict[str, Any]) -> None:
        """
        Publish event to Redis Pub/Sub.

        Args:
            event_type: Type of event
            data: Event data
        """
        if not self.redis_client:
            return

        event = TradingEvent.create(
            event_type=event_type,
            bot_name=self.config.name,
            data=data,
        )

        try:
            channel = f"trading_events:{self.config.name}"
            await self.redis_client.publish(channel, event.to_json())
            logger.debug("event_published", event_type=event_type.value)
        except Exception as e:
            logger.error("event_publish_failed", error=str(e))

    async def get_status(self) -> dict[str, Any]:
        """
        Get current bot status.

        Returns:
            Status dictionary with v2.0 components
        """
        status = {
            "bot_name": self.config.name,
            "symbol": self.config.symbol,
            "strategy": self.config.strategy,
            "state": self.state.value,
            "current_price": str(self.current_price) if self.current_price else None,
            "dry_run": self.config.dry_run,
            "version": "2.0",
        }

        # Add grid status
        if self.grid_engine:
            status["grid"] = self.grid_engine.get_grid_status()

        # Add DCA status
        if self.dca_engine:
            status["dca"] = self.dca_engine.get_position_status()

        # Add Trend-Follower status
        if self.trend_follower_strategy:
            active_positions_count = len(
                self.trend_follower_strategy.position_manager.active_positions
            )
            statistics = {}
            if self.trend_follower_strategy.trade_logger:
                statistics = self.trend_follower_strategy.get_statistics()

            status["trend_follower"] = {
                "active_positions": active_positions_count,
                "statistics": statistics,
                "market_conditions": (
                    {
                        "phase": self.trend_follower_strategy.current_market_conditions.phase.value,
                        "trend_strength": self.trend_follower_strategy.current_market_conditions.trend_strength.value,
                        "rsi": str(self.trend_follower_strategy.current_market_conditions.rsi),
                    }
                    if self.trend_follower_strategy.current_market_conditions
                    else None
                ),
            }

        # Add risk status
        if self.risk_manager:
            status["risk"] = self.risk_manager.get_risk_status()

        # v2.0: Strategy registry status
        status["strategy_registry"] = self.strategy_registry.get_registry_status()

        # v2.0: Market regime
        if self._current_regime:
            status["market_regime"] = self._current_regime.to_dict()

        # v2.0: Health monitor
        status["health"] = self.health_monitor.get_health_summary()

        return status

    # =========================================================================
    # v2.0: Multi-Strategy Management
    # =========================================================================

    def register_strategy(
        self,
        strategy_id: str,
        strategy_type: str,
        config: dict[str, Any] | None = None,
    ) -> StrategyInstance:
        """
        Register a new strategy with the orchestrator.

        Args:
            strategy_id: Unique identifier for the strategy.
            strategy_type: Type of strategy ('grid', 'dca', 'smc', 'trend_follower').
            config: Strategy-specific configuration.

        Returns:
            The registered StrategyInstance.
        """
        instance = self.strategy_registry.register(
            strategy_id=strategy_id,
            strategy_type=strategy_type,
            config=config,
        )

        self._publish_event_sync(
            EventType.STRATEGY_REGISTERED,
            {
                "strategy_id": strategy_id,
                "strategy_type": strategy_type,
            },
        )

        return instance

    async def start_strategy(self, strategy_id: str) -> bool:
        """Start a registered strategy."""
        result = await self.strategy_registry.start_strategy(strategy_id)

        if result:
            await self._publish_event(
                EventType.STRATEGY_STARTED,
                {"strategy_id": strategy_id},
            )

        return result

    async def stop_strategy(self, strategy_id: str) -> bool:
        """Stop a running strategy."""
        result = await self.strategy_registry.stop_strategy(strategy_id)

        if result:
            await self._publish_event(
                EventType.STRATEGY_STOPPED,
                {"strategy_id": strategy_id},
            )

        return result

    async def pause_strategy(self, strategy_id: str) -> bool:
        """Pause a running strategy."""
        result = await self.strategy_registry.pause_strategy(strategy_id)

        if result:
            await self._publish_event(
                EventType.STRATEGY_PAUSED,
                {"strategy_id": strategy_id},
            )

        return result

    async def resume_strategy(self, strategy_id: str) -> bool:
        """Resume a paused strategy."""
        result = await self.strategy_registry.resume_strategy(strategy_id)

        if result:
            await self._publish_event(
                EventType.STRATEGY_RESUMED,
                {"strategy_id": strategy_id},
            )

        return result

    def get_active_strategies(self) -> list[StrategyInstance]:
        """Get all currently active strategies."""
        return self.strategy_registry.get_active()

    def get_strategy_status(self, strategy_id: str) -> dict[str, Any] | None:
        """Get status of a specific strategy."""
        instance = self.strategy_registry.get(strategy_id)
        if instance:
            return instance.get_status()
        return None

    # =========================================================================
    # v2.0: Market Regime Detection
    # =========================================================================

    async def detect_market_regime(self) -> RegimeAnalysis | None:
        """
        Fetch market data and detect current regime.

        Returns:
            RegimeAnalysis or None on failure.
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol=self.config.symbol,
                timeframe="1h",
                limit=100,
            )

            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            analysis = self.market_regime_detector.analyze(df)

            # Check for regime change
            old_regime = self._current_regime
            self._current_regime = analysis

            if old_regime and old_regime.regime != analysis.regime:
                await self._publish_event(
                    EventType.REGIME_CHANGED,
                    {
                        "old_regime": old_regime.regime.value,
                        "new_regime": analysis.regime.value,
                        "confidence": analysis.confidence,
                        "recommended_strategy": analysis.recommended_strategy.value,
                    },
                )
                logger.info(
                    "market_regime_changed",
                    old=old_regime.regime.value,
                    new=analysis.regime.value,
                    recommended=analysis.recommended_strategy.value,
                )
            else:
                await self._publish_event(
                    EventType.REGIME_DETECTED,
                    analysis.to_dict(),
                )

            return analysis

        except Exception as e:
            logger.error("regime_detection_failed", error=str(e), exc_info=True)
            return None

    def get_strategy_recommendation(self) -> RecommendedStrategy | None:
        """Get current strategy recommendation based on market regime."""
        if self._current_regime:
            return self._current_regime.recommended_strategy
        return None

    async def _regime_monitor_loop(self) -> None:
        """Periodic market regime detection loop."""
        logger.info("regime_monitor_started")

        while self._running:
            try:
                await self.detect_market_regime()
                await asyncio.sleep(self._regime_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("regime_monitor_error", error=str(e))
                await asyncio.sleep(self._regime_check_interval)

        logger.info("regime_monitor_stopped")

    # =========================================================================
    # v2.0: Health Monitoring Callbacks
    # =========================================================================

    async def _on_strategy_unhealthy(
        self, strategy_id: str, result: HealthCheckResult
    ) -> None:
        """Handle unhealthy strategy event."""
        logger.warning(
            "strategy_unhealthy",
            strategy_id=strategy_id,
            message=result.message,
        )
        await self._publish_event(
            EventType.HEALTH_DEGRADED,
            {
                "strategy_id": strategy_id,
                "status": result.status.value,
                "message": result.message,
            },
        )

    async def _on_strategy_critical(
        self, strategy_id: str, result: HealthCheckResult
    ) -> None:
        """Handle critical strategy health event."""
        logger.error(
            "strategy_critical",
            strategy_id=strategy_id,
            message=result.message,
        )
        await self._publish_event(
            EventType.HEALTH_CRITICAL,
            {
                "strategy_id": strategy_id,
                "status": result.status.value,
                "message": result.message,
            },
        )

    def _publish_event_sync(self, event_type: EventType, data: dict[str, Any]) -> None:
        """Fire-and-forget event publishing (for sync contexts)."""
        if not self.redis_client:
            return
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._publish_event(event_type, data))
        except RuntimeError:
            pass

    async def cleanup(self) -> None:
        """Cleanup resources including v2.0 components."""
        logger.info("cleaning_up_orchestrator")

        if self.state != BotState.STOPPED:
            await self.stop()

        # v2.0: Stop health monitor
        await self.health_monitor.stop()

        # v2.0: Stop all strategies
        await self.strategy_registry.stop_all()

        # v2.0: Cancel regime monitor
        if self._regime_monitor_task and not self._regime_monitor_task.done():
            self._regime_monitor_task.cancel()
            try:
                await self._regime_monitor_task
            except asyncio.CancelledError:
                pass

        # Close exchange client connection
        if self.exchange:
            try:
                await self.exchange.close()
                logger.info("exchange_client_closed")
            except Exception as e:
                logger.error("exchange_close_failed", error=str(e))

        if self.redis_client:
            await self.redis_client.aclose()

        logger.info("orchestrator_cleaned_up")
