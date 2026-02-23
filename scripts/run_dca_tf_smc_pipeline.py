#!/usr/bin/env python3
"""
DCA + Trend Follower + SMC Backtesting Pipeline.

Runs Phases 1-5 from docs/BACKTEST_PLAN_DCA_TF_SMC.md using the existing
multi-timeframe backtesting engine and analysis modules.

Usage:
    # Full pipeline (auto-discover pairs from data dir):
    python scripts/run_dca_tf_smc_pipeline.py --data-dir data/historical/ --workers 14

    # Single phase:
    python scripts/run_dca_tf_smc_pipeline.py --phase 1 --data-dir data/historical/

    # Specific symbols:
    python scripts/run_dca_tf_smc_pipeline.py --symbols BTC,ETH,SOL --data-dir data/historical/

    # Resume from a phase:
    python scripts/run_dca_tf_smc_pipeline.py --start-phase 3 --data-dir data/historical/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import traceback
import urllib.request
import urllib.parse
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.strategies.dca_adapter import DCAAdapter
from bot.strategies.smc.config import SMCConfig
from bot.strategies.smc_adapter import SMCStrategyAdapter
from bot.strategies.trend_follower.config import TrendFollowerConfig
from bot.strategies.trend_follower_adapter import TrendFollowerAdapter
from bot.tests.backtesting.backtesting_engine import BacktestResult
from bot.tests.backtesting.monte_carlo import MonteCarloConfig, MonteCarloSimulation
from bot.tests.backtesting.multi_tf_data_loader import (
    MultiTimeframeData,
    MultiTimeframeDataLoader,
)
from bot.tests.backtesting.multi_tf_engine import (
    MultiTFBacktestConfig,
    MultiTimeframeBacktestEngine,
)
from bot.tests.backtesting.optimization import (
    OptimizationConfig,
    ParameterOptimizer,
)
from bot.tests.backtesting.sensitivity import SensitivityAnalysis
from bot.tests.backtesting.stress_testing import StressTestConfig, StressTester
from bot.tests.backtesting.walk_forward import WalkForwardAnalysis, WalkForwardConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESULTS_DIR = PROJECT_ROOT / "data" / "backtest_results"
BALANCE = Decimal("10000")

# Global error collector — all errors across all phases
ALL_ERRORS: list[dict[str, Any]] = []

# ---------------------------------------------------------------------------
# Telegram notifications
# ---------------------------------------------------------------------------

# Load from .env file in project root (simple key=value parsing)
_dotenv_path = PROJECT_ROOT / ".env"
_dotenv: dict[str, str] = {}
if _dotenv_path.exists():
    for _line in _dotenv_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _dotenv[_k.strip()] = _v.strip()

TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") or _dotenv.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID") or _dotenv.get("TELEGRAM_CHAT_ID", "")


def tg_send(text: str) -> None:
    """Send a message to Telegram. Silently ignores errors."""
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": TG_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        # Fallback: retry without parse_mode (Markdown can fail on special chars)
        try:
            data = urllib.parse.urlencode({
                "chat_id": TG_CHAT_ID,
                "text": text,
            }).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass


BASELINE_CONFIG = MultiTFBacktestConfig(
    initial_balance=BALANCE,
    warmup_bars=60,
    lookback=100,
    analyze_every_n=4,
    risk_per_trade=Decimal("0.02"),
    enable_regime_filter=False,
    enable_risk_manager=False,
)

REGIME_CONFIG = MultiTFBacktestConfig(
    initial_balance=BALANCE,
    warmup_bars=60,
    lookback=100,
    analyze_every_n=4,
    risk_per_trade=Decimal("0.02"),
    enable_regime_filter=True,
    regime_check_interval=12,
    regime_timeframe="h1",
    enable_risk_manager=True,
    rm_max_position_size=Decimal("5000"),
    rm_stop_loss_percentage=Decimal("0.10"),
    rm_max_daily_loss=Decimal("500"),
)

# --- Parameter grids (from BACKTEST_PLAN_DCA_TF_SMC.md) ---

DCA_GRID: dict[str, list[Any]] = {
    "price_deviation_pct": [0.01, 0.015, 0.02, 0.03, 0.05],
    "safety_step_pct": [0.01, 0.015, 0.02, 0.025, 0.03],
    "take_profit_pct": [0.005, 0.01, 0.015, 0.02, 0.03],
    "max_safety_orders": [3, 5, 7, 10],
}

TF_GRID: dict[str, list[Any]] = {
    "ema_fast_period": [5, 10, 15, 20, 30],
    "ema_slow_period": [40, 50, 80, 100, 200],
    "require_volume_confirmation": [True, False],
    "max_atr_filter_pct": [0.03, 0.05, 0.08, 0.10],
}

SMC_GRID: dict[str, list[Any]] = {
    "swing_length": [3, 5, 7, 10],
    "min_risk_reward": [1.5, 2.0, 2.5, 3.0],
    "risk_per_trade": [0.01, 0.02, 0.03, 0.05],
    "close_mitigation": [True, False],
}

# Default parameters (used for baseline and as optimization starting point)
DCA_DEFAULTS: dict[str, Any] = {
    "price_deviation_pct": 0.02,
    "safety_step_pct": 0.015,
    "take_profit_pct": 0.015,
    "max_safety_orders": 5,
}

TF_DEFAULTS: dict[str, Any] = {
    "ema_fast_period": 20,
    "ema_slow_period": 50,
    "require_volume_confirmation": True,
    "max_atr_filter_pct": 0.05,
}

SMC_DEFAULTS: dict[str, Any] = {
    "swing_length": 50,
    "min_risk_reward": 2.5,
    "risk_per_trade": 0.02,
    "close_mitigation": False,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("pipeline")


def setup_logging() -> str:
    """Configure logging to file and stderr. Returns log file path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = RESULTS_DIR / f"pipeline_{ts}.log"

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(fh)
    root.addHandler(sh)

    return str(log_path)


