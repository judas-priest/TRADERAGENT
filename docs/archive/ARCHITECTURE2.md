# TRADERAGENT v2.0 — Architecture (Updated 2026-02-17)

## Overview

| Metric | Value |
|--------|-------|
| Python files | 312 |
| TypeScript files | 51 |
| Total LOC | ~79,000 (72,552 Python + 6,536 TypeScript) |
| Commits | 391 |
| Tests | 532 passing |
| Strategies | 5 (Grid, DCA, Hybrid, SMC, Trend Follower) |
| DB tables | 16 |
| Docker services | 6 |
| Server | 185.233.200.13 (synced to `663c2d6`) |

---

## System Architecture

```
                              ┌──────────────────────────┐
                              │      Web Frontend         │
                              │  React + Vite + Zustand   │
                              │     7 pages, :3000        │
                              └────────────┬─────────────┘
                                           │ Axios + JWT
                              ┌────────────▼─────────────┐
                              │     Web Backend           │
                              │  FastAPI + WebSocket      │
                              │   JWT Auth, :8000         │
                              └────────────┬─────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         │                                 │                                 │
┌────────▼─────────┐          ┌────────────▼─────────────┐      ┌───────────▼──────────┐
│   PostgreSQL 15   │          │    Bot Application       │      │      Redis 7          │
│  16 tables        │◄────────►│  (bot/main.py)           │◄────►│  Pub/Sub + Cache      │
│  asyncpg          │          │                          │      │                       │
└──────────────────┘          └────────────┬─────────────┘      └───────────────────────┘
                                           │
                          ┌────────────────┼────────────────┐
                          │                │                │
                 ┌────────▼──────┐  ┌──────▼──────┐  ┌─────▼──────────┐
                 │  Orchestrator  │  │  Telegram   │  │  Monitoring    │
                 │  (main loop)   │  │  Bot        │  │  Prometheus    │
                 └────────┬──────┘  └─────────────┘  └────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
   ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
   │  Strategy    │ │  Risk       │ │  Exchange   │
   │  Registry    │ │  Manager    │ │  Client     │
   │  (5 strats)  │ │             │ │  CCXT+Bybit │
   └──────┬──────┘ └─────────────┘ └─────────────┘
          │
  ┌───────┼───────┬───────┬───────┬───────┐
  │       │       │       │       │       │
┌─▼──┐ ┌─▼──┐ ┌──▼─┐ ┌──▼─┐ ┌──▼──────┐
│Grid│ │DCA │ │Hyb │ │SMC │ │Trend    │
│    │ │    │ │rid │ │    │ │Follower │
└────┘ └────┘ └────┘ └────┘ └─────────┘


         ┌──────────────────────────────────────┐
         │   Backtesting Service (standalone)    │
         │   FastAPI :8100, SQLite, Docker       │
         │   services/backtesting/               │
         └──────────────────────────────────────┘
```

---

## Code Distribution

### By Directory

| Directory | Files | LOC | Description |
|-----------|-------|-----|-------------|
| `bot/` | 116 | 37,134 | Main trading bot |
| `tests/` | 85 | 22,350 | Test suite |
| `services/` | 54 | 6,377 | Backtesting microservice |
| `web/` | 35 | 2,440 | Web UI (backend + frontend) |
| `scripts/` | 4 | 1,425 | Utility scripts |
| Other | 18 | 2,826 | Examples, root helpers |
| **Total Python** | **312** | **72,552** | |
| Frontend (TS) | 51 | 6,536 | React + TypeScript |

### Bot Module Breakdown (37,134 LOC)

| Module | Files | LOC | Role |
|--------|-------|-----|------|
| `strategies/` | 39 | 13,512 | 5 trading strategies (37% of bot code) |
| `orchestrator/` | 8 | 3,813 | Main loop, state, health, strategy selection |
| `database/` | 7 | 1,890 | Models, manager, migrations, backup |
| `api/` | 4 | 1,768 | CCXT client + Bybit V5 native |
| `core/` | 4 | 1,164 | DCA/Grid engines, Risk manager |
| `utils/` | 5 | 1,059 | Logging, capital, security |
| `telegram/` | 2 | 859 | Telegram bot & notifications |
| `monitoring/` | 4 | 757 | Prometheus metrics, alerts |
| `config/` | 3 | 694 | YAML config loader, Pydantic schemas |
| `tests/` | 33 | 11,276 | Legacy tests (deprecated, use root `tests/`) |
| `main.py` | 1 | 342 | Entry point |

