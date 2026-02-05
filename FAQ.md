# TRADERAGENT - Frequently Asked Questions (FAQ)

Answers to commonly asked questions about the TRADERAGENT trading bot.

## Table of Contents

- [General Questions](#general-questions)
- [Setup and Installation](#setup-and-installation)
- [Trading Strategies](#trading-strategies)
- [Risk and Safety](#risk-and-safety)
- [Technical Questions](#technical-questions)
- [Performance and Optimization](#performance-and-optimization)
- [Troubleshooting](#troubleshooting)

---

## General Questions

### What is TRADERAGENT?

TRADERAGENT is an autonomous trading bot for cryptocurrency exchanges that supports Grid Trading, DCA (Dollar Cost Averaging), and Hybrid strategies. It's designed to automate trading while providing robust risk management and monitoring capabilities.

### Is TRADERAGENT free to use?

Yes, TRADERAGENT is open-source and free to use under the Mozilla Public License 2.0 (MPL-2.0). However, you'll need to pay for:
- VPS/server hosting (if running 24/7)
- Exchange trading fees
- Your own trading capital

### Is TRADERAGENT profitable?

**There are no guarantees of profit.** Trading cryptocurrency involves significant risk and you can lose money. TRADERAGENT is a tool that executes strategies automatically, but profitability depends on:
- Market conditions
- Strategy parameters
- Trading pair selection
- Risk management settings
- Exchange fees

Always start with testnet and small amounts to test strategies before deploying significant capital.

### Which exchanges are supported?

TRADERAGENT uses CCXT library and supports 150+ exchanges including:
- ✅ Binance (tested)
- ✅ Bybit (tested)
- ✅ OKX (tested)
- Coinbase Pro
- Kraken
- KuCoin
- Huobi
- Bitfinex
- And many more

See [CCXT Supported Exchanges](https://docs.ccxt.com/#/README?id=supported-cryptocurrency-exchange-markets) for the full list.

### Do I need a VPS?

Not required, but **highly recommended** for:
- 24/7 operation
- Stable internet connection
- Lower latency to exchange
- No dependency on personal computer uptime

You can run locally on your computer for testing or small-scale trading.

### Is my API key secure?

Yes. TRADERAGENT:
- Encrypts API keys using AES-256 encryption
- Stores encrypted keys in local database only
- Never sends keys to external servers
- Never transmits keys over the network (except to exchange)
- Supports read-only keys (recommended)

**Best practices:**
- Use API keys with trading permissions only (no withdrawals)
- Enable IP whitelisting on exchange
- Use different keys for testnet and mainnet
- Rotate keys regularly

---

## Setup and Installation

### What are the system requirements?

**Minimum:**
- CPU: 2 cores
- RAM: 2 GB
- Storage: 10 GB
- OS: Ubuntu 20.04+, Debian 11+, or any Linux with Docker

**Recommended:**
- CPU: 4 cores
- RAM: 4 GB
- Storage: 20 GB SSD
- OS: Ubuntu 22.04 LTS

### Do I need Python knowledge?

No programming knowledge required for basic usage:
- Copy example configurations
- Edit YAML files (simple text format)
- Use Docker for deployment (automatic setup)

Python knowledge helpful for:
- Custom strategy development
- Troubleshooting issues
- Contributing to the project

### Can I run it on Windows?

Yes, but Linux is recommended. Options for Windows:
1. **Docker Desktop** - Easiest, recommended
2. **WSL 2 (Windows Subsystem for Linux)** - Good performance
3. **Native Python** - Possible but requires more setup

### Can I run it on a Raspberry Pi?

Yes! Raspberry Pi 4 with 4GB+ RAM works well. Use Docker for easy setup:

```bash
# Install Docker on Raspberry Pi
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Follow normal Docker deployment steps
```

### How long does setup take?

**With Docker (recommended):** 10-15 minutes
- 5 min: Clone repo, configure .env and config files
- 5-10 min: Docker build and start services

**Manual setup:** 20-30 minutes
- Plus time for PostgreSQL installation/setup

### Do I need a Telegram bot?

No, Telegram is optional but highly recommended for:
- Real-time notifications of trades
- Error alerts
- Bot management commands (future feature)
- Status updates

You can run without Telegram by disabling notifications in config.

---

## Trading Strategies

### Which strategy should I use?

Depends on market conditions and your goals:

**Grid Trading:**
- Best for: Range-bound markets (sideways)
- Pros: Consistent small profits, simple
- Cons: Vulnerable to strong trends
- Example: BTC trading $40k-$50k for weeks

**DCA (Dollar Cost Averaging):**
- Best for: Downtrends with expected recovery
- Pros: Lower average entry, good for accumulation
- Cons: Requires belief in asset, can lose if no recovery
- Example: Buying ETH during a dip

**Hybrid (Grid + DCA):**
- Best for: Uncertain markets
- Pros: Combines both strategies, more flexible
- Cons: More complex to configure
- Example: Grid in range, DCA protection below range

### Can I run multiple strategies simultaneously?

Yes! You can configure multiple bots in one config file:

```yaml
bots:
  - name: btc_grid
    strategy: grid
    # ...

  - name: eth_dca
    strategy: dca
    # ...

  - name: bnb_hybrid
    strategy: hybrid
    # ...
```

Each bot operates independently with its own balance tracking and risk management.

### How do I choose grid parameters?

**Step-by-step approach:**

1. **Analyze price history** (last 30-90 days)
   - Find support and resistance levels
   - Identify typical range

2. **Set boundaries** conservatively
   - Upper: Recent resistance
   - Lower: Recent support
   - Leave 10-20% buffer outside current price

3. **Choose grid levels**
   - Start with 5-10 levels
   - More levels = more trades, smaller profit each
   - Fewer levels = fewer trades, larger profit each

4. **Calculate capital needed**
   - Total = levels × amount_per_grid
   - Example: 10 levels × $100 = $1,000

5. **Set profit percentage**
   - Must cover exchange fees (typically 0.1-0.2%)
   - Recommended: 1-3% per level
   - Higher = less frequent fills

### What's a good profit target for grid trading?

**Conservative:** 2-3% per grid level
- Pros: More reliable fills
- Cons: Lower profit per trade
- Best for: Low volatility pairs

**Moderate:** 1-1.5% per grid level
- Pros: Good balance
- Cons: Still requires volatility
- Best for: Major pairs (BTC, ETH)

**Aggressive:** 0.5-1% per grid level
- Pros: Frequent fills, more trades
- Cons: Lower profit per trade, more fees
- Best for: High volatility pairs

### How many DCA steps should I use?

Depends on risk tolerance and capital:

**Conservative: 3-5 steps**
- Lower capital requirement
- Less exposure to continued drops
- Higher average entry price

**Moderate: 5-7 steps**
- Balanced approach
- Good for moderate drops
- Reasonable capital

**Aggressive: 7-10 steps**
- More capital required
- Better average on deep drops
- Higher risk if no recovery

**Formula:** Max capital needed = steps × amount_per_step
- Example: 5 steps × $100 = $500 max

---

## Risk and Safety

### Can I lose money?

**Yes.** Cryptocurrency trading is risky:
- Market can move against your positions
- Liquidation is possible (margin/futures)
- Exchange hacks or failures
- Bot errors or misconfiguration
- Network issues

**Always:**
- Start with testnet
- Use only money you can afford to lose
- Set stop-losses
- Monitor regularly
- Start with small amounts

### What are the main risks?

1. **Market Risk**
   - Price crashes (strong downtrend)
   - Flash crashes
   - Low liquidity

2. **Technical Risk**
   - Bot errors or bugs
   - Exchange API issues
   - Network problems
   - Server downtime

3. **Configuration Risk**
   - Wrong parameters
   - No stop-loss set
   - Excessive position size

4. **Exchange Risk**
   - Exchange hacked
   - Withdrawal suspended
   - Account frozen

### How can I minimize risks?

**Risk Management:**
```yaml
risk_management:
  max_position_size: "1000"  # Limit total exposure
  stop_loss_percentage: "0.20"  # 20% stop loss
  max_daily_loss: "100"  # Stop if lose $100/day
```

**Best Practices:**
1. Always test on testnet first
2. Start with small capital (1-5% of portfolio)
3. Use stop-losses
4. Monitor daily
5. Diversify across pairs/strategies
6. Keep most funds off exchange
7. Regular backups of configuration and logs

### What happens if bot crashes?

**Built-in Protection:**
- State saved to database continuously
- Bot recovers state on restart
- Open orders tracked by exchange
- No double-ordering

**Recovery Steps:**
```bash
# Check logs for errors
tail -n 100 logs/bot.log

# Restart bot
docker-compose restart bot  # Docker
# or
python -m bot.main --config configs/production.yaml  # Manual

# Verify state recovered
python -m bot.cli bot-status --name your_bot_name
```

### Should I use stop-loss?

**Pros of stop-loss:**
- Limits maximum loss
- Protects against crashes
- Peace of mind

**Cons of stop-loss:**
- Can trigger on temporary dips
- Miss recovery if stopped out

**Recommendation:**
- **Grid trading:** Optional (ranges usually recover)
- **DCA:** Yes (protects if no recovery)
- **Hybrid:** Yes (recommended 20-30%)

### Is testnet enough for testing?

Testnet is essential first step, but:

**Testnet advantages:**
- No real money risk
- Test all features
- Practice configuration

**Testnet limitations:**
- Different liquidity than mainnet
- May have bugs not in mainnet
- Different price movements

**Recommended testing path:**
1. Testnet (1-2 weeks)
2. Small mainnet ($50-100, 1-2 weeks)
3. Gradually increase if profitable

---

## Technical Questions

### What database is used?

**PostgreSQL** for production:
- Reliable and battle-tested
- Excellent performance
- Strong data integrity
- Good for time-series data

**SQLite** for tests:
- Lightweight
- No separate server needed
- Good for development

### Does it support futures/margin trading?

**Current version (v1.0):** Spot trading only

**Planned for future:**
- v2.0: Leverage trading support
- v3.0: Advanced derivatives

**Workaround:**
Some exchanges allow leverage on spot pairs - configure carefully!

### Can I backtest strategies?

Yes! TRADERAGENT includes backtesting framework:

```bash
# Run backtest
pytest bot/tests/backtesting/ -v

# Custom backtest
python -m bot.tests.backtesting.backtesting_engine \
    --symbol BTC/USDT \
    --strategy grid \
    --start-date 2024-01-01 \
    --end-date 2024-01-31
```

Features:
- Market simulator
- Historical data replay
- Performance metrics
- Equity curve generation

See [TESTING.md](TESTING.md) for details.

### How does the bot handle rate limits?

Built-in rate limit management:
- CCXT library automatic throttling
- Request queue system
- Configurable delays
- WebSocket for real-time data (fewer requests)

```yaml
exchange:
  rate_limit: true  # Enable protection
  rateLimit: 1200  # Custom delay (ms)
```

### Can I modify the code?

Yes! TRADERAGENT is open-source (MPL-2.0):
- Read and modify source code
- Add custom strategies
- Fix bugs
- Contribute improvements

**Requirements:**
- Python 3.10+ knowledge
- Understanding of async/await
- Familiarity with trading concepts

See [CONTRIBUTING](README.md#contributing) section.

### How do I update to a new version?

```bash
# Docker
git pull origin main
docker-compose build
docker-compose down
docker-compose up -d

# Manual
git pull origin main
pip install -r requirements.txt
alembic upgrade head
python -m bot.main --config configs/production.yaml
```

**Important:**
- Read CHANGELOG for breaking changes
- Test on testnet after update
- Backup database before update

---

## Performance and Optimization

### How much profit can I make?

**No guarantees!** Realistic expectations:

**Grid Trading (range-bound market):**
- Conservative: 5-15% monthly
- Moderate: 10-25% monthly
- Aggressive: 15-40% monthly (higher risk)

**DCA (downtrend + recovery):**
- Highly variable
- Can be +50% on good recovery
- Can be -30% if no recovery

**Factors affecting profit:**
- Market volatility
- Trading pair
- Strategy parameters
- Exchange fees
- Luck

### How can I optimize performance?

**Strategy Optimization:**
1. Backtest different parameters
2. Adjust grid levels based on volatility
3. Use tighter spreads in low volatility
4. Wider spreads in high volatility

**Technical Optimization:**
```yaml
# Use WebSocket for price updates
# Reduce database pool size if not needed
database_pool_size: 3

# Increase log level
log_level: WARNING  # Less I/O

# Use SSD for database
```

### What are typical trading fees?

**Exchange Fees:**
- Binance: 0.1% maker/taker
- Bybit: 0.1% maker/taker
- OKX: 0.08-0.1% maker/taker

**Fee discount strategies:**
- Hold exchange token (BNB, BIT, OKB)
- Increase trading volume for VIP status
- Use maker orders (usually cheaper)

**Profitability threshold:**
Your profit per trade must exceed 2× fees:
- With 0.1% fees: Need >0.2% profit
- Recommended: 1-3% for safety margin

### How often should I check the bot?

**Recommended monitoring:**
- **Daily:** Quick check via Telegram notifications
- **Weekly:** Review performance metrics
- **Monthly:** Adjust parameters if needed

**Signs to check immediately:**
- Error notifications
- Unusual loss
- Exchange maintenance
- High volatility events

---

## Troubleshooting

### Bot not placing orders?

**Common causes:**
1. `dry_run: true` - Set to `false` for real trading
2. Insufficient balance
3. Price outside grid range
4. Risk limits reached
5. Exchange API error

**Debug:**
```bash
grep -i "error\|order" logs/bot.log
python -m bot.cli bot-status --name your_bot
```

### Orders getting rejected?

**Common causes:**
1. Order size too small (below exchange minimum)
2. Invalid price (too many decimals)
3. Insufficient balance
4. Rate limit exceeded
5. Exchange maintenance

**Solutions:**
```yaml
# Increase order size
amount_per_grid: "15"  # Above minimum

# Check exchange status
# Visit exchange status page
```

### High CPU/memory usage?

**Solutions:**
1. Reduce grid levels
2. Increase log level (less logging)
3. Use WebSocket instead of polling
4. Restart bot daily (cron job)
5. Upgrade server resources

### Still need help?

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Search [GitHub Issues](https://github.com/alekseymavai/TRADERAGENT/issues)
3. Ask in [GitHub Discussions](https://github.com/alekseymavai/TRADERAGENT/discussions)
4. Create new issue with:
   - Problem description
   - Configuration (remove secrets)
   - Relevant logs
   - System info

---

## Related Documentation

- [README.md](README.md) - Main documentation
- [CONFIGURATION.md](CONFIGURATION.md) - Configuration guide
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Troubleshooting guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [TESTING.md](TESTING.md) - Testing guide
- [ROADMAP.md](ROADMAP.md) - Future plans

---

**⚠️ Disclaimer:** This bot is for educational purposes only. Cryptocurrency trading carries significant risk. Always do your own research and never invest more than you can afford to lose.
