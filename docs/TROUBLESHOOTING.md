# TRADERAGENT - Troubleshooting Guide

Comprehensive troubleshooting guide for common issues and their solutions.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Configuration Issues](#configuration-issues)
- [Database Issues](#database-issues)
- [Exchange Connection Issues](#exchange-connection-issues)
- [Trading Issues](#trading-issues)
- [Performance Issues](#performance-issues)
- [Monitoring Issues](#monitoring-issues)
- [Docker Issues](#docker-issues)
- [Logging and Debugging](#logging-and-debugging)

---

## Installation Issues

### Python Version Mismatch

**Problem:** `ERROR: Python 3.10 or higher required`

**Solutions:**
```bash
# Check Python version
python --version
python3 --version
python3.11 --version

# Install Python 3.11 (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv python3-pip

# Create venv with specific Python version
python3.11 -m venv venv
source venv/bin/activate
```

### Dependency Installation Failures

**Problem:** `pip install` fails with compilation errors

**Solutions:**
```bash
# Install build dependencies (Ubuntu/Debian)
sudo apt-get install build-essential python3-dev libpq-dev

# Upgrade pip, setuptools, wheel
pip install --upgrade pip setuptools wheel

# Install with verbose output to see errors
pip install -v -r requirements.txt

# Try installing problematic packages individually
pip install ccxt
pip install sqlalchemy
pip install asyncpg
```

### Permission Denied Errors

**Problem:** `PermissionError: [Errno 13]`

**Solutions:**
```bash
# Don't use sudo with pip in venv
# Instead, ensure venv is activated
source venv/bin/activate

# Check file permissions
ls -la

# Fix permissions if needed
chmod +x deploy.sh
chmod 755 bot/
```

---

## Configuration Issues

### Invalid YAML Syntax

**Problem:** `yaml.scanner.ScannerError: mapping values are not allowed here`

**Solutions:**
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('configs/production.yaml'))"

# Common YAML mistakes:
# 1. Tabs instead of spaces (use spaces only)
# 2. Missing colons
# 3. Incorrect indentation
# 4. Unquoted strings with special characters

# Use YAML linter
pip install yamllint
yamllint configs/production.yaml
```

### Environment Variables Not Loaded

**Problem:** Bot can't find environment variables

**Solutions:**
```bash
# Check .env file exists
ls -la .env

# Check .env file is in correct location (project root)
pwd
cat .env

# Load .env manually for testing
export $(cat .env | xargs)

# Check if variables are loaded
echo $TELEGRAM_BOT_TOKEN

# In Docker, ensure .env is in same directory as docker-compose.yml
```

### Encryption Key Issues

**Problem:** `Failed to decrypt API credentials` or `Invalid encryption key`

**Solutions:**
```bash
# Generate new encryption key
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"

# Add to .env
echo "ENCRYPTION_KEY=your_generated_key" >> .env

# Re-encrypt credentials
python -m bot.cli re-encrypt-credentials --old-key OLD_KEY --new-key NEW_KEY

# If key is lost, credentials must be re-added
python -m bot.cli delete-credentials --name binance_main
python -m bot.cli add-credentials --name binance_main --exchange binance
```

---

## Database Issues

### Database Connection Failed

**Problem:** `could not connect to server: Connection refused`

**Solutions:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Start PostgreSQL
sudo systemctl start postgresql

# In Docker, check container is running
docker ps | grep postgres
docker-compose ps

# Check database URL is correct
echo $DATABASE_URL

# Test connection
psql postgresql://user:password@localhost/traderagent

# Common issues:
# 1. Wrong host (use 'postgres' in Docker, 'localhost' outside)
# 2. Wrong port (default: 5432)
# 3. Wrong credentials
# 4. Database doesn't exist
```

### Database Doesn't Exist

**Problem:** `database "traderagent" does not exist`

**Solutions:**
```bash
# Create database
sudo -u postgres psql
CREATE DATABASE traderagent;
CREATE USER traderagent WITH ENCRYPTED PASSWORD 'yourpassword';
GRANT ALL PRIVILEGES ON DATABASE traderagent TO traderagent;
\q

# In Docker
docker-compose up -d postgres
docker-compose exec postgres psql -U traderagent -d traderagent

# Run migrations
alembic upgrade head
```

### Migration Issues

**Problem:** `alembic.util.exc.CommandError: Can't locate revision identified by`

**Solutions:**
```bash
# Check current migration version
alembic current

# Show migration history
alembic history

# Reset to base (WARNING: drops all tables)
alembic downgrade base

# Upgrade to latest
alembic upgrade head

# If migrations are corrupted, recreate database:
dropdb traderagent
createdb traderagent
alembic upgrade head
```

### Connection Pool Exhausted

**Problem:** `TimeoutError: QueuePool limit of size X overflow Y reached`

**Solutions:**
```yaml
# Increase pool size in config
database_pool_size: 10  # Default: 5
database_max_overflow: 20  # Default: 10

# Check for connection leaks
# Ensure all database sessions are properly closed

# Monitor connection count
SELECT count(*) FROM pg_stat_activity WHERE datname = 'traderagent';
```

---

## Exchange Connection Issues

### API Key Authentication Failed

**Problem:** `AuthenticationError: Invalid API key`

**Solutions:**
```bash
# Verify API key and secret
python -m bot.cli test-credentials --name binance_main

# Common issues:
# 1. Wrong API key or secret
# 2. API key not activated
# 3. API key permissions insufficient (needs spot trading)
# 4. IP whitelist enabled (add your server IP)
# 5. Using mainnet keys with testnet or vice versa

# Re-add credentials
python -m bot.cli delete-credentials --name binance_main
python -m bot.cli add-credentials \
    --name binance_main \
    --exchange binance \
    --api-key YOUR_API_KEY \
    --api-secret YOUR_API_SECRET
```

### Rate Limit Exceeded

**Problem:** `RateLimitExceeded: binance 429 Too Many Requests`

**Solutions:**
```yaml
# Enable rate limiting in config
exchange:
  rate_limit: true

# Increase rate limit delay
exchange:
  rateLimit: 2000  # ms between requests

# Reduce bot activity
grid:
  grid_levels: 5  # Fewer levels = fewer orders

# Use WebSocket for price updates instead of polling
```

### Network Timeout Errors

**Problem:** `RequestTimeout: binance GET https://api.binance.com/... timed out`

**Solutions:**
```yaml
# Increase timeout
exchange:
  timeout: 60000  # 60 seconds

# Check network connection
ping api.binance.com

# Try different DNS
# Google DNS: 8.8.8.8, 8.8.4.4
# Cloudflare DNS: 1.1.1.1, 1.0.0.1

# Check if exchange is accessible
curl https://api.binance.com/api/v3/ping

# Use VPN if exchange is blocked in your region
```

### Insufficient Balance

**Problem:** `InsufficientFunds: binance insufficient balance`

**Solutions:**
```bash
# Check account balance
python -m bot.cli get-balance --exchange binance_main

# Reduce order sizes
# amount_per_grid: "50"  # Instead of "100"

# Reduce grid levels
# grid_levels: 5  # Instead of 10

# Check if in spot wallet (not futures/margin)

# Transfer funds to spot wallet if needed
```

---

## Trading Issues

### Orders Not Being Placed

**Problem:** Bot starts but no orders are placed

**Diagnosis:**
```bash
# Check logs
tail -f logs/bot.log

# Check dry_run mode
grep "dry_run" configs/production.yaml

# Check bot status
python -m bot.cli bot-status --name btc_grid_bot
```

**Solutions:**
1. Ensure `dry_run: false` for real trading
2. Check `auto_start: true` or manually start bot
3. Verify price is within grid range
4. Check risk limits not exceeded
5. Verify sufficient balance

### Orders Getting Cancelled

**Problem:** Orders placed but immediately cancelled

**Solutions:**
```bash
# Check exchange logs
python -m bot.cli get-order-history --bot btc_grid_bot --limit 10

# Common causes:
# 1. Post-only order hit as taker
# 2. Price moved before order placed
# 3. Insufficient margin
# 4. Invalid price/quantity
# 5. Exchange rejected (check exchange status)
```

### Grid Not Rebalancing

**Problem:** Grid orders not replaced after fill

**Solutions:**
```bash
# Check grid engine logs
grep "GridEngine" logs/bot.log

# Verify WebSocket connection
grep "WebSocket" logs/bot.log

# Restart bot
python -m bot.cli restart-bot --name btc_grid_bot

# Check risk manager not blocking
grep "RiskManager" logs/bot.log
```

### DCA Not Triggering

**Problem:** Price dropped but DCA didn't trigger

**Solutions:**
```yaml
# Check trigger percentage
dca:
  trigger_percentage: "0.05"  # Must drop 5%

# Check if max_steps reached
# max_steps: 5  # Already at 5 steps?

# Check position size limit
risk_management:
  max_position_size: "10000"  # Limit reached?
```

---

## Performance Issues

### High CPU Usage

**Problem:** Bot using 100% CPU

**Solutions:**
```bash
# Check for infinite loops in logs
grep -i "error\|exception" logs/bot.log

# Reduce polling frequency
# Use WebSocket instead of REST polling

# Reduce grid levels
# grid_levels: 5  # Instead of 20

# Increase log level (less I/O)
# log_level: WARNING  # Instead of DEBUG
```

### High Memory Usage

**Problem:** Bot using excessive memory

**Solutions:**
```bash
# Check memory usage
docker stats  # For Docker
ps aux | grep python  # For native

# Reduce database connection pool
database_pool_size: 3  # Instead of 10

# Clear old data
python -m bot.cli cleanup-old-trades --days 90

# Restart bot periodically
# Add to crontab: 0 4 * * * docker-compose restart bot
```

### Slow Database Queries

**Problem:** Slow performance, database queries taking long

**Solutions:**
```sql
# Check slow queries
SELECT * FROM pg_stat_activity WHERE state = 'active' AND query_start < now() - interval '5 seconds';

# Add indexes
CREATE INDEX idx_orders_bot_id ON orders(bot_id);
CREATE INDEX idx_trades_timestamp ON trades(timestamp);

# Vacuum database
VACUUM ANALYZE;

# Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Monitoring Issues

### Prometheus Not Scraping

**Problem:** No metrics in Prometheus

**Solutions:**
```bash
# Check Prometheus targets
# Visit: http://localhost:9090/targets

# Check bot exporter is running
curl http://localhost:9100/metrics

# Check Prometheus config
docker-compose -f docker-compose.monitoring.yml exec prometheus cat /etc/prometheus/prometheus.yml

# Restart monitoring stack
docker-compose -f docker-compose.monitoring.yml restart
```

### Grafana Dashboards Not Loading

**Problem:** Grafana shows "No data"

**Solutions:**
```bash
# Check Grafana datasource
# Visit: http://localhost:3000/datasources

# Test Prometheus connection
curl http://localhost:9090/api/v1/query?query=up

# Check if bot is exporting metrics
curl http://localhost:9100/metrics | grep bot_

# Restart Grafana
docker-compose -f docker-compose.monitoring.yml restart grafana
```

### Alerts Not Firing

**Problem:** AlertManager not sending alerts

**Solutions:**
```bash
# Check AlertManager status
# Visit: http://localhost:9093

# Check alert rules in Prometheus
# Visit: http://localhost:9090/alerts

# Test alert configuration
docker-compose -f docker-compose.monitoring.yml exec prometheus promtool check rules /etc/prometheus/alerts.yml

# Check Telegram bot token
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
     -d "chat_id=${TELEGRAM_CHAT_ID}&text=Test"
```

---

## Docker Issues

### Container Won't Start

**Problem:** `docker-compose up` fails

**Solutions:**
```bash
# Check Docker is running
sudo systemctl status docker

# Check docker-compose.yml syntax
docker-compose config

# Check logs
docker-compose logs bot
docker-compose logs postgres
docker-compose logs redis

# Remove old containers
docker-compose down -v
docker-compose up -d

# Check port conflicts
netstat -tulpn | grep :5432  # PostgreSQL
netstat -tulpn | grep :6379  # Redis
netstat -tulpn | grep :3000  # Grafana
```

### Permission Denied in Container

**Problem:** `PermissionError` inside container

**Solutions:**
```dockerfile
# Check Dockerfile USER directive
# Ensure correct permissions

# Fix permissions on host
chmod -R 755 bot/
chown -R 1000:1000 bot/  # Default user in Docker

# Run container as root (temporary, for debugging only)
docker-compose run --user root bot /bin/bash
```

### Volume Mount Issues

**Problem:** Files not visible in container

**Solutions:**
```bash
# Check volume mounts
docker inspect <container_id> | grep Mounts -A 20

# Use absolute paths in docker-compose.yml
volumes:
  - /absolute/path/to/configs:/app/configs

# Check SELinux (if on Red Hat/CentOS)
sudo setsebool -P container_manage_cgroup 1
```

---

## Logging and Debugging

### Enable Debug Logging

```yaml
# In config file
log_level: DEBUG
log_to_file: true
log_to_console: true
```

```bash
# Or via environment variable
export LOG_LEVEL=DEBUG
```

### Common Log Patterns

**Finding errors:**
```bash
# Show errors only
grep -i "error" logs/bot.log

# Show with context
grep -i -A 5 -B 5 "error" logs/bot.log

# Count errors
grep -i "error" logs/bot.log | wc -l

# Show unique errors
grep -i "error" logs/bot.log | sort | uniq
```

**Finding specific bot activity:**
```bash
# Show grid activity
grep "GridEngine" logs/bot.log

# Show DCA activity
grep "DCAEngine" logs/bot.log

# Show risk manager activity
grep "RiskManager" logs/bot.log

# Show order activity
grep "Order" logs/bot.log
```

**Real-time monitoring:**
```bash
# Follow logs
tail -f logs/bot.log

# Follow with filtering
tail -f logs/bot.log | grep -i "error\|warning"

# Follow multiple logs
tail -f logs/bot.log logs/error.log
```

### Debug Mode Commands

```bash
# Test configuration
python -m bot.main --config configs/production.yaml --dry-run --debug

# Test exchange connection
python -m bot.cli test-exchange --exchange binance_main --debug

# Test strategy
python -m bot.cli test-strategy --config configs/production.yaml --bot btc_grid_bot --debug

# Show bot state
python -m bot.cli show-state --bot btc_grid_bot
```

### Interactive Debugging

```python
# Add to code for debugging
import ipdb; ipdb.set_trace()

# Or use built-in pdb
import pdb; pdb.set_trace()

# Run with Python debugger
python -m pdb bot/main.py
```

---

## Getting Help

If you can't resolve the issue:

1. **Check existing issues:** [GitHub Issues](https://github.com/alekseymavai/TRADERAGENT/issues)

2. **Create a new issue** with:
   - Clear description of the problem
   - Steps to reproduce
   - Configuration (remove sensitive data!)
   - Relevant log excerpts
   - System information:
     ```bash
     python --version
     docker --version
     uname -a
     ```

3. **Ask in discussions:** [GitHub Discussions](https://github.com/alekseymavai/TRADERAGENT/discussions)

4. **Provide diagnostic info:**
   ```bash
   # Generate diagnostic report
   python -m bot.cli diagnostics --output diagnostic-report.txt
   ```

---

## Related Documentation

- [CONFIGURATION.md](CONFIGURATION.md) - Configuration guide
- [FAQ.md](FAQ.md) - Frequently asked questions
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [TESTING.md](TESTING.md) - Testing guide
