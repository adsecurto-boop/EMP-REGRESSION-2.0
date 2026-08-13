"""Test Storage Type settings (S3 Bucket).
"""

from playwright.sync_api import Page, expect


def test_storage_type_settings(auth_page: Page):
    """Verify navigating to Settings -> Storage Type and inspecting active storage."""
    auth_page.get_by_role("link", name="Settings ", exact=False).click()
    auth_page.get_by_role("link", name="Storage Type").click()
    auth_page.wait_for_load_state("networkidle")

    expect(auth_page.get_by_text("Amazon - S3 Bucket", exact=False)).to_be_visible()
