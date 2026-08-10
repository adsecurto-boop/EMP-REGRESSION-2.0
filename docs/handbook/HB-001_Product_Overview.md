# HB-001 — EmpMonitor Product Overview

## 1. Purpose

This chapter establishes the baseline understanding of **EmpMonitor — the product under validation**. It defines the ecosystem components the automation framework must validate, the terminology used across the handbook, and the provenance rules that govern what may be written here.

> **Important:** This handbook documents the *product* (EmpMonitor). Documentation about the *automation framework itself* lives in the [README](../../README.md), the [Repository Guide](../Repository_Guide.md), and the [ADS suite](../ADS/README.md). Do not mix the two.

## 2. Provenance Rules

Because the framework's conclusions are only as trustworthy as its understanding of the product, this handbook distinguishes:

| Class | Meaning | Marking |
|---|---|---|
| **Known** | Stated by stakeholders / project charter, not yet independently verified | Listed under "Known Behaviour" |
| **Verified** | Confirmed by direct observation on a real installation, with evidence | Listed under "Verified Behaviour", with evidence reference |
| **Unknown** | Not yet established | `TODO` |

**Never invent EmpMonitor behavior.** If it is not known or verified, it is a TODO.

## 3. What EmpMonitor Is

EmpMonitor is an employee monitoring product. Its ecosystem, as identified for validation purposes, comprises:

| Component | Description | Detailed In |
|---|---|---|
| Windows Agent | Endpoint software installed on monitored Windows machines | [HB-003](HB-003_Agent_Architecture.md), [RE-001](../../knowledge_base/RE-001_Agent_Startup.md) |
| Dashboard | Web-based management/reporting interface | [HB-002 §5](HB-002_Product_Architecture.md) |
| APIs | Server-side interfaces the agent and dashboard communicate through | [RE-006](../../knowledge_base/RE-006_API_Flow.md) |
| Local SQLite Database | Agent-side local storage | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| Local Configuration | Agent-side configuration artifacts (e.g., `config.js`, `empm.ini`) | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) |
| Local Logs | Agent-side log output | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |
| Runtime Processes | Agent processes running on the endpoint | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| Windows Services | Service(s) backing the agent | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| Scheduler | Scheduled task behavior on the endpoint | [RE-003](../../knowledge_base/RE-003_Scheduler.md) |
| File System | Agent folder structure and file artifacts | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| End-to-End Synchronization | Data flow from endpoint capture to dashboard visibility | [RE-012](../../knowledge_base/RE-012_Offline_Synchronization.md) |

> **TODO:** Verify component names, versions, and exact artifact names on a real installation and promote entries from Known to Verified.

## 4. Feature Areas Under Validation

The validation scope is the **fourteen feature profiles in `config/features.json`**, each specified in [HB-006](HB-006_Feature_Specifications.md) and mapping to the plugin catalog (see [Plugin Development Guide](../ADS/plugin_standard.md)).

`config/features.json` is authoritative for every status below; the statuses are copied from it, not restated. Where this table and that file disagree, the file is correct and this table is stale. The vocabulary is the four-status model of [knowledge_base README §6](../../knowledge_base/README.md) — **Hypothesis**, **Partially Verified**, **Verified**, **Deprecated**; no feature is currently Deprecated.

