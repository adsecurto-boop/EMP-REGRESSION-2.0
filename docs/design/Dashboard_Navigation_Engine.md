# Dashboard Navigation Engine Design

> Design only — no code this phase. The navigation *model* (which pages exist, hierarchy, permissions) is owned by [Dashboard_Navigation.md](Dashboard_Navigation.md) and is not restated here; this document designs the *engine* that walks it.

## 1. Contract

One navigation engine (`framework/dashboard/navigation/`), the **only component that navigates**. Page objects read; plugins ask the collector; the collector asks the engine.

- One method per page-register identifier — the identifier, not the display name, is the method suffix. The register's 17 identifiers are already the stable contract used by `config/features.json`; inventing a second naming scheme (e.g., `open_screen_recordings` for `recordings`) would create a mapping problem where none exists.
- Every method: `open_<identifier>(page, params) -> PageObject | NavigationFailure`.
- `NavigationFailure` carries a machine-readable reason (`TIMEOUT`, `NOT_FOUND`, `PERMISSION_DENIED`, `UNEXPECTED_STATE`) plus detail — it flows directly into `DashboardObservation(reached=False, errors=...)`. Navigation never raises for an unreachable page.

## 2. Method Register

| Method | Params (from register Inputs) | Returns page object for | Notes |
|---|---|---|---|
| `open_dashboard_home()` | — | `dashboard_home` | The brief's `open_dashboard()` |
| `open_organization()` | organisation selection | `organization` | Possibly a precondition for everything ([Architecture §7.4](Playwright_Architecture.md)) |
| `open_users()` | search/filter/paging | `users` | |
| `open_employee(employee_ref)` | employee identifier | `employee` | `employee_ref` form unknown until observed |
| `open_live_monitoring(employee_ref)` | employee | `live_monitoring` | Brief's `open_live_monitor` |
| `open_screenshots(employee_ref, date_range)` | employee, range | `screenshots` | |
| `open_recordings(employee_ref, date_range)` | employee, range | `recordings` | Brief's `open_screen_recordings` |
| `open_timesheet(employee_ref, date_range)` | employee, range | `timesheet` | |
| `open_reports(report_type, scope, date_range)` | type, scope, range | `reports` | |
| `open_settings()` | — | `settings` | |
| `open_monitoring_control()` | — | `monitoring_control` | Highest-value page ([Navigation §5](Dashboard_Navigation.md)) |
| `open_roles()` / `open_permissions()` / `open_storage()` / `open_localization()` / `open_shift_management()` | — | respective settings children | |

`login` deliberately has **no** `open_login()` — navigation operates inside a supplied session ([Authentication design](Dashboard_Authentication.md)); arriving at the login page is a *failure signal* (`EXPIRED`), not a destination.

## 3. Behavioural Rules

1. **Route-agnostic until observed.** Whether a page is a URL, a SPA state, or a menu path is unknown. Methods encapsulate whatever the recording sessions reveal; callers never see routes. URL fragments discovered at recording time are recorded in the locator/provenance layer, not hardcoded in callers.
2. **Hierarchy from the model, resolved at run time.** The assumed parent chain (e.g., `employee` via `users`) is a hypothesis; each method documents its assumed path and *verifies arrival* (readiness condition per [Locator Standard §4.4](../ADS/locator_standard.md)) rather than trusting the click sequence.
3. **Arrival is verified, permission-aware.** A permission-denied surface must map to `PERMISSION_DENIED` — the `permissions` page spec's question "do effective permissions explain any page that could not be reached?" needs exactly this signal.
4. **Navigation emits timing.** Each method records navigated-at / arrived-at timestamps into observation metadata — cheap now, and the propagation-delay question ([Navigation §6.3](Dashboard_Navigation.md)) will need it.
5. **No navigation retries a login, ever.**
6. **Read-only params.** Employee refs, date ranges, report types are reads (filtering); nothing in a params object may name a mutating action.

## 4. Duplication Guard

Before this engine, zero navigation code exists (verified this phase — no Playwright imports anywhere under `framework/` or `plugins/`). After it, any `page.goto`, menu click, or route knowledge outside `framework/dashboard/navigation/` is a review-blocking defect. Feature plugins never navigate — the collector mediates every observation.

## 5. Cross References

- [Dashboard_Navigation.md](Dashboard_Navigation.md) — the model (identifiers, hierarchy, permissions, timestamp questions)
- [Dashboard Collector design](Dashboard_Collector.md) — the only caller of this engine
- [Locator Standard](../ADS/locator_standard.md) — readiness and waiting rules navigation obeys

---
**Document Status:** Design complete — no code; all paths hypothetical until first recording session
**Owner:** TODO
**Last Updated:** 2026-07-31
