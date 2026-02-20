# ARCHITECTURE — TRADERAGENT v2.0

> Autonomous multi-strategy cryptocurrency trading platform
> Stack: Python 3.12 | asyncio | PostgreSQL | Redis | FastAPI | React | Docker

---

## 1. System Overview

```mermaid
graph TB
    subgraph External["External Services"]
        BYBIT["Bybit Exchange<br/>(api-demo.bybit.com)"]
        TG_API["Telegram API"]
        PROM["Prometheus"]
    end

    subgraph Docker["Docker Compose Cluster"]
        subgraph Bot["traderagent-bot"]
            APP["BotApplication"]
            ORCH["BotOrchestrator ×N"]
            STRAT["Strategy Registry"]
            EXCH["Exchange Client"]
            TGBOT["Telegram Bot"]
            MON["Metrics Exporter<br/>:9100"]
        end

        PG[("PostgreSQL 15<br/>Orders, Trades,<br/>Credentials, State")]
        REDIS[("Redis 7<br/>Pub/Sub Events")]

        subgraph WebUI["Web UI"]
            BACK["FastAPI Backend<br/>:8000"]
            FRONT["React Frontend<br/>:3000 (nginx)"]
        end

        subgraph Backtest["Backtesting Service"]
            BT_API["Backtest API"]
            BT_ENG["Simulator + Optimizer"]
        end
    end

    APP --> ORCH
    ORCH --> STRAT
    ORCH --> EXCH
    EXCH -->|REST API / WebSocket| BYBIT
    ORCH -->|events| REDIS
    ORCH -->|CRUD| PG
    TGBOT -->|commands| ORCH
    TGBOT --> TG_API
    REDIS -->|subscribe| TGBOT
    REDIS -->|WebSocket bridge| BACK
    BACK --> PG
    FRONT -->|API + WS| BACK
    MON --> PROM
    BT_ENG --> PG

    style Docker fill:#1a1a2e,stroke:#16213e,color:#fff
    style Bot fill:#0f3460,stroke:#533483,color:#fff
    style WebUI fill:#0f3460,stroke:#533483,color:#fff
    style Backtest fill:#0f3460,stroke:#533483,color:#fff
    style External fill:#533483,stroke:#e94560,color:#fff
```

---

## 2. Directory Structure

```
TRADERAGENT/
├── bot/                            # Core trading bot
│   ├── main.py                     # Entry point — bootstraps everything
│   ├── api/                        # Exchange connectivity
│   │   ├── exchange_client.py      #   CCXT unified wrapper
│   │   ├── bybit_direct_client.py  #   Bybit V5 direct API (demo)
│   │   └── exceptions.py           #   Custom exchange errors
│   ├── config/                     # Configuration
│   │   ├── manager.py              #   YAML loader + hot reload
│   │   └── schemas.py              #   Pydantic validation models
│   ├── core/                       # Trading engines
│   │   ├── grid_engine.py          #   Grid order placement
│   │   ├── dca_engine.py           #   Dollar-cost averaging
│   │   └── risk_manager.py         #   Capital protection
│   ├── database/                   # Persistence layer
│   │   ├── manager.py              #   Async SQLAlchemy operations
│   │   ├── models.py               #   v1 schema (credentials, orders)
│   │   ├── models_v2.py            #   v2 schema (strategies, signals)
│   │   └── models_state.py         #   State snapshots
│   ├── orchestrator/               # Multi-strategy coordination
│   │   ├── bot_orchestrator.py     #   Main trading loop
│   │   ├── strategy_registry.py    #   Strategy lifecycle manager
│   │   ├── strategy_selector.py    #   Dynamic strategy selection
│   │   ├── events.py               #   Redis Pub/Sub event system
│   │   ├── health_monitor.py       #   Auto-restart on failure
│   │   └── state_persistence.py    #   Crash recovery
│   ├── strategies/                 # Strategy implementations
│   │   ├── base.py                 #   BaseStrategy ABC
│   │   ├── grid/                   #   Grid strategy (6 files)
│   │   ├── dca/                    #   DCA strategy (5 files)
│   │   ├── smc/                    #   Smart Money Concepts (5 files)
│   │   ├── trend_follower/         #   Trend follower (6 files)
│   │   ├── hybrid/                 #   Grid+DCA hybrid (2 files)
│   │   └── *_adapter.py            #   Adapters to BaseStrategy
│   ├── telegram/bot.py             # Telegram control & alerts
│   └── monitoring/                 # Prometheus metrics + alerts
├── web/                            # Web dashboard
│   ├── backend/                    #   FastAPI (42 routes + WS)
│   └── frontend/                   #   React + TypeScript (7 pages)
├── services/backtesting/           # Backtesting microservice
├── configs/                        # YAML configurations
├── tests/                          # 1884 tests (100% pass rate)
├── alembic/                        # DB migrations
├── docker-compose.yml              # Production deployment
└── Dockerfile
```

