# Architecture Compliance Report — Phase 3

Assesses Phase 3 against the frozen architecture. **Verdict: compliant.** No architectural contract was changed. Two implementation defects were fixed, one of which closed a gap between the ratified standard and the code, and one long-standing structural gap was closed by resolving a deferred decision.

## 1. Frozen Contracts

| Contract | Status | Evidence |
|---|---|---|
| Dependency direction (`plugins → core → shared`) | ✅ | No framework module imports `plugins`; verified by grep |
| Collectors collect, validators conclude | ✅ | The three sync collectors return only `Evidence`; only validators return `Finding` |
| One artifact, one collector (§4.1) | ✅ | See §3 — the one shared artifact is declared in evidence |
| Verdict model unchanged | ✅ | No verdict added or redefined |
| Corroboration rules unchanged | ✅ | Enforcement *extended* to match the standard — see §4.1 |
| Confidence computed, never asserted | ✅ | Every sync finding uses `Finding.build` |
| Failure taxonomy unchanged | ✅ | `SYNCHRONIZATION_DEFECT` applied where L3 diverges |
| No hardcoded URLs, table names, or log messages | ✅ | See §2 |
| Passive observation only (Manifest §14) | ✅ | See §5 |
| Secrets never recorded | ✅ | See §6 |
| Evidence Catalog is authoritative | ✅ | Drift found, closed, and now mechanically enforced — §7 |

## 2. The Brief's Hardcoding Prohibitions

| Rule | How it is honoured | Verified by |
|---|---|---|
| Never hardcode URLs | Endpoints are **discovered** from configuration and from log lines at runtime. No product host appears in any source file | Test asserts `empmonitor.com` and `track.` appear nowhere in the collector source |
| Never hardcode table names | Queue tables are **discovered** from the database by a configured *prefix* (`pending_`). Six were found without any being named in code | Test asserts no specific table name appears in source |
| Never hardcode log messages | All 14 log patterns are **configured regexes**. The collector holds no product log text | Test asserts no observed log phrasing appears in source |
| Discover whenever possible | Endpoints, table names, log files, and API names are all discovered | §3 of the architecture report |
| Configuration overrides observation | Patterns, prefixes, thresholds, and locations all come from configuration | By construction |
| Observation overrides assumptions | Two of the brief's own assumptions were corrected by observation in Phase 2; the design's fidelity estimate was corrected in Phase 3 | Architecture report §3 |
| Evidence overrides documentation | The design ranked log-derived lowest; measurement promoted it to primary, and the design document was updated to match | `design/Synchronization_Monitor.md` §6 |

The last row is worth dwelling on: the framework's own design document was **wrong**, evidence showed it was wrong, and the document was corrected rather than the evidence being made to fit it.

## 3. The Independence Rule — A Real Case

`SyncQueueCollector` reads the **same database file** as `SqliteCollector`. Under §4.1 two readings of one artifact do not independently corroborate each other, however different their identifiers.

Rather than leave that implicit, the queue collector records `"shares_artifact_with": "EV-003"` in its evidence, and the evidence graph surfaces it with an explicit note. A validator or reader can therefore *see* that EV-007-from-queue and EV-003 are not independent supports.

This is the rule working as intended in a case where it would have been easy to accidentally double-count.

## 4. Defects Fixed

### 4.1 The model under-enforced the ratified standard

`Finding` enforced corroboration for `HEALTHY` but **not** for `DEGRADED`. The Validation Standard §5.4 sets the same minimum for both — `DEGRADED` is a positive conclusion ("functioning, with anomalies") and needs the same support.

The gap left the easier positive verdict as an unguarded route to an under-corroborated claim. Enforcement now covers both. This **aligns the code with the frozen contract** rather than changing it, which is why it is a defect fix and not an amendment.

### 4.2 Validators crashed instead of reporting when corroboration was absent

A validator building a positive finding cannot know in advance whether the corroborating layers were collected — a collector may have failed, or the plugin may run in isolation. Without a guard, a missing layer became a `ValidationError` rather than an `INCONCLUSIVE` finding.

All eight sync validators now route positive verdicts through `_positive_verdict`, which downgrades to `INCONCLUSIVE` with a recorded reason. This is the difference between a validator that reports honestly and one that falls over.

### 4.3 Promotions carried no agent version

The verification workflow requires `Verified Against Version` on every promoted claim. EM001's pipeline did not observe the executable, so every record had `None`. A claim without a version is not reviewable — nobody can tell what it applies to. `ExecutableCollector` was added to the pipeline for exactly this reason.

## 5. Passive Observation Upheld

| Requirement | How |
|---|---|
| No request issued to the product's server | The network collector reads the host connection table; it opens no socket |
| No product artifact modified | Logs and the database are opened **read-only** |
| No interception | Proxy interception formally rejected; the spike showed it is also unnecessary |
| Offline behaviour not induced | `RecoveryValidator` reports `INCONCLUSIVE` and states that verifying it would require perturbing the system, which is out of remit |

