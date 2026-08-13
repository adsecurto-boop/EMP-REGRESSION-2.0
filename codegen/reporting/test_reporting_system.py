"""Unit tests for the reporting module.
"""

import json
from pathlib import Path
import pytest
import docx

from codegen.reporting.models import TestCaseMetadata, TestResult, ExecutionSummary, mask_secrets
from codegen.reporting.catalog_loader import CatalogLoader
from codegen.reporting.json_report import JSONReportGenerator
from codegen.reporting.html_report import HTMLReportGenerator
from codegen.reporting.docx_report import DOCXReportGenerator


def test_mask_secrets():
    """Verify passwords and credentials are replaced with asterisks."""
    raw_data = {"username": "qt_dev", "password": "qt_developers", "token": "secret_123"}
    masked = mask_secrets(raw_data)
    assert masked["username"] == "qt_dev"
    assert masked["password"] == "********"
    assert masked["token"] == "********"

    text = "Logged in with password qt_developers successfully."
    masked_text = mask_secrets(text)
    assert "qt_developers" not in masked_text
    assert "********" in masked_text


def test_catalog_loader():
    """Verify CatalogLoader loads metadata from CODEGEN_TEST_CATALOG.md."""
    loader = CatalogLoader()
    meta = loader.get_metadata("auth/test_login.py")
    assert meta.id == "TC-AUTH-001"
    assert meta.module == "Authentication"
    assert meta.title == "Valid login & navigation"


@pytest.mark.testcase(
    id="TC-UNIT-999",
    module="Testing",
    title="Custom decorator test",
    test_data={"key": "val"},
    expected="Passes unit test",
    preconditions="None"
)
def test_custom_decorator_marker():
    """Dummy test to exercise custom testcase marker."""
    assert True


def test_report_generators(tmp_path):
    """Verify HTML, DOCX, and JSON report generation."""
    test1 = TestResult(
        test_id="TC-AUTH-001",
        module="Authentication",
        title="Valid login",
        test_file="auth/test_login.py",
        test_data={"user": "qt_dev", "password": "qt_developers"},
        preconditions="Valid credentials",
        expected="Dashboard loads",
        actual="Dashboard loaded successfully",
        status="PASS",
        start_time="2026-08-13 12:00:00",
        end_time="2026-08-13 12:00:02",
        duration_seconds=2.15,
        browser="Chromium",
        environment="DEV"
    )

    test2 = TestResult(
        test_id="TC-EMP-001",
        module="Employee Mgmt",
        title="Search employee",
        test_file="employees/test_employee_list_search.py",
        test_data={"search": "suman"},
        preconditions="Authenticated",
        expected="Matching employee displayed",
        actual="Failed to locate element",
        status="FAIL",
        start_time="2026-08-13 12:00:03",
        end_time="2026-08-13 12:00:05",
        duration_seconds=1.85,
        browser="Chromium",
        environment="DEV",
        failure_reason="TimeoutError: Locator not found",
        exception_message="Playwright TimeoutError: Waiting for selector '#search-box'"
    )

    summary = ExecutionSummary(
        timestamp="2026-08-13_12-00-00",
        environment="DEV",
        browser="Chromium",
        base_url="https://app.dev.empmonitor.com/amember/member",
        total=2,
        passed=1,
        failed=1,
        skipped=0,
        pass_percentage=50.0,
        overall_status="FAILED",
        results_dir=str(tmp_path),
        tests=[test1, test2]
    )

    # 1. JSON
    json_path = tmp_path / "test_results.json"
    JSONReportGenerator.generate(summary, json_path)
    assert json_path.exists()
    with open(json_path, "r") as f:
        data = json.load(f)
    assert data["summary"]["total"] == 2
    assert data["summary"]["failed"] == 1
    assert data["summary"]["overall_status"] == "FAILED"
    assert "qt_developers" not in json.dumps(data)

    # 2. HTML
    html_path = tmp_path / "test_report.html"
    HTMLReportGenerator.generate(summary, html_path)
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "EMPMonitor Regression Test Report" in html_content
    assert "TC-AUTH-001" in html_content
    assert "TC-EMP-001" in html_content

    # 3. DOCX
    docx_path = tmp_path / "test_report.docx"
    DOCXReportGenerator.generate(summary, docx_path)
    assert docx_path.exists()
    doc = docx.Document(str(docx_path))
    full_text = " ".join([p.text for p in doc.paragraphs])
    assert "EMPMonitor Regression Test Report" in full_text
