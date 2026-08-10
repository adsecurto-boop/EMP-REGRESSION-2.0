# Page Object -- `users`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 008); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | User list: search, filter, page through monitored users and their displayed status. |
| **Expected Inputs** | search text, filters, paging (all reads) |
| **Expected Outputs** | user list with per-user status |
| **Expected Elements** | search box, user list, per-user status, paging control |
| **Expected Assertions** | Does the monitored user appear? Does their status match the locally observed agent state? |
| **Dependencies** | navigation.open_users(); components: sidebar, paging |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | PresenceValidator, StatusValidator |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/users.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
