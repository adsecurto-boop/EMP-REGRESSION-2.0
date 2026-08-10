# Validation Standard — Multi-Source Evidence Model

> **RATIFIED — v1.0 (2026-07-30).** This document is the official framework contract. Every validator, monitor, plugin, and report must comply with it. Changes require the process in [ADS README §5](README.md) and a version bump recorded in §13. Numeric thresholds marked *(configurable)* may be tuned via framework configuration without re-ratification; the model itself may not.

## 1. Purpose

This standard defines the framework's central engineering rule: **a validation conclusion must be supported by multiple independent evidence sources across defined layers.** It exists because a binary PASS/FAIL is not an acceptable output for this platform.

Every validation the framework performs must be able to answer:

1. **What** failed
2. **Where** it failed (which layer, which component)
3. **Why** it failed (the causal finding, not the symptom)
4. **What evidence** supports that conclusion

## 2. Scope

Applies to every validator under `framework/validators/`, every monitor under `framework/monitors/`, and every plugin under `plugins/`. No plugin may report a feature as healthy on the strength of a single evidence source.

## 3. The Four Evidence Layers (Ratified)

| Layer | Name | Question It Answers | Product Surfaces |
|---|---|---|---|
| **L1** | Configuration | Is the feature *supposed* to be doing this? | `config.js`, `empm.ini`, dashboard settings |
| **L2** | Runtime | Is the endpoint *actually* doing it? | Processes, Windows services, scheduler, CPU, RAM, SQLite, logs |
| **L3** | Synchronization | Is the result *reaching* the server? | Authentication, upload queue, APIs, retry logic, offline sync |
| **L4** | Dashboard | Is the result *visible and correct* to the user? | UI validation, timestamp validation, feature visibility, user status |

Layer definitions map to product surfaces documented in [HB-002 §6](../handbook/HB-002_Product_Architecture.md).

### 3.1 Why Layers, Not Just Checks

Layers localize failure. A feature that passes L1–L2 but fails L3 is a *sync* defect; the same symptom at L4 only ("data missing on dashboard") is indistinguishable from a capture defect without layered evidence. **The layer at which evidence first diverges is the localization of the fault.**

### 3.2 Pipeline-Stage ↔ Layer Mapping (Ratified)

[HB-002 §5](../handbook/HB-002_Product_Architecture.md) describes the product's assumed data path as five stages. The authoritative mapping between that pipeline and this standard's layers is:

| Pipeline Stage (HB-002 §5) | Evidence Layer(s) | Note |
|---|---|---|
| Configure | L1 | |
| Capture | L2 | Observed via runtime behavior and its immediate outputs |
| Persist | L2 | SQLite / file system are runtime surfaces of the endpoint |
| Synchronize | L3 | |
| Surface | L4 | |

Other documents must reference this table rather than re-deriving their own mapping.

## 4. Evidence Source Catalog

The master registry of evidence sources — with IDs, assigned collectors, and per-source confidence ratings — is the [Evidence Catalog](../Evidence_Catalog.md). That catalog is authoritative for *what sources exist*; this standard is authoritative for *how their evidence combines into conclusions*. A source not registered in the catalog may not be cited as evidence.

### 4.1 Independence Rule (Ratified)

Two pieces of evidence corroborate each other only if they are **independent**: collected by different collectors from different underlying artifacts. Specifically:

- A single artifact observed once contributes evidence to **exactly one layer** per observation, even if the catalog registers it against multiple layers. Example: dashboard settings are *authored* at L1 and *observed* at L4 — a single read of the dashboard settings page counts as L4 evidence (an observation of the dashboard) **or** as L1 evidence (the configured intent), never both at once. Claiming both layers requires two observations with distinct intent, and the L1 claim should prefer an endpoint-side artifact where one exists.
- Derived evidence does not corroborate its own source (e.g., a log line *about* an upload does not corroborate the upload API response if the log line was generated from that same response — they share a common origin).

## 5. Corroboration Rules (Ratified)

### 5.1 Positive Conclusions

A **positive** conclusion (`HEALTHY`) requires corroborating evidence from **at least two layers** *(configurable minimum, never below two)*, of which at least one must be **L2 or higher**. Rationale: L1 alone proves intent, not behavior.

### 5.2 Negative Conclusions

A **negative** conclusion (`FAILED`) requires:

1. Evidence identifying the **first diverging layer** — the earliest layer at which observed state departs from expected state; and
2. Evidence from the layer immediately *upstream* of the divergence establishing that upstream state was sound (so the fault is localized, not merely detected).

If upstream soundness cannot be evidenced, the verdict is `FAILED` with reduced confidence (§8) and `why: undetermined` — never a silent guess at localization.

### 5.3 Insufficient Evidence

Evidence from a single layer yields `INCONCLUSIVE`, never `HEALTHY` and never `FAILED`. `INCONCLUSIVE` is a first-class outcome and must be reported as such (§10).

### 5.4 Minimum Evidence Requirements per Verdict

| Verdict | Minimum Evidence |
|---|---|
| `HEALTHY` | ≥2 layers corroborating, ≥1 at L2+ (§5.1) |
| `DEGRADED` | Same as `HEALTHY`, plus ≥1 anomaly finding that does not constitute divergence |
| `FAILED` | First-diverging-layer evidence (§5.2) |
| `INCONCLUSIVE` | Any evidence that fails to meet the above |
| `BLOCKED` | Evidence that a precondition failed (environment/configuration), recorded before validation logic ran |

## 6. Verdict Model (Ratified)

The framework must not emit bare PASS/FAIL. The verdict set is:

| Verdict | Meaning |
|---|---|
| `HEALTHY` | Corroborated across the required layers |
| `DEGRADED` | Functioning, but with corroborated anomalies (e.g., retries eventually succeeding, latency beyond threshold) |
| `FAILED` | Divergence localized to a specific layer with supporting evidence |
| `INCONCLUSIVE` | Insufficient independent evidence to conclude — **not** a pass and **not** a failure |
| `BLOCKED` | Preconditions (environment/configuration) not met; validation did not run |

Verdict transitions and precedence: `BLOCKED` preempts all others (if validation could not run, nothing else may be claimed). `FAILED` preempts `DEGRADED`. `INCONCLUSIVE` may never be upgraded or downgraded into another verdict by aggregation — a roll-up containing an `INCONCLUSIVE` finding must surface it.

## 7. Evidence Priority and Conflict Resolution (Ratified)

When independent evidence sources disagree, the conflict is resolved by these rules, applied in order:

1. **A conflict is itself a finding.** Disagreement between layers is never averaged away; it is recorded in the finding's `conflicts[]` field and always caps confidence at `Low` (§8) unless resolved by rule 2 or 3.
2. **Proximity wins within a layer's own question.** For a question about a given layer, evidence native to that layer outranks evidence about it from another layer. Example: for "is the process running?" (L2 question), runtime observation outranks a dashboard status badge (L4). The outranked evidence is retained in the finding as the conflict record.
3. **Direct observation outranks derived evidence.** Artifact contents outrank a log line describing the artifact; an API response outranks a UI rendering of it.
4. **Absence is weak evidence.** Absence of an expected artifact/log is admissible only as corroborating (never primary) evidence, and absence of an *error* is not positive evidence at all (§11 anti-patterns).
5. **Unresolvable conflicts force `INCONCLUSIVE`** for the affected claim, with both sides of the conflict reported.

## 8. Confidence Model (Ratified)

### 8.1 Confidence Levels

Every finding carries exactly one confidence level:

| Level | Meaning |
|---|---|
| `VERY_HIGH` | ≥3 independent layers corroborate; no unresolved conflicts; all sources rated High confidence in the [Evidence Catalog](../Evidence_Catalog.md) |
| `HIGH` | 2 independent layers corroborate; no unresolved conflicts; primary source rated High |
| `MEDIUM` | Corroboration met, but a contributing source is rated Medium or below, or upstream soundness (§5.2) could not be evidenced |
| `LOW` | Single-source support, or an unresolved conflict is present |
| `UNKNOWN` | Evidence could not be collected at all (collector unavailable, `BLOCKED` verdict) |

### 8.2 Confidence Calculation

Confidence is **computed, not asserted**: it is derived mechanically from (a) the number of independent corroborating layers, (b) the per-source confidence ratings registered in the [Evidence Catalog](../Evidence_Catalog.md), and (c) the presence of unresolved conflicts, per the table above. A plugin may lower a computed confidence (with a recorded reason); it may never raise one. The numeric boundaries above are *(configurable)*; the monotonicity rules (more independent corroboration never lowers confidence; a conflict never raises it) are not.

## 9. Failure Classification (Ratified)

Every `FAILED` finding is classified by its first diverging layer, which yields the framework's failure taxonomy:

