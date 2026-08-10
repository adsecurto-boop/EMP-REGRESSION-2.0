# Architecture Review — Documentation Phase

## 1. Purpose

Per project instruction, no feature implementation begins until this review is complete. This document is that review: it examines the full documentation set produced so far (ADS suite, EmpMonitor product handbook, reverse-engineering knowledge base, roadmap) as a system, and identifies missing documentation, weak architecture, duplicate concepts, future maintenance risks, and better abstractions — ranked by priority, with tradeoffs.

This review does not itself make binding architecture decisions (e.g., ratifying the corroboration rule). It identifies what must be decided and by when, so that Phase 1 of the [Implementation Plan](roadmap/implementation_plan.md) starts on settled ground rather than shifting sand.

## 2. Method

Every document under `docs/`, `knowledge_base/`, and the root (`README.md`, `CONTRIBUTING.md`) was read in full or in representative sample. Findings below are organized by priority tier, not by document, because most of the real risk in this documentation set is *cross-document* (a decision made in one file silently assumed as fact in five others).

## 3. Priority Tiers

| Tier | Meaning |
|---|---|
| **P0 — Blocking** | Must be resolved before Phase 1 (Framework Foundation) begins; downstream design decisions depend on the answer |
| **P1 — High** | Should be resolved before Phase 3/4; currently tolerable but will compound |
| **P2 — Medium** | Should be resolved before the plugin catalog grows past its current 6 entries |
| **P3 — Low** | Housekeeping / worth tracking, not urgent |

---

## 4. P0 — Blocking Findings

### 4.1 The corroboration rule and verdict model are unratified, but already treated as load-bearing

[`validation_standard.md`](ADS/validation_standard.md) §5 (corroboration rule) and §6 (verdict model: `HEALTHY`/`DEGRADED`/`FAILED`/`INCONCLUSIVE`/`BLOCKED`) are both marked `TODO: ratify`, yet [`reporting.md`](ADS/reporting.md), [`plugin_standard.md`](ADS/plugin_standard.md), and every one of the 12 RE documents already cite them as the governing model. This is the correct way to *draft* a standard, but it means **Phase 1's "Base Models" deliverable cannot actually be designed yet** — a Finding schema, a verdict enum, and a corroboration-checking function all require this to be a decision, not a proposal.

**Tradeoff:** Ratifying now, before any monitor/validator exists, risks designing in a vacuum with no empirical feedback. Waiting until after Phase 3 (once real evidence sources exist) risks having already written Phase 1 base models around a guess, forcing a breaking change.

**Recommendation:** Ratify the *shape* of the model now (verdict enum, Finding fields) — these are cheap to change before code exists — but explicitly defer the *thresholds* (e.g., "at least two layers" in §5) as a tunable configuration value rather than a hardcoded rule, so empirical adjustment after Phase 3 doesn't require a schema change. This is itself a "better abstraction" recommendation (see §8.1).

### 4.2 Layer 3 (Synchronization) has no assigned evidence collector anywhere in the roadmap

This is flagged individually in at least six places (`validation_standard.md` §9, `HB-004` §8/§17, `RE-004`, `RE-006`, `RE-012`, `HB-006` §8) — each document correctly refuses to invent a collector that doesn't exist, but the *aggregate* signal is a structural gap: [Phase 3 — Runtime Monitoring](roadmap/implementation_plan.md#5-phase-3--runtime-monitoring) builds monitors for Layer 2 only. Nothing in Phases 1–3 produces Layer 3 evidence, yet Phase 5 (Feature Plugins) and the entire premise of multi-layer corroboration assume it exists by then.

**Tradeoff:** Adding a Layer 3 collector (API/network evidence) is a bigger engineering lift than a file/process monitor — it likely requires either instrumenting the agent's own network calls (if observable) or a proxy/capture approach, which has its own design questions (does this require MITM tooling, or can requests be observed passively?). This is exactly the kind of decision that must not be made implicitly by omission.

**Recommendation:** Add an explicit Phase 2 or Phase 3 deliverable — even if its content is "spike: determine how Layer 3 evidence can be collected at all" — so the gap is a tracked decision with an owner, not a silent absence six documents independently apologize for.

