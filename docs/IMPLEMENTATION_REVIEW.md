# Implementation Review — Phase 1: Framework Foundation

## 1. Summary

Phase 1 delivers the reusable framework foundation every future validator, collector, monitor, and plugin inherits from. All eleven required components are implemented, ~6,500 lines across 26 new Python modules plus configuration. The framework starts, produces a report, and exits with a verdict-derived code.

**No architectural change was required.** The frozen architecture supported implementation as specified. One placement decision was *derived* from the frozen dependency rules rather than added to them (§3.1), and two defects found during self-review were fixed (§6).

Verification: **86 of 86 contract checks pass**, all 28 modules import cleanly in isolation, and no circular dependency or dependency-rule violation exists.

## 2. Files Created

### `framework/shared/` — contracts and cross-cutting foundations
| File | Contents |
|---|---|
| `constants.py` | Invariant values; deliberately contains zero EmpMonitor paths/names/endpoints |
| `exceptions.py` | `FrameworkError` hierarchy: configuration, environment, evidence, validation, plugin (+ not-found/dependency), synchronization, scheduler, reporting |
| `models.py` | `EvidenceLayer`, `Verdict`, `Confidence`, `FailureClass`, `SourceReliability`, `EvidenceSourceSpec`, `Evidence`, `EvidenceConflict`, `Finding`, `ExecutionStatus`, `ExecutionResult`, `PluginMetadata`, `ValidationContext`, `EnvironmentInfo`, `AgentInfo`, `DashboardInfo` |
| `interfaces.py` | `Component`, `Collector`, `Validator`, `Monitor`, `Plugin`, `Reporter`, `Scheduler` ABCs |
| `config.py` | `Configuration`, `ConfigurationManager` (singleton), layered load, `${VAR}` substitution, validation |
| `logger.py` | Structured/console/rotating-file logging, execution + correlation + plugin IDs via `ContextVar`, `JsonFormatter` |
| `utils/` | `filesystem`, `datetime_utils`, `version`, `hashing`, `retry`, `json_utils`, `ini_utils`, `sqlite_utils`, `http_utils` |

### `framework/core/` — orchestration engine
| File | Contents |
|---|---|
| `context.py` | `RuntimeContext` (execution ID, timing, environment/agent/dashboard info, output root, evidence store, plugin registry) |
| `event_bus.py` | `EventBus`, `Event`, `EventType` (22 lifecycle/plugin/evidence/validation/monitor/report events), `Subscription` |
| `evidence.py` | `EvidenceCatalog`, `EvidenceStore`, `build_catalog_from_config` |
| `registry.py` | `PluginRegistry`: registration, class registration, runtime discovery, deterministic topological ordering |
| `reporting.py` | `Report`, `ReportMetadata`, `ReportSummary`, `ReportSection`, `FindingRecord`, `TimelineEntry`, `Attachment` — models only |
| `scheduler.py` | `ScheduleKind`, `ScheduleSpec` — contract vocabulary only, no scheduling |
| `orchestrator.py` | `bootstrap()`, `BootstrapResult`, `Orchestrator` |

### Other
`framework/__init__.py`, `framework/monitors/__init__.py`, `framework/validators/__init__.py` (documented empty-by-design), `run.py` (CLI entry point), `config/framework.json`, `config/environments/local.json`, `config/README.md`, `.gitignore`.

## 3. Architecture Compliance

