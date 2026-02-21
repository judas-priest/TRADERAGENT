"""
Tests for production readiness utilities: security audit and config validation.
"""

from decimal import Decimal
from pathlib import Path

from bot.utils.config_validator import ConfigValidationReport, ConfigValidator
from bot.utils.security_audit import SecurityAuditor, SecurityAuditReport

# ===========================================================================
# Security Audit
# ===========================================================================


class TestSecurityAuditor:
    def test_auditor_creates_report(self):
        auditor = SecurityAuditor(project_root=Path(__file__).parent.parent)
        report = auditor.run_full_audit()
        assert isinstance(report, SecurityAuditReport)
        assert len(report.results) > 0

    def test_report_summary(self):
        auditor = SecurityAuditor(project_root=Path(__file__).parent.parent)
        report = auditor.run_full_audit()
        summary = report.summary()
        assert "total_checks" in summary
        assert "passed" in summary
        assert "overall_status" in summary

    def test_gitignore_check(self):
        auditor = SecurityAuditor(project_root=Path(__file__).parent.parent)
        result = auditor._check_gitignore()
        assert result.check_name in ("gitignore_exists", "gitignore_complete")

    def test_env_file_check(self):
        auditor = SecurityAuditor(project_root=Path(__file__).parent.parent)
        result = auditor._check_env_file()
        assert result.check_name in ("env_file_exists", "env_file_protected")

    def test_source_scan(self):
        auditor = SecurityAuditor(project_root=Path(__file__).parent.parent)
        results = auditor._scan_source_for_secrets()
        assert len(results) > 0
        assert results[0].check_name == "no_hardcoded_secrets"

    def test_debug_mode_check(self):
        auditor = SecurityAuditor()
        result = auditor._check_debug_mode()
        assert result.check_name == "debug_disabled"

    def test_database_url_check(self):
        auditor = SecurityAuditor()
        result = auditor._check_database_url()
        assert result.check_name == "database_url_secure"

    def test_redis_url_check(self):
        auditor = SecurityAuditor()
        result = auditor._check_redis_url()
        assert result.check_name == "redis_url_secure"

    def test_report_passed_property(self):
        report = SecurityAuditReport()
        assert report.passed is True  # No checks = passed

    def test_report_critical_failures(self):
        report = SecurityAuditReport()
        from bot.utils.security_audit import AuditResult

        report.results.append(
            AuditResult(check_name="test", passed=False, severity="critical", message="fail")
        )
        assert not report.passed
        assert len(report.critical_failures) == 1

    def test_report_warnings(self):
        report = SecurityAuditReport()
        from bot.utils.security_audit import AuditResult

        report.results.append(
            AuditResult(check_name="test", passed=False, severity="warning", message="warn")
        )
        # Warnings don't affect passed status (only critical does)
        assert report.passed
        assert len(report.warnings) == 1


# ===========================================================================
# Config Validator
# ===========================================================================


class TestConfigValidator:
    def test_default_risk_passes(self):
        validator = ConfigValidator()
        results = validator.validate_risk_params()
        assert all(r.passed for r in results)

    def test_excessive_risk_fails(self):
        validator = ConfigValidator()
        results = validator.validate_risk_params(risk_per_trade=Decimal("0.10"))
        risk_check = next(r for r in results if r.check_name == "risk_per_trade")
        assert not risk_check.passed

    def test_excessive_exposure_fails(self):
        validator = ConfigValidator()
        results = validator.validate_risk_params(max_exposure=Decimal("0.80"))
        check = next(r for r in results if r.check_name == "max_exposure")
        assert not check.passed

    def test_low_risk_reward_fails(self):
        validator = ConfigValidator()
        results = validator.validate_risk_params(min_risk_reward=Decimal("0.5"))
        check = next(r for r in results if r.check_name == "min_risk_reward")
        assert not check.passed

    def test_default_grid_passes(self):
        validator = ConfigValidator()
        results = validator.validate_grid_config()
        assert all(r.passed for r in results)

    def test_excessive_grid_levels_fails(self):
        validator = ConfigValidator()
        results = validator.validate_grid_config(num_levels=100)
        check = next(r for r in results if r.check_name == "grid_levels")
        assert not check.passed

    def test_grid_total_investment_fails(self):
        validator = ConfigValidator()
        results = validator.validate_grid_config(num_levels=50, amount_per_grid=Decimal("2000"))
        check = next(r for r in results if r.check_name == "grid_total_investment")
        assert not check.passed

    def test_wide_grid_range_fails(self):
        validator = ConfigValidator()
        results = validator.validate_grid_config(grid_range_pct=Decimal("0.30"))
        check = next(r for r in results if r.check_name == "grid_range")
        assert not check.passed

    def test_default_dca_passes(self):
        validator = ConfigValidator()
        results = validator.validate_dca_config()
        assert all(r.passed for r in results)

    def test_excessive_safety_orders_fails(self):
        validator = ConfigValidator()
        results = validator.validate_dca_config(max_safety_orders=15)
        check = next(r for r in results if r.check_name == "dca_safety_orders")
        assert not check.passed

    def test_low_take_profit_fails(self):
        validator = ConfigValidator()
        results = validator.validate_dca_config(take_profit_pct=Decimal("0.001"))
        check = next(r for r in results if r.check_name == "dca_take_profit")
        assert not check.passed

    def test_full_validation_report(self):
        validator = ConfigValidator()
        report = validator.run_full_validation()
        assert isinstance(report, ConfigValidationReport)
        assert len(report.results) > 0

    def test_full_validation_summary(self):
        validator = ConfigValidator()
        report = validator.run_full_validation()
        summary = report.summary()
        assert "total_checks" in summary
        assert "categories" in summary
        assert "overall_status" in summary

    def test_full_validation_defaults_pass(self):
        validator = ConfigValidator()
        report = validator.run_full_validation()
        assert report.passed

    def test_full_validation_with_bad_config(self):
        validator = ConfigValidator()
        report = validator.run_full_validation(
            risk={"risk_per_trade": Decimal("0.20")},
            grid={"num_levels": 100},
        )
        assert not report.passed
        assert len(report.failures) >= 2
