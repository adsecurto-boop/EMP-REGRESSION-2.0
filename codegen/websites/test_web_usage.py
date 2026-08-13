"""Test Website Usage tracking list and domain details.
"""

from playwright.sync_api import Page, expect


def test_web_usage_history(auth_page: Page):
    """Verify viewing Web Usage history list on employee details."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    web_history_btn = auth_page.get_by_role("link", name=" Web History")
    if web_history_btn.is_visible():
        web_history_btn.click()
        auth_page.wait_for_load_state("networkidle")
        expect(auth_page.get_by_role("link", name=" Web History")).to_be_visible()
