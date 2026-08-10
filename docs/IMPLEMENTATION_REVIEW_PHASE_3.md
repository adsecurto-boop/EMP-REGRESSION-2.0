# Implementation Review — Phase 3: Synchronization Reverse Engineering & Validator (EM001)

## 1. Summary

Phase 3 delivers **EM001_Synchronization**, which reverse-engineers the EmpMonitor synchronization lifecycle from passive evidence and then validates what it found. The order was the point: the objective was not to prove synchronization works, but to establish **how** it works.

Against a live agent it reconstructed **13 of 16 lifecycle stages** across Layers 1, 2, and 3, and produced 13 findings — 11 healthy or degraded, and the rest honestly inconclusive.

It also closed the last structural gap in the architecture: **Layer 3 now has a working collector**, and the observation-strategy decision deferred since the Architecture Review is resolved by measurement.

**No architectural contract was changed.** Three defects were fixed (§6), one of which closed a gap between the ratified standard and the code. The long-predicted Evidence Catalog drift finally occurred and is now mechanically prevented.

Verification: **82 new checks pass**, and all prior harnesses still pass — **405 green** across four phases.

Four documents were produced as required: this review, the [Synchronization Architecture Report](Synchronisation_Architecture_Report.md), the [Knowledge Base Update](Knowledge_Base_Update.md), and the [Architecture Compliance Report](Architecture_Compliance_Report.md).

## 2. The Decisive Finding: Interception Was Unnecessary

The Synchronization Monitor design ranked four observation strategies and left the choice open, warning that proxy interception would violate the passive constraint. It also *guessed* that log-derived observation had the lowest fidelity.

**Measurement reversed that ranking.** The agent logs request URLs, API names, HTTP reply codes, server messages, and per-item upload outcomes — exactly the data interception was being considered for. So the intrusive option was not merely rejected on principle; it turned out to be **unnecessary**:

| Strategy | Estimated | Measured | Adopted |
|---|---|---|---|
| Log-derived | Low–Med | **High** | **Primary** |
| Queue-state | Medium | Medium–High | Yes |
| Network state | High | Medium (TLS) | Yes |
| Proxy interception | Highest | — | **Rejected** |

The design document has been corrected. Evidence overrode documentation, which is what the brief's own rule demands.

## 3. What Was Built

| Component | Location | Role |
|---|---|---|
| Synchronization Monitor | `framework/monitors/sync_monitor.py` | Three collectors: log (EV-007), queue (EV-007), connection state (EV-017) |
| Sync validators | `framework/validators/synchronization.py` | All 8 the brief named, as distinct classes |
| EM001 plugin | `plugins/EM001_Synchronization/plugin.py` | Composes the pipeline; asserts no verdict itself |
| Lifecycle timeline | `plugins/EM001_Synchronization/timeline.py` | 16-stage reconstruction + evidence graph |
| Knowledge promotion | `plugins/EM001_Synchronization/promotion.py` | Proposes `Hypothesis → Partially Verified → Verified` records |
| Report summaries | `plugins/EM001_Synchronization/summary.py` | Every section the brief requires |
| Sync profile | `config/framework.json` (`empmonitor.synchronization`) | 14 discovered log patterns, prefixes, thresholds — all configuration |
| **Catalog drift check** | `scripts/check_evidence_catalog.py` | Closes the risk flagged since Phase 1 |

## 4. What Was Learned About the Product

Full detail in the [architecture report](Synchronisation_Architecture_Report.md). The load-bearing results:

**Verified.** Upload cadence is **180 s with ≈0 drift**, matching `dataSendingPeriodSec` — corroborated across L1 (configured), L2 (process alive), and L3 (observed timing). Four APIs exercised, **12 of 12 replies HTTP 200**. The **GUI process uploads, not the service**; the service listens on loopback and the GUI connects to it, so a running service does not by itself imply uploads are happening. Six `pending_*` queue tables discovered by prefix, draining to zero.

**Three product anomalies, found rather than sought.** A retention sweep that logs an **unsubstituted placeholder** for its retention period and returns **`-1` records deleted**, every cycle — two corroborating signals for one defect, with plausible unbounded local growth. 54 access-denied process inspections. A configured SFTP upload channel silently unusable.

**Six questions remain `Hypothesis`** — offline detection, reconnect, queue recovery, failed-upload retry, token refresh, and screenshot/recording upload. All for the same honest reason: **nothing failed during the observation window, and the framework must not induce a failure to find out.**

## 5. Design Decisions Worth Recording

**Eight collectors became three.** Five of the brief's eight would have read the same log file. Under the independence rule, evidence from two collectors reading one artifact does not corroborate — so eight collectors would have *looked* like eight independent sources while being three, inflating apparent corroboration and, through the confidence calculation, overstating confidence. Consolidation was required by the architecture, not chosen for convenience. All eight *validators* exist, because they answer genuinely distinct questions.

**The one genuinely shared artifact is declared.** `SyncQueueCollector` reads the same database as `SqliteCollector`, so its evidence carries `shares_artifact_with: EV-003` and the evidence graph surfaces it. The rule is enforced visibly rather than trusted.

**Nothing reached `Verified`, and that is correct.** Log evidence is rated `medium` reliability, confidence is computed from the weakest source, and `Verified` requires `HIGH`. Ten claims corroborated across all three layers therefore sit at `Partially Verified`. Log parsing genuinely *is* less reliable than reading a service state; the model declining to overstate it is the confidence system working.

