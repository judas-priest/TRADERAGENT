# Plan bektestirovaniya: DCA + Trend Follower + SMC

**Data sozdaniya:** 2026-02-22
**Session:** 22
**VM:** compute-vm-16-32-100-ssd (16 vCPU / 32 GB RAM / 100 GB SSD)
**Dvizhok:** `bot/tests/backtesting/multi_tf_engine.py` (MultiTimeframeBacktestEngine)

---

## Obzor

Polnyy tsikl bektestirovaniya trekh strategiy (DCA, Trend Follower, SMC) na 18 torgovyh parah cherez edinyy multi-TF dvizhok s integrirovannym RegimeClassifier i RiskManager.

### Pochemu tolko bot layer

- `MultiTimeframeBacktestEngine` podderzhivayet **lyubuyu** BaseStrategy (DCA, TF, SMC)
- 5 taymfreymov odnovremenno (M5 → M15 → H1 → H4 → D1)
- RegimeClassifier (6 rezhimov) + RiskManager — integrirovaniy v Session 21
- Vosproizvodit prodakshn-povedeniye bota
- Service layer (`services/backtesting/`) — tolko Grid, ne podhodit

### Strategii

| Strategiya | Adapter | Napravleniye | Fayl |
|------------|---------|-------------|------|
| DCA | `DCAAdapter` (306 strok) | LONG only | `bot/strategies/dca_adapter.py` |
| Trend Follower | `TrendFollowerAdapter` (310 strok) | LONG + SHORT | `bot/strategies/trend_follower_adapter.py` |
| SMC | `SMCStrategyAdapter` (308 strok) | LONG + SHORT | `bot/strategies/smc_adapter.py` |

Vse tri realizuyut `BaseStrategy` i gotovy k ispolzovaniyu s `MultiTimeframeBacktestEngine`.

---

## Faza 0: Zagruzka dannyh (~1 chas)

### Tselevye pary (18 sht)

| Tir | Pary | Kol-vo | Pochemu |
|-----|------|--------|---------|
| Blue Chips | BTC, ETH, SOL, BNB, XRP | 5 | Vysokaya likvidnost |
| Mid Caps | DOGE, ADA, AVAX, LINK, DOT, MATIC, NEAR, APT | 8 | Srednyaya volatilnost |
| Volatile | PEPE, WIF, BONK, SUI, SEI | 5 | Stress-test strategiy |

### Deystviya

1. Dorabotat `scripts/download_historical_data.py`:
   - Parallelnaya zagruzka (4 potoka, Bybit rate-limit)
   - Period: 12 mesyatsev nazad
   - Tayframe: tolko M5 (engine sam resemplit v M15/H1/H4/D1)
   - Validatsiya: proverka propuskov > 3 svechey podryad

2. Zapusk:
   ```bash
   python scripts/download_m5_data.py \
     --exchange bybit \
     --symbols BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,DOGE/USDT,ADA/USDT,AVAX/USDT,LINK/USDT,DOT/USDT,MATIC/USDT,NEAR/USDT,APT/USDT,PEPE/USDT,WIF/USDT,BONK/USDT,SUI/USDT,SEI/USDT \
     --timeframe 5m \
     --months 12 \
     --output-dir data/historical/
   ```

### Otsenka dannyh

```
18 par × 105,120 svechey (12 mes M5) × ~30 bayt ≈ 55 MB
Zagruzka: ~1000 zaprosov k Bybit API → ~15-20 min s rate-limiting
```

### Vyhod

`data/historical/bybit_{SYMBOL}_USDT_5m.csv` × 18 faylov

---

## Faza 1: Baseline — progon bez optimizatsii (~5 min)

### Zadacha

Poluchit bazovye metriki kazhdoy strategii s defoltnymy parametrami.

### Konfig

```python
MultiTFBacktestConfig(
    initial_balance=Decimal("10000"),
    warmup_bars=60,
    lookback=100,
    analyze_every_n=4,
    risk_per_trade=Decimal("0.02"),
    enable_regime_filter=False,
    enable_risk_manager=False,
)
```

### Zapusk

18 par × 3 strategii = **54 bektesta**

```
~500 ms/bektest (multi-TF na 105K M5 svechey)
S 14 workers: ~2 min
```

### Vyhod

Tablitsa baseline:

| Para | Strategiya | Return % | Sharpe | Sortino | MaxDD % | WinRate | Trades |
|------|-----------|----------|--------|---------|---------|---------|--------|

Tsel: ponyat kakie strategii na kakih parah generiruyut sdelki i pribyl.

