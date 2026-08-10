# Page Object -- `recordings`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 005); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Recording list metadata for one employee and range (EM011). NO PLAYBACK -- playback is treated as a write until proven side-effect-free. |
| **Expected Inputs** | employee identifier, date range, paging (all reads) |
| **Expected Outputs** | recording count, durations, timestamps -- metadata only |
| **Expected Elements** | recording list, duration, timestamp, playback control (never operated) |
| **Expected Assertions** | Does a recording appear for an observed capture period? Does duration agree with what was captured? |
| **Dependencies** | navigation.open_recordings(); components: employee_selector, date_range_picker, paging |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | RecordingAvailabilityValidator, TimestampValidator (generic) |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/recordings.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
