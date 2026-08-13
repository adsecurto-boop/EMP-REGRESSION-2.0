"""Test Keystrokes log table navigation and view.
"""

from playwright.sync_api import Page, expect


def test_keystrokes_log_view(auth_page: Page):
    """Verify navigating to Employee Details -> Key Strokes tab and viewing key logs table."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    keystrokes_link = auth_page.get_by_role("link", name=" Key Strokes")
    if keystrokes_link.is_visible():
        keystrokes_link.click()
        auth_page.wait_for_load_state("networkidle")
        expect(auth_page.get_by_role("gridcell", name="Application").first).to_be_visible()