---

## Faza 2: Optimizatsiya parametrov (~15 min)

### 2.1 DCA

| Parametr | Diapazon | Shagov |
|----------|----------|--------|
| `price_deviation_pct` | 0.01, 0.015, 0.02, 0.03, 0.05 | 5 |
| `safety_step_pct` | 0.01, 0.015, 0.02, 0.025, 0.03 | 5 |
| `take_profit_pct` | 0.005, 0.01, 0.015, 0.02, 0.03 | 5 |
| `max_safety_orders` | 3, 5, 7, 10 | 4 |

Kombinatsiy: 5 × 5 × 5 × 4 = **500 na paru**
Vsego: 18 × 500 = **9,000 bektestov** → ~5 min na 14 workers

### 2.2 Trend Follower

| Parametr | Diapazon | Shagov |
|----------|----------|--------|
| `ema_fast_period` | 5, 10, 15, 20, 30 | 5 |
| `ema_slow_period` | 40, 50, 80, 100, 200 | 5 |
| `require_volume_confirmation` | True, False | 2 |
| `max_atr_filter_pct` | 0.03, 0.05, 0.08, 0.10 | 4 |

Kombinatsiy: 5 × 5 × 2 × 4 = **200 na paru**
Vsego: 18 × 200 = **3,600 bektestov** → ~2 min

### 2.3 SMC

| Parametr | Diapazon | Shagov |
|----------|----------|--------|
| `swing_length` | 3, 5, 7, 10 | 4 |
| `min_risk_reward` | 1.5, 2.0, 2.5, 3.0 | 4 |
| `risk_per_trade` | 0.01, 0.02, 0.03, 0.05 | 4 |
| `close_mitigation` | True, False | 2 |

Kombinatsiy: 4 × 4 × 4 × 2 = **128 na paru**
Vsego: 18 × 128 = **2,304 bektestov** → ~1.5 min

### Two-Phase Fine-Tuning

Posle coarse search — top-10 rezultatov per pair → refined grid:
+5,400 dopolnitelnyh bektestov → ~4 min

### Itogo Faza 2

```
20,304 bektestov → ~15 min na 14 workers
RAM pik: ~4 GB (dannye) + ~8 GB (workers) = ~12 GB
```

### Vyhod

Best params per pair per strategy + JSON-otchyot s param_impact analitikoy.

---

## Faza 3: Regime-Aware bektest (~5 min)

### Zadacha

Peregnat luchshie konfigi s vklyuchonnymi RegimeClassifier + RiskManager.

### Konfig

```python
MultiTFBacktestConfig(
    ...  # best params from Phase 2
    enable_regime_filter=True,
    regime_check_interval=12,        # kazhdyy chas (12 M5 barov)
    regime_timeframe="h1",
    enable_risk_manager=True,
    rm_max_position_size=Decimal("5000"),
    rm_stop_loss_percentage=Decimal("0.10"),   # 10% portfelnyy stop
    rm_max_daily_loss=Decimal("500"),
)
```

### Zapusk

18 par × 3 strategii × best params = **54 bektesta**

### Analiz

- `regime_filter_blocks` — skolko signalov zablokiroval rezhim
- `risk_manager_blocks` — skolko zablokiroval risk manager
- `regime_changes` — chastota smeny rezhimov
- `risk_halted` — ostanovilsya li bektest po risk limit
- Sravneniye Return/Sharpe **s** i **bez** rezhimnogo filtra

### Vyhod: Matritsa Regime × Strategy

```
                TIGHT_RANGE  WIDE_RANGE  QUIET_TRANS  VOLATILE_TRANS  BULL_TREND  BEAR_TREND
DCA             blokirovan   blokirovan  blokirovan   blokirovan      razreshyon  razreshyon
TrendFollower   blokirovan   blokirovan  blokirovan   blokirovan      razreshyon  razreshyon
SMC             razreshyon   razreshyon  razreshyon   razreshyon      razreshyon  razreshyon
```

---

## Faza 4: Robastnost (~50 min)

### 4.1 Walk-Forward Validation

- 5 skolzyashchih okon: 70% train / 30% test
- 18 par × 3 strategii = **54 validatsii** (po 5 okon = 270 bektestov)
- Porog: consistency ratio ≥ 0.6 = robust

### 4.2 Stress Testing

- Top-3 samyh volatilnyh perioda na paru
- 18 par × 3 strategii × 3 perioda = **162 bektesta**
- Porog: min Sharpe v stresse > 0

### 4.3 Monte Carlo Simulation

