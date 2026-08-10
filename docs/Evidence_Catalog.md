# Evidence Catalog

> **Authoritative registry.** This document is the single master registry of every evidence source the framework may use. It is referenced by the [Validation Standard](ADS/validation_standard.md), the [Synchronization Monitor Design](design/Synchronization_Monitor.md), and every feature specification in [HB-006](handbook/HB-006_Feature_Specifications.md). **A source not registered here may not be cited as evidence** ([Validation Standard §4](ADS/validation_standard.md)).

## 1. Purpose

The [Validation Standard](ADS/validation_standard.md) governs *how* evidence combines into conclusions; this catalog governs *what evidence exists*. Splitting the two means the combination rules never have to change when a new source is added — a new source is a new row here, nothing more.

## 2. How to Read This Catalog

| Column | Meaning |
|---|---|
| **Evidence ID** | Stable identifier `EV-NNN`. Assigned sequentially, never reused (see [Naming Convention](ADS/naming_convention.md)). |
| **Name** | The artifact/signal observed. |
| **Description** | What it is and what it tells us. |
| **Collector** | The framework component responsible for observing it. Names ending `.py` refer to scaffold files under `framework/`; where the file is an empty scaffold today, that is noted in §4. |
| **Confidence** | The source's *inherent reliability* rating (`High`/`Medium`/`Low`), consumed by the confidence calculation in [Validation Standard §8.2](ADS/validation_standard.md). This is the reliability of the source, **not** the confidence of any particular finding. |
| **Layer** | The evidence layer (L1–L4) this source primarily serves ([Validation Standard §3](ADS/validation_standard.md)). |
| **Dependencies** | Other EV sources or product facts this source relies on. |
| **Future Expansion** | Known ways this row is expected to grow. |

### 2.1 Confidence Rating Rubric (source-level)

| Rating | Criteria |
|---|---|
| **High** | Direct observation of a durable, structured artifact (file contents, DB rows, service state) with low ambiguity. |
| **Medium** | Observation subject to rendering, timing, or interpretation (UI state, log-line phrasing). |
| **Low** | Inferred or absence-based signals; admissible only as corroboration ([Validation Standard §7 rule 4](ADS/validation_standard.md)). |

## 3. Layer Coverage Summary

| Layer | Sources Registered | Collector Status |
|---|---|---|
| L1 — Configuration | EV-001, EV-002, EV-008, EV-016 | Implemented except EV-008 (dashboard-authored settings) |
| L2 — Runtime | EV-003, EV-004, EV-005, EV-009, EV-010, EV-011, EV-012, EV-013, EV-014, EV-015 | Implemented except EV-004 (log parsing) and EV-009 (scheduled tasks) |
| L3 — Synchronization | EV-007, EV-017 | **Implemented** — `framework/monitors/sync_monitor.py`, three passive strategies (log, queue, connection state) |
| L4 — Dashboard | EV-006 | Scaffold present, unimplemented |

## 4. Registry

