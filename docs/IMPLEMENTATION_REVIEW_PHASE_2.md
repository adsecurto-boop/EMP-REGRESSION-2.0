# Implementation Review — Phase 2: Environment & Agent Validation

## 1. Summary

Phase 2 delivers **EM000_EnvironmentValidator**, the first real EmpMonitor plugin and the mandatory pre-check for every regression run. It answers the sprint's question — *is this Windows machine correctly prepared to execute EmpMonitor regression testing?* — from local evidence only, with no dashboard automation and no business API calls.

Run against a real installation on this host, it collected **23 pieces of evidence across Layers 1 and 2** and produced **8 findings**, six of them corroborated across both layers.

**No architectural change was required.** Two framework *defects* were found by real integration and fixed (§6); the gating requirement was met using an existing extension point with zero framework change (§4).

The most consequential outcome is not the code: EmpMonitor turned out to be installed on this machine, so facts that were `Hypothesis` are now **`Verified`** — and two of the brief's own assumptions were **corrected** by observation (§3).

Verification: **75 new checks pass**, and the Phase 1 and 1.5 harnesses still pass (86 and 162), for **323 green** overall.

## 2. What Was Built

| Component | Location | Role |
|---|---|---|
| Product profile reader | `framework/shared/profile.py` | Typed access to the configured product facts, with the `verified` flag that governs verdict severity |
| Host OS helper | `framework/shared/utils/windows.py` | Generic service/process/OS/clock/registry/signature inspection. No product knowledge |
| Configuration collector + validator | `framework/validators/configuration.py` | EV-001, EV-002, EV-016. Redacts secrets before evidence exists |
| Environment collector + validator | `framework/validators/environment.py` | EV-012, EV-014, EV-015. OS, network, clock |
| Runtime validator | `framework/validators/runtime.py` | Pairs L1 intent with L2 reality to earn corroboration |
| Filesystem collector | `framework/monitors/folder_monitor.py` | EV-010. Roots, folders, permissions, disk |
| Executable collector | `framework/monitors/executable_monitor.py` | EV-013. Path, hash, size, version, signature |
| Service + process collectors | `framework/monitors/runtime_monitor.py` | EV-005, EV-011 |
| SQLite collector | `framework/monitors/sqlite_monitor.py` | EV-003. Structure only, never contents |
| EM000 plugin | `plugins/EM000_EnvironmentValidator/plugin.py` | Composes the pipeline; asserts no verdict itself |
| Environment gate | `plugins/EM000_EnvironmentValidator/gate.py` | Blocks downstream plugins on a negative pre-check |
| Report summaries | `plugins/EM000_EnvironmentValidator/summary.py` | Environment / installation / configuration / runtime, warnings, failures, recommendations |
| Product profile config | `config/framework.json` (`empmonitor`) | Every product fact, with per-item `verified` flags |

Five new evidence sources were registered in both the [Evidence Catalog](Evidence_Catalog.md) and its config mirror: EV-012 (OS), EV-013 (executable metadata), EV-014 (network), EV-015 (clock), EV-016 (registry).

## 3. Product Knowledge: Hypothesis → Verified

EmpMonitor is installed and running on this host, so the pre-check verified facts rather than assuming them. Full detail is recorded in the knowledge base (RE-005, RE-006, RE-007, RE-008, RE-009, RE-010, RE-012, and HB-005).

**Two of the brief's assumptions were corrected by observation:**

| Brief stated | Actually observed |
|---|---|
| Install root `C:\Program Files\EmpMonitor` | `C:\Program Files\EmpMonitor\EmpMonitor` — **double-nested** |
| `ffmpeg.exe` OR `esr.exe` | Only `esr.exe` exists. ffmpeg ships as DLLs (`avcodec-61.dll`, `avformat-61.dll`, …), never as `ffmpeg.exe` |

**Verified this run:** agent `empmonitor.exe` 3.7.4, `emp_psa_service.exe` **3.7.3** (a version skew worth noting), `esr.exe`, plus previously undocumented `UpdateMgr_Emp.exe` and `EmailMonitorSvc.exe` — all five Authenticode **Valid**, all SHA-256 hashed. Service `BrowserHandlingService` RUNNING, AUTO_START, recovery actions configured. Data root `%APPDATA%\screen`, `empm.ini` with three sections, `config.js` at `gui/configs/`, log folder at `%APPDATA%\screen\empm\logs`, and a **28-table** SQLite database (9 populated).

**Two long-standing open questions moved forward:**

