# Page Object -- `reports`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 010); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §2.3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | PRIORITY PAGE. Aggregated activity reports -- closes chains for EM017/EM018/EM019/EM023. NO EXPORT -- export is a write. |
| **Expected Inputs** | report type, scope (org/team/employee), date range (reads) |
| **Expected Outputs** | result table rows, aggregate totals |
| **Expected Elements** | report-type selector, scope selector, date range, result table, aggregate totals, export control (never operated) |
| **Expected Assertions** | Does usage/USB/email activity appear for rows observed at L2/L3? Does an empty report render as empty rather than error? (Email is the best first target: only feature with per-item observed upload success.) |
| **Dependencies** | navigation.open_reports(); components: date_range_picker, paging |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | PresenceValidator, CountValidator |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/reports.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
