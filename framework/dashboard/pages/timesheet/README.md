# Page Object -- `timesheet`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 006); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §2.2](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | PRIORITY PAGE. Worked/idle/break totals per employee and range -- closes the EM013/EM014 chain (clock_data6 -> displayed totals). |
| **Expected Inputs** | employee identifier, date range (reads) |
| **Expected Outputs** | worked-time, idle-time, break-time totals; per-day breakdown |
| **Expected Elements** | employee selector, date-range control, worked/idle/break totals, per-day breakdown, shift indicator |
| **Expected Assertions** | Do totals agree with clock_data6 start/end pairs? Break time vs todayRemainingBreakInSeconds? Do the parts sum to the whole (checkable without timezone knowledge -- first assertion to verify)? |
| **Dependencies** | navigation.open_timesheet(); components: employee_selector, date_range_picker |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | CountValidator, CorrelationValidator (generic) |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/timesheet.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