---

## 3. Bot Lifecycle

```mermaid
stateDiagram-v2
    [*] --> STOPPED
    STOPPED --> STARTING: start()
    STARTING --> RUNNING: initialized
    RUNNING --> PAUSED: pause()
    PAUSED --> RUNNING: resume()
    RUNNING --> STOPPING: stop()
    PAUSED --> STOPPING: stop()
    STOPPING --> STOPPED: cleanup done
    RUNNING --> EMERGENCY: critical risk
    EMERGENCY --> STOPPING: operator ack

    state RUNNING {
        [*] --> FetchPrice
        FetchPrice --> ProcessGrid: grid enabled
        FetchPrice --> ProcessDCA: dca enabled
        FetchPrice --> ProcessTrend: trend enabled
        ProcessGrid --> UpdateRisk
        ProcessDCA --> UpdateRisk
        ProcessTrend --> UpdateRisk
        UpdateRisk --> SaveState: every 30s
        SaveState --> Sleep1s
        Sleep1s --> FetchPrice
    }
```

---

## 4. Strategy Architecture

```mermaid
graph TB
    subgraph Registry["Strategy Registry"]
        direction TB
        BS["BaseStrategy ABC<br/>analyze() → Signal"]
    end

    subgraph Strategies["5 Strategy Implementations"]
        GRID["Grid Strategy<br/>arithmetic / geometric levels<br/>buy low → sell high"]
        DCA["DCA Strategy<br/>safety orders on dip<br/>average down + TP"]
        SMC["SMC Strategy<br/>BOS / CHoCH / OB / FVG<br/>confluence zones"]
        TREND["Trend Follower<br/>EMA pullback / breakout<br/>trailing stop"]
        HYBRID["Hybrid Strategy<br/>Grid + DCA adaptive<br/>regime-based switching"]
    end

    subgraph Adapters["Adapter Layer"]
        GA["GridAdapter"]
        DA["DCAAdapter"]
        SA["SMCAdapter"]
        TA["TrendFollowerAdapter"]
    end

    GRID --> GA
    DCA --> DA
    SMC --> SA
    TREND --> TA

    GA --> BS
    DA --> BS
    SA --> BS
    TA --> BS
    HYBRID --> BS

    subgraph Regime["Market Regime Detector"]
        MRD["ADX + EMA + ATR + Volume"]
    end

    MRD -->|recommends| Registry

    style Strategies fill:#1a1a2e,stroke:#e94560,color:#fff
    style Registry fill:#16213e,stroke:#0f3460,color:#fff
    style Adapters fill:#16213e,stroke:#533483,color:#fff
    style Regime fill:#533483,stroke:#e94560,color:#fff
```

### Strategy Selection by Market Regime

```mermaid
graph LR
    subgraph Regimes["Market Regimes"]
        TR["TIGHT_RANGE<br/>ADX < 18, ATR < 1%"]
        WR["WIDE_RANGE<br/>ADX < 18, ATR >= 1%"]
        QT["QUIET_TRANSITION<br/>ADX 22-32, ATR < 2%"]
        VT["VOLATILE_TRANSITION<br/>ADX 22-32, ATR >= 2%"]
        BULL["BULL_TREND<br/>ADX > 32, EMA20 > 50"]
        BEAR["BEAR_TREND<br/>ADX > 32, EMA20 < 50"]
    end

    TR -->|"Grid (arithmetic)"| G1["Grid Bot"]
    WR -->|"Grid (geometric)"| G2["Grid Bot"]
    QT -->|"Grid (cautious, range×0.7)"| G3["Grid Bot"]
    VT -->|"DCA (cautious)"| D1["DCA Bot"]
    BULL -->|"Trend Follower (long)"| T1["Trend Bot"]
    BEAR -->|"DCA (accumulation)"| D2["DCA Bot"]

    style Regimes fill:#1a1a2e,stroke:#533483,color:#fff
```

