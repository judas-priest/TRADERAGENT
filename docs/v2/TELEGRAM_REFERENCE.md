# TRADERAGENT v2.0 Telegram Command Reference

## Setup

### Prerequisites

1. Create a Telegram bot via [@BotFather](https://t.me/BotFather)
2. Get your chat ID via [@userinfobot](https://t.me/userinfobot)
3. Set environment variables:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=your_chat_id
REDIS_URL=redis://localhost:6379
```

### Security

Only chat IDs in the `allowed_chat_ids` list can execute commands. Unauthorized users receive no response.

---

## Control Commands

### `/start`

Displays welcome message and available commands.

### `/help`

Shows the full command list with descriptions.

### `/start_bot [name]`

Starts a specific trading bot by name.

**Example**: `/start_bot btc_smc`

### `/stop_bot [name]`

Stops a specific trading bot. Cancels open orders and closes positions.

**Example**: `/stop_bot btc_smc`

### `/pause`

Pauses all active trading bots. Existing positions are maintained but no new trades are opened.

### `/resume`

Resumes paused trading bots.

---

## Monitoring Commands

### `/status`

Shows the current state of all bots:

```
Bot: btc_smc
  State: RUNNING
  Strategy: smc
  Uptime: 2d 5h 30m

Bot: eth_grid
  State: PAUSED
  Strategy: grid
```

### `/balance`

Fetches and displays current account balance from ByBit.

```
Balance:
  Total: $10,234.56
  Free: $8,100.00
  Used: $2,134.56
```

### `/orders`

Lists open orders across all bots.

```
Open Orders:
  BTC/USDT BUY LIMIT @ $42,000 (0.01 BTC)
  ETH/USDT SELL LIMIT @ $3,200 (0.5 ETH)
```

### `/positions`

Shows current open positions with unrealized PnL.

```
Positions:
  BTC/USDT LONG 0.01 BTC
    Entry: $43,000 | Current: $43,500
    PnL: +$5.00 (+1.16%)
```

### `/pnl`

Shows profit/loss summary.

```
PnL Summary:
  Today: +$125.50
  This Week: +$430.00
  Total: +$1,245.00
```

### `/list`

Lists all configured bots and their states.

```
Configured Bots:
  1. btc_smc [RUNNING] - SMC on BTC/USDT
  2. eth_grid [STOPPED] - Grid on ETH/USDT
  3. sol_dca [PAUSED] - DCA on SOL/USDT
```

### `/report`

Generates a detailed performance report including:
- Win rate, total trades, profit factor
- Max drawdown, Sharpe ratio
- Per-strategy breakdown
- Capital deployment phase status

---

## Strategy Commands

### `/switch_strategy [bot_name] [strategy]`

Switches a bot's active strategy.

**Strategies**: `smc`, `trend_follower`, `grid`, `dca`

**Example**: `/switch_strategy btc_smc trend_follower`

---

## Event Notifications

When Redis is configured, the bot automatically sends notifications for:

| Event | Description |
|-------|-------------|
| `TRADE_OPENED` | New position opened |
| `TRADE_CLOSED` | Position closed with PnL |
| `ORDER_FILLED` | Limit order executed |
| `SIGNAL_GENERATED` | New trading signal detected |
| `ERROR` | Strategy or API error |
| `PHASE_ADVANCED` | Capital deployment phase changed |

Notifications are pushed to all `allowed_chat_ids` via Redis Pub/Sub.

---

## Multi-Bot Management

The Telegram bot manages multiple `BotOrchestrator` instances. Each bot has:
- A unique name (e.g., `btc_smc`, `eth_grid`)
- Its own strategy configuration
- Independent state (RUNNING, PAUSED, STOPPED)

```python
TelegramBot(
    token="...",
    allowed_chat_ids=[123456789],
    orchestrators={
        "btc_smc": orchestrator_1,
        "eth_grid": orchestrator_2,
    },
)
```