### 4.3 No Verification Workflow exists, so the knowledge base's core premise is unenforceable

[`knowledge_base/README.md`](../knowledge_base/README.md) §6 defines the Known → Verified promotion as central to the whole reverse-engineering effort, then marks the *process* for doing that promotion as `TODO`. Without it: who is allowed to mark something Verified, what evidence must be attached, and where that evidence lives (`baselines/`? `reports/`?) are all undefined. Practically, this means the knowledge base could remain 100% "Known (unverified)" indefinitely even once engineers start observing real behavior, because there's no defined mechanism to record that observation as authoritative.

**Recommendation:** This should be one of the very first process decisions ratified — before Phase 2 environment validation work begins — not left as a trailing TODO in an index document.

---

## 5. P1 — High-Priority Findings

### 5.1 Two overlapping lifecycle models are used interchangeably without a translation table

[`HB-002`](handbook/HB-002_Product_Architecture.md) §5 describes a 5-stage pipeline (Configure → Capture → Persist → Synchronize → Surface). [`validation_standard.md`](ADS/validation_standard.md) §3 describes a 4-layer evidence model (Configuration / Runtime / Synchronization / Dashboard). These are related but not isomorphic — "Persist" and "Runtime" aren't quite the same concept, and "Capture" doesn't map cleanly to any single layer. Multiple documents (`HB-004` §14, several RE docs) already informally cross-reference between the two ("these map to the capturing-but-not-persisting classes named in HB-002 §7"), which means each author is independently inventing the same mapping.

**Recommendation:** Add a small explicit stage↔layer mapping table to `validation_standard.md`, once, and have every other document reference it instead of re-deriving it. Low effort, meaningfully reduces drift risk.

### 5.2 `milestones.md` and `backlog.md` are empty but already treated as existing companion documents

[`SPRINT_ROADMAP.md`](roadmap/SPRINT_ROADMAP.md) and [`implementation_plan.md`](roadmap/implementation_plan.md) both reference these as authoritative companions. They are 0 bytes. This isn't wrong per se (they were out of scope for the original documentation pass), but as of this review they are the most conspicuous "documentation referenced but not written" gap outside the RE/HB set.

**Recommendation:** Populate at minimum a stub with the same provenance discipline used elsewhere (structure + TODO), so a reader following a cross-reference doesn't hit a blank file.

### 5.3 Dependency rules exist only as prose, with no enforcement mechanism

[`ADS/architecture.md`](ADS/architecture.md) §3 states the module dependency rules (plugins may depend on core; core must never depend on plugins) and explicitly defers enforcement ("TODO: confirm... add enforcement notes... once tooling is decided"). Prose-only architecture rules are the single most common way a "clean" architecture document diverges from the actual codebase within a few contributions — nobody violates the rule maliciously, it just erodes one convenient import at a time.

**Recommendation:** Treat "how is this rule enforced" as a Phase 1 deliverable alongside the base interfaces, not an afterthought. Even a manual review-checklist item (already partially present in `CONTRIBUTING.md` §7) is better than nothing, but a mechanical check should be the target once the toolchain is chosen.

### 5.4 No ownership assigned anywhere

Every one of the ~23 documents produced carries `**Owner:** TODO`. For a project explicitly framed as needing to be maintainable "years later" by someone else, a documentation set with zero named accountable owners is a real risk — not because the content is wrong, but because nobody is positioned to notice when it becomes wrong.

**Recommendation:** Assign at least a Documentation Owner and an Architecture Owner before Phase 1 begins. This is a one-line fix per document but a real governance gap today.

---

## 6. P2 — Medium-Priority Findings

### 6.1 Dashboard settings are double-counted across Layer 1 and Layer 4

[`validation_standard.md`](ADS/validation_standard.md) §4 marks "Dashboard settings state" as both Layer 1 (authored) and Layer 4 (observed). This is conceptually defensible, but the corroboration rule in §5 ("at least two layers... one of which must be Layer 2+") doesn't say whether a single dashboard-settings observation can satisfy *both* layers at once for corroboration purposes, or whether that would improperly let a single data source masquerade as two independent ones. This should be resolved as part of ratifying §4.1 above, not left implicit.

