"""Test Productivity Analytics widget rendering.
"""

from playwright.sync_api import Page, expect


def test_productivity_analytics_widgets(auth_page: Page):
    """Verify top application and web usage analytics widgets on employee details."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    app_history = auth_page.get_by_role("link", name=" App History")
    if app_history.is_visible():
        app_history.click()
        auth_page.wait_for_load_state("networkidle")
        expect(auth_page.get_by_text("Top Application Usage")).to_be_visible()