| Evidence ID | Name | Description | Collector | Confidence | Layer | Dependencies | Future Expansion |
|---|---|---|---|---|---|---|---|
| **EV-001** | `config.js` | EmpMonitor endpoint configuration file contents | `framework/validators/configuration.py` | High | L1 | [RE-005](../knowledge_base/RE-005_Configuration_Loading.md) — location/keys TODO | Per-key semantic validation once schema known |
| **EV-002** | `empm.ini` | EmpMonitor INI configuration file contents | `framework/validators/configuration.py` | High | L1 | [RE-005](../knowledge_base/RE-005_Configuration_Loading.md) — location/keys TODO | Diff vs. dashboard-authored intent (EV-008) |
| **EV-003** | Local SQLite | Local database file presence, schema, and row contents | `framework/monitors/sqlite_monitor.py` | High | L2 | [RE-007](../knowledge_base/RE-007_SQLite_Database.md) — file/schema TODO | Row-lifecycle tracking (captured→synced); queue-state source for EV-007 |
| **EV-004** | Agent Logs | Agent log file content and parsed events | `framework/monitors/log_monitor.py` | Medium | L2 | [RE-008](../knowledge_base/RE-008_Logging_System.md) — files/format TODO | Structured event extraction once log format known |
| **EV-005** | Windows Service state | Presence and running state of the backing Windows service(s) | `framework/monitors/runtime_monitor.py` | High | L2 | [RE-009](../knowledge_base/RE-009_Runtime_Components.md) — service names TODO | Service recovery-setting inspection |
| **EV-006** | Dashboard UI state | Rendered dashboard state: feature visibility, timestamps, user status | `framework/validators/dashboard.py` | Medium | L4 | [RE-006](../knowledge_base/RE-006_API_Flow.md); HB-002 §6 | Timestamp-freshness and per-feature visibility assertions |
| **EV-007** | Synchronization activity | Endpoint↔server sync outcomes, cycle cadence, API reply codes, queue drain, retries | `framework/monitors/sync_monitor.py` | High | L3 | [Sync Monitor Design](design/Synchronization_Monitor.md); [RE-004](../knowledge_base/RE-004_Upload_Pipeline.md); [RE-006](../knowledge_base/RE-006_API_Flow.md); observation strategy TODO (§6 there) | Sub-metrics: latency, retry curve, WebSocket lifecycle (if confirmed) |
| **EV-008** | Dashboard settings (authored) | Feature configuration as authored in the dashboard, treated as L1 intent | `framework/validators/dashboard.py` | Medium | L1 | [RE-005](../knowledge_base/RE-005_Configuration_Loading.md); independence rule [Validation Standard §4.1](ADS/validation_standard.md) | Divergence detection vs. local config (EV-001/EV-002) |
| **EV-009** | Scheduled task state | Presence/state of EmpMonitor scheduled task entries | `framework/monitors/scheduler_monitor.py` | High | L2 | [RE-003](../knowledge_base/RE-003_Scheduler.md) — task names TODO | Trigger/frequency verification |
| **EV-010** | File system artifacts | Capture output, staging/queue folders, and other on-disk artifacts | `framework/monitors/folder_monitor.py` | High | L2 | [RE-010](../knowledge_base/RE-010_Folder_Structure.md) — paths TODO | Queue-depth series (file-based) as source for EV-007 |
| **EV-011** | Resource usage (CPU/RAM) | Process resource consumption of the agent | `framework/monitors/runtime_monitor.py` | Medium | L2 | [RE-009](../knowledge_base/RE-009_Runtime_Components.md) | Baseline/threshold comparison for `DEGRADED` detection |
| **EV-012** | Host OS / platform identification | Windows edition, build number and architecture of the monitored endpoint. Establishes the platform context every other L2 observation is scoped to, and is what makes a Verified claim's `Verified Against Version` meaningful | `framework/validators/environment.py` | High | L2 | None — this is a host fact, independent of EmpMonitor | Multi-version matrix support; per-OS expectation sets as paths/behaviour are found to vary |
| **EV-013** | Executable file metadata | File version resource and Authenticode signature status of EmpMonitor binaries | `framework/monitors/executable_monitor.py` | High | L2 | [RE-009](../knowledge_base/RE-009_Runtime_Components.md); [RE-010](../knowledge_base/RE-010_Folder_Structure.md) — binary paths | Signature-validity assertions as a tamper signal; intra-install version-skew detection (gui vs. service) |
| **EV-014** | Network reachability | Host-level DNS resolution and outbound TCP availability | `framework/validators/environment.py` | Medium | L2 | None — a host fact | Per-endpoint reachability once the server contract is verified |
| **EV-015** | System clock and time zone | Local time, time zone, and measured drift against the OS time source | `framework/validators/environment.py` | High | L2 | `w32tm` availability | Drift trending across runs; correlation with dashboard timestamp checks |
| **EV-016** | Windows registry | Configured registry values, when any are documented | `framework/validators/configuration.py` | High | L1 | No EmpMonitor registry key is documented, so none is read by default | Populate once a key is verified |
| **EV-017** | Agent network connection state | Which agent process holds which connection, connection states, listening endpoints, local IPC topology | `framework/monitors/sync_monitor.py` | Medium | L3 | [RE-006](../knowledge_base/RE-006_API_Flow.md); agent process names | Per-endpoint attribution if a passive strategy for it is found |

> **Note on EV-012 / EV-013 (registered 2026-07-30):** both were added when the first real installation was observed and neither could be cited under an existing row. **EV-012** is distinct from EV-005/EV-009/EV-010 in that it describes the *host*, not EmpMonitor — it is the source that substantiates the platform half of `Verified Against Version`. **EV-013** is distinct from EV-010 because file *presence* and file *metadata* are different observations with different failure meanings: EV-010 answers "is the binary there", EV-013 answers "which build is it, and is it authentically signed". Both were exercised by the `EM000_EnvironmentValidator` plugin rather than by their assigned collectors, which remain empty scaffolds (§5).

> **Note on EV-005 / EV-011:** both are served by `runtime_monitor.py` but are registered as **distinct evidence sources** because they answer different questions (service *exists and runs* vs. process *consumes resources normally*) and carry different confidence ratings. The independence rule ([Validation Standard §4.1](ADS/validation_standard.md)) still applies — two readings of the same underlying process do not independently corroborate each other merely because they have different EV IDs.