### 6.2 `framework/core/registry.py` scope is ambiguous

It's described as the plugin registry in [`plugin_standard.md`](ADS/plugin_standard.md), but [`ADS/architecture.md`](ADS/architecture.md) doesn't clarify whether monitors and validators are registered through the same mechanism or discovered some other way. Low cost to clarify now, higher cost to reconcile after both patterns exist in code.

### 6.3 The Finding structure is a subsection of a standard, not a standard of its own

[`validation_standard.md`](ADS/validation_standard.md) §7 defines the `what`/`where`/`why`/`evidence[]`/`verdict`/`corroboration` structure — this will likely become the single most-reused contract in the entire system (every plugin, every report, every monitor output funnels through it eventually). See §8.1 below for the recommended abstraction.

### 6.4 `docs/ADS/prompt_standard.md` remains empty and unaddressed

It exists, is referenced from `ADS/README.md`, and governs the (also empty) `prompts/` directory, but was out of scope for this pass. Worth an explicit decision: either it's needed before Phase 4 (if prompt-driven tooling is part of the automation approach) or it should be explicitly deprioritized with a note explaining why, rather than sitting as a silent gap.

### 6.5 Minor self-correction

While reviewing the full set, two small issues from this same documentation pass were found and fixed directly (not left as findings, since they were pure hygiene): `docs/ADS/coding_standards.md` §2 and §2.1 overlapped in content and have been consolidated; `CONTRIBUTING.md`'s review checklist didn't mention keeping `HB-005` (Component Inventory) or `HB-006` (Feature Specifications evidence layers) in sync, despite both documents explicitly warning about drift risk — checklist items were added.

---

## 7. P3 — Low-Priority Findings

### 7.1 No numbering authority for `EM0XX` / `HB-0XX` / `RE-0XX` identifiers

Each naming scheme's TODO independently asks "who assigns the next number." Fine at the current scale (6 plugins, 6 handbook chapters, 12 RE docs); will need an answer once more than one contributor is adding entries concurrently.

### 7.2 No data-sensitivity standard for captured evidence

EmpMonitor is an employee-monitoring product; its captures (screenshots, recordings, activity data) are inherently sensitive. The framework's own evidence/reporting output (`reports/`, `baselines/`) will likely contain or reference this same class of data. No current standard addresses retention, access control, or handling of this data at the automation-framework level. Not urgent at the documentation stage, but should be resolved before Phase 5 (Feature Plugins) starts producing real evidence artifacts from real endpoints.

### 7.3 No test/QA strategy beyond a one-line TODO

[`coding_standards.md`](ADS/coding_standards.md) §6 defers testing expectations entirely. Given the project's explicit SDET/QA framing, this likely deserves more than a TODO eventually — but is reasonably deferred until Phase 1's base models exist to be tested.

---

## 8. Suggested Better Abstractions

### 8.1 Promote the Finding schema to its own document once ratified

Once §4.1 is resolved, extract the Finding structure out of `validation_standard.md` §7 into its own document (e.g., `docs/ADS/finding_schema.md`), since it will be referenced far more often, by far more components, than any other single piece of the ADS suite. Keeping it as a subsection of another standard undersells how central it is.

### 8.2 Give the Layer 3 gap one owned tracking artifact instead of six restatements

The same unresolved gap (§4.2) is currently, correctly, independently flagged in six different documents. That's good discipline (nobody invented a fake collector to paper over it) but it means the gap has six places to go stale and zero places that track its resolution. Once `backlog.md` exists (§5.2), this gap should become a single backlog entry that every other document links to, rather than restates.

### 8.3 Make "evidence layers per feature" a required Plugin Guide checklist item, not just a handbook field

[`HB-006`](handbook/HB-006_Feature_Specifications.md) records suggested evidence layers per plugin, but nothing in [`plugin_standard.md`](ADS/plugin_standard.md) §11's checklist requires a new plugin to confirm or correct that entry. As the catalog grows, a new plugin could ship without HB-006 ever being touched. Recommend adding this to the plugin checklist directly.

## 9. Summary Table

