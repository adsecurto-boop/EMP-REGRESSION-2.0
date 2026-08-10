# Page Object -- `shift_management`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 011); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Shift definitions and assignment. |
| **Expected Inputs** | none (read) |
| **Expected Outputs** | shift list, assignments, schedule |
| **Expected Elements** | shift list, assignment, schedule |
| **Expected Assertions** | Do shift definitions explain observed timesheet boundaries? |
| **Dependencies** | navigation.open_shift_management() |
| **Evidence Produced** | EV-008 (L1 intent) |
| **Consumed by validators** | CorrelationValidator (generic) |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/shift_management.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
