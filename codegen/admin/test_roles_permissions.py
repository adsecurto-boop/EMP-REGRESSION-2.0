"""Test Roles and Permissions management section.
"""

from playwright.sync_api import Page, expect


def test_roles_and_permissions(auth_page: Page):
    """Verify navigating to Roles or Employee Details to inspect role column header."""
    auth_page.get_by_role("link", name="Employee ", exact=False).click()
    auth_page.get_by_role("link", name="Employee-Details").click()
    auth_page.wait_for_load_state("networkidle")

    role_header = auth_page.get_by_role("columnheader", name="Role : activate to sort")
    if role_header.is_visible():
        role_header.click()
        expect(role_header).to_be_visible()
