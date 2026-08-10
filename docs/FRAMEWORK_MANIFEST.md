# Framework Manifest

> **This is the constitution of the EmpMonitor Automation Framework.** It is not a handbook, not a how-to, and not a standard. It states the principles every other document and every future architectural decision must comply with. Where a standard describes *how* to do something, this manifest says *why it must be that way* and *what may never change*. When a proposed change conflicts with this manifest, the change is wrong until this manifest is deliberately amended (§13).

## 1. Mission

To **continuously and provably validate the entire EmpMonitor ecosystem** — endpoint agent, configuration, runtime, storage, synchronization, and dashboard — such that any failure is not merely detected but *located, explained, and evidenced*.

## 2. Vision

A framework an engineer can return to years from now and extend with confidence: where the architecture is frozen, the standards are ratified, every claim about the product under validation carries a known confidence, and adding coverage means adding a plugin, never rewiring the core.

## 3. Core Principles

1. **Evidence over assertion.** Nothing is healthy because it "should" be. A conclusion exists only as far as evidence supports it.
2. **Locate, don't just detect.** "Something is broken" is not an acceptable output. The framework names the layer, component, and cause.
3. **Multiple independent sources.** No conclusion rests on a single source ([Validation Standard §5](ADS/validation_standard.md)).
4. **Honest uncertainty.** `INCONCLUSIVE` and `Hypothesis` are first-class. A guess dressed as a fact is the single most dangerous thing this framework can produce.
5. **The core is feature-agnostic.** Feature knowledge lives in plugins; the core never learns what "attendance" is.
6. **Configuration over code.** Behavior that varies is configured, not hardcoded ([Configuration Standard](ADS/configuration_standard.md)).
7. **Observability is not optional.** Every component can explain its own behavior through logs and evidence.
8. **Document before building.** Architecture and its reference documents precede implementation — this manifest exists because that principle was followed.

## 4. Architectural Philosophy

- **Layered, not tangled.** The core provides orchestration, collection, validation, and reporting primitives; plugins compose them. Dependencies flow one way: plugins → core → shared. The core never imports a plugin ([Framework Architecture Standard §3](ADS/architecture.md)).
- **Collectors collect; validators conclude.** A monitor produces evidence and never a verdict; a validator applies the [Validation Standard](ADS/validation_standard.md) to evidence to produce a verdict. This separation is load-bearing and may not be blurred for convenience.
- **One artifact, one collector.** Each product artifact has a single responsible collector ([Evidence Catalog §6](Evidence_Catalog.md)); composition happens by *consuming* another collector's evidence, never by re-reading its artifact ([Validation Standard §4.1](ADS/validation_standard.md)).
- **Extension points, not modification points.** New coverage enters through defined seams (plugin registry, new evidence sources, new monitors) without editing orchestration control flow.

## 5. Evidence Philosophy

- Evidence is **layered** (L1 Configuration, L2 Runtime, L3 Synchronization, L4 Dashboard) and the layer of first divergence *is* the fault localization ([Validation Standard §3.1](ADS/validation_standard.md)).
- Every evidence source is **registered** in the [Evidence Catalog](Evidence_Catalog.md) with an inherent confidence rating; unregistered sources are inadmissible.
- Confidence is **computed from evidence, never asserted** ([Validation Standard §8.2](ADS/validation_standard.md)).
- **Absence is weak.** Absence of an artifact is corroboration at most; absence of an error is not evidence at all.
- **Conflict is information.** Disagreement between sources is recorded, never averaged away ([Validation Standard §7](ADS/validation_standard.md)).

## 6. Validation Philosophy

- The [Validation Standard](ADS/validation_standard.md) is the ratified contract; every validator, monitor, plugin, and report complies with it.
- **No bare PASS/FAIL, ever.** The verdict set (`HEALTHY`/`DEGRADED`/`FAILED`/`INCONCLUSIVE`/`BLOCKED`) plus confidence plus a structured finding is the minimum unit of a result.
- A **positive** conclusion is the *hardest* to reach (requires corroboration across layers); a negative conclusion must be *localized*, not merely detected.

## 7. Plugin Philosophy

- A plugin is the **only** place feature-specific validation logic lives ([Plugin Development Guide](ADS/plugin_standard.md)).
- A plugin **must** gather evidence across every layer relevant to its feature; a single-layer plugin is non-conformant.
- A plugin's *behavioral scope* is declared in [HB-006](handbook/HB-006_Feature_Specifications.md); its *structure* follows the Plugin Development Guide. The two are kept distinct on purpose.
- Plugins depend on the core; the core is forbidden from depending on any plugin. This is inviolable.

## 8. Coding Philosophy

