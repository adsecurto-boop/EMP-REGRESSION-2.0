"""Test Monitoring Control configurations (Tracking toggles, DLP, Screenshots).
"""

from playwright.sync_api import Page, expect


def test_monitoring_control_settings(auth_page: Page):
    """Verify navigating to Settings -> Monitoring Control and saving tracking feature settings."""
    auth_page.get_by_role("link", name="Settings ", exact=False).click()
    auth_page.get_by_role("link", name="Monitoring Control").click()
    auth_page.wait_for_load_state("networkidle")

    # Verify group settings tabs
    expect(auth_page.get_by_title("Group Settings")).to_be_visible()

    # Expand/Toggle tracking section
    tracking_sec = auth_page.locator("#Tracking")
    if tracking_sec.is_visible():
        tracking_sec.click()

    # Save configuration
    save_btn = auth_page.get_by_role("button", name="Save")
    expect(save_btn).to_be_visible()
    save_btn.click()
    auth_page.wait_for_load_state("networkidle")
