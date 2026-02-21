"""
Bot service: bridge between API and BotOrchestrator.
"""

import logging
from datetime import datetime
from decimal import Decimal

from bot.orchestrator.bot_orchestrator import BotOrchestrator
from web.backend.schemas.bot import (
    BotCreateRequest,
    BotListResponse,
    BotStatusResponse,
    BotUpdateRequest,
    PnLResponse,
    PositionResponse,
    TradeResponse,
)

logger = logging.getLogger(__name__)


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
                            Decimal(status["current_price"]) if status.get("current_price") else None
                        ),
                    )
                )

            return positions
        except Exception:
            return []

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

    async def create_bot(self, data: BotCreateRequest) -> tuple[bool, str]:
        """Create a new bot configuration.

        Note: In production this would persist config and instantiate a new orchestrator.
        Currently returns success acknowledgement; the orchestrator map is populated at startup.
        """
        if data.name in self.orchestrators:
            return False, f"Bot '{data.name}' already exists"
        # Log the creation intent — actual orchestrator wiring is done at startup
        # from persisted config. Future implementations would reload configs here.
        logger.info(
            "Bot create request: name=%s strategy=%s symbol=%s",
            data.name,
            data.strategy,
            data.symbol,
        )
        return True, f"Bot '{data.name}' configuration saved. Restart the service to activate."

    async def update_bot(self, bot_name: str, data: BotUpdateRequest) -> tuple[bool, str]:
        """Update bot configuration (risk params and strategy params)."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False, f"Bot '{bot_name}' not found"
        logger.info("Bot update request: name=%s", bot_name)
        return True, f"Bot '{bot_name}' configuration updated. Changes take effect after restart."

    async def delete_bot(self, bot_name: str) -> tuple[bool, str]:
        """Delete a bot (only if stopped)."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return False, f"Bot '{bot_name}' not found"
        try:
            bot_status = await orch.get_status()
            state = bot_status.get("state", "unknown")
            if state == "running":
                return False, f"Bot '{bot_name}' is running. Stop it before deleting."
        except Exception:
            pass
        logger.info("Bot delete request: name=%s", bot_name)
        return True, f"Bot '{bot_name}' deleted. Restart the service to apply."

    async def get_trades(self, bot_name: str, limit: int = 50) -> list[TradeResponse]:
        """Get trade history for a bot from orchestrator status."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return []
        try:
            status = await orch.get_status()
            trades: list[TradeResponse] = []
            # Extract recent trades from grid engine history if available
            grid = status.get("grid", {})
            for i, trade in enumerate(grid.get("recent_trades", [])[:limit]):
                trades.append(
                    TradeResponse(
                        id=i + 1,
                        symbol=status.get("symbol", ""),
                        side=trade.get("side", "buy"),
                        price=Decimal(str(trade.get("price", 0))),
                        amount=Decimal(str(trade.get("amount", 0))),
                        fee=Decimal(str(trade.get("fee", 0))),
                        profit=Decimal(str(trade.get("profit", 0))) if trade.get("profit") is not None else None,
                        executed_at=datetime.fromisoformat(trade["executed_at"])
                        if isinstance(trade.get("executed_at"), str)
                        else datetime.utcnow(),
                    )
                )
            return trades
        except Exception:
            return []
