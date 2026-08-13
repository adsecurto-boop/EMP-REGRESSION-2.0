"""Test session state retention across page reloads.
"""

from playwright.sync_api import Page, expect


def test_session_persistence(auth_page: Page):
    """Verify that an authenticated page reloads without requiring re-authentication."""
    auth_page.reload()
    auth_page.wait_for_load_state("networkidle")
    expect(auth_page.get_by_role("link", name="Total Enrollments")).to_be_visible()
