# Page Object -- `permissions`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 011); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Effective permissions per role. |
| **Expected Inputs** | role selection (read) |
| **Expected Outputs** | effective-permission list |
| **Expected Elements** | role selector, effective-permission list |
| **Expected Assertions** | Do effective permissions explain any page that could not be reached (PERMISSION_DENIED navigation failures)? |
| **Dependencies** | navigation.open_permissions() |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | PresenceValidator |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/permissions.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