- 500 randomizatsiy poryadka sdelok na kazhdyy rezultat
- 18 par × 3 strategii × 500 = **27,000 simulyatsiy**
- 95-y pertsintil drawdown kak risk metric

### 4.4 Sensitivity Analysis

- ±20% po kazhdomu optimalnomu parametru
- 18 par × 3 strategii × ~6 parametrov × 2 = **~648 progonov**
- Porog: Sharpe padayet > 50% ot ±20% — parametr hrupkiy

### Resursy

```
Summmarno: ~28,000 progonov
14 workers: ~50 min
RAM pik: ~16 GB
```

---

## Faza 5: Itogovyy otchyot i portfolio allocation (~30 min)

### Deystviya

1. **Ranzhirovaniye** — 18 par × 3 strategii po Sharpe (regime-aware)
2. **Filtratsiya** — otbrasyvaem:
   - Walk-Forward consistency < 0.6
   - Stress Sharpe < 0
   - Sensitivity > 50% degradatsiya
   - `risk_halted = True`
3. **Top-N selection** — luchshaya strategiya dlya kazhdoy pary
4. **Capital allocation** — 5% depozita raspredelyn po top param (ravnovzveshenno ili po Sharpe)

### Vyhod

- `data/backtest_results/full_pipeline_report_{timestamp}.json` — polnyy otchyot
- `data/backtest_results/regime_routing_table.json` — matritsa Strategy × Regime
- `data/presets/` — per-pair optimal strategy + params (YAML)
- Sravnenie Return/Sharpe: baseline vs optimized vs regime-aware

---

## Svodnaya tablica resursov VM

| Faza | Bektestov | Vremya | CPU | RAM |
|------|-----------|--------|-----|-----|
| 0. Dannye | — | ~1 ch | 4 cores | 2 GB |
| 1. Baseline | 54 | ~2 min | 14 cores | 4 GB |
| 2. Optimizatsiya | 20,304 | ~15 min | 14 cores | 12 GB |
| 3. Regime-Aware | 54 | ~2 min | 14 cores | 4 GB |
| 4. Robastnost | ~28,000 | ~50 min | 14 cores | 16 GB |
| 5. Otchyot | — | ~30 min | 2 cores | 4 GB |
| **Itogo** | **~48,400** | **~3 chasa** | **max 14** | **max 16 GB** |

---

## Novyy kod (chto nuzhno napisat)

| # | Skript | Zadacha | Ocenka |
|---|--------|---------|--------|
| 1 | `scripts/download_m5_data.py` | Parallelnaya zagruzka M5 dlya 18 par | ~150 strok |
| 2 | `scripts/run_dca_tf_smc_pipeline.py` | Edinyy skript: fazy 1→5, CLI argumenty | ~400 strok |
| 3 | Adaptatsiya `ParameterOptimizer` | `ProcessPoolExecutor` vmesto Thread (CPU-bound) | ~30 strok diff |
| 4 | Regime routing report generator | Generatsiya matritsy Strategy × Regime | ~100 strok |

### Sushchestvuyushchie moduli (ispolzuyem bez izmeneniy)

- `StrategyComparison` — multi-strategy runner
- `WalkForwardAnalysis` — skolzyashchaya validatsiya
- `StressTester` — volatilnyye periody
- `MonteCarloSimulation` — randomizatsiya sdelok
- `SensitivityAnalysis` — analiz chuvstvitelnosti parametrov
- `ParameterOptimizer` — grid search + two-phase (+ minor fix dlya ProcessPool)

---

## Kriterii uspekha

| Metriks | Porog | Pochemu |
|---------|-------|---------|
| Sharpe Ratio (regime-aware) | > 1.0 | Minimalno priemlemyy risk-adjusted return |
| Max Drawdown | < 15% | Ogranichenie riska |
| Win Rate | > 45% | Minimalnaya nadezhnost |
| Walk-Forward Consistency | ≥ 0.6 | Robastnost vne sample |
| Monte Carlo 95th DD | < 20% | Worst-case risk |
| Sensitivity Degradation | < 50% | Stabilnost parametrov |

---

## Sleduyushchiye shagi posle bektesta

1. Deploy luchshih konfiguratsy na production server (Phase 8)
2. Implementatsiya MasterLoop + CapitalAllocator (v2.0 modules)
3. Monitoring dashboard dlya rezhimnoy pereklyucheniya strategiy
4. Live paper trading s luchshimi parametrami (1-2 nedeli)
5. Perehod na real trading s 5% kapitala