---

## 5. Data Flow

```mermaid
sequenceDiagram
    participant EX as Bybit Exchange
    participant EC as ExchangeClient
    participant BO as BotOrchestrator
    participant SR as StrategyRegistry
    participant RM as RiskManager
    participant DB as PostgreSQL
    participant RD as Redis
    participant TG as Telegram Bot
    participant WS as WebSocket (UI)

    loop Every 1 second
        BO->>EC: fetch_ticker(BTCUSDT)
        EC->>EX: GET /v5/market/tickers
        EX-->>EC: {last: 67740.5}
        EC-->>BO: price update

        BO->>EC: fetch_open_orders()
        EC->>EX: GET /v5/order/realtime
        EX-->>EC: [6 orders]
        EC-->>BO: order status

        BO->>SR: analyze(ohlcv_data)
        SR-->>BO: Signal(LONG, entry=67500)

        BO->>RM: validate(signal)
        RM-->>BO: approved (size=0.002)

        BO->>EC: create_order(BUY, 0.002, 67500)
        EC->>EX: POST /v5/order/create
        EX-->>EC: order_id

        BO->>DB: INSERT order
        BO->>RD: PUBLISH order_placed

        RD-->>TG: event notification
        TG->>TG: send message
        RD-->>WS: push to browser
    end
```

---

## 6. Database Schema

```mermaid
erDiagram
    exchange_credentials {
        int id PK
        string name UK
        string exchange_id
        text api_key_encrypted
        text api_secret_encrypted
        bool is_sandbox
        bool is_active
    }

    bots {
        int id PK
        string name UK
        int credentials_id FK
        string symbol
        string strategy
        string status
        json config_data
    }

    orders {
        int id PK
        int bot_id FK
        string symbol
        string side
        decimal amount
        decimal price
        string exchange_order_id
        string status
        datetime created_at
    }

    trades {
        int id PK
        int order_id FK
        decimal entry_price
        decimal exit_price
        decimal profit_loss
        datetime filled_at
    }

    strategies_v2 {
        int id PK
        string strategy_id UK
        string strategy_type
        int bot_id FK
        string state
        json config_data
        int total_signals
        int executed_trades
        decimal total_pnl
    }

    signals_v2 {
        int id PK
        int strategy_id FK
        string direction
        decimal entry_price
        decimal stop_loss
        decimal take_profit
        float confidence
        datetime timestamp
    }

    positions_v2 {
        int id PK
        int strategy_id FK
        string symbol
        string direction
        decimal entry_price
        decimal size
        string status
        datetime created_at
        datetime closed_at
    }

    bot_state_snapshots {
        int id PK
        string bot_name UK
        text bot_state
        text grid_state
        text dca_state
        text risk_state
        text trend_state
        text hybrid_state
        datetime saved_at
    }

    exchange_credentials ||--o{ bots : "credentials_id"
    bots ||--o{ orders : "bot_id"
    bots ||--o{ strategies_v2 : "bot_id"
    orders ||--o| trades : "order_id"
    strategies_v2 ||--o{ signals_v2 : "strategy_id"
    strategies_v2 ||--o{ positions_v2 : "strategy_id"
```

---

## 7. Exchange Integration

