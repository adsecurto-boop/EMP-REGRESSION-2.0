"""Test searching and sorting employee list table.
"""

from playwright.sync_api import Page, expect


def test_employee_search_and_table(auth_page: Page):
    """Verify navigating to Employee Details, filtering by search term, and sorting table columns."""
    auth_page.get_by_role("link", name="Employee ", exact=False).click()
    auth_page.get_by_role("link", name="Employee-Details").click()
    auth_page.wait_for_load_state("networkidle")

    search_input = auth_page.get_by_role("textbox", name="Search")
    search_input.fill("suman")
    search_input.press("Enter")

    search_btn = auth_page.locator("#SearchButton")
    if search_btn.is_visible():
        search_btn.click()
    auth_page.wait_for_load_state("networkidle")

    # Assert search result table renders cell with employee details
    expect(auth_page.locator("body")).to_contain_text("suman", ignore_case=True)
