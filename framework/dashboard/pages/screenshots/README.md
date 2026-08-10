# Page Object -- `screenshots`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 004); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §2.1](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | PRIORITY PAGE. Screenshot list metadata for one employee and range -- closes the EM010 chain (pending_screenshots6 drain -> visible screenshot). |
| **Expected Inputs** | employee identifier, date range, paging (all reads) |
| **Expected Outputs** | item count, per-item timestamps, thumbnail presence, empty-state -- METADATA ONLY, never image content |
| **Expected Elements** | employee selector, date-range control, screenshot list/grid, per-item timestamp, thumbnail, empty-state indicator, paging |
| **Expected Assertions** | Does a screenshot appear for a period when the queue was observed draining? Timestamp within tolerance of capture? Count agrees with queue-drain rows? Empty state (not error) when nothing captured? |
| **Dependencies** | navigation.open_screenshots(); components: employee_selector, date_range_picker, paging |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | ImageAvailabilityValidator, CountValidator, TimestampValidator (generic) |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/screenshots.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
