# Playwright Recording Plan — First Observation Sessions

> A checklist, not code. Each recording is a **human-attended, headed** `playwright codegen` session governed by [Dashboard Automation Standard §7](../ADS/dashboard_automation_standard.md). These sessions are also the framework's **first-ever observation of the dashboard** — every recording doubles as the evidence that promotes pages in [Dashboard_Navigation.md](Dashboard_Navigation.md) from `Hypothesis`.

## 1. Prerequisites (all must hold before session 1)

| # | Prerequisite | Status |
|---|---|---|
| P1 | **Tenant decision** — confirm whether a dev/QA EmpMonitor tenant exists, or only production ([Authentication §4](Dashboard_Authentication.md)). If production-only: stakeholder sign-off recorded before any session | **OPEN — blocking** |
| P2 | A dashboard account with the **narrowest read role available**; ideally view-only. Account name recorded in session notes | OPEN |
| P3 | Credentials provisioned as environment variables per [Authentication §2.1](Dashboard_Authentication.md) — never typed into any file | OPEN |
| P4 | Dashboard URL taken from the deployment's `config.js` (RE-005; treated as secret — referenced as `<DASHBOARD_URL>` throughout this plan, value never committed) | OPEN |
| P5 | Recording host: any workstation with Playwright + Chromium pinned; **not** required to be the monitored endpoint | OPEN |
| P6 | `framework/dashboard/recordings/raw/` quarantine folder exists (created this phase) | Done |

## 2. Session Rules

1. Human drives; codegen records. The operator performs **only** the listed workflow — one workflow per recording, restart on deviation.
2. **Reads only.** No save, toggle, create, edit, delete, export, playback. If a page auto-prompts a write (e.g., "apply settings?"), dismiss and note it.
3. Before commit to `raw/`: scrub credentials/tokens, parameterise the URL to a config reference, verify no personal data is embedded in the script text.
4. During every session, keep observation notes per page: actual title, actual route/state form, element inventory vs the [Page Specifications](Dashboard_Page_Specifications.md) checklist, timezone/format of displayed timestamps, rounding, and anything that contradicts the assumed hierarchy.
5. After each session: promote the observed pages' register rows (with the six verification-metadata fields), correct the page specs, and record locators with provenance per the [Locator Standard §3](../ADS/locator_standard.md).

## 3. Recording List

**Environment:** per P1 (target: `qa`; fallback: signed-off production).
**Credentials:** the P2 read-role account via P3 — identified here only as `DASH_READ_ACCOUNT`.
**URLs:** all relative to `<DASHBOARD_URL>` (P4). Actual routes are *discovered by* these sessions, not known before them.

| # | Recording | Workflow (exact scope) | Pages observed | Feeds |
|---|---|---|---|---|
| 001 | `login` | From signed-out state: open `<DASHBOARD_URL>`, sign in as `DASH_READ_ACCOUNT`, land, save storage state. Codegen paused/discarded while credentials are typed — the artifact of this session is the **storage state + observation notes**, not a replayable credential script | `login`, landing page | [Authentication §3](Dashboard_Authentication.md) bootstrap; session-probe design |
| 002 | `logout` | From signed-in: sign out, observe where the session lands | `login` | Expired-vs-rejected classification |
| 003 | `open_monitoring_control` | Navigate to monitoring/configuration surface; read every feature toggle state and interval **without touching any** | `settings` path, `monitoring_control` | EV-008; the `from_remote\` divergence question — highest-value page |
| 004 | `open_screenshots` | Users → an employee → screenshots; set a date range; page once | `users`, `employee`, `screenshots` | EM010 chain; timestamp semantics |
| 005 | `open_recordings` | Employee → recordings; read list metadata; **no playback** | `recordings` | EM011 chain |
| 006 | `open_timesheet` | Employee → timesheet; one date range | `timesheet` | EM013/EM014 chain; the parts-sum-to-whole check |
| 007 | `open_live_monitor` | Employee → live view; observe connection indicator only | `live_monitoring` | EM012; wss corroboration |
| 008 | `search_user` | Users list: search for the monitored endpoint's user; read status | `users` | Status/presence baseline |
| 009 | `open_employee` | Employee detail: read identity header, last-seen, visible feature tabs | `employee` | `visible_features`; last-seen vs sync-cycle |
| 010 | `open_reports` | Reports: select one activity report type, org scope, small range; read; **no export** | `reports` | EM017/EM018/EM019/EM023 chain |
| 011 | `open_settings_read` | Settings sections walk-through: roles, permissions, storage, localization, shift management — read only | `settings`, `roles`, `permissions`, `storage`, `localization`, `shift_management` | `storage` retention-policy question (Page Specs §4); the timezone prerequisite (`localization`) |
| 012 | `open_dashboard_home` | Landing/overview: read org summary, active-user count | `dashboard_home`, `organization` | Active-count vs running agents |

Sessions 001–003 are the minimum viable first sitting; 004–006 the second; the rest as access allows. Twelve recordings cover all 17 register pages.

## 4. Excluded Workflows — and Why This Is Not an Omission

The sprint brief lists `create_user`, `edit_user`, `delete_user`, and `monitoring_settings` (as a *change*) among candidate recordings. **They are excluded.** Each is a write; the read-only constraint is ratified and binding ([Standard §3.1](../ADS/dashboard_automation_standard.md)) — user management mutates a live organisation, and toggling monitoring settings would alter the very agent behaviour Layers 1–3 are evidencing. No framework component will ever replay them.

If user-management validation (EM002's concern — currently unprofiled, [HB-001 §4.1](../handbook/HB-001_Product_Overview.md)) is ever prioritised, the path is: a dedicated disposable tenant, a stakeholder decision, a profile in `config/features.json`, and an amendment to the Standard — in that order. Recording them today would produce scripts nothing may run.

**`monitoring_settings` survives as recording 003 — the read of that page**, which is the valuable part anyway (EV-008 intent).

## 5. Definition of Done (per session)

- Raw recording scrubbed and quarantined (or, for 001/002, storage state + notes only)
- Observation notes filed; register rows promoted with verification metadata
- Page specs corrected where observation contradicted assumption
- Locators extracted with provenance; raw recording deleted once refactored ([Standard §7.4](../ADS/dashboard_automation_standard.md))
- Timestamp-semantics table ([Navigation §6](Dashboard_Navigation.md)) updated with what the session established

## 6. Cross References

- [Dashboard Automation Standard §7](../ADS/dashboard_automation_standard.md) — codegen policy this plan instantiates
- [Dashboard_Navigation.md §7](Dashboard_Navigation.md) — the promote-by-observation workflow these sessions execute
- [Locator Standard](../ADS/locator_standard.md) · [Authentication design](Dashboard_Authentication.md)

---
**Document Status:** Ready pending P1–P5 — no session has occurred; dashboard remains unobserved
**Owner:** TODO
**Last Updated:** 2026-07-31