1. **Where upload-queue state lives** (RE-004, RE-012, and the Synchronization Monitor design §10 all flagged this). The database contains six `pending_*` tables — `pending_screenshots6`, `pending_usagedata6`, `pending_usbdata6`, `pending_clipboardata`, `pending_aduserproperties6`, `pending_bluetoothdata`. Recorded **Partially Verified**: the tables demonstrably exist, but that they *function* as the upload queue is inference, not observation.
2. **Whether a WebSocket channel exists** (RE-006, and Sync Monitor design §12 treated it as conditional). `config.js` carries `wss://` endpoints. Recorded **Partially Verified** for the same reason — configuration evidences the channel, its use has not been observed.

Both are exactly the kind of fact the Layer 3 collector will need, and both arrived as a by-product of a Layer 1/2 pre-check.

## 4. The Gating Requirement — Solved Without Framework Change

The brief requires that a failed pre-check causes later plugins to be *skipped or blocked*. A dependency declaration alone does **not** achieve this, and the distinction matters:

> The execution graph blocks dependents when a unit **fails to execute**. But EM000 executing correctly and concluding "the environment is broken" is a **successful** run producing a negative result — so the graph would happily let dependents proceed.

Dependency ordering answers *did it run?*; gating needs *what did it conclude?*. Both are therefore used together: `depends_on=("EM000_EnvironmentValidator",)` guarantees order, and `EnvironmentGate` consults the verdict via the **`BEFORE_PLUGIN` hook veto built in Phase 1.5**. Zero framework change.

Verified end to end: a `FAILED` pre-check skips downstream plugins with the reason recorded; a `HEALTHY` one lets them run; and a pre-check that **crashes** also closes the gate, because a crashed pre-check has established nothing about the environment. Skipped plugins carry an `INCONCLUSIVE` verdict, so a gated run can never read as a pass.

## 5. The Design Decision That Matters Most

**An unmet expectation whose name is unverified reports `INCONCLUSIVE`, never `FAILED`.**

Each expectation in the product profile carries a `verified` flag, and `Expectation.unmet_verdict` turns it into a verdict. This is the knowledge base's verification model reaching into runtime behaviour, and this run demonstrates exactly why it is right:

The "failed screenshots" and "failed recordings" folders named in the brief **do not exist** on this machine, and their real names were never observed. Reporting `FAILED` would have been wrong twice over — the framework doesn't know what the folders are called, *and* for folders that hold failed uploads, absence most plausibly means **nothing has failed**, which is healthy. So the run reports two open questions and tells the operator how to close them:

> *2 check(s) were inconclusive because the expected name or location is unverified. Supply the confirmed names in `config/framework.json` 'empmonitor' and set `verified:true` so absence becomes a real failure rather than an open question.*

The overall verdict is therefore `INCONCLUSIVE`: six checks passed, none failed, two questions remain. Per the ratified precedence an `INCONCLUSIVE` finding cannot be masked by healthy ones, and the plain-language answer says so — *"the environment is not certified as prepared"*. That is the honest answer, and it is more useful than a green tick would have been.

## 6. Defects Found and Fixed

All three were found by running against a real machine, not by inspection.

1. **Plugin discovery could not discover plugins.** `registry.discover` required `candidate.__module__ == module_name`, but a plugin organised as a subpackage — `plugins/EM000_Name/plugin.py`, the repository's own canonical layout — defines its class in a submodule. Discovery silently returned zero plugins. Now accepts classes defined in the module *or its submodules*, which still excludes classes merely imported from elsewhere.
2. **Reports could cite evidence that appeared nowhere in them.** Findings produced inside a plugin cite evidence the plugin collected, but that evidence never reached the run's store, so the report's `evidence` list was empty while its findings cited `EV-002`, `EV-003`, … — breaking the rule that citations must resolve ([Validation Standard §10 rule 5](ADS/validation_standard.md)). The aggregator now also harvests evidence from findings.
3. **The gate never closed on a crash.** `plugin.failed` events carried `unit_id` but not `plugin_id`, while `plugin.started`/`plugin.completed` carried `plugin_id` — so a subscriber could not identify which plugin failed, and anything gating on failure silently never fired. Terminal plugin events now carry both.

Two quality defects in my own new code were also fixed: recommendation advice was keyed by component *prefix*, so a folder-name gap produced "check the database is not locked" — advice pointing at the wrong thing; and the `INCONCLUSIVE` answer said only "cannot tell" without saying that six checks had in fact passed.

## 7. Architecture Compliance