# ---------------------------------------------------------------------------
# Strategy factories
# ---------------------------------------------------------------------------


def dca_factory(params: dict[str, Any]) -> DCAAdapter:
    return DCAAdapter(
        price_deviation_pct=Decimal(str(params["price_deviation_pct"])),
        safety_step_pct=Decimal(str(params["safety_step_pct"])),
        take_profit_pct=Decimal(str(params["take_profit_pct"])),
        max_safety_orders=params["max_safety_orders"],
        name="dca",
    )


def tf_factory(params: dict[str, Any]) -> TrendFollowerAdapter:
    config = TrendFollowerConfig(
        ema_fast_period=params["ema_fast_period"],
        ema_slow_period=params["ema_slow_period"],
        require_volume_confirmation=params["require_volume_confirmation"],
        max_atr_filter_pct=Decimal(str(params["max_atr_filter_pct"])),
    )
    return TrendFollowerAdapter(
        config=config, initial_capital=BALANCE, name="trend-follower", log_trades=False,
    )


def smc_factory(params: dict[str, Any]) -> SMCStrategyAdapter:
    config = SMCConfig(
        swing_length=params["swing_length"],
        min_risk_reward=Decimal(str(params["min_risk_reward"])),
        risk_per_trade=Decimal(str(params["risk_per_trade"])),
        close_mitigation=params["close_mitigation"],
    )
    return SMCStrategyAdapter(config=config, account_balance=BALANCE, name="smc")


