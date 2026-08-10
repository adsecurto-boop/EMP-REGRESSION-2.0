# Architecture Review — Phase 4

Assesses Phase 4 against the frozen architecture, with the duplication and drift checks the sprint required. **Verdict: compliant, with one pre-existing defect surfaced and resolved (§5).**

## 1. Required Checks

| Check | Result | Evidence |
|---|---|---|
| No duplicated validators | ✅ | 20 validator classes, each answering a distinct question; the one overlap found was removed (§3) |
| No duplicated collectors | ✅ | 11 collector classes, one per artifact. Feature plugins reuse them; none was cloned |
| No duplicated evidence | ✅ | 17 catalog sources, no new source added this phase — the reuse register (§2) made new ones unnecessary |
| No duplicated profiles | ✅ | 14 feature profiles, unique ids, loaded through one registry |
| No duplicated page definitions | ✅ | 17 pages defined once in the navigation model; page specs reference identifiers rather than restating them |
| No architecture drift | ✅ | §4 |
| No dependency violations | ✅ | `shared` imports nothing above it; no framework module imports `plugins` |
| No circular imports | ✅ | Every module imports in isolation |

## 2. Reuse Instead of Rebuild

The sprint asked for "reusable collectors" and "reusable validators". Phases 2–3 had already built most of them, and Task 10 forbids duplication — so the work was **an audit and a reuse register**, not a second implementation.

| Asked for | Outcome |
|---|---|
| Configuration Snapshot Collector | **Existed** — `ConfigurationCollector` |
| Runtime Snapshot Collector | **Existed** — `ProcessCollector`, `ServiceCollector`, `ExecutableCollector` |
| SQLite Snapshot Collector | **Existed** — `SqliteCollector` |
| Log Snapshot Collector | **Existed** — `SyncLogCollector` |
| Synchronization Snapshot Collector | **Existed** — `SyncQueueCollector`, `AgentNetworkCollector` |
| Dashboard Snapshot Interface | **Built** — interface only, no implementation |
| Configuration / Runtime / Upload / Queue Validators | **Existed** — Phases 2–3 |
| Timestamp / Frequency / Correlation Validators | **Built** — genuine gaps |
| Dashboard Validator Interface | **Built** — negative case only |

Six of nine collectors and four of eight validators already existed. Building them again would have created the exact defect Task 10 asks to prevent: **two collectors reading one artifact produce evidence that looks independent, inflating apparent corroboration and, through the confidence calculation, overstating confidence** ([Validation Standard §4.1](ADS/validation_standard.md)).

Recorded permanently in [Feature Validation Standard §6](ADS/feature_validation_standard.md), so the next phase does not rediscover it.

## 3. A Duplicate Found and Removed

Phase 3's `SchedulerValidator` computed cadence inline. Phase 4 needed the same arithmetic for feature intervals.

Writing a second copy would have left the framework with two implementations of "every 180 seconds", free to disagree — and a framework whose two answers differ has no answer. Instead `analyse_cadence` in `framework/core/correlation.py` is now the single implementation, and `SchedulerValidator` was refactored to delegate to it.

Verified: one definition, one call site for the arithmetic, and the Phase 3 harness still passes.

## 4. No Architecture Drift

| Frozen contract | Status |
|---|---|
| Evidence model | Unchanged — no source added, no layer redefined |
| Validation Standard | Unchanged — Phase 4 *extends* it via a subordinate standard that explicitly defers to it |
| Plugin contract | Unchanged — `FeatureValidationPlugin` implements the existing `Plugin` ABC; nothing in `shared/interfaces.py` was touched |
| Dependency direction | Unchanged — see §4.1 |
| Collector/validator separation | Reinforced — the correlation engine returns correlations, never verdicts |

### 4.1 A placement decision that avoided drift

`FeatureValidationPlugin` composes `core`, `monitors`, and `validators`. The dependency rules permit that combination **for plugins**; a framework module doing it would create a new tier and be drift.

It therefore lives in `plugins/base.py`, not in `framework/`. The frozen direction is intact, and the base class still has access to everything it needs.

## 5. Defect Surfaced: A Plugin ID Collision I Introduced

**The naming convention states that plugin numbers are never reused.** Phase 3 broke that rule and it went unnoticed until this phase's audit.

| Identifier | Allocated to | Status |
|---|---|---|
| `EM001` | `EM001_Login` (original scaffold) | Never implemented — empty directory |
| `EM001` | `EM001_Synchronization` (Phase 3) | **Implemented and working** |

