"""Tests for OptimizationCheckpoint — trial save/resume."""

import os
import tempfile

import pytest

from grid_backtester.persistence.checkpoint import OptimizationCheckpoint


class TestOptimizationCheckpoint:

    def _make_checkpoint(self, tmpdir: str) -> OptimizationCheckpoint:
        return OptimizationCheckpoint(checkpoint_dir=tmpdir)

    def test_save_and_load_trial(self, tmp_path):
        cp = self._make_checkpoint(str(tmp_path))
        run_id = "test-run-1"

        cp.save_trial(run_id, trial_id=0, config_hash="abc123", result={"roi": 5.0})
        cp.save_trial(run_id, trial_id=1, config_hash="def456", result={"roi": 3.0})

        completed = cp.load_completed(run_id)
        assert len(completed) == 2
        assert completed["abc123"]["roi"] == 5.0
        assert completed["def456"]["roi"] == 3.0

    def test_load_empty_returns_empty(self, tmp_path):
        cp = self._make_checkpoint(str(tmp_path))
        completed = cp.load_completed("nonexistent-run")
        assert completed == {}

    def test_cleanup_removes_file(self, tmp_path):
        cp = self._make_checkpoint(str(tmp_path))
        run_id = "cleanup-test"

        cp.save_trial(run_id, trial_id=0, config_hash="aaa", result={"x": 1})
        assert cp.get_checkpoint_path(run_id).exists()

        cp.cleanup(run_id)
        assert not cp.get_checkpoint_path(run_id).exists()

    def test_cleanup_nonexistent_is_noop(self, tmp_path):
        cp = self._make_checkpoint(str(tmp_path))
        cp.cleanup("no-such-run")  # Should not raise

    def test_list_checkpoints(self, tmp_path):
        cp = self._make_checkpoint(str(tmp_path))
        cp.save_trial("run-a", 0, "h1", {"x": 1})
        cp.save_trial("run-b", 0, "h2", {"x": 2})

        runs = cp.list_checkpoints()
        assert set(runs) == {"run-a", "run-b"}

    def test_config_hash_deterministic(self):
        config = {"symbol": "BTCUSDT", "levels": 15, "spacing": "arithmetic"}
        h1 = OptimizationCheckpoint.config_hash(config)
        h2 = OptimizationCheckpoint.config_hash(config)
        assert h1 == h2
        assert len(h1) == 16

    def test_config_hash_differs_for_different_configs(self):
        config1 = {"symbol": "BTCUSDT", "levels": 15}
        config2 = {"symbol": "ETHUSDT", "levels": 15}
        assert OptimizationCheckpoint.config_hash(config1) != OptimizationCheckpoint.config_hash(config2)

    def test_duplicate_config_hash_overwrites(self, tmp_path):
        cp = self._make_checkpoint(str(tmp_path))
        run_id = "dup-test"

        cp.save_trial(run_id, trial_id=0, config_hash="same", result={"roi": 1.0})
        cp.save_trial(run_id, trial_id=1, config_hash="same", result={"roi": 2.0})

        completed = cp.load_completed(run_id)
        # Last write wins for same config_hash
        assert completed["same"]["roi"] == 2.0

    def test_corrupted_lines_skipped(self, tmp_path):
        cp = self._make_checkpoint(str(tmp_path))
        run_id = "corrupt-test"

        # Write a valid trial
        cp.save_trial(run_id, trial_id=0, config_hash="good", result={"roi": 5.0})

        # Append corrupted data
        path = cp.get_checkpoint_path(run_id)
        with open(path, "a") as f:
            f.write("this is not json\n")
            f.write("{\"bad\": \"no config_hash key\"}\n")

        completed = cp.load_completed(run_id)
        assert len(completed) == 1
        assert "good" in completed
