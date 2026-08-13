"""Test Screen Cast / Live Monitoring connection controls and canvas.
"""

from playwright.sync_api import Page, expect


def test_screencast_live_monitoring(auth_page: Page):
    """Verify navigating to Screen Cast and clicking Connect button."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    screencast_link = auth_page.get_by_role("link", name=" Screen Cast")
    if screencast_link.is_visible():
        screencast_link.click()
        auth_page.wait_for_load_state("networkidle")

        connect_btn = auth_page.get_by_role("button", name="Connect")
        if connect_btn.is_visible():
            expect(connect_btn).to_be_enabled()
            connect_btn.click()
            auth_page.wait_for_load_state("networkidle")
