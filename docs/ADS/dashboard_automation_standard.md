# Dashboard Automation Standard

## 1. Purpose

Governs the Dashboard Automation Layer — the Playwright-based subsystem that observes the EmpMonitor dashboard as **Layer 4 of the Evidence Model**. This is the binding standard; the detailed designs live in `docs/design/` (see §10). Where a design document and this standard disagree, this standard wins.

This standard **changes nothing upstream**: the Evidence Model ([Validation Standard](validation_standard.md)), the plugin contract ([Plugin Development Guide](plugin_standard.md)), and the Layer 4 collector contract ([`framework/validators/dashboard.py`](../../framework/validators/dashboard.py)) are frozen inputs to it.

## 2. The One Architectural Rule

**Dashboard automation is a collector, not a framework.**

The dashboard layer produces `Evidence` (EV-006, EV-008) through the existing `DashboardSnapshotCollector` contract and hands it to the existing pipeline. It draws no conclusions, owns no verdicts, schedules nothing, and no framework component outside `plugins/` may depend on it. If a change to `framework/core/`, the Evidence Model, or a plugin contract seems necessary to make dashboard automation work, the dashboard design is wrong — stop and re-review.

Concretely:

| It is | It is not |
|---|---|
| One more evidence source, peer to the SQLite and sync monitors | The centre of the framework |
| An implementation of `DashboardSnapshotCollector` | A new collector contract |
| A consumer of `framework/shared` (config, logger, retry, models) | A dependency of anything under `framework/core`, `framework/monitors`, `framework/validators` |
| Replaceable — remove it and every run still completes, reporting Layer 4 `INCONCLUSIVE` via `UnavailableDashboardCollector` | Load-bearing for any other layer |

## 3. Binding Constraints (Ratified Before This Phase — Restated, Not Renegotiated)

1. **Read-only, without exception.** Navigate, filter, page, read. Never create, modify, delete, save, toggle, export, or play back until an action is proven side-effect-free. Real people are monitored by this product ([Dashboard Page Specifications §5](../design/Dashboard_Page_Specifications.md)).
2. **The collector never enters credentials.** A session is supplied to it. Authentication is a **separate component** (§5) precisely so this constraint holds at the collector boundary.
3. **No invented product facts.** The dashboard has never been observed — 0 of 17 pages. No selector, label, URL, or expected value may be committed anywhere until it has been observed, and then only with the six verification-metadata fields ([knowledge_base README §6.1](../../knowledge_base/README.md)).
4. **A page that could not be reached is `reached=False` with a reason** — never an empty successful observation, never an exception swallowed into silence.
5. **Evidence only from registered sources.** EV-006 and EV-008 are registered ([Evidence Catalog](../Evidence_Catalog.md)); a new observable needs a new catalog row *before* it is cited.

## 4. Data Sensitivity Policy

Everything the dashboard displays is monitored-employee personal data — the L4 equivalent of the "EV-003 is count-only" rule ([Evidence Catalog §5](../Evidence_Catalog.md)).

| Artifact | Policy |
|---|---|
| Observed values in `Evidence.data` | Structure, counts, timestamps, statuses — never screenshot image content, email fields, or any per-person payload beyond what an assertion needs |
| Page screenshots (ours, of the dashboard) | Off by default. Enabled per run via configuration for debugging; written under the run's `reports/` artifact folder; treated as sensitive; never committed |
| Playwright traces | **On-failure only** by default (config-switchable). Traces embed full DOM and network payloads — sensitive, never committed |
| Playwright video | **Off** by default; explicit config opt-in for supervised debugging only |
| Downloads | **Forbidden.** `accept_downloads=False`. Export controls are treated as writes ([Page Specifications §2.3](../design/Dashboard_Page_Specifications.md)) |
| Storage state files | Secret-equivalent: outside the repository, per-environment path, never committed, never logged |
| Credentials | Never in code, configuration files committed to the repo, logs, evidence, traces, or recordings. Loaded only via the credential provider ([Authentication design](../design/Dashboard_Authentication.md)) |

## 5. Component Boundaries

Five components, one dependency direction (details: [Playwright Architecture](../design/Playwright_Architecture.md)):

```
plugins ──▶ PlaywrightDashboardCollector ──▶ Navigation ──▶ Page Objects ──▶ Locators
                     │                            │
                     └──▶ Session/Authentication ─┘──▶ PlaywrightManager (browser/context lifecycle)
```

