"""Test case for valid EmpMonitor login.
"""

from playwright.sync_api import Page, expect
from codegen.helpers.auth_helper import login


def test_valid_login(page: Page, base_url: str, credentials: dict):
    """Verify that a user with valid credentials can log into EmpMonitor successfully."""
    login(page, base_url, credentials["username"], credentials["password"])
    
    # Assert navigation away from login screen and visibility of main elements
    expect(page).not_to_have_url(f"{base_url}/login")
    expect(page.get_by_role("link", name="Total Enrollments")).to_be_visible()