| ID | Feature Area | Status | Specification |
|---|---|---|---|
| `EM010_Screenshots` | Screenshots | Partially Verified | [HB-006 §2](HB-006_Feature_Specifications.md#2-em010_screenshots--screenshots) |
| `EM011_ScreenRecording` | Screen Recording | Partially Verified | [HB-006 §3](HB-006_Feature_Specifications.md#3-em011_screenrecording--screen-recording) |
| `EM012_LiveMonitoring` | Live Monitoring | Partially Verified | [HB-006 §4](HB-006_Feature_Specifications.md#4-em012_livemonitoring--live-monitoring) |
| `EM013_Attendance` | Attendance | Partially Verified | [HB-006 §5](HB-006_Feature_Specifications.md#5-em013_attendance--attendance) |
| `EM014_IdleTime` | Idle Time | Partially Verified | [HB-006 §6](HB-006_Feature_Specifications.md#6-em014_idletime--idle-time) |
| `EM015_Timesheet` | Timesheet | Hypothesis | [HB-006 §7](HB-006_Feature_Specifications.md#7-em015_timesheet--timesheet) |
| `EM016_Keystrokes` | Keystrokes | Hypothesis | [HB-006 §8](HB-006_Feature_Specifications.md#8-em016_keystrokes--keystrokes) |
| `EM017_ApplicationUsage` | Application Usage | Partially Verified | [HB-006 §9](HB-006_Feature_Specifications.md#9-em017_applicationusage--application-usage) |
| `EM018_WebsiteUsage` | Website Usage | Partially Verified | [HB-006 §10](HB-006_Feature_Specifications.md#10-em018_websiteusage--website-usage) |
| `EM019_UsbDetection` | USB Detection | Partially Verified | [HB-006 §11](HB-006_Feature_Specifications.md#11-em019_usbdetection--usb-detection) |
| `EM020_Webcam` | Webcam | Hypothesis | [HB-006 §12](HB-006_Feature_Specifications.md#12-em020_webcam--webcam) |
| `EM021_FaceDetection` | Face Detection | Hypothesis | [HB-006 §13](HB-006_Feature_Specifications.md#13-em021_facedetection--face-detection) |
| `EM022_Productivity` | Productivity | Hypothesis | [HB-006 §14](HB-006_Feature_Specifications.md#14-em022_productivity--productivity) |
| `EM023_EmailMonitoring` | Email Monitoring | Verified | [HB-006 §15](HB-006_Feature_Specifications.md#15-em023_emailmonitoring--email-monitoring) |

One **Verified**, eight **Partially Verified**, five **Hypothesis**.

### 4.1 Unprofiled — `EM001_Login` and `EM002_UserManagement`

Neither has a profile in `config/features.json`, and neither has an HB-006 section. Both are **dashboard-side concerns, not agent features**: authentication and user-account administration are exercised through the dashboard, and **the dashboard has never been observed** — no Layer 4 collector exists. No agent-side artifact was attributed to either. They are absent by design rather than by oversight, and nothing in the handbook specifies them ([HB-006 §1.1](HB-006_Feature_Specifications.md#11-feature-id-migration-map-inbound-links)).

The `[auth]` section of `empm.ini`, observed present while a user was signed in and absent afterwards ([RE-005](../../knowledge_base/RE-005_Configuration_Loading.md)), is a configuration observation only — not a Login feature specification.

### 4.2 Retired Scaffold IDs

This table previously listed the `EM001`–`EM006` scaffold. Four of those six are superseded by IDs above; the retired numbers are **not reissued**.

| Retired ID | Superseded by |
|---|---|
| `EM003` — Attendance | `EM013_Attendance` ([HB-006 §5](HB-006_Feature_Specifications.md#5-em013_attendance--attendance)) |
| `EM004` — Live Monitoring | `EM012_LiveMonitoring` ([HB-006 §4](HB-006_Feature_Specifications.md#4-em012_livemonitoring--live-monitoring)) |
| `EM005` — Screenshots | `EM010_Screenshots` ([HB-006 §2](HB-006_Feature_Specifications.md#2-em010_screenshots--screenshots)) |
| `EM006` — Screen Recording | `EM011_ScreenRecording` ([HB-006 §3](HB-006_Feature_Specifications.md#3-em011_screenrecording--screen-recording)) |
| `EM001` — Login | nothing — unprofiled (§4.1) |
| `EM002` — User Management | nothing — unprofiled (§4.1) |

Feature IDs start at `EM010` because `EM001` is double-booked between the retired `EM001_Login` scaffold and the implemented `EM001_Synchronization` plugin; `EM002`–`EM009` are a deliberate gap ([HB-006 §1.2](HB-006_Feature_Specifications.md#12-plugin-identifier-collision--em001), [Architecture Review — Phase 4 §5](../ARCHITECTURE_REVIEW_PHASE_4.md)).

## 5. Why This Product Needs Multi-Source Validation

EmpMonitor spans an endpoint agent, local storage, a sync pipeline, server APIs, and a web dashboard. A feature can appear healthy at one layer while broken at another (e.g., captures written locally but never uploaded). The framework therefore validates every feature through independent evidence sources across four layers — see the [Validation Standard](../ADS/validation_standard.md).

## 6. Terminology

| Term | Definition |
|---|---|
| Agent | The EmpMonitor Windows endpoint software |
| Endpoint | A monitored Windows machine running the Agent |
| Capture | A unit of monitored data produced by the Agent (screenshot, recording, activity record, etc.) |
| Upload Queue | The agent-side mechanism holding captures pending transmission — **TODO: verify mechanism** |
| Watchdog | Suspected agent self-recovery mechanism — **TODO: verify existence and behavior** ([RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md)) |
| Evidence Layer | One of the four validation layers defined in the [Validation Standard](../ADS/validation_standard.md) |

## 7. Version Notes

> **TODO:** Record the EmpMonitor version(s) this handbook has been verified against. Until then, all "Verified" claims are unversioned and should be treated with caution.

## 8. Cross References

- [HB-002 — Product Architecture](HB-002_Product_Architecture.md)
- [Validation Standard](../ADS/validation_standard.md)
- [Reverse Engineering Knowledge Base](../../knowledge_base/README.md)

---
**Document Status:** Draft — structure established; product facts pending verification. §4 repointed to the fourteen `EM010`–`EM023` feature profiles with statuses copied from `config/features.json`; `EM001_Login` and `EM002_UserManagement` recorded as unprofiled.
**Owner:** TODO
**Last Updated:** 2026-07-31
