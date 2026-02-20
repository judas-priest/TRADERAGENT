"""
State serialization / deserialization for trading engines.

Converts in-memory engine state to JSON strings for DB persistence
and restores engine state from saved snapshots.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from bot.utils.logger import get_logger

logger = get_logger(__name__)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal, datetime, and date objects."""

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        return super().default(o)


# ---------------------------------------------------------------------------
# Grid Engine
# ---------------------------------------------------------------------------


def serialize_grid_state(grid_engine: Any) -> str | None:
    """Serialize GridEngine state to JSON string."""
    if grid_engine is None:
        return None

    active_orders = {}
    for order_id, order in grid_engine.active_orders.items():
        active_orders[order_id] = {
            "level": order.level,
            "price": str(order.price),
            "amount": str(order.amount),
            "side": order.side,
            "order_id": order.order_id,
            "filled": order.filled,
        }

    state = {
        "active_orders": active_orders,
        "total_profit": str(grid_engine.total_profit),
        "buy_count": grid_engine.buy_count,
        "sell_count": grid_engine.sell_count,
    }
    return json.dumps(state, cls=DecimalEncoder)


def deserialize_grid_state(grid_engine: Any, json_str: str | None) -> bool:
    """Restore GridEngine state from JSON. Returns True if restored."""
    if json_str is None or grid_engine is None:
        return False

    try:
        from bot.core.grid_engine import GridOrder

        state = json.loads(json_str)
        grid_engine.active_orders.clear()
        for order_id, od in state.get("active_orders", {}).items():
            order = GridOrder(
                level=od["level"],
                price=Decimal(od["price"]),
                amount=Decimal(od["amount"]),
                side=od["side"],
                order_id=od.get("order_id"),
                filled=od.get("filled", False),
            )
            grid_engine.active_orders[order_id] = order

        grid_engine.total_profit = Decimal(state.get("total_profit", "0"))
        grid_engine.buy_count = state.get("buy_count", 0)
        grid_engine.sell_count = state.get("sell_count", 0)

        logger.info(
            "grid_state_restored",
            active_orders=len(grid_engine.active_orders),
            total_profit=str(grid_engine.total_profit),
        )
        return True
    except Exception as e:
        logger.error("grid_state_restore_failed", error=str(e))
        return False


# ---------------------------------------------------------------------------
# DCA Engine
# ---------------------------------------------------------------------------


def serialize_dca_state(dca_engine: Any) -> str | None:
    """Serialize DCAEngine state to JSON string."""
    if dca_engine is None:
        return None

    position_data = None
    if dca_engine.position is not None:
        pos = dca_engine.position
        position_data = {
            "symbol": pos.symbol,
            "entry_price": str(pos.entry_price),
            "amount": str(pos.amount),
            "step_number": pos.step_number,
            "total_cost": str(pos.total_cost),
            "average_entry_price": str(pos.average_entry_price),
        }

    state = {
        "position": position_data,
        "last_buy_price": str(dca_engine.last_buy_price) if dca_engine.last_buy_price else None,
        "highest_price_since_entry": (
            str(dca_engine.highest_price_since_entry)
            if dca_engine.highest_price_since_entry
            else None
        ),
        "total_dca_steps": dca_engine.total_dca_steps,
        "total_invested": str(dca_engine.total_invested),
        "realized_profit": str(dca_engine.realized_profit),
    }
    return json.dumps(state, cls=DecimalEncoder)