That last one is the clearest test of the principle. It would have been easy to disconnect the network, verify offline queueing, and claim the coverage. The framework declines, says why, and leaves the question open.

## 6. Secret and Content Safety

The agent's log contains captured monitoring data — mail subjects, clipboard text. Two independent controls apply:

1. **Only configured patterns are read.** Unrecognised log content never enters evidence, so captured activity is excluded by construction rather than by filtering.
2. **A field-name backstop.** Any capture group whose *name* suggests content (`subj`, `body`, `mail`, `clip`, `token`, `password`, `email`) is replaced with an elision marker before evidence is built — protecting against a future pattern author capturing something they should not.

Verified: no credential value, mail subject, endpoint URL, or tenant token appears in the report, evidence, or any document produced this phase.

## 7. Evidence Catalog Drift — Predicted, Occurred, Now Controlled

This risk was recorded as the highest-severity long-term defect in Phase 1 (§9.1) and re-flagged in Phase 1.5 and Phase 2. In Phase 3 **it happened**: four sources existed in configuration but not in the document, and one collector was mis-attributed.

`scripts/check_evidence_catalog.py` now compares the two registries and exits non-zero on divergence. It caught all six divergences immediately; they are fixed and the check passes on 17 sources.

One detail worth recording: the check was initially **too lenient** — comparing collector attributions token-wise let `runtime_monitor.py` and `executable_monitor.py` match on the shared word "monitor", masking a real mis-attribution. Tightening the stopword list surfaced it. A drift check that cannot distinguish two monitors is worse than none, because it certifies agreement that does not exist.

## 8. Consolidation Against the Brief's Component List

The brief named 8 collectors; 3 were implemented. This is a compliance decision, not an omission.

| Brief's collector | Where it lives |
|---|---|
| Synchronization Collector | `SyncLogCollector` |
| Network Collector | `AgentNetworkCollector` |
| SQLite Queue Collector | `SyncQueueCollector` |
| Scheduler Collector | Folded into `SyncLogCollector` — cadence *is* log timestamps |
| API Collector | Folded into `SyncLogCollector` — API outcomes *are* log lines |
| Retry Collector | Folded into `SyncLogCollector` — retries *are* log events |
| Offline Collector | Folded into `SyncLogCollector` + `AgentNetworkCollector` |
| WebSocket Collector | Not implemented — no observable WebSocket artifact exists (§2.6 of the architecture report) |

**Why consolidation is required rather than merely convenient:** five of the eight would have read the *same log file*. Under §4.1 evidence from two collectors reading one artifact does not independently corroborate — so eight collectors would have produced evidence that *looked* like eight independent sources while actually being three. That would have inflated apparent corroboration and, through the confidence calculation, produced overstated confidence. The architecture's own independence rule requires one collector per artifact.

All eight validators the brief named **are** implemented as distinct classes, because they answer genuinely distinct questions.

## 9. Residual Risks

| Risk | Severity | Note |
|---|---|---|
| Log-derived fidelity depends on product log wording | **High** | A version that changes its logging silently reduces coverage. Mitigated: patterns are configuration, and an unmatched pattern degrades to `INCONCLUSIVE`, never to a false negative |
| Reviewer role still unassigned | **High** | No promotion can complete. The knowledge base cannot advance past `Partially Verified` regardless of evidence gathered |
| 405 checks live in scratchpad, not CI | **High** | Four phases of debt. Every phase adds to it |
| Six sync questions remain `Hypothesis` | Medium (accepted) | Honest consequence of a window in which nothing failed |
| Observed deployment is non-production | Medium | Should be confirmed before figures are read as production behaviour |
| Nothing can reach `Verified` on log evidence alone | Medium (by design) | A policy question for the reviewer, documented in the Knowledge Base Update §5 |

## 10. Verdict

**Compliant.** No frozen contract was changed. The architecture accommodated a phase it was designed for — the Synchronization Monitor was specified two phases before it was built, and the specification held, including its own instruction to resolve the observation-strategy decision by measurement rather than assumption.

The one place the architecture proved *wrong* — the fidelity estimate for log-derived observation — was corrected by evidence, in the document, with the reasoning recorded. That is the amendment process working, not a breach of it.

## 11. Cross References

- [Framework Manifest](FRAMEWORK_MANIFEST.md) · [Validation Standard v1.0](ADS/validation_standard.md) · [Evidence Catalog](Evidence_Catalog.md)
- [Framework Architecture Standard](ADS/architecture.md) · [Synchronization Monitor Design](design/Synchronization_Monitor.md)
- [Architecture Freeze Report](ARCHITECTURE_FREEZE_REPORT.md) · [Architecture Review](ARCHITECTURE_REVIEW.md)
- [Phase 3 Implementation Review](IMPLEMENTATION_REVIEW_PHASE_3.md)

---
**Document Status:** Final — Phase 3
**Owner:** TODO
**Last Updated:** 2026-07-30
