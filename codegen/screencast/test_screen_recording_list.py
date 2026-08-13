"""Test Screen Recording list and search functionality.
"""

from playwright.sync_api import Page, expect


def test_screen_recording_search(auth_page: Page):
    """Verify navigating to Screen Recording tab and performing search query."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    recording_link = auth_page.get_by_role("link", name=" Screen Recording")
    if recording_link.is_visible():
        recording_link.click()
        auth_page.wait_for_load_state("networkidle")

        search_btn = auth_page.get_by_role("button", name=" Search")
        if search_btn.is_visible():
            search_btn.click()
            auth_page.wait_for_load_state("networkidle")
            expect(auth_page.get_by_text("No screen records present for")).to_be_visible()
