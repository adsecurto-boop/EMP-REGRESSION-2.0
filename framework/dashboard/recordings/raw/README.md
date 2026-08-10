# recordings/raw -- Codegen Quarantine

Raw `playwright codegen` output lands here and **nowhere else**. Policy: [Dashboard Automation Standard §7](../../../../docs/ADS/dashboard_automation_standard.md).

- Nothing imports from this folder; nothing executes it; it is data, not code.
- Naming: `NNN_<workflow>.py` per the [Recording Plan](../../../../docs/design/Playwright_Recording_Plan.md).
- Committed only after scrubbing (credentials/tokens removed, URL parameterised, no personal data in script text).
- **Deleted after refactoring** into locators/page objects/navigation -- the page object is the durable artifact.
- Write workflows (create/edit/delete user, settings changes) are excluded by the read-only constraint and never land here.

Empty today: no recording session has occurred.
