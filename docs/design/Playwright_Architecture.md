# Playwright Architecture — Dashboard Automation Layer

> Design document for Phase 5 (roadmap [Phase 4 — Playwright Foundation](../roadmap/implementation_plan.md)). **No code exists yet**; this document decides the shape code will take. Binding rules live in the [Dashboard Automation Standard](../ADS/dashboard_automation_standard.md); this document explains and details them.

## 1. Placement in the Framework

New package: `framework/dashboard/` (structure: §8; folder rules: per-folder READMEs).

**Dependency rule** (extends [Architecture Standard §3](../ADS/architecture.md) without changing any existing rule):

- `framework/dashboard/` may depend on `framework/shared/` **only**.
- `plugins/` may depend on `framework/dashboard/`.
- Nothing under `framework/core/`, `framework/monitors/`, or `framework/validators/` may import `framework/dashboard/`.

The one seam with the rest of the framework is the contract already frozen in [`framework/validators/dashboard.py`](../../framework/validators/dashboard.py): `PlaywrightDashboardCollector` subclasses `DashboardSnapshotCollector` and produces `DashboardObservation`/`Evidence`. Registration replaces `UnavailableDashboardCollector` with the real collector — the docstring's promise "Replace it with a real collector; nothing else needs to change" is the acceptance test for this whole design.

`playwright` becomes an **optional dependency**: imported inside `framework/dashboard/` only, so `import framework` continues to work on hosts without browsers (the pattern already used for PyYAML in `framework/shared/config.py`).

## 2. Component Design

Composition-over-inheritance throughout; every class implements `Component` (`setup`/`teardown`) so lifecycle is managed like every other framework component.

### 2.1 PlaywrightManager (`framework/dashboard/playwright_manager/`)

The only module that starts/stops Playwright.

| Responsibility | Decision |
|---|---|
| Lifecycle | `setup()` starts sync Playwright and launches one Chromium; `teardown()` closes both, always, including on failure paths |
| Ownership | One instance per run, owned by the collector; never a module-level singleton (no hidden global state) |
| Browser | Chromium; executable/channel and pinned version recorded into run metadata (feeds `Verified Against Version` for any future Verified L4 claim) |
| Headless | `dashboard.headless` (default `true`); headed reserved for supervised bootstrap/recording |
| Context creation | Exposes `new_context(storage_state=...)`; applies `accept_downloads=False`, viewport, locale/timezone **as configured, never guessed** — timezone matters because the timestamp-semantics question ([Navigation §6](Dashboard_Navigation.md)) requires knowing what the *viewer* renders in |
| Tracing | Starts a trace per context when `dashboard.tracing` is `on`; default `on-failure` keeps the trace only if the observation cycle raised or any page ended `reached=False` |
| Video | `record_video` only when `dashboard.video=true` (default `false`) |

### 2.2 ContextManager

Folded into PlaywrightManager rather than a separate class: with a sequential, single-session policy there is exactly one context per run, created from storage state and closed at teardown. A separate manager would be an abstraction with one caller and one behaviour — the kind of speculative structure the freeze forbids. If parallelism is ever approved (§6), a context pool becomes a real requirement and earns its own class *then*.

### 2.3 Authentication and Session (`framework/dashboard/authentication/`)

Designed in full in [Dashboard_Authentication.md](Dashboard_Authentication.md). Summary of the split:

- **CredentialProvider** — resolves credentials/secrets from configuration + `EMPAF_`-prefixed environment variables. Nothing else reads secrets.
- **SessionManager** — loads/saves storage state, probes session validity (distinguishes *expired* from *rejected* — the open question the `login` page spec asks), decides reuse.
- **AuthenticationManager** — the only component permitted to perform `login()`/`logout()`, and only in supervised (headed, human-attended) mode. Unattended collection consumes stored sessions exclusively, preserving the ratified constraint that the *collector* never enters credentials.

### 2.4 Navigation Engine (`framework/dashboard/navigation/`)

