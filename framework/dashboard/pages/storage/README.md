# Page Object -- `storage`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 011); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §4](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Storage usage and retention policy -- the page that would turn the observed inert local retention sweep (logs placeholder, -1 deleted) into an evidenced end-to-end contradiction. |
| **Expected Inputs** | none (read) |
| **Expected Outputs** | usage figures, retention policy |
| **Expected Elements** | usage figures, retention policy |
| **Expected Assertions** | Does the dashboard retention policy agree with observed local retention behaviour (Page Specs section 4)? |
| **Dependencies** | navigation.open_storage() |
| **Evidence Produced** | EV-008 (L1 intent) |
| **Consumed by validators** | CorrelationValidator (generic) |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/storage.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
