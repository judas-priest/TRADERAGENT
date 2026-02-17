"""
Grid Backtester — Standalone backtesting and optimization service for grid trading strategies.

Provides:
- Grid backtest simulation with intra-candle price sweep
- Two-phase parameter optimization (coarse + fine)
- Coin volatility classification and clustering
- Trailing grid algorithm
- Capital efficiency and risk-adjusted metrics
- SQLite-backed job persistence and preset storage
- Plotly visualization
- FastAPI REST service
"""

__version__ = "1.0.0"
