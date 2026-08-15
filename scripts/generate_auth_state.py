"""
Utility: generate_auth_state.py
Purpose: Authenticates and saves context storage state to bypass login screens.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

AUTH_PATH = Path("playwright-profile/auth.json")
AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)

def generate_state():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://app.dev.empmonitor.com/amember/member")
        page.locator("input[name*='user'], input[placeholder*='Username']").fill("qt_dev")
        page.locator("input[name*='pass'], input[placeholder*='Password']").fill("qt_developers")
        page.locator("button:has-text('Login'), input[type='submit']").click()
        
        page.wait_for_load_state("networkidle")
        context.storage_state(path=str(AUTH_PATH))
        print(f"[AUTH]: Session state successfully written to {AUTH_PATH}")
        
        context.close()
        browser.close()

if __name__ == "__main__":
    generate_state()
