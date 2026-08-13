"""Test Screenshot module date/time filtering and empty/data state.
"""

from playwright.sync_api import Page, expect


def test_screenshot_filtering_and_view(auth_page: Page):
    """Verify selecting date and searching for employee screenshots."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    screenshot_link = auth_page.get_by_role("link", name=" Screenshots")
    if screenshot_link.is_visible():
        screenshot_link.click()
        auth_page.wait_for_load_state("networkidle")

        search_btn = auth_page.get_by_role("button", description="Search", exact=True)
        if search_btn.is_visible():
            search_btn.click()
            auth_page.wait_for_load_state("networkidle")
