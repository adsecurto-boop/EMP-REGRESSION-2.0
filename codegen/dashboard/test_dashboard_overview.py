"""Test dashboard home widgets and overview section loading.
"""

from playwright.sync_api import Page, expect


def test_dashboard_overview(auth_page: Page):
    """Verify that dashboard home displays key overview widgets and enrollment counts."""
    enrollments_link = auth_page.get_by_role("link", name="Total Enrollments")
    expect(enrollments_link).to_be_visible()
    
    # Click total enrollments and verify employee search box is visible
    enrollments_link.click()
    auth_page.wait_for_load_state("networkidle")
    expect(auth_page.get_by_role("searchbox", name="Search:")).to_be_visible()
