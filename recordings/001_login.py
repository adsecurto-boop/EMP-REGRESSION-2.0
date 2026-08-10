import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page.goto("https://app.dev.empmonitor.com/amember/member")
    page.get_by_role("textbox", name="Username/Email").click()
    page.get_by_role("textbox", name="Username/Email").fill("qt_dev")
    page.get_by_role("textbox", name="Password").click()
    page.get_by_role("textbox", name="Password").fill("qt_developers")
    page.get_by_role("button", name="Login").click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
