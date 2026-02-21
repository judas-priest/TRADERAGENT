# ARCHITECTURE — TRADERAGENT v2.1

> Autonomous multi-strategy cryptocurrency trading platform
> Stack: Python 3.12 | asyncio | PostgreSQL | Redis | FastAPI | React | Docker
> Updated: February 21, 2026 | 468 commits | 202 files | 60,891 LOC | 1,534 tests

---

## 1. System Overview

```mermaid
graph TB
    subgraph External["External Services"]
        BYBIT["Bybit Exchange<br/>(api-demo.bybit.com)"]
        TG_API["Telegram API"]
        PROM["Prometheus"]
    end

    subgraph Docker["Docker Compose Cluster — 185.233.200.13"]
        subgraph Bot["traderagent-bot"]
            APP["BotApplication<br/>(main.py, 339 LOC)"]
            ORCH["BotOrchestrator ×5<br/>(1,622 LOC)"]
            STRAT["Strategy Registry<br/>(357 LOC)"]
            EXCH["Exchange Client<br/>(1,813 LOC)"]
            TGBOT["Telegram Bot<br/>(844 LOC)"]
            MON["Metrics Exporter<br/>:9100"]
        end

        PG[("PostgreSQL 15<br/>Orders, Trades,<br/>Credentials, State")]
        REDIS[("Redis 7<br/>Pub/Sub Events")]

        subgraph WebUI["Web UI Dashboard"]
            BACK["FastAPI Backend<br/>:8000 (42 routes)"]
            FRONT["React Frontend<br/>:3000 (nginx, 7 pages)"]
        end

        subgraph Backtest["Backtesting Engine"]
            BT_ENG["MultiTF Engine<br/>(1,067 LOC)"]
            BT_SIM["Market Simulator<br/>SHORT + LONG"]
        end
    end

    APP --> ORCH
    ORCH --> STRAT
    ORCH --> EXCH
    EXCH -->|REST API| BYBIT
    ORCH -->|events| REDIS
    ORCH -->|CRUD| PG
    TGBOT -->|commands| ORCH
    TGBOT --> TG_API
    REDIS -->|subscribe| TGBOT
    REDIS -->|WebSocket bridge| BACK
    BACK --> PG
    FRONT -->|API + WS| BACK
    MON --> PROM
    BT_ENG --> STRAT

    style Docker fill:#1a1a2e,stroke:#16213e,color:#fff
    style Bot fill:#0f3460,stroke:#533483,color:#fff
    style WebUI fill:#0f3460,stroke:#533483,color:#fff
    style Backtest fill:#0f3460,stroke:#533483,color:#fff
    style External fill:#533483,stroke:#e94560,color:#fff
```

---

## 2. Directory Structure