| Requirement | Status | Evidence |
|---|---|---|
| Dependency rules ([architecture.md §3](ADS/architecture.md)) | ✅ | Verified by grep: `shared` imports nothing above it; no framework module imports `plugins`; monitors/validators import only `shared` |
| No circular imports | ✅ | All 28 modules import successfully *in isolation*, not just in a favourable order |
| Verdict model ([validation_standard.md §6](ADS/validation_standard.md)) | ✅ | `Verdict.aggregate` implements full precedence; 5 checks pass |
| Corroboration rule (§5.1) | ✅ | A `HEALTHY` `Finding` **cannot be constructed** without ≥2 layers incl. L2+; enforced in `__post_init__` |
| Confidence computed, never asserted (§8.2) | ✅ | `Finding.build` computes; `with_confidence` permits lowering with a reason and rejects raising |
| Failure taxonomy (§9) | ✅ | `FailureClass.from_layer`, incl. the L2 capture/persistence distinction |
| Finding structure (§10) | ✅ | Every required field present; evidence ≥1 enforced; `FAILED` requires a failure class |
| Only catalog-registered evidence admissible | ✅ | `EvidenceStore` strict mode rejects unregistered IDs and layer contradictions |
| Collector/validator separation ([Manifest §4](FRAMEWORK_MANIFEST.md)) | ✅ | `Collector.collect` returns `Evidence`; only `Validator.validate` returns `Finding` |
| No product behaviour implemented | ✅ | No log parsing, no SQLite reads of product data, no API calls, no browser automation, no agent config reads |
| Scheduling not implemented | ✅ | `scheduler.py` defines vocabulary only; `Scheduler` ABC has no implementation |
| Reporting models only, no rendering | ✅ | No HTML/PDF anywhere; `Reporter` ABC unimplemented |
| Python 3.12+, typing, dataclasses, ABCs | ✅ | `from __future__ import annotations` throughout; frozen slotted dataclasses; ABC interfaces |
| Documented public API | ✅ | Module, class, and method docstrings with Args/Returns/Raises |
| No hardcoded paths | ✅ | Paths derive from repository root or configuration; `constants.py` holds no product paths |
| Approved singletons only | ✅ | Two: `ConfigurationManager` and the logging registry, both with `reset()` for tests |

### 3.1 One derived placement decision (not an architecture change)

The brief listed "Framework Models", "Exception Hierarchy", and "Base Interfaces" as components without assigning them a package. They are implemented in **`framework/shared/`**, not `framework/core/`, because [architecture.md §3](ADS/architecture.md) permits `monitors/` and `validators/` to depend on `shared` but **not** on `core`. Since those tiers must implement the interfaces and produce the models, placing the contracts in `core` would have inverted the frozen dependency rule.

This *follows from* the frozen rules rather than altering them. `architecture.md` §2.4 and the Repository Guide have been updated to record it, per the Manifest's rule that documentation drift is a defect.

Related: the empty `framework/shared/utils.py` scaffold (0 bytes) became the `utils/` package, since one module holding nine unrelated concerns would violate the single-responsibility expectation in the Coding Standards. Same tier, same responsibility, no dependency change.

## 4. Verification Performed

| Check | Result |
|---|---|
| All modules import | 28/28 |
| Isolated import (cycle detection) | 15/15 entry points, 0 failures |
| Dependency-rule grep | 0 violations |
| Contract behaviour harness | 86/86 pass |
| `python run.py --check` | Starts successfully |
| `python run.py` (full run) | Report written; exit code 2 (`INCONCLUSIVE`) |
| Report serialisation | Round-trips to JSON with readable enum names |

The harness covers verdict precedence, corroboration enforcement, confidence computation and monotonicity, failure classification, identifier validation, evidence strictness, registry ordering/cycles/duplicates, event-bus isolation, scheduler spec validation, report aggregation, utility behaviour, and an end-to-end run including a deliberately crashing plugin.

Notably verified: **a crashed plugin yields `ERRORED` status with an `INCONCLUSIVE` verdict, never a pass**, and a run with no plugins is `INCONCLUSIVE` rather than green. Silence is not success.

The harness lives outside the repository (scratchpad) because Phase 1's brief asked for framework code, and a test suite's location/conventions are an open decision (§7, [coding_standards.md §6](ADS/coding_standards.md)).

## 5. Duplicated Functionality — Detected and Removed