---

## Strategies (13,512 LOC)

### Architecture

```
bot/strategies/
├── base.py                          # AbstractStrategy base class
├── {name}_adapter.py                # Adapter → Orchestrator interface (x4)
├── grid/           (6 files, 1,982 LOC)   # Grid Trading
├── dca/            (8 files, 3,454 LOC)   # Dollar Cost Averaging
├── hybrid/         (4 files, 1,228 LOC)   # Grid + DCA combo
├── smc/            (7 files, 2,725 LOC)   # Smart Money Concepts
└── trend_follower/ (8 files, 2,537 LOC)   # Trend Following
```

### Strategy Comparison

| Strategy | LOC | Modules | Entry Logic | Exit Logic | Status |
|----------|-----|---------|-------------|------------|--------|
| **Grid** | 1,982 | calculator, order_mgr, risk_mgr, config | Grid levels (buy low, sell high) | Profit per grid level | Production |
| **DCA** | 3,454 | engine, signal_gen, position_mgr, risk_mgr, trailing, backtester, config | % drop trigger | Take profit % from avg | Production |
| **Hybrid** | 1,228 | strategy, config, market_regime_detector | Grid in range + DCA below | Grid profit + DCA TP | Production |
| **SMC** | 2,725 | strategy, market_structure, confluence_zones, entry_signals, position_mgr, config | Order Blocks + FVG + Price Action | Kelly sizing + partial TP + trailing | Production |
| **Trend Follower** | 2,537 | strategy, market_analyzer, entry_logic, position_mgr, risk_mgr, trade_logger, config | EMA crossover + RSI + Volume | ATR-based TP/SL + trailing | Production |

### Shared Core (Grid)

Grid strategy uses shared core modules for both live trading and backtesting:

```
bot/strategies/grid/
├── grid_calculator.py         ← shared core (used by services/backtesting/)
├── grid_config.py             ← shared core
├── grid_order_manager.py      ← shared core
├── grid_risk_manager.py       ← shared core
├── exchange_protocol.py       ← Protocol interface for exchange abstraction
└── __init__.py
```

`services/backtesting/` imports from `bot.strategies.grid` to avoid code duplication.

---

## Orchestrator (3,813 LOC)

Central coordination layer for all trading activity.

| File | LOC | Role |
|------|-----|------|
| `bot_orchestrator.py` | 1,377 | Main loop: init → start → trade → save state → stop |
| `state_persistence.py` | 380 | Serialize/deserialize all 5 engine states to PostgreSQL |
| `strategy_selector.py` | ~400 | Multi-strategy routing and selection |
| `strategy_registry.py` | ~300 | Strategy registration and discovery |
| `health_monitor.py` | ~400 | Health checks, diagnostics, auto-recovery |
| `market_regime.py` | ~350 | Market phase detection (Bullish/Bearish/Sideways) |
| `events.py` | ~200 | Event definitions for component communication |

### Lifecycle

```
initialize()
  └─ load state from PostgreSQL (if exists)

start()
  ├─ if state loaded → reconcile_with_exchange()
  └─ else → fresh grid/DCA init

_main_loop() (every 5-10s)
  ├─ fetch market data (CCXT/Bybit)
  ├─ run strategy logic
  ├─ place/cancel orders
  ├─ update risk checks
  └─ save state snapshot (every 30s)

stop() / emergency_stop()
  └─ save final state → close connections
```

---

## Exchange Integration

### Dual Client Architecture

```
┌─────────────────────────┐    ┌──────────────────────────┐
│  ExchangeAPIClient       │    │  ByBitDirectClient        │
│  (CCXT wrapper)          │    │  (Native V5 API)          │
│  672 LOC                 │    │  1,024 LOC                │
│                          │    │                           │
│  - 150+ exchanges        │    │  - HMAC-SHA256 auth       │
│  - Retry + rate limiting │    │  - api-demo.bybit.com     │
│  - WebSocket support     │    │  - CCXT-compatible format │
│  - Sandbox mode          │    │  - Linear (futures) only  │
└─────────────────────────┘    └──────────────────────────┘
```