```mermaid
graph TB
    subgraph Clients["Exchange Clients"]
        CCXT["ExchangeAPIClient<br/>(CCXT Wrapper)<br/>Binance, OKX, Kraken"]
        DIRECT["ByBitDirectClient<br/>(Direct V5 API)<br/>api-demo.bybit.com"]
    end

    subgraph Selection["Auto-Selection Logic<br/>(bot/main.py)"]
        CHECK{"exchange_id == 'bybit'<br/>AND sandbox == true?"}
    end

    CHECK -->|Yes| DIRECT
    CHECK -->|No| CCXT

    subgraph API["Bybit V5 Endpoints"]
        MARKET["/v5/market/tickers<br/>/v5/market/kline<br/>/v5/market/instruments-info"]
        TRADE["/v5/order/create<br/>/v5/order/cancel<br/>/v5/order/realtime"]
        ACCOUNT["/v5/account/wallet-balance<br/>/v5/position/list"]
    end

    DIRECT --> MARKET
    DIRECT --> TRADE
    DIRECT --> ACCOUNT

    subgraph Features["Client Features"]
        RL["Async Rate Limiting<br/>(non-blocking)"]
        RETRY["Retry with Backoff<br/>(tenacity)"]
        SIGN["HMAC-SHA256 Signing<br/>(api_key + timestamp)"]
    end

    DIRECT --- RL
    DIRECT --- RETRY
    DIRECT --- SIGN

    style Clients fill:#0f3460,stroke:#533483,color:#fff
    style Selection fill:#533483,stroke:#e94560,color:#fff
    style API fill:#1a1a2e,stroke:#16213e,color:#fff
```

---

## 8. Event System

```mermaid
graph LR
    subgraph Producers["Event Producers"]
        BO["BotOrchestrator"]
        HM["HealthMonitor"]
        RM["RiskManager"]
    end

    subgraph Bus["Redis Pub/Sub"]
        CH["Channel:<br/>trading_events:{bot_name}"]
    end

    subgraph Consumers["Event Consumers"]
        TG["Telegram Bot<br/>→ user notifications"]
        WS["WebSocket Bridge<br/>→ browser updates"]
        MC["MetricsCollector<br/>→ Prometheus"]
        AH["AlertHandler<br/>→ risk alerts"]
    end

    BO -->|publish| CH
    HM -->|publish| CH
    RM -->|publish| CH

    CH -->|subscribe| TG
    CH -->|subscribe| WS
    CH -->|subscribe| MC
    CH -->|subscribe| AH

    subgraph EventTypes["Event Types"]
        direction TB
        E1["BOT_STARTED / STOPPED / PAUSED"]
        E2["ORDER_PLACED / FILLED / FAILED"]
        E3["TAKE_PROFIT_HIT / STOP_LOSS"]
        E4["PRICE_UPDATED / BALANCE_UPDATED"]
        E5["HEALTH_CRITICAL / STRATEGY_ERROR"]
        E6["MARKET_REGIME_CHANGED"]
    end

    style Bus fill:#e94560,stroke:#533483,color:#fff
    style Producers fill:#0f3460,stroke:#533483,color:#fff
    style Consumers fill:#0f3460,stroke:#533483,color:#fff
    style EventTypes fill:#1a1a2e,stroke:#16213e,color:#fff
```

---

## 9. Web UI Architecture

```mermaid
graph TB
    subgraph Frontend["React Frontend (:3000)"]
        PAGES["Pages:<br/>Dashboard | Bots | Strategies<br/>Portfolio | Backtesting | Settings | Login"]
        STORE["Zustand Stores:<br/>auth | bots | UI"]
        APIC["API Client (Axios)<br/>+ WebSocket"]
    end

    subgraph Nginx["nginx"]
        SPA["SPA routing<br/>→ index.html"]
        PROXY["/api/* → :8000<br/>/ws/* → :8000"]
    end

    subgraph Backend["FastAPI Backend (:8000)"]
        AUTH["JWT Auth<br/>login / register / refresh"]
        ROUTES["REST API v1"]
        WSM["WebSocket Manager"]
        BRIDGE["Redis Bridge"]
    end

    subgraph Endpoints["42 API Routes"]
        direction TB
        R1["/api/v1/dashboard — stats"]
        R2["/api/v1/bots — CRUD + control"]
        R3["/api/v1/strategies — list + config"]
        R4["/api/v1/portfolio — positions + PnL"]
        R5["/api/v1/market — ticker + OHLCV"]
        R6["/api/v1/backtesting — jobs"]
        R7["/api/v1/settings — config"]
    end

    PAGES --> STORE
    STORE --> APIC
    APIC --> SPA
    SPA --> PROXY
    PROXY --> AUTH
    AUTH --> ROUTES
    ROUTES --- Endpoints
    WSM --> BRIDGE
    BRIDGE --> REDIS[("Redis")]

    style Frontend fill:#0f3460,stroke:#533483,color:#fff
    style Backend fill:#0f3460,stroke:#533483,color:#fff
    style Endpoints fill:#1a1a2e,stroke:#16213e,color:#fff
```

