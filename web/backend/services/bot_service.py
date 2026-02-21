"""
Bot service: bridge between API and BotOrchestrator.
"""

from decimal import Decimal

from bot.orchestrator.bot_orchestrator import BotOrchestrator
from web.backend.schemas.bot import (
    BotListResponse,
    BotStatusResponse,
    PnLDataPoint,
    PnLHistoryResponse,
    PnLResponse,
    PositionResponse,
    TradeResponse,
)


def _extract_metrics(status: dict) -> dict:
    """Extract aggregated metrics from orchestrator status sub-dicts."""
    total_trades = 0
    total_profit = Decimal("0")
    active_positions = 0
    open_orders = 0

    grid = status.get("grid")
    if grid:
        total_trades += grid.get("buy_count", 0) + grid.get("sell_count", 0)
        total_profit += Decimal(str(grid.get("total_profit", 0)))
        open_orders += grid.get("active_orders", 0)

    dca = status.get("dca")
    if dca:
        if dca.get("has_position"):
            active_positions += 1
        total_profit += Decimal(str(dca.get("realized_profit", 0)))

    tf = status.get("trend_follower")
    if tf:
        active_positions += tf.get("active_positions", 0)
        stats = tf.get("statistics", {})
        risk_metrics = stats.get("risk_metrics", {})
        total_trades += risk_metrics.get("total_trades", 0)
        total_profit += Decimal(str(risk_metrics.get("total_pnl", 0)))

    return {
        "total_trades": total_trades,
        "total_profit": total_profit,
        "active_positions": active_positions,
        "open_orders": open_orders,
    }


