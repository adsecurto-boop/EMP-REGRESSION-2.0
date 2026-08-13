"""Test Localization settings navigation and save.
"""

from playwright.sync_api import Page, expect


def test_localization_settings_save(auth_page: Page):
    """Verify navigating to Settings -> Localization and saving configuration."""
    auth_page.get_by_role("link", name="Settings ", exact=False).click()
    auth_page.get_by_role("link", name="Localization").click()
    auth_page.wait_for_load_state("networkidle")

    save_btn = auth_page.get_by_role("button", name="Save")
    expect(save_btn).to_be_visible()
    save_btn.click()
    auth_page.wait_for_load_state("networkidle")
