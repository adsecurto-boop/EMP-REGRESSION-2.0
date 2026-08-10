# Page Object -- `employee`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 009); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Per-employee detail hub: identity, activity summary, feature tabs, last-seen. |
| **Expected Inputs** | employee identifier (form unknown until observed) |
| **Expected Outputs** | identity header, activity summary, visible feature tabs, last-seen timestamp |
| **Expected Elements** | identity header, activity summary, feature tabs, last-seen timestamp |
| **Expected Assertions** | Is last-seen within tolerance of the last observed sync cycle? Are tabs present only for enabled features? |
| **Dependencies** | navigation.open_employee(); components: sidebar, employee_selector |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | TimestampValidator (generic), PresenceValidator, StatusValidator |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/employee.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
