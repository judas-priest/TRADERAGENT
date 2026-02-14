"""DCA Strategy Package — v2.0 Signal Generator and related utilities."""

from bot.strategies.dca.dca_signal_generator import (
    ConditionResult,
    DCASignalConfig,
    DCASignalGenerator,
    MarketState,
    SignalResult,
)

__all__ = [
    "DCASignalGenerator",
    "DCASignalConfig",
    "MarketState",
    "SignalResult",
    "ConditionResult",
]