```
TRADERAGENT/                          468 commits, 60,891 LOC
├── bot/                              Core trading bot
│   ├── main.py                       Entry point — bootstraps everything (339 LOC)
│   ├── api/                          Exchange connectivity (1,813 LOC)
│   │   ├── exchange_client.py          CCXT unified wrapper (671 LOC)
│   │   ├── bybit_direct_client.py      Bybit V5 direct API for demo (1,014 LOC)
│   │   └── exceptions.py               Custom exchange errors
│   ├── config/                       Configuration
│   │   ├── manager.py                  YAML loader + env substitution
│   │   └── schemas.py                  Pydantic validation models (454 LOC)
│   ├── core/                         Trading engines
│   │   ├── grid_engine.py              Grid order placement
│   │   ├── dca_engine.py               Dollar-cost averaging
│   │   └── risk_manager.py             Capital protection (384 LOC)
│   ├── database/                     Persistence layer
│   │   ├── manager.py                  Async SQLAlchemy operations
│   │   ├── models.py                   v1 schema (credentials, orders)
│   │   ├── models_v2.py                v2 schema (strategies, signals, positions)
│   │   └── models_state.py             State snapshots
│   ├── orchestrator/                 Multi-strategy coordination (3,990 LOC)
│   │   ├── bot_orchestrator.py         Main trading loop (1,622 LOC)
│   │   ├── strategy_registry.py        Strategy lifecycle manager (357 LOC)
│   │   ├── strategy_selector.py        Dynamic strategy selection (469 LOC)
│   │   ├── market_regime.py            ADX/EMA/ATR regime detection (693 LOC)
│   │   ├── events.py                   Redis Pub/Sub event system (154 LOC)
│   │   ├── health_monitor.py           Auto-restart on failure (330 LOC)
│   │   └── state_persistence.py        Crash recovery (365 LOC)
│   ├── strategies/                   5 strategy families (33 files, ~7,000 LOC)
│   │   ├── base.py                     BaseStrategy ABC (325 LOC)
│   │   ├── grid/                       Grid strategy (6 files)
│   │   ├── dca/                        DCA strategy (8 files)
│   │   ├── smc/                        Smart Money Concepts (7 files, 2,466 LOC)
│   │   ├── trend_follower/             Trend follower (8 files)
│   │   ├── hybrid/                     Grid+DCA hybrid (4 files)
│   │   ├── grid_adapter.py             Grid → BaseStrategy (281 LOC)
│   │   ├── dca_adapter.py              DCA → BaseStrategy (306 LOC)
│   │   ├── smc_adapter.py              SMC → BaseStrategy (308 LOC)
│   │   └── trend_follower_adapter.py   TF → BaseStrategy (310 LOC)
│   ├── telegram/bot.py               Telegram control & alerts (844 LOC)
│   ├── monitoring/                   Prometheus metrics + alerts
│   └── tests/backtesting/            Backtesting engine (17 files, 1,067 LOC core)
├── web/                              Web dashboard
│   ├── backend/                        FastAPI (42 routes + WebSocket)
│   └── frontend/                       React + TypeScript (7 pages)
├── tests/                            Test suite (1,534 tests)
├── configs/phase7_demo.yaml          5 bots: Hybrid, Grid, DCA, Trend, SMC
├── alembic/                          DB migrations
├── docker-compose.yml                Production deployment
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
        FetchPrice --> ProcessGrid: grid/hybrid
        FetchPrice --> ProcessDCA: dca/hybrid
        FetchPrice --> ProcessTrend: trend_follower
        FetchPrice --> ProcessSMC: smc (4 timeframes)
        ProcessGrid --> UpdateRisk
        ProcessDCA --> UpdateRisk
        ProcessTrend --> UpdateRisk
        ProcessSMC --> UpdateRisk
        UpdateRisk --> SaveState: every 30s
        SaveState --> Sleep1s
        Sleep1s --> FetchPrice
    }
```

---

## 4. Strategy Architecture

```mermaid
graph TB
    subgraph Registry["Strategy Registry (357 LOC)"]
        direction TB
        BS["BaseStrategy ABC (325 LOC)<br/>analyze_market() → generate_signal()<br/>→ open_position() → update_positions()"]
    end

    subgraph Strategies["5 Strategy Implementations"]
        GRID["Grid Strategy<br/>6 files<br/>arithmetic / geometric levels<br/>buy low → sell high"]
        DCA["DCA Strategy<br/>8 files<br/>safety orders on dip<br/>average down + TP"]
        SMC["SMC Strategy<br/>7 files, 2,466 LOC<br/>BOS / CHoCH / OB / FVG<br/>4-TF confluence zones"]
        TREND["Trend Follower<br/>8 files, 468 LOC core<br/>EMA pullback / breakout<br/>ATR trailing stop"]
        HYBRID["Hybrid Strategy<br/>4 files<br/>Grid + DCA adaptive<br/>regime-based switching"]
    end

    subgraph Adapters["Adapter Layer (1,205 LOC total)"]
        GA["GridAdapter (281)"]
        DA["DCAAdapter (306)"]
        SA["SMCAdapter (308)"]
        TA["TFAdapter (310)"]
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

    subgraph Regime["Market Regime Detector (693 LOC)"]
        MRD["ADX + EMA + ATR + Volume<br/>→ 6 regimes with hysteresis"]
    end

    MRD -->|recommends| Registry

    style Strategies fill:#1a1a2e,stroke:#e94560,color:#fff
    style Registry fill:#16213e,stroke:#0f3460,color:#fff
    style Adapters fill:#16213e,stroke:#533483,color:#fff
    style Regime fill:#533483,stroke:#e94560,color:#fff
```

