"""
Bot service: bridge between API and BotOrchestrator.
"""

from decimal import Decimal

from bot.orchestrator.bot_orchestrator import BotOrchestrator
from web.backend.schemas.bot import (
    BotListResponse,
    BotStatusResponse,
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
