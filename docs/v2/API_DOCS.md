# TRADERAGENT v2.0 API Documentation

## Exchange Client

### ByBitDirectClient

**Module**: `bot/api/bybit_direct_client.py`

Direct implementation of ByBit V5 API with demo trading support.

```python
from bot.api.bybit_direct_client import ByBitDirectClient

client = ByBitDirectClient(
    api_key="your_key",
    api_secret="your_secret",
    testnet=True,          # Use demo trading endpoint
    market_type="linear",  # "linear" (USDT perps) or "spot"
)
await client.initialize()
```

#### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `initialize()` | Create HTTP session and load markets | `None` |
| `close()` | Close HTTP session | `None` |
| `fetch_ticker(symbol)` | Get current price data | `dict` |
| `fetch_markets()` | Get all available markets | `dict` |
| `fetch_balance()` | Get account balance | `dict` |
| `fetch_open_orders(symbol)` | Get open orders | `list` |
| `create_limit_order(symbol, side, amount, price)` | Place limit order | `dict` |
| `create_market_order(symbol, side, amount)` | Place market order | `dict` |
| `cancel_order(order_id, symbol)` | Cancel an order | `dict` |
| `fetch_klines(symbol, interval, limit)` | Get candlestick data | `list` |
| `get_statistics()` | Get client statistics | `dict` |

#### URLs

| Environment | URL |
|------------|-----|
| Production | `https://api.bybit.com` |
| Demo Trading | `https://api-demo.bybit.com` |

#### Authentication

All private endpoints use HMAC SHA256 signatures:
- Timestamp + API key + recv_window + query string/body
- `recv_window` = 10000ms (handles server time drift)

#### Error Handling

```python
from bot.api.exceptions import (
    AuthenticationError,    # Invalid API key/secret
    RateLimitError,         # Too many requests
    InsufficientFundsError, # Not enough balance
    InvalidOrderError,      # Bad order params
    NetworkError,           # Connection issues
    ExchangeAPIError,       # Generic API error
)
```

Automatic retry (via tenacity) on `NetworkError` and `RateLimitError` with exponential backoff.

---

## Strategy Interface

### BaseStrategy (Abstract)

**Module**: `bot/strategies/base.py`

```python
from bot.strategies.base import BaseStrategy

class MyStrategy(BaseStrategy):
    @property
    def strategy_type(self) -> str:
        return "my_strategy"

    def analyze_market(self, *dataframes: pd.DataFrame) -> BaseMarketAnalysis:
        ...

    def generate_signal(self, df: pd.DataFrame, balance: Decimal) -> BaseSignal | None:
        ...

    def open_position(self) -> PositionInfo:
        ...

    def update_positions(self, current_price: Decimal, df: pd.DataFrame) -> list[PositionInfo]:
        ...

    def close_position(self) -> PositionInfo:
        ...

    def get_performance(self) -> StrategyPerformance:
        ...
```

### Strategy Adapters

| Adapter | Module | Strategy Type |
|---------|--------|--------------|
| `SMCStrategyAdapter` | `bot/strategies/smc_adapter.py` | `"smc"` |
| `TrendFollowerAdapter` | `bot/strategies/trend_follower_adapter.py` | `"trend_follower"` |
| `GridAdapter` | `bot/strategies/grid_adapter.py` | `"grid"` |
| `DCAAdapter` | `bot/strategies/dca_adapter.py` | `"dca"` |

---

## Orchestrator

### BotOrchestrator

**Module**: `bot/orchestrator/bot_orchestrator.py`

Manages the trading loop: strategy execution, order placement, and position tracking.

```python
from bot.orchestrator.bot_orchestrator import BotOrchestrator, BotState

orchestrator = BotOrchestrator(
    name="btc_smc",
    strategy=smc_adapter,
    client=bybit_client,
    db_manager=db_manager,
)
```

#### States

| State | Description |
|-------|-------------|
| `INITIALIZING` | Setting up components |
| `RUNNING` | Actively trading |
| `PAUSED` | No new trades, positions maintained |
| `STOPPED` | Fully stopped |
| `ERROR` | Error state, needs intervention |

