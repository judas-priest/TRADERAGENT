# TRADERAGENT Bot - Deployment Guide

Complete guide for deploying the TRADERAGENT trading bot to production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)

## Prerequisites

### Required Software

- **Docker** (>= 20.10) and **Docker Compose** (>= 2.0)
- **Git** for cloning the repository
- **Python 3.11+** (for local development)

### Required Accounts

1. **Exchange Account**: Binance, Bybit, OKX, or other CCXT-supported exchange
2. **Telegram Bot**: Create via [@BotFather](https://t.me/botfather)
3. **Server**: VPS/VDS with at least 2GB RAM and 10GB storage

### System Requirements

- **Minimum**: 2 CPU cores, 2GB RAM, 10GB storage
- **Recommended**: 4 CPU cores, 4GB RAM, 20GB storage
- **Operating System**: Ubuntu 20.04/22.04, Debian 11+, or any Linux with Docker support

## Quick Start

For experienced users who want to deploy quickly:

```bash
# 1. Clone repository
git clone https://github.com/alekseymavai/TRADERAGENT.git
cd TRADERAGENT

# 2. Configure environment
cp .env.example .env
nano .env  # Edit with your values

# 3. Configure bot
cp configs/example.yaml configs/production.yaml
nano configs/production.yaml  # Edit with your trading parameters

# 4. Deploy
chmod +x deploy.sh
./deploy.sh
```

## Detailed Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/alekseymavai/TRADERAGENT.git
cd TRADERAGENT
```

### Step 2: Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow instructions to create your bot
4. Save the **bot token** provided by BotFather
5. Get your **chat ID** by sending a message to [@userinfobot](https://t.me/userinfobot)

### Step 3: Environment Configuration

Create `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```bash
nano .env
```

**Required Variables:**

```env
# Database
DB_USER=traderagent
DB_PASSWORD=your_secure_password_here
DB_NAME=traderagent

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather
TELEGRAM_ALLOWED_CHAT_IDS=your_chat_id_from_userinfobot

# Security - Generate with: python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
ENCRYPTION_KEY=your_generated_base64_key_here

# Logging
LOG_LEVEL=INFO
```

**Generate Encryption Key:**

```bash
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
```

### Step 4: Bot Configuration

Create bot configuration file:

```bash
cp configs/example.yaml configs/production.yaml
nano configs/production.yaml
```

**Key Configuration Sections:**

```yaml
# Database URL (automatically set in Docker)
database_url: postgresql+asyncpg://user:pass@postgres:5432/traderagent

# Logging
log_level: INFO

# Encryption key (from .env)
encryption_key: ${ENCRYPTION_KEY}

# Bot configurations
bots:
  - name: my_grid_bot
    symbol: BTC/USDT
    strategy: grid  # or 'dca' or 'hybrid'

    exchange:
      exchange_id: binance
      credentials_name: binance_main
      sandbox: true  # Start with testnet!

    grid:
      enabled: true
      upper_price: "50000"
      lower_price: "40000"
      grid_levels: 10
      amount_per_grid: "100"
      profit_per_grid: "0.01"

    risk_management:
      max_position_size: "10000"
      stop_loss_percentage: "0.15"
      min_order_size: "10"

    dry_run: true  # Start in simulation mode!
    auto_start: false  # Manual start recommended
```

**⚠️ Important:** Always start with:
- `sandbox: true` (testnet)
- `dry_run: true` (simulation)
- Small amounts

### Step 5: Exchange API Keys

API keys should be stored encrypted in the database. For initial setup:

1. Ensure `encryption_key` is set in `.env`
2. Use the bot's credential management (after deployment)
3. Or manually add to database with encryption

**Never commit API keys to version control!**

## Deployment

### Automatic Deployment

Use the deployment script:

```bash
chmod +x deploy.sh
./deploy.sh
```

The script will:
1. Check prerequisites (Docker, Docker Compose)
2. Verify environment configuration
3. Build Docker images
4. Start database and Redis
5. Run database migrations
6. Start the trading bot
7. Show status and logs

### Manual Deployment

If you prefer manual control:

```bash
# Build images
docker-compose build

# Start database and Redis
docker-compose up -d postgres redis

# Wait for services to be healthy
sleep 10

# Run migrations
docker-compose run --rm migrations

# Start bot
docker-compose up -d bot

# View logs
docker-compose logs -f bot
```

### Verify Deployment

Check that all services are running:

```bash
docker-compose ps
```

Expected output:
```
NAME                    STATUS
traderagent-bot         Up (healthy)
traderagent-postgres    Up (healthy)
traderagent-redis       Up (healthy)
```

View bot logs:

```bash
docker-compose logs -f bot
```

## Monitoring

### View Logs

**Real-time logs:**
```bash
docker-compose logs -f bot
```

**Last 100 lines:**
```bash
docker-compose logs --tail=100 bot
```

**Specific service:**
```bash
docker-compose logs -f postgres
docker-compose logs -f redis
```

### Telegram Bot Commands

Once deployed, use Telegram to manage your bot:

**Control Commands:**
- `/start` - Show help and available commands
- `/list` - List all configured bots
- `/status [bot_name]` - Show bot status
- `/start_bot <name>` - Start a trading bot
- `/stop_bot <name>` - Stop a trading bot
- `/pause <name>` - Pause trading
- `/resume <name>` - Resume trading

**Monitoring Commands:**
- `/balance <name>` - View current balance
- `/orders <name>` - View open orders
- `/pnl <name>` - View profit and loss

### Health Checks

**Database health:**
```bash
docker-compose exec postgres pg_isready
```

**Redis health:**
```bash
docker-compose exec redis redis-cli ping
```

**Bot health:**
```bash
docker-compose exec bot python -c "from bot.database.manager import DatabaseManager; import asyncio; asyncio.run(DatabaseManager('${DATABASE_URL}').health_check())"
```

### System Monitoring

**Resource usage:**
```bash
docker stats
```

**Disk usage:**
```bash
du -sh /var/lib/docker/volumes
```

## Maintenance

### Update Bot

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d

# Run new migrations if any
docker-compose run --rm migrations
```

### Backup Database

```bash
# Create backup
docker-compose exec postgres pg_dump -U traderagent traderagent > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker-compose exec -T postgres psql -U traderagent traderagent < backup_20240101_120000.sql
```

### Stop Bot

```bash
# Stop all services
docker-compose down

# Stop but keep data
docker-compose stop

# Stop and remove all data (CAREFUL!)
docker-compose down -v
```

## Troubleshooting

### Bot Won't Start

**Check logs:**
```bash
docker-compose logs bot
```

**Common issues:**
- Missing environment variables: Check `.env` file
- Database connection: Ensure postgres is healthy
- Configuration errors: Validate `production.yaml`

### Database Connection Issues

```bash
# Check database is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U traderagent -d traderagent -c "SELECT 1;"
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
```

### Telegram Bot Not Responding

1. Verify `TELEGRAM_BOT_TOKEN` in `.env`
2. Check `TELEGRAM_ALLOWED_CHAT_IDS` includes your chat ID
3. Ensure bot is running: `docker-compose ps bot`
4. Check for errors in logs: `docker-compose logs bot | grep telegram`

### Exchange API Errors

- **Rate limit**: Reduce trading frequency
- **Insufficient balance**: Check account balance
- **Invalid API keys**: Verify credentials in configuration
- **Sandbox mode**: Ensure `sandbox: true` for testing

## Security Best Practices

### 1. Environment Security

- **Never commit** `.env` or API keys to git
- Use **strong passwords** for database
- Rotate **encryption keys** periodically
- Keep **Docker images updated**

### 2. Network Security

- Use **firewall** to restrict access
- **Disable** unnecessary ports
- Use **VPN** or **SSH tunnel** for remote access
- Enable **HTTPS** if exposing web interface

### 3. API Key Security

- Use **API key restrictions** on exchange:
  - Restrict to trading only (no withdrawals)
  - Whitelist server IP if possible
  - Set maximum order sizes
- Store keys **encrypted** in database
- Use **separate keys** for production/testing

### 4. Operational Security

- Start with **testnet/sandbox**
- Use **dry_run: true** for testing
- Start with **small amounts**
- Monitor **closely** in first days
- Set **stop-loss limits**
- Enable **Telegram notifications**

### 5. Regular Maintenance

- **Update** dependencies regularly
- **Backup** database weekly
- **Review** logs daily
- **Monitor** system resources
- **Test** recovery procedures

## Advanced Configuration

### Custom Redis Configuration

Edit `docker-compose.yml`:

```yaml
redis:
  command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

### Multiple Bot Instances

Add multiple bot configurations in `production.yaml`:

```yaml
bots:
  - name: btc_grid
    symbol: BTC/USDT
    strategy: grid
    # ... config ...

  - name: eth_dca
    symbol: ETH/USDT
    strategy: dca
    # ... config ...
```

### External Database

To use external PostgreSQL:

```yaml
# In docker-compose.yml, remove postgres service
# Update bot environment:
environment:
  DATABASE_URL: postgresql+asyncpg://user:pass@external-host:5432/db
```

## Support

For issues and questions:

- **GitHub Issues**: https://github.com/alekseymavai/TRADERAGENT/issues
- **Documentation**: See README.md and bot/README.md
- **Logs**: Always include logs when reporting issues

## License

Mozilla Public License 2.0

## Disclaimer

**⚠️ IMPORTANT:** This bot is for educational purposes. Trading cryptocurrencies involves substantial risk of loss. Always:

- Start with testnet/sandbox
- Test thoroughly before using real funds
- Never invest more than you can afford to lose
- Monitor the bot regularly
- Understand the strategies being used

The authors are not responsible for any financial losses incurred through use of this software.
