# Page Object -- `login`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 001 / 002); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Session entry surface. No page object logic beyond what the session-validity probe needs: arriving here during collection is a failure signal (EXPIRED), not a destination. |
| **Expected Inputs** | credentials -- supplied to AuthenticationManager only; the collector and this page object never see them |
| **Expected Outputs** | authenticated session (storage state), or a classified failure (NO_STATE / EXPIRED / REJECTED / UNREACHABLE) |
| **Expected Elements** | username field, password field, submit, error area |
| **Expected Assertions** | Is a session valid? Is an expired session distinguishable from a rejected one? |
| **Dependencies** | authentication/ (AuthenticationManager, SessionManager). Deliberately NO open_login() navigation method |
| **Evidence Produced** | none (session state is not evidence; a failed probe is reported via the collector's unavailable record) |
| **Consumed by validators** | -- (session probe feeds DashboardValidator's existing INCONCLUSIVE path) |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/login.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
