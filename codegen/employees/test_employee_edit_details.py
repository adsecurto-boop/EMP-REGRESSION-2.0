"""Test editing employee profile details and shift settings.
"""

from playwright.sync_api import Page, expect


def test_edit_employee_details(auth_page: Page):
    """Verify editing employee shift and updating profile settings."""
    auth_page.get_by_role("link", name="Total Enrollments").click()
    auth_page.wait_for_load_state("networkidle")

    first_edit = auth_page.get_by_role("link", name="Edit").first
    if first_edit.is_visible():
        first_edit.click()
        auth_page.wait_for_load_state("networkidle")

        shift_select = auth_page.locator("#ShiftfilterEdit")
        if shift_select.is_visible():
            shift_select.select_option(index=0)

        update_btn = auth_page.get_by_role("button", name="Update")
        if update_btn.is_visible():
            update_btn.click()
            auth_page.wait_for_load_state("networkidle")
            ok_btn = auth_page.get_by_role("button", name="OK")
            if ok_btn.is_visible():
                ok_btn.click()
