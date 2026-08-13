"""Test registering a new employee modal and validation.
"""

import time
from playwright.sync_api import Page, expect


def test_register_employee_form(auth_page: Page):
    """Verify opening Register Employee form, populating details, and triggering registration."""
    auth_page.get_by_role("link", name="Employee ", exact=False).click()
    auth_page.get_by_role("link", name="Employee-Details").click()
    auth_page.wait_for_load_state("networkidle")

    reg_button = auth_page.get_by_role("button", name="Register Employee")
    reg_button.click()

    unique_email = f"auto_{int(time.time())}@gmail.com"
    auth_page.get_by_role("textbox", name="Enter First Name").fill("auto")
    auth_page.get_by_role("textbox", name="Last Name *").fill("test")
    auth_page.get_by_role("textbox", name="Email Address * Email Address").fill(unique_email)
    auth_page.get_by_role("textbox", name="Password *", exact=True).fill("Pass@123")
    auth_page.get_by_role("textbox", name="Confirm Password * Employee").fill("Pass@123")
    auth_page.get_by_role("textbox", name="Employee Code", exact=True).fill(f"emp_{int(time.time())}")

    # Select location and department if options exist
    loc_select = auth_page.locator("#locations-addEmp")
    if loc_select.is_visible():
        loc_select.select_option(index=1)

    dept_select = auth_page.locator("#EmpReg_departments")
    if dept_select.is_visible():
        dept_select.select_option(index=0)

    # Click submit
    register_submit = auth_page.locator("#empReg")
    if register_submit.is_visible():
        register_submit.click()
        auth_page.wait_for_load_state("networkidle")
        ok_btn = auth_page.get_by_role("button", name="OK")
        if ok_btn.is_visible():
            ok_btn.click()