---

## 10. Deployment Architecture

```mermaid
graph TB
    subgraph Server["Production Server<br/>185.233.200.13"]
        subgraph DC["Docker Compose"]
            BOT["traderagent-bot<br/>Python 3.11<br/>Volume: ./bot:/app/bot:ro"]
            PG["postgres:15<br/>Port: 5432<br/>Volume: pg_data"]
            RD["redis:7<br/>Port: 6379"]
            WEB_B["webui-backend<br/>FastAPI :8000"]
            WEB_F["webui-frontend<br/>nginx :3000"]
        end
    end

    subgraph Deploy["Deployment Flow"]
        D1["1. tar czf sync.tar.gz bot/"]
        D2["2. scp → server"]
        D3["3. tar xzf"]
        D4["4. docker compose restart bot"]
    end

    D1 --> D2 --> D3 --> D4
    D4 --> BOT

    BOT -->|asyncpg| PG
    BOT -->|aioredis| RD
    WEB_B -->|asyncpg| PG
    WEB_B -->|aioredis| RD
    WEB_F -->|proxy /api| WEB_B

    subgraph Env[".env (secrets)"]
        E1["DATABASE_URL"]
        E2["ENCRYPTION_KEY"]
        E3["TELEGRAM_BOT_TOKEN"]
    end

    Env --> BOT

    style Server fill:#1a1a2e,stroke:#e94560,color:#fff
    style DC fill:#0f3460,stroke:#533483,color:#fff
    style Deploy fill:#16213e,stroke:#533483,color:#fff
    style Env fill:#533483,stroke:#e94560,color:#fff
```

---

## 11. Backtesting System

```mermaid
graph TB
    subgraph Pipeline["Backtest Pipeline"]
        direction TB
        INPUT["OHLCV CSV Data<br/>45 pairs × 10 timeframes<br/>5.4 GB"]
        CLASSIFY["CoinClusterizer<br/>ATR% + Volume → cluster"]
        SIM["GridBacktestSimulator<br/>walk-forward simulation"]
        OPT["GridOptimizer<br/>coarse → fine search"]
        STRESS["Stress Test<br/>regime-specific metrics"]
        REPORT["Reporter<br/>JSON + YAML preset"]
    end

    INPUT --> CLASSIFY --> SIM --> OPT --> STRESS --> REPORT

    subgraph Components["Reused from Production"]
        GC["GridCalculator"]
        GOM["GridOrderManager"]
        GRM["GridRiskManager"]
        MS["MarketSimulator"]
    end

    Components --> SIM

    subgraph Output["Results"]
        JSON["backtest_results/<br/>{SYMBOL}_backtest.json"]
        PRESET["backtest_results/<br/>{SYMBOL}_preset.yaml"]
        SQLITE["presets.db<br/>(preset library)"]
    end

    REPORT --> JSON
    REPORT --> PRESET
    REPORT --> SQLITE

    style Pipeline fill:#0f3460,stroke:#533483,color:#fff
    style Components fill:#16213e,stroke:#533483,color:#fff
    style Output fill:#1a1a2e,stroke:#e94560,color:#fff
```

---

## 12. State Persistence & Crash Recovery

```mermaid
sequenceDiagram
    participant BO as BotOrchestrator
    participant SP as StateSerializer
    participant DB as PostgreSQL
    participant EX as Exchange

    Note over BO: Normal operation — save every 30s
    loop Every 30 seconds
        BO->>SP: serialize(grid, dca, risk, trend, hybrid)
        SP->>DB: UPSERT bot_state_snapshots
        DB-->>SP: saved_at = now()
    end

    Note over BO: Crash happens!
    BO-xBO: Process killed

    Note over BO: Restart
    BO->>DB: SELECT * FROM bot_state_snapshots<br/>WHERE bot_name = 'demo_btc_hybrid'
    DB-->>BO: snapshot (grid_state, dca_state, ...)

    BO->>SP: deserialize(snapshot)
    SP-->>BO: engines restored

    BO->>EX: fetch_open_orders()
    EX-->>BO: [6 orders]
    BO->>BO: reconcile_with_exchange()<br/>match saved orders with live
    Note over BO: Resume trading
```

---

## 13. Security Model