**Selection logic** (`bot/main.py`):
- `exchange_id == "bybit"` AND `sandbox == true` → `ByBitDirectClient` (demo trading)
- Everything else → `ExchangeAPIClient` (CCXT)

**Why dual?** CCXT `set_sandbox_mode(True)` routes to `testnet.bybit.com` (wrong for demo). Bybit demo trading uses `api-demo.bybit.com` with production API keys.

---

## Database

### Schema (16 tables)

```
┌─ Initial Migration (20260213) ─────────────────────┐
│  exchange_credentials    API keys (AES-256)         │
│  bots                    Bot config & status         │
│  orders                  Order history               │
│  trades                  Trade history               │
│  grid_levels             Grid state                  │
│  dca_history             DCA averaging history       │
│  bot_logs                Bot activity logs           │
└────────────────────────────────────────────────────┘

┌─ V2 Multi-Strategy Migration (20260214) ──────────┐
│  strategies              Strategy definitions       │
│  signals                 Trading signals            │
│  positions               Open/closed positions      │
│  dca_deals               DCA deal tracking          │
│  dca_orders              DCA order details          │
│  dca_signals             DCA signal history         │
│  strategy_templates      Strategy presets           │
└────────────────────────────────────────────────────┘

┌─ Created via create_all_tables() ─────────────────┐
│  bot_state_snapshots     State persistence (JSON)   │
└────────────────────────────────────────────────────┘

┌─ System ──────────────────────────────────────────┐
│  alembic_version         Migration tracking         │
└────────────────────────────────────────────────────┘
```

### Connection Stack

```
Python (asyncio) → asyncpg → PostgreSQL 15
                 → aiosqlite (backtesting service only)
                 → Redis 7 (pub/sub, caching)
```

---

## Web UI

### Backend (FastAPI, 1,291 LOC)

| Endpoint Group | Status | Details |
|---------------|--------|---------|
| Auth (JWT) | **REAL** | bcrypt + refresh rotation + DB sessions |
| Dashboard | **REAL** | Real bot data via orchestrator |
| Bots API | **REAL** | CRUD, start/stop |
| Market API | **REAL** | Live exchange data |
| Strategies | **REAL** | Templates persisted to DB |
| Backtesting | **REAL** | Uses `GridBacktestSimulator` |
| Settings | **REAL** | Reads from `config_manager` |
| Portfolio summary | **REAL** | Connected to orchestrator |
| Portfolio history | **STUB** | Returns empty arrays |
| WebSocket | **REAL** | RedisBridge in lifespan |

### Frontend (React + TypeScript, 6,536 LOC)

| Component | Files | Description |
|-----------|-------|-------------|
| Pages | 7 | Login, Dashboard, Bots, Strategies, Portfolio, Backtesting, Settings |
| Components | 14 | BotCard, Badge, Button, Card, Modal, Spinner, Toggle, Layout |
| Stores | 3 | authStore, botStore, uiStore (Zustand) |
| API Layer | 4 | Axios client + JWT interceptor + auto-refresh on 401 |
| Router | 2 | ProtectedRoute + index |

**Screenshots:** [`docs/screenshots/`](screenshots/) | [HTML Gallery](screenshots/index.html)

---

## Backtesting Service (standalone)

Standalone microservice under `services/backtesting/`, separate from main bot.

### Module Structure (6,377 LOC)

| Module | LOC | Description |
|--------|-----|-------------|
| `core/` | ~400 | Imports shared core from `bot.strategies.grid` + market simulator |
| `engine/` | 1,982 | Simulator, Optimizer (parallel), Clusterizer, Reporter, System |
| `api/` | ~350 | FastAPI :8100, background tasks, API key auth |
| `persistence/` | 488 | SQLite job store, preset store, JSONL checkpoints |
| `trailing/` | 193 | Trailing grid manager (fixed + ATR modes) |
| `visualization/` | 190 | Plotly charts (equity, drawdown, heatmap) |
| `caching/` | ~80 | LRU indicator cache |
| `logging/` | 133 | Structured logging (structlog) |
| Tests | 24 files | 93 tests passing |

### Known Issues (from Session 12 audit)