def deserialize_dca_state(dca_engine: Any, json_str: str | None) -> bool:
    """Restore DCAEngine state from JSON. Returns True if restored."""
    if json_str is None or dca_engine is None:
        return False

    try:
        from bot.core.dca_engine import DCAPosition

        state = json.loads(json_str)

        pos_data = state.get("position")
        if pos_data:
            pos = DCAPosition(
                symbol=pos_data["symbol"],
                entry_price=Decimal(pos_data["entry_price"]),
                amount=Decimal(pos_data["amount"]),
                step_number=pos_data["step_number"],
            )
            pos.total_cost = Decimal(pos_data["total_cost"])
            pos.average_entry_price = Decimal(pos_data["average_entry_price"])
            dca_engine.position = pos
        else:
            dca_engine.position = None

        lbp = state.get("last_buy_price")
        dca_engine.last_buy_price = Decimal(lbp) if lbp else None
        hp = state.get("highest_price_since_entry")
        dca_engine.highest_price_since_entry = Decimal(hp) if hp else None
        dca_engine.total_dca_steps = state.get("total_dca_steps", 0)
        dca_engine.total_invested = Decimal(state.get("total_invested", "0"))
        dca_engine.realized_profit = Decimal(state.get("realized_profit", "0"))

        logger.info(
            "dca_state_restored",
            has_position=dca_engine.position is not None,
            total_dca_steps=dca_engine.total_dca_steps,
        )
        return True
    except Exception as e:
        logger.error("dca_state_restore_failed", error=str(e))
        return False


# ---------------------------------------------------------------------------
# Risk Manager (core)
# ---------------------------------------------------------------------------


def serialize_risk_state(risk_manager: Any) -> str | None:
    """Serialize core RiskManager state to JSON string."""
    if risk_manager is None:
        return None

    state = {
        "initial_balance": str(risk_manager.initial_balance)
        if risk_manager.initial_balance
        else None,
        "current_balance": str(risk_manager.current_balance)
        if risk_manager.current_balance
        else None,
        "peak_balance": str(risk_manager.peak_balance) if risk_manager.peak_balance else None,
        "daily_loss": str(risk_manager.daily_loss),
        "is_halted": risk_manager.is_halted,
        "halt_reason": risk_manager.halt_reason,
        "total_trades": risk_manager.total_trades,
        "rejected_trades": risk_manager.rejected_trades,
        "stop_loss_triggers": risk_manager.stop_loss_triggers,
    }
    return json.dumps(state, cls=DecimalEncoder)


def deserialize_risk_state(risk_manager: Any, json_str: str | None) -> bool:
    """Restore core RiskManager state from JSON. Returns True if restored."""
    if json_str is None or risk_manager is None:
        return False

    try:
        state = json.loads(json_str)

        ib = state.get("initial_balance")
        if ib is not None:
            risk_manager.initial_balance = Decimal(ib)
        cb = state.get("current_balance")
        if cb is not None:
            risk_manager.current_balance = Decimal(cb)
        pb = state.get("peak_balance")
        if pb is not None:
            risk_manager.peak_balance = Decimal(pb)

        risk_manager.daily_loss = Decimal(state.get("daily_loss", "0"))
        risk_manager.is_halted = state.get("is_halted", False)
        risk_manager.halt_reason = state.get("halt_reason")
        risk_manager.total_trades = state.get("total_trades", 0)
        risk_manager.rejected_trades = state.get("rejected_trades", 0)
        risk_manager.stop_loss_triggers = state.get("stop_loss_triggers", 0)

        logger.info(
            "risk_state_restored",
            is_halted=risk_manager.is_halted,
            daily_loss=str(risk_manager.daily_loss),
        )
        return True
    except Exception as e:
        logger.error("risk_state_restore_failed", error=str(e))
        return False


# ---------------------------------------------------------------------------
# Trend-Follower Strategy (risk_manager counters only)
# ---------------------------------------------------------------------------


def serialize_trend_state(strategy: Any) -> str | None:
    """Serialize Trend-Follower risk_manager counters."""
    if strategy is None:
        return None

    rm = getattr(strategy, "risk_manager", None)
    if rm is None:
        return None

    state = {
        "current_capital": str(rm.current_capital),
        "consecutive_losses": rm.consecutive_losses,
        "daily_pnl": str(rm.daily_pnl),
        "daily_trades": rm.daily_trades,
    }
    return json.dumps(state, cls=DecimalEncoder)


