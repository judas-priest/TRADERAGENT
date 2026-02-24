# TRADERAGENT Bot - Deployment Guide

> **Обновлено:** 2026-02-23 — добавлен Bybit Demo Trading, актуализированы конфиги

Complete guide for deploying the TRADERAGENT trading bot to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Demo Trading)](#quick-start-demo-trading)
- [Detailed Setup](#detailed-setup)
- [Bybit Demo Trading](#bybit-demo-trading)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Maintenance](#maintenance)
- [Security Best Practices](#security-best-practices)

## Prerequisites

### Required Software

- **Docker** (>= 20.10) and **Docker Compose** (>= 2.0)
- **Git** for cloning the repository
- **Python 3.12+** (for local development and scripts)

### Required Accounts

1. **Bybit Account**: Production account at [bybit.com](https://bybit.com) (works for both live and demo trading)
2. **Telegram Bot**: Create via [@BotFather](https://t.me/botfather) (optional but recommended)
3. **Server**: VPS/VDS with at least 2GB RAM and 10GB storage

### System Requirements

- **Minimum**: 2 CPU cores, 2GB RAM, 10GB storage
- **Recommended**: 4 CPU cores, 4GB RAM, 20GB storage
- **Operating System**: Ubuntu 20.04/22.04/24.04, Debian 11+, or any Linux with Docker support

---

## Quick Start (Demo Trading)

For users who want to start with paper trading (virtual funds on Bybit Demo):

```bash
# 1. Clone repository
git clone https://github.com/alekseymavai/TRADERAGENT.git
cd TRADERAGENT

# 2. Configure environment
cp .env.example .env
nano .env  # Fill in: DATABASE_URL, ENCRYPTION_KEY, TELEGRAM_BOT_TOKEN

# 3. Start infrastructure
docker compose up -d postgres redis

# 4. Run database migrations
docker compose run --rm bot python -m bot.database.migrations

# 5. Validate demo config
python scripts/validate_demo.py

# 6. Start bot with demo config
CONFIG_FILE=configs/phase7_demo.yaml docker compose up -d bot

# 7. Check logs
docker compose logs -f bot
```

---

## Detailed Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/alekseymavai/TRADERAGENT.git
cd TRADERAGENT
```

### Step 2: Create Telegram Bot (Optional)

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command and follow instructions
3. Save the **bot token** provided by BotFather
4. Get your **chat ID** by sending a message to [@userinfobot](https://t.me/userinfobot)

### Step 3: Environment Configuration

Create `.env` file from the example:

```bash
cp .env.example .env
nano .env
```

**Required Variables:**

```env
# Database (required)
DATABASE_URL=postgresql+asyncpg://traderagent:yourpassword@postgres:5432/traderagent

# Encryption key for API credentials (required)
# Generate: python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
ENCRYPTION_KEY=your_generated_base64_key_here

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather
TELEGRAM_ALLOWED_CHAT_IDS=your_chat_id_from_userinfobot

# Logging
LOG_LEVEL=INFO
```

### Step 4: Bot Configuration

The main config for demo trading is `configs/phase7_demo.yaml`. For custom deployment, copy and edit:

```bash
cp configs/phase7_demo.yaml configs/production.yaml
nano configs/production.yaml
```

**Key Configuration Sections:**

```yaml
# Database
database_url: ${DATABASE_URL}
encryption_key: ${ENCRYPTION_KEY}

bots:
  - name: my_btc_bot
    symbol: BTC/USDT
    strategy: hybrid  # grid | dca | hybrid | trend_follower | smc

    exchange:
      exchange_id: bybit
      credentials_name: bybit_demo   # Name of credentials in DB
      sandbox: true   # true = api-demo.bybit.com (Demo)
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

    dry_run: false   # false = real orders (virtual money on demo)
    auto_start: true
```

### Step 5: Exchange API Keys

API keys are stored **encrypted in PostgreSQL**, referenced by `credentials_name` in the YAML. They are **never** stored in `.env` or config files.

To add credentials after the bot first starts:
```bash
# Via Telegram command: /set_credentials bybit_demo <api_key> <api_secret>
# Or via the validate_demo.py script which checks credentials exist
```

---

## Bybit Demo Trading

Demo trading uses **virtual funds** on `api-demo.bybit.com`. You get 100,000 USDT to trade with. Your **production API keys** work for demo — no separate testnet keys needed.

### Why Demo, Not Testnet?

| | Demo (`api-demo.bybit.com`) | Testnet (`testnet.bybit.com`) |
|---|---|---|
| API keys | **Production keys** | Separate testnet keys |
| Balance | 100,000 USDT virtual | Separate testnet balance |
| Instruments | Linear futures (same as live) | Testnet instruments |
| CCXT sandbox | ❌ Routes to testnet (wrong!) | ✅ |
| Our client | ✅ `ByBitDirectClient` auto-routes | ❌ |

**CCXT `set_sandbox_mode(True)` is NOT used.** `ByBitDirectClient` connects directly to `api-demo.bybit.com` when `sandbox: true` in config.

### Demo Constraints

- Only **linear (futures) contracts** supported — no spot trading
- Minimum order sizes apply (same as live): BTC ≥ 0.001 BTC (~$64), ETH ≥ 0.01 ETH (~$20)
- Same API rate limits as production

### Setup Steps

1. Activate Demo Trading in your Bybit account
2. Generate API keys (production account → API Management)
3. Add permissions: Contract Trading (read + write)
4. Store in database via Telegram or validate script
5. Use `configs/phase7_demo.yaml` as-is or customize

---

## Deployment

### Docker Compose (Recommended)

```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f bot

# Restart after code change (bot/ is volume-mounted — no rebuild needed)
docker compose restart bot

# Stop everything
docker compose down
```

**Services started:**
- `bot` — Trading bot (Python)
- `postgres` — PostgreSQL database
- `redis` — Redis pub/sub
- `webui-backend` — FastAPI dashboard backend
- `webui-frontend` — React dashboard (nginx)

### Verify Deployment

```bash
docker compose ps
```

Expected output:
```
NAME                     STATUS
traderagent-bot          Up (healthy)
traderagent-postgres     Up (healthy)
traderagent-redis        Up (healthy)
```

### Pre-deployment Validation

```bash
# Validate configuration and credentials
python scripts/validate_demo.py

# Security audit
python -c "
from bot.utils.security_audit import SecurityAuditor
r = SecurityAuditor().run_full_audit()
print(r.summary())
"
```

---

## Monitoring

### View Logs

**Real-time logs:**
```bash
docker compose logs -f bot
```

**Last 100 lines:**
```bash
docker compose logs --tail=100 bot
```

**Search for errors:**
```bash
docker compose logs bot 2>&1 | grep '"level":"error"'
```

**Search for warnings:**
```bash
docker compose logs bot 2>&1 | grep '"level":"warning"'
```

### Telegram Bot Commands

Once deployed, use Telegram to manage your bot:

**Control Commands:**
- `/start` — Show help and available commands
- `/list` — List all configured bots
- `/status [bot_name]` — Show bot status and positions
- `/start_bot <name>` — Start a trading bot
- `/stop_bot <name>` — Stop a trading bot
- `/pause <name>` — Pause trading
- `/resume <name>` — Resume trading

**Monitoring Commands:**
- `/balance <name>` — View current balance
- `/orders <name>` — View open orders
- `/pnl <name>` — View profit and loss

### Health Checks

```bash
docker compose exec postgres pg_isready
docker compose exec redis redis-cli ping
docker compose ps
```

---

## Maintenance

### Update Bot

```bash
git pull
docker compose restart bot   # Volume-mounted bot/ — no rebuild needed
# If dependencies changed:
docker compose build bot && docker compose up -d bot
```

### Sync Code to Remote Server

```bash
tar czf /tmp/sync.tar.gz bot/ configs/ scripts/
scp /tmp/sync.tar.gz user@server:/tmp/
ssh user@server "cd /home/user/TRADERAGENT && tar xzf /tmp/sync.tar.gz && docker compose restart bot"
```

### Backup Database

Automated daily backups use `scripts/backup_db.sh`.

**Manual backup:**
```bash
./scripts/backup_db.sh
```

**Set up daily cron job (recommended):**
```bash
# Edit crontab
crontab -e

# Add daily backup at 03:00 UTC
0 3 * * * /home/ai-agent/TRADERAGENT/scripts/backup_db.sh >> /home/ai-agent/TRADERAGENT/logs/backup.log 2>&1
```

**Backup settings (via environment variables or `.env`):**
- `BACKUP_DIR` — backup destination (default: `./backups`)
- `BACKUP_RETAIN_DAYS` — local retention (default: 7 days)
- Telegram alerts on failure (uses `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_CHAT_IDS`)

**Restore from backup:**
```bash
# List available backups
ls -lh backups/

# Restore (interactive confirmation required)
./scripts/backup_db.sh --restore backups/traderagent_20260224_030000.sql.gz
```

> **Warning:** Restore drops and recreates the database. Stop the bot first:
> `docker compose stop bot`

**Backup verification:**
```bash
# Check backup contents without restoring
gunzip -c backups/traderagent_20260224_030000.sql.gz | head -20
```

### Reset Bot State

To make a bot start fresh (forget all saved orders and positions):
```bash
# Via Telegram: /reset_state <bot_name>
# Or directly:
docker compose exec postgres psql -U traderagent -c "DELETE FROM bot_state_snapshots WHERE bot_name='demo_btc_hybrid';"
docker compose restart bot
```

---

## Security Best Practices

### 1. Environment Security

- **Never commit** `.env` or API keys to git
- Use **strong passwords** for database
- Rotate **encryption keys** periodically
- Keep **Docker images updated**

### 2. API Key Security

- Use **API key restrictions** on Bybit:
  - Restrict to Contract Trading (no withdrawals)
  - Whitelist server IP if possible
- Store keys **encrypted** in database (never in config files)
- Use **separate keys** for demo/production

### 3. Network Security

- Use **firewall** to restrict access (only allow your IP for SSH)
- **Disable** unnecessary ports
- The Web UI dashboard runs on port 3000 — restrict access or use VPN

### 4. Operational Security

- Start with **demo/dry_run** before using real funds
- Start with **small amounts**
- Monitor **closely** in first days
- Set **stop-loss limits** (`max_daily_loss` in config)
- Enable **Telegram notifications** (`notifications.enabled: true`)

### 5. Regular Maintenance

- **Update** dependencies regularly
- **Backup** database daily (`scripts/backup_db.sh` via cron)
- **Review** logs daily: `docker compose logs --tail=200 bot`
- **Monitor** system resources: `docker stats`

---

## Troubleshooting

See [v2/TROUBLESHOOTING.md](v2/TROUBLESHOOTING.md) for detailed troubleshooting guide.

**Quick checks:**
```bash
# Bot won't start
docker compose logs bot | tail -50

# Database connection
docker compose exec postgres psql -U traderagent -c "SELECT 1;"

# Redis connection
docker compose exec redis redis-cli ping

# Check bot state in DB
docker compose exec postgres psql -U traderagent -c "SELECT bot_name, saved_at FROM bot_state_snapshots;"
```

---

## Support

- **GitHub Issues**: https://github.com/alekseymavai/TRADERAGENT/issues
- **Logs**: Always include logs when reporting issues
- **Session History**: `docs/SESSION_CONTEXT.md` — detailed log of all changes

---

## Disclaimer

**⚠️ IMPORTANT:** This bot is for educational purposes. Trading cryptocurrencies involves substantial risk of loss. Always:

- Start with demo/paper trading
- Test thoroughly before using real funds
- Never invest more than you can afford to lose
- Monitor the bot regularly
- Understand the strategies being used

The authors are not responsible for any financial losses incurred through use of this software.

---

Mozilla Public License 2.0
