# TRADERAGENT - Roadmap

> **Обновлено:** 2026-02-23 | Текущая версия: v2.0.0 (Released)

---

## Current Status

**v2.0.0 — Released February 2026. Demo trading LIVE on Bybit.**

- 5 strategies deployed: Grid, DCA, Hybrid, Trend Follower, SMC
- 1,531 tests passing (100%)
- Web UI Dashboard: 42 REST routes, 7 pages, JWT auth
- Demo trading: `api-demo.bybit.com`, 5 bots running
- Backtesting pipeline: DCA + TF + SMC on 45 pairs (running)

---

## Version History

### ✅ v1.0.0 — Core Platform (February 2026)

- Grid trading engine
- DCA (Dollar Cost Averaging) engine
- Hybrid (Grid + DCA combined)
- Risk management system
- PostgreSQL + Redis + asyncio architecture
- Telegram bot interface
- Prometheus + Grafana monitoring
- State persistence and recovery on restart
- Docker deployment

### ✅ v2.0.0 — Advanced Strategies + Web UI (February 2026)

- **SMC Strategy** (Smart Money Concepts): Order Blocks, FVG, BOS/CHoCH, multi-timeframe
- **Trend Follower Strategy**: EMA crossover, ATR-based TP/SL, trailing stop
- **Web UI Dashboard**: React + FastAPI, 7 pages, real-time WebSocket
- **Grid Backtesting System**: coin clustering, two-phase optimization, 39 tests
- **Multi-TF Backtesting**: DCA + TF + SMC on historical data, CSV support
- **Bybit Demo Trading**: `api-demo.bybit.com` with production API keys
- **State Persistence**: PostgreSQL snapshots + startup reconciliation
- **Load Testing**: 40 stress tests, 1,599 req/s, no memory leaks
- **Code Quality**: ruff + black + mypy, 100% pass rate

---

## Active Development (v2.1)

### 1. Adaptive Hybrid Strategy 🟡 (Planned)

**Goal:** Connect `MarketRegimeDetector` output to the main trading loop so the Hybrid strategy actually switches between Grid/DCA/etc based on market regime.

**Current state:** `MarketRegimeDetector` runs every 60s and publishes regime to Redis, but `HybridStrategy.evaluate()` is never called in `_main_loop()`. Grid and DCA always run simultaneously.

**Plan:**
- Read `get_strategy_recommendation()` in `_main_loop()`
- When regime = SIDEWAYS → activate Grid only
- When regime = DOWNTREND → activate DCA only
- When regime = HIGH_VOLATILITY → reduce exposure, pause new entries
- Maintain cooldowns and confirmation counts to prevent thrashing

### 2. Multi-Symbol Backtesting Pipeline Results 🟡 (In Progress)

**Current state:** Pipeline running on Yandex Cloud (16 CPU, 32GB RAM):
- Phase 1 DONE: 135/135 baseline backtests, 0 errors, 85 min
- Phase 2 IN PROGRESS: optimization (45 pairs × 3 strategies × 14 workers)
- Phases 3-5 pending: regime-aware, robustness, final report

**Goal:** Identify top-performing pairs and optimal parameters per strategy.

### 3. Backtesting Results Analysis 🟡 (Planned)

After pipeline completes:
- Rank pairs by Sharpe ratio, return, stability
- Build regime routing table (which strategy wins per market condition)
- Export optimal parameters to live bot configs

---

## Roadmap v2.x (2026)

### Strategy Improvements

- **SMC position_manager.py fix**: Inconsistent `is_long` detection in `check_exit_conditions` (known bug, low priority while in dry_run)
- **SMC live trading**: Switch `demo_btc_smc` from `dry_run: true` to `dry_run: false` after pipeline validation
- **Grid dynamic rebalancing**: Auto-adjust grid boundaries when price moves outside range

### Backtesting & Analytics

- **Backtest Results Visualization**: Equity curves, trade markers, drawdown charts in Web UI
- **Walk-forward analysis**: Out-of-sample validation of optimized parameters
- **Strategy comparison**: Side-by-side performance across pairs and timeframes

### Web UI Enhancements

- **Lightweight-charts**: Real-time price charts with trade markers
- **Full bot creation forms**: Create/edit bots without editing YAML
- **Portfolio history**: Replace stub endpoints with real historical data

### Infrastructure

- **Alembic migrations**: Proper schema versioning instead of auto-create
- **Multi-account support**: Multiple Bybit accounts per bot instance

---

## Roadmap v3.0 (Q4 2026)

### Additional Strategies

- **Fibonacci Retracement**: ALMIRBGCLOD strategy backtester (#85)
- **Martingale**: Double-down on losses with configurable multiplier
- **Mean Reversion**: Bollinger Bands + RSI oversold/overbought

### TradingView Integration (#97)

- Webhook integration for TradingView alerts
- Execute orders based on Pine Script signals

### AI/ML Features

- Auto-parameter optimization using backtesting results
- Market regime classification with ML model
- Adaptive position sizing

---

## Roadmap v4.0 (2027)

### Enterprise Features

- Multi-user support (roles, permissions)
- Futures/Margin trading (leverage 1x-125x)
- Advanced order types (OCO, TWAP, VWAP)
- 2FA authentication
- PDF report generation and email alerts

---

## Known Architectural Gaps

| Gap | Description | Priority |
|-----|-------------|----------|
| **Regime → Trading** | `MarketRegimeDetector` output not connected to `_main_loop()` | Medium |
| **SMC position_manager** | `check_exit_conditions` has inverted `is_long` logic | Low |
| **Web UI portfolio history** | Portfolio history endpoints return stubs | Low |

---

## Completed Issues

All major audit bugs fixed. See `docs/SESSION_CONTEXT.md` for full history.

Key fixes:
- `b477fbf` — Bybit status normalization (`"filled"` → `"closed"`) at source
- `f06dc8c` — SMC: stale signal filter, wrong trend key, duplicate logs
- `a7f4e66` — Grid: handle Bybit native `"filled"` status
- `a0f97ce` — State persistence + startup reconciliation
- `5cf8f71` — 6 AttributeError crashes in BotOrchestrator

---

## Contributing

**Submit Feature Requests:**
1. Search existing [issues](https://github.com/alekseymavai/TRADERAGENT/issues)
2. Create new issue with "Feature Request" template
3. Describe the feature, use case, and benefits

**Contribute Code:**
1. Check "Help Wanted" issues
2. Comment to claim an issue
3. Fork, develop, and submit PR

---

**Last Updated:** February 2026 | **Next Review:** After Phase 2-5 pipeline completes
