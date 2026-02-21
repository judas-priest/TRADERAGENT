"""
Tests for the gradual capital deployment manager.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from bot.utils.capital_manager import (
    DEFAULT_PHASES,
    CapitalManager,
    DeploymentPhase,
    PhaseMetrics,
    ScalingDecision,
)

# ===========================================================================
# DeploymentPhase enum
# ===========================================================================


class TestDeploymentPhase:
    def test_phase_values(self):
        assert DeploymentPhase.PHASE_1.value == "phase_1_5pct"
        assert DeploymentPhase.PHASE_2.value == "phase_2_25pct"
        assert DeploymentPhase.PHASE_3.value == "phase_3_100pct"
        assert DeploymentPhase.HALTED.value == "halted"

    def test_is_string_enum(self):
        assert isinstance(DeploymentPhase.PHASE_1, str)
        assert DeploymentPhase.PHASE_1 == "phase_1_5pct"


# ===========================================================================
# PhaseMetrics
# ===========================================================================


class TestPhaseMetrics:
    def test_win_rate_zero_trades(self):
        m = PhaseMetrics(phase=DeploymentPhase.PHASE_1, started_at=datetime.now(timezone.utc))
        assert m.win_rate == Decimal("0")

    def test_win_rate_calculation(self):
        m = PhaseMetrics(
            phase=DeploymentPhase.PHASE_1,
            started_at=datetime.now(timezone.utc),
            total_trades=10,
            winning_trades=7,
        )
        assert m.win_rate == Decimal("0.7")

    def test_duration_days(self):
        m = PhaseMetrics(
            phase=DeploymentPhase.PHASE_1,
            started_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        assert m.duration_days == 5

    def test_to_dict(self):
        m = PhaseMetrics(
            phase=DeploymentPhase.PHASE_1,
            started_at=datetime.now(timezone.utc),
            total_trades=3,
            winning_trades=2,
            total_pnl=Decimal("100"),
            current_balance=Decimal("600"),
        )
        d = m.to_dict()
        assert d["phase"] == "phase_1_5pct"
        assert d["total_trades"] == 3
        assert d["winning_trades"] == 2
        assert float(d["win_rate"]) == pytest.approx(2 / 3)
        assert d["total_pnl"] == "100"
        assert d["current_balance"] == "600"
        assert "started_at" in d
        assert "duration_days" in d

    def test_default_values(self):
        m = PhaseMetrics(phase=DeploymentPhase.PHASE_1, started_at=datetime.now(timezone.utc))
        assert m.total_trades == 0
        assert m.winning_trades == 0
        assert m.total_pnl == Decimal("0")
        assert m.max_drawdown_pct == Decimal("0")
        assert m.errors_count == 0


# ===========================================================================
# CapitalManager — Initialization
# ===========================================================================


class TestCapitalManagerInit:
    def test_default_capital(self):
        cm = CapitalManager()
        assert cm.total_capital == Decimal("10000")

    def test_custom_capital(self):
        cm = CapitalManager(total_capital=Decimal("50000"))
        assert cm.total_capital == Decimal("50000")

    def test_starts_halted(self):
        cm = CapitalManager()
        assert cm.current_phase == DeploymentPhase.HALTED

    def test_allocated_capital_when_halted(self):
        cm = CapitalManager()
        assert cm.allocated_capital == Decimal("0")

    def test_default_phases(self):
        cm = CapitalManager()
        assert len(cm.phases) == 3

    def test_custom_phases(self):
        custom = [DEFAULT_PHASES[0]]
        cm = CapitalManager(phases=custom)
        assert len(cm.phases) == 1


# ===========================================================================
# CapitalManager — Phase 1
# ===========================================================================


class TestCapitalManagerPhase1:
    def test_start_phase_1(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        alloc = cm.start_phase_1()
        assert alloc == Decimal("500")  # 5% of 10000
        assert cm.current_phase == DeploymentPhase.PHASE_1

    def test_allocated_capital_phase_1(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        assert cm.allocated_capital == Decimal("500")

    def test_phase_1_metrics_initialized(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        assert cm.current_metrics is not None
        assert cm.current_metrics.phase == DeploymentPhase.PHASE_1
        assert cm.current_metrics.current_balance == Decimal("500")
        assert cm.current_metrics.peak_balance == Decimal("500")


# ===========================================================================
# CapitalManager — Recording Trades
# ===========================================================================


class TestRecordTrade:
    def test_record_winning_trade(self):
        cm = CapitalManager()
        cm.start_phase_1()
        cm.record_trade(won=True, pnl=Decimal("50"))
        assert cm.current_metrics.total_trades == 1
        assert cm.current_metrics.winning_trades == 1
        assert cm.current_metrics.total_pnl == Decimal("50")

    def test_record_losing_trade(self):
        cm = CapitalManager()
        cm.start_phase_1()
        cm.record_trade(won=False, pnl=Decimal("-30"))
        assert cm.current_metrics.total_trades == 1
        assert cm.current_metrics.winning_trades == 0
        assert cm.current_metrics.total_pnl == Decimal("-30")

    def test_multiple_trades(self):
        cm = CapitalManager()
        cm.start_phase_1()
        cm.record_trade(won=True, pnl=Decimal("50"))
        cm.record_trade(won=True, pnl=Decimal("30"))
        cm.record_trade(won=False, pnl=Decimal("-20"))
        assert cm.current_metrics.total_trades == 3
        assert cm.current_metrics.winning_trades == 2
        assert cm.current_metrics.total_pnl == Decimal("60")

    def test_balance_updated(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.record_trade(won=True, pnl=Decimal("50"))
        assert cm.current_metrics.current_balance == Decimal("550")

    def test_peak_balance_tracked(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.record_trade(won=True, pnl=Decimal("100"))
        cm.record_trade(won=False, pnl=Decimal("-50"))
        assert cm.current_metrics.peak_balance == Decimal("600")
        assert cm.current_metrics.current_balance == Decimal("550")

    def test_drawdown_tracked(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        # Balance starts at 500, goes to 600, drops to 540
        cm.record_trade(won=True, pnl=Decimal("100"))
        cm.record_trade(won=False, pnl=Decimal("-60"))
        # Drawdown = (600 - 540) / 600 = 10%
        assert cm.current_metrics.max_drawdown_pct == Decimal("60") / Decimal("600")

    def test_no_active_phase_raises(self):
        cm = CapitalManager()
        with pytest.raises(RuntimeError, match="No active phase"):
            cm.record_trade(won=True, pnl=Decimal("10"))


# ===========================================================================
# CapitalManager — Record Error
# ===========================================================================


class TestRecordError:
    def test_record_error(self):
        cm = CapitalManager()
        cm.start_phase_1()
        cm.record_error()
        assert cm.current_metrics.errors_count == 1

    def test_record_error_no_phase(self):
        cm = CapitalManager()
        # Should not raise, just no-op
        cm.record_error()


# ===========================================================================
# CapitalManager — Evaluate Scaling
# ===========================================================================


class TestEvaluateScaling:
    def _make_ready_cm(self) -> CapitalManager:
        """Create a CM that meets all Phase 1 scaling gates."""
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        # Backdate start to meet 3-day requirement
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=4)
        # Record 5 winning trades
        for _ in range(5):
            cm.record_trade(won=True, pnl=Decimal("10"))
        return cm

    def test_no_active_phase(self):
        cm = CapitalManager()
        decision = cm.evaluate_scaling()
        assert not decision.can_scale
        assert "No active phase" in decision.blockers

    def test_can_scale_when_gates_met(self):
        cm = self._make_ready_cm()
        decision = cm.evaluate_scaling()
        assert decision.can_scale
        assert decision.next_phase == DeploymentPhase.PHASE_2
        assert len(decision.blockers) == 0

    def test_blocked_by_duration(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        # Only 1 day old
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=1)
        for _ in range(5):
            cm.record_trade(won=True, pnl=Decimal("10"))
        decision = cm.evaluate_scaling()
        assert not decision.can_scale
        assert any("Duration" in b for b in decision.blockers)

    def test_blocked_by_trade_count(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=4)
        # Only 2 trades, need 5
        cm.record_trade(won=True, pnl=Decimal("10"))
        cm.record_trade(won=True, pnl=Decimal("10"))
        decision = cm.evaluate_scaling()
        assert not decision.can_scale
        assert any("Trades" in b for b in decision.blockers)

    def test_blocked_by_win_rate(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=4)
        # 1 win, 5 losses = 16.7% win rate < 40%
        cm.record_trade(won=True, pnl=Decimal("10"))
        for _ in range(5):
            cm.record_trade(won=False, pnl=Decimal("-1"))
        decision = cm.evaluate_scaling()
        assert not decision.can_scale
        assert any("Win rate" in b for b in decision.blockers)

    def test_blocked_by_drawdown(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=4)
        # Big gain then big loss to trigger >5% drawdown
        cm.record_trade(won=True, pnl=Decimal("100"))
        cm.record_trade(won=True, pnl=Decimal("100"))
        cm.record_trade(won=True, pnl=Decimal("100"))
        cm.record_trade(won=True, pnl=Decimal("100"))
        cm.record_trade(won=False, pnl=Decimal("-200"))
        # peak=900, current=700, drawdown=22%
        decision = cm.evaluate_scaling()
        assert not decision.can_scale
        assert any("Drawdown" in b for b in decision.blockers)

    def test_blocked_by_negative_pnl(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=4)
        # 5 trades but net negative (3 wins, 2 big losses)
        cm.record_trade(won=True, pnl=Decimal("5"))
        cm.record_trade(won=True, pnl=Decimal("5"))
        cm.record_trade(won=True, pnl=Decimal("5"))
        cm.record_trade(won=False, pnl=Decimal("-10"))
        cm.record_trade(won=False, pnl=Decimal("-10"))
        decision = cm.evaluate_scaling()
        assert not decision.can_scale
        assert any("PnL" in b for b in decision.blockers)

    def test_already_at_max_phase(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.current_phase = DeploymentPhase.PHASE_3
        cm.current_metrics = PhaseMetrics(
            phase=DeploymentPhase.PHASE_3,
            started_at=datetime.now(timezone.utc),
        )
        decision = cm.evaluate_scaling()
        assert not decision.can_scale
        assert "Already at maximum allocation" in decision.reasons

    def test_scaling_decision_fields(self):
        cm = self._make_ready_cm()
        decision = cm.evaluate_scaling()
        assert decision.current_phase == DeploymentPhase.PHASE_1
        assert decision.next_phase == DeploymentPhase.PHASE_2
        assert len(decision.reasons) > 0


# ===========================================================================
# CapitalManager — Advance Phase
# ===========================================================================


class TestAdvancePhase:
    def _make_ready_cm(self) -> CapitalManager:
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=4)
        for _ in range(5):
            cm.record_trade(won=True, pnl=Decimal("10"))
        return cm

    def test_advance_to_phase_2(self):
        cm = self._make_ready_cm()
        alloc = cm.advance_phase()
        assert cm.current_phase == DeploymentPhase.PHASE_2
        assert alloc == Decimal("2500")  # 25% of 10000

    def test_advance_archives_metrics(self):
        cm = self._make_ready_cm()
        cm.advance_phase()
        assert len(cm.phase_history) == 1
        assert cm.phase_history[0].phase == DeploymentPhase.PHASE_1

    def test_advance_resets_metrics(self):
        cm = self._make_ready_cm()
        cm.advance_phase()
        assert cm.current_metrics.phase == DeploymentPhase.PHASE_2
        assert cm.current_metrics.total_trades == 0
        assert cm.current_metrics.current_balance == Decimal("2500")

    def test_advance_fails_if_not_ready(self):
        cm = CapitalManager()
        cm.start_phase_1()
        with pytest.raises(RuntimeError, match="Cannot advance"):
            cm.advance_phase()

    def test_full_phase_progression(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        # Phase 1
        cm.start_phase_1()
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=4)
        for _ in range(5):
            cm.record_trade(won=True, pnl=Decimal("10"))
        cm.advance_phase()
        assert cm.current_phase == DeploymentPhase.PHASE_2

        # Phase 2
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=8)
        for _ in range(20):
            cm.record_trade(won=True, pnl=Decimal("20"))
        cm.advance_phase()
        assert cm.current_phase == DeploymentPhase.PHASE_3
        assert cm.allocated_capital == Decimal("10000")
        assert len(cm.phase_history) == 2


# ===========================================================================
# CapitalManager — Halt
# ===========================================================================


class TestHalt:
    def test_halt(self):
        cm = CapitalManager()
        cm.start_phase_1()
        cm.halt(reason="test")
        assert cm.current_phase == DeploymentPhase.HALTED
        assert cm.current_metrics is None
        assert cm.allocated_capital == Decimal("0")

    def test_halt_archives_metrics(self):
        cm = CapitalManager()
        cm.start_phase_1()
        cm.record_trade(won=True, pnl=Decimal("10"))
        cm.halt()
        assert len(cm.phase_history) == 1

    def test_halt_when_already_halted(self):
        cm = CapitalManager()
        cm.halt()  # No-op, no error
        assert cm.current_phase == DeploymentPhase.HALTED


# ===========================================================================
# CapitalManager — Report
# ===========================================================================


class TestGetReport:
    def test_report_halted(self):
        cm = CapitalManager()
        report = cm.get_report()
        assert report["current_phase"] == "halted"
        assert report["allocated_capital"] == "0"
        assert report["current_metrics"] is None
        assert report["phase_history"] == []

    def test_report_active(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.record_trade(won=True, pnl=Decimal("50"))
        report = cm.get_report()
        assert report["total_capital"] == "10000"
        assert report["current_phase"] == "phase_1_5pct"
        assert Decimal(report["allocated_capital"]) == Decimal("500")
        assert report["current_metrics"] is not None
        assert report["current_metrics"]["total_trades"] == 1

    def test_report_with_history(self):
        cm = CapitalManager(total_capital=Decimal("10000"))
        cm.start_phase_1()
        cm.current_metrics.started_at = datetime.now(timezone.utc) - timedelta(days=4)
        for _ in range(5):
            cm.record_trade(won=True, pnl=Decimal("10"))
        cm.advance_phase()
        report = cm.get_report()
        assert len(report["phase_history"]) == 1
        assert report["current_phase"] == "phase_2_25pct"


# ===========================================================================
# ScalingDecision dataclass
# ===========================================================================


class TestScalingDecision:
    def test_scaling_decision_creation(self):
        sd = ScalingDecision(
            can_scale=True,
            current_phase=DeploymentPhase.PHASE_1,
            next_phase=DeploymentPhase.PHASE_2,
            reasons=["All gates passed"],
        )
        assert sd.can_scale
        assert sd.current_phase == DeploymentPhase.PHASE_1
        assert sd.next_phase == DeploymentPhase.PHASE_2

    def test_default_lists(self):
        sd = ScalingDecision(
            can_scale=False,
            current_phase=DeploymentPhase.PHASE_1,
            next_phase=None,
        )
        assert sd.reasons == []
        assert sd.blockers == []


# ===========================================================================
# DEFAULT_PHASES config
# ===========================================================================


class TestDefaultPhases:
    def test_phase_1_config(self):
        p1 = DEFAULT_PHASES[0]
        assert p1.phase == DeploymentPhase.PHASE_1
        assert p1.allocation_pct == Decimal("0.05")
        assert p1.min_duration_days == 3
        assert p1.max_drawdown_pct == Decimal("0.05")
        assert p1.min_trades == 5
        assert p1.min_win_rate == Decimal("0.40")

    def test_phase_2_config(self):
        p2 = DEFAULT_PHASES[1]
        assert p2.phase == DeploymentPhase.PHASE_2
        assert p2.allocation_pct == Decimal("0.25")
        assert p2.min_duration_days == 7
        assert p2.min_trades == 20

    def test_phase_3_config(self):
        p3 = DEFAULT_PHASES[2]
        assert p3.phase == DeploymentPhase.PHASE_3
        assert p3.allocation_pct == Decimal("1.00")
        assert p3.min_duration_days == 0


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    def test_unknown_phase_raises(self):
        cm = CapitalManager()
        with pytest.raises(ValueError, match="Unknown phase"):
            cm._get_phase_config(DeploymentPhase.HALTED)

    def test_zero_capital(self):
        cm = CapitalManager(total_capital=Decimal("0"))
        alloc = cm.start_phase_1()
        assert alloc == Decimal("0")

    def test_large_capital(self):
        cm = CapitalManager(total_capital=Decimal("1000000"))
        alloc = cm.start_phase_1()
        assert alloc == Decimal("50000")