STRATEGIES = {
    "dca": {"factory": dca_factory, "defaults": DCA_DEFAULTS, "grid": DCA_GRID},
    "trend-follower": {"factory": tf_factory, "defaults": TF_DEFAULTS, "grid": TF_GRID},
    "smc": {"factory": smc_factory, "defaults": SMC_DEFAULTS, "grid": SMC_GRID},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def discover_pairs(data_dir: str) -> list[str]:
    """Auto-discover pairs from *_5m.csv files in data_dir."""
    pairs: list[str] = []
    pattern = re.compile(r"(?:bybit_)?(.+?)_5m\.csv$", re.IGNORECASE)
    for fname in sorted(os.listdir(data_dir)):
        m = pattern.match(fname)
        if m:
            pairs.append(m.group(1))
    if not pairs:
        logger.warning("No *_5m.csv files found in %s", data_dir)
    return pairs


def find_csv(data_dir: str, pair: str) -> str | None:
    """Find the 5m CSV file for a pair (supports bybit_ prefix or plain)."""
    candidates = [
        os.path.join(data_dir, f"bybit_{pair}_5m.csv"),
        os.path.join(data_dir, f"{pair}_5m.csv"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def load_pair_data(data_dir: str, pair: str) -> MultiTimeframeData:
    """Load CSV and build MultiTimeframeData for one pair."""
    csv_path = find_csv(data_dir, pair)
    if csv_path is None:
        raise FileNotFoundError(f"No 5m CSV found for {pair} in {data_dir}")
    loader = MultiTimeframeDataLoader()
    return loader.load_csv(csv_path, base_timeframe="5m")


def result_to_dict(r: BacktestResult) -> dict[str, Any]:
    """Convert BacktestResult to JSON-serialisable dict."""
    return r.to_dict()


def save_json(data: Any, path: Path) -> None:
    """Write data as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Saved %s", path)


def generate_sensitivity_ranges(
    base_params: dict[str, Any], pct: float = 0.20,
) -> dict[str, list[Any]]:
    """Generate ±pct variations for each numeric parameter."""
    ranges: dict[str, list[Any]] = {}
    for k, v in base_params.items():
        try:
            fv = float(v)
            lo = fv * (1 - pct)
            hi = fv * (1 + pct)
            if isinstance(v, int):
                vals = sorted({max(1, int(lo)), int(v), max(1, int(hi))})
            else:
                vals = [round(lo, 6), round(fv, 6), round(hi, 6)]
            ranges[k] = vals
        except (TypeError, ValueError):
            continue
    return ranges


# ---------------------------------------------------------------------------
# Pipeline phases
# ---------------------------------------------------------------------------


async def phase1_baseline(
    pairs: list[str], data_dir: str, workers: int,
) -> dict[str, Any]:
    """Phase 1: Baseline — run each strategy with default params on every pair."""
    logger.info("=" * 60)
    logger.info("PHASE 1: Baseline (%d pairs × 3 strategies)", len(pairs))
    logger.info("=" * 60)

    results: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    ok_count = 0
    t0 = time.monotonic()

    for i, pair in enumerate(pairs, 1):
        try:
            data = load_pair_data(data_dir, pair)
        except Exception:
            msg = traceback.format_exc()
            logger.error("Failed to load data for %s:\n%s", pair, msg)
            errors.append({"pair": pair, "strategy": "all", "error": "data_load", "traceback": msg})
            continue

        results[pair] = {}
        for strat_name, spec in STRATEGIES.items():
            try:
                strategy = spec["factory"](spec["defaults"])
                engine = MultiTimeframeBacktestEngine(config=BASELINE_CONFIG)
                result = await engine.run(strategy, data)
                results[pair][strat_name] = result_to_dict(result)
                ok_count += 1
                logger.info(
                    "  %s / %s: return=%.2f%% sharpe=%s trades=%d",
                    pair, strat_name,
                    float(result.total_return_pct),
                    result.sharpe_ratio,
                    result.total_trades,
                )
            except Exception:
                msg = traceback.format_exc()
                logger.error("  %s / %s FAILED:\n%s", pair, strat_name, msg)
                errors.append({"pair": pair, "strategy": strat_name, "error": str(sys.exc_info()[1]), "traceback": msg})

        if i % 10 == 0 or i == len(pairs):
            tg_send(f"Phase 1 progress: {i}/{len(pairs)} pairs ({ok_count} OK, {len(errors)} err)")

    elapsed = time.monotonic() - t0
    total = len(pairs) * len(STRATEGIES)
    logger.info("Phase 1 done: %d/%d OK, %d errors", ok_count, total, len(errors))
    tg_send(f"✅ *Phase 1 done* ({elapsed:.0f}s)\n{ok_count}/{total} OK, {len(errors)} errors")

    save_json(results, RESULTS_DIR / "phase1_baseline.json")
    if errors:
        save_json(errors, RESULTS_DIR / "phase1_errors.json")
    for e in errors:
        e["phase"] = 1
    ALL_ERRORS.extend(errors)

    return results


async def phase2_optimization(
    pairs: list[str], data_dir: str, workers: int,
) -> dict[str, Any]:
    """Phase 2: Parameter optimisation — two-phase grid search per pair per strategy."""
    logger.info("=" * 60)
    logger.info("PHASE 2: Optimization (%d pairs × 3 strategies)", len(pairs))
    logger.info("=" * 60)

    best_params: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    ok_count = 0
    t_phase = time.monotonic()

    opt_config = OptimizationConfig(
        objective="total_return_pct",
        higher_is_better=True,
        backtest_config=BASELINE_CONFIG,
    )
    optimizer = ParameterOptimizer(config=opt_config)

    for i, pair in enumerate(pairs, 1):
        try:
            data = load_pair_data(data_dir, pair)
        except Exception:
            msg = traceback.format_exc()
            logger.error("Failed to load data for %s:\n%s", pair, msg)
            errors.append({"pair": pair, "strategy": "all", "error": "data_load", "traceback": msg})
            continue

        best_params[pair] = {}
        for strat_name, spec in STRATEGIES.items():
            try:
                logger.info("  Optimising %s / %s ...", pair, strat_name)
                t0 = time.monotonic()
                opt_result = await optimizer.two_phase_optimize(
                    strategy_factory=spec["factory"],
                    param_grid=spec["grid"],
                    data=data,
                    max_workers=workers,
                )
                elapsed = time.monotonic() - t0
                best_params[pair][strat_name] = {
                    "best_params": opt_result.best_params,
                    "best_objective": opt_result.best_objective,
                    "total_trials": len(opt_result.all_trials),
                    "result": result_to_dict(opt_result.best_result),
                }
                ok_count += 1
                logger.info(
                    "    best=%.2f%% (%d trials, %.1fs)",
                    opt_result.best_objective, len(opt_result.all_trials), elapsed,
                )
            except Exception:
                msg = traceback.format_exc()
                logger.error("  %s / %s OPT FAILED:\n%s", pair, strat_name, msg)
                errors.append({"pair": pair, "strategy": strat_name, "error": str(sys.exc_info()[1]), "traceback": msg})

        if i % 5 == 0 or i == len(pairs):
            el = time.monotonic() - t_phase
            tg_send(f"Phase 2 progress: {i}/{len(pairs)} pairs ({ok_count} OK, {len(errors)} err, {el:.0f}s)")

    elapsed_total = time.monotonic() - t_phase
    total = len(pairs) * len(STRATEGIES)
    logger.info("Phase 2 done: %d/%d OK, %d errors", ok_count, total, len(errors))
    tg_send(f"✅ *Phase 2 done* ({elapsed_total:.0f}s)\n{ok_count}/{total} OK, {len(errors)} errors")

    save_json(best_params, RESULTS_DIR / "phase2_optimization.json")
    if errors:
        save_json(errors, RESULTS_DIR / "phase2_errors.json")
    for e in errors:
        e.setdefault("phase", 2)
    ALL_ERRORS.extend(errors)

    return best_params


async def phase3_regime(
    pairs: list[str], data_dir: str, phase2: dict[str, Any],
) -> dict[str, Any]:
    """Phase 3: Regime-aware — best params + regime filter + risk manager."""
    logger.info("=" * 60)
    logger.info("PHASE 3: Regime-Aware (%d pairs × 3 strategies)", len(pairs))
    logger.info("=" * 60)

    results: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    ok_count = 0
    t0 = time.monotonic()

    for i, pair in enumerate(pairs, 1):
        try:
            data = load_pair_data(data_dir, pair)
        except Exception:
            msg = traceback.format_exc()
            logger.error("Failed to load data for %s:\n%s", pair, msg)
            errors.append({"pair": pair, "strategy": "all", "error": "data_load", "traceback": msg})
            continue

        results[pair] = {}
        for strat_name, spec in STRATEGIES.items():
            try:
                # Use best params from phase 2, fallback to defaults
                p2_entry = (phase2.get(pair, {}).get(strat_name, {}))
                params = p2_entry.get("best_params", spec["defaults"])

                strategy = spec["factory"](params)
                engine = MultiTimeframeBacktestEngine(config=REGIME_CONFIG)
                result = await engine.run(strategy, data)
                results[pair][strat_name] = result_to_dict(result)
                ok_count += 1
                logger.info(
                    "  %s / %s: return=%.2f%% sharpe=%s regime_blocks=%d risk_blocks=%d",
                    pair, strat_name,
                    float(result.total_return_pct),
                    result.sharpe_ratio,
                    result.regime_filter_blocks,
                    result.risk_manager_blocks,
                )
            except Exception:
                msg = traceback.format_exc()
                logger.error("  %s / %s FAILED:\n%s", pair, strat_name, msg)
                errors.append({"pair": pair, "strategy": strat_name, "error": str(sys.exc_info()[1]), "traceback": msg})

        if i % 10 == 0 or i == len(pairs):
            tg_send(f"Phase 3 progress: {i}/{len(pairs)} pairs ({ok_count} OK, {len(errors)} err)")

    elapsed = time.monotonic() - t0
    total = len(pairs) * len(STRATEGIES)
    logger.info("Phase 3 done: %d/%d OK, %d errors", ok_count, total, len(errors))
    tg_send(f"✅ *Phase 3 done* ({elapsed:.0f}s)\n{ok_count}/{total} OK, {len(errors)} errors")

    save_json(results, RESULTS_DIR / "phase3_regime.json")
    if errors:
        save_json(errors, RESULTS_DIR / "phase3_errors.json")
    for e in errors:
        e.setdefault("phase", 3)
    ALL_ERRORS.extend(errors)

    return results


async def phase4_robustness(
    pairs: list[str], data_dir: str, phase2: dict[str, Any],
) -> dict[str, Any]:
    """Phase 4: Robustness — walk-forward, stress, Monte Carlo, sensitivity."""
    logger.info("=" * 60)
    logger.info("PHASE 4: Robustness (%d pairs × 3 strategies)", len(pairs))
    logger.info("=" * 60)

    robustness: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    ok_count = 0
    t0 = time.monotonic()

    wf_cfg = WalkForwardConfig(n_splits=5, train_pct=0.7, backtest_config=BASELINE_CONFIG)
    wf = WalkForwardAnalysis(config=wf_cfg)
    stress_cfg = StressTestConfig(num_periods=3, backtest_config=BASELINE_CONFIG)
    mc = MonteCarloSimulation(config=MonteCarloConfig(n_simulations=500))
    sa = SensitivityAnalysis()

    for i, pair in enumerate(pairs, 1):
        try:
            data = load_pair_data(data_dir, pair)
        except Exception:
            msg = traceback.format_exc()
            logger.error("Failed to load data for %s:\n%s", pair, msg)
            errors.append({"pair": pair, "strategy": "all", "error": "data_load", "traceback": msg})
            continue

        robustness[pair] = {}
        for strat_name, spec in STRATEGIES.items():
            p2_entry = phase2.get(pair, {}).get(strat_name, {})
            params = p2_entry.get("best_params", spec["defaults"])
            entry: dict[str, Any] = {}

            # --- 4a: Walk-Forward ---
            try:
                logger.info("  %s / %s walk-forward ...", pair, strat_name)
                strategy = spec["factory"](params)
                wf_result = await wf.run(strategy, data)
                entry["walk_forward"] = {
                    "consistency_ratio": wf_result.consistency_ratio,
                    "aggregate_return_pct": float(wf_result.aggregate_test_return_pct),
                    "aggregate_sharpe": float(wf_result.aggregate_test_sharpe) if wf_result.aggregate_test_sharpe else None,
                    "avg_win_rate": float(wf_result.avg_test_win_rate),
                    "avg_drawdown_pct": float(wf_result.avg_test_drawdown_pct),
                    "is_robust": wf_result.is_robust(min_consistency=0.6),
                }
            except Exception:
                msg = traceback.format_exc()
                logger.error("    walk-forward FAILED: %s", msg)
                errors.append({"pair": pair, "strategy": strat_name, "phase": "4a_wf", "error": str(sys.exc_info()[1]), "traceback": msg})

            # --- 4b: Stress Testing ---
            try:
                logger.info("  %s / %s stress test ...", pair, strat_name)
                stress_result = await StressTester().run(
                    strategy_factory=lambda p=params, f=spec["factory"]: f(p),
                    data=data,
                    config=stress_cfg,
                )
                entry["stress"] = {
                    "worst_return_pct": stress_result.worst_return_pct,
                    "avg_return_pct": stress_result.avg_return_pct,
                    "num_periods": len(stress_result.periods),
                }
            except Exception:
                msg = traceback.format_exc()
                logger.error("    stress FAILED: %s", msg)
                errors.append({"pair": pair, "strategy": strat_name, "phase": "4b_stress", "error": str(sys.exc_info()[1]), "traceback": msg})

            # --- 4c: Monte Carlo ---
            try:
                logger.info("  %s / %s Monte Carlo ...", pair, strat_name)
                # Need a baseline result to feed into MC
                strategy = spec["factory"](params)
                engine = MultiTimeframeBacktestEngine(config=BASELINE_CONFIG)
                base_result = await engine.run(strategy, data)
                mc_result = mc.run(base_result)
                entry["monte_carlo"] = {
                    "probability_of_profit": mc_result.probability_of_profit,
                    "probability_of_worse_drawdown": mc_result.probability_of_worse_drawdown,
                    "var_5pct": mc_result.get_var(0.05),
                    "cvar_5pct": mc_result.get_cvar(0.05),
                    "return_p50": mc_result.return_percentiles.get(0.50, 0.0),
                    "drawdown_p95": mc_result.drawdown_percentiles.get(0.95, 0.0),
                }
            except Exception:
                msg = traceback.format_exc()
                logger.error("    MC FAILED: %s", msg)
                errors.append({"pair": pair, "strategy": strat_name, "phase": "4c_mc", "error": str(sys.exc_info()[1]), "traceback": msg})

            # --- 4d: Sensitivity Analysis ---
            try:
                logger.info("  %s / %s sensitivity ...", pair, strat_name)
                sens_ranges = generate_sensitivity_ranges(params, pct=0.20)
                if sens_ranges:
                    sa_result = await sa.run(
                        strategy_factory=spec["factory"],
                        base_params=params,
                        param_ranges=sens_ranges,
                        data=data,
                    )
                    ranking = sa_result.rank_by_impact("total_return_pct")
                    entry["sensitivity"] = {
                        "impact_ranking": ranking,
                        "most_sensitive": sa_result.most_sensitive_param("total_return_pct"),
                    }
                else:
                    entry["sensitivity"] = {"impact_ranking": [], "most_sensitive": None}
            except Exception:
                msg = traceback.format_exc()
                logger.error("    sensitivity FAILED: %s", msg)
                errors.append({"pair": pair, "strategy": strat_name, "phase": "4d_sens", "error": str(sys.exc_info()[1]), "traceback": msg})

            robustness[pair][strat_name] = entry
            ok_count += 1

        if i % 5 == 0 or i == len(pairs):
            el = time.monotonic() - t0
            tg_send(f"Phase 4 progress: {i}/{len(pairs)} pairs ({ok_count} OK, {len(errors)} err, {el:.0f}s)")

    elapsed = time.monotonic() - t0
    total = len(pairs) * len(STRATEGIES)
    logger.info("Phase 4 done: %d/%d OK, %d errors", ok_count, total, len(errors))
    tg_send(f"✅ *Phase 4 done* ({elapsed:.0f}s)\n{ok_count}/{total} OK, {len(errors)} errors")

    save_json(robustness, RESULTS_DIR / "phase4_robustness.json")
    if errors:
        save_json(errors, RESULTS_DIR / "phase4_errors.json")
    for e in errors:
        e.setdefault("phase", 4)
    ALL_ERRORS.extend(errors)

    return robustness


def phase5_report(
    phase1: dict | None,
    phase2: dict | None,
    phase3: dict | None,
    phase4: dict | None,
) -> None:
    """Phase 5: Final report — ranking, filtering, regime routing table."""
    logger.info("=" * 60)
    logger.info("PHASE 5: Final Report")
    logger.info("=" * 60)

    # Build combined ranking from phase3 (regime-aware) results
    ranking: list[dict[str, Any]] = []

    if phase3:
        for pair, strats in phase3.items():
            for strat_name, data in strats.items():
                sharpe = data.get("sharpe_ratio")
                sharpe_f = float(sharpe) if sharpe is not None else float("-inf")
                entry = {
                    "pair": pair,
                    "strategy": strat_name,
                    "sharpe_ratio": sharpe_f,
                    "total_return_pct": float(data.get("total_return_pct", 0)),
                    "max_drawdown_pct": float(data.get("max_drawdown_pct", 0)),
                    "win_rate": float(data.get("win_rate", 0)),
                    "total_trades": data.get("total_trades", 0),
                    "regime_filter_blocks": data.get("regime_filter_blocks", 0),
                    "risk_manager_blocks": data.get("risk_manager_blocks", 0),
                }

                # Attach robustness flags from phase4
                if phase4:
                    rob = phase4.get(pair, {}).get(strat_name, {})
                    wf = rob.get("walk_forward", {})
                    stress = rob.get("stress", {})
                    entry["wf_consistent"] = wf.get("is_robust", False)
                    entry["wf_consistency_ratio"] = wf.get("consistency_ratio", 0)
                    entry["stress_worst_return"] = stress.get("worst_return_pct", 0)
                else:
                    entry["wf_consistent"] = None
                    entry["wf_consistency_ratio"] = None
                    entry["stress_worst_return"] = None

                ranking.append(entry)

    # Sort by Sharpe descending
    ranking.sort(key=lambda x: x["sharpe_ratio"], reverse=True)

    # Filter: remove entries that fail robustness thresholds
    filtered: list[dict[str, Any]] = []
    for e in ranking:
        reasons: list[str] = []
        if e.get("wf_consistent") is False:
            reasons.append("wf_consistency<0.6")
        if e["sharpe_ratio"] < 0:
            reasons.append("negative_sharpe")
        if e.get("max_drawdown_pct", 0) > 15:
            reasons.append("max_dd>15%")

        e["rejected"] = bool(reasons)
        e["reject_reasons"] = reasons
        filtered.append(e)

    # Build regime routing table: best strategy per pair
    routing: dict[str, dict[str, Any]] = {}
    for e in filtered:
        pair = e["pair"]
        if pair not in routing and not e["rejected"]:
            # Best non-rejected strategy per pair (already sorted by Sharpe)
            routing[pair] = {
                "strategy": e["strategy"],
                "sharpe": e["sharpe_ratio"],
                "return_pct": e["total_return_pct"],
                "max_dd_pct": e["max_drawdown_pct"],
            }
            if phase2:
                p2 = phase2.get(pair, {}).get(e["strategy"], {})
                routing[pair]["best_params"] = p2.get("best_params", {})

    # Summary
    total = len(ranking)
    accepted = sum(1 for e in filtered if not e["rejected"])
    logger.info("Final ranking: %d entries, %d accepted, %d rejected", total, accepted, total - accepted)
    logger.info("Regime routing table: %d pairs covered", len(routing))

    # Build top-5 summary for Telegram
    top_lines: list[str] = []
    for pair, info in routing.items():
        logger.info(
            "  %s → %s (Sharpe=%.2f, Return=%.2f%%)",
            pair, info["strategy"], info["sharpe"], info["return_pct"],
        )
        if len(top_lines) < 5:
            top_lines.append(f"  {pair} → {info['strategy']} (Sharpe={info['sharpe']:.2f})")

    top_str = "\n".join(top_lines) if top_lines else "  (none)"
    tg_send(
        f"✅ *Phase 5 — Final Report*\n"
        f"Total: {total}, Accepted: {accepted}, Rejected: {total - accepted}\n"
        f"Pairs covered: {len(routing)}\n\n"
        f"Top results:\n{top_str}"
    )

    # Save outputs
    report = {
        "generated_at": datetime.now().isoformat(),
        "ranking": filtered,
        "routing_table": routing,
        "summary": {
            "total_entries": total,
            "accepted": accepted,
            "rejected": total - accepted,
            "pairs_covered": len(routing),
        },
    }

    save_json(report, RESULTS_DIR / "final_report.json")
    save_json(routing, RESULTS_DIR / "regime_routing_table.json")


# ---------------------------------------------------------------------------
# Main pipeline runner
# ---------------------------------------------------------------------------


async def run_pipeline(args: argparse.Namespace) -> None:
    """Execute the backtesting pipeline based on CLI arguments."""
    data_dir = args.data_dir
    workers = args.workers

    # Determine pairs
    if args.symbols:
        pairs = [s.strip().upper() + "_USDT" if "_" not in s.strip().upper() else s.strip().upper() for s in args.symbols.split(",")]
    else:
        pairs = discover_pairs(data_dir)

    if not pairs:
        logger.error("No pairs found. Provide --symbols or check --data-dir")
        sys.exit(1)

    logger.info("Pipeline starting: %d pairs, %d workers", len(pairs), workers)
    logger.info("Pairs: %s", ", ".join(pairs))
    tg_send(f"🚀 *Pipeline started*\nPairs: {len(pairs)}, Workers: {workers}\nPhases: {phases if args.phase else 'all (1-5)'}")

    # Determine which phases to run
    if args.phase:
        phases = [args.phase]
    else:
        start = args.start_phase or 1
        phases = list(range(start, 6))

    logger.info("Phases to run: %s", phases)

    phase1_data = None
    phase2_data = None
    phase3_data = None
    phase4_data = None

    # Load prior phase results if resuming
    if 1 not in phases:
        p1_path = RESULTS_DIR / "phase1_baseline.json"
        if p1_path.exists():
            phase1_data = json.loads(p1_path.read_text())

    if 2 not in phases:
        p2_path = RESULTS_DIR / "phase2_optimization.json"
        if p2_path.exists():
            phase2_data = json.loads(p2_path.read_text())

    if 3 not in phases and 5 in phases:
        p3_path = RESULTS_DIR / "phase3_regime.json"
        if p3_path.exists():
            phase3_data = json.loads(p3_path.read_text())

    if 4 not in phases and 5 in phases:
        p4_path = RESULTS_DIR / "phase4_robustness.json"
        if p4_path.exists():
            phase4_data = json.loads(p4_path.read_text())

    t_start = time.monotonic()

    # --- Phase 1 ---
    if 1 in phases:
        phase1_data = await phase1_baseline(pairs, data_dir, workers)

    # --- Phase 2 ---
    if 2 in phases:
        phase2_data = await phase2_optimization(pairs, data_dir, workers)

    # --- Phase 3 ---
    if 3 in phases:
        if phase2_data is None:
            logger.warning("Phase 2 results not available; using default params for Phase 3")
            phase2_data = {}
        phase3_data = await phase3_regime(pairs, data_dir, phase2_data)

    # --- Phase 4 ---
    if 4 in phases:
        if phase2_data is None:
            logger.warning("Phase 2 results not available; using default params for Phase 4")
            phase2_data = {}
        phase4_data = await phase4_robustness(pairs, data_dir, phase2_data)

    # --- Phase 5 ---
    if 5 in phases:
        phase5_report(phase1_data, phase2_data, phase3_data, phase4_data)

    elapsed = time.monotonic() - t_start
    logger.info("Pipeline complete in %.1f seconds (%.1f min)", elapsed, elapsed / 60)

    # --- Save consolidated error log ---
    _save_error_summary(elapsed)

    mins = elapsed / 60
    tg_send(
        f"🏁 *Pipeline finished* ({mins:.1f} min)\n"
        f"Total errors: {len(ALL_ERRORS)}"
    )


def _save_error_summary(elapsed: float) -> None:
    """Save consolidated error log across all phases."""
    summary = {
        "generated_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "total_errors": len(ALL_ERRORS),
        "errors_by_phase": {},
        "errors_by_pair": {},
        "errors_by_strategy": {},
        "errors": ALL_ERRORS,
    }

    # Aggregate counts
    for e in ALL_ERRORS:
        phase = str(e.get("phase", "unknown"))
        pair = e.get("pair", "unknown")
        strat = e.get("strategy", "unknown")
        summary["errors_by_phase"][phase] = summary["errors_by_phase"].get(phase, 0) + 1
        summary["errors_by_pair"][pair] = summary["errors_by_pair"].get(pair, 0) + 1
        summary["errors_by_strategy"][strat] = summary["errors_by_strategy"].get(strat, 0) + 1

    save_json(summary, RESULTS_DIR / "pipeline_errors.json")

    if ALL_ERRORS:
        logger.warning(
            "TOTAL ERRORS: %d (by phase: %s)",
            len(ALL_ERRORS),
            summary["errors_by_phase"],
        )
    else:
        logger.info("No errors across all phases")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DCA + TF + SMC Backtesting Pipeline (Phases 1-5)",
    )
    parser.add_argument(
        "--data-dir", required=True,
        help="Directory with *_5m.csv historical data files",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Max parallel workers for optimization (default: 4)",
    )
    parser.add_argument(
        "--phase", type=int, choices=[1, 2, 3, 4, 5],
        help="Run only this phase",
    )
    parser.add_argument(
        "--start-phase", type=int, choices=[1, 2, 3, 4, 5],
        help="Start from this phase (run all subsequent phases)",
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated symbols (e.g. BTC,ETH,SOL). Auto-appends _USDT if needed.",
    )

    args = parser.parse_args()

    log_path = setup_logging()
    logger.info("Log file: %s", log_path)

    try:
        asyncio.run(run_pipeline(args))
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user (Ctrl+C)")
        tg_send(f"⚠️ *Pipeline interrupted* (Ctrl+C)\nErrors so far: {len(ALL_ERRORS)}")
        _save_error_summary(0)
        sys.exit(130)
    except Exception:
        msg = traceback.format_exc()
        logger.critical("SYSTEM CRASH:\n%s", msg)
        short_err = str(sys.exc_info()[1])[:200]
        ALL_ERRORS.append({
            "phase": "system",
            "pair": "N/A",
            "strategy": "N/A",
            "error": str(sys.exc_info()[1]),
            "traceback": msg,
        })
        tg_send(f"🔴 *SYSTEM CRASH*\n{short_err}")
        _save_error_summary(0)
        sys.exit(1)


if __name__ == "__main__":
    main()
