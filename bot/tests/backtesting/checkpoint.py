"""
Optimization Checkpointing — JSONL-based trial persistence.

Saves completed optimization trials to disk so that interrupted runs
can be resumed without re-evaluating already-tested parameter combinations.

Usage:
    ckpt = OptimizationCheckpoint(directory="/tmp/checkpoints")
    ckpt.save_trial(run_id, trial_id, config_hash, result_dict)
    completed = ckpt.load_completed(run_id)
    ckpt.cleanup(run_id)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class OptimizationCheckpoint:
    """JSONL append-only checkpoint for optimization trials."""

    def __init__(self, directory: str | Path = "/tmp/backtest_checkpoints") -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _file_path(self, run_id: str) -> Path:
        return self.directory / f"opt_{run_id}.jsonl"

    def save_trial(
        self,
        run_id: str,
        trial_id: str,
        config_hash: str,
        result_dict: dict[str, Any],
    ) -> None:
        """Append a completed trial to the checkpoint file."""
        entry = {
            "trial_id": trial_id,
            "config_hash": config_hash,
            "result": result_dict,
        }
        with open(self._file_path(run_id), "a") as f:
            f.write(json.dumps(entry) + "\n")

    def load_completed(self, run_id: str) -> dict[str, dict]:
        """Load all completed trials for a run.

        Returns:
            Dict mapping config_hash to result dict.
        """
        path = self._file_path(run_id)
        if not path.exists():
            return {}

        completed: dict[str, dict] = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                completed[entry["config_hash"]] = entry["result"]

        return completed

    def cleanup(self, run_id: str) -> None:
        """Remove checkpoint file after successful completion."""
        path = self._file_path(run_id)
        if path.exists():
            path.unlink()

    @staticmethod
    def config_hash(config_dict: dict[str, Any]) -> str:
        """Generate a deterministic hash for a config dict."""
        serialized = json.dumps(config_dict, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
