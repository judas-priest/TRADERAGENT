"""
Preset Export — Export optimized strategy parameters to YAML/JSON.

Exports strategy name, parameters, and key backtest metrics for
reproducible deployment of backtested configurations.

Usage:
    exporter = PresetExporter()
    yaml_str = exporter.export_yaml("smc", best_params, backtest_result)
    exporter.save("/tmp/preset.yaml", yaml_str)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bot.tests.backtesting.backtesting_engine import BacktestResult


class PresetExporter:
    """Export optimized strategy parameters as YAML or JSON presets."""

    def _build_preset(
        self,
        strategy_name: str,
        params: dict[str, Any],
        result: BacktestResult,
    ) -> dict[str, Any]:
        """Build the preset data structure."""
        return {
            "strategy": strategy_name,
            "params": {k: self._serialize_value(v) for k, v in params.items()},
            "metrics": {
                "total_return_pct": float(result.total_return_pct),
                "sharpe_ratio": float(result.sharpe_ratio) if result.sharpe_ratio else None,
                "sortino_ratio": float(result.sortino_ratio) if result.sortino_ratio else None,
                "calmar_ratio": float(result.calmar_ratio) if result.calmar_ratio else None,
                "max_drawdown_pct": float(result.max_drawdown_pct),
                "profit_factor": float(result.profit_factor) if result.profit_factor else None,
                "win_rate": float(result.win_rate),
                "total_trades": result.total_trades,
            },
        }

    def export_yaml(
        self,
        strategy_name: str,
        params: dict[str, Any],
        result: BacktestResult,
    ) -> str:
        """Export preset as YAML string."""
        preset = self._build_preset(strategy_name, params, result)
        # Simple YAML serialization without external dependency
        lines = []
        lines.append(f"strategy: {preset['strategy']}")
        lines.append("params:")
        for k, v in preset["params"].items():
            lines.append(f"  {k}: {v}")
        lines.append("metrics:")
        for k, v in preset["metrics"].items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines) + "\n"

    def export_json(
        self,
        strategy_name: str,
        params: dict[str, Any],
        result: BacktestResult,
    ) -> str:
        """Export preset as JSON string."""
        preset = self._build_preset(strategy_name, params, result)
        return json.dumps(preset, indent=2)

    def save(self, filepath: str | Path, content: str) -> Path:
        """Save preset content to file."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    @staticmethod
    def _serialize_value(v: Any) -> Any:
        """Convert Decimal and other types to JSON-safe values."""
        from decimal import Decimal

        if isinstance(v, Decimal):
            return float(v)
        return v
