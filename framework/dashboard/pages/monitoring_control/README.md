# Page Object -- `monitoring_control`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 003); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §2.4](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | PRIORITY PAGE -- highest value of all 17. Per-feature enable state and intervals as authored in the dashboard: the likely ORIGIN of L1 intent (from_remote-prefixed local keys suggest local config is a cache). STRICTLY READ -- no toggle may ever be operated. |
| **Expected Inputs** | none (read) |
| **Expected Outputs** | per-feature enabled state, per-feature interval/schedule, org-wide policy |
| **Expected Elements** | per-feature enable/disable state, per-feature interval, organisation-wide policy, save control (never operated) |
| **Expected Assertions** | Does each feature's dashboard state match the local from_remote key? Intervals match? Any feature enabled here but absent locally, or the reverse (the currently-invisible divergence defect class)? |
| **Dependencies** | navigation.open_monitoring_control() |
| **Evidence Produced** | EV-008 (treated as L1 intent) -- or EV-006 per run config; one visit yields ONE id (independence rule) |
| **Consumed by validators** | CorrelationValidator (generic) vs EV-001/EV-002; StatusValidator |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/monitoring_control.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
