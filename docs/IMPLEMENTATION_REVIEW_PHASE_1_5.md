# Implementation Review — Phase 1.5: Validation & Execution Engine

## 1. Summary

Phase 1.5 delivers the execution and validation engine every future EmpMonitor plugin will run through. All twelve required components are implemented: ~5,800 new lines across 11 new modules plus substantial additions to two existing ones, taking the framework to ~12,400 lines.

**No architectural change was required.** The frozen architecture accommodated every component. Five contract *extensions* were made, all additive and backward compatible (§3.2). Three defects found during self-review were fixed (§6).

Verification: **162 of 162 contract checks pass**, every module imports in isolation, no circular dependency exists, and the framework executes a plugin type it has never seen with zero framework changes — the sprint's stated success criterion.

## 2. Files Created and Modified

### New modules (`framework/core/`)
| Module | Lines | Delivers |
|---|---|---|
| `execution.py` | 847 | Execution engine: sequential/parallel, cancellation, timeout, retry, graceful shutdown, resume |
| `scheduler.py` (extended) | 691 | Scheduler engine: continuous, interval, cron, event-driven, one-shot; five-field cron parser |
| `lifecycle.py` | 635 | Plugin lifecycle engine: 10 stages, each emitting events |
| `validation.py` | 567 | The verdict engine: layer evaluation, correlation, conflict resolution, confidence, aggregation |
| `artifacts.py` | 514 | Artifact manager with execution id, timestamp, module, source, checksum |
| `graph.py` | 474 | Execution DAG: failure propagation, partial execution, resume, text/Mermaid/DOT rendering |
| `pipeline.py` | 432 | Collector → Normalizer → Validator → Correlator → Verdict pipeline |
| `dependencies.py` | 375 | Dependency resolver: topological sort, cycles, optional/required, version compatibility |
| `aggregator.py` | 360 | Result aggregator: evidence, findings, warnings, errors, performance, statistics, verdict |
| `metrics.py` | 347 | Metrics engine: timing, CPU, memory, retries, failures, warnings, skipped, blocked |
| `hooks.py` | 286 | Extension hooks: 16 before/after points |
| `timeline.py` | 284 | Event-sourced execution timeline |

### Modified
`shared/interfaces.py` (Normalizer, Correlator, optional Plugin hooks) · `shared/models.py` (`LifecycleStage`, richer `ExecutionStatus`, extended `PluginMetadata`) · `shared/exceptions.py` (5 new types) · `shared/utils/version.py` (constraint matching) · `shared/utils/http_utils.py` (clock fix) · `core/registry.py` (delegates ordering) · `core/event_bus.py` (11 new event types) · `core/orchestrator.py` (rewired onto the engine) · `core/__init__.py`.

## 3. Architecture Compliance Report

### 3.1 Frozen constraints
| Requirement | Status | Evidence |
|---|---|---|
| Dependency rules ([architecture.md §3](ADS/architecture.md)) | ✅ | `shared` imports nothing above it; no framework module imports `plugins`; verified by grep |
| No circular imports | ✅ | All modules import **in isolation**, not merely in a favourable order |
| Verdict model unchanged (§6) | ✅ | Engine consumes the ratified `Verdict.aggregate` precedence; no new verdicts |
| Corroboration rules unchanged (§5) | ✅ | `ValidationEngine` delegates to `Finding`'s constructor invariants |
| Confidence computed, never asserted (§8.2) | ✅ | `build_finding` computes; monotonicity enforced |
| Failure taxonomy unchanged (§9) | ✅ | `FailureClass.from_layer` derives from first divergence |
| Collector/validator separation ([Manifest §4](FRAMEWORK_MANIFEST.md)) | ✅ | Pipeline enforces it structurally: collectors return `Evidence`, only validators return `Finding` |
| One artifact, one collector (§4.1) | ✅ | Pipeline composes collectors; none re-reads another's artifact |
| No EmpMonitor rules in the engine | ✅ | `validation.py` references no product path, process, schema, or endpoint |
| No feature/Playwright/PowerShell/SQLite-parsing/log-parsing/API code | ✅ | None present |
| Determinism | ✅ | 25 repeated identical inputs produced one verdict; ordering sorted throughout |
| Python 3.12+, typing, dataclasses, ABCs, DI | ✅ | Frozen slotted dataclasses; every collaborator injected |
| Documented public API | ✅ | Module, class, and method docstrings with Args/Returns/Raises |

