"""
Module: screenshots_page.py
Layer: Layer 4 (L4) - Web Dashboard Automation
Evidence IDs: EV-013, EV-014, EV-015
Feature: EM010_Screenshots
"""

import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from playwright.sync_api import Page, Locator, expect


class ScreenshotsPage:
    def __init__(self, page: Page, base_url: str = "https://app.dev.empmonitor.com"):
        self.page = page
        self.base_url = base_url

        # Navigation Locators
        self.nav_employee_menu = page.locator("a:has-text('Employee')")
        self.nav_employee_details = page.locator("a[href*='employee-details'], a:has-text('Employee-Details')")
        self.modal_close_btn = page.locator("button.close, button[aria-label='Close'], div.modal-header button:has-text('×')")
        
        # Search Locators
        self.search_input = page.locator("input[placeholder*='Search'], input[type='search']").first
        self.search_button = page.locator("#SearchButton, button:has-text('Search')")
        
        # Employee Grid Elements
        self.table_rows = page.locator("tbody tr, div[role='row']")
        self.tab_screenshots = page.locator("a:has-text('Screenshots'), a[href*='screenshot']")
        self.date_picker_input = page.locator("input[placeholder*='Select Date'], input.datepicker, input#dateFilter")
        self.date_search_btn = page.locator("button#search_submit, button:has-text('Search'):visible")
        
        # Screenshot UI Elements
        self.sc_scroll_container = page.locator("div.screenshot-container, div.sc-wrapper, div.timeline-slider, div.horizontal-scroll")
        self.sc_cards = page.locator("a[title*='-sc'], div.screenshot-thumb, div.sc-item")
        self.sc_next_button = page.locator("a:has-text('Next'), button.slick-next, .carousel-control-next")

    def dismiss_modals(self) -> None:
        """Dismisses any transient/promotional popups."""
        try:
            if self.modal_close_btn.first.is_visible(timeout=1500):
                self.modal_close_btn.first.click()
        except Exception:
            pass

    def navigate_to_employee_details(self) -> None:
        """Navigates to Employee Details page."""
        self.nav_employee_menu.click()
        self.nav_employee_details.click()
        self.dismiss_modals()
        self.page.wait_for_load_state("networkidle")

    def find_and_select_employee(self, email_or_identifier: str) -> Dict[str, str]:
        """
        Searches for an employee using email or name, retrieves their full name
        from the dashboard table, and clicks the record.
        """
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.fill(email_or_identifier)
        self.search_button.click()
        self.dismiss_modals()
        self.page.wait_for_load_state("networkidle")

        # Locate matching row dynamically
        target_row = self.table_rows.filter(has_text=email_or_identifier).first
        target_row.wait_for(state="visible", timeout=8000)

        # Extract full name from the row (typically in the 1st or 2nd column/gridcell)
        full_name_element = target_row.locator("td.name, div[role='gridcell'], a.emp-name").first
        full_name = full_name_element.inner_text().strip() if full_name_element.count() > 0 else email_or_identifier

        # Open employee profile
        target_row.click()
        return {
            "query_email": email_or_identifier,
            "dashboard_full_name": full_name
        }

    def switch_to_screenshots_tab(self, target_day: Optional[str] = None) -> None:
        """Switches to the screenshots tab and sets the filter date."""
        self.tab_screenshots.wait_for(state="visible", timeout=10000)
        self.tab_screenshots.click()
        self.dismiss_modals()

        if target_day:
            self.date_picker_input.wait_for(state="visible", timeout=5000)
            self.date_picker_input.click()
            day_cell = self.page.locator(
                f"td.day:not(.old):not(.new):has-text('{target_day}'), a:has-text('{target_day}')"
            ).first
            day_cell.click()
            self.date_search_btn.click()
            self.page.wait_for_load_state("networkidle")

    def scroll_gallery_to_right(self) -> None:
        """
        Scrolls the screenshot timeline/carousel to the far right to guarantee
        all dynamic elements are loaded in DOM.
        """
        # Strategy A: Scroll horizontal container via JS
        if self.sc_scroll_container.count() > 0:
            try:
                self.page.evaluate(
                    "elem => { if (elem) elem.scrollLeft = elem.scrollWidth; }", 
                    self.sc_scroll_container.first.element_handle()
                )
                time.sleep(1)
            except Exception:
                pass

        # Strategy B: Click through 'Next' pagination arrows if present
        try:
            while self.sc_next_button.first.is_visible(timeout=1000) and self.sc_next_button.first.is_enabled():
                self.sc_next_button.first.click()
                time.sleep(0.5)
        except Exception:
            pass

        self.page.wait_for_load_state("networkidle")

    def capture_dashboard_evidence_screenshot(self, output_path: Path) -> Path:
        """
        Captures a full viewport screenshot of the dashboard state as objective evidence.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(output_path), full_page=True)
        return output_path

    def get_all_rendered_screenshot_metadata(self) -> List[Dict[str, Any]]:
        """Extracts titles and timestamps of all screenshot cards rendered in UI."""
        metadata = []
        count = self.sc_cards.count()
        for idx in range(count):
            item = self.sc_cards.nth(idx)
            title = item.get_attribute("title") or item.inner_text() or f"sc_index_{idx}"
            metadata.append({
                "index": idx,
                "title": title
            })
        return metadata

    # Backward compatibility aliases
    def open_screenshots_tab(self) -> None:
        self.switch_to_screenshots_tab()

    def filter_employee(self, employee_identifier: str) -> None:
        self.find_and_select_employee(employee_identifier)

    def get_rendered_screenshot_count(self) -> int:
        return len(self.get_all_rendered_screenshot_metadata())