### Unified Signal Interface

```python
@dataclass
class BaseSignal:
    direction: SignalDirection    # LONG | SHORT
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    confidence: float            # 0.0 — 1.0
    timestamp: datetime
    strategy_type: str           # "grid" | "dca" | "smc" | "trend_follower"
    metadata: dict[str, Any]     # strategy-specific data
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
    QT -->|"Grid (cautious)"| G3["Grid Bot"]
    VT -->|"DCA (cautious)"| D1["DCA Bot"]
    BULL -->|"Trend Follower (long)"| T1["Trend Bot"]
    BEAR -->|"DCA (accumulation)"| D2["DCA Bot"]

    style Regimes fill:#1a1a2e,stroke:#533483,color:#fff
```

---

## 5. SMC Strategy Pipeline (NEW in v2.1)

```mermaid
graph TB
    subgraph DataFetch["4-Timeframe OHLCV Fetch (asyncio.gather)"]
        D1["D1 × 200 candles"]
        H4["H4 × 200 candles"]
        H1["H1 × 200 candles"]
        M15["M15 × 200 candles"]
    end

    subgraph Analysis["Market Structure Analysis (435 LOC)"]
        SWING["Swing Detection<br/>adaptive: D1=swing//5, H4=swing//2"]
        BOS["BOS / CHoCH<br/>(smartmoneyconcepts library)"]
        TREND["Trend Direction<br/>BULLISH / BEARISH / RANGING"]
    end

    subgraph Confluence["Confluence Zones (688 LOC)"]
        OB["Order Blocks"]
        FVG["Fair Value Gaps"]
        LIQ["Liquidity Zones"]
        SCORE["Zone Scoring<br/>OB+FVG+LIQ overlap"]
    end

    subgraph Entry["Entry Signals (729 LOC)"]
        SIG["Signal Generator<br/>min R:R 2.5<br/>volume confirmation"]
        FILTER["Filter: confidence > 60%<br/>trend-aligned boost +10%"]
    end

    subgraph Position["Position Manager (557 LOC)"]
        SIZE["Kelly Criterion Sizing<br/>max 2% risk per trade"]
        TRAIL["Trailing Stop<br/>activation 1.5%, distance 0.5%"]
        EXIT["Exit: SL / TP / trailing"]
    end

    D1 --> SWING
    H4 --> SWING
    SWING --> BOS --> TREND
    H1 --> Confluence
    TREND --> Confluence
    Confluence --> SCORE
    M15 --> Entry
    SCORE --> Entry
    SIG --> FILTER
    FILTER --> SIZE --> TRAIL --> EXIT

    style DataFetch fill:#533483,stroke:#e94560,color:#fff
    style Analysis fill:#0f3460,stroke:#533483,color:#fff
    style Confluence fill:#0f3460,stroke:#533483,color:#fff
    style Entry fill:#16213e,stroke:#533483,color:#fff
    style Position fill:#1a1a2e,stroke:#e94560,color:#fff
```

---

