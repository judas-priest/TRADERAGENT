# Plan: Integrate `smartmoneyconcepts` Library into SMC Strategy (Variant B)

> **Issue:** [#238](https://github.com/alekseymavai/TRADERAGENT/issues/238)
> **PR:** This branch (`feature/smc-smartmoneyconcepts-integration`)
> **Date:** 2026-02-20, Session 16

## Context

The bot's SMC strategy has critical parameter mismatches vs industry-standard tools (LuxAlgo, BigBeluga, smartmoneyconcepts lib). Key issues: `swing_length=5` (should be 50), OB lookback hardcoded to 20 (config says 50), no liquidity zone detection. Instead of manually fixing parameters (Variant A), we integrate the well-tested `smartmoneyconcepts` Python library (1,100+ GitHub stars, MIT license) as the detection engine while keeping the bot's unique advantages (entry patterns, confidence scoring, zone strength scoring, Kelly sizing, MTF pipeline).

## Comparative Analysis: Bot SMC vs Industry Standards

| Parameter | Bot (current) | smartmoneyconcepts | LuxAlgo | BigBeluga |
|-----------|:---:|:---:|:---:|:---:|
| swing_length | **5** | **50** | **50** | ~20-30 |
| BOS method | close only | close/wick (configurable) | close/wick | close/wick |
| OB detection | last opposite candle, lookback=20 | last opposite candle, lookback=swing | last opposite candle | volumetric bid/ask |
| OB mitigation | price close (hard) | wick (soft, configurable) | ATR-based | close/wick/avg |
| FVG join | no | yes (configurable) | no | no |
| Liquidity zones | **missing** | yes (range_percent) | yes (EQH/EQL) | yes (SFP) |
| Internal structure | no | no | yes | yes |
| **Entry patterns** | **3 patterns + quality** | none | none | none |
| **Confidence formula** | **composite 0-1.0** | none | none | none |
| **Zone scoring** | **0-100 (5 factors)** | none | none | none |
| **Kelly sizing** | **quarter Kelly** | none | none | none |
| **MTF pipeline** | **D1→H4→H1→M15** | single TF | single TF | single TF |

## Sub-issues (execution order)

1. [#239](https://github.com/alekseymavai/TRADERAGENT/issues/239) — Add `smartmoneyconcepts` dependency, update `config.py` (`swing_length` 5→50, 4 new fields)
2. [#240](https://github.com/alekseymavai/TRADERAGENT/issues/240) — Replace swing/BOS/CHoCH detection in `market_structure.py`
3. [#241](https://github.com/alekseymavai/TRADERAGENT/issues/241) — Replace OB/FVG detection, add Liquidity Zones in `confluence_zones.py`
4. [#242](https://github.com/alekseymavai/TRADERAGENT/issues/242) — Add liquidity-based TP targeting and confluence scoring in `entry_signals.py`
5. [#243](https://github.com/alekseymavai/TRADERAGENT/issues/243) — Wire new config params through `smc_strategy.py` and adapter
6. [#244](https://github.com/alekseymavai/TRADERAGENT/issues/244) — Update tests for library-based detection

## Files to Modify

| File | Action | Lines affected |
|------|--------|---------------|
| `requirements.txt` | Add dependency | +1 line |
| `bot/strategies/smc/config.py` | Change default + add fields | ~10 lines |
| `bot/strategies/smc/market_structure.py` | **Major refactor** | ~200 lines replaced |
| `bot/strategies/smc/confluence_zones.py` | **Major refactor + new feature** | ~250 lines replaced + ~80 new |
| `bot/strategies/smc/entry_signals.py` | Add liquidity TP + confluence | ~40 lines added |
| `bot/strategies/smc/smc_strategy.py` | Wire params | ~20 lines modified |
| `bot/strategies/smc/__init__.py` | Export LiquidityZone | +3 lines |
| `bot/strategies/smc_adapter.py` | Add metadata key | +1 line |
| `tests/strategies/smc/*.py` | Update for new defaults | ~50 lines modified |

## What Changes vs What Stays

| Component | Action | Reason |
|-----------|--------|--------|
| Swing detection | **REPLACE** with `smc.swing_highs_lows()` | Library default=50, well-tested |
| BOS/CHoCH detection | **REPLACE** with `smc.bos_choch()` | Library handles edge cases better |
| Order Block detection | **REPLACE** with `smc.ob()` | Library uses precise Top/Bottom zones |
| FVG detection | **REPLACE** with `smc.fvg()` | Library adds join_consecutive option |
| Liquidity zones | **NEW** via `smc.liquidity()` | Missing feature, critical for TP targeting |
| Entry patterns (engulf/pin/inside) | **KEEP** | Bot's unique advantage |
| Confidence formula | **KEEP** | Not in any library |
| Zone strength scoring | **KEEP** | Not in any library |
| Kelly Criterion sizing | **KEEP** | Not in any library |
| Position management | **KEEP** | Not in any library |
| MTF pipeline | **KEEP** | Not in any library |
| BaseStrategy adapter | **KEEP** (minimal metadata addition) | Interface compatibility |

## `smartmoneyconcepts` Library API Reference

```python
from smartmoneyconcepts import smc

# Input: pandas DataFrame with lowercase columns: open, high, low, close, volume
# Output: DataFrames with same index, NaN where no detection

# Foundation (required by all others)
swings = smc.swing_highs_lows(ohlc, swing_length=50)
# → HighLow (1=high, -1=low, NaN), Level (price)

bos = smc.bos_choch(ohlc, swings, close_break=True)
# → BOS (1/-1/NaN), CHOCH (1/-1/NaN), Level, BrokenIndex

ob = smc.ob(ohlc, swings, close_mitigation=False)
# → OB (1/-1/NaN), Top, Bottom, OBVolume, Percentage, MitigatedIndex

fvg = smc.fvg(ohlc, join_consecutive=False)
# → FVG (1/-1/NaN), Top, Bottom, MitigatedIndex

liq = smc.liquidity(ohlc, swings, range_percent=0.01)
# → Liquidity (1/-1/NaN), Level, End, Swept
```

## Verification

1. `pip install smartmoneyconcepts` — verify import works
2. `python -m pytest tests/strategies/smc/ -v` — all SMC tests pass
3. `python -m pytest tests/ -x --timeout=60` — no regressions in other strategies
4. Manual: `SMCStrategy(SMCConfig(swing_length=50))` → swing, BOS/CHoCH, OB, FVG, liquidity detected
