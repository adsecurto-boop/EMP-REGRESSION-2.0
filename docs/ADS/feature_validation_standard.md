# Feature Validation Standard

> **Extends, does not amend.** This standard sits *under* the ratified [Validation Standard v1.0](validation_standard.md) and changes nothing in it. Where the two appear to conflict, the Validation Standard wins. This document only says how a *feature* plugin applies it.

## 1. Purpose

Defines how every EmpMonitor feature plugin is built, so that fourteen plugins written by different people at different times reach comparable conclusions from comparable evidence.

The Validation Standard says a conclusion needs corroboration across layers. This standard says what that means for a feature: **a feature is healthy when configuration, runtime, synchronization, and dashboard all agree about it** — and the layer where they stop agreeing localises the fault.

## 2. Scope

Applies to every plugin inheriting :class:`plugins.base.FeatureValidationPlugin` — the fourteen profiled features and any added later. It does not apply to `EM000_EnvironmentValidator` or `EM001_Synchronization`, which are cross-cutting rather than feature plugins.

## 3. Every Feature Plugin Must

1. **Inherit from `FeatureValidationPlugin`.** Feature-specific logic goes in the subclass; anything reusable belongs in the base or in a generic validator.
2. **Have a profile in `config/features.json`** before it has code. The profile records what the feature *should* do; writing the plugin first means encoding expectations in code where they cannot be reviewed.
3. **Declare only observable layers.** `metadata.evidence_layers` is derived from the profile's `observable_layers`, which excludes Layer 4 while no dashboard collector exists. A plugin must not claim a layer it cannot observe.
4. **Depend on `EM000_EnvironmentValidator`.** Validating a feature on a machine whose agent is not installed and running is meaningless, and the environment gate skips the plugin when the pre-check is negative.
5. **Reuse existing collectors and validators.** See §6. Adding a collector requires an Evidence Catalog entry first.
6. **Never decide its own verdict.** The plugin produces evidence and correlations; the validation engine decides.
7. **Report absence according to the profile's status.** See §4 — this is the rule most easily got wrong.

## 4. Absence Is Not Failure

The single most important rule in this standard.

| Feature status | Expected artifact absent → | Why |
|---|---|---|
| **Verified** | `FAILED` | The mechanism has been observed working. Its absence now is a real defect. |
| **Partially Verified** | `INCONCLUSIVE` | Supporting artifacts were observed but the mechanism was not. Absence may mean the framework is looking in the wrong place. |
| **Hypothesis** | `INCONCLUSIVE` | Nothing about the mechanism is known. The framework does not yet know what absence *means* for this feature. |

Encoded in `FeatureProfile.absence_verdict`, so a plugin cannot get it wrong by forgetting.

Concretely: `pending_screenshots6` being empty is **not** evidence that screenshots are broken. It is equally consistent with nothing having been captured yet. Only for a `Verified` feature is "expected artifact missing" a defect — and today exactly one feature qualifies (`EM023_EmailMonitoring`).

**A feature plugin's first job is often reverse engineering, not validation.** Five of fourteen features are `Hypothesis`: no table, config key, or log pattern has been identified. For those, the plugin's honest output is a set of open questions and a promotion record — not a verdict.

## 5. Corroboration for Features

A feature's healthy verdict must pair layers, exactly as [§5.1](validation_standard.md) requires:

| Layer | The question it answers for a feature |
|---|---|
| **L1** Configuration | Is the feature *supposed* to be running, and how often? |
| **L2** Runtime | Is the component that implements it alive, and is data landing locally? |
| **L3** Synchronization | Is that data reaching the server? |
| **L4** Dashboard | Is it visible and correct to the user? |

**L1 + L2 is the minimum** for any positive feature verdict: configuration alone proves intent, runtime alone proves activity without purpose. Neither suffices.

**L4 is unavailable.** No dashboard collector exists, so every Layer 4 correlation returns `INDETERMINATE` and no feature can currently be validated end to end. The consequence must be stated plainly in every feature report: **a synchronization defect and a surfacing defect are indistinguishable today.** Data proven to reach the server may still be invisible to the user, and the framework cannot tell.

## 6. Reuse Register — Do Not Duplicate

Phases 2 and 3 built most of what a feature needs. A plugin that writes its own is duplication, and duplicated collectors are worse than merely wasteful: two collectors reading one artifact produce evidence that *looks* independent, inflating apparent corroboration and, through the confidence calculation, overstating confidence ([§4.1](validation_standard.md)).

