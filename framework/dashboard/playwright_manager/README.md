# framework/dashboard/playwright_manager

Folder scaffold only (Phase 5).

Browser and context lifecycle -- the only module that starts/stops Playwright. Design: [Playwright Architecture §2.1](../../../docs/design/Playwright_Architecture.md). Policies: headless default, accept_downloads=False, tracing on-failure, video off, Chromium pinned and version-recorded.
