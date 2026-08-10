# Implementation Review — Phase 4: Feature Validation Foundation

## 1. Summary

Phase 4 builds the infrastructure every future feature plugin will use: a base plugin, 14 feature profiles, a cross-layer correlation engine, three generic validators, the Layer 4 contract, 14 inert plugin templates, and the dashboard model.

**No architecture was changed.** The Evidence Model, Validation Standard, and Plugin Contract are untouched; Phase 4 extends them through a subordinate standard that explicitly defers to the ratified one.

The phase's defining decision was **not to build what already existed**. Six of nine requested collectors and four of eight requested validators were already in the framework, and rebuilding them would have created the precise defect the sprint's own review task forbids. The work became an audit, a reuse register, and the removal of one duplicate that had already crept in.

Three real defects were caught: **all 14 templates would have executed in every regression run** (§4.1), a **mis-escaped configuration key that could never match** (§4.3), and a **plugin ID collision I introduced in Phase 3** (§4.4).

Verification: **395 checks pass** across four harnesses; no duplication, no dependency violations, no cycles, no catalog drift.

## 2. What Was Built

| Deliverable | Location | Note |
|---|---|---|
| Feature Validation Standard | `docs/ADS/feature_validation_standard.md` | Extends the ratified standard; does not amend it |
| Feature Validation Base Plugin | `plugins/base.py` | Abstract, so discovery skips it |
| 14 Feature Profiles | `config/features.json` + `docs/Feature_Profiles.md` | 1 Verified, 8 Partially Verified, 5 Hypothesis |
| Profile reader | `framework/shared/features.py` | `absence_verdict` encodes the status→severity rule |
| Correlation Engine | `framework/core/correlation.py` | 5 cross-layer questions; returns correlations, never verdicts |
| Generic Validators | `framework/validators/generic.py` | Timestamp, Frequency, Correlation |
| Dashboard contract | `framework/validators/dashboard.py` | Interfaces only; no browser code |
| Evidence sufficiency | `framework/validators/evidence.py` | Validates the *run's* coverage, not the product |
| 14 Plugin Templates | `plugins/EM010_*` … `EM023_*` | Abstract and inert |
| Template generator | `scripts/new_feature_plugin.py` | One generator instead of 14 files free to drift |
| Profile integrity check | `scripts/check_feature_profiles.py` | Catches mis-escaped keys and dangling references (§4.3) |
| Dashboard Navigation | `docs/design/Dashboard_Navigation.md` | 17 pages, all `Hypothesis` |
| Dashboard Page Specs | `docs/design/Dashboard_Page_Specifications.md` | 0 elements confirmed |
| Architecture Review | `docs/ARCHITECTURE_REVIEW_PHASE_4.md` | Task 10 checks |

The last two empty scaffolds in `framework/validators/` are now filled, leaving only `log_monitor.py` and `scheduler_monitor.py` — both superseded in practice by `sync_monitor.py` and left for a phase that needs them.

## 3. The Decisions That Shaped the Phase

**Reuse over rebuild.** The reuse register in [Feature Validation Standard §6](ADS/feature_validation_standard.md) is the phase's most durable artifact: it tells the next engineer what already exists and why writing a second one is harmful, not merely wasteful. Two collectors reading one artifact produce evidence that *looks* independent, inflating corroboration and overstating confidence.

**One cadence implementation.** Phase 3 computed cadence inside `SchedulerValidator`; Phase 4 needed the same maths for feature intervals. Rather than copy it, `analyse_cadence` became the single implementation and `SchedulerValidator` now delegates. Two implementations of "every 180 seconds" are free to disagree.

**Absence is not failure.** `FeatureProfile.absence_verdict` makes a feature's verification status govern what its plugin may report. Only a `Verified` feature can report `FAILED` for a missing artifact — exactly one feature qualifies today. `pending_screenshots6` being empty is not evidence that screenshots are broken.

**A generator, not 14 files.** Fourteen hand-written templates would be fourteen near-identical files free to drift, in a sprint that forbids duplication. One generator keeps the shape in one place.

**Layer 4 absence made explicit.** `UnavailableDashboardCollector` emits evidence of its own absence, so the gap appears in reports as an open question rather than as silence. The framework is no better informed than before — it is now honest about that.

## 4. Defects Found and Fixed

### 4.1 Every template would have run in every regression

The first generator produced templates whose `feature_summary` *raised* `NotImplementedError`. Defining the method satisfies the ABC, so the class was **concrete** — discovery would have registered all 14 and executed them, reporting on features nobody had implemented.

Fixed by re-declaring the override `@abstractmethod`, which keeps the subclass abstract while still carrying the implementation guidance. Verified: `inspect.isabstract` is true for all 14, and a real run registers exactly 2 plugins.

This is the defect I was specifically guarding against, and my first attempt at the guard is what introduced it.

### 4.2 Generated docstrings emitted syntax warnings

Real configuration keys contain backslashes (`from_remote\screenshotPeriodSec`), which became invalid escape sequences in generated docstrings. The generator now escapes them.

### 4.3 A mis-escaped configuration key that could never match

`EM013_Attendance` profiled its key as `settings/data\trackingMode` with a single
backslash. In JSON that is a **TAB**, so the parsed key was
`settings/data<TAB>rackingMode` and could never match the real INI key — configuration
checking for Attendance and Idle Time would have been silently dead forever.

It slipped through for a specific reason: the two neighbouring keys used `\s` and `\A`,
which are *invalid* escapes and produced warnings that made me look at them. `\t` is a
*valid* escape, so nothing warned. The one that was safe to write is the one that broke.