| Need | Use | Do **not** write |
|---|---|---|
| Product configuration (L1) | `ConfigurationCollector` | another config reader |
| Processes and services (L2) | `ProcessCollector`, `ServiceCollector` | another process lister |
| Executable identity (L2) | `ExecutableCollector` | another hasher |
| Filesystem and disk (L2) | `FilesystemCollector` | another path walker |
| Database structure (L2) | `SqliteCollector` | another database reader |
| Queue state (L3) | `SyncQueueCollector` | another queue reader |
| Log-derived sync events (L3) | `SyncLogCollector` | another log parser |
| Connection state (L3) | `AgentNetworkCollector` | another netstat wrapper |
| Dashboard (L4) | `UnavailableDashboardCollector` until a real one exists | anything with a browser in it |
| Configuration correctness | `ConfigurationValidator` | — |
| Runtime expectations | `RuntimeValidator` | — |
| Upload outcomes | `UploadValidator` | — |
| Queue health | `QueueValidator` | — |
| Freshness | `TimestampValidator` | your own age arithmetic |
| Interval correctness | `FrequencyValidator` | your own cadence arithmetic |
| Cross-layer agreement | `CorrelationValidator` | your own agreement logic |
| Evidence adequacy | `EvidenceSufficiencyValidator` | — |
| Cadence or freshness maths | `framework.core.correlation.analyse_cadence` / `analyse_freshness` | a second copy |

The last row is not a style preference. Two implementations of "every 180 seconds" are free to disagree, and a framework whose two answers differ has no answer.

## 7. Correlation, Not Judgement

`FeatureCorrelationEngine` answers cross-layer questions and returns `Correlation` objects with `AGREES`, `DISAGREES`, or `INDETERMINATE`.

**A correlation is not a verdict.** `DISAGREES` does not mean failed — two layers can disagree because the product is broken, because an observation was taken at the wrong moment, or because the expectation is wrong. Only `CorrelationValidator`, applying the Validation Standard, turns agreement into a verdict.

**`INDETERMINATE` must never be counted as agreement.** A comparison that could not be made is an open question. Rolling it into a pass is the precise failure mode `INCONCLUSIVE` exists to prevent.

Two distinct questions, easily conflated:

- `runtime_matches_configuration` — are the configured and observed values *equal*?
- `configuration_explains_runtime` — does configuration *account for* the observed state?

A queue holding one row is *explained* by a six-hourly send interval. Calling that a mismatch would be wrong, and this is not a hypothetical: it is exactly what `pending_aduserproperties6` looked like on the reference machine.

## 8. Report Requirements

Every feature report states:

1. **Verification status alongside the verdict.** A `FAILED` verdict on a `Hypothesis` feature means something very different from one on a `Verified` feature, and a reader must be able to tell.
2. **`layers_not_observable`** — which required layers could not be observed at all. Today that is L4 for every feature expecting a dashboard page.
3. **`absence_means`** — what absence would have implied for this feature, so the reasoning is auditable.
4. **Correlation summary** with `INDETERMINATE` counted separately.
5. **Expected failure modes** from the profile, so a reader can see what was looked for as well as what was found.

## 9. Templates and Activation

`scripts/new_feature_plugin.py` generates a template per profiled feature. Templates are **abstract**: `feature_summary` is re-declared `@abstractmethod`, so plugin discovery skips them and an unfinished plugin cannot run in a regression.

That property is load-bearing. A concrete empty template would be discovered, registered, and executed in every run, reporting on a feature nobody had implemented. Implementing `feature_summary` is the deliberate act of activation.

## 10. Adding a Feature — Checklist

- [ ] Profile added to `config/features.json`, status honestly set
- [ ] Template generated via `scripts/new_feature_plugin.py`
- [ ] Any new evidence source registered in the [Evidence Catalog](../Evidence_Catalog.md) **and** its config mirror; `python scripts/check_evidence_catalog.py` passes
- [ ] Existing collectors and validators reused (§6)
- [ ] Absence handled per the profile's status (§4)
- [ ] Correlations returned, verdicts left to the engine (§7)
- [ ] `feature_summary` implemented — the plugin is inert until then
- [ ] Report states verification status, unobservable layers, and open questions (§8)
- [ ] [HB-006](../handbook/HB-006_Feature_Specifications.md) updated

## 11. Cross References

- [Validation Standard v1.0](validation_standard.md) — the ratified contract this extends
- [Plugin Development Guide](plugin_standard.md) · [Framework Manifest](../FRAMEWORK_MANIFEST.md)
- [Feature Profiles](../Feature_Profiles.md) · [Evidence Catalog](../Evidence_Catalog.md)
- [Dashboard Navigation](../design/Dashboard_Navigation.md) · [Dashboard Page Specifications](../design/Dashboard_Page_Specifications.md)

---
**Document Status:** Active — extends Validation Standard v1.0 without amending it
**Owner:** TODO
**Last Updated:** 2026-07-30