## 6. Data Flow

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

        alt Grid / DCA / Hybrid
            BO->>EC: fetch_open_orders()
            BO->>SR: analyze(ohlcv_1h)
        else Trend Follower
            BO->>EC: fetch_ohlcv(1h, 200)
            BO->>SR: analyze(ohlcv_1h)
        else SMC Strategy
            BO->>EC: fetch_ohlcv(D1+H4+H1+M15)
            BO->>SR: analyze_market(df_d1, df_h4, df_h1, df_m15)
        end

        SR-->>BO: Signal(LONG, entry=67500, conf=0.72)
        BO->>RM: validate(signal)
        RM-->>BO: approved (size=0.002)

        BO->>EC: create_order(BUY, 0.002, 67500)
        EC->>EX: POST /v5/order/create
        EX-->>EC: order_id

        BO->>DB: INSERT order + signal
        BO->>RD: PUBLISH order_placed

        RD-->>TG: notification
        RD-->>WS: push to browser
    end
```

---

## 7. Database Schema

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
        text smc_state
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

## 8. Exchange Integration

```mermaid
graph TB
    subgraph Clients["Exchange Clients (1,813 LOC)"]
        CCXT["ExchangeAPIClient<br/>(CCXT Wrapper, 671 LOC)<br/>Binance, OKX, Kraken"]
        DIRECT["ByBitDirectClient<br/>(Direct V5 API, 1,014 LOC)<br/>api-demo.bybit.com"]
    end

    subgraph Selection["Auto-Selection Logic (main.py)"]
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

## 9. Multi-Timeframe Backtesting Engine (NEW in v2.1)

```mermaid
graph TB
    subgraph Input["Data Sources"]
        CSV["CSV Files<br/>45 pairs × 10 TF<br/>5.4 GB historical"]
        SYNTH["Synthetic Generator<br/>configurable volatility"]
    end

    subgraph Engine["MultiTFBacktestEngine (415 LOC)"]
        ITER["M15 Candle Iterator<br/>→ rolling D1/H4/H1 context"]
        STRAT["Strategy Adapter<br/>Grid | DCA | SMC | TF"]
        SIM["MarketSimulator (408 LOC)<br/>LONG + SHORT execution<br/>slippage, fees, partial fills"]
    end

    subgraph Analytics["Advanced Analytics"]
        WF["Walk-Forward Analysis"]
        MC["Monte Carlo Simulation"]
        OPT["Parameter Optimization"]
        SENS["Sensitivity Analysis"]
    end

    subgraph Output["Results"]
        HTML["HTML Report<br/>equity curve, drawdown"]
        JSON["JSON Results<br/>trade-by-trade log"]
        PRESET["YAML Preset<br/>optimal parameters"]
    end

    CSV --> ITER
    SYNTH --> ITER
    ITER --> STRAT
    STRAT --> SIM
    SIM --> Analytics
    Analytics --> Output

    style Input fill:#533483,stroke:#e94560,color:#fff
    style Engine fill:#0f3460,stroke:#533483,color:#fff
    style Analytics fill:#16213e,stroke:#533483,color:#fff
    style Output fill:#1a1a2e,stroke:#e94560,color:#fff
```

### Backtesting Capabilities

| Feature | Status |
|:--------|:-------|
| Multi-timeframe (M5 → D1) | DONE |
| LONG positions | DONE |
| SHORT positions (futures) | DONE |
| CSV data loading | DONE |
| Synthetic data generation | DONE |
| Walk-forward analysis | DONE |
| Monte Carlo simulation | DONE |
| HTML report generation | DONE |
| All 5 strategies supported | DONE |

---

## 10. Event System

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
        E7["SMC_SIGNAL_GENERATED"]
    end

    style Bus fill:#e94560,stroke:#533483,color:#fff
    style Producers fill:#0f3460,stroke:#533483,color:#fff
    style Consumers fill:#0f3460,stroke:#533483,color:#fff
    style EventTypes fill:#1a1a2e,stroke:#16213e,color:#fff