| # | Issue | Status |
|---|-------|--------|
| BUG-1 | Parallel optimizer reruns all trials (2x slower) | Open |
| BUG-2 | `IndicatorCache` not wired to any module | Open |
| BUG-3 | `OptimizationCheckpoint` not wired to optimizer | Open |
| BUG-4 | Trailing grid ATR mode ignored, standalone class unused | Open |
| STUB-1 | Chart endpoint returns JSON stub | Open |

---

## Docker Deployment

### Services (docker-compose.yml)

```yaml
services:
  postgres:     # PostgreSQL 15-alpine, :5432, healthcheck
  redis:        # Redis 7-alpine, :6379, healthcheck
  bot:          # Main trading bot, :9100 (metrics), :8080 (alerts)
  webui-backend:  # FastAPI, :8000
  webui-frontend: # React/Vite, :3000
  migrations:     # Alembic upgrade head (profile: migration)
```

### Volume Mounts (bot service)

```
./bot:/app/bot:ro           # Code (read-only, no rebuild needed)
./configs:/app/configs:ro   # Config files
./logs:/app/logs            # Log output
```

**Key insight:** `bot/` is mounted as a volume — `git pull` on server is enough for code updates, no Docker rebuild needed (unless `requirements.txt` changes).

### Production Server (185.233.200.13)

| Resource | Value |
|----------|-------|
| CPU | 2 cores |
| RAM | 1.9 GB (558 MB used) |
| Disk | 56 GB (17 GB used, 30%) |
| OS | Ubuntu, Linux 6.8.0 |
| Docker | Compose v2 |
| User | ai-agent (SSH key auth) |
| Git HEAD | `663c2d6` (synced with local) |
| Bot status | Stopped (intentional) |

---

## Testing

### Test Distribution (532 passing)

| Suite | Tests | Location |
|-------|-------|----------|
| Bot (unit + integration) | 385 | `bot/tests/` |
| Web API | 46 | `tests/web/` |
| State persistence | 8 | `tests/orchestrator/`, `tests/database/` |
| Backtester service | 93 | `services/backtesting/tests/` |

### Test Categories

```
tests/
├── api/              # Exchange client mocks
├── backtesting/      # Grid backtester
├── database/         # Models, migrations, backup
├── integration/      # E2E: adapters, DB persistence, multi-strategy
├── loadtest/         # Performance: API load, memory, WebSocket stress
├── orchestrator/     # Health monitor, state persistence, strategy registry
├── strategies/       # All 5 strategies: DCA(6), Grid(5), Hybrid(2), SMC(5), TF(5)
├── telegram/         # Bot integration
├── testnet/          # Testnet validation
└── web/              # Auth, bots API, portfolio, settings, strategies
```

---

## Configuration

### Config Files

| File | Purpose |
|------|---------|
| `configs/phase7_demo.yaml` | **Main config** — 4 demo bots (Bybit) |
| `configs/example.yaml` | Template for new deployments |
| `configs/trend_follower_production.yaml` | Trend Follower settings |
| `configs/demo_trading.yaml` | Demo variant |
| `configs/bybit_example.yaml` | Bybit-specific example |
| `.env` | DB password, encryption key, Telegram token |
| `alembic.ini.example` | Database migration config |

### Environment Variables

```
DATABASE_URL          # PostgreSQL connection string
ENCRYPTION_KEY        # AES-256 key for API credentials
TELEGRAM_BOT_TOKEN    # Telegram bot token
TELEGRAM_ALLOWED_CHAT_IDS  # Authorized Telegram users
CONFIG_FILE           # Active YAML config (default: phase7_demo.yaml)
LOG_LEVEL             # DEBUG / INFO / WARNING
```

---

## Monitoring Stack

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Bot Metrics  │───►│  Prometheus   │───►│   Grafana     │
│  :9100        │    │  :9090        │    │   :3000       │
└──────────────┘    └──────┬───────┘    └──────────────┘
                           │
                    ┌──────▼───────┐
                    │ AlertManager  │──► Telegram
                    │  :9093        │
                    └──────────────┘
```

**Metrics collected:** portfolio value, PnL, drawdown, trade count, win rate, API latency, error rate, DB connections, CPU/memory.

---

## Key Files Reference

```
# Entry Points
bot/main.py                              # Bot entry point (342 LOC)
web/backend/main.py                      # Web backend entry
web/frontend/src/main.tsx                 # React entry