| Class | First Divergence | Meaning |
|---|---|---|
| Configuration Defect | L1 | Intent is wrong, missing, or contradictory |
| Capture/Runtime Defect | L2 | Endpoint not doing what configuration intends |
| Persistence Defect | L2 (storage surfaces) | Captured but not (correctly) persisted locally |
| Synchronization Defect | L3 | Persisted but not (correctly) reaching the server |
| Surfacing Defect | L4 | Server has it, dashboard shows it wrong or not at all |

This taxonomy is the validation-level complement of the *framework-internal* error categories in the [Error Handling Standard](error_handling_standard.md) — that standard classifies failures of the framework itself; this section classifies failures of the product under validation. The two must not be conflated in reports.

## 10. Finding Structure and Reporting Rules (Ratified)

Every validation result must carry a structured finding, not a message string:

| Field | Description | Required |
|---|---|---|
| `what` | The observed defect or observed healthy behavior | Always |
| `where` | Layer + component + artifact | Always |
| `why` | Causal finding, or explicitly `undetermined` | Always |
| `evidence[]` | References to captured evidence artifacts, each carrying its [Evidence Catalog](../Evidence_Catalog.md) ID | Always, ≥1 entry |
| `verdict` | From §6 | Always |
| `confidence` | From §8 | Always |
| `corroboration` | Which layers contributed evidence | Always |
| `conflicts[]` | Unresolved evidence disagreements (§7) | When present |

Reporting rules (binding on the [Reporting Standard](reporting.md) and all plugins):

1. A report must render every field above; no field may be dropped in aggregation.
2. `INCONCLUSIVE` and `BLOCKED` findings appear in reports with the same prominence as `FAILED` — they are unanswered questions, not noise.
3. A failed run still produces a report ([Reporting Standard §7](reporting.md)).
4. Confidence is always displayed alongside the verdict; a verdict without its confidence is non-conformant.
5. The evidence references in `evidence[]` must resolve to artifacts retained under `reports/` per the [Reporting Standard](reporting.md).

> **TODO (implementation-phase, does not block ratification):** the concrete serialization (schema file, field types) is a Phase 1 deliverable per the [Implementation Plan](../roadmap/implementation_plan.md). This section fixes the semantics; Phase 1 fixes the syntax. Once base models exist, extract this section into `docs/ADS/finding_schema.md` per [Architecture Review §8.1](../ARCHITECTURE_REVIEW.md).

## 11. Anti-Patterns

The following are non-conformant and must be rejected in review:

- Concluding a feature is healthy from dashboard UI alone (L4 only).
- Concluding a feature is healthy because a process is running (L2 presence without output verification).
- Treating absence of an error log as positive evidence.
- Reporting a symptom as the `why` (e.g., "screenshot missing on dashboard" is a `what`, not a `why`).
- Collapsing `INCONCLUSIVE` into `FAILED` or `HEALTHY`.
- Counting one observation of one artifact as evidence in two layers (§4.1).
- Asserting a confidence level rather than computing it (§8.2).

## 12. Known Gaps

| Gap | Impact | Status |
|---|---|---|
| L3 collector not implemented | L3 evidence cannot be collected until Phase 3 | **Designed** — see [Synchronization Monitor Design](../design/Synchronization_Monitor.md); implementation scheduled in the [Implementation Plan](../roadmap/implementation_plan.md) |

The two former gaps (corroboration rule and verdict model unratified) are closed by this ratification.

## 13. Version History

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-07-30 | Ratified: layers, corroboration rules, verdict model, evidence priority/conflict resolution, confidence model, failure classification, reporting rules |

## 14. Cross References

- [Evidence Catalog](../Evidence_Catalog.md) — master registry of evidence sources
- [Synchronization Monitor Design](../design/Synchronization_Monitor.md) — L3 collector design
- [HB-002 — Product Architecture](../handbook/HB-002_Product_Architecture.md)
- [Reporting Standard](reporting.md)
- [Error Handling Standard](error_handling_standard.md)
- [Plugin Development Guide](plugin_standard.md)
- [Framework Manifest](../FRAMEWORK_MANIFEST.md)
- [Architecture Review](../ARCHITECTURE_REVIEW.md)

---
**Document Status:** **Ratified — v1.0.** Semantics frozen; *(configurable)* thresholds tunable via configuration; serialization deferred to Phase 1.
**Owner:** TODO
**Last Updated:** 2026-07-30