Fixed, and guarded: `scripts/check_feature_profiles.py` now rejects any control
character in a profiled key and names the escape that caused it. It also catches
dangling evidence and dashboard-page references. Verified against the real config and
against a deliberately corrupted key.

Found by the knowledge-base agent auditing my work, not by me.

### 4.4 A plugin ID collision I introduced in Phase 3

The naming convention says plugin numbers are never reused. Phase 3 assigned `EM001` to `EM001_Synchronization` while the catalog already allocated `EM001` to the (never implemented) `EM001_Login` scaffold. My error, unnoticed until this phase's audit.

Resolved in [Architecture Review §5](ARCHITECTURE_REVIEW_PHASE_4.md): `EM001` stays with the working plugin, `EM001_Login` is retired without reissuing its number, and feature plugins start at **EM010**. EM002–EM009 remain a deliberate gap — the permanent record of the mistake, and cheaper than renumbering four documents and every promotion record.

Root cause: the naming convention still has **no numbering authority**, open since the first Architecture Review.

## 5. What the Environment Taught Us Mid-Phase

Two things happened to the live agent during this phase, neither triggered by the framework:

**The agent emptied its own log directory.** Every Layer 3 log-derived assertion lost its evidence base. The framework responded correctly: all eight synchronization health areas became `INCONCLUSIVE`, zero `FAILED` findings were produced, and all promotions dropped to `Hypothesis`. It refused to invent a failure when its evidence vanished.

**A user logged out**, removing the `[auth]` section from `empm.ini`. EM000 caught it immediately and reported a `CONFIGURATION_DEFECT`.

Both are stronger evidence of the framework's honesty than any test could be, because neither was arranged. They also produced two useful side effects: three previously unrecorded configuration keys were discovered (`settings/data\trackingMode`, `appSettings/todayRemainingBreakInSeconds`, `appSettings/currentDate`) and fed straight into the Attendance and Idle Time profiles; and the log wipe elevated **log-evidence durability** from a theoretical risk to an observed one.

It also exposed a test-design flaw: three harnesses asserted things that depend on the product's *state*. A harness observing a live product must separate "the code is wrong" from "the product changed". They now assert the contract conditionally — including the degradation path, which is a stronger test than the original.

## 6. Verification

| Harness | Result |
|---|---|
| Phase 1 | 86 / 86 |
| Phase 1.5 | 162 / 162 |
| Phase 2 | 73 / 73 |
| Phase 3 | 74 / 74 |
| **Total** | **395 / 395** |

Plus, for Phase 4 specifically: 14 profiles load with correct status→severity mapping; `absence_verdict` returns `FAILED` only for the one `Verified` feature; the correlation engine's tolerant comparison and `INDETERMINATE` dashboard path behave correctly; cadence analysis returns 180 s mean with 0 s drift; all 14 templates are abstract; a real run registers exactly 2 plugins; and the Evidence Catalog drift check passes on 17 sources.

## 7. Remaining TODOs and Risks

| Item | Severity | Note |
|---|---|---|
| **Reviewer role unassigned** | **High** | Now blocks 14 feature profiles as well as every synchronization promotion. Open since the first Architecture Review. A five-minute decision holding back the framework's central purpose |
| **395 checks outside CI** | **High** | Four phases of debt; Phase 4 added infrastructure verified only by hand |
| **Log evidence is not durable** | **High** | Observed, not theorised: the agent wipes its own logs |
| ~~Dashboard page ids have no drift check~~ | Resolved | `scripts/check_feature_profiles.py` now validates page and evidence references |
| No numbering authority | Medium | Caused §4.3 |
| 5 of 14 features are `Hypothesis` | Medium (expected) | Must reverse-engineer before validating |
| L4 unavailable | Medium | No feature can be validated end to end; sync and surfacing defects indistinguishable |
| `log_monitor.py`, `scheduler_monitor.py` still empty | Low | Superseded in practice by `sync_monitor.py` |

## 8. Definition of Done

| Deliverable | Status |
|---|---|
| Feature Validation Standard | ✅ |
| Feature Profiles (14) | ✅ 1 Verified, 8 Partially Verified, 5 Hypothesis |
| Dashboard Navigation Specification | ✅ 17 pages, all `Hypothesis` |
| Dashboard Page Specifications | ✅ 0 elements confirmed, no selectors invented |
| Generic Validators | ✅ 3 built; existing ones reused |
| Generic Collectors | ✅ Dashboard interface built; 6 existing reused |
| Correlation Engine | ✅ 5 questions, returns correlations never verdicts |
| Plugin Templates | ✅ 14, all inert |
| Updated Knowledge Base | ✅ HB-006 rewritten for 14 features; RE-005/007/008 updated |
| Architecture Review | ✅ |
| Phase 4 Review | ✅ This document |
| **No Playwright / Selenium / UI automation / dashboard tests / screenshot or recording validation** | ✅ None present |

## 9. Cross References

- [Feature Validation Standard](ADS/feature_validation_standard.md) · [Feature Profiles](Feature_Profiles.md)
- [Architecture Review — Phase 4](ARCHITECTURE_REVIEW_PHASE_4.md)
- [Dashboard Navigation](design/Dashboard_Navigation.md) · [Dashboard Page Specifications](design/Dashboard_Page_Specifications.md)
- [Phase 1](IMPLEMENTATION_REVIEW.md) · [Phase 1.5](IMPLEMENTATION_REVIEW_PHASE_1_5.md) · [Phase 2](IMPLEMENTATION_REVIEW_PHASE_2.md) · [Phase 3](IMPLEMENTATION_REVIEW_PHASE_3.md)

---
**Document Status:** Final — Phase 4 complete
**Owner:** TODO
**Last Updated:** 2026-07-30