```mermaid
graph TB
    subgraph Secrets["Credential Security"]
        FERNET["Fernet (AES-128-CBC)<br/>ENCRYPTION_KEY from .env"]
        ENC_DB["PostgreSQL<br/>api_key_encrypted<br/>api_secret_encrypted"]
    end

    subgraph Auth["Web Authentication"]
        JWT["JWT Tokens<br/>bcrypt password hashing"]
        SESSIONS["UserSession table<br/>token expiry enforcement"]
    end

    subgraph Access["Access Control"]
        TG_WL["Telegram: chat_id whitelist"]
        CORS["CORS: frontend origin only"]
        RO["Docker volume: read-only<br/>./bot:/app/bot:ro"]
    end

    subgraph Exchange["Exchange Safety"]
        RATE["Async rate limiter<br/>per-exchange limits"]
        RETRY["Tenacity retry<br/>exponential backoff"]
        VALID["Pydantic validation<br/>all order params"]
    end

    FERNET --> ENC_DB
    JWT --> SESSIONS

    style Secrets fill:#e94560,stroke:#533483,color:#fff
    style Auth fill:#0f3460,stroke:#533483,color:#fff
    style Access fill:#0f3460,stroke:#533483,color:#fff
    style Exchange fill:#16213e,stroke:#533483,color:#fff
```

---

## 14. Strategy Capabilities Matrix

| Strategy | Entry Logic | Exit Logic | Risk Management | Best Market |
|:---------|:-----------|:-----------|:----------------|:------------|
| **Grid** | Price hits grid level | Counter-order at next level | Max position size, stop-loss | Sideways / Range |
| **DCA** | Price drops N% from entry | Take profit at avg + M% | Max steps, daily loss limit | Dips / Bear market |
| **Trend Follower** | EMA pullback / breakout | Trailing stop, ATR-based TP | 1-2% risk per trade | Trending market |
| **SMC** | Confluence zone + pattern | Dynamic SL/TP, partial close | Kelly criterion sizing | Price action setups |
| **Hybrid** | Grid in range, DCA on breakout | Context-dependent | Combined limits | Mixed / Uncertain |

---

## 15. Monitoring Stack

```mermaid
graph LR
    BOT["Trading Bot<br/>MetricsExporter :9100"]
    PROM["Prometheus<br/>scrape interval: 15s"]
    GRAF["Grafana<br/>dashboards"]
    TG["Telegram Bot<br/>alert notifications"]
    REDIS["Redis Pub/Sub<br/>event stream"]

    BOT -->|"/metrics"| PROM
    PROM --> GRAF
    BOT -->|events| REDIS
    REDIS --> TG

    subgraph Metrics["Exported Metrics"]
        direction TB
        M1["bot_status (running/stopped)"]
        M2["bot_balance_usdt"]
        M3["bot_open_orders_count"]
        M4["bot_trades_total"]
        M5["bot_pnl_daily_usdt"]
        M6["bot_drawdown_pct"]
        M7["exchange_latency_ms"]
    end

    BOT --- Metrics

    style Metrics fill:#1a1a2e,stroke:#16213e,color:#fff
```

---

## 16. Testing Architecture

```
Total: 1884 tests | Pass rate: 100% (1859 passed, 25 skipped)
```

```mermaid
pie title Test Distribution by Module
    "Strategies (Grid/DCA/SMC/Trend/Hybrid)" : 743
    "Bot Core (unit)" : 385
    "Orchestrator" : 143
    "Root tests" : 139
    "Integration" : 108
    "Database" : 84
    "API" : 75
    "Telegram" : 55
    "Web UI" : 46
    "Load/Stress" : 40
    "Backtesting" : 39
    "Testnet" : 27
```

---

## 17. Configuration Example

```yaml
# configs/phase7_demo.yaml
database_url: ${DATABASE_URL}
log_level: INFO
encryption_key: ${ENCRYPTION_KEY}
telegram_bot_token: ${TELEGRAM_BOT_TOKEN}
telegram_chat_id: ${TELEGRAM_CHAT_ID}

bots:
  - name: demo_btc_hybrid
    symbol: BTC/USDT
    strategy: hybrid
    exchange:
      exchange_id: bybit
      credentials_name: bybit_demo
      sandbox: true              # → api-demo.bybit.com

    grid:
      enabled: true
      upper_price: "72000"
      lower_price: "65000"
      grid_levels: 6
      amount_per_grid: "150"
      profit_per_grid: "0.012"

    dca:
      enabled: true
      trigger_percentage: "0.04"
      amount_per_step: "150"
      max_steps: 4
      take_profit_percentage: "0.08"

    risk_management:
      max_position_size: "3000"
      stop_loss_percentage: "0.12"
      max_daily_loss: "600"

    dry_run: false
    auto_start: true
```