### 3.2 Additive contract extensions (five, all backward compatible)

The brief required capabilities the frozen contracts did not yet express. Each extension adds; none changes or removes existing behaviour, so all Phase 1 code and any conforming plugin still works unchanged.

| Extension | Why required | Compatibility |
|---|---|---|
| `Normalizer`, `Correlator` ABCs | The brief's pipeline names both stages | New types; nothing implements them by force |
| Optional `Plugin` methods (`should_execute`, `precheck`, `validate`, `postcheck`) | Lifecycle stages need plugin participation | All have safe defaults; a minimal plugin implements only `execute` |
| `LifecycleStage` enum | Stages are part of the plugin contract, and reports reference them | New enum |
| `PluginMetadata`: `optional_depends_on`, `requires`, `timeout_seconds`, `max_attempts` | Brief requires optional deps, version compatibility, timeouts, retry | All defaulted; existing construction unaffected |
| `ExecutionStatus`: `TIMED_OUT`, `CANCELLED` | A timeout and a crash are different outcomes and must not be conflated | New members; existing members unchanged |

None of these touches the verdict model, layer model, corroboration rules, dependency direction, or collector/validator separation — the five things [Manifest §11](FRAMEWORK_MANIFEST.md) defines as structural. They are therefore extensions under that rule, not amendments.

### 3.3 Internal core layering

`core` grew from 7 to 18 modules, so an explicit tier order now prevents cycles (documented in `core/__init__.py`): leaf utilities → graph/timeline/registry → pipeline/lifecycle → execution → aggregator → orchestrator. A module imports only from tiers above it.

## 4. Verification Performed

| Check | Result |
|---|---|
| Contract behaviour harness | **162 / 162** |
| All modules import | 100% |
| Isolated import (cycle detection) | 0 cycles |
| Dependency-rule grep | 0 violations |
| Duplicate topological sort | Eliminated (registry 0, dependencies 1) |
| `python run.py --check` | Starts successfully |
| End-to-end run, sequential and parallel | Both produce reports |

Coverage by component: resolver (12 checks), graph (12), validation engine (18), pipeline (7), hooks (5), lifecycle (13), execution engine (19), scheduler (23), metrics (8), artifacts (13), timeline (9), aggregator (10), end-to-end (9), unknown-plugin capability (4).

Behaviours specifically confirmed:
- **Cycles detected** and reported without raising in tolerant mode; raised in strict mode.
- **Verdicts deterministic** across 25 repetitions of identical input.
- **Timeouts return promptly** (0.2 s limit on a 2 s unit returned in < 1.5 s) and yield `TIMED_OUT` → `INCONCLUSIVE`.
- **Parallel execution is genuinely concurrent** (4 × 50 ms units completed in < 190 ms).
- **`CLEANUP` runs even after a mid-execution crash.**
- **Failure propagation blocks dependents** rather than running them, with the reason naming the root cause.
- **Resume** skips seeded units and runs only outstanding work.
- **Every event reaches the timeline**, with monotonic sequence numbers breaking timestamp ties.
- **Artifact tampering is detected** by checksum re-verification.

## 5. Duplicated Functionality — Detected and Removed

| Duplication | Resolution |
|---|---|
| Topological sort in both `registry.py` and `dependencies.py` | **Removed.** `registry.resolve_order` now delegates; `dependencies` is the single implementation. Two sorts would eventually disagree, making run order depend on which path resolved it. |
| Timeline built from both orchestrator records and event history (a Phase 1 defect) | **Removed.** The timeline is event-sourced only; bus history defaults off so the same events are not stored twice. |
| Bus history vs. timeline | `keep_event_history` now defaults to `False` in `bootstrap`, since the timeline already records everything. |
| `utc_now` in `models` and `datetime_utils` | Retained deliberately: `models` must not import `utils` without coupling the contract layer to helpers. Documented in both. |
| Attachment projection in two scopes of `Report.to_dict` | Accepted: two call sites of a five-line literal; extraction would add indirection without removing meaningful duplication. |

