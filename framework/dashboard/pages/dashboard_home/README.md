# Page Object -- `dashboard_home`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 012); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Organisation-level overview / landing page. |
| **Expected Inputs** | none (read) |
| **Expected Outputs** | organisation summary, active-user count, alerts |
| **Expected Elements** | organisation summary, active-user count, alert area |
| **Expected Assertions** | Does the active-user count agree with observed running agents? |
| **Dependencies** | navigation.open_dashboard_home(); components: sidebar, header |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | CountValidator, StatusValidator |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/dashboard_home.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
