# Implementation Review — Phase 5: Dashboard Automation Foundation

## 1. What This Phase Was

The first sprint of actual product automation groundwork: the architecture, standards, and repository structure for Playwright-based observation of the EmpMonitor dashboard as **Layer 4 of the Evidence Model**. It corresponds to roadmap [Phase 4 — Playwright Foundation](roadmap/implementation_plan.md) (sprint phase numbering and roadmap phase numbering diverged in Phase 3; recorded here to prevent confusion).

Per the brief and per this phase's own standard: **design and scaffold only.** No Playwright code, no scripts, no codegen output, no feature plugins, no locators, no assertions. The dashboard remains unobserved — 0 of 17 pages — and nothing in this phase pretends otherwise.

## 2. Deliverables

| Deliverable | Location |
|---|---|
| Dashboard Automation Standard (binding) | [docs/ADS/dashboard_automation_standard.md](ADS/dashboard_automation_standard.md) |
| Playwright Architecture (Task 1 — all 14 strategy decisions) | [docs/design/Playwright_Architecture.md](design/Playwright_Architecture.md) |
| Locator Standard (Task 4 — priority order, waiting, retry, staleness) | [docs/ADS/locator_standard.md](ADS/locator_standard.md) |
| Navigation Engine design (Task 5) | [docs/design/Dashboard_Navigation_Engine.md](design/Dashboard_Navigation_Engine.md) |
| Authentication design (Task 3 — login/logout/session/storage state/credentials/environments) | [docs/design/Dashboard_Authentication.md](design/Dashboard_Authentication.md) |
| Dashboard Collector design (Task 6) | [docs/design/Dashboard_Collector.md](design/Dashboard_Collector.md) |
| Dashboard Validator interfaces (Task 7) | [docs/design/Dashboard_Validators.md](design/Dashboard_Validators.md) |
| Codegen strategy (Task 8) | [Standard §7](ADS/dashboard_automation_standard.md) + [Recording Plan](design/Playwright_Recording_Plan.md) |
| Repository structure (Tasks 2, 9 — 31 READMEs: 17 page objects with the full seven-field contract, 5 components, 7 packages, codegen quarantine) | `framework/dashboard/` |
| Recording plan (Task 10 — 12 sessions covering all 17 pages, prerequisites, exclusions) | [docs/design/Playwright_Recording_Plan.md](design/Playwright_Recording_Plan.md) |
| Architecture review (Task 11) | [docs/ARCHITECTURE_REVIEW_PHASE_5.md](ARCHITECTURE_REVIEW_PHASE_5.md) |
| Dependency rule for the new package | [Architecture Standard §2.5/§3](ADS/architecture.md) — only framework doc touched; no existing rule changed |

## 3. Decisions Worth Remembering

1. **The layer is a collector, not a framework.** Its acceptance test is the promise already written in `framework/validators/dashboard.py`: replace `UnavailableDashboardCollector` and nothing else changes. Every design choice was checked against that sentence.
2. **`dashboard.enabled=false` is the default.** Every existing run keeps its current honest behaviour (L4 `INCONCLUSIVE`) until an environment deliberately switches Layer 4 on.
3. **Storage-state-first authentication.** Unattended runs never log in; supervised, headed bootstrap produces the session. This preserved the ratified "collector never enters credentials" constraint while still delivering the brief's `login()`/`logout()` design — as a separate component.
4. **Write workflows excluded.** The brief's `create_user`/`edit_user`/`delete_user` recordings are writes against a live organisation monitoring real people; the read-only constraint wins ([Review §8](ARCHITECTURE_REVIEW_PHASE_5.md)).
5. **Reuse over rebuild:** existing generic validators (Timestamp/Frequency/Correlation), existing retry policy, existing config precedence, existing artifact manager. New interfaces limited to the five genuinely L4-shaped questions (Presence, Count, Status, ImageAvailability, RecordingAvailability).
6. **Sequential, single-context execution** — parallelism rejected in writing, with the reasons and the re-entry path recorded.
7. **Recording sessions double as first observation.** The Recording Plan is also the promotion vehicle for the 17 Hypothesis pages — every session ends with register promotion, spec correction, and locator provenance.

## 4. Residual Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | **Tenant unknown** — whether a non-production dashboard tenant exists is unresolved (Recording Plan P1). If production-only, all collection needs sign-off and the observation footprint question sharpens | Blocking prerequisite, explicitly gated; production overlay defaults `enabled=false` |
| R2 | **The dashboard may contradict the model** — SPA states instead of pages, no stable attributes, org-selection gates, short-lived sessions | Falsifiability list written into the architecture ([§7](design/Playwright_Architecture.md)) so the first implementation sprint checks rather than discovers |
| R3 | **Dependency rule not tool-enforced** — the new `framework/dashboard/` boundary (like all existing boundaries) has no import-linter | Carried from the pre-existing §3 TODO; recommend an import-boundary check when code lands |
| R4 | **Timestamp semantics still unresolved** — timezone/rounding/propagation ([Navigation §6](design/Dashboard_Navigation.md)) block every L4 timestamp assertion | Collector design captures raw+flagged-parse; `localization` read scheduled in session 011; assertions stay `INCONCLUSIVE` until measured |
| R5 | **Doc debt** — Repository_Guide tree stale; ARCHITECTURE_REVIEW.md §4.2 citation stale | Recorded in [Review §9](ARCHITECTURE_REVIEW_PHASE_5.md); neither blocks implementation |

## 5. Readiness Statement

**The framework is ready for Playwright code generation — conditionally.**

Architecturally ready, unconditionally: contracts frozen and honoured, structure in place, standards binding, duplication guards set, and the layer removable at a config flag. Nothing about writing the first line of Playwright code requires another framework decision.

Operationally, code generation (in the literal sense of this brief — `codegen` recording sessions) is gated on the Recording Plan's prerequisites, chiefly **P1 (tenant decision)** and **P2/P3 (read-role account and credentials)**. These are stakeholder/provisioning actions, not engineering ones. The first engineering sprint after they clear is: sessions 001–003, refactor into `authentication/` + the first locator registries, replace `UnavailableDashboardCollector` behind `dashboard.enabled`, and promote the first pages from Hypothesis.

Until then, generating Playwright code would mean recording against an unknown tenant with unprovisioned credentials — the plan exists precisely so that does not happen ad hoc.

---
**Document Status:** Complete — Phase 5 delivered design + scaffold; no code, no product facts asserted; readiness conditional on Recording Plan P1–P5
**Owner:** TODO
**Last Updated:** 2026-07-31
