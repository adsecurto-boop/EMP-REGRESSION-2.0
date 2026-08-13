"""Authentication helper methods for Playwright scripts.
"""

from playwright.sync_api import Page, expect


def login(page: Page, base_url: str, username: str, password: str) -> None:
    """Perform deterministic login to EmpMonitor."""
    page.goto(base_url)
    username_field = page.get_by_role("textbox", name="Username/Email")
    password_field = page.get_by_role("textbox", name="Password")
    login_btn = page.get_by_role("button", name="Login")

    username_field.fill(username)
    password_field.fill(password)
    login_btn.click()
    page.wait_for_load_state("networkidle")


def logout(page: Page) -> None:
    """Perform logout if logout button or profile dropdown exists."""
    profile_menu = page.locator(".user-profile, .dropdown-toggle, #user-dropdown").first
    if profile_menu.is_visible():
        profile_menu.click()
    logout_item = page.get_by_role("link", name="Logout", exact=False)
    if logout_item.is_visible():
        logout_item.click()
        page.wait_for_load_state("networkidle")