## 6. Defects Found and Fixed

1. **The model under-enforced the ratified standard.** Corroboration was enforced for `HEALTHY` but not `DEGRADED`, though §5.4 sets the same minimum for both — leaving the easier positive verdict as an unguarded route to an under-corroborated claim. Now enforced for both. This aligns code with the frozen contract rather than changing it.
2. **Validators crashed instead of reporting.** A validator building a positive finding cannot know whether the corroborating layers were collected; without a guard, a missing layer raised `ValidationError` instead of yielding `INCONCLUSIVE`. All eight now downgrade gracefully with a recorded reason.
3. **Promotions carried no agent version.** The verification workflow requires it, and a claim without a version is not reviewable. `ExecutableCollector` was added to the pipeline so every record is stamped `3.7.4`.

Also fixed: layer verdicts reported L1 and L2 as `NOT_OBSERVED` because they grouped only by where findings were *localized*, not which layers *supported* them — true of the localization, misleading about coverage on a run whose conclusions rest on exactly that corroboration.

**The drift check caught a defect in itself.** Comparing collector attributions token-wise let `runtime_monitor.py` and `executable_monitor.py` match on the shared word "monitor", masking a real mis-attribution. A drift check that cannot tell two monitors apart is worse than none, because it certifies agreement that does not exist.

## 7. Verification

| Check | Result |
|---|---|
| Phase 3 harness | **82 / 82** |
| Phase 2 regression | 75 / 75 |
| Phase 1.5 regression | 162 / 162 |
| Phase 1 regression | 86 / 86 |
| **Total** | **405 / 405** |
| Catalog drift check | Passes on 17 sources |

Coverage: registration and dependency (5), no-hardcoding compliance (5), live collector observation (12), secret safety (2), validator honesty (8), full run (4), the sprint's five questions (5), timeline and graph (7), layer verdicts (5), observed behaviour (7), product anomalies (4), knowledge promotion (11), drift control (2).

Three regressions initially failed for the same reason: enabling plugin discovery means `bootstrap()` now auto-registers EM000 *and* EM001, so harnesses assuming an empty registry saw extra sections. Test staleness, not code regressions — isolated by clearing or unregistering in the affected scenarios.

## 8. Remaining TODOs and Risks

| Item | Severity | Detail |
|---|---|---|
| **Reviewer role unassigned** | **High** | No promotion can complete. The knowledge base **cannot advance past `Partially Verified`** regardless of how much evidence accumulates. This is now the single most consequential process gap in the project — it has gone from a governance nicety to a hard blocker on the framework's central purpose. |
| **405 checks not in CI** | **High** | Four phases of debt, growing each phase |
| Log-pattern fragility | **High** | Fidelity depends on product log wording. Mitigated: patterns are configuration and an unmatched pattern degrades to `INCONCLUSIVE`, never a false negative |
| Report the retention-sweep defect | High | Two corroborating signals, every cycle, plausible unbounded growth |
| Confirm the deployment is intended | Medium | Endpoints point at a non-production host |
| Six questions still `Hypothesis` | Medium (accepted) | Requires either natural failure or a separately authorised perturbation test |
| Nothing can reach `Verified` on log evidence | Medium (by design) | A policy question for the reviewer |
| Plugin evidence reaches the report via citations and summary, not the top-level evidence list | Low | Unchanged from Phase 2; `ValidationContext` carries evidence, not the store |
| L4 has no collector | Low (out of scope) | Dashboard validation remains unbuilt; EM001 correctly declines to claim it |

## 9. Definition of Done

| Criterion | Status |
|---|---|
| Reverse-engineer before validating | ✅ Spike ran first; findings drove the implementation |
| Report only Verified behaviour | ✅ 0 Verified, 10 Partially Verified, 3 Hypothesis — nothing overstated |
| Never invent product behaviour | ✅ Six questions left explicitly open |
| Complete pipeline constructed | ✅ 13 of 16 stages observed, 3 gaps with reasons |
| Collectors implemented | ✅ 3, consolidated per the independence rule (§5) |
| Validators implemented | ✅ All 8 as distinct classes |
| Every step references evidence | ✅ Verified by test |
| Knowledge promotion with full metadata | ✅ 13 records, reviewer deliberately unset |
| Never hardcode URLs / tables / log messages | ✅ Verified by test |
| Answers "how", "where", "which layer", "what class", "what evidence" | ✅ §7 of the harness |
| No feature automation, no invented dashboard assertions | ✅ L4 declined explicitly |
| Four documents produced | ✅ |

## 10. Cross References

- [Synchronization Architecture Report](Synchronisation_Architecture_Report.md) — what was learned
- [Knowledge Base Update](Knowledge_Base_Update.md) — proposed promotions
- [Architecture Compliance Report](Architecture_Compliance_Report.md) — compliance detail
- [Synchronization Monitor Design](design/Synchronization_Monitor.md) — §6 records the resolved decision
- [Phase 1](IMPLEMENTATION_REVIEW.md) · [Phase 1.5](IMPLEMENTATION_REVIEW_PHASE_1_5.md) · [Phase 2](IMPLEMENTATION_REVIEW_PHASE_2.md)

---
**Document Status:** Final — Phase 3 complete
**Owner:** TODO
**Last Updated:** 2026-07-30
