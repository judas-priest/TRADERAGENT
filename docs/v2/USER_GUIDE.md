# TRADERAGENT v2.0 User Guide

> **Обновлено:** 2026-02-23

## Overview

TRADERAGENT v2.0 is an autonomous cryptocurrency trading bot that supports multiple strategies on the ByBit exchange (Demo and Production). It provides:

- **5 Trading Strategies**: Grid, DCA, Hybrid (Grid+DCA), Trend Follower, SMC (Smart Money Concepts)
- **Unified Strategy Interface**: All strategies share a common lifecycle
- **Telegram Control**: Manage bots via Telegram commands
- **Gradual Capital Deployment**: Phased scaling from 5% to 100%
- **Demo Trading**: Paper trading on `api-demo.bybit.com` with virtual funds
- **State Persistence**: Bot state saved every 30s, restored on restart with exchange reconciliation
- **Production Safety**: Security audits, config validation, risk limits

## Prerequisites

- Python 3.12+
- ByBit account (demo or production)
- PostgreSQL (required for demo/production; SQLite for development only)
- Redis (required for event streaming and Telegram notifications)
- Telegram Bot Token (optional, for remote control and alerts)

## Installation

```bash
git clone https://github.com/alekseymavai/TRADERAGENT.git
cd TRADERAGENT
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Required
DATABASE_URL=postgresql+asyncpg://traderagent:password@localhost:5432/traderagent
ENCRYPTION_KEY=your_base64_key  # python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"

# Telegram (optional but recommended)
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_ALLOWED_CHAT_IDS=your_chat_id

# Logging
LOG_LEVEL=INFO
```

