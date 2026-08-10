# Reverse Engineering Knowledge Base

## 1. Purpose

This knowledge base documents the **internal behavior of EmpMonitor** as established through investigation. These are engineering documents written for automation developers — not user documentation, not product marketing, and not framework documentation.

Their function is to make automation development possible: you cannot validate a system you do not understand, and you cannot localize a failure without knowing what the correct internal behavior looks like.

## 2. Provenance Discipline (Mandatory)

Every RE document separates:

| Section | Contains | Rule |
|---|---|---|
| **Known Behaviour** | Stated by stakeholders/charter, not independently confirmed | Must be labeled as unverified |
| **Verified Behaviour** | Directly observed, with a recorded evidence reference and product version | Must cite how it was verified |
| **TODO** | Not yet established | Never fill with assumption |

**Do not invent EmpMonitor behavior.** An empty section is correct and useful; a plausible guess is a liability that will be trusted years later by someone who cannot tell it was a guess.

This section describes how a document is *structured*. Section §6 below defines the **verification status** every individual claim must now carry, and §7 the **workflow** for promoting a claim between statuses. Provenance discipline (this section) and verification status (§6) are complementary: provenance says *where a claim came from*; status says *how far it has been confirmed*.

## 3. Document Index

| ID | Document | Subject | Primary Evidence Layer |
|---|---|---|---|
| RE-001 | [Agent Startup](RE-001_Agent_Startup.md) | How the agent initializes | 2 |
| RE-002 | [Watchdog Behaviour](RE-002_Watchdog_Behaviour.md) | Self-recovery mechanism | 2 |
| RE-003 | [Scheduler](RE-003_Scheduler.md) | Timed/scheduled behavior | 2 |
| RE-004 | [Upload Pipeline](RE-004_Upload_Pipeline.md) | Capture → server transmission | 3 |
| RE-005 | [Configuration Loading](RE-005_Configuration_Loading.md) | How config is read and applied | 1 |
| RE-006 | [API Flow](RE-006_API_Flow.md) | Agent/dashboard ↔ server contracts | 3 |
| RE-007 | [SQLite Database](RE-007_SQLite_Database.md) | Local schema and contents | 2 |
| RE-008 | [Logging System](RE-008_Logging_System.md) | Agent log output | 2 |
| RE-009 | [Runtime Components](RE-009_Runtime_Components.md) | Processes and Windows services | 2 |
| RE-010 | [Folder Structure](RE-010_Folder_Structure.md) | On-disk layout | 2 |
| RE-011 | [Recovery Behaviour](RE-011_Recovery_Behaviour.md) | Failure recovery | 2 |
| RE-012 | [Offline Synchronization](RE-012_Offline_Synchronization.md) | Behavior without connectivity | 3 |
| RE-013 | [Agent State Machine](RE-013_Agent_State_Machine.md) | Expected agent lifecycle states/transitions | 2, 3 |

## 4. Relationship to Other Documentation

| Question | Document |
|---|---|
| What is EmpMonitor and what are we validating? | [HB-001](../docs/handbook/HB-001_Product_Overview.md) |
| How does the ecosystem fit together? | [HB-002](../docs/handbook/HB-002_Product_Architecture.md) |
| How does *this component* behave internally? | This knowledge base |
| How must the framework validate it? | [Validation Standard](../docs/ADS/validation_standard.md) |
| How do I build the plugin that validates it? | [Plugin Development Guide](../docs/ADS/plugin_standard.md) |

## 5. Document Template

New RE documents must follow the section order below, so that any engineer can navigate an unfamiliar document by position:

1. Purpose
2. Scope
3. Architecture
4. Sequence / Flow (diagram where appropriate)
5. Known Behaviour *(unverified)*
6. Verified Behaviour *(with evidence + version)*
7. Configuration Inputs
8. Known Files
9. Known APIs
10. Storage / SQLite
11. Logs
12. Failure Modes
13. Recovery
14. Troubleshooting
15. Evidence Sources for Automation
16. Open Questions / TODO
17. Future Expansion
18. Version Notes
19. Cross References

Sections that do not apply to a given subject should be retained with an explicit "Not applicable" note rather than deleted — an absent section is ambiguous, an explicit one is information.

