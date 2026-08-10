# Architecture Review — Phase 5: Dashboard Automation Foundation

Scope: the Task 11 verification of this phase's design set against the frozen framework. Method: every claim below was checked against the repository, not asserted from intent. This phase produced **designs and folder scaffolds only** — no code — so the review verifies the designs' claims and the scaffold's structure.

## 1. No Duplicate Navigation

**Pass.** Zero navigation code existed before this phase: no Playwright import appears anywhere under `framework/` or `plugins/` (grep-verified), and no module drives a browser. The design concentrates all future navigation in one engine (`framework/dashboard/navigation/`) with the rule that any `goto`/route knowledge elsewhere is a review-blocking defect ([Navigation Engine §4](design/Dashboard_Navigation_Engine.md)). The engine's method names bind 1:1 to the 17 pre-existing page-register identifiers rather than introducing a second naming scheme — the brief's `open_screen_recordings`/`open_live_monitor` variants were normalised to the register's `recordings`/`live_monitoring` for exactly this reason.

## 2. No Duplicate Page Objects

**Pass.** One package per register identifier — 17, no more (`framework/dashboard/pages/`, verified against [Dashboard Navigation §4](design/Dashboard_Navigation.md)). Element/assertion truth stays in [Dashboard_Page_Specifications.md](design/Dashboard_Page_Specifications.md); page READMEs point at it instead of copying it, so there is one place to correct when observation contradicts assumption. Controls the specifications repeat across pages (employee selector, date-range, paging, sidebar, header) were factored into `components/` — the structural guard against the same control being written five times.

## 3. No Duplicate Locators

**Pass — vacuously today, structurally tomorrow.** Zero locators exist (the dashboard has never been observed; committing one before observation is forbidden). The [Locator Standard](ADS/locator_standard.md) enforces future non-duplication: central per-page registries, inline selectors banned, one-element-one-locator with promotion to `components/` on second use, and mandatory provenance so an unsourced locator is detectable as invented.

## 4. No Duplicate Authentication

**Pass.** No authentication code existed anywhere (verified — the only credential-adjacent artifact is the `empm.ini [auth]` *observation* in RE-005, which is product knowledge, not framework code). The design creates exactly one authentication home (`framework/dashboard/authentication/`), reusing the existing configuration system for credential references rather than inventing a parallel secrets mechanism. Sessions are storage-state-first, so even login *events* are minimised, not just login code.

## 5. No Framework Drift

**Pass.** Checked against each freeze:

| Frozen artifact | Touched? |
|---|---|
| Evidence Model (`framework/shared/models.py`, Validation Standard) | No — collector emits existing `Evidence` via existing `DashboardObservation.to_dict()` |
| Validation Standard verdict/corroboration/confidence rules | No — validator designs consume them; L4-only positives still gate to `INCONCLUSIVE` |
| Plugin contract (`framework/shared/interfaces.py`, plugin_standard) | No — plugins keep the same lifecycle; they gain evidence, not APIs to drive browsers |
| Layer 4 contract (`framework/validators/dashboard.py`) | No — implemented as-is; `UnavailableDashboardCollector` remains the default until `dashboard.enabled=true` |
| Evidence Catalog | No new rows — EV-006/EV-008 already registered cover every observable this phase designs |
| Existing generic validators | Reused (`TimestampValidator`, `FrequencyValidator`, `CorrelationValidator`); the brief's request for a dashboard `TimestampValidator` was satisfied by the existing one, not a copy |

New abstractions were limited to those the brief requires and none replicate an existing mechanism: retry reuses `shared/utils/retry.py`, configuration reuses `shared/config.py` precedence, artifacts reuse `core/artifacts.py`. One proposed manager was **rejected** as speculative (a separate ContextManager — one context per run makes it a class with one caller; folded into PlaywrightManager, [Architecture §2.2](design/Playwright_Architecture.md)).

## 6. No Dependency Violations

**Pass.** The new package's rule is recorded in [Architecture Standard §2.5/§3](ADS/architecture.md): `framework/dashboard/` → `framework/shared/` only; only `plugins/` may import it; `core`/`monitors`/`validators` may not. Two design decisions exist specifically to keep this true:

- The five new validator interfaces are placed in `framework/validators/` and consume the observation **dict** shape (already part of the frozen contract), so validators need no import of the dashboard package.
- `playwright` is imported only inside `framework/dashboard/`, keeping `import framework` working on browserless hosts — same pattern as the optional PyYAML dependency.

No enforcement tooling exists yet (the standard's §3 TODO predates this phase); until it does, the rule is review-enforced. Flagged as residual risk R3 in the [Phase 5 review](IMPLEMENTATION_REVIEW_PHASE_5.md).

## 7. Dashboard Layer Follows the Evidence Model

**Pass.**

- Collector collects; never concludes. Verdicts stay in validators/correlation.
- Absence is evidence: unreachable pages, failed session probes, and the disabled state all emit records the existing `DashboardValidator` already knows how to conclude `INCONCLUSIVE` from.
- Independence rule honoured: one `monitoring_control` visit yields EV-008 *or* EV-006, never both ([Collector §2](design/Dashboard_Collector.md)).
- Source registration honoured: nothing cites an unregistered source.
- Corroboration honoured: no L4-only `HEALTHY` is possible by construction (validators route through the existing downgrade gate).
- The layer is removable: with `dashboard.enabled=false` (the default), every run behaves exactly as today.

## 8. Conflicts Between the Sprint Brief and Ratified Constraints — Resolved, Not Ignored

Two items in the brief collided with constraints ratified before this phase. Both were resolved in favour of the ratified constraint, with the brief's intent preserved where possible:

1. **`Login()` vs "the collector never enters credentials."** Resolved by boundary: authentication is a separate component, the only one that may log in, supervised-mode only; unattended runs reuse stored sessions and never log in. The collector constraint holds verbatim ([Authentication §1](design/Dashboard_Authentication.md)).
2. **`create_user` / `edit_user` / `delete_user` recordings vs read-only.** Excluded from the [Recording Plan §4](design/Playwright_Recording_Plan.md) — they are writes against a live organisation. The path to ever doing them (disposable tenant → stakeholder decision → profile → standard amendment) is documented so the exclusion is a decision, not an omission. `monitoring_settings` survives as a *read* (recording 003).

## 9. Defects and Debt Recorded

| # | Item | Disposition |
|---|---|---|
| D1 | `docs/Repository_Guide.md` §repo-tree still shows the retired `EM001_Login`–`EM006_ScreenRecording` plugin folders and predates both `EM010`–`EM023` and `framework/dashboard/` | Known-stale before this phase; not fixed here (out of scope), carried as debt |
| D2 | `ARCHITECTURE_REVIEW.md` §4.2 cites "HB-006 §8" for the Layer 3 gap — stale since the HB-006 renumbering | Pre-existing; carried |
| D3 | Environment overlays `dev`/`qa`/`production` designed but not created (config semantics deferred to implementation) | Deliberate — Phase 5 creates no config until the tenant question (Recording Plan P1) is answered |

## 10. Verdict

Design set is internally consistent, duplication-free, dependency-clean, and drift-free against every frozen artifact. Readiness statement: [Phase 5 Review §5](IMPLEMENTATION_REVIEW_PHASE_5.md).

---
**Document Status:** Complete — all seven Task-11 checks pass; two brief-vs-constraint conflicts resolved and recorded
**Owner:** TODO
**Last Updated:** 2026-07-31
