"""Negative test case for invalid EmpMonitor login credentials.
"""

from playwright.sync_api import Page, expect


def test_invalid_login(page: Page, base_url: str):
    """Verify that logging in with invalid credentials fails gracefully with feedback or retains user on login page."""
    page.goto(base_url)
    page.get_by_role("textbox", name="Username/Email").fill("invalid_user_999")
    page.get_by_role("textbox", name="Password").fill("wrong_password")
    page.get_by_role("button", name="Login").click()
    page.wait_for_load_state("networkidle")

    # Assert remaining on login page or error message displayed
    username_box = page.get_by_role("textbox", name="Username/Email")
    expect(username_box).to_be_visible()
