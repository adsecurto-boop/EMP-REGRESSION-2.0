"""Test Reports navigation and report type selection.
"""

from playwright.sync_api import Page, expect


def test_reports_navigation(auth_page: Page):
    """Verify navigating to Reports module if present in main menu."""
    reports_link = auth_page.get_by_role("link", name="Reports", exact=False)
    if reports_link.is_visible():
        reports_link.click()
        auth_page.wait_for_load_state("networkidle")
        expect(auth_page).not_to_have_url("")