Per [Coding Standards](ADS/coding_standards.md): reusable, modular, configuration-driven, observable, documented, strongly typed, well-logged, production-ready. Forbidden: magic numbers, hardcoded paths, duplicated logic, hidden dependencies, silently swallowed errors. Language/toolchain specifics are deferred to that standard, but these properties are not negotiable regardless of language.

## 9. Reporting Philosophy

- A report is an **argument backed by evidence**, not a status line ([Reporting Standard](ADS/reporting.md)).
- Every finding renders all required fields ([Validation Standard §10](ADS/validation_standard.md)); `INCONCLUSIVE`/`BLOCKED` get the same prominence as `FAILED`.
- A failed run still produces a report. Reporting never depends on success.
- Canonical reference evidence ("what correct looks like") lives in `baselines/`; run output lives in `reports/`. The two are never conflated.

## 10. Scalability Principles

- **Coverage scales by plugin count, not core change.** Adding the Nth feature must not require touching the orchestrator.
- **Evidence sources scale by catalog rows, not combination-rule change.** The [Validation Standard](ADS/validation_standard.md) combination rules are independent of *which* sources exist.
- **Documents scale by a fixed template.** RE docs, handbook chapters, and standards each have a fixed section order so an unfamiliar document is navigable by position.
- **Identifiers are sequential and never reused** (`EM0NN`, `HB-0NN`, `RE-0NN`, `EV-0NN`) so references never collide or drift.

## 11. Extension Rules

A change is a conforming *extension* (welcome) rather than a *structural change* (requires amending frozen architecture) when it:

1. Adds a plugin without modifying core control flow; **or**
2. Adds an evidence source as a new [Evidence Catalog](Evidence_Catalog.md) row with a single named collector; **or**
3. Adds a monitor/validator that registers through the existing registry and honors the common interface; **or**
4. Fills a `TODO`/`Hypothesis` with a `Verified` claim via the [verification workflow](../knowledge_base/README.md).

Anything that changes the verdict model, the layer model, the corroboration rules, the dependency direction, or the collector/validator separation is a **structural change** and is out of scope after this freeze except by amendment (§13).

## 12. Backward Compatibility Rules

- **Ratified standards are versioned.** The [Validation Standard](ADS/validation_standard.md) carries a version and history; breaking its semantics requires a major version bump and a migration note.
- **Identifiers are permanent.** A retired plugin/evidence ID is never reissued; its number is burned.
- **Deprecation, not deletion.** A superseded verified claim becomes `Deprecated` with a pointer to its replacement ([knowledge_base README §6](../knowledge_base/README.md)), never silently removed.
- **Configuration keys are additive.** Removing/repurposing a key is a breaking change subject to the same discipline as a code interface.

## 13. Amending This Manifest

This manifest may be amended only deliberately: a proposed amendment is written, reviewed against the whole document set for ripple effects, and recorded with a rationale. An amendment that invalidates a ratified standard must update that standard's version in the same change. Drift — a decision elsewhere that quietly contradicts this manifest — is a defect, not an amendment.

## 14. Non-Goals

- **Not a test runner for EmpMonitor's UI alone.** Dashboard checks are one layer of four, never the whole story.
- **Not a load/performance/security testing tool.** Resource observation exists to inform `DEGRADED`, not to benchmark.
- **Not a monitoring/alerting product.** It validates correctness with evidence; it is not a production APM.
- **Not a modifier of the product under validation.** Collection is passive; the framework observes EmpMonitor, it never drives or mutates it.
- **Not a documentation of EmpMonitor for end users.** The knowledge base is engineering reverse-engineering, not user docs.
- **Not a place for unverified claims to masquerade as facts.** See §4 core principle 4.

## 15. Long-Term Design Goals

- A living knowledge base where the ratio of `Verified` to `Hypothesis` claims rises release over release.
- A plugin catalog that grows to cover every EmpMonitor feature area, each conforming to the same standard.
- Fault localization precise enough that a `FAILED` verdict points a human directly at the responsible layer and component.
- A framework whose architecture never needed a structural change after this freeze — the ultimate measure of whether this sprint succeeded.

## 16. Cross References

- [Validation Standard](ADS/validation_standard.md) — the ratified validation contract
- [Evidence Catalog](Evidence_Catalog.md) — the evidence-source registry
- [Framework Architecture Standard](ADS/architecture.md) — module boundaries
- [Plugin Development Guide](ADS/plugin_standard.md)
- [Reporting Standard](ADS/reporting.md)
- [Coding Standards](ADS/coding_standards.md)
- [Knowledge Base](../knowledge_base/README.md) — verification model
- [Architecture Review](ARCHITECTURE_REVIEW.md)
- [Architecture Freeze Report](ARCHITECTURE_FREEZE_REPORT.md)

---
**Document Status:** Ratified — framework constitution, effective at architecture freeze
**Owner:** TODO
**Last Updated:** 2026-07-30
