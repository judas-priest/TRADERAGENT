# TRADERAGENT Monitoring Stack

Complete monitoring solution for the TRADERAGENT trading bot using Prometheus and Grafana.

## Overview

The monitoring stack provides:

- **Metrics Collection**: Prometheus scrapes metrics from bot, database, Redis, and system
- **Visualization**: Grafana dashboards for real-time monitoring
- **Alerting**: Automated alerts for critical events
- **Historical Data**: 30-day metric retention

## Architecture

```
┌─────────────┐
│   Grafana   │ ← User Interface (Port 3000)
└──────┬──────┘
       │
┌──────▼──────┐
│ Prometheus  │ ← Metrics Storage (Port 9090)
└──────┬──────┘
       │
       ├─► Bot Exporter (Port 9100)      - Trading metrics
       ├─► Node Exporter (Port 9101)     - System metrics
       ├─► Postgres Exporter (Port 9102) - Database metrics
       ├─► Redis Exporter (Port 9103)    - Cache metrics
       └─► AlertManager (Port 9093)      - Alert management
```

## Quick Start

### 1. Start Monitoring Stack

```bash
# Start main services first
docker-compose up -d

# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d
```

### 2. Access Dashboards

**Grafana UI:**
- URL: http://localhost:3000
- Default user: `admin`
- Default password: `admin` (change on first login)

**Prometheus UI:**
- URL: http://localhost:9090

**AlertManager UI:**
- URL: http://localhost:9093

### 3. Import Dashboards

Dashboards are automatically provisioned from `monitoring/grafana/dashboards/`:

1. **Trading Bot Dashboard**: Main bot performance metrics
2. **System Resources**: CPU, memory, disk, network
3. **Database Performance**: PostgreSQL metrics
4. **Redis Performance**: Cache metrics

## Metrics Overview

### Bot Metrics

#### Trading Performance
- `bot_portfolio_value_usdt` - Total portfolio value in USDT
- `bot_portfolio_return_percent` - Total return percentage
- `bot_portfolio_drawdown_percent` - Current drawdown percentage
- `bot_total_trades` - Total number of trades executed
- `bot_winning_trades` - Number of profitable trades
- `bot_losing_trades` - Number of losing trades
- `bot_win_rate_percent` - Win rate percentage

#### Orders
- `bot_open_orders` - Number of currently open orders
- `bot_total_orders_total` - Total orders created (counter)
- `bot_failed_orders_total` - Failed orders (counter)
- `bot_canceled_orders_total` - Canceled orders (counter)

#### Exchange API
- `bot_api_requests_total` - Total API requests (counter)
- `bot_api_request_duration_seconds` - API request latency histogram
- `bot_api_errors_total` - API errors (counter)
- `bot_api_rate_limit_remaining` - Remaining API calls before rate limit

#### Strategy Metrics
- `bot_grid_levels_active` - Active grid levels (grid strategy)
- `bot_dca_steps_active` - Active DCA steps (DCA strategy)
- `bot_position_size_base` - Position size in base currency
- `bot_position_size_quote` - Position size in quote currency

#### System Health
- `bot_uptime_seconds` - Bot uptime in seconds
- `bot_errors_total` - Total errors (counter)
- `bot_last_trade_timestamp` - Unix timestamp of last trade

### System Metrics (Node Exporter)

- CPU usage, load average
- Memory usage, swap usage
- Disk I/O, disk space
- Network traffic
- System uptime

### Database Metrics (Postgres Exporter)

- Active connections
- Query performance
- Database size
- Transaction rate
- Lock statistics

### Redis Metrics

- Memory usage
- Connected clients
- Operations per second
- Hit/miss ratio
- Key statistics

## Alerts

### Critical Alerts (Immediate Action Required)

1. **BotDown**: Trading bot is not running
2. **CriticalDrawdown**: Portfolio drawdown > 20%
3. **DatabaseDown**: Database is unavailable
4. **RedisDown**: Redis cache is unavailable

### Warning Alerts (Investigation Needed)

1. **HighErrorRate**: Elevated error rate detected
2. **LargeDrawdown**: Portfolio drawdown > 10%
3. **HighOrderFailureRate**: Many orders failing
4. **HighMemoryUsage**: System memory > 90%
5. **HighCPUUsage**: CPU usage > 80%
6. **DiskSpaceLow**: Disk space < 10%

### Info Alerts (For Awareness)

1. **NoRecentTrades**: No trades in last hour
2. **RateLimitApproaching**: API rate limit nearly reached

## Grafana Dashboards

### 1. Trading Bot Overview

Key metrics at a glance:
- Portfolio value and return
- Win rate and trade statistics
- Open orders and positions
- Recent trades timeline

### 2. Trading Performance

Detailed performance analysis:
- Equity curve over time
- Profit/loss by day, week, month
- Trade distribution
- Drawdown chart
- Sharpe ratio calculation

### 3. System Health

System resource monitoring:
- CPU usage by core
- Memory usage breakdown
- Disk I/O and space
- Network traffic
- Process statistics

### 4. Database Performance

PostgreSQL monitoring:
- Query performance
- Connection pool usage
- Table sizes
- Index efficiency
- Slow query log

### 5. API Performance

Exchange API monitoring:
- Request rate
- Latency percentiles (p50, p95, p99)
- Error rate
- Rate limit status
- Endpoint breakdown

## Alert Configuration

### Telegram Notifications