| # | Finding | Tier | Blocks |
|---|---|---|---|
| 4.1 | Corroboration rule / verdict model unratified | P0 | Phase 1 base models |
| 4.2 | No Layer 3 evidence collector planned | P0 | Phase 3 → Phase 5 |
| 4.3 | No Verification Workflow defined | P0 | Knowledge base usefulness |
| 5.1 | Two unreconciled lifecycle models (5-stage vs. 4-layer) | P1 | Consistent failure-mode documentation |
| 5.2 | `milestones.md` / `backlog.md` empty but referenced | P1 | Sprint planning |
| 5.3 | Dependency rules unenforced | P1 | Long-term architecture integrity |
| 5.4 | No document ownership assigned | P1 | Long-term maintainability |
| 6.1 | Dashboard settings double-counted across layers | P2 | Corroboration rule clarity |
| 6.2 | Registry scope ambiguous (plugins vs. monitors/validators) | P2 | Extension consistency |
| 6.3 | Finding schema under-promoted | P2 | Reuse clarity |
| 6.4 | `prompt_standard.md` gap unaddressed | P2 | `prompts/` directory scope |
| 7.1 | No ID numbering authority | P3 | Multi-contributor scaling |
| 7.2 | No data-sensitivity standard | P3 | Phase 5 evidence handling |
| 7.3 | No test/QA strategy | P3 | Phase 1+ code quality |

## 10. Recommendation

Do not begin Phase 1 implementation until §4.1–4.3 (P0) are explicitly decided by the team — not necessarily fully detailed, but decided in shape. The P1 items should be resolved during Phase 1, in parallel with base model construction, since they inform how those models are built. P2/P3 items can be tracked in `backlog.md` once it exists (see 5.2) and addressed opportunistically.

## 10.1 Addendum — Status at Architecture Freeze (2026-07-30)

The Architecture Freeze sprint resolved the following findings after this review was written. This addendum records disposition without rewriting the findings above; the full account is in the [Architecture Freeze Report](ARCHITECTURE_FREEZE_REPORT.md).

| Finding | Disposition at freeze |
|---|---|
| 4.1 Corroboration/verdict model unratified | **Resolved** — [Validation Standard](ADS/validation_standard.md) ratified v1.0, including confidence model; thresholds configurable per this review's own recommendation |
| 4.2 No Layer 3 collector | **Resolved (design level)** — [Synchronization Monitor](design/Synchronization_Monitor.md) designed; implementation + §6 observation-strategy spike scheduled, tracked in [Validation Standard §12](ADS/validation_standard.md) |
| 4.3 No verification workflow | **Resolved** — status model + workflow ratified in [knowledge_base README §6–§7](../knowledge_base/README.md); reviewer-role assignment still open (see 5.4) |
| 5.1 Two lifecycle models | **Resolved** — stage↔layer mapping ratified in [Validation Standard §3.2](ADS/validation_standard.md) |
| 5.2 Empty milestones/backlog | **Open** — still empty; carried into freeze report as a pre-Phase-1 item |
| 5.3 Dependency-rule enforcement | **Open** — remains a Phase 1 deliverable |
| 5.4 No ownership assigned | **Open** — every document still carries Owner: TODO |
| 6.1 Dashboard settings double-counted | **Resolved** — independence rule, [Validation Standard §4.1](ADS/validation_standard.md); split into EV-006/EV-008 in the [Evidence Catalog](Evidence_Catalog.md) |
| 6.3 Finding schema under-promoted | **Partially resolved** — semantics ratified in §10 of the standard; extraction to `finding_schema.md` deferred to Phase 1 by design |
| 8.2 Layer 3 gap tracked once | **Resolved** — single tracking point is now [Validation Standard §12](ADS/validation_standard.md); six restatements updated to point at the design |
| Others (6.2, 6.4, 7.1–7.3, 8.3) | **Open** — carried into the freeze report's Remaining TODOs |

## 11. Cross References

- [Validation Standard](ADS/validation_standard.md)
- [Implementation Plan](roadmap/implementation_plan.md)
- [Knowledge Base Index](../knowledge_base/README.md)
- [Repository Guide](Repository_Guide.md)

---
**Document Status:** Complete for this documentation pass — supersedes no prior review (first review conducted)
**Owner:** TODO
**Last Updated:** 2026-07-30