```

---

## 11. Web UI Architecture

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
        R2["/api/v1/bots — CRUD + control + DELETE"]
        R3["/api/v1/strategies — list + config + apply"]
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

## 12. State Persistence & Crash Recovery

```mermaid
sequenceDiagram
    participant BO as BotOrchestrator
    participant SP as StateSerializer
    participant DB as PostgreSQL
    participant EX as Exchange

    Note over BO: Normal operation — save every 30s
    loop Every 30 seconds
        BO->>SP: serialize(grid, dca, risk, trend, hybrid, smc)
        SP->>DB: UPSERT bot_state_snapshots
        DB-->>SP: saved_at = now()
    end

    Note over BO: Crash happens!
    BO-xBO: Process killed

    Note over BO: Restart
    BO->>DB: SELECT * FROM bot_state_snapshots<br/>WHERE bot_name = 'demo_btc_smc'
    DB-->>BO: snapshot (grid/dca/risk/trend/hybrid/smc state)

    BO->>SP: deserialize(snapshot)
    SP-->>BO: engines restored

    BO->>EX: fetch_open_orders()
    EX-->>BO: [orders]
    BO->>BO: reconcile_with_exchange()<br/>match saved orders with live
    Note over BO: Resume trading
```

---

## 13. Deployment Architecture

```mermaid
graph TB
    subgraph Server["Production Server — 185.233.200.13"]
        subgraph DC["Docker Compose"]
            BOT["traderagent-bot<br/>Python 3.11<br/>Volume: ./bot:/app/bot:ro"]
            PG["postgres:15<br/>Port: 5432<br/>Volume: pg_data"]
            RD["redis:7<br/>Port: 6379"]
            WEB_B["webui-backend<br/>FastAPI :8000"]
            WEB_F["webui-frontend<br/>nginx :3000"]
        end
    end

    subgraph Deploy["Deployment Flow (no rebuild needed)"]
        D1["1. tar czf bot/ tests/ configs/"]
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

## 14. Security Model

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
        VALID["Pydantic validation<br/>all config + order params"]
    end

    FERNET --> ENC_DB
    JWT --> SESSIONS

    style Secrets fill:#e94560,stroke:#533483,color:#fff
    style Auth fill:#0f3460,stroke:#533483,color:#fff
    style Access fill:#0f3460,stroke:#533483,color:#fff
    style Exchange fill:#16213e,stroke:#533483,color:#fff
```

---

## 15. Strategy Capabilities Matrix

| Strategy | Entry Logic | Exit Logic | Risk Management | Timeframes | Best Market |
|:---------|:-----------|:-----------|:----------------|:-----------|:------------|
| **Grid** | Price hits grid level | Counter-order at next level | Max position, stop-loss | 1h | Sideways / Range |
| **DCA** | Price drops N% from entry | Take profit at avg + M% | Max steps, daily loss | 1h | Dips / Bear |
| **Trend Follower** | EMA pullback / breakout | Trailing stop, ATR-based TP | 1-2% risk per trade | 1h | Trending |
| **SMC** | Confluence zone + BOS/CHoCH | Dynamic SL/TP, trailing | Kelly criterion, max 3 pos | D1+H4+H1+M15 | Price action |
| **Hybrid** | Grid in range, DCA on breakout | Context-dependent | Combined limits | 1h | Mixed |

---

## 16. Testing Architecture

```
Total: 1,534 tests | Pass rate: 100% (1,508 passed, 25 skipped, 1 perf benchmark)
```

```mermaid
pie title Test Distribution
    "Strategies (Grid/DCA/SMC/TF/Hybrid)" : 620
    "Orchestrator" : 143
    "Backtesting" : 163
    "Integration" : 108
    "Database" : 84
    "API" : 75
    "Telegram" : 55
    "Web UI" : 46
    "Load/Stress" : 40
    "Monitoring + Utils" : 139
    "Testnet" : 27
    "Misc" : 34