> ⚠️ API keys for Bybit are stored **encrypted in PostgreSQL** (not in `.env`). They are referenced by `credentials_name` in the YAML config. See [Bybit Demo Setup](#bybit-demo-trading).

### Bot Configuration (YAML)

The main config file is `configs/phase7_demo.yaml`. Example bot entry:

```yaml
bots:
  - name: my_grid_bot
    symbol: BTC/USDT
    strategy: grid  # grid | dca | hybrid | trend_follower | smc

    exchange:
      exchange_id: bybit
      credentials_name: bybit_demo  # Name of credentials stored in DB
      sandbox: true   # true = api-demo.bybit.com (Demo Trading)
      rate_limit: true

    grid:
      enabled: true
      upper_price: "69000"
      lower_price: "62000"
      grid_levels: 6
      amount_per_grid: "150"
      profit_per_grid: "0.012"

    risk_management:
      max_position_size: "3000"
      stop_loss_percentage: "0.12"
      max_daily_loss: "600"
      min_order_size: "66"

    dry_run: false    # false = real API calls (virtual money on demo)
    auto_start: true
```

### Config Validation

Before going live, validate your configuration:

```python
from bot.utils.config_validator import ConfigValidator

validator = ConfigValidator()
report = validator.run_full_validation(
    risk={"risk_per_trade": Decimal("0.02"), "max_exposure": Decimal("0.20")},
    grid={"num_levels": 10, "amount_per_grid": Decimal("100")},
    dca={"max_safety_orders": 5},
)
print(report.summary())
# {'total_checks': 10, 'passed': 10, 'failed': 0, 'overall_status': 'PASS'}
```

**Safe Limits Enforced**:
| Parameter | Max Value |
|-----------|-----------|
| Risk per trade | 5% |
| Total exposure | 50% |
| Daily loss | 10% |
| Min risk:reward | 1.5:1 |
| Grid levels | 50 |
| Safety orders | 10 |
| Position size | $50,000 |

---

## Bybit Demo Trading

Demo trading uses virtual funds on `api-demo.bybit.com`. **Production API keys** work for demo — no separate testnet keys needed.

### Setup

1. Log into [Bybit](https://bybit.com) and activate Demo Trading
2. Generate API keys in your Bybit account (production keys)
3. Store them in the database:
   ```python
   # Via Telegram: /set_credentials or via API
   # Or directly (development only):
   await db.store_credentials("bybit_demo", api_key, api_secret, encrypted=True)
   ```
4. Set `sandbox: true` and `credentials_name: bybit_demo` in YAML config
5. Use `dry_run: false` for real API calls with virtual money

### Important Constraints

- Demo only supports **linear (futures) contracts** — no spot trading
- Balance starts at 100,000 USDT (virtual)
- Same rate limits as production API

---

## Strategies

### Grid Trading
Best for sideways/ranging markets. Places a grid of buy/sell limit orders. Profit is captured each time a buy+sell pair completes.

```yaml
strategy: grid
grid:
  enabled: true
  upper_price: "69000"
  lower_price: "62000"
  grid_levels: 6
  amount_per_grid: "150"
  profit_per_grid: "0.012"  # 1.2% profit per completed grid
```

### DCA (Dollar Cost Averaging)
Averages into a position on price drops, exits on recovery. Best for downtrending or volatile markets.

```yaml
strategy: dca
dca:
  enabled: true
  trigger_percentage: "0.05"      # Enter when price drops 5%
  amount_per_step: "20"           # $20 per safety order
  max_steps: 5
  take_profit_percentage: "0.10"  # Exit at 10% gain
```

### Hybrid (Grid + DCA)
Both Grid and DCA engines run simultaneously. `MarketRegimeDetector` monitors market conditions every 60s and publishes regime data to Redis — adaptive switching between engines is planned but not yet active.

```yaml
strategy: hybrid
grid:
  enabled: true
  # ... grid params
dca:
  enabled: true
  # ... dca params
```

### Trend Follower
EMA-based trend detection with ATR-scaled TP/SL. Enters on pullbacks in trending markets.

```yaml
strategy: trend_follower
trend_follower:
  enabled: true
  ema_fast_period: 20
  ema_slow_period: 50
  atr_period: 14
  risk_per_trade_pct: "0.01"     # 1% risk per trade
  tp_atr_multiplier_strong: "2.5"
  sl_atr_multiplier_trend: "1.0"
```

### SMC (Smart Money Concepts)
Multi-timeframe institutional analysis: Order Blocks, Fair Value Gaps, BOS/CHoCH structure. High-confidence signals with R:R ≥ 2.5.

```yaml
strategy: smc
smc:
  enabled: true
  swing_length: 50
  risk_per_trade: "0.02"       # 2% risk per trade
  min_risk_reward: "2.5"
  max_position_size: "5000"
  max_positions: 3

dry_run: true  # Recommended for observation first
```

> **Note**: SMC analysis runs every 300 seconds (5 min). Signals are rejected if entry price differs from current price by more than 2% (stale signal filter).

---

## Capital Deployment

TRADERAGENT uses a phased capital deployment model to protect against losses during initial trading.

### Phase 1: Monitoring (5% capital)
- Duration: 3 days minimum
- Requirements: 5+ trades, 40%+ win rate, <5% drawdown, positive PnL

### Phase 2: Scaling (25% capital)
- Duration: 7 days minimum
- Requirements: 20+ trades, 45%+ win rate, <10% drawdown, positive PnL

### Phase 3: Full Deployment (100% capital)
- No minimum duration
- Continuous monitoring with halt capability

```python
from bot.utils.capital_manager import CapitalManager

cm = CapitalManager(total_capital=Decimal("10000"))
cm.start_phase_1()  # Returns Decimal("500")

# After trading...
cm.record_trade(won=True, pnl=Decimal("50"))
decision = cm.evaluate_scaling()
if decision.can_scale:
    cm.advance_phase()  # Returns Decimal("2500")
```

---

## Security Audit

Run a security audit before production deployment:

```python
from bot.utils.security_audit import SecurityAuditor

auditor = SecurityAuditor()
report = auditor.run_full_audit()
print(report.summary())
```

Checks performed:
- `.env` file protection (in `.gitignore`)
- No hardcoded secrets in source files
- Debug mode disabled
- Required environment variables set
- Database/Redis URL security (SSL for remote)

---

## Deployment (Docker)

```bash
# Start all services
docker compose up -d

# View bot logs
docker compose logs -f bot

# Restart after code change (bot/ is volume-mounted, no rebuild needed)
docker compose restart bot

# Validate demo config before starting
python scripts/validate_demo.py
```

---

## Running Tests

```bash
# All tests (1531 passing)
python -m pytest -p no:pdb -v

# Unit tests only
python -m pytest tests/ -p no:pdb -v --ignore=tests/integration

# Demo smoke tests (requires live credentials)
DEMO_SMOKE_TEST=1 python -m pytest tests/integration/test_demo_smoke.py -v
```

---

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Show help |
| `/list` | List all configured bots |
| `/status [bot_name]` | Show bot status and positions |
| `/start_bot <name>` | Start a trading bot |
| `/stop_bot <name>` | Stop a trading bot |
| `/balance <name>` | View current balance |
| `/orders <name>` | View open orders |
| `/pnl <name>` | View profit and loss |

---

## Troubleshooting

See [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues and solutions.