# Core Trading
bot/orchestrator/bot_orchestrator.py      # Main loop (1,377 LOC)
bot/orchestrator/state_persistence.py     # State snapshots (380 LOC)
bot/api/exchange_client.py               # CCXT client (672 LOC)
bot/api/bybit_direct_client.py           # Bybit V5 native (1,024 LOC)
bot/core/grid_engine.py                  # Grid engine (377 LOC)
bot/core/dca_engine.py                   # DCA engine (388 LOC)
bot/core/risk_manager.py                 # Risk manager (~300 LOC)

# Strategies
bot/strategies/grid/                     # Grid (6 files, 1,982 LOC)
bot/strategies/dca/                      # DCA (8 files, 3,454 LOC)
bot/strategies/hybrid/                   # Hybrid (4 files, 1,228 LOC)
bot/strategies/smc/                      # SMC (7 files, 2,725 LOC)
bot/strategies/trend_follower/           # Trend Follower (8 files, 2,537 LOC)

# Database
bot/database/manager.py                  # DB manager + create_all_tables()
bot/database/models.py                   # V1 models
bot/database/models_v2.py                # V2 multi-strategy models
bot/database/models_state.py             # BotStateSnapshot
alembic/versions/                        # 2 migrations

# Web UI
web/backend/api/v1/                      # REST API endpoints
web/backend/auth/                        # JWT auth
web/frontend/src/pages/                  # 7 React pages
web/frontend/src/api/client.ts           # Axios + JWT interceptor

# Backtesting Service
services/backtesting/src/grid_backtester/  # Standalone service
services/backtesting/Dockerfile            # Multi-stage build
services/backtesting/docker-compose.yml    # Port 8100

# Infrastructure
docker-compose.yml                       # 6 services
Dockerfile                               # Bot container
requirements.txt                         # Python dependencies
configs/phase7_demo.yaml                 # Active config
```

---

## Data Flow

### Trading Cycle

```
Market Data (Bybit API)
    │
    ▼
Orchestrator._main_loop()
    │
    ├─► Strategy.analyze(candles, orderbook)
    │       │
    │       ▼
    │   Signal: BUY / SELL / HOLD
    │       │
    │       ▼
    ├─► RiskManager.check(signal, balance, positions)
    │       │
    │       ▼
    │   Approved / Rejected
    │       │
    │       ▼
    ├─► ExchangeClient.create_order(symbol, side, amount, price)
    │       │
    │       ▼
    │   Order placed on exchange
    │       │
    │       ▼
    ├─► DatabaseManager.save_order(order)
    │       │
    │       ▼
    ├─► StatePersistence.save_snapshot() (every 30s)
    │       │
    │       ▼
    └─► TelegramBot.notify(trade_info)
```

### State Persistence

```
Bot Running
    │
    ├─ Every 30s ─► serialize engines ─► PostgreSQL (bot_state_snapshots)
    │
    ├─ On stop() ─► final snapshot ─► PostgreSQL
    │
    └─ On start() ─► load snapshot ─► reconcile_with_exchange()
                                          │
                                          ├─ Check open orders (filled? orphaned?)
                                          ├─ Refresh balance
                                          └─ Resume trading from saved state
```

---

## Deployment Workflow

### Code Update (no rebuild)

```bash
# On server (185.233.200.13)
cd ~/TRADERAGENT
git pull origin main
# Done — volume mount picks up changes automatically
```

### Full Rebuild (when requirements.txt changes)

```bash
cd ~/TRADERAGENT
git pull origin main
docker compose build bot
docker compose up -d bot
```

### Database Migration

```bash
# Auto: via create_all_tables() (safe, idempotent)
docker compose run --rm bot python -c "
import asyncio
from bot.database import DatabaseManager
async def main():
    dm = DatabaseManager('postgresql+asyncpg://...')
    await dm.initialize()
    await dm.create_all_tables()
asyncio.run(main())
"

# Manual: via alembic
docker compose run --rm migrations alembic upgrade head
```

---

## Last Updated

- **Date:** February 17, 2026
- **Git HEAD:** `663c2d6`
- **Co-Authored:** Claude Opus 4.6
