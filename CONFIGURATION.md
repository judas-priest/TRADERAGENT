# TRADERAGENT - Configuration Guide

Comprehensive guide for configuring the TRADERAGENT trading bot.

## Table of Contents

- [Overview](#overview)
- [Configuration File Structure](#configuration-file-structure)
- [Environment Variables](#environment-variables)
- [Bot Configuration](#bot-configuration)
- [Strategy Configurations](#strategy-configurations)
- [Risk Management Configuration](#risk-management-configuration)
- [Notifications Configuration](#notifications-configuration)
- [Advanced Configuration](#advanced-configuration)
- [Configuration Examples](#configuration-examples)
- [Best Practices](#best-practices)

---

## Overview

TRADERAGENT uses a combination of environment variables (`.env`) and YAML configuration files (`configs/*.yaml`) for configuration.

**Configuration Hierarchy:**
1. Environment variables (`.env`) - infrastructure and secrets
2. YAML config files (`configs/*.yaml`) - bot and trading parameters
3. Command-line arguments - override specific settings

---

## Configuration File Structure

### Directory Layout

```
TRADERAGENT/
├── .env                          # Environment variables (DO NOT commit)
├── .env.example                  # Example environment variables
├── configs/
│   ├── example.yaml              # Example configuration
│   ├── production.yaml           # Production configuration (DO NOT commit)
│   ├── development.yaml          # Development configuration
│   └── testnet.yaml              # Testnet configuration
└── alembic.ini                   # Database migrations config
```

---

## Environment Variables

### Creating .env File

```bash
cp .env.example .env
nano .env  # Edit with your values
```

### Database Configuration

```bash
# PostgreSQL configuration
DB_USER=traderagent
DB_PASSWORD=your_secure_password_here
DB_NAME=traderagent
DB_HOST=localhost  # Use 'postgres' in Docker
DB_PORT=5432

# Full database URL (auto-generated from above in docker-compose)
# DATABASE_URL=postgresql+asyncpg://traderagent:password@localhost:5432/traderagent
```

**Best Practices:**
- Use strong passwords (min 16 characters)
- Never commit `.env` to version control
- Rotate passwords regularly

### Redis Configuration

```bash
# Redis configuration
REDIS_HOST=localhost  # Use 'redis' in Docker
REDIS_PORT=6379
REDIS_PASSWORD=  # Optional, leave empty if not using auth

# Full Redis URL
# REDIS_URL=redis://localhost:6379
```

### Bot Configuration

```bash
# Bot settings
CONFIG_FILE=production.yaml  # Path to main config file
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**Log Levels:**
- `DEBUG` - Detailed information for debugging (verbose)
- `INFO` - General information (recommended for production)
- `WARNING` - Warning messages only
- `ERROR` - Error messages only
- `CRITICAL` - Critical errors only

### Telegram Bot Configuration

```bash
# Telegram Bot Token from @BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Allowed chat IDs (comma-separated)
TELEGRAM_ALLOWED_CHAT_IDS=123456789,987654321
```

**Getting Telegram Credentials:**
1. Create bot: Send `/newbot` to [@BotFather](https://t.me/botfather)
2. Get chat ID: Send message to [@userinfobot](https://t.me/userinfobot)

### Security Configuration

```bash
# Encryption key for API keys storage (32 bytes, base64-encoded)
ENCRYPTION_KEY=your_base64_encoded_32_byte_key_here
```

**Generate Encryption Key:**
```bash
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

⚠️ **IMPORTANT:** Store encryption key securely. If lost, you cannot decrypt API keys!

---

## Bot Configuration

### Main Configuration Structure

```yaml
# configs/production.yaml

# Database Configuration
database_url: postgresql+asyncpg://user:password@localhost/traderagent
database_pool_size: 5  # Connection pool size

# Logging Configuration
log_level: INFO
log_to_file: true
log_to_console: true
json_logs: false  # Enable for structured logging

# Encryption Key (can also use env variable)
encryption_key: ${ENCRYPTION_KEY}

# Bot Configurations
bots:
  - # Bot 1 configuration
    version: 1
    name: my_first_bot
    # ... (see below)

  - # Bot 2 configuration
    version: 1
    name: my_second_bot
    # ... (see below)
```

### Bot Instance Configuration

```yaml
bots:
  - version: 1  # Configuration schema version
    name: btc_grid_bot  # Unique bot name (alphanumeric, underscores)
    symbol: BTC/USDT  # Trading pair (format: BASE/QUOTE)
    strategy: grid  # Strategy: grid, dca, or hybrid

    # Exchange configuration (see below)
    exchange:
      exchange_id: binance
      credentials_name: binance_main
      sandbox: true
      rate_limit: true

    # Strategy configuration (see Strategy Configurations section)
    grid:
      # ...

    # Risk management (see Risk Management section)
    risk_management:
      # ...

    # Notifications (see Notifications section)
    notifications:
      # ...

    # Operational settings
    dry_run: true  # Simulation mode (no real orders)
    auto_start: false  # Auto-start on bot initialization
```

### Exchange Configuration

```yaml
exchange:
  exchange_id: binance  # Exchange ID (binance, bybit, okx, etc.)
  credentials_name: binance_main  # Reference to stored credentials
  sandbox: true  # Use testnet/sandbox mode
  rate_limit: true  # Enable rate limit protection
```

**Supported Exchanges:**
- All exchanges supported by CCXT library (150+)
- Tested exchanges: Binance, Bybit, OKX
- See [CCXT Documentation](https://docs.ccxt.com/#/README?id=supported-cryptocurrency-exchange-markets) for full list

**Credentials Storage:**
API credentials are stored encrypted in the database. Use Telegram bot or CLI to add credentials:

```bash
# Add credentials via CLI
python -m bot.cli add-credentials \
    --name binance_main \
    --exchange binance \
    --api-key YOUR_API_KEY \
    --api-secret YOUR_API_SECRET
```

---

## Strategy Configurations

### Grid Trading Strategy

```yaml
grid:
  enabled: true  # Enable grid trading
  upper_price: "50000"  # Upper price boundary (string for precision)
  lower_price: "40000"  # Lower price boundary
  grid_levels: 10  # Number of grid levels (2-100)
  amount_per_grid: "100"  # Amount per grid level in quote currency
  profit_per_grid: "0.01"  # Profit per grid (0.01 = 1%)
```

**Parameter Guidelines:**

**upper_price & lower_price:**
- Must be strings for decimal precision
- `upper_price` must be > `lower_price`
- Range should cover expected price movement
- Wider range = fewer fills, narrower = more frequent trades

**grid_levels:**
- Min: 2, Max: 100
- More levels = smaller profit per level, more trades
- Fewer levels = larger profit per level, fewer trades
- Recommended: 5-20 for most scenarios

**amount_per_grid:**
- Amount in quote currency (USDT, BUSD, etc.)
- Must meet exchange minimum order size
- Total capital = `amount_per_grid` × `grid_levels`
- Example: 10 levels × $100 = $1,000 total

**profit_per_grid:**
- Decimal format (0.01 = 1%, 0.005 = 0.5%)
- Min: 0.001 (0.1%), Max: 1.0 (100%)
- Must cover exchange fees (typically 0.1%)
- Recommended: 0.01-0.03 (1-3%)

**Example Calculation:**
```
Price Range: $40,000 - $50,000
Grid Levels: 10
Price Step: ($50,000 - $40,000) / 10 = $1,000

Level 1: Buy at $41,000, Sell at $41,410 (+1%)
Level 2: Buy at $42,000, Sell at $42,420 (+1%)
...
Level 10: Buy at $50,000, Sell at $50,500 (+1%)

Total Capital Required: 10 × $100 = $1,000 USDT
```

### DCA (Dollar Cost Averaging) Strategy

```yaml
dca:
  enabled: true  # Enable DCA
  trigger_percentage: "0.05"  # Price drop to trigger (0.05 = 5%)
  amount_per_step: "100"  # Amount per DCA step
  max_steps: 5  # Maximum DCA steps (1-20)
  take_profit_percentage: "0.1"  # Take profit (0.1 = 10%)
```

**Parameter Guidelines:**

**trigger_percentage:**
- Price drop percentage to trigger next DCA step
- Decimal format (0.05 = 5%, 0.03 = 3%)
- Smaller = more aggressive (more steps), larger = more conservative
- Recommended: 0.03-0.10 (3-10%)

**amount_per_step:**
- Amount to buy on each DCA step
- Must meet exchange minimum order size
- Total max capital = `amount_per_step` × `max_steps`
- Can increase per step (see Advanced Configuration)

**max_steps:**
- Max number of DCA steps
- Min: 1, Max: 20
- Protects against unlimited drawdown
- Recommended: 3-7 steps

**take_profit_percentage:**
- Profit target to exit DCA position
- Calculated from average entry price
- Recommended: 0.05-0.15 (5-15%)

**Example Scenario:**
```
Initial Entry: $45,000
Trigger: 5% drop
Amount per step: $100
Max steps: 5

Step 1: $45,000 (initial entry, $100)
Step 2: $42,750 (-5%, $100, avg: $43,875)
Step 3: $40,612 (-5%, $100, avg: $42,787)
Step 4: $38,582 (-5%, $100, avg: $41,736)
Step 5: $36,653 (-5%, $100, avg: $40,719)

Take Profit: $44,791 (+10% from avg $40,719)
Total Capital Used: $500
```

### Hybrid Strategy (Grid + DCA)

```yaml
grid:
  enabled: true
  upper_price: "50000"
  lower_price: "45000"
  grid_levels: 5
  amount_per_grid: "200"
  profit_per_grid: "0.015"

dca:
  enabled: true
  trigger_percentage: "0.03"  # DCA triggers when price drops 3% below grid
  amount_per_step: "150"
  max_steps: 3
  take_profit_percentage: "0.08"
```

**Hybrid Strategy Logic:**
1. Grid operates in range: $45,000 - $50,000
2. If price drops below $45,000 by 3% → DCA activates
3. DCA accumulates position with averaging
4. When price recovers 8% above avg → DCA exits
5. Grid continues normal operation

**Benefits:**
- Passive income from grid in range
- Protection against deep drawdowns via DCA
- Combines trend and range strategies

---

## Risk Management Configuration

```yaml
risk_management:
  max_position_size: "10000"  # Maximum total position in quote currency
  stop_loss_percentage: "0.15"  # Stop loss (0.15 = 15%, optional)
  max_daily_loss: "500"  # Max daily loss in quote currency (optional)
  min_order_size: "10"  # Minimum order size in quote currency
```

**Parameter Guidelines:**

**max_position_size:**
- Maximum total position value
- Prevents over-exposure
- Should be based on portfolio size
- Recommended: 10-30% of total capital

**stop_loss_percentage:**
- Optional global stop loss
- Stops all trading if portfolio drops by this %
- `null` to disable
- Recommended: 0.15-0.30 (15-30%)

**max_daily_loss:**
- Optional daily loss limit
- Pauses trading if daily loss exceeds this amount
- Resets at midnight UTC
- `null` to disable
- Recommended: 1-5% of capital

**min_order_size:**
- Minimum order size to place
- Must meet exchange requirements
- Prevents dust orders
- Check exchange minimums

**Exchange Minimum Order Sizes (Examples):**
```
Binance:
- BTC/USDT: $10
- ETH/USDT: $10
- Most pairs: $10

Bybit:
- BTC/USDT: $10
- ETH/USDT: $10

OKX:
- Varies by pair
```

---

## Notifications Configuration

```yaml
notifications:
  enabled: true  # Enable notifications
  telegram_bot_token: ${TELEGRAM_BOT_TOKEN}  # From env or hardcode
  telegram_chat_id: ${TELEGRAM_CHAT_ID}  # From env or hardcode
  notify_on_trade: true  # Notify on order execution
  notify_on_error: true  # Notify on errors
  notify_on_startup: true  # Notify when bot starts
  notify_on_shutdown: true  # Notify when bot stops
```

**Notification Types:**

**Trade Notifications:**
- Order placed
- Order filled
- Order cancelled
- Grid level filled
- DCA step triggered
- Take profit hit
- Stop loss hit

**System Notifications:**
- Bot started
- Bot stopped
- Configuration reloaded
- Error occurred
- Warning issued
- Risk limit hit

**Example Notifications:**
```
🟢 Trade Executed
Bot: btc_grid_bot
Pair: BTC/USDT
Type: BUY
Price: $45,123.45
Amount: 0.0022 BTC ($100)
Strategy: Grid Level 5
Time: 2026-02-05 18:30:45 UTC

⚠️ Risk Alert
Bot: btc_grid_bot
Alert: Approaching max position size
Current: $9,500 / $10,000
Action: Limiting new orders
```

---

## Advanced Configuration

### Database Connection Pool

```yaml
database_url: postgresql+asyncpg://user:pass@localhost/traderagent
database_pool_size: 5  # Connection pool size
database_pool_timeout: 30  # Timeout in seconds
database_max_overflow: 10  # Max overflow connections
```

### Logging Configuration

```yaml
log_level: INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
log_to_file: true  # Log to file
log_to_console: true  # Log to console
log_file_path: logs/bot.log  # Log file path
log_max_bytes: 10485760  # 10MB per log file
log_backup_count: 5  # Keep 5 old log files
json_logs: false  # Use JSON structured logging
```

### Hot Reload Configuration

```yaml
hot_reload: true  # Enable hot reload
reload_interval: 60  # Check for config changes every 60 seconds
```

### Multiple Bots Configuration

```yaml
bots:
  # Grid bot on BTC
  - name: btc_grid
    symbol: BTC/USDT
    strategy: grid
    # ...

  # DCA bot on ETH
  - name: eth_dca
    symbol: ETH/USDT
    strategy: dca
    # ...

  # Hybrid bot on BNB
  - name: bnb_hybrid
    symbol: BNB/USDT
    strategy: hybrid
    # ...
```

### Exchange-Specific Settings

```yaml
exchange:
  exchange_id: binance
  credentials_name: binance_main
  sandbox: false
  rate_limit: true

  # Advanced settings
  enableRateLimit: true
  rateLimit: 1200  # Custom rate limit (ms)
  timeout: 30000  # Request timeout (ms)

  # Order options
  defaultType: limit  # limit or market
  recvWindow: 5000  # API receive window (ms, Binance specific)
```

---

## Configuration Examples

### Example 1: Conservative Grid Bot (Testnet)

```yaml
bots:
  - version: 1
    name: conservative_grid
    symbol: BTC/USDT
    strategy: grid

    exchange:
      exchange_id: binance
      credentials_name: binance_testnet
      sandbox: true  # Testnet
      rate_limit: true

    grid:
      enabled: true
      upper_price: "50000"
      lower_price: "45000"
      grid_levels: 5  # Few levels
      amount_per_grid: "100"
      profit_per_grid: "0.02"  # 2% profit

    risk_management:
      max_position_size: "5000"
      stop_loss_percentage: "0.20"  # 20% stop loss
      min_order_size: "10"

    notifications:
      enabled: true
      notify_on_trade: true
      notify_on_error: true

    dry_run: true  # Simulation mode
    auto_start: false
```

### Example 2: Aggressive DCA Bot (Production)

```yaml
bots:
  - version: 1
    name: aggressive_dca
    symbol: ETH/USDT
    strategy: dca

    exchange:
      exchange_id: binance
      credentials_name: binance_main
      sandbox: false  # Real trading
      rate_limit: true

    dca:
      enabled: true
      trigger_percentage: "0.03"  # 3% trigger
      amount_per_step: "200"
      max_steps: 7  # Aggressive (7 steps)
      take_profit_percentage: "0.08"  # 8% profit

    risk_management:
      max_position_size: "15000"
      stop_loss_percentage: "0.25"  # 25% stop loss
      max_daily_loss: "750"
      min_order_size: "10"

    notifications:
      enabled: true
      notify_on_trade: true
      notify_on_error: true

    dry_run: false  # Real orders
    auto_start: true
```

### Example 3: Balanced Hybrid Bot

```yaml
bots:
  - version: 1
    name: balanced_hybrid
    symbol: BTC/USDT
    strategy: hybrid

    exchange:
      exchange_id: binance
      credentials_name: binance_main
      sandbox: false
      rate_limit: true

    grid:
      enabled: true
      upper_price: "50000"
      lower_price: "45000"
      grid_levels: 8  # Moderate
      amount_per_grid: "150"
      profit_per_grid: "0.015"  # 1.5%

    dca:
      enabled: true
      trigger_percentage: "0.04"  # 4% below grid
      amount_per_step: "150"
      max_steps: 5
      take_profit_percentage: "0.10"  # 10%

    risk_management:
      max_position_size: "12000"
      stop_loss_percentage: "0.20"
      max_daily_loss: "600"
      min_order_size: "10"

    notifications:
      enabled: true
      notify_on_trade: true
      notify_on_error: true

    dry_run: false
    auto_start: true
```

---

## Best Practices

### Security

1. **Never commit secrets:**
   - Add `.env` to `.gitignore`
   - Use environment variables for sensitive data
   - Rotate API keys regularly

2. **Use read-only API keys when possible:**
   - Disable withdrawals
   - Enable IP whitelisting
   - Use separate keys for testnet/mainnet

3. **Secure encryption key:**
   - Generate strong 32-byte key
   - Store securely (password manager, vault)
   - Never share or commit

### Testing

1. **Always start with testnet:**
   ```yaml
   sandbox: true
   dry_run: true
   ```

2. **Test with small amounts:**
   ```yaml
   amount_per_grid: "10"  # Small amount
   max_position_size: "100"  # Small limit
   ```

3. **Enable all notifications during testing:**
   ```yaml
   notify_on_trade: true
   notify_on_error: true
   notify_on_startup: true
   ```

### Production

1. **Start conservative:**
   - Fewer grid levels
   - Wider price ranges
   - Lower position sizes
   - Higher profit targets

2. **Monitor closely:**
   - Check logs daily
   - Review performance weekly
   - Adjust parameters based on results

3. **Use risk management:**
   - Always set `max_position_size`
   - Consider `stop_loss_percentage`
   - Set `max_daily_loss` for volatile markets

### Performance Optimization

1. **Database connection pool:**
   ```yaml
   database_pool_size: 5  # Default
   database_pool_size: 10  # For multiple bots
   database_pool_size: 20  # For many bots
   ```

2. **Logging:**
   ```yaml
   log_level: INFO  # Production
   log_level: DEBUG  # Only for debugging
   json_logs: true  # For log aggregation
   ```

3. **Rate limiting:**
   ```yaml
   rate_limit: true  # Always enable
   ```

### Configuration Validation

Before deploying, validate your configuration:

```bash
# Validate configuration
python -m bot.cli validate-config --config configs/production.yaml

# Test configuration (dry run)
python -m bot.main --config configs/production.yaml --dry-run

# Check testnet connection
pytest bot/tests/testnet/ --testnet -v
```

---

## Troubleshooting

### Configuration Errors

**Error: "Invalid configuration: upper_price must be greater than lower_price"**
- Solution: Ensure `upper_price` > `lower_price` in grid config

**Error: "Strategy 'grid' requires grid configuration"**
- Solution: Add `grid:` section to bot config when using `strategy: grid`

**Error: "Failed to decrypt API credentials"**
- Solution: Check `ENCRYPTION_KEY` is correct and matches key used to encrypt

**Error: "Database connection failed"**
- Solution: Check `DATABASE_URL` and ensure PostgreSQL is running

### See Also

- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Full troubleshooting guide
- [FAQ.md](FAQ.md) - Frequently asked questions
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide

---

**Need Help?**
- 📧 [GitHub Issues](https://github.com/alekseymavai/TRADERAGENT/issues)
- 📖 [Full Documentation](https://github.com/alekseymavai/TRADERAGENT)