Configure Telegram alerts in `monitoring/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'telegram'
    telegram_configs:
      - bot_token: 'YOUR_BOT_TOKEN'
        chat_id: YOUR_CHAT_ID
        message: |
          {{ range .Alerts }}
          🚨 {{ .Labels.severity | toUpper }}
          {{ .Annotations.summary }}
          {{ .Annotations.description }}
          {{ end }}
```

### Email Notifications

```yaml
receivers:
  - name: 'email'
    email_configs:
      - to: 'your-email@example.com'
        from: 'alerts@traderagent.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'your-email@gmail.com'
        auth_password: 'your-app-password'
```

### Slack Notifications

```yaml
receivers:
  - name: 'slack'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#trading-alerts'
        title: 'TRADERAGENT Alert'
```

## Custom Metrics

### Adding Bot Metrics

In your bot code, expose metrics using Prometheus client:

```python
from prometheus_client import Counter, Gauge, Histogram

# Define metrics
trades_total = Counter('bot_trades_total', 'Total trades', ['side', 'strategy'])
portfolio_value = Gauge('bot_portfolio_value_usdt', 'Portfolio value in USDT')
api_latency = Histogram('bot_api_request_duration_seconds', 'API request duration', ['endpoint'])

# Update metrics
trades_total.labels(side='buy', strategy='grid').inc()
portfolio_value.set(10500.50)
api_latency.labels(endpoint='create_order').observe(0.234)
```

### Exposing Metrics Endpoint

```python
from prometheus_client import start_http_server

# Start metrics server on port 9100
start_http_server(9100)
```

## Troubleshooting

### Grafana Can't Connect to Prometheus

**Check**:
```bash
docker-compose -f docker-compose.monitoring.yml logs grafana
docker-compose -f docker-compose.monitoring.yml logs prometheus
```

**Solution**:
- Ensure Prometheus is running: `curl http://localhost:9090/-/healthy`
- Check datasource configuration in Grafana

### No Metrics Appearing

**Check Targets in Prometheus**:
1. Go to http://localhost:9090/targets
2. Verify all targets show "UP" status
3. Check firewall rules if targets are down

**Check Exporter Logs**:
```bash
docker-compose -f docker-compose.monitoring.yml logs bot-exporter
```

### High Resource Usage

**Reduce Prometheus Retention**:
```yaml
# In docker-compose.monitoring.yml
command:
  - '--storage.tsdb.retention.time=7d'  # Reduce from 30d to 7d
```

**Reduce Scrape Frequency**:
```yaml
# In monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 30s  # Increase from 15s
```

### Alerts Not Firing

**Check AlertManager**:
```bash
# View AlertManager status
curl http://localhost:9093/api/v2/status

# Check alert rules in Prometheus
# Go to http://localhost:9090/alerts
```

## Backup and Restore

### Backup Grafana Dashboards

```bash
# Export all dashboards
docker-compose -f docker-compose.monitoring.yml exec grafana \
  curl -X GET http://localhost:3000/api/search | \
  jq '.[] | .uid' | \
  xargs -I {} docker-compose -f docker-compose.monitoring.yml exec grafana \
  curl -X GET http://localhost:3000/api/dashboards/uid/{} > backup-{}.json
```

### Backup Prometheus Data

```bash
# Stop Prometheus
docker-compose -f docker-compose.monitoring.yml stop prometheus

# Backup data directory
docker cp traderagent-prometheus:/prometheus ./prometheus-backup

# Restart Prometheus
docker-compose -f docker-compose.monitoring.yml start prometheus
```

### Restore from Backup

```bash
# Stop Prometheus
docker-compose -f docker-compose.monitoring.yml stop prometheus

# Restore data
docker cp ./prometheus-backup traderagent-prometheus:/prometheus

# Start Prometheus
docker-compose -f docker-compose.monitoring.yml start prometheus
```

## Performance Tuning

### Optimize Prometheus

```yaml
# In monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 30s        # Less frequent scraping
  evaluation_interval: 30s    # Less frequent rule evaluation

# Reduce metric retention
# In docker-compose.monitoring.yml:
command:
  - '--storage.tsdb.retention.time=7d'
  - '--storage.tsdb.retention.size=10GB'  # Limit storage size
```

### Optimize Grafana

```yaml
# In docker-compose.monitoring.yml grafana environment:
- GF_METRICS_ENABLED=false              # Disable Grafana's own metrics
- GF_ANALYTICS_REPORTING_ENABLED=false  # Disable analytics
- GF_ANALYTICS_CHECK_FOR_UPDATES=false  # Disable update checks
```

## Security Best Practices

1. **Change Default Passwords**
   ```bash
   # Change Grafana admin password immediately after first login
   ```

2. **Enable Authentication**
   - Use strong passwords
   - Enable OAuth if possible
   - Restrict network access

3. **Use HTTPS**
   - Configure reverse proxy (nginx) with SSL
   - Use Let's Encrypt for certificates

4. **Limit Exposed Ports**
   ```yaml
   # Only expose Grafana externally
   ports:
     - "127.0.0.1:9090:9090"  # Prometheus internal only
     - "0.0.0.0:3000:3000"     # Grafana public
   ```

5. **Regular Updates**
   ```bash
   # Update monitoring stack images
   docker-compose -f docker-compose.monitoring.yml pull
   docker-compose -f docker-compose.monitoring.yml up -d
   ```

## Further Reading

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [AlertManager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)
- [Node Exporter Metrics](https://github.com/prometheus/node_exporter#enabled-by-default)
