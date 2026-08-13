"""Pytest configuration and Playwright fixtures for EmpMonitor Codegen tests.
"""

import os
import pytest
from playwright.sync_api import Playwright, BrowserContext, Page
from codegen.reporting.reporter import TestReporter

DEFAULT_BASE_URL = os.getenv("EMPMONITOR_BASE_URL", "https://app.dev.empmonitor.com/amember/member")
DEFAULT_USERNAME = os.getenv("EMPMONITOR_USERNAME", "qt_dev")
DEFAULT_PASSWORD = os.getenv("EMPMONITOR_PASSWORD", "qt_developers")


def pytest_configure(config):
    """Configure custom pytest markers and initialize global reporter."""
    config.addinivalue_line(
        "markers",
        "testcase(id, module, title, test_data, expected, preconditions, description): Metadata marker for automated QA reports"
    )
    reporter = TestReporter()
    reporter.setup_directories()
    config._reporter = reporter


def pytest_runtest_setup(item):
    """Track item start execution time."""
    reporter = getattr(item.config, "_reporter", None)
    if reporter:
        reporter.record_start(item.nodeid)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Collect test outcomes, capture failure screenshots, and pass to reporter."""
    outcome = yield
    report = outcome.get_result()
    
    if report.when == "call" or (report.when == "setup" and (report.failed or report.skipped)):
        reporter = getattr(item.config, "_reporter", None)
        if reporter:
            page_obj = item.funcargs.get("auth_page") or item.funcargs.get("page")
            reporter.record_result(item, report, page_obj=page_obj)


def pytest_sessionfinish(session, exitstatus):
    """Generate final HTML, DOCX, and JSON reports and print terminal summary."""
    reporter = getattr(session.config, "_reporter", None)
    if reporter:
        summary = reporter.generate_reports()
        reporter.print_terminal_summary(summary)


@pytest.fixture(scope="session")
def base_url() -> str:
    """Return the base EmpMonitor URL."""
    return DEFAULT_BASE_URL


@pytest.fixture(scope="session")
def credentials() -> dict:
    """Return test account credentials."""
    return {
        "username": DEFAULT_USERNAME,
        "password": DEFAULT_PASSWORD,
    }


@pytest.fixture(scope="function")
def authenticated_context(playwright: Playwright, base_url: str, credentials: dict) -> BrowserContext:
    """Provide a Playwright BrowserContext authenticated into EmpMonitor."""
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 800})
    page = context.new_page()
    page.goto(base_url)
    page.get_by_role("textbox", name="Username/Email").fill(credentials["username"])
    page.get_by_role("textbox", name="Password").fill(credentials["password"])
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("networkidle")
    yield context
    context.close()
    browser.close()


@pytest.fixture(scope="function")
def auth_page(authenticated_context: BrowserContext) -> Page:
    """Provide an authenticated Playwright Page."""
    pages = authenticated_context.pages
    return pages[0] if pages else authenticated_context.new_page()

