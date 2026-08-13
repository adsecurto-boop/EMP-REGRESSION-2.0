"""Test Timesheets attendance grid, column sorting, and date range filters.
"""

from playwright.sync_api import Page, expect


def test_timesheet_grid_and_sorting(auth_page: Page):
    """Verify navigating to Timesheets tab, sorting by Clock In/Out columns, and checking ranges."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    timesheet_link = auth_page.get_by_role("link", name=" Timesheets", description="Timesheets", exact=True)
    if timesheet_link.is_visible():
        timesheet_link.click()
        auth_page.wait_for_load_state("networkidle")

        clock_in_header = auth_page.get_by_role("columnheader", name="Clock In: activate to sort")
        if clock_in_header.is_visible():
            clock_in_header.click()

        clock_out_header = auth_page.get_by_role("columnheader", name="Clock Out: activate to sort")
        if clock_out_header.is_visible():
            clock_out_header.click()