| Duplication | Resolution |
|---|---|
| Two `utc_now()` implementations (`models.py`, `datetime_utils.py`) | Retained deliberately: `models` cannot import `utils` without coupling the contract layer to helpers. `models.utc_now` is the canonical one for models; `datetime_utils` serves general use. Documented in both. |
| Run timeline recorded twice — once by the orchestrator, once from event history | **Fixed.** Timeline now derives solely from orchestrator records; the raw event stream stays on the bus for subscribers. |
| `Path`/`Enum`/dataclass JSON encoding | Centralised once in `json_utils.default_encoder`. |
| Attachment serialisation appears in both section and run scope in `Report.to_dict` | Accepted: two call sites of a five-line literal; extracting a helper for it would add indirection without removing meaningful duplication. |

## 6. Defects Found in Self-Review and Fixed

1. **`Finding.UNDETERMINED` was silently becoming a dataclass field.** Annotated as `str` with a default before non-default fields, it would have broken class construction. Fixed to `ClassVar[str]`.
2. **`IntEnum` members serialised as bare integers.** `Confidence` and `EvidenceLayer` are `IntEnum` (chosen so ordering and monotonicity rules are expressible), so `json.dumps` emitted `"lowest_confidence": 0` — bypassing the custom encoder entirely, since `IntEnum` *is* an `int`. A report reading `confidence: 0` does not satisfy the §10 rule that confidence is always displayed with the verdict. Fixed with an explicit `Report.to_dict()` that owns display policy in the reporting layer: verdicts render as values, confidence as its name, layers as `L<n>`.
3. **Timeline duplication** (§5).

## 7. Remaining TODOs

| Item | Where | Blocking? |
|---|---|---|
| Extract `Finding` schema to `docs/ADS/finding_schema.md` | [Architecture Review §8.1](ARCHITECTURE_REVIEW.md) | No — semantics are now fixed in code |
| Test suite location/framework decision, then port the scratchpad harness | [coding_standards.md §6](ADS/coding_standards.md) | No, but should precede Phase 2 |
| Dependency-rule *mechanical* enforcement (currently grep-verified by hand) | [architecture.md §3](ADS/architecture.md) | No — see risk 7.1 below |
| Linter/formatter/type-checker selection and configuration | [coding_standards.md §4](ADS/coding_standards.md) | No |
| Typing discipline confirmation ("strongly typed" row) | [coding_standards.md §2.1](ADS/coding_standards.md) | No |
| Document ownership (every doc still `Owner: TODO`) | [Freeze Report §6](ARCHITECTURE_FREEZE_REPORT.md) | No |
| `milestones.md` / `backlog.md` still empty | `docs/roadmap/` | No |
| Retry/escalation policy for the framework's own failures | [error_handling_standard.md §6–§7](ADS/error_handling_standard.md) | No — `RetryPolicy` exists; the *policy choice* is open |
| Error classification/hierarchy TODOs now satisfied by code | [error_handling_standard.md §3–§4](ADS/error_handling_standard.md) | Standard should be updated to reference the implemented hierarchy |

## 8. Future Extension Points

| Extension | How | Requires core change? |
|---|---|---|
| New plugin | Implement `Plugin`, register via `PluginRegistry` (or discovery) | No |
| New evidence source | Add a row to `docs/Evidence_Catalog.md` **and** `config/framework.json` | No |
| New monitor / validator | Implement `Monitor`/`Validator` in its package | No |
| Synchronization Monitor (L3) | Implement per [its design](design/Synchronization_Monitor.md); `SynchronizationError` and `EV-007` already reserved | No |
| Scheduler implementation | Implement the `Scheduler` ABC against `ScheduleSpec`; all five kinds already modelled | No |
| Report renderer (HTML/PDF) | Implement `Reporter` consuming `Report` | No |
| Corroboration threshold tuning | `validation.minimum_corroborating_layers` in configuration, clamped to the ratified floor of 2 | No |
| New environment | Add `config/environments/<name>.json` | No |
| Event subscribers | `EventBus.subscribe`, including a wildcard handler | No |

