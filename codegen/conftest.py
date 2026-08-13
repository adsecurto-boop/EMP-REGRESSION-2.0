"""Pytest configuration and Playwright fixtures for EmpMonitor Codegen tests.
"""

import os
import pytest
from playwright.sync_api import Playwright, BrowserContext, Page

DEFAULT_BASE_URL = os.getenv("EMPMONITOR_BASE_URL", "https://app.dev.empmonitor.com/amember/member")
DEFAULT_USERNAME = os.getenv("EMPMONITOR_USERNAME", "qt_dev")
DEFAULT_PASSWORD = os.getenv("EMPMONITOR_PASSWORD", "qt_developers")


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