## 6. Defects Found in Self-Review and Fixed

1. **`time.monotonic()` cannot measure short durations on Windows.** Its resolution is 15.625 ms, so a unit finishing in under ~16 ms measured as `0.016` or `0.0` — and short units dominate a validation run. Switched to `time.perf_counter()` (~100 ns resolution, 156,000× finer) in `metrics.py` and in `http_utils.py`, where the same defect would have corrupted the Layer 3 latency measurements the [Synchronization Monitor design](design/Synchronization_Monitor.md) §13 depends on.
2. **`should_execute` emitted a duplicate `PRECHECK` stage record.** The applicability gate was recorded as a lifecycle stage, so every unit logged two `PRECHECK` entries. It is now a gate, not a stage — it is asked before any resource is acquired.
3. **Dead code and incoherent state in two new modules.** `pipeline.run` built a `ValidationContext` then discarded it; `lifecycle._terminal` computed a `blocked_reason` that could never be correct (blocking is handled by `_blocked`). Both removed.

A fourth finding turned out to be **correct behaviour, wrongly asserted by the test**: a plugin that constructs `Evidence` directly gets the default `MEDIUM` reliability and therefore `MEDIUM` confidence, because catalog reliability is applied by `EvidenceStore.add`. This fails in the *safe* direction — confidence understated, never overstated — so the code stands. It is now documented at the point of use in `validation.py`, since a plugin author must route evidence through the store to have it assessed at its registered strength.

## 7. Extension Point Review

The sprint's success criterion is that the framework can execute completely unknown plugins without modification. Verified directly (harness §14): a plugin declaring an absent optional dependency, custom evidence layers, retry policy, and lifecycle hooks executed to a `HEALTHY` verdict with **zero framework changes**.

| Extension | Mechanism | Framework change needed? |
|---|---|---|
| New plugin | Implement `Plugin`; register or auto-discover | No |
| New collector / normalizer / validator / correlator | Implement the ABC; add to `EvidencePipeline` | No |
| New evidence source | Row in `Evidence_Catalog.md` + `config/framework.json` | No |
| Behaviour around any stage | 16 `HookPoint`s, before/after, with veto | No |
| New scheduling mechanism | New `ScheduleKind` + `_advance` branch | Enum only |
| Report renderer (HTML/PDF) | Implement `Reporter`; `ArtifactKind` already reserves both | No |
| Layer 3 collector | Implement per its design; `EV-007` and `SynchronizationError` reserved | No |
| Custom execution policy | Inject a `LifecycleEngine`, `CancellationToken`, or `ValidationEngine` | No |
| Timeline/metrics consumers | Subscribe to the bus; `to_dict()` on both | No |
| Resume from prior run | Pass `completed={}` to `execute` | No |

Deliberate seams left open for later phases: `Reporter` has no implementation (models only, per brief), `Scheduler` has an engine but nothing drives it on a clock (execution policy belongs to the execution engine), and `monitors/` and `validators/` remain empty scaffolds.

## 8. Performance Risks

| # | Risk | Severity | Detail |
|---|---|---|---|
| 8.1 | **Timeouts cannot be enforced, only observed** | **High** | Python cannot kill a thread. A unit exceeding its timeout is *abandoned*: recorded `TIMED_OUT` while its thread may run to completion, holding memory, file handles, and possibly a browser. Units must cooperate with `CancellationToken`. Mitigated by daemon-style non-blocking pool shutdown, so an abandoned thread cannot prevent interpreter exit — but it can still consume resources for the rest of the run. A process-based executor would fix this at the cost of serialising context; recommended only if abandonment proves harmful in practice. |
| 8.2 | Level-barrier parallelism under-utilises workers | Medium | A dependency level finishes only when its slowest unit does, so one slow unit idles the pool. Chosen because a level boundary *is* the guarantee that dependencies have finished — correctness structural rather than policed. A work-stealing scheduler would improve utilisation and would need its own dependency-completion tracking. |
| 8.3 | One thread pool per timed unit | Medium | `_attempt_once` creates a single-worker pool per attempt when a timeout is set. Pool creation is cheap relative to validation work, but a run with hundreds of timed units pays it hundreds of times. Reuse a shared pool if unit counts grow large. |
| 8.4 | Cron `next_after` scans minute by minute | Low | Up to ~527,000 iterations for a pathological expression, bounded by a 366-day horizon so it always terminates. Fine at registration frequency; a field-arithmetic implementation would be faster if schedules are computed in hot paths. |
| 8.5 | `tracemalloc` distorts what it measures | Low | Memory tracing slows execution, so it is opt-in (`metrics.trace_memory`, default off) — otherwise it would corrupt the timings collected alongside it. |
| 8.6 | Whole-run state held in memory | Low | Evidence, findings, timeline, and metrics accumulate for the run's duration. Fine for expected plugin counts; a long continuous-monitoring session would need streaming or periodic flushing. |
| 8.7 | Synchronous hook and event delivery | Low | A slow subscriber or hook directly extends the run. Accepted deliberately: asynchronous delivery would make event ordering non-deterministic, and ordering is what makes the timeline usable as a correlation aid. |