---

## Database

### DatabaseManager

**Module**: `bot/database/manager.py`

Async database operations for credentials, bots, orders, trades, and grid levels.

```python
from bot.database.manager import DatabaseManager

db = DatabaseManager(database_url="sqlite+aiosqlite:///trading.db")
await db.initialize()
```

#### Models

| Model | Table | Purpose |
|-------|-------|---------|
| `Credential` | `credentials` | API key storage |
| `BotModel` | `bots` | Bot configuration |
| `Order` | `orders` | Order history |
| `Trade` | `trades` | Trade records |
| `GridLevel` | `grid_levels` | Grid strategy levels |
| `BotLog` | `bot_logs` | Structured logs |

---

## Capital Manager

### CapitalManager

**Module**: `bot/utils/capital_manager.py`

Phased capital deployment with performance gates.

```python
from bot.utils.capital_manager import CapitalManager

cm = CapitalManager(total_capital=Decimal("10000"))
```

#### Methods

| Method | Description | Returns |
|--------|-------------|---------|
| `start_phase_1()` | Begin with 5% allocation | `Decimal` (allocated capital) |
| `record_trade(won, pnl)` | Record a trade result | `None` |
| `record_error()` | Record an error event | `None` |
| `evaluate_scaling()` | Check if scaling gates are met | `ScalingDecision` |
| `advance_phase()` | Scale to next phase | `Decimal` (new allocation) |
| `halt(reason)` | Stop all trading | `None` |
| `get_report()` | Get deployment status report | `dict` |

#### ScalingDecision

```python
@dataclass
class ScalingDecision:
    can_scale: bool
    current_phase: DeploymentPhase
    next_phase: DeploymentPhase | None
    reasons: list[str]    # Passed gates
    blockers: list[str]   # Failed gates
```

---

## Security Audit

### SecurityAuditor

**Module**: `bot/utils/security_audit.py`

```python
from bot.utils.security_audit import SecurityAuditor

auditor = SecurityAuditor(project_root="/path/to/project")
report = auditor.run_full_audit()
```

#### Checks

| Check | Severity | Description |
|-------|----------|-------------|
| `env_file_protected` | critical | `.env` in `.gitignore` |
| `no_hardcoded_secrets` | critical | No API keys in source |
| `gitignore_complete` | warning | Essential patterns present |
| `debug_disabled` | warning | DEBUG mode off |
| `env_vars_set` | warning | Required vars present |
| `database_url_secure` | warning | SSL for remote DB |
| `redis_url_secure` | info | Redis connection check |

---

## Config Validator

### ConfigValidator

**Module**: `bot/utils/config_validator.py`

```python
from bot.utils.config_validator import ConfigValidator

validator = ConfigValidator()
report = validator.run_full_validation(
    risk={"risk_per_trade": Decimal("0.02")},
    grid={"num_levels": 10},
    dca={"max_safety_orders": 5},
)
```

#### Validation Categories

| Category | Checks |
|----------|--------|
| `risk` | risk_per_trade, max_exposure, max_daily_loss, min_risk_reward |
| `strategy` | grid_levels, grid_total_investment, grid_range, dca_safety_orders, dca_max_capital, dca_take_profit |

---

## Event System

### TradingEvent

**Module**: `bot/orchestrator/events.py`

```python
from bot.orchestrator.events import EventType, TradingEvent

event = TradingEvent(
    event_type=EventType.TRADE_OPENED,
    bot_name="btc_smc",
    data={"symbol": "BTC/USDT", "side": "buy", "amount": "0.001"},
)
```

#### Event Types

| Type | Description |
|------|-------------|
| `TRADE_OPENED` | New position opened |
| `TRADE_CLOSED` | Position closed |
| `ORDER_PLACED` | Order submitted |
| `ORDER_FILLED` | Order executed |
| `ORDER_CANCELLED` | Order cancelled |
| `SIGNAL_GENERATED` | New signal detected |
| `ERROR` | Error occurred |
| `STATUS_CHANGE` | Bot state changed |
