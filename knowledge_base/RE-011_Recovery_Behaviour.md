# RE-011 — Recovery Behaviour

## 1. Purpose

This document records what is known and verified about how the EmpMonitor Windows Agent is **believed to recover** from crashes, Windows service stops, or corrupted local state, for use by automation developers building Layer 2 (Runtime) validation of failure/recovery scenarios.

## 2. Scope

Covers the agent's own recovery mechanisms on the endpoint: process/service restart behaviour, handling of corrupted local state (SQLite, configuration, logs), and any self-healing logic. Does not cover the offline synchronization recovery path once connectivity returns (see [RE-012](RE-012_Offline_Synchronization.md)), which is a related but distinct concern at the Synchronization layer.

## 3. Architecture

> **TODO:** Nothing is yet established about what mechanism(s) drive recovery — a Windows service restart policy, a dedicated watchdog process, scheduler-driven periodic checks, or some combination. This document depends directly on [RE-002 — Watchdog Behaviour](RE-002_Watchdog_Behaviour.md), whose existence is itself unverified (see [HB-001 §6](../docs/handbook/HB-001_Product_Overview.md)). Any recovery behaviour described here that assumes a watchdog exists must be treated as doubly unverified until RE-002 confirms the watchdog itself.

## 4. Sequence / Flow

> **TODO:** Nothing is yet established about the sequence of events following a crash or stop (detection → decision → restart → state reconciliation). No sequence diagram can be responsibly drawn yet.

```mermaid
flowchart LR
    CRASH[Agent Crash/Stop] --> DETECT["Detection Mechanism - unverified"]
    DETECT --> RESTART["Restart Action - unverified"]
    RESTART --> RECONCILE["State Reconciliation - unverified"]
```

> Diagram represents an assumed, unverified relationship only.

## 5. Known Behaviour (unverified)

- HB-002 lists "Recovery" as an ecosystem-level concern with candidate mechanisms to investigate: "self-recovery via watchdog, service restart, scheduler-driven restart, etc." ([HB-002 §8](../docs/handbook/HB-002_Product_Architecture.md)), stated as a TODO investigation list rather than confirmed behaviour.
- HB-001's terminology table flags "Watchdog" as a suspected self-recovery mechanism, existence unverified.

## 6. Verified Behaviour (with evidence + version)

> **TODO:** No behaviour has been independently verified yet. Any entry added here must cite the evidence artifact and the EmpMonitor product version it was observed against.

## 7. Configuration Inputs

> **TODO:** Nothing is known about whether recovery behaviour is configurable (e.g., restart delay, retry count) via local configuration (`config.js` / `empm.ini`, see [RE-005](RE-005_Configuration_Loading.md)) or via Windows service recovery settings.

## 8. Known Files

> **TODO:** No file(s) associated with recovery state (e.g., a crash marker, last-known-good state file) have been confirmed.

## 9. Known APIs

Not applicable to this subject — recovery is a local/endpoint behaviour, not a documented API surface, unless verified otherwise.

## 10. Storage / SQLite

> **TODO:** Nothing is known about whether corrupted SQLite state (see [RE-007](RE-007_SQLite_Database.md)) is detected and repaired, recreated, or left as-is by recovery logic.

## 11. Logs

> **TODO:** Nothing is known about whether recovery events (crash detected, restart performed) are recorded in agent logs (see [RE-008](RE-008_Logging_System.md)).

## 12. Failure Modes

> **TODO:** Candidate classes to investigate: process crash not detected, process crash detected but not restarted, service stopped and not auto-restarted, restart occurs but local state (SQLite/config) not reconciled, repeated crash-restart loop, corrupted SQLite database not detected on restart.

## 13. Recovery

> **TODO:** This section is the subject of the document itself and is currently empty pending verification. Do not populate with assumed mechanisms — record only what is confirmed by direct observation, with evidence and version per §6.

## 14. Troubleshooting

> **TODO:** No troubleshooting guidance can be written until a recovery mechanism (if any) is confirmed to exist.

## 15. Evidence Sources for Automation

| Source | Layer | Collector | Status |
|---|---|---|---|
| Process/service state before and after induced failure | 2 | `framework/monitors/runtime_monitor.py` | Scaffolded, unimplemented (0 lines) — see [RE-009](RE-009_Runtime_Components.md) |
| Log content around failure/restart window | 2 | `framework/monitors/log_monitor.py` | Scaffolded, unimplemented (0 lines) — see [RE-008](RE-008_Logging_System.md) |
| SQLite state before and after induced failure | 2 | `framework/monitors/sqlite_monitor.py` | Scaffolded, unimplemented (0 lines) — see [RE-007](RE-007_SQLite_Database.md) |

No dedicated recovery-testing collector exists in the scaffold; recovery validation would need to compose the monitors above around an induced-failure test scenario.

## 16. Open Questions / TODO

- Does a watchdog mechanism exist at all? (Blocking question — see [RE-002](RE-002_Watchdog_Behaviour.md))
- If a crash/stop occurs, is it detected, and by what?
- How quickly does recovery occur, if it occurs?
- Is local state (SQLite, in-flight uploads, config) reconciled on restart, or does data loss occur?
- Are recovery events logged?
- Is there a maximum retry/restart count before the agent gives up, if any?

## 17. Future Expansion

> **TODO:** Once a recovery mechanism is confirmed, document any changes to recovery behaviour observed across EmpMonitor releases.

## 18. Version Notes

> **TODO:** No EmpMonitor version has been verified against for this subject. All statements in this document are unversioned.

## 19. Cross References

- [Knowledge Base Index](README.md)
- [HB-001 — Product Overview](../docs/handbook/HB-001_Product_Overview.md)
- [HB-002 — Product Architecture](../docs/handbook/HB-002_Product_Architecture.md)
- [Validation Standard](../docs/ADS/validation_standard.md)
- [RE-002 — Watchdog Behaviour](RE-002_Watchdog_Behaviour.md)
- [RE-007 — SQLite Database](RE-007_SQLite_Database.md)
- [RE-008 — Logging System](RE-008_Logging_System.md)
- [RE-009 — Runtime Components](RE-009_Runtime_Components.md)
- [RE-012 — Offline Synchronization](RE-012_Offline_Synchronization.md)

---
**Document Status:** Draft — structural scaffold only; no verified behaviour established
**Owner:** TODO
**Last Updated:** 2026-07-30
