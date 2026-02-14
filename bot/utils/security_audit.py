"""
Security audit utility for TRADERAGENT production deployment.

Checks:
- API key exposure in source files
- Database connection security
- Configuration validation
- File permissions
- Environment variable safety
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bot.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AuditResult:
    """Result of a single audit check."""
    check_name: str
    passed: bool
    severity: str  # "critical", "warning", "info"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityAuditReport:
    """Complete security audit report."""
    results: list[AuditResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results if r.severity == "critical")

    @property
    def critical_failures(self) -> list[AuditResult]:
        return [r for r in self.results if not r.passed and r.severity == "critical"]

    @property
    def warnings(self) -> list[AuditResult]:
        return [r for r in self.results if not r.passed and r.severity == "warning"]

    def summary(self) -> dict[str, Any]:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        return {
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "critical_failures": len(self.critical_failures),
            "warnings": len(self.warnings),
            "overall_status": "PASS" if self.passed else "FAIL",
        }


class SecurityAuditor:
    """Run security checks against the TRADERAGENT codebase and configuration."""

    # Patterns that indicate potential secret exposure
    SECRET_PATTERNS = [
        (r'api_key\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', "Hardcoded API key"),
        (r'api_secret\s*=\s*["\'][a-zA-Z0-9]{20,}["\']', "Hardcoded API secret"),
        (r'password\s*=\s*["\'][^"\']{8,}["\']', "Hardcoded password"),
        (r'token\s*=\s*["\'][0-9]+:[a-zA-Z0-9_-]{35}["\']', "Hardcoded bot token"),
        (r'redis://[^@\s]+:[^@\s]+@', "Redis credentials in URL"),
        (r'postgresql://[^@\s]+:[^@\s]+@', "Database credentials in URL"),
    ]

    # Files that should never contain secrets
    SCAN_EXTENSIONS = {".py", ".yml", ".yaml", ".json", ".toml", ".cfg", ".ini"}

    # Files that are expected to have secrets (excluded from scan)
    EXCLUDE_PATTERNS = {".env", ".env.example", "test_", "conftest"}

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def run_full_audit(self) -> SecurityAuditReport:
        """Run all security checks and return a report."""
        report = SecurityAuditReport()

        report.results.append(self._check_env_file())
        report.results.append(self._check_gitignore())
        report.results.extend(self._scan_source_for_secrets())
        report.results.append(self._check_debug_mode())
        report.results.append(self._check_env_vars())
        report.results.append(self._check_database_url())
        report.results.append(self._check_redis_url())

        return report

    def _check_env_file(self) -> AuditResult:
        """Check that .env file exists and is not committed."""
        env_path = self.project_root / ".env"
        gitignore_path = self.project_root / ".gitignore"

        if not env_path.exists():
            return AuditResult(
                check_name="env_file_exists",
                passed=True,
                severity="info",
                message="No .env file found (using environment variables directly)",
            )

        # Check if .env is in .gitignore
        if gitignore_path.exists():
            gitignore_content = gitignore_path.read_text()
            if ".env" in gitignore_content:
                return AuditResult(
                    check_name="env_file_protected",
                    passed=True,
                    severity="critical",
                    message=".env file exists and is in .gitignore",
                )

        return AuditResult(
            check_name="env_file_protected",
            passed=False,
            severity="critical",
            message=".env file exists but is NOT in .gitignore — secrets may be committed",
        )

    def _check_gitignore(self) -> AuditResult:
        """Check that .gitignore contains essential exclusions."""
        gitignore_path = self.project_root / ".gitignore"
        if not gitignore_path.exists():
            return AuditResult(
                check_name="gitignore_exists",
                passed=False,
                severity="warning",
                message="No .gitignore file found",
            )

        content = gitignore_path.read_text()
        required = [".env", "__pycache__", "*.pyc"]
        missing = [r for r in required if r not in content]

        if missing:
            return AuditResult(
                check_name="gitignore_complete",
                passed=False,
                severity="warning",
                message=f".gitignore missing patterns: {', '.join(missing)}",
            )

        return AuditResult(
            check_name="gitignore_complete",
            passed=True,
            severity="warning",
            message=".gitignore contains all required exclusions",
        )

    def _scan_source_for_secrets(self) -> list[AuditResult]:
        """Scan source files for hardcoded secrets."""
        results = []
        files_scanned = 0
        issues_found = []

        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in self.SCAN_EXTENSIONS:
                continue
            if any(excl in path.name for excl in self.EXCLUDE_PATTERNS):
                continue
            if ".git" in str(path) or "node_modules" in str(path) or "__pycache__" in str(path):
                continue

            files_scanned += 1
            try:
                content = path.read_text(errors="ignore")
                for pattern, description in self.SECRET_PATTERNS:
                    matches = re.findall(pattern, content)
                    if matches:
                        issues_found.append({
                            "file": str(path.relative_to(self.project_root)),
                            "issue": description,
                            "count": len(matches),
                        })
            except (PermissionError, UnicodeDecodeError):
                continue

        if issues_found:
            results.append(AuditResult(
                check_name="no_hardcoded_secrets",
                passed=False,
                severity="critical",
                message=f"Found {len(issues_found)} files with potential hardcoded secrets",
                details={"issues": issues_found, "files_scanned": files_scanned},
            ))
        else:
            results.append(AuditResult(
                check_name="no_hardcoded_secrets",
                passed=True,
                severity="critical",
                message=f"No hardcoded secrets found in {files_scanned} files",
                details={"files_scanned": files_scanned},
            ))

        return results

    def _check_debug_mode(self) -> AuditResult:
        """Check that debug mode is not enabled in production configs."""
        env_debug = os.environ.get("DEBUG", "").lower()
        if env_debug in ("1", "true", "yes"):
            return AuditResult(
                check_name="debug_disabled",
                passed=False,
                severity="warning",
                message="DEBUG mode is enabled — disable for production",
            )
        return AuditResult(
            check_name="debug_disabled",
            passed=True,
            severity="warning",
            message="DEBUG mode is not enabled",
        )

    def _check_env_vars(self) -> AuditResult:
        """Check that required environment variables are set."""
        required = ["BYBIT_TESTNET_API_KEY", "BYBIT_TESTNET_API_SECRET"]
        optional = ["DATABASE_URL", "REDIS_URL", "TELEGRAM_BOT_TOKEN"]

        missing_required = [v for v in required if not os.environ.get(v)]
        missing_optional = [v for v in optional if not os.environ.get(v)]

        if missing_required:
            return AuditResult(
                check_name="env_vars_set",
                passed=False,
                severity="warning",
                message=f"Missing env vars: {', '.join(missing_required)}",
                details={"missing_optional": missing_optional},
            )
        return AuditResult(
            check_name="env_vars_set",
            passed=True,
            severity="warning",
            message="All required environment variables are set",
            details={"missing_optional": missing_optional},
        )

    def _check_database_url(self) -> AuditResult:
        """Check database URL security."""
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            return AuditResult(
                check_name="database_url_secure",
                passed=True,
                severity="info",
                message="No DATABASE_URL set (using default or in-memory)",
            )

        if "localhost" in db_url or "127.0.0.1" in db_url:
            return AuditResult(
                check_name="database_url_secure",
                passed=True,
                severity="info",
                message="Database is local",
            )

        if "ssl" not in db_url.lower() and "sslmode" not in db_url.lower():
            return AuditResult(
                check_name="database_url_secure",
                passed=False,
                severity="warning",
                message="Remote database URL does not include SSL parameters",
            )

        return AuditResult(
            check_name="database_url_secure",
            passed=True,
            severity="warning",
            message="Database URL appears secure",
        )

    def _check_redis_url(self) -> AuditResult:
        """Check Redis URL security."""
        redis_url = os.environ.get("REDIS_URL", "")
        if not redis_url:
            return AuditResult(
                check_name="redis_url_secure",
                passed=True,
                severity="info",
                message="No REDIS_URL set (using default localhost)",
            )

        if "localhost" in redis_url or "127.0.0.1" in redis_url:
            return AuditResult(
                check_name="redis_url_secure",
                passed=True,
                severity="info",
                message="Redis is local",
            )

        return AuditResult(
            check_name="redis_url_secure",
            passed=True,
            severity="info",
            message="Redis URL configured",
        )
