"""
Module: screenshots_page.py
Layer: Layer 4 (L4) - Web Dashboard Automation
Evidence IDs: EV-013, EV-014
Feature: EM010_Screenshots
"""

from typing import List
from playwright.sync_api import Page, Locator, expect


class ScreenshotsPage:
    def __init__(self, page: Page, base_url: str = "https://app.dev.empmonitor.com"):
        self.page = page
        self.base_url = base_url

        # Dynamic Locators (Decoupled from hardcoded icon fonts and index paths)
        self.nav_employee_menu = page.locator("a:has-text('Employee')")
        self.nav_employee_details = page.locator("a[href*='employee-details'], a:has-text('Employee-Details')")
        self.modal_close_btn = page.locator("button.close, button[aria-label='Close'], div.modal-header button:has-text('×')")
        
        # Search & Filtering
        self.search_input = page.locator("input[placeholder*='Search'], input[type='search']").first
        self.search_button = page.locator("#SearchButton, button:has-text('Search')")
        self.employee_row = lambda name: page.locator(f"tr:has-text('{name}'), div[role='gridcell']:has-text('{name}')")
        
        # Navigation to Screenshots
        self.tab_screenshots = page.locator("a:has-text('Screenshots'), a[href*='screenshot']")
        self.date_picker_input = page.locator("input[placeholder*='Select Date'], input.datepicker, input#dateFilter")
        self.date_search_btn = page.locator("button#search_submit, button:has-text('Search'):visible")
        
        # Screenshot Grid Items
        self.screenshot_cards = page.locator("div.screenshot-thumb, div.sc-container, a[title*='-sc']")
        self.modal_lightbox_image = page.locator("div.modal.show img.lightbox-img, div.fancybox-content img")
        self.modal_lightbox_close = page.locator("div.modal.show button.close, a.fancybox-close-small")

    def dismiss_modals(self) -> None:
        """Dismisses any transient/promotional modals if visible."""
        try:
            if self.modal_close_btn.first.is_visible(timeout=2000):
                self.modal_close_btn.first.click()
        except Exception:
            pass

    def navigate_to_employee_details(self) -> None:
        """Navigates from sidebar to the Employee Details view."""
        self.nav_employee_menu.click()
        self.nav_employee_details.click()
        self.dismiss_modals()

    def filter_employee(self, employee_identifier: str) -> None:
        """Searches and opens the record for a specific employee."""
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.fill(employee_identifier)
        self.search_button.click()
        self.dismiss_modals()
        
        target_row = self.employee_row(employee_identifier).first
        target_row.wait_for(state="visible", timeout=8000)
        target_row.click()

    def open_screenshots_tab(self) -> None:
        """Switches to the screenshots tab within the selected employee profile."""
        self.tab_screenshots.wait_for(state="visible", timeout=10000)
        self.tab_screenshots.click()
        self.dismiss_modals()

    def filter_by_date(self, target_date_day: str) -> None:
        """Selects a date on the calendar picker and executes filter search."""
        self.date_picker_input.wait_for(state="visible", timeout=5000)
        self.date_picker_input.click()
        
        # Select active day cell dynamically
        day_cell = self.page.locator(f"td.day:not(.old):not(.new):has-text('{target_date_day}'), a:has-text('{target_date_day}')").first
        day_cell.click()
        self.date_search_btn.click()
        self.page.wait_for_load_state("networkidle")

    def get_rendered_screenshot_count(self) -> int:
        """Returns the number of verified screenshot thumbnails present on the L4 UI."""
        self.page.wait_for_selector("div.screenshot-thumb, a[title*='-sc'], div.sc-container", state="attached", timeout=10000)
        return self.screenshot_cards.count()

    def extract_screenshot_timestamps(self) -> List[str]:
        """Extracts raw titles/timestamps of all screenshots rendered on the dashboard."""
        self.page.wait_for_selector("a[title*='-sc'], div.screenshot-thumb, div.sc-container", timeout=10000)
        titles: List[str] = []
        count = self.screenshot_cards.count()
        for i in range(count):
            title = self.screenshot_cards.nth(i).get_attribute("title")
            if title:
                titles.append(title)
        return titles

    def inspect_first_screenshot(self) -> str:
        """Opens first screenshot in preview lightbox, verifies rendering, and returns its title/timestamp."""
        first_sc = self.screenshot_cards.first
        title = first_sc.get_attribute("title") or ""
        first_sc.click()
        
        # Verify lightbox container
        expect(self.modal_lightbox_image.first).to_be_visible(timeout=5000)
        self.modal_lightbox_close.first.click()
        return title