## 9. Remaining TODOs

| Item | Where | Blocking? |
|---|---|---|
| Port both harnesses (162 + 86 checks) into the repository | scratchpad → `tests/` | No, but highest-value early Phase 2 task |
| Evidence Catalog sync check (doc vs. config mirror) | [Phase 1 review §9.1](IMPLEMENTATION_REVIEW.md) | No — still the likeliest long-term defect |
| Mechanical dependency-rule enforcement | [architecture.md §3](ADS/architecture.md) | No |
| Toolchain: formatter, linter, type checker | [coding_standards.md §4](ADS/coding_standards.md) | No |
| Update `error_handling_standard.md` §3–§4, §6 to reference the implemented hierarchy and retry policy | [error_handling_standard.md](ADS/error_handling_standard.md) | No — code has now answered these TODOs |
| Document ownership (every doc still `Owner: TODO`) | Whole set | No |
| `milestones.md` / `backlog.md` still empty | `docs/roadmap/` | No |
| Extract `Finding` schema to `finding_schema.md` | [Architecture Review §8.1](ARCHITECTURE_REVIEW.md) | No |
| Decide whether a `Reporter` implementation lands in Phase 2 or later | [reporting.md](ADS/reporting.md) | No |
| Wire a driver that polls `SchedulerEngine.due()` and executes | `core/scheduler.py` | No — deliberately out of scope; no EmpMonitor task is scheduled |

## 10. Definition of Done — Phase 1.5

| Criterion | Status |
|---|---|
| No circular imports | ✅ 0 cycles, verified in isolation |
| Execution engine starts | ✅ Sequential and parallel, end-to-end |
| Scheduler starts | ✅ All five kinds; 23 checks |
| Plugin lifecycle works | ✅ All 10 stages, each emitting events |
| Dependency resolver detects cycles | ✅ Tolerant and strict modes |
| Validation engine produces deterministic verdicts | ✅ 25 repetitions, one verdict |
| Artifact manager stores metadata correctly | ✅ Execution id, timestamp, module, source, checksum; tamper detected |
| Metrics engine records execution | ✅ Timing, CPU, memory, retries, counters |
| Timeline contains every event | ✅ Event-sourced wildcard subscription |
| Implementation Review | ✅ This document |
| Architecture Compliance Report | ✅ §3 |
| Extension Point Review | ✅ §7 |
| Performance Risks | ✅ §8 |
| Remaining TODOs | ✅ §9 |
| **Executes unknown plugins with no framework change** | ✅ Verified, harness §14 |

## 11. Cross References

- [Framework Manifest](FRAMEWORK_MANIFEST.md) · [Validation Standard v1.0](ADS/validation_standard.md) · [Evidence Catalog](Evidence_Catalog.md)
- [Phase 1 Implementation Review](IMPLEMENTATION_REVIEW.md) · [Architecture Freeze Report](ARCHITECTURE_FREEZE_REPORT.md)
- [Framework Architecture Standard](ADS/architecture.md) · [Synchronization Monitor Design](design/Synchronization_Monitor.md)
- [Implementation Plan](roadmap/implementation_plan.md)

---
**Document Status:** Final — Phase 1.5 complete
**Owner:** TODO
**Last Updated:** 2026-07-30