| Requirement | Status |
|---|---|
| Uses the Phase 1/1.5 framework; does not bypass the validation engine | ✅ Plugin composes collectors/validators; all verdicts come from `ValidationEngine` |
| Every observation becomes Evidence; every Evidence feeds Findings; every Finding carries a Verdict | ✅ 23 evidence → 8 findings → verdicts, all with confidence and layer |
| No PASS/FAIL without evidence | ✅ Enforced by `Finding`'s constructor; verified for every finding |
| Corroboration rule (§5.1) genuinely satisfied | ✅ All 6 healthy findings span L1+L2 with an L2+ member |
| No hardcoded product paths or names | ✅ Every product fact is configuration; `constants.py` remains product-free |
| Collector/validator separation | ✅ Collectors return only `Evidence`; only validators return `Finding` |
| Dependency rules | ✅ No framework module imports `plugins`; discovery is runtime-only |
| Secrets never recorded | ✅ `auth/crypto_password` redacted before evidence construction; verified absent from report and evidence |
| Scope limits (no dashboard, screenshots, recordings, reports, business APIs) | ✅ None present |
| Database contents not read | ✅ Table names and row counts only, opened read-only |
| Plugin conformance (multi-layer, registered, lifecycle) | ✅ Declares L1+L2; auto-discovered; participates in all stages |

## 8. Extension Point Review

Nothing about EM000 required a new seam. It uses: plugin discovery, the evidence pipeline (7 collectors, 3 validators), `Collector`/`Validator` interfaces, the `BEFORE_PLUGIN` hook veto, `PLUGIN_COMPLETED`/`PLUGIN_FAILED` events, `ValidationEngine`, `ExecutionResult.metadata`, and the configuration system. A second plugin needs none of it changed.

The `verified`-flag pattern is reusable by any future plugin: declare an expectation, and severity follows the knowledge base's confidence in the underlying fact.

## 9. Remaining TODOs and Risks

| Item | Severity | Detail |
|---|---|---|
| **Supply the failed-screenshot / failed-recording folder names** | **High** | These are the only two open questions in the pre-check. Until supplied, the environment cannot be certified. Requires someone to trigger an upload failure and observe where the agent writes it. |
| Test harnesses still in scratchpad | **High** | 323 checks now exist across three harnesses and none run in CI. Unchanged advice from Phase 1; the cost of delay is now three times larger. |
| Evidence Catalog drift | Medium | Now 16 sources duplicated between doc and config. A sync check remains unwritten and is now more valuable than when first flagged. |
| Plugin-collected evidence reaches the report via findings and the summary, not the top-level evidence list | Low | `ValidationContext` deliberately carries evidence, not the store, so a plugin cannot record into the run store. Nothing is lost (all 23 items appear in the summary), but the report's evidence list holds only cited items. |
| `esr.exe` version resource unreadable | Low | Recorded as `None` rather than guessed. Recorder version is therefore unknown. |
| Service/gui version skew (3.7.3 vs 3.7.4) | Low — worth watching | Observed, recorded, not judged: no expectation exists yet that they must match. |
| `w32tm` dependency for clock drift | Low | Drift is `None` where the tool or time source is unavailable, and reported as an open question rather than a pass. |
| PowerShell used for process/service/signature detail | Low | Each call degrades to `None` or a `tasklist` fallback. Documented as host inspection, not product automation. |

## 10. Definition of Done

| Criterion | Status |
|---|---|
| Plugin registration | ✅ Auto-discovered as `EM000_EnvironmentValidator` |
| Lifecycle participation | ✅ Applicability gate, precheck, execute, postcheck, cleanup |
| Evidence generation | ✅ 23 items across 8 sources, L1 and L2 |
| Validation engine integration | ✅ All verdicts and confidence computed by the engine |
| Report generation | ✅ Every section the brief requires |
| Extension compliance | ✅ No new seam required |
| Architecture compliance | ✅ §7 |
| Answers the sprint question without touching the dashboard | ✅ Local evidence only |
| Mandatory pre-check for future plugins | ✅ Dependency + gate, verified in three scenarios |

## 11. Cross References

- [Validation Standard v1.0](ADS/validation_standard.md) · [Evidence Catalog](Evidence_Catalog.md) · [Framework Manifest](FRAMEWORK_MANIFEST.md)
- [Knowledge Base](../knowledge_base/README.md) — verification model and the newly verified facts
- [Plugin Development Guide](ADS/plugin_standard.md) · [Synchronization Monitor Design](design/Synchronization_Monitor.md)
- [Phase 1 Review](IMPLEMENTATION_REVIEW.md) · [Phase 1.5 Review](IMPLEMENTATION_REVIEW_PHASE_1_5.md)

---
**Document Status:** Final — Phase 2 complete
**Owner:** TODO
**Last Updated:** 2026-07-30
