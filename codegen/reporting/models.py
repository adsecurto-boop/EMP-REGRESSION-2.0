"""Data models for test execution reporting.
"""

import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


SECRET_KEYWORDS = ["password", "passwd", "pwd", "secret", "token", "api_key", "credential"]
DEFAULT_KNOWN_SECRETS = ["qt_developers", "Pass@123", "wrong_password"]


def mask_secrets(value: Any) -> Any:
    """Recursively mask secrets in data structures and strings."""
    if value is None:
        return ""
    
    # Check env variables for dynamic passwords
    known_secrets = list(DEFAULT_KNOWN_SECRETS)
    env_pass = os.getenv("EMPMONITOR_PASSWORD")
    if env_pass and env_pass not in known_secrets:
        known_secrets.append(env_pass)

    if isinstance(value, str):
        masked = value
        for sec in known_secrets:
            if sec and len(sec) > 1:
                masked = masked.replace(sec, "********")
        return masked

    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if any(kw in str(k).lower() for kw in SECRET_KEYWORDS):
                result[k] = "********"
            else:
                result[k] = mask_secrets(v)
        return result

    if isinstance(value, list):
        return [mask_secrets(item) for item in value]

    return value


@dataclass
class TestCaseMetadata:
    """Metadata describing a test case, loaded from marker or catalog."""
    __test__ = False
    id: str
    module: str
    title: str
    description: str = ""
    test_data: Any = field(default_factory=dict)
    preconditions: str = ""
    expected: str = ""


@dataclass
class TestResult:
    """Collected test execution result."""
    __test__ = False
    test_id: str
    module: str
    title: str
    test_file: str
    test_data: Any
    preconditions: str
    expected: str
    actual: str
    status: str  # PASS, FAIL, SKIP
    start_time: str
    end_time: str
    duration_seconds: float
    browser: str = "Chromium"
    environment: str = "DEV"
    url: str = ""
    failure_reason: str = ""
    exception_message: str = ""
    screenshot_path: Optional[str] = None
    trace_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert test result to dictionary with masked secrets."""
        d = asdict(self)
        d["test_data"] = mask_secrets(self.test_data)
        d["exception_message"] = mask_secrets(self.exception_message)
        d["actual"] = mask_secrets(self.actual)
        d["expected"] = mask_secrets(self.expected)
        return d


@dataclass
class ExecutionSummary:
    """Overall test session execution summary."""
    timestamp: str
    environment: str
    browser: str
    base_url: str
    total: int
    passed: int
    failed: int
    skipped: int
    pass_percentage: float
    overall_status: str  # PASSED, PASSED WITH SKIPS, FAILED
    results_dir: str
    tests: List[TestResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to dictionary representation."""
        return {
            "execution": {
                "timestamp": self.timestamp,
                "environment": self.environment,
                "browser": self.browser,
                "base_url": mask_secrets(self.base_url),
                "results_dir": self.results_dir
            },
            "summary": {
                "total": self.total,
                "passed": self.passed,
                "failed": self.failed,
                "skipped": self.skipped,
                "pass_percentage": self.pass_percentage,
                "overall_status": self.overall_status
            },
            "tests": [t.to_dict() for t in self.tests]
        }
