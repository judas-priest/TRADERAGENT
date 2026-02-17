"""
OptimizationCheckpoint — Save/resume optimization trials (Issue #11).

Saves completed trial results to disk so that optimization can be resumed
after interruption without re-running already completed trials.
"""

import json
import os
from pathlib import Path
from typing import Any

from grid_backtester.logging import get_logger

logger = get_logger(__name__)


class OptimizationCheckpoint:
    """
    Manages optimization checkpoint files for incremental resume.

    Each optimization run gets a unique checkpoint file based on symbol + config hash.
    Completed trials are appended to the file. On resume, already-computed trials
    are loaded and skipped.
    """

    def __init__(self, checkpoint_dir: str = "data/checkpoints") -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def get_checkpoint_path(self, run_id: str) -> Path:
        """Get checkpoint file path for a run."""
        return self.checkpoint_dir / f"{run_id}.jsonl"

    def save_trial(self, run_id: str, trial_id: int, config_hash: str, result: dict[str, Any]) -> None:
        """Append a completed trial to checkpoint."""
        path = self.get_checkpoint_path(run_id)
        entry = {
            "trial_id": trial_id,
            "config_hash": config_hash,
            "result": result,
        }
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        logger.debug("Trial checkpointed", run_id=run_id, trial_id=trial_id)

    def load_completed(self, run_id: str) -> dict[str, dict[str, Any]]:
        """Load completed trials from checkpoint. Returns config_hash -> result mapping."""
        path = self.get_checkpoint_path(run_id)
        if not path.exists():
            return {}

        completed: dict[str, dict[str, Any]] = {}
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    completed[entry["config_hash"]] = entry["result"]
                except (json.JSONDecodeError, KeyError):
                    continue

        logger.info(
            "Checkpoint loaded",
            run_id=run_id,
            completed_trials=len(completed),
        )
        return completed

    def cleanup(self, run_id: str) -> None:
        """Remove checkpoint file after successful completion."""
        path = self.get_checkpoint_path(run_id)
        if path.exists():
            os.remove(path)
            logger.info("Checkpoint cleaned up", run_id=run_id)

    def list_checkpoints(self) -> list[str]:
        """List all active checkpoint run IDs."""
        return [
            p.stem for p in self.checkpoint_dir.glob("*.jsonl")
        ]

    @staticmethod
    def config_hash(config_dict: dict[str, Any]) -> str:
        """Generate a hash for a config dict to identify unique trials."""
        import hashlib
        serialized = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
