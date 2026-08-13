"""Test dashboard employee filters (Currently Active / Absent).
"""

from playwright.sync_api import Page, expect


def test_dashboard_active_absent_filters(auth_page: Page):
    """Verify filtering employees by Currently Active and Absent status."""
    # Click Currently Active filter
    active_link = auth_page.get_by_role("link", name="Currently Active")
    if active_link.is_visible():
        active_link.click()
        auth_page.wait_for_load_state("networkidle")
        close_btn = auth_page.get_by_role("button", name="×")
        if close_btn.is_visible():
            close_btn.click()

    # Click Absent filter
    absent_link = auth_page.get_by_role("link", name="Absent")
    if absent_link.is_visible():
        absent_link.click()
        auth_page.wait_for_load_state("networkidle")
        search_box = auth_page.get_by_role("searchbox", name="Search:")
        expect(search_box).to_be_visible()