```

---

## 17. Deployed Configuration

```yaml
# configs/phase7_demo.yaml — 5 bots on Bybit Demo
bots:
  - name: demo_btc_hybrid     # BTC/USDT, Grid+DCA, auto_start: true
  - name: demo_eth_grid        # ETH/USDT, Grid only, manual start
  - name: demo_sol_dca         # SOL/USDT, DCA only, manual start
  - name: demo_btc_trend       # BTC/USDT, Trend Follower, manual start
  - name: demo_btc_smc         # BTC/USDT, SMC, dry_run: true, manual start
```

---

## 18. Key Design Decisions

| Decision | Rationale |
|:---------|:----------|
| **ByBitDirectClient** vs CCXT sandbox | CCXT `set_sandbox_mode(True)` routes to testnet (wrong). Demo requires `api-demo.bybit.com` |
| **Linear futures only** | Bybit demo does not support spot trading |
| **Adapter pattern** for strategies | Unified `BaseStrategy` interface lets registry manage all types uniformly |
| **Redis Pub/Sub** for events | Decouples producers from consumers (Telegram, Web UI, monitoring) |
| **Read-only volume mount** | `./bot:/app/bot:ro` — code changes via tar/scp, no Docker rebuild |
| **State snapshots** every 30s | Crash recovery without losing grid/DCA/risk/SMC state |
| **asyncpg** (not psycopg2) | Native async PostgreSQL driver — no thread pool overhead |
| **Fernet encryption** for API keys | AES-128-CBC, keys never stored in plaintext |
| **Adaptive swing_length** for SMC | D1: swing//5 (10), H4: swing//2 (25) — works with 50 daily candles |
| **Kelly criterion** for SMC sizing | Optimal position sizing based on win rate and payoff ratio |
| **smartmoneyconcepts library** | Battle-tested BOS/CHoCH/OB/FVG detection vs custom implementation |

---

## 19. Monitoring Stack

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

## 20. Quick Reference

```bash
# Run ALL tests (1,534)
python -m pytest tests/ -q

# Lint check
python -m ruff check bot/ tests/
python -m black --check bot/ tests/
python -m mypy bot/ --ignore-missing-imports

# Deploy code to server
tar czf /tmp/sync.tar.gz bot/ tests/ configs/ && \
scp /tmp/sync.tar.gz ai-agent@185.233.200.13:/tmp/ && \
ssh ai-agent@185.233.200.13 "cd ~/TRADERAGENT && tar xzf /tmp/sync.tar.gz"

# Restart bot
ssh ai-agent@185.233.200.13 "cd ~/TRADERAGENT && docker compose restart bot"

# View logs
ssh ai-agent@185.233.200.13 "docker logs traderagent-bot --since 5m"

# SMC bot logs
ssh ai-agent@185.233.200.13 "docker logs traderagent-bot 2>&1 | grep smc"

# Start/stop bot via Telegram
/start_bot demo_btc_smc
/stop_bot demo_btc_smc

# Run backtesting
python bot/tests/backtesting/multi_tf_engine.py --strategy smc --symbol BTCUSDT
```

---

## Changelog: v2.0 → v2.1

| Change | Details |
|:-------|:--------|
| **SMC standalone strategy** | Full deployment pipeline: Pydantic schema, orchestrator integration, 4-TF OHLCV fetch, entry/exit execution |
| **Adaptive swing_length** | D1: swing//5, H4: swing//2 — no longer needs 101 daily candles |
| **Multi-TF backtesting** | SHORT positions, M5 timeframe, CSV loading, CLI runner |
| **Bot management dashboard** | Create/delete bots, PnL charts, strategy templates, loading indicators |
| **CI fixes** | mypy 0 errors, pandas>=2.1.0 for Python 3.12, types-PyYAML |
| **Lint cleanup** | ruff + black 0 errors across bot/ and tests/ |
| **5 deployed bots** | Hybrid, Grid, DCA, Trend Follower, SMC (dry_run) |
| **Test count** | 1,504 → 1,534 (+30 new tests) |

---

> **Last updated:** February 21, 2026 | **Session:** 17 | **Commit:** `4d67d5e`
> **Co-Authored:** Claude Opus 4.6
