# Page Object -- `live_monitoring`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 007); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Live/near-live view state for one employee. Connection indicator only -- no stream interaction. |
| **Expected Inputs** | employee identifier (read) |
| **Expected Outputs** | connection indicator state, stream-area presence |
| **Expected Elements** | live view area, connection indicator, employee selector |
| **Expected Assertions** | Does a stream establish while esr.exe runs? Does the indicator agree with the observed wss connection (EV-017)? |
| **Dependencies** | navigation.open_live_monitoring(); components: employee_selector |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | StatusValidator, PresenceValidator; CorrelationValidator (generic) vs EV-017 |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/live_monitoring.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