The architecture's central claim — coverage scales by plugin count, not core change — holds in the implementation.

## 9. Risks

| Risk | Severity | Detail and mitigation |
|---|---|---|
| **9.1 Evidence Catalog drift** | **High** | The catalog now exists twice: `docs/Evidence_Catalog.md` (authoritative for humans) and `config/framework.json` `evidence.sources` (authoritative for the running framework). Nothing mechanically keeps them in step; a source added to one and not the other either blocks valid evidence or admits undocumented evidence. **Recommend a sync check** (a test comparing the two) before Phase 2 adds collectors. Documented in `config/README.md`. |
| 9.2 Unenforced dependency rules | Medium | Verified by grep during this sprint, not by tooling. Erosion is gradual and unnoticed. Should become an automated check. |
| 9.3 Confidence thresholds are untested against reality | Medium | The §8.1 boundaries were ratified before any collector existed. Deliberately configurable, so tuning needs no re-ratification — but expect adjustment after Phase 3. |
| 9.4 `AgentInfo`/`DashboardInfo` are all-optional shells | Low (by design) | Every field is optional because no product fact is verified yet. Once collectors populate them, some fields may prove mandatory — a model change, not an architecture change. |
| 9.5 No test suite in-repo | Medium | 86 checks exist but live in scratchpad, so they will not run in CI and will rot. Porting them is the highest-value early Phase 2 task. |
| 9.6 `http_utils` could be misread as sanctioning an L3 strategy | Low | Its docstring explicitly states it does not settle the [§6 observation-strategy spike](design/Synchronization_Monitor.md) and that passive observation remains the default. |
| 9.7 PyYAML absent | Low | YAML is an optional import; JSON is used throughout. A YAML file without PyYAML installed raises a clear `ConfigurationError` rather than an import failure. |

## 10. Recommendations

1. **Port the verification harness into the repository** as the first Phase 2 action, once the test-framework decision is made (risk 9.5).
2. **Add an Evidence Catalog sync check** — highest-value single guard against the sprint's most likely long-term defect (risk 9.1).
3. **Choose the toolchain** (formatter, linter, type checker) and wire the dependency-rule check into it (risk 9.2, TODO §7).
4. **Update `error_handling_standard.md` §3–§4** to reference the now-implemented hierarchy, closing two TODOs that code has answered.
5. **Assign document owners** before Phase 2 — unchanged advice from the freeze report, unchanged cost of delay.
6. Do **not** relax the strict evidence mode when collectors arrive. It will be tempting during Phase 2/3 debugging; disabling it removes the guarantee that reported evidence is traceable.

## 11. Definition of Done — Phase 1

| Criterion | Status |
|---|---|
| The framework starts successfully | ✅ `python run.py --check` |
| All packages import successfully | ✅ 28/28 |
| No circular dependencies exist | ✅ Verified in isolation |
| Every interface is reusable | ✅ 7 ABCs, extension points verified |
| Every future module can inherit from this foundation | ✅ End-to-end run with plugins built only on the public API |
| No feature-specific implementation exists | ✅ No product behaviour anywhere |

## 12. Cross References

- [Framework Manifest](FRAMEWORK_MANIFEST.md) · [Validation Standard v1.0](ADS/validation_standard.md) · [Evidence Catalog](Evidence_Catalog.md)
- [Framework Architecture Standard](ADS/architecture.md) · [Coding Standards](ADS/coding_standards.md)
- [Synchronization Monitor Design](design/Synchronization_Monitor.md)
- [Architecture Freeze Report](ARCHITECTURE_FREEZE_REPORT.md) · [Architecture Review](ARCHITECTURE_REVIEW.md)
- [Implementation Plan](roadmap/implementation_plan.md)

---
**Document Status:** Final — Phase 1 complete
**Owner:** TODO
**Last Updated:** 2026-07-30