---

## 18. Key Design Decisions

| Decision | Rationale |
|:---------|:----------|
| **ByBitDirectClient** instead of CCXT sandbox | CCXT `set_sandbox_mode(True)` routes to `testnet.bybit.com` (wrong). Demo trading requires `api-demo.bybit.com` |
| **Linear futures only** for demo | Bybit demo does not support spot trading |
| **Adapter pattern** for strategies | Unified `BaseStrategy` interface lets `StrategyRegistry` manage all types uniformly |
| **Redis Pub/Sub** for events | Decouples producers (bot) from consumers (Telegram, Web UI, monitoring) |
| **Read-only volume mount** | `./bot:/app/bot:ro` — code changes via tar/scp, no Docker rebuild needed |
| **State snapshots** every 30s | Crash recovery without losing grid/DCA/risk state |
| **asyncpg** (not psycopg2) | Native async PostgreSQL driver — no thread pool overhead |
| **Fernet encryption** for API keys | AES-128-CBC, keys never stored in plaintext |
| **SMC as filter, not strategy** | Filters only ENTRY signals; exit/SL/TP/grid-counter bypass SMC |
| **HYBRID removed** in v2.0 design | Function moved to Strategy Router — eliminates double routing |

---

## 19. v2.0 Algorithm Architecture (Planned)

```mermaid
graph TB
    subgraph MasterLoop["Master Loop (60s cycle)"]
        RC["RegimeClassifier<br/>6 regimes with hysteresis"]
        CA["CapitalAllocator<br/>committed / available capital"]
        RA["RiskAggregator<br/>trade → pair → portfolio"]
    end

    subgraph StrategyLoop["Strategy Loop (1-5s cycle)"]
        SR["Strategy Router<br/>(replaces HYBRID)"]
        SF["SMC Filter<br/>confidence_decay, max 2 touches"]
        GT["Graceful Transition<br/>lock + 2h timeout"]
    end

    subgraph Strategies
        G["Grid"]
        D["DCA"]
        T["Trend Follower"]
    end

    RC -->|regime| SR
    CA -->|budget| SR
    SR -->|select| Strategies
    SF -->|filter ENTRY| Strategies
    GT -->|safe switch| SR
    RA -->|limits| SR

    subgraph Emergency["Emergency Halt"]
        EH["3-stage protocol<br/>1. Freeze new orders<br/>2. Close positions<br/>3. Operator notification"]
    end

    RA -->|portfolio drawdown > 15%| Emergency

    style MasterLoop fill:#0f3460,stroke:#533483,color:#fff
    style StrategyLoop fill:#16213e,stroke:#533483,color:#fff
    style Emergency fill:#e94560,stroke:#533483,color:#fff
```

---

## 20. Quick Reference

```bash
# Run ALL tests (1884)
python -m pytest bot/tests/ tests/ --ignore=bot/tests/testnet -q

# Deploy code to server
tar czf /tmp/sync.tar.gz bot/ && \
scp /tmp/sync.tar.gz ai-agent@185.233.200.13:/tmp/ && \
ssh ai-agent@185.233.200.13 "cd ~/TRADERAGENT && tar xzf /tmp/sync.tar.gz"

# Restart bot
ssh ai-agent@185.233.200.13 "cd ~/TRADERAGENT && docker compose restart bot"

# View logs
ssh ai-agent@185.233.200.13 "docker logs traderagent-bot --since 5m"

# Start web UI
docker compose up webui-backend webui-frontend

# Run backtesting
docker compose run --rm bot python scripts/run_grid_backtest_all.py \
  --data-dir /app/data/historical --symbols BTC,ETH,SOL
```

---

> **Last updated:** February 20, 2026 | **Session:** 15 | **Commit:** `7d84e8d`
> **Co-Authored:** Claude Opus 4.6