Designed in [Dashboard_Navigation_Engine.md](Dashboard_Navigation_Engine.md). One `open_<identifier>()` per page-register identifier; returns the page object or a typed `NavigationFailure(reason)` — never raises for an unreachable page, because unreachable-with-reason is exactly what `DashboardObservation(reached=False)` reports.

### 2.5 Page Objects (`framework/dashboard/pages/`) and Components (`framework/dashboard/components/`)

- One package per page-register identifier (17), plus shared components for elements the page specifications repeat across pages: `sidebar`, `header`, `employee_selector`, `date_range_picker`, `paging`. A control that appears on two pages is a component, or it will be written twice.
- A page object exposes **read methods returning plain data** (`dict`/dataclass/`datetime`), named after the page spec's Expected Elements. It receives a `Page`; it never creates one, never navigates elsewhere, never builds `Evidence`, never asserts.
- Every page folder's README carries the Task-2 contract (Purpose / Inputs / Outputs / Elements / Assertions / Dependencies / Evidence) and defers element truth to [Dashboard_Page_Specifications.md](Dashboard_Page_Specifications.md) — single source, no duplication.

### 2.6 Locators (`framework/dashboard/locators/`)

One module per page, named constants only, governed by the [Locator Standard](../ADS/locator_standard.md). **Empty until observation**: committing a locator before its page has been opened is forbidden. Each locator carries provenance metadata (observed date, dashboard version, recording reference).

### 2.7 Helpers (`framework/dashboard/helpers/`)

Only what proves shared in practice: safe-read wrappers (element → value-or-absent), displayed-timestamp parsing (which must *flag* the unresolved timezone question, not silently assume), evidence-artifact capture. A helper duplicating something in `framework/shared/utils` (retry, datetime tolerance, hashing) is a review-blocking defect.

## 3. Strategy Decisions (Task 1 checklist)

| Strategy | Decision | Rationale / policy source |
|---|---|---|
| Browser Manager | §2.1 — one per run, sync API, Chromium pinned | Framework is synchronous; one engine suffices for observation |
| Context Manager | One context per run from storage state; no pool | §2.2 |
| Authentication Manager | Supervised-only login; storage-state-first | Ratified credential constraint; [Authentication design](Dashboard_Authentication.md) |
| Session Manager | Storage-state persistence + validity probe + expiry classification | [Authentication design §4](Dashboard_Authentication.md) |
| Locator Strategy | testid → id → role → aria-label → stable CSS → XPath; central per-page registries; provenance required | [Locator Standard](../ADS/locator_standard.md) |
| Retry Strategy | `framework.shared.utils.retry.RetryPolicy` at operation level; no retry through login; no retry of a completed-but-unwelcome observation | One retry mechanism; retrying an honest "not there" into a "there" would fabricate evidence |
| Timeout Strategy | `dashboard.timeouts.{navigation,action,expect}` from configuration; per-page override table allowed; no literals | [Configuration Standard](../ADS/configuration_standard.md) |
| Screenshot Strategy | Off by default; per-run opt-in; stored via `ArtifactManager` under `reports/`; sensitive | [Standard §4](../ADS/dashboard_automation_standard.md) |
| Tracing Strategy | On-failure by default; full-on/off via config; traces sensitive, never committed | [Standard §4](../ADS/dashboard_automation_standard.md) |
| Video Strategy | Off; supervised debugging opt-in only | [Standard §4](../ADS/dashboard_automation_standard.md) |
| Download Strategy | Forbidden; `accept_downloads=False`; export controls are writes | Read-only constraint |
| Storage State Strategy | Per-environment file outside repo; secret-equivalent; refreshed after successful run | [Authentication design §5](Dashboard_Authentication.md) |
| Headless Strategy | Headless unattended; headed only supervised | [Standard §6](../ADS/dashboard_automation_standard.md) |
| Parallel Execution | Sequential; revisit only with a written case | §6 |

## 4. Configuration Additions

