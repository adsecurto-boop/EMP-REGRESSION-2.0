# Page Object -- `organization`

Folder scaffold only ([Phase 5](../../../../docs/design/Playwright_Architecture.md)). **No code until this page has been observed** (Recording Plan session 012); no locator may be committed before then ([Locator Standard](../../../../docs/ADS/locator_standard.md)).

Authoritative element/assertion detail: [Dashboard Page Specifications §3](../../../../docs/design/Dashboard_Page_Specifications.md) -- corrected by observation, never duplicated here.

| Field | Value |
|---|---|
| **Purpose** | Organisation context selection and overview. |
| **Expected Inputs** | organisation selection (read) |
| **Expected Outputs** | organisation context; observed organisation identity |
| **Expected Elements** | organisation selector, name, member count |
| **Expected Assertions** | Does the observed organisation match the locally configured tenant? |
| **Dependencies** | navigation.open_organization(); components: sidebar, header |
| **Evidence Produced** | EV-006 (L4) |
| **Consumed by validators** | PresenceValidator, StatusValidator |

**Rules:** read-only; returns plain data, never `Evidence`, never a verdict; receives a `Page`, never creates or navigates one; locators only from `locators/organization.py` (empty until observed).

**Status:** Hypothesis -- page never observed (0 elements confirmed).
