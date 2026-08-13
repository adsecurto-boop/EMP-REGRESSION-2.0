"""Test Productivity Rules configuration and classification.
"""

from playwright.sync_api import Page, expect


def test_productivity_rules_view(auth_page: Page):
    """Verify navigating to Settings or Productivity Rules section."""
    auth_page.get_by_role("link", name="Settings ", exact=False).click()
    auth_page.get_by_role("link", name="Monitoring Control").click()
    auth_page.wait_for_load_state("networkidle")

    tracking_tab = auth_page.get_by_text("Employee General Settings")
    expect(tracking_tab).to_be_visible()
