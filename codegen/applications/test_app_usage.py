"""Test Application Usage tracking list and details.
"""

from playwright.sync_api import Page, expect


def test_app_usage_history(auth_page: Page):
    """Verify viewing Application Usage history on employee profile."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    app_history_btn = auth_page.get_by_role("link", name=" App History")
    if app_history_btn.is_visible():
        app_history_btn.click()
        auth_page.wait_for_load_state("networkidle")
        expect(auth_page.get_by_text("Top Application Usage")).to_be_visible()
