# TRADERAGENT v2.0 Troubleshooting Guide

> **Обновлено:** 2026-02-23 — добавлены секции по Bybit Demo Trading, нормализации статусов ордеров и SMC-багам

---

## Connection Issues

### ByBit API Authentication Failed

**Symptom**: `AuthenticationError: Invalid API key`

**Solutions**:
1. Verify API key/secret are correct in `.env`
2. For testnet: use `testnet=True` in client initialization
3. For demo trading: the URL is `https://api-demo.bybit.com` (handled automatically when `sandbox: true`)
4. Check that API key permissions include trading
5. Ensure system clock is synchronized (API uses timestamp-based signatures with 10s window)

> ⚠️ **Demo vs Testnet**: `sandbox: true` in YAML config routes to `api-demo.bybit.com` via `ByBitDirectClient`. This is NOT the same as `testnet.bybit.com`. Demo uses production API keys; testnet requires separate keys.

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

### Grid: `grid_order_not_filled` Warning Loop

**Symptom**: Logs flooded with repeated warnings every ~2 seconds:
```
grid_order_not_filled order_id=xxx status=filled
```

**Root cause**: This was caused by `ByBitDirectClient` returning native Bybit status `"filled"` while the orchestrator compared against CCXT-normalized `"closed"`. **Fixed in commit `b477fbf`** — `_normalize_order_status()` now maps `"filled"` → `"closed"` at the source.

**If you see this on an old version**: Update to latest and restart the bot.

### SMC Strategy Not Generating Signals

**Possible causes**:
1. **Insufficient data**: SMC requires 4 timeframes (D1, H4, H1, M15). Ensure all are loaded.
2. **No confluence zones**: Market may not have active Order Blocks or Fair Value Gaps
3. **Volume filter**: If `require_volume_confirmation=True`, low volume periods are filtered
4. **Risk:Reward too high**: Lower `min_risk_reward` from 2.5 to 2.0 if signals are rare
5. **Wrong trend detection** *(old bug, fixed)*: `SMCStrategy.analyze_market()` returns `"current_trend"` key (a `TrendDirection` enum). The adapter now correctly reads this key and calls `.value.lower()` on the enum. If you forked before **commit `f06dc8c`**, apply the fix manually.

### SMC Signals Triggering Immediate TP (Stale Signals)

**Symptom**: SMC opens positions that immediately hit take profit. Logs show hundreds of profitable trades in `dry_run` mode that don't correspond to real market movements.

**Root cause**: SMC caches Order Block zones between analysis cycles (every 300 seconds). If the price moves significantly while the cache is stale, the signal's `entry_price` is far from current market price, and TP triggers on the very next price check.

**Fix** *(commit `f06dc8c`)*: A 2% staleness filter was added in `bot_orchestrator.py`:
```python
price_diff_pct = abs(signal.entry_price - self.current_price) / self.current_price
if price_diff_pct > Decimal("0.02"):
    logger.warning("smc_signal_stale", ...)
    signal = None
```

**If you see `smc_signal_stale` in logs**: This is normal — the bot is correctly rejecting stale signals. No action needed.

### Grid Strategy Accumulating Losses

**Possible causes**:
1. **Trending market**: Grid works best in ranges. Consider switching to SMC or Trend-Follower
2. **Range too narrow**: Increase grid range to capture wider oscillations
3. **Too many levels**: Reduce `grid_levels` to concentrate capital

### DCA Safety Orders Not Triggering

**Possible causes**:
1. **Price not dropping enough**: Safety orders require specific price deviation thresholds
2. **Max safety orders reached**: Check `max_steps` limit
3. **Insufficient balance**: Each safety order needs available capital

---

## Bybit Demo Trading

### Orders Not Placed / "Invalid instrument" Errors

**Cause**: Demo trading (`api-demo.bybit.com`) only supports **linear (futures) contracts**, not spot.

**Fix**: All symbols in `configs/phase7_demo.yaml` must be futures pairs:
```yaml
symbol: BTC/USDT  # ✅ linear futures
# NOT: BTC/USDT:USDT or spot-only pairs
```

### CCXT `set_sandbox_mode` Does Not Work for Demo

**Cause**: CCXT's `set_sandbox_mode(True)` routes to `testnet.bybit.com` — a completely different endpoint with separate API keys and balance.

**Fix**: Use `ByBitDirectClient` (automatically selected when `exchange_id: bybit` and `sandbox: true`). This client connects directly to `api-demo.bybit.com` using your production API keys.

### Demo Balance Shows 0 or Not Found

1. Ensure your API keys are the **production** keys (not testnet keys)
2. Check that demo account has been activated at `https://testnet.bybit.com` → Demo Trading
3. Verify `credentials_name: bybit_demo` exists in the database with correct keys

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

### State Not Restored on Restart

**Symptom**: Bot starts fresh instead of resuming previous orders

**Cause**: State is loaded from `bot_state_snapshots` table in PostgreSQL. Check:
1. `DATABASE_URL` is set correctly
2. Table exists: `SELECT * FROM bot_state_snapshots WHERE bot_name='demo_btc_hybrid';`
3. Bot was not reset: `reset_state()` deletes the snapshot

---

## Telegram Bot Issues

### Bot Not Responding

**Possible causes**:
1. **Invalid token**: Verify `TELEGRAM_BOT_TOKEN` is correct
2. **Chat not authorized**: Ensure your chat ID is in `allowed_chat_ids`
3. **Bot not started**: The event loop must be running for the bot to process messages
4. **Webhook conflict**: If using webhooks elsewhere, clear them: `bot.delete_webhook()`

### Markdown Parse Errors in Notifications

**Symptom**: `BadRequest: can't parse entities` in logs, but notification is still sent

**Behavior**: The bot automatically retries notification without `parse_mode` (plain text fallback). This is expected — check the notification still arrives.

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

### Demo Smoke Tests Skipped

**Symptom**: `tests/integration/test_demo_smoke.py` shows SKIPPED

**Solution**: Set the environment variable:
```bash
DEMO_SMOKE_TEST=1 python -m pytest tests/integration/test_demo_smoke.py -v
```
Also ensure `bybit_demo` credentials are present in the database.

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

# Validate demo config
python scripts/validate_demo.py
```

Both should show `overall_status: PASS` before going live.

---

## Getting Help

- GitHub Issues: https://github.com/alekseymavai/TRADERAGENT/issues
- Check logs: structured logging with `structlog` — search for `error` severity
- Enable debug mode: `log_level: DEBUG` in YAML config (disable for production)
- Session history: `docs/SESSION_CONTEXT.md` — detailed log of all changes and fixes