- **PlaywrightManager** owns browser and context lifecycle. Nothing else touches Playwright's API surface directly except page objects acting through a supplied `Page`.
- **Authentication/Session** obtains and validates sessions (storage state first). It is the only component that may ever perform a login, and never during unattended collection (§6 of the [Authentication design](../design/Dashboard_Authentication.md)).
- **Navigation** maps the 17 stable page identifiers of the [Navigation model](../design/Dashboard_Navigation.md) to `open_<page>()` methods. It is the only component that navigates.
- **Page objects** read one page each. They return plain observed data; they never build `Evidence` and never assert.
- **The collector** composes the above into `DashboardObservation` → `Evidence`. It is the only component the rest of the framework sees.

## 6. Execution Policies

| Concern | Policy | Why |
|---|---|---|
| API flavour | Playwright **sync** API | The framework pipeline is synchronous; an async island would force adapters through the collector boundary |
| Browser | Chromium, pinned version recorded per run | One engine until cross-browser evidence is ever needed (it is not — this is observation, not compat testing) |
| Headless | Headless for collection; **headed only** for supervised bootstrap and recording sessions | Collection is unattended; recording is human-attended by design |
| Parallelism | **Sequential.** One browser, one context, one page, pages visited in order | Read-only observation of a live tenant: parallel sessions multiply load, interleave evidence timestamps, and risk per-session state divergence — for no corroboration gain, since one run is one observation window |
| Timeouts | Config-driven: navigation, action, and assertion timeouts under `dashboard.timeouts`; no literals in code | [Configuration Standard](configuration_standard.md) |
| Retry | Reuse `framework.shared.utils.retry.RetryPolicy` for page-level operations; never retry through a login; never retry a failed observation into a fake success | One retry mechanism in the framework, not two |

## 7. Codegen Management Policy

`playwright codegen` output is **source material, never framework code**.

1. One recording = one workflow (login, open one page, one read interaction). A recording that spans two workflows is re-recorded, not split after the fact.
2. Raw recordings land in `framework/dashboard/recordings/raw/` — quarantined: nothing imports from it, nothing executes it, CI treats it as data. Name: `NNN_<workflow>.py` matching the [Recording Plan](../design/Playwright_Recording_Plan.md).
3. Before commit, a recording is scrubbed: credentials and tokens removed, storage-state paths parameterised, target hostname replaced with a config reference.
4. Refactoring is one-way: recorded selectors are promoted into `locators/` under the [Locator Standard](locator_standard.md) (with provenance metadata), interactions into page objects, navigation into the navigation engine. The raw recording is then **deleted** — the page object is the durable artifact; keeping both invites drift.
5. Recorded **write** interactions (anything that saves, creates, toggles, deletes) are never refactored into the framework. See the Recording Plan for the workflows excluded on this ground.

## 8. What Feature Plugins May Do With This Layer

A feature plugin asks the collector to observe the pages its profile names (`expected_dashboard_pages` in `config/features.json`), receives `Evidence`, and validates it with existing generic validators plus the L4 validator interfaces ([Dashboard Validators design](../design/Dashboard_Validators.md)). A plugin never drives the browser, never navigates, and never holds a `Page`.

## 9. Non-Goals of the Dashboard Layer

- No test-case management, no BDD layer, no assertion DSL — the Validation Standard's finding model is the assertion vocabulary.
- No dashboard *testing* (the dashboard is not the system under validation; it is an evidence surface for the agent's features).
- No self-healing locators, no AI selector recovery — a broken locator is a broken observation, reported as such.

## 10. Cross References

| Deliverable | Document |
|---|---|
| Playwright architecture (managers, strategies) | [design/Playwright_Architecture.md](../design/Playwright_Architecture.md) |
| Locator policy, waiting, retry, staleness | [ADS/locator_standard.md](locator_standard.md) |
| Navigation engine | [design/Dashboard_Navigation_Engine.md](../design/Dashboard_Navigation_Engine.md) |
| Authentication, sessions, credentials, environments | [design/Dashboard_Authentication.md](../design/Dashboard_Authentication.md) |
| Collector design | [design/Dashboard_Collector.md](../design/Dashboard_Collector.md) |
| Validator interfaces | [design/Dashboard_Validators.md](../design/Dashboard_Validators.md) |
| Recording plan | [design/Playwright_Recording_Plan.md](../design/Playwright_Recording_Plan.md) |
| Page/navigation model (pre-existing, authoritative) | [design/Dashboard_Navigation.md](../design/Dashboard_Navigation.md) · [design/Dashboard_Page_Specifications.md](../design/Dashboard_Page_Specifications.md) |
| Layer 4 contract (frozen) | [`framework/validators/dashboard.py`](../../framework/validators/dashboard.py) |

---
**Document Status:** Active — binding for all Phase 5+ dashboard automation work; no product fact asserted (dashboard remains unobserved)
**Owner:** TODO
**Last Updated:** 2026-07-31