Two plugins hold one number. My error, in Phase 3, when I chose `EM001` for the synchronization validator without checking the catalog.

**Resolution.** `EM001` stays with `EM001_Synchronization`: it is implemented, working, referenced by four documents and every knowledge-base promotion, and renaming it would invalidate all of that to preserve a scaffold that has never contained code. `EM001_Login` is **retired unimplemented** and its number is *not* reissued — consistent with the rule that a retired number is burned.

**Consequence.** Feature plugins start at **EM010**, leaving EM002–EM009 unallocated as a deliberate gap. That gap is the record of this mistake, and it is cheaper than a renumbering.

**What this says about the process.** The naming convention has no numbering authority — flagged as an open item since the first Architecture Review (7.1) and still unassigned. This is the first real collision it caused. It will not be the last while the gap remains.

## 6. Layer 4 Is Now Explicit Rather Than Absent

Before this phase, Layer 4 was simply missing from every report. Now:

- `UnavailableDashboardCollector` **emits evidence of its own absence**, so the gap appears in reports as an open question instead of as silence;
- Layer 4 correlations return `INDETERMINATE` with the reason;
- `FeatureProfile.observable_layers` excludes L4, so no plugin can declare a layer it cannot observe;
- feature reports carry `layers_not_observable`.

The framework is no worse informed than before — it is now *honest about* being no better informed. The consequence is stated in [Feature Validation Standard §5](ADS/feature_validation_standard.md): a synchronization defect and a surfacing defect remain indistinguishable.

## 7. The Dashboard Documents Are Deliberately Unverified

17 pages and their elements are specified, and **not one has been observed**. Both documents open with a prominent warning, every entry is `Hypothesis`, and no selector appears anywhere.

This was the phase's largest temptation. A confident-looking dashboard model would have been quick, plausible, and impossible for a future reader to distinguish from observation — and assertions would then have been built on invention. The specifications are written as **checklists of questions for whoever first opens the dashboard**, with `monitoring_control` and `storage` flagged as the highest-value pages because each would close a defect class the framework currently cannot see at all.

## 8. Residual Risks

| Risk | Severity | Note |
|---|---|---|
| Reviewer role still unassigned | **High** | No knowledge promotion can complete. The knowledge base cannot advance past `Partially Verified` regardless of evidence. Unchanged across three phases and now blocking 14 feature profiles as well. |
| Harnesses still outside CI | **High** | 395 checks, four phases of debt |
| Log evidence is not durable | **High** | The agent was observed **emptying its own log directory** mid-session. Log-derived validation can lose its entire evidence base without warning. The framework degraded correctly, but the fragility is inherent |
| No numbering authority | Medium | Caused §5. Will recur |
| Dashboard page identifiers have no drift check | Medium | `config/features.json` references page ids with nothing enforcing they exist, unlike the Evidence Catalog which now has a checker |
| 5 of 14 features are `Hypothesis` | Medium (expected) | No artifact identified for keystrokes, webcam, face detection, productivity, timesheet. Those plugins must reverse-engineer before validating |
| L4 unavailable | Medium | Blocks every end-to-end feature verdict |

## 9. Recommendation

Phase 4's infrastructure is sound and duplication-free. Before feature implementation begins, two things should be settled:

1. **Assign the reviewer role.** It has been open since the Architecture Review and now blocks fourteen profiles as well as every synchronization promotion. It is a five-minute decision holding back the framework's central purpose.
2. **Port the harnesses into CI.** Four phases of test debt, and Phase 4 added infrastructure whose correctness is only checked by hand.

Neither blocks starting Phase 5, but both compound.

## 10. Cross References

- [Feature Validation Standard](ADS/feature_validation_standard.md) · [Feature Profiles](Feature_Profiles.md)
- [Dashboard Navigation](design/Dashboard_Navigation.md) · [Dashboard Page Specifications](design/Dashboard_Page_Specifications.md)
- [Phase 4 Review](IMPLEMENTATION_REVIEW_PHASE_4.md) · [Phase 3 Compliance Report](Architecture_Compliance_Report.md)
- [Framework Manifest](FRAMEWORK_MANIFEST.md) · [Validation Standard v1.0](ADS/validation_standard.md)

---
**Document Status:** Final — Phase 4
**Owner:** TODO
**Last Updated:** 2026-07-30