## 5. Collector Implementation Status

Every collector referenced above except the Synchronization Monitor exists as an **empty scaffold file** (0 lines) in the current repository; the Synchronization Monitor does not exist even as a scaffold and is specified only in its [design document](design/Synchronization_Monitor.md). No evidence can actually be collected **by these collectors** until the [Implementation Plan](roadmap/implementation_plan.md) phases build them out. This catalog registers *intent and assignment*; it does not assert that collection works today.

**One qualification as of 2026-07-30:** EV-001, EV-002, EV-003, EV-005, EV-010, EV-011, EV-012 and EV-013 have now each yielded real evidence at least once, via the `EM000_EnvironmentValidator` plugin plus direct filesystem inspection rather than via their assigned collectors. The findings are recorded in [RE-005](../knowledge_base/RE-005_Configuration_Loading.md), [RE-006](../knowledge_base/RE-006_API_Flow.md), [RE-007](../knowledge_base/RE-007_SQLite_Database.md), [RE-008](../knowledge_base/RE-008_Logging_System.md), [RE-009](../knowledge_base/RE-009_Runtime_Components.md), [RE-010](../knowledge_base/RE-010_Folder_Structure.md), [RE-012](../knowledge_base/RE-012_Offline_Synchronization.md) and inventoried in [HB-005](handbook/HB-005_Component_Inventory.md). Two constraints on how these sources may be re-read emerged from that pass and bind future collector implementations:

- **EV-003 is count-only.** The local database holds captured employee monitoring data. Table names and row counts are readable; **row contents are not** ([RE-007 §6.0](../knowledge_base/RE-007_SQLite_Database.md)).
- **EV-001 and EV-002 carry secrets.** `config.js` holds deployment endpoint URLs; `empm.ini` `[auth]` holds credential keys. Collectors must assert on structure and never emit values ([RE-005 §6.0](../knowledge_base/RE-005_Configuration_Loading.md)).

EV-003 also gained an unanticipated Layer 3 use: `pending_*` table row counts serve as an upload-queue-depth metric, partially mitigating the missing Synchronization Monitor ([RE-012](../knowledge_base/RE-012_Offline_Synchronization.md)). EV-004's collector was **not** exercised beyond locating log files — no log content has been read, so its Medium confidence rating remains untested.

## 6. Adding an Evidence Source — Rules

1. Assign the next sequential `EV-NNN`; never reuse a retired ID.
2. Every source must name a single responsible collector (no orphan evidence).
3. Assign a source-level confidence per the §2.1 rubric — this is inherent reliability, decided here, and is an input to (not a substitute for) the per-finding confidence computed in [Validation Standard §8.2](ADS/validation_standard.md).
4. A source must map to exactly one **primary** layer; cross-layer artifacts (e.g., dashboard settings) are split into separate rows per intent (EV-006 vs. EV-008), honoring the independence rule.
5. Update the [Validation Standard](ADS/validation_standard.md) only if the source introduces a new *combination* rule; otherwise this catalog is the only file that changes.

## 6.1 Keeping This Catalog and Its Config Mirror in Step

This registry exists twice: this document is authoritative for humans, and the
`evidence.sources` block of `config/framework.json` is authoritative for the running
framework. That duplication was recorded as the highest-severity long-term risk in
[Implementation Review §9.1](IMPLEMENTATION_REVIEW.md) — and it then happened: four
sources were added to configuration without being documented here, and one collector
was mis-attributed.

A check now enforces agreement:

```bash
python scripts/check_evidence_catalog.py
```

It compares identifiers, layers, reliabilities, and collector attributions, and exits
non-zero on any divergence. Layer and reliability must match exactly because both feed
the confidence calculation in [Validation Standard §8.2](ADS/validation_standard.md);
a silent disagreement there changes computed verdicts. Run it with any change to either
file.

## 7. Cross References

- [Validation Standard](ADS/validation_standard.md) — combination/corroboration/confidence rules
- [Synchronization Monitor Design](design/Synchronization_Monitor.md) — EV-007 collector
- [Reverse Engineering Knowledge Base](../knowledge_base/README.md) — where each source's product facts are documented
- [HB-006 — Feature Specifications](handbook/HB-006_Feature_Specifications.md) — consumes this catalog per feature
- [Naming Convention](ADS/naming_convention.md) — EV-NNN identifier rule

---
**Document Status:** Active — registry established; **EV-012 and EV-013 registered 2026-07-30**; all assigned collectors remain unimplemented, though eight sources have now yielded evidence via the `EM000_EnvironmentValidator` plugin (see §5)
**Owner:** TODO
**Last Updated:** 2026-07-30
