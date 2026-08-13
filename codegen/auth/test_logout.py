"""Test case for logout and session invalidation.
"""

from playwright.sync_api import Page, expect
from codegen.helpers.auth_helper import logout


def test_logout(auth_page: Page, base_url: str):
    """Verify logging out closes session and redirects to login/member screen."""
    logout(auth_page)
    # Verify page redirects to login or username input is visible
    expect(auth_page.get_by_role("textbox", name="Username/Email")).to_be_visible()
