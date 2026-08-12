"""Playwright Dashboard Inspector & Regression Runner.

Provides browser automation, session management, page navigation, and assertion generation
for the EmpMonitor Dashboard Layer (Layer 4).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def run_playwright_inspection(url: str, headless: bool = True) -> dict[str, Any]:
    """Run Playwright page check against dashboard endpoint."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status": "BLOCKED",
            "error": "Playwright library is not installed in Python environment.",
            "url": url,
        }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            response = page.goto(url, timeout=30000)
            title = page.title()
            status_code = response.status if response else None
            page_content = page.content()
            browser.close()

            return {
                "status": "SUCCESS",
                "url": url,
                "status_code": status_code,
                "title": title,
                "page_length": len(page_content),
                "assertions": {
                    "page_loaded": status_code == 200,
                    "title_present": bool(title),
                }
            }
    except Exception as exc:
        return {
            "status": "FAILED",
            "url": url,
            "error": str(exc),
        }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EmpMonitor Playwright Dashboard Inspector")
    parser.add_argument("--url", type=str, default="https://app.dev.empmonitor.com/amember/member", help="Dashboard URL")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args(argv)

    result = run_playwright_inspection(args.url)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=== EMPMONITOR DASHBOARD PLAYWRIGHT INSPECTION ===")
        print(f"URL:         {result.get('url')}")
        print(f"Status:      {result.get('status')}")
        print(f"Status Code: {result.get('status_code')}")
        print(f"Title:       {result.get('title')}")
        print("\nJSON Output:")
        print(json.dumps(result, indent=2))

    return 0

if __name__ == "__main__":
    sys.exit(main())
