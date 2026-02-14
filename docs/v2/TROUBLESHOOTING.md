# TRADERAGENT v2.0 Troubleshooting Guide

## Connection Issues

### ByBit API Authentication Failed

**Symptom**: `AuthenticationError: Invalid API key`

**Solutions**:
1. Verify API key/secret are correct in `.env`
2. For testnet: use `testnet=True` in client initialization
3. For demo trading: the URL is `https://api-demo.bybit.com` (handled automatically)
4. Check that API key permissions include trading
5. Ensure system clock is synchronized (API uses timestamp-based signatures with 10s window)

### Rate Limit Exceeded

**Symptom**: `RateLimitError: 429 Too Many Requests`

**Solutions**:
1. The client has built-in retry with exponential backoff (tenacity)
2. Reduce polling frequency in strategy config
3. ByBit rate limits: 120 requests/min for order endpoints, 600/min for market data

### Network Timeout

**Symptom**: `NetworkError: Connection timeout`

**Solutions**:
1. Check internet connectivity
2. Verify ByBit API status at https://status.bybit.com
3. The client retries automatically up to 3 times
4. Consider increasing timeout in aiohttp session config

---

## Strategy Issues

### SMC Strategy Not Generating Signals

**Possible causes**:
1. **Insufficient data**: SMC requires 4 timeframes (D1, H4, H1, M15). Ensure all are loaded.
2. **No confluence zones**: Market may not have active Order Blocks or Fair Value Gaps
3. **Volume filter**: If `require_volume_confirmation=True`, low volume periods are filtered
4. **Risk:Reward too high**: Lower `min_risk_reward` from 2.5 to 2.0 if signals are rare

### Grid Strategy Accumulating Losses

**Possible causes**:
1. **Trending market**: Grid works best in ranges. Consider switching to SMC or Trend-Follower
2. **Range too narrow**: Increase `grid_range_pct` to capture wider oscillations
3. **Too many levels**: Reduce `num_levels` to concentrate capital

### DCA Safety Orders Not Triggering

**Possible causes**:
1. **Price not dropping enough**: Safety orders require specific price deviation thresholds
2. **Max safety orders reached**: Check `max_safety_orders` limit
3. **Insufficient balance**: Each safety order needs available capital

---

## Database Issues

### SQLite Lock Errors

**Symptom**: `OperationalError: database is locked`

**Solutions**:
1. SQLite doesn't support concurrent writes. Switch to PostgreSQL for production:
   ```env
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/traderagent
   ```
2. For development, ensure only one bot process runs at a time

### Migration Errors

**Symptom**: Table schema mismatch after upgrade

**Solutions**:
1. For development: delete the SQLite file and restart (tables auto-create)
2. For production: use Alembic migrations:
   ```bash
   alembic upgrade head
   ```

---

## Telegram Bot Issues

### Bot Not Responding

**Possible causes**:
1. **Invalid token**: Verify `TELEGRAM_BOT_TOKEN` is correct
2. **Chat not authorized**: Ensure your chat ID is in `allowed_chat_ids`
3. **Bot not started**: The event loop must be running for the bot to process messages
4. **Webhook conflict**: If using webhooks elsewhere, clear them: `bot.delete_webhook()`

### No Event Notifications

**Possible causes**:
1. **Redis not running**: Start Redis: `redis-server`
2. **Wrong Redis URL**: Verify `REDIS_URL` in `.env`
3. **Event listener not started**: Ensure `TelegramBot.run()` is called

---

## Capital Deployment Issues

### Cannot Advance Phase

**Symptom**: `RuntimeError: Cannot advance: Duration 2d < required 3d`

The `CapitalManager` enforces performance gates before scaling:

| Gate | Phase 1 | Phase 2 |
|------|---------|---------|
| Duration | 3 days | 7 days |
| Min trades | 5 | 20 |
| Win rate | 40% | 45% |
| Max drawdown | 5% | 10% |
| Net PnL | Positive | Positive |

Check which gates are blocking:
```python
decision = cm.evaluate_scaling()
print(decision.blockers)  # ['Duration 2d < required 3d', ...]
print(decision.reasons)   # ['Win rate gate passed (60.00%)', ...]
```

### Deployment Halted

**Symptom**: Phase shows `HALTED`

The system halts when critical errors occur or when manually stopped. To resume:
1. Investigate the halt reason in logs
2. Fix underlying issues
3. Restart from Phase 1: `cm.start_phase_1()`

---

## Testing Issues

### pdbpp/fancycompleter Error

**Symptom**: `TypeError` related to `fancycompleter` or `pdb`

**Solution**: Always run pytest with `-p no:pdb`:
```bash
python -m pytest -p no:pdb -v
```

### Testnet Tests Skipped

**Symptom**: All testnet tests show `SKIPPED`

**Solution**: Set testnet credentials:
```bash
export BYBIT_TESTNET_API_KEY=your_key
export BYBIT_TESTNET_API_SECRET=your_secret
python -m pytest tests/testnet/test_testnet_validation.py -p no:pdb -v
```

### Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'bot'`

**Solution**: Run from project root or install in editable mode:
```bash
pip install -e .
```

---

## Production Readiness Checks

Before deploying to production, run the full audit:

```bash
# Security audit
python -c "
from bot.utils.security_audit import SecurityAuditor
report = SecurityAuditor().run_full_audit()
print(report.summary())
for f in report.critical_failures:
    print(f'CRITICAL: {f.message}')
"

# Config validation
python -c "
from bot.utils.config_validator import ConfigValidator
report = ConfigValidator().run_full_validation()
print(report.summary())
for f in report.failures:
    print(f'FAIL: {f.message}')
"
```

Both should show `overall_status: PASS` before going live.

---

## Getting Help

- GitHub Issues: https://github.com/alekseymavai/TRADERAGENT/issues
- Check logs: structured logging with `structlog` — search for `error` severity
- Enable debug mode: `DEBUG=true` in `.env` (disable for production)
