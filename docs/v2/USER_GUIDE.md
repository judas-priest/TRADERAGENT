# TRADERAGENT v2.0 User Guide

## Overview

TRADERAGENT v2.0 is an autonomous cryptocurrency trading bot that supports multiple strategies on the ByBit exchange. It provides:

- **4 Trading Strategies**: SMC, Trend-Follower, Grid, DCA
- **Unified Strategy Interface**: All strategies share a common lifecycle
- **Telegram Control**: Manage bots via Telegram commands
- **Gradual Capital Deployment**: Phased scaling from 5% to 100%
- **Production Safety**: Security audits, config validation, risk limits

## Prerequisites

- Python 3.12+
- ByBit account (testnet or production)
- PostgreSQL (optional, SQLite for development)
- Redis (optional, for Telegram event streaming)
- Telegram Bot Token (optional, for remote control)

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
# Required - ByBit API
BYBIT_TESTNET_API_KEY=your_api_key
BYBIT_TESTNET_API_SECRET=your_api_secret

# Optional - Database (defaults to SQLite)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/traderagent

# Optional - Redis (for Telegram event streaming)
REDIS_URL=redis://localhost:6379

# Optional - Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=your_chat_id

# Production flags
DEBUG=false
```

### Strategy Configuration

Each strategy has a configuration dataclass. See [Strategy Documentation](STRATEGY_DOCS.md) for parameter details.

**SMC Strategy** (`bot/strategies/smc/config.py`):
```python
SMCConfig(
    risk_per_trade=Decimal("0.02"),    # 2% risk per trade
    min_risk_reward=Decimal("2.5"),    # Minimum 2.5:1 R:R
    max_position_size=Decimal("10000"),# Max $10,000 per position
    use_trailing_stop=True,
)
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

## Running Tests

```bash
# All tests
python -m pytest -p no:pdb -v

# Unit tests only
python -m pytest tests/ -p no:pdb -v --ignore=tests/testnet

# Integration tests
python -m pytest tests/integration/ -p no:pdb -v

# Load/stress tests
python -m pytest tests/testnet/test_load_stress.py -p no:pdb -v

# Testnet validation (requires API credentials)
python -m pytest tests/testnet/test_testnet_validation.py -p no:pdb -v
```

## Troubleshooting

See [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues and solutions.