def deserialize_trend_state(strategy: Any, json_str: str | None) -> bool:
    """Restore Trend-Follower risk_manager counters from JSON."""
    if json_str is None or strategy is None:
        return False

    rm = getattr(strategy, "risk_manager", None)
    if rm is None:
        return False

    try:
        state = json.loads(json_str)
        rm.current_capital = Decimal(state.get("current_capital", str(rm.current_capital)))
        rm.consecutive_losses = state.get("consecutive_losses", 0)
        rm.daily_pnl = Decimal(state.get("daily_pnl", "0"))
        rm.daily_trades = state.get("daily_trades", 0)

        logger.info(
            "trend_state_restored",
            consecutive_losses=rm.consecutive_losses,
            daily_pnl=str(rm.daily_pnl),
        )
        return True
    except Exception as e:
        logger.error("trend_state_restore_failed", error=str(e))
        return False


# ---------------------------------------------------------------------------
# Hybrid Strategy (mode, transitions, regime detector state)
# ---------------------------------------------------------------------------


def serialize_hybrid_state(hybrid_strategy: Any) -> str | None:
    """Serialize HybridStrategy state to JSON string."""
    if hybrid_strategy is None:
        return None

    state: dict[str, Any] = {
        "mode": hybrid_strategy._mode.value,
        "mode_since": hybrid_strategy._mode_since.isoformat(),
        "total_transitions": hybrid_strategy._total_transitions,
        "grid_to_dca_count": hybrid_strategy._grid_to_dca_count,
        "dca_to_grid_count": hybrid_strategy._dca_to_grid_count,
    }

    if hybrid_strategy._last_transition is not None:
        state["last_transition"] = hybrid_strategy._last_transition.isoformat()
    else:
        state["last_transition"] = None

    # Serialize regime detector state if available
    detector = getattr(hybrid_strategy, "_regime_detector", None)
    if detector is not None:
        state["regime_detector"] = {
            "current_regime": detector._current_regime.value,
            "current_strategy": detector._current_strategy.value,
            "evaluation_count": detector._evaluation_count,
        }

    return json.dumps(state, cls=DecimalEncoder)


def deserialize_hybrid_state(hybrid_strategy: Any, json_str: str | None) -> bool:
    """Restore HybridStrategy state from JSON. Returns True if restored."""
    if json_str is None or hybrid_strategy is None:
        return False

    try:
        from bot.strategies.hybrid.hybrid_config import HybridMode
        from bot.strategies.hybrid.market_regime_detector import (
            RegimeType,
            StrategyRecommendation,
        )

        state = json.loads(json_str)

        hybrid_strategy._mode = HybridMode(state["mode"])
        hybrid_strategy._mode_since = datetime.fromisoformat(state["mode_since"])
        hybrid_strategy._total_transitions = state.get("total_transitions", 0)
        hybrid_strategy._grid_to_dca_count = state.get("grid_to_dca_count", 0)
        hybrid_strategy._dca_to_grid_count = state.get("dca_to_grid_count", 0)

        lt = state.get("last_transition")
        hybrid_strategy._last_transition = datetime.fromisoformat(lt) if lt else None

        # Restore regime detector state
        detector = getattr(hybrid_strategy, "_regime_detector", None)
        rd = state.get("regime_detector")
        if detector is not None and rd is not None:
            detector._current_regime = RegimeType(rd["current_regime"])
            detector._current_strategy = StrategyRecommendation(rd["current_strategy"])
            detector._evaluation_count = rd.get("evaluation_count", 0)

        logger.info(
            "hybrid_state_restored",
            mode=hybrid_strategy._mode.value,
            total_transitions=hybrid_strategy._total_transitions,
        )
        return True
    except Exception as e:
        logger.error("hybrid_state_restore_failed", error=str(e))
        return False
