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


class BotService:
    """Service layer for bot operations."""

    def __init__(self, orchestrators: dict[str, BotOrchestrator]):
        self.orchestrators = orchestrators

    def list_bots(
        self,
        strategy: str | None = None,
        status_filter: str | None = None,
        symbol: str | None = None,
    ) -> list[BotListResponse]:
        """List all bots with optional filters."""
        results = []
        for name, orch in self.orchestrators.items():
            try:
                bot_status = orch.get_status()
            except Exception:
                bot_status = {
                    "bot_name": name,
                    "strategy_type": "unknown",
                    "symbol": "",
                    "status": "error",
                }

            s_type = bot_status.get("strategy_type", "unknown")
            s_status = bot_status.get("status", "unknown")
            s_symbol = bot_status.get("symbol", "")

            if strategy and s_type != strategy:
                continue
            if status_filter and s_status != status_filter:
                continue
            if symbol and s_symbol != symbol:
                continue

            metrics = bot_status.get("metrics", {})
            results.append(
                BotListResponse(
                    name=name,
                    strategy=s_type,
                    symbol=s_symbol,
                    status=s_status,
                    total_trades=metrics.get("total_trades", 0),
                    total_profit=Decimal(str(metrics.get("total_pnl", 0))),
                    active_positions=metrics.get("active_positions", 0),
                )
            )
        return results

    def get_bot_status(self, bot_name: str) -> BotStatusResponse | None:
        """Get detailed bot status."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return None

        try:
            status = orch.get_status()
        except Exception:
            return BotStatusResponse(
                name=bot_name,
                strategy="unknown",
                symbol="",
                status="error",
            )

        metrics = status.get("metrics", {})
        return BotStatusResponse(
            name=bot_name,
            strategy=status.get("strategy_type", "unknown"),
            symbol=status.get("symbol", ""),
            status=status.get("status", "unknown"),
            dry_run=status.get("dry_run", False),
            uptime_seconds=metrics.get("uptime_seconds"),
            total_trades=metrics.get("total_trades", 0),
            total_profit=Decimal(str(metrics.get("total_pnl", 0))),
            unrealized_pnl=Decimal(str(metrics.get("unrealized_pnl", 0))),
            active_positions=metrics.get("active_positions", 0),
            open_orders=metrics.get("open_orders", 0),
            config=status.get("config"),
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
            status = orch.get_status()
            positions = status.get("positions", [])
            return [
                PositionResponse(
                    symbol=p.get("symbol", ""),
                    side=p.get("side", ""),
                    size=Decimal(str(p.get("size", 0))),
                    entry_price=Decimal(str(p.get("entry_price", 0))),
                    current_price=(
                        Decimal(str(p["current_price"])) if p.get("current_price") else None
                    ),
                    unrealized_pnl=(
                        Decimal(str(p["unrealized_pnl"])) if p.get("unrealized_pnl") else None
                    ),
                    leverage=p.get("leverage", 1),
                )
                for p in positions
            ]
        except Exception:
            return []

    async def get_pnl(self, bot_name: str) -> PnLResponse | None:
        """Get PnL metrics for a bot."""
        orch = self.orchestrators.get(bot_name)
        if not orch:
            return None

        try:
            status = orch.get_status()
            metrics = status.get("metrics", {})
            return PnLResponse(
                total_realized_pnl=Decimal(str(metrics.get("total_pnl", 0))),
                total_unrealized_pnl=Decimal(str(metrics.get("unrealized_pnl", 0))),
                total_fees=Decimal(str(metrics.get("total_fees", 0))),
                win_rate=metrics.get("win_rate"),
                total_trades=metrics.get("total_trades", 0),
                winning_trades=metrics.get("winning_trades", 0),
                losing_trades=metrics.get("losing_trades", 0),
            )
        except Exception:
            return PnLResponse()