New `dashboard` block in `config/framework.json` + environment overlays (keys designed now, added when implementation lands — configuration precedence and `${VAR}` substitution already exist in `framework/shared/config.py`):

```
dashboard:
  enabled: false            # Layer 4 stays off until a session and tenant are provisioned
  base_url: "${EMPMON_DASHBOARD_URL}"      # value never committed; config.js holds it (RE-005: secret)
  headless: true
  timeouts: { navigation_ms, action_ms, expect_ms }
  storage_state_path: "${EMPAF_STORAGE_STATE_DIR}/<environment>.json"
  tracing: "on-failure"     # on | on-failure | off
  video: false
  screenshots: "off"        # off | on-failure | on
  pages: []                 # default observation set; plugins request their own
```

`enabled: false` is the default so that every existing run keeps its current honest behaviour (`UnavailableDashboardCollector` → `INCONCLUSIVE`) until Layer 4 is deliberately switched on per environment.

## 5. Failure Model

Aligned with the [Error Handling Standard](../ADS/error_handling_standard.md): conditions the layer exists to observe are **reported, not raised**.

| Condition | Behaviour |
|---|---|
| Page unreachable, element absent, empty state | `DashboardObservation(reached=False / values absent)` with reason — observation, not exception |
| Session invalid/expired | Collection aborts for L4 only; evidence of the failed probe emitted; run continues, L4 findings `INCONCLUSIVE` |
| Browser/Playwright failure (launch, crash) | `EvidenceError` from `collect()` — the source could not be read at all, which the `Collector` contract already distinguishes from collecting an absence |
| Timeout on read | Retried per policy; then recorded as an unreachable/absent observation with the timeout as reason |

## 6. Parallel Execution — Deliberately Rejected for v1

One browser, one context, one page, sequential visits. Reasons: (a) the tenant is a **live production monitoring system** — observation load must stay minimal; (b) evidence timestamps from interleaved sessions would complicate every freshness correlation for zero corroboration gain (two simultaneous logins are not independent observations); (c) the orchestrator executes plugins sequentially anyway, so parallel page visits would optimise a non-bottleneck. Revisiting requires a written case in an architecture review, not a config flag.

## 7. What Would Falsify This Design

Recorded now so the first implementation sprint checks them instead of discovering them:

1. The dashboard may be a SPA whose "pages" are states, not URLs — navigation methods survive (identifiers are the contract), but `open_*` implementations and the reached-probe change.
2. Session cookies may be short-lived or IP-bound — storage-state reuse collapses to per-run supervised bootstrap (design already tolerates this; cadence suffers).
3. The dashboard may render no stable attributes at all (no testids/ids) — locator standard's lower tiers absorb this at higher maintenance cost.
4. An org/tenant selection step may gate every page — becomes a navigation precondition on `organization`, already a register page.

## 8. Repository Structure (created this phase, folders + READMEs only)

```
framework/dashboard/
├── README.md                  # boundary rules, dependency rule, package map
├── playwright_manager/        # §2.1
├── authentication/            # §2.3
├── navigation/                # §2.4
├── pages/                     # §2.5 — 17 identifier-named packages
├── components/                # §2.5 — sidebar, header, employee_selector, date_range_picker, paging
├── locators/                  # §2.6 — empty until observation
├── helpers/                   # §2.7
└── recordings/raw/            # codegen quarantine (Standard §7)
```

## 9. Cross References

- [Dashboard Automation Standard](../ADS/dashboard_automation_standard.md) — binding policies
- [Dashboard Navigation](Dashboard_Navigation.md) · [Dashboard Page Specifications](Dashboard_Page_Specifications.md) — the page model this layer implements
- [`framework/validators/dashboard.py`](../../framework/validators/dashboard.py) — frozen contract
- [Recording Plan](Playwright_Recording_Plan.md) — first observation session

---
**Document Status:** Design complete — no code, no product facts asserted; dashboard remains unobserved (0 of 17 pages)
**Owner:** TODO
**Last Updated:** 2026-07-31
