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
    page.get_by_role("link", name="Settings ").click()
    page.get_by_role("link", name="Localization").click()
    page.get_by_role("button", name="Save").click()
    page.locator("div").nth(1).dblclick()
    page.get_by_role("link", name="Settings ").click()
    page.get_by_role("link", name="Monitoring Control").click()
    page.get_by_title("Group Settings").click()
    page.get_by_text("Employee General Settings").click()
    page.get_by_text("Visible").click()
    page.locator("#Tracking").click()
    page.locator("#keystrokes1").check()
    page.locator("#email_monitoring1").check()
    page.locator("#web_usage1").check()
    page.locator("#screenshots1").check()
    page.locator("input[name=\"videoOption\"]").first.check()
    page.get_by_role("row", name="Screen Recording With Voice").get_by_label("Enable").check()
    page.locator("#ScreenCast1").check()
    page.get_by_text("DLP Features").click()
    page.locator("#clipboard_detection_enable").check()
    page.locator("#Screens").get_by_text("Screenshots").click()
    page.get_by_text("Agent Automatic Update").click()
    page.get_by_role("button", name="On Off").click()
    page.get_by_text("Employee's tracking Time").click()
    page.get_by_role("link", name="Unlimited").click()
    page.get_by_role("button", name="Save").click()
    page.get_by_role("link", name="Settings ").click()
    page.get_by_role("link", name="Storage Type").click()
    page.get_by_role("row", name="Amazon - S3 Bucket Active ").locator("#dropdownMenuLink").click()
    page.get_by_role("row", name="Amazon - S3 Bucket Active ").locator("#dropdownMenuLink").click()
    page.get_by_text("Amazon - S3 Bucket Is").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
