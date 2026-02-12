"""
Smart Money Concepts (SMC) Strategy
Main strategy class - Issue #123
"""

from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass
import pandas as pd

from bot.strategies.smc.config import SMCConfig, DEFAULT_SMC_CONFIG
from bot.strategies.smc.market_structure import MarketStructureAnalyzer, TrendDirection
from bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SMCSignal:
    timestamp: pd.Timestamp
    signal_type: str
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    confidence: float
    risk_reward: Decimal
    position_size: Decimal
    reasons: List[str]


class SMCStrategy:
    def __init__(self, config: Optional[SMCConfig] = None):
        self.config = config or DEFAULT_SMC_CONFIG
        self.market_structure = MarketStructureAnalyzer(
            swing_length=self.config.swing_length,
            trend_period=self.config.trend_period
        )
        self.current_trend = None
        self.active_signals = []
        logger.info("smc_strategy_initialized")
    
    def get_strategy_state(self) -> Dict:
        return {
            "current_trend": self.current_trend.value if self.current_trend else None,
            "active_signals": len(self.active_signals),
        }
