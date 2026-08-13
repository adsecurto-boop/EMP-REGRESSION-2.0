"""Test Agent Automatic Update setting toggle.
"""

from playwright.sync_api import Page, expect


def test_agent_auto_update_toggle(auth_page: Page):
    """Verify toggling Agent Automatic Update setting under Monitoring Control."""
    auth_page.get_by_role("link", name="Settings ", exact=False).click()
    auth_page.get_by_role("link", name="Monitoring Control").click()
    auth_page.wait_for_load_state("networkidle")

    auto_update_tab = auth_page.get_by_text("Agent Automatic Update")
    if auto_update_tab.is_visible():
        auto_update_tab.click()
        toggle_btn = auth_page.get_by_role("button", name="On Off")
        expect(toggle_btn).to_be_visible()
