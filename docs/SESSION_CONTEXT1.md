# TRADERAGENT v2.0 — Session Context (Updated 2026-02-17)

## Current Status

**Date:** February 17, 2026
**Session:** 12 (Grid Backtesting Standalone Service — audited)
**Tests:** 532 passing (385 bot + 46 web + 8 state persistence + 93 backtester service)
**Codebase:** 306 Python files (74,196 LOC) + 51 TypeScript files (6,536 LOC)
**Commits:** 385 total
**Open Audit Issues:** 0 — all 12/12 closed (#226-#237)

---

## Session 12: Grid Backtesting Standalone Service

### What Was Done

Extracted grid backtesting system into a standalone microservice under `services/backtesting/`. Implemented 13 planned issues — from code extraction to Docker deployment. Post-implementation audit выявил 4 бага и 4 проблемы средней критичности.

### New Service: `services/backtesting/`

| Module | Files | LOC | Description |
|--------|-------|-----|-------------|
| `core/` | calculator, order_manager, risk_manager, config, market_simulator | ~2,200 | Grid calculation engine, order lifecycle, risk checks |
| `engine/` | models, simulator, optimizer, clusterizer, reporter, system | ~1,700 | Backtest simulation, 2-phase optimization, coin clustering |
| `trailing/` | manager | ~150 | Trailing grid algorithm (fixed/ATR recentering) |
| `visualization/` | charts | ~200 | Plotly equity curve, drawdown, grid heatmap |
| `persistence/` | job_store, preset_store, checkpoint | ~350 | SQLite persistence (aiosqlite), JSONL checkpoints |
| `caching/` | indicator_cache | ~80 | LRU indicator cache with stats |
| `api/` | app, auth, routes | ~350 | FastAPI REST service, API key auth |
| `logging/` | logger | ~100 | Structured logging (structlog) |
| **Tests** | 14 files | ~700 | 93 tests — core, engine, API |
| **Infra** | Dockerfile, docker-compose.yml, pyproject.toml, .env.example | — | Multi-stage Docker build, port 8100 |
| **Итого** | 44 файла | ~5,230 | — |

### 13 Issues: Статус после аудита

| # | Issue | Реальный статус | Проблема |
|---|-------|----------------|----------|
| 1 | Extract into standalone package | **DONE** | Все `bot.*` → `grid_backtester.*`, оригинал полностью сохранён |
| 2 | Take-profit at grid level | **DONE** | `simulator.py:371-383`, PnL% exit, тест есть |
| 3 | Structured logging | **DONE** | ~40+ вызовов structlog по всем модулям |
| 4 | Trailing grid algorithm | **PARTIAL** | Inline в simulator работает (fixed mode), но `TrailingGridManager` **не подключён**, ATR recentering **не работает** |
| 5 | Parallel trial execution | **DEFECT** | ProcessPoolExecutor запускается, но затем re-run последовательно — **2x медленнее** чем sequential |
| 6 | Capital efficiency metric | **DONE** | Трекинг и расчёт в simulator, тест есть |
| 7 | SQLite job persistence | **DONE** | `JobStore` полностью, CRUD + cleanup |
| 8 | Visualization | **PARTIAL** | `GridChartGenerator` написан, но **API chart endpoint — заглушка**, charts нигде не вызываются |
| 9 | FastAPI standalone service | **DONE** | 11 endpoints, background tasks, auth |
| 10 | Indicator caching | **NOT WIRED** | Класс написан (93 LOC), но **ни один модуль его не импортирует** |
| 11 | Incremental resume | **NOT WIRED** | Класс написан (92 LOC), но **optimizer его не использует** |
| 12 | Preset API for bot integration | **DONE** | `PresetStore` + REST CRUD + auto-save |
| 13 | Docker deployment | **DONE** | Dockerfile, docker-compose, .env.example, healthcheck |

**Итого: 8 полностью готовы, 2 частично, 2 не подключены, 1 с дефектом**

### Критические баги (найдены аудитом)

**BUG-1: Параллельный оптимизатор перезапускает все trials**
- `optimizer.py:443-445` — после parallel прогона каждый trial re-run последовательно
- Результат: параллельный режим в 2x медленнее последовательного
- Fix: десериализовать `GridBacktestResult` из dict вместо re-run

**BUG-2: `IndicatorCache` не подключён (Issue #10)**
- Класс написан полностью (LRU, stats, get_or_compute)
- Ни simulator, ни optimizer, ни clusterizer его не импортируют
- ATR пересчитывается каждый раз заново

**BUG-3: `OptimizationCheckpoint` не подключён (Issue #11)**
- Класс написан полностью (JSONL, config_hash)
- optimizer.py его не импортирует и не вызывает
- При перезапуске все trials считаются заново

**BUG-4: Trailing grid — дублирование и неполная реализация (Issue #4)**
- `trailing/manager.py` — standalone класс с `_recenter_fixed()` и `_recenter_atr()`
- `simulator.py:273-342` — inline реализация (только fixed mode)
- Simulator **не использует** `TrailingGridManager`
- `trailing_recenter_mode="atr"` из конфига фактически **игнорируется**

### Проблемы средней критичности

**ISSUE-5:** `/api/v1/chart/{job_id}` возвращает JSON-заглушку, `GridChartGenerator` не вызывается

**ISSUE-6:** `_execute_optimize` в `routes.py:230-247` — positional args в `run_in_executor` хрупко

**ISSUE-7:** `datetime.utcnow()` deprecated (Python 3.12+) — 4000+ warnings в тестах

**ISSUE-8:** Молчаливое `except Exception: pass` в `market_simulator.py:235` и `simulator.py:317`

### Тестовое покрытие: ~60%

| Модуль | Тесты | Покрыто | Не покрыто |
|--------|-------|---------|-----------|
| core/calculator | 9 | arithmetic, geometric, ATR, grid orders | — |
| core/order_manager | 4 | init, register/fill, rebalance, stats | partial fill |
| core/risk_manager | 25 | все проверки, classify, evaluate, reset | — |
| core/config | 13 | presets, yaml, validation | from_yaml_file |
| engine/simulator | 12 | basic, stop-loss, take-profit, trailing, capital efficiency | direction LONG/SHORT |
| engine/optimizer | 5 | basic, objectives, top_n, param_impact | **parallel execution** |
| engine/clusterizer | 6 | classify, stable, meme, presets | — |
| engine/system | 5 | single, pipeline, stress, multi-symbol | — |
| api | 5 | health, submit, presets | **optimize, chart, delete, auth with key** |
| **trailing/** | **0** | — | **TrailingGridManager полностью** |
| **persistence/** | **0** | — | **JobStore, PresetStore, Checkpoint** |
| **caching/** | **0** | — | **IndicatorCache** |
| **visualization/** | **0** | — | **GridChartGenerator** |

### Сравнение с оригиналом

| Модуль | Оригинал | Извлечение | Потери | Добавлено |
|--------|----------|-----------|--------|-----------|
| GridCalculator | 578 LOC | 388 LOC | 0 (сжаты docstrings) | Logging |
| GridOrderManager | 558 LOC | 437 LOC | 0 | Logging |
| GridRiskManager | 521 LOC | 400 LOC | 0 | Logging |
| GridBacktestSimulator | 416 LOC | 543 LOC | 0 | +Take-profit, +Trailing, +Capital efficiency |
| GridOptimizer | 394 LOC | 494 LOC | 0 | +Parallel, +Config serialization |

**Оригинальная функциональность полностью сохранена.** Все методы и классы на месте, логика идентична.

### API Endpoints

```
GET  /health                     — healthcheck
POST /api/v1/backtest/run        — submit backtest (202 + job_id)
GET  /api/v1/backtest/{job_id}   — get job status/result
GET  /api/v1/backtest/history    — list jobs
POST /api/v1/optimize/run        — submit optimization (202 + job_id)
GET  /api/v1/presets             — list active presets
GET  /api/v1/presets/{symbol}    — get preset for symbol
POST /api/v1/presets             — create preset (201)
DELETE /api/v1/presets/{id}      — delete preset
GET  /api/v1/chart/{job_id}     — STUB (returns JSON, not actual chart)
```

Auth: `X-API-Key` header (optional — пропускает если `BACKTESTER_API_KEY` не задан)

### How to Run

```bash
# Install & test
cd services/backtesting
pip install -e ".[dev]"
pytest tests/ -v                     # 93 tests

# Run service
uvicorn grid_backtester.api.app:create_app --factory --port 8100

# Docker
docker compose up -d
curl http://localhost:8100/health
```

---

## Session 11: State Persistence (#237)

### What Was Done

Implemented full state persistence, startup reconciliation, and hybrid strategy serialization — closing the last audit issue.

| Change | Details |
|--------|---------|
| `bot/database/models_state.py` | `BotStateSnapshot` model with `hybrid_state` column |
| `bot/orchestrator/state_persistence.py` | Serialize/deserialize for all 5 engines (Grid, DCA, Risk, Trend, Hybrid) |
| `bot/database/manager.py` | `save_state_snapshot()`, `load_state_snapshot()`, `delete_state_snapshot()` |
| `bot/orchestrator/bot_orchestrator.py` | `save_state()`, `load_state()`, `reconcile_with_exchange()`, `reset_state()` |
| `bot/database/__init__.py` | Export `BotStateSnapshot` for auto table registration |
| `web/backend/app.py` | Import `BotStateSnapshot` in lifespan for table creation |
| `bot/strategies/smc/position_manager.py` | Fix `is_long` detection (entry > stop_loss, not <) |
| Tests (8 new) | Hybrid serialization (6), reset_state, save_state hybrid coverage |

### How State Persistence Works

1. **`initialize()`** — loads last snapshot from PostgreSQL
2. **`start()`** — if state loaded, runs `reconcile_with_exchange()` instead of fresh grid init
3. **`_main_loop()`** — saves state every 30 seconds
4. **`stop()` / `emergency_stop()`** — saves final state before exit
5. **`reconcile_with_exchange()`** — checks grid orders (filled vs orphaned), refreshes risk balance
6. **`reset_state()`** — deletes snapshot for explicit fresh start

### Commit

| Issue | Title | Commit | Status |
|-------|-------|--------|--------|
| [#237](https://github.com/alekseymavai/TRADERAGENT/issues/237) | Add state persistence for positions/orders and startup reconciliation | `a0f97ce` | **FIXED** |

### Repository Cleanup

Removed 11 temporary files from root: `BYBIT_INTEGRATION_REPORT.txt`, `BYBIT_SETUP_GUIDE.md`, `GIT_PUSH_INSTRUCTIONS.md`, `QUICK_PRODUCTION_COMMANDS.sh`, `QUICK_START_BYBIT.md`, `SERVER_INFO.txt`, `SETUP_DATABASE.md`, `check_orders.py`, `show_api_key.py`, `test_bybit_direct.py`, `test_bybit_final.py`.

---

## Session 9-10: Bug Fixes from Audit (12/12 closed)

| Issue | Title | Commit | Status |
|-------|-------|--------|--------|
| [#226](https://github.com/alekseymavai/TRADERAGENT/issues/226) | Fix 6 AttributeError crashes in BotOrchestrator | `5cf8f71` | **FIXED** |
| [#227](https://github.com/alekseymavai/TRADERAGENT/issues/227) | Fix BotService async/sync mismatch and field name mismatches | `bdb0551` | **FIXED** |
| [#228](https://github.com/alekseymavai/TRADERAGENT/issues/228) | Fix Market API attribute name (exchange_client → exchange) | `842072f` | **FIXED** |
| [#229](https://github.com/alekseymavai/TRADERAGENT/issues/229) | Activate WebSocket RedisBridge in app.py lifespan | `93facee` | **FIXED** |
| [#230](https://github.com/alekseymavai/TRADERAGENT/issues/230) | Grid fill detection treats cancelled orders as filled | `7dab5d8` | **FIXED** |
| [#231](https://github.com/alekseymavai/TRADERAGENT/issues/231) | DCA engine state advances before exchange order confirmation | `7dab5d8` | **FIXED** |
| [#232](https://github.com/alekseymavai/TRADERAGENT/issues/232) | Add daily_loss automatic reset mechanism | `7dab5d8` | **FIXED** |
| [#233](https://github.com/alekseymavai/TRADERAGENT/issues/233) | Cache balance to avoid 3+ API calls per loop iteration | `7dab5d8` | **FIXED** |
| [#234](https://github.com/alekseymavai/TRADERAGENT/issues/234) | Replace backtesting API placeholder with real BacktestingEngine | `2524fdf` | **FIXED** |
| [#235](https://github.com/alekseymavai/TRADERAGENT/issues/235) | Replace Settings API hardcoded values with real config | `2524fdf` | **FIXED** |
| [#236](https://github.com/alekseymavai/TRADERAGENT/issues/236) | Persist strategy templates to database | `2524fdf` | **FIXED** |
| [#237](https://github.com/alekseymavai/TRADERAGENT/issues/237) | Add state persistence for positions/orders and startup reconciliation | `a0f97ce` | **FIXED** |

---

## Session 8: Full Project Audit

### What Was Done

1. **Launched Web UI locally** — Backend (FastAPI :8001) + Frontend (Vite :3000)
2. **Screenshots of all 7 pages** — committed to `docs/screenshots/` and pushed to main
3. **Full codebase audit** — three parallel deep audits (structure, trading logic, web API)
4. **Graceful BotApplication init** — `web/backend/app.py` now catches init errors for standalone mode
5. **Created 12 GitHub Issues** (#226-#237) from audit findings, grouped by priority

### Screenshots (in repo)

| Page | File |
|------|------|
| Login | `docs/screenshots/01-login.png` |
| Dashboard | `docs/screenshots/02-dashboard.png` |
| Bots | `docs/screenshots/03-bots.png` |
| Strategies | `docs/screenshots/04-strategies.png` |
| Portfolio | `docs/screenshots/05-portfolio.png` |
| Backtesting | `docs/screenshots/06-backtesting.png` |
| Settings | `docs/screenshots/07-settings.png` |
| Settings (full) | `docs/screenshots/08-settings-full.png` |

---

## Audit Results: What's REAL vs MOCK vs DEAD CODE

### Bot Core — ALL REAL

| Module | Lines | Quality |
|--------|-------|---------|
| ExchangeAPIClient (CCXT) | 672 | Solid — retry, rate limiting, WebSocket |
| ByBitDirectClient (V5 native) | 1,024 | Working — HMAC auth, CCXT-compatible format |
| Grid Engine | 377 | Prototype — logic issues in profit calc |
| DCA Engine | 388 | Prototype — clean logic, integration ~~broken~~ **FIXED** |
| Trend Follower (5 modules) | 2,400 | Best module — ATR TP/SL, trailing, partial close |
| SMC Strategy (5 modules) | 2,650 | Full implementation, is_long bug **FIXED** |
| Hybrid (Grid+DCA) | 1,100 | Implemented |
| Risk Manager | ~300 | Basic — daily reset **FIXED**, no peak-based SL |
| Bot Orchestrator | 1,377 | State persistence + reconciliation **DONE** |
| Telegram Bot | 854 | Working |
| Monitoring (Prometheus) | ~500 | Implemented |

### Web UI Backend — ALL REAL (except portfolio history stubs)

| Endpoint | Verdict | Details |
|----------|---------|---------|
| Auth (JWT) | **REAL** | bcrypt + JWT refresh rotation + DB sessions |
| Bots API | **REAL** | Properly awaits + correct field names |
| Dashboard | **REAL** | Shows real bot data |
| Market API | **REAL** | Uses `orch.exchange` correctly |
| Portfolio summary | **REAL** | Connected properly |
| Portfolio history/drawdown/trades | **STUB** | Returns empty arrays |
| Strategies | **REAL** | Persisted to DB via `StrategyTemplate` model |
| Backtesting | **REAL** | Uses `GridBacktestSimulator` |
| Settings | **REAL** | Reads from `config_manager` with fallback |
| WebSocket | **REAL** | RedisBridge started in lifespan with graceful fallback |
| Frontend | **REAL** | All pages call real API, no client-side mocks |

### Backtesting Service — AUDIT RESULTS

| Component | Verdict | Details |
|-----------|---------|---------|
| Grid Simulator | **REAL** | Intra-candle sweep, fees, PnL, all metrics |
| Take-profit | **REAL** | PnL% exit, stop_reason, tested |
| Capital efficiency | **REAL** | Deployed capital tracking, tested |
| Optimizer | **REAL** | 2-phase (coarse+fine), all objectives |
| Clusterizer | **REAL** | ATR%-based: STABLE/BLUE_CHIPS/MID_CAPS/MEMES |
| Reporter | **REAL** | Summary, optimization report, YAML/JSON preset export |
| REST API | **REAL** | 10 working endpoints + 1 stub (chart) |
| Job persistence | **REAL** | SQLite CRUD, background tasks |
| Preset persistence | **REAL** | SQLite, auto-deactivation, REST CRUD |
| Trailing grid (inline) | **PARTIAL** | Fixed recentering works, ATR mode **ignored** |
| Trailing grid (standalone) | **DEAD CODE** | `TrailingGridManager` not imported by simulator |
| Parallel optimizer | **DEFECT** | Runs trials, then re-runs them sequentially (2x slower) |
| Chart endpoint | **STUB** | Returns JSON message, `GridChartGenerator` **not called** |
| Indicator caching | **DEAD CODE** | `IndicatorCache` not imported anywhere |
| Optimization resume | **DEAD CODE** | `OptimizationCheckpoint` not imported by optimizer |

### Web UI Frontend — REAL
All 7 pages make real API calls. Axios client with JWT interceptor + auto-refresh on 401. Zustand stores. No hardcoded mock data in pages.

---

## What Works Well

1. **Architecture** — clean separation: exchange API / strategies / orchestration / DB / web
2. **5 real strategies** — Grid, DCA, Trend Follower, Hybrid, SMC (~10,500 lines)
3. **Dual exchange client** — CCXT for broad support + native Bybit V5 for demo
4. **Async throughout** — asyncio, asyncpg, aiohttp, async Redis
5. **State persistence** — PostgreSQL snapshots, startup reconciliation, graceful shutdown
6. **JWT auth** — proper refresh rotation, bcrypt, DB sessions
7. **Docker** — production-quality, multi-stage builds, health checks, non-root
8. **CI/CD** — GitHub Actions (lint + test + docker + security scan)
9. **532 tests passing** — bot, web, state persistence, backtester service
10. **Standalone backtesting service** — core simulation, optimization, preset management working

---

## Phase Implementation Status

```
Phase 1: Architecture Foundation      [##########] 100%
Phase 2: Grid Trading Engine          [##########] 100%
Phase 3: DCA Engine                   [##########] 100%
Phase 4: Hybrid Strategy              [##########] 100%
Phase 5: Infrastructure & DevOps      [##########] 100%
Phase 6: Advanced Backtesting         [##########] 100%
Phase 7.1-7.2: Testing                [##########] 100%
Phase 7.3: Demo Trading Deployment    [##########] 100%  ← DEPLOYED (stopped)
Phase 7.4: Load/Stress Testing        [##########] 100%
Phase 8: Production Launch            [##########] 100%  ← ALL 12/12 BUGS FIXED
Phase 9: Backtesting Standalone Svc   [#######...]  75%  ← 8/13 done, 5 need fixes
```

**Web UI Dashboard:**
```
Backend Foundation    [##########] 100%  (Auth=REAL)
WebSocket + Events    [##########] 100%  (RedisBridge activated in lifespan)
Full REST API         [#########.]  90%  (all endpoints REAL except portfolio history stubs)
Frontend              [##########] 100%  (all pages real API integration)
Docker                [##########] 100%
Tests                 [##########] 100%  (46 tests, mocks now match real orchestrator)
```

**Backtesting Service (post-audit):**
```
Core extraction       [##########] 100%  (calculator, orders, risk, config, simulator)
Engine features       [##########] 100%  (optimizer, clusterizer, reporter, system)
Take-profit (#2)      [##########] 100%  (PnL% exit, tested)
Logging (#3)          [##########] 100%  (structlog, ~40 calls)
Capital efficiency(#6)[##########] 100%  (deployed capital tracking, tested)
Job persistence (#7)  [##########] 100%  (SQLite CRUD, background tasks)
Preset API (#12)      [##########] 100%  (REST CRUD, auto-save)
Docker (#13)          [##########] 100%  (multi-stage, healthcheck, port 8100)
Trailing grid (#4)    [######....]  60%  (fixed mode inline works, ATR mode dead, standalone unused)
Parallel optim (#5)   [###.......]  30%  (runs but re-runs all trials — 2x slower)
Visualization (#8)    [####......]  40%  (class written, chart endpoint is stub)
Caching (#10)         [##........]  20%  (class written, not wired to any module)
Resume (#11)          [##........]  20%  (class written, not wired to optimizer)
Tests                 [######....]  60%  (93 pass, 4 modules have 0 tests)
```

---

## Backtester Service: What Needs Fixing

### Priority 1 — Bugs (need fix before production)

| # | Bug | File | Effort |
|---|-----|------|--------|
| BUG-1 | Parallel optimizer re-runs trials (2x slower) | `optimizer.py:443-445` | 2-3h |
| BUG-2 | `IndicatorCache` dead code — not wired | All engine modules | 1-2h |
| BUG-3 | `OptimizationCheckpoint` dead code — not wired | `optimizer.py` | 1-2h |
| BUG-4 | Trailing grid: ATR mode ignored, standalone class unused | `simulator.py`, `trailing/manager.py` | 2-3h |

### Priority 2 — Stubs and gaps

| # | Issue | File | Effort |
|---|-------|------|--------|
| STUB-1 | Chart endpoint returns JSON, not HTML | `routes.py:349-355` | 1h |
| STUB-2 | `datetime.utcnow()` deprecated (4000+ warnings) | `market_simulator.py` | 15min |
| STUB-3 | Silent `except Exception: pass` | `market_simulator.py:235`, `simulator.py:317` | 15min |
| STUB-4 | Positional args in `run_in_executor` fragile | `routes.py:230-247` | 15min |

### Priority 3 — Missing tests

| Module | Missing tests | Effort |
|--------|--------------|--------|
| `trailing/` | TrailingGridManager full suite | 1h |
| `persistence/` | JobStore, PresetStore, Checkpoint | 2h |
| `caching/` | IndicatorCache | 30min |
| `visualization/` | GridChartGenerator | 1h |
| `optimizer` | Parallel execution path | 1h |
| `api` | Optimize, chart, delete, auth with key | 1h |

**Estimated total fix time: 14-16 hours**

---

## Key Files

```
# Main Bot
bot/orchestrator/bot_orchestrator.py    — Main trading loop (1,377 lines, state persistence)
bot/orchestrator/state_persistence.py   — Serialize/deserialize all engines (380 lines)
bot/database/models_state.py            — BotStateSnapshot model
bot/api/exchange_client.py              — CCXT exchange client (672 lines)
bot/api/bybit_direct_client.py          — Bybit V5 native client (1,024 lines)
bot/core/grid_engine.py                 — Grid trading engine (377 lines)
bot/core/dca_engine.py                  — DCA engine (388 lines)
bot/core/risk_manager.py                — Risk management (~300 lines)
bot/strategies/trend_follower/          — Trend Follower (5 files, 2,400 lines)
bot/strategies/smc/                     — SMC Strategy (5 files, 2,650 lines)
bot/strategies/hybrid/                  — Hybrid Grid+DCA (4 files, 1,100 lines)
bot/main.py                             — BotApplication entry (343 lines)
web/backend/services/bot_service.py     — Bridge to orchestrators
web/backend/app.py                      — FastAPI factory + lifespan
web/frontend/src/api/client.ts          — Axios + JWT interceptor
configs/phase7_demo.yaml                — Bybit demo config (4 strategies)

# Backtesting Standalone Service
services/backtesting/src/grid_backtester/core/      — Grid calculator, orders, risk (~2,200 LOC)
services/backtesting/src/grid_backtester/engine/     — Simulator, optimizer, clusterizer (~1,700 LOC)
services/backtesting/src/grid_backtester/trailing/   — Trailing grid — STANDALONE NOT WIRED
services/backtesting/src/grid_backtester/api/        — FastAPI REST service (~350 LOC)
services/backtesting/src/grid_backtester/persistence/ — SQLite job/preset store (~350 LOC)
services/backtesting/src/grid_backtester/visualization/ — Plotly charts — NOT WIRED TO API
services/backtesting/src/grid_backtester/caching/    — Indicator LRU cache — NOT WIRED
services/backtesting/Dockerfile                      — Multi-stage build, port 8100
services/backtesting/docker-compose.yml              — Service config with volumes
services/backtesting/pyproject.toml                  — Package config (no ccxt/sqlalchemy deps)
```

---

## Quick Commands

```bash
cd /home/hive/TRADERAGENT

# Run all tests (532)
python -m pytest bot/tests/ --ignore=bot/tests/testnet tests/web/ tests/orchestrator/ tests/database/ -q
cd services/backtesting && python -m pytest tests/ -q && cd ../..

# Bot tests only (385)
python -m pytest bot/tests/ --ignore=bot/tests/testnet -q

# Web tests only (46)
python -m pytest tests/web/ -q

# State persistence tests (8)
python -m pytest tests/orchestrator/test_state_persistence.py tests/database/test_state_model.py -v

# Backtester service tests (93)
cd services/backtesting && python -m pytest tests/ -v

# Backtester service run
cd services/backtesting && uvicorn grid_backtester.api.app:create_app --factory --port 8100

# Frontend dev
cd web/frontend && npm run dev

# Backend dev
uvicorn web.backend.main:app --reload --port 8000

# Docker
docker compose up webui-backend webui-frontend
cd services/backtesting && docker compose up -d  # backtester on :8100
```

---

## Open Issues (non-audit)

| Issue | Title |
|-------|-------|
| [#85](https://github.com/alekseymavai/TRADERAGENT/issues/85) | Fibonacci strategy tester (ALMIRBGCLOD) |
| [#90](https://github.com/alekseymavai/TRADERAGENT/issues/90) | Systematic strategy testing on top 100 crypto pairs |
| [#91](https://github.com/alekseymavai/TRADERAGENT/issues/91) | Testing results analysis report |
| [#97](https://github.com/alekseymavai/TRADERAGENT/issues/97) | TradingView chart data automation |
| [#144](https://github.com/alekseymavai/TRADERAGENT/issues/144) | Backtest results visualization |

---

## Links

- **Repository:** https://github.com/alekseymavai/TRADERAGENT
- **Screenshots:** https://github.com/alekseymavai/TRADERAGENT/tree/main/docs/screenshots
- **Architecture:** https://github.com/alekseymavai/TRADERAGENT/blob/main/docs/ARCHITECTURE.md
- **Web UI PR:** https://github.com/alekseymavai/TRADERAGENT/pull/221
- **Issues Board:** https://github.com/alekseymavai/TRADERAGENT/issues

---

## Last Updated

- **Date:** February 17, 2026
- **Session:** 12 (Grid Backtesting Standalone Service — post-audit)
- **Tests:** 532/532 passing (100%)
- **Audit Bugs Fixed:** 12/12 — #226-#237 all resolved
- **Backtester Service:** 8/13 fully done, 2 partial, 2 dead code, 1 defect; 93 tests (60% coverage)
- **Remaining Backtester Fixes:** ~14-16 hours (4 bugs + 4 stubs + missing tests)
- **Remaining Issues:** 5 open (non-audit: #85, #90, #91, #97, #144)
- **Next Action:** Fix BUG-1..4, wire dead code, add missing tests, then deploy
- **Co-Authored:** Claude Opus 4.6