## 6. Verification Status Model (Ratified)

Every substantive behavioral claim in an RE document must carry exactly one **verification status**. This replaces the informal Known/TODO split with a four-level model that tells a future reader the confidence of any single statement at a glance.

| Status | Meaning | May a plugin rely on it? |
|---|---|---|
| **Hypothesis** | Assumed or charter-stated; not independently observed. (Supersedes the old "Known (unverified)" label.) | No — treat as unproven; design for it being wrong |
| **Partially Verified** | Observed at least once, but not across all required conditions/versions, or with a single (non-corroborated) evidence source | With caution, and only corroborated per the Validation Standard |
| **Verified** | Directly observed with recorded evidence, corroborated per the [Validation Standard](../docs/ADS/validation_standard.md), against a recorded product version | Yes |
| **Deprecated** | Was Verified/Partially Verified, but is no longer true (product changed) or has been superseded | No — retained for history only, must state what replaced it |

### 6.1 Required Metadata for a Verified or Partially Verified Claim

Any claim marked **Verified** or **Partially Verified** must record, adjacent to the claim (or in the document's Verified Behaviour table):

| Field | Meaning |
|---|---|
| `Verified On` | Date the observation was made |
| `Verified Against Version` | EmpMonitor product/build version observed |
| `Evidence Source` | The [Evidence Catalog](../docs/Evidence_Catalog.md) `EV-NNN` ID(s) that substantiate it |
| `Verification Method` | How it was observed (what was done to produce the evidence) |
| `Reviewer` | Who confirmed the promotion |
| `Last Review Date` | When the claim was last re-checked against the product |

A claim marked Verified without all six fields is non-conformant and must be demoted to Hypothesis in review.

### 6.2 Status and Confidence Are Distinct

A claim's **verification status** (this section) is about *how well the fact is established*. A finding's **confidence** ([Validation Standard §8](../docs/ADS/validation_standard.md)) is about *how strongly evidence supports a runtime conclusion*. A plugin must not treat a Hypothesis-status fact as a High-confidence input, regardless of how plausible it seems.

## 7. Verification Workflow (Ratified)

Promotion of a claim between statuses follows this process:

1. **Observe.** Collect evidence via the appropriate catalog source(s) ([Evidence Catalog](../docs/Evidence_Catalog.md)). A single source supports at most **Partially Verified**; promotion to **Verified** requires corroboration per the [Validation Standard §5](../docs/ADS/validation_standard.md).
2. **Record evidence.** Store the supporting artifact under `baselines/` (durable reference evidence) and reference it by its `EV-NNN` ID and artifact path. Run-time evidence lives under `reports/`; canonical reference evidence that defines "correct" lives under `baselines/`.
3. **Fill the metadata.** Populate all six §6.1 fields on the claim.
4. **Review.** A reviewer other than the author confirms the evidence supports the claimed status. The reviewer is recorded.
5. **Promote.** Update the claim's status and, in the same change, update [HB-005 — Component Inventory](../docs/handbook/HB-005_Component_Inventory.md) if the claim concerns a catalogued component (per the drift rule in that document).
6. **Re-review on version change.** When a new EmpMonitor version is encountered, Verified claims are re-checked; if broken, they move to **Deprecated** with a pointer to the superseding claim, and `Last Review Date` is updated.

> **TODO (process ownership):** assign the standing Reviewer role / reviewer pool. The workflow is ratified; the named owner is still [TODO](../docs/ARCHITECTURE_REVIEW.md) pending the ownership decision in the Architecture Review.

## 8. Migration Note

The twelve existing RE documents (RE-001–RE-012) and RE-013 were authored under the earlier "Known (unverified)" convention. Under this model, every claim currently labeled "Known (unverified)" is **Hypothesis** status, and every "Verified Behaviour" table is empty (no claim has yet completed the §7 workflow). Documents may be relabeled to the new vocabulary opportunistically; until a document is relabeled, read "Known (unverified)" as **Hypothesis**.

---
**Document Status:** Active — index established; verification status model and workflow ratified (§6–§7)
**Owner:** TODO
**Last Updated:** 2026-07-30