class BotService:
    """Service layer for bot operations."""

    def __init__(self, orchestrators: dict[str, BotOrchestrator]):
        self.orchestrators = orchestrators

    async def list_bots(
        self,
        strategy: str | None = None,
        status_filter: str | None = None,
        symbol: str | None = None,
    ) -> list[BotListResponse]:
        """List all bots with optional filters."""
        results = []
        for name, orch in self.orchestrators.items():
            try:
                bot_status = await orch.get_status()
            except Exception:
                bot_status = {
                    "bot_name": name,
                    "strategy": "unknown",
                    "symbol": "",
                    "state": "error",
                }

            s_type = bot_status.get("strategy", "unknown")
            s_status = bot_status.get("state", "unknown")
            s_symbol = bot_status.get("symbol", "")

            if strategy and s_type != strategy:
                continue
            if status_filter and s_status != status_filter:
                continue
            if symbol and s_symbol != symbol:
                continue

            metrics = _extract_metrics(bot_status)
            results.append(
                BotListResponse(
                    name=name,
                    strategy=s_type,
                    symbol=s_symbol,
                    status=s_status,
                    total_trades=metrics["total_trades"],
                    total_profit=metrics["total_profit"],
                    active_positions=metrics["active_positions"],
                )
            )
        return results

    async def get_bot_status(self, bot_name: str) -> BotStatusResponse | None:
        """Get detailed bot status."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return None

        try:
            status = await orch.get_status()
        except Exception:
            return BotStatusResponse(
                name=bot_name,
                strategy="unknown",
                symbol="",
                status="error",
            )

        metrics = _extract_metrics(status)
        return BotStatusResponse(
            name=bot_name,
            strategy=status.get("strategy", "unknown"),
            symbol=status.get("symbol", ""),
            status=status.get("state", "unknown"),
            dry_run=status.get("dry_run", False),
            total_trades=metrics["total_trades"],
            total_profit=metrics["total_profit"],
            active_positions=metrics["active_positions"],
            open_orders=metrics["open_orders"],
        )

    async def start_bot(self, bot_name: str) -> bool:
        """Start a bot."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False
        await orch.start()
        return True

    async def stop_bot(self, bot_name: str) -> bool:
        """Stop a bot."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False
        await orch.stop()
        return True

    async def pause_bot(self, bot_name: str) -> bool:
        """Pause a bot."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False
        await orch.pause()
        return True

    async def resume_bot(self, bot_name: str) -> bool:
        """Resume a bot."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False
        await orch.resume()
        return True

    async def emergency_stop(self, bot_name: str) -> bool:
        """Emergency stop a bot."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False
        await orch.emergency_stop()
        return True

    async def get_positions(self, bot_name: str) -> list[PositionResponse]:
        """Get active positions for a bot."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return []

        try:
            status = await orch.get_status()
            positions: list[PositionResponse] = []

            # Extract DCA position
            dca = status.get("dca")
            if dca and dca.get("has_position"):
                positions.append(
                    PositionResponse(
                        symbol=dca.get("symbol", status.get("symbol", "")),
                        side="buy",
                        size=Decimal(str(dca.get("position_amount", 0))),
                        entry_price=Decimal(str(dca.get("average_entry_price", 0))),
                        current_price=(
                            Decimal(status["current_price"])
                            if status.get("current_price")
                            else None
                        ),
                    )
                )

            return positions
        except Exception:
            return []

    async def update_bot(self, bot_name: str, data: dict) -> str | bool:
        """Update bot configuration (dry_run and strategy params).

        Returns:
            True on success, False if bot not found, "running" if bot is running.
        """
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False
        try:
            status = await orch.get_status()
            if status.get("state") in ("running", "starting"):
                return "running"
        except Exception:
            pass
        config = orch.bot_config
        if "dry_run" in data and data["dry_run"] is not None:
            config.dry_run = data["dry_run"]
        for key in ("grid", "dca", "trend_follower", "risk_management"):
            if key in data and data[key] is not None:
                setattr(config, key, data[key])
        return True

    async def delete_bot(self, bot_name: str) -> str | bool:
        """Delete a stopped bot from the orchestrators registry.

        Returns:
            True on success, False if bot not found, "running" if bot is running.
        """
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False
        try:
            status = await orch.get_status()
            if status.get("state") in ("running", "starting"):
                return "running"
        except Exception:
            pass
        del self.orchestrators[bot_name]
        return True

    async def get_trades(self, bot_name: str, limit: int = 50) -> list[TradeResponse] | None:
        """Get trade history for a bot from the database.

        Returns None if the bot does not exist, empty list if no trades found.
        """
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return None
        try:
            db_manager = getattr(orch, "db_manager", None)
            if db_manager is None:
                return []
            from sqlalchemy import select

            from bot.database.models import Bot, Trade

            async with db_manager.session() as session:
                bot_result = await session.execute(
                    select(Bot).where(Bot.name == bot_name)
                )
                bot = bot_result.scalar_one_or_none()
                if not bot:
                    return []
                trade_result = await session.execute(
                    select(Trade)
                    .where(Trade.bot_id == bot.id)
                    .order_by(Trade.executed_at.desc())
                    .limit(limit)
                )
                trades = trade_result.scalars().all()
                return [TradeResponse.model_validate(t) for t in trades]
        except Exception:
            return []

    async def get_pnl_history(self, bot_name: str, period: str = "7d") -> PnLHistoryResponse | None:
        """Get time-series PnL data for sparkline chart.

        Args:
            bot_name: Name of the bot.
            period: Time period for the history — one of "1d", "7d", "30d", "all".
        """
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return None

        try:
            import time

            status = await orch.get_status()
            points: list[PnLDataPoint] = []

            # Build cumulative PnL series from available strategy metrics.
            # We generate synthetic time-series from aggregate stats since
            # in-memory orchestrator does not persist per-trade timestamps.
            metrics = _extract_metrics(status)
            total_profit = float(metrics["total_profit"])
            total_trades = metrics["total_trades"]

            # Determine window in seconds based on requested period.
            period_seconds: float | None
            if period == "1d":
                period_seconds = 86_400.0
            elif period == "7d":
                period_seconds = 7 * 86_400.0
            elif period == "30d":
                period_seconds = 30 * 86_400.0
            else:
                period_seconds = None  # "all" — no time restriction

            if total_trades > 0:
                # Distribute profit evenly across N synthetic points in time.
                n_points = min(total_trades, 30)
                now = time.time()
                window = period_seconds if period_seconds is not None else n_points * 3600
                interval = window / n_points
                step = total_profit / n_points
                cumulative = 0.0
                for i in range(n_points):
                    cumulative += step
                    ts = now - (n_points - i - 1) * interval
                    points.append(PnLDataPoint(timestamp=ts, value=cumulative))

            return PnLHistoryResponse(points=points)
        except Exception:
            return PnLHistoryResponse()

    async def get_pnl(self, bot_name: str) -> PnLResponse | None:
        """Get PnL metrics for a bot."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return None

        try:
            status = await orch.get_status()
            metrics = _extract_metrics(status)

            # Extract win/loss stats from trend follower if available
            win_rate = None
            winning_trades = 0
            losing_trades = 0
            tf = status.get("trend_follower")
            if tf:
                stats = tf.get("statistics", {})
                risk_metrics = stats.get("risk_metrics", {})
                win_rate = risk_metrics.get("win_rate")
                total = risk_metrics.get("total_trades", 0)
                if win_rate is not None and total > 0:
                    winning_trades = int(total * win_rate)
                    losing_trades = total - winning_trades

            return PnLResponse(
                total_realized_pnl=metrics["total_profit"],
                total_trades=metrics["total_trades"],
                win_rate=win_rate,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
            )
        except Exception:
            return PnLResponse()
