# Dashboard Validator Interfaces — Design

> Design only — no code, no feature implementation this phase. Validators **conclude from** Layer 4 evidence; they never collect it ([interfaces.py](../../framework/shared/interfaces.py) `Validator` contract, unchanged).

## 1. Reuse First — What Already Exists and Is Not Rebuilt

Three of the brief's named validators already exist, feature-agnostic, in `framework/validators/generic.py`, and dashboard evidence flows into them **unchanged** because it arrives as ordinary `Evidence`:

| Brief asks for | Already exists | Dashboard usage |
|---|---|---|
| `TimestampValidator` | `generic.TimestampValidator` | Displayed-timestamp freshness — gated on the [Navigation §6](Dashboard_Navigation.md) semantics questions; until answered, parsed L4 timestamps are `INCONCLUSIVE`-grade inputs by design |
| — (cadence) | `generic.FrequencyValidator` | e.g., screenshot cadence as displayed vs configured interval |
| — (cross-layer) | `generic.CorrelationValidator` | The whole point of L4: does the dashboard agree with L1–L3? |
| `StatusValidator` *(partially)* | `dashboard.DashboardValidator` | Already concludes `INCONCLUSIVE` for unavailable/unreached L4 — kept as-is, and remains the fallback |

Building dashboard-flavoured copies of these would be the duplication Task 11 exists to catch. **Only genuinely L4-shaped questions get new interfaces.**

## 2. New Interfaces (design signatures — implementations in a later sprint)

All live in `framework/validators/` (which may not import `framework/dashboard/` — they consume `Evidence`, whose `data` is a `DashboardObservation.to_dict()`, so no dependency on the dashboard package is needed; the dict shape is part of the frozen contract). All are constructed with expectations from a feature profile, return `Finding` via `Finding.build`, and route positive verdicts through the existing corroboration downgrade so a single-layer L4 reading can never assert `HEALTHY` alone.

### 2.1 `PresenceValidator`

*Question:* did an expected element/record/feature-surface appear on a reached page?

```
PresenceValidator(subject, page, expected_keys, evidence) -> Finding
```

- Page not reached → `INCONCLUSIVE` (reason from observation, never invented).
- Reached, key absent → **absence is a real observation**: `FAILED` only with lower-layer corroboration that the thing should exist (e.g., uploads observed at L3); otherwise `DEGRADED`/`INCONCLUSIVE` per the §5 corroboration rules.
- Empty-state shown ≠ error state — distinguished exactly as the page specs demand.

### 2.2 `CountValidator`

*Question:* does a displayed count agree with a lower-layer count within a declared tolerance?

```
CountValidator(subject, displayed_count, reference_count, reference_layer, tolerance, evidence) -> Finding
```

- The reference count comes from existing L2/L3 evidence (e.g., rows leaving `pending_screenshots6`).
- Tolerance is explicit and configured — never implicit — because propagation delay is unmeasured ([Navigation §6.3](Dashboard_Navigation.md)); until measured, a shortfall within one sync cycle is `INCONCLUSIVE`, not `FAILED`.

### 2.3 `StatusValidator`

*Question:* does a displayed status (user online/offline, feature active, connection indicator) agree with observed runtime state?

```
StatusValidator(subject, displayed_status, expected_status, expectation_source_layer, evidence) -> Finding
```

- Expected status must cite the evidence it derives from (e.g., EV-005 service running). Disagreement localises to the *first diverging layer* via the existing correlation machinery, not inside this validator.

### 2.4 `ImageAvailabilityValidator`

*Question:* for a window where capture/upload was evidenced at L2/L3, does the screenshots page show items?

```
ImageAvailabilityValidator(employee_ref, window, displayed_items, lower_layer_evidence, evidence) -> Finding
```

- Concludes on **metadata presence** (items listed, thumbnails render) — never on image content ([Standard §4](../ADS/dashboard_automation_standard.md)).
- This is the "uploaded but not surfaced" detector for EM010 — the failure mode currently undetectable for every feature ([HB-006 §16](../handbook/HB-006_Feature_Specifications.md)).

### 2.5 `RecordingAvailabilityValidator`

Same shape as 2.4 for the recordings page (EM011), with one extra rule: **no playback** — availability is list-presence and metadata only, because playback is treated as a write until proven side-effect-free ([Page Specifications §3](Dashboard_Page_Specifications.md)). Notable asymmetry it must tolerate: EM011 has *no* profiled L2 table, so its lower-layer reference may legitimately be empty — in which case the validator reports what L4 shows without a cross-layer verdict.

## 3. Shared Rules (all five)

1. Constructed per-use with expectations injected — no validator holds feature knowledge; feature profiles supply it (the `generic.py` pattern).
2. Never touch a browser, page object, or locator. Evidence in, findings out.
3. Positive verdicts pass the corroboration gate (≥2 layers, one ≥L2). An L4-only reading concludes at most `INCONCLUSIVE`.
4. Unreached/unavailable pages defer to the existing `DashboardValidator` fallback — new validators do not re-conclude unavailability.
5. Verdict semantics, confidence computation, and finding structure: [Validation Standard](../ADS/validation_standard.md) — consumed, not extended.

## 4. What Is Deliberately Absent

No `LoginValidator` (login is unprofiled — [HB-001 §4.1](../handbook/HB-001_Product_Overview.md)); no per-feature validators (EM010 screenshot rules etc. belong to feature plugins in a later sprint, composing these interfaces); no assertion DSL.

## 5. Cross References

- [`framework/validators/generic.py`](../../framework/validators/generic.py) · [`framework/validators/dashboard.py`](../../framework/validators/dashboard.py) — reused, unchanged
- [Dashboard Collector design](Dashboard_Collector.md) — the evidence these consume
- [Validation Standard](../ADS/validation_standard.md) — verdict/corroboration/confidence rules (frozen)

---
**Document Status:** Design complete — interfaces only; no implementation, no feature logic
**Owner:** TODO
**Last Updated:** 2026-07-31
