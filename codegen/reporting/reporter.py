"""Test reporter manager that orchestrates pytest hooks, screenshot capture, and report generation.
"""

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from codegen.reporting.models import TestCaseMetadata, TestResult, ExecutionSummary, mask_secrets
from codegen.reporting.catalog_loader import CatalogLoader
from codegen.reporting.json_report import JSONReportGenerator
from codegen.reporting.html_report import HTMLReportGenerator
from codegen.reporting.docx_report import DOCXReportGenerator


class TestReporter:
    """Central test reporter coordinating metrics collection and report generation."""

    def __init__(self, root_results_dir: Optional[Path] = None):
        self.timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if root_results_dir is None:
            root_results_dir = Path("test-results")
        self.results_dir = root_results_dir / self.timestamp_str
        self.screenshots_dir = self.results_dir / "screenshots"
        self.traces_dir = self.results_dir / "traces"

        self.catalog_loader = CatalogLoader()
        self.results: List[TestResult] = []
        self.item_start_times: Dict[str, float] = {}
        self._recorded_nodes: set = set()

        self.base_url = os.getenv("EMPMONITOR_BASE_URL", "https://app.dev.empmonitor.com/amember/member")
        self.browser_name = "Chromium"
        self.environment = "DEV"

    def setup_directories(self) -> None:
        """Create timestamped report directory structure."""
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir.mkdir(parents=True, exist_ok=True)

    def record_start(self, item_id: str) -> None:
        """Record start time for a test item."""
        self.item_start_times[item_id] = time.time()

    def capture_failure_screenshot(self, page_obj: Any, test_id_clean: str) -> Optional[str]:
        """Capture screenshot from Playwright Page fixture if available."""
        if not page_obj:
            return None
        try:
            screenshot_file = self.screenshots_dir / f"{test_id_clean}_fail.png"
            page_obj.screenshot(path=str(screenshot_file), full_page=True)
            return str(screenshot_file)
        except Exception as e:
            # Fallback if screenshot capture fails
            return None

    def record_result(
        self,
        item: Any,
        call_report: Any,
        page_obj: Optional[Any] = None,
        exception: Optional[Exception] = None
    ) -> None:
        """Process pytest test report and record test result."""
        node_id = item.nodeid
        if node_id in self._recorded_nodes:
            return
        self._recorded_nodes.add(node_id)

        start_t = self.item_start_times.get(node_id, time.time())
        end_t = time.time()
        duration = round(call_report.duration if hasattr(call_report, "duration") else (end_t - start_t), 2)

        rel_file = str(Path(item.fspath).relative_to(Path.cwd())) if hasattr(item, "fspath") else str(node_id)

        # Check for @pytest.mark.testcase decorator
        tc_marker = item.get_closest_marker("testcase")
        if tc_marker and tc_marker.kwargs:
            kw = tc_marker.kwargs
            meta = TestCaseMetadata(
                id=kw.get("id", "TC-000"),
                module=kw.get("module", "General"),
                title=kw.get("title", item.name),
                description=kw.get("description", item.name),
                test_data=mask_secrets(kw.get("test_data", {})),
                preconditions=kw.get("preconditions", "Authenticated context"),
                expected=kw.get("expected", "Test passes successfully")
            )
        else:
            meta = self.catalog_loader.get_metadata(rel_file, default_title=item.name)

        # Determine status
        if call_report.passed:
            status = "PASS"
            actual = "Executed successfully without assertion or runtime errors"
            failure_reason = ""
            exc_msg = ""
            screenshot_path = None
        elif call_report.skipped:
            status = "SKIP"
            actual = "Test skipped during execution"
            failure_reason = str(call_report.longrepr) if hasattr(call_report, "longrepr") else "Skipped"
            exc_msg = failure_reason
            screenshot_path = None
        else:
            status = "FAIL"
            actual = f"Failed during {call_report.when} step"
            failure_reason = str(call_report.longreprname) if hasattr(call_report, "longreprname") else "Test Failed"
            
            # Format exception message cleanly
            if hasattr(call_report, "longrepr") and call_report.longrepr:
                exc_msg = str(call_report.longrepr)
            elif exception:
                exc_msg = str(exception)
            else:
                exc_msg = "Unknown assertion or execution error"

            # Capture failure screenshot
            tc_clean = meta.id.replace("-", "_").lower()
            screenshot_path = self.capture_failure_screenshot(page_obj, f"{tc_clean}_{int(time.time())}")

        # Page URL if accessible
        current_url = ""
        if page_obj and hasattr(page_obj, "url"):
            try:
                current_url = page_obj.url
            except Exception:
                pass

        test_result = TestResult(
            test_id=meta.id,
            module=meta.module,
            title=meta.title,
            test_file=rel_file,
            test_data=mask_secrets(meta.test_data),
            preconditions=meta.preconditions,
            expected=meta.expected,
            actual=actual,
            status=status,
            start_time=datetime.fromtimestamp(start_t).strftime("%Y-%m-%d %H:%M:%S"),
            end_time=datetime.fromtimestamp(end_t).strftime("%Y-%m-%d %H:%M:%S"),
            duration_seconds=duration,
            browser=self.browser_name,
            environment=self.environment,
            url=current_url,
            failure_reason=failure_reason,
            exception_message=mask_secrets(exc_msg),
            screenshot_path=screenshot_path
        )

        self.results.append(test_result)

    def generate_reports(self) -> ExecutionSummary:
        """Generate HTML, DOCX, and JSON reports and return ExecutionSummary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        skipped = sum(1 for r in self.results if r.status == "SKIP")

        pass_pct = (passed / total * 100.0) if total > 0 else 0.0

        if failed > 0:
            overall_status = "FAILED"
        elif skipped > 0:
            overall_status = "PASSED WITH SKIPS"
        else:
            overall_status = "PASSED"

        summary = ExecutionSummary(
            timestamp=self.timestamp_str,
            environment=self.environment,
            browser=self.browser_name,
            base_url=self.base_url,
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            pass_percentage=pass_pct,
            overall_status=overall_status,
            results_dir=str(self.results_dir),
            tests=self.results
        )

        # Generate output files
        json_file = self.results_dir / "test_results.json"
        html_file = self.results_dir / "test_report.html"
        docx_file = self.results_dir / "test_report.docx"

        JSONReportGenerator.generate(summary, json_file)
        HTMLReportGenerator.generate(summary, html_file)
        DOCXReportGenerator.generate(summary, docx_file)

        return summary

    def print_terminal_summary(self, summary: ExecutionSummary) -> None:
        """Print concise summary block to terminal stdout."""
        border = "=" * 60
        print("\n" + border)
        print("EMPMonitor Regression Test Summary")
        print(border)
        print(f"Total    : {summary.total}")
        print(f"Passed   : {summary.passed}")
        print(f"Failed   : {summary.failed}")
        print(f"Skipped  : {summary.skipped}")
        print(f"Pass %   : {summary.pass_percentage:.2f}%")
        print(f"Result   : {summary.overall_status}")
        print()
        print(f"HTML     : {self.results_dir / 'test_report.html'}")
        print(f"DOCX     : {self.results_dir / 'test_report.docx'}")
        print(f"JSON     : {self.results_dir / 'test_results.json'}")
        print(border + "\n")
