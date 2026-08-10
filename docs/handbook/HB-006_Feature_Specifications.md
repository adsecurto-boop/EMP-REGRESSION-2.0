# HB-006 — EmpMonitor Feature Specifications

## 1. Purpose and Scope

This chapter governs plugin *behavioral scope* — what each feature area is expected to do, and which [evidence layers](../ADS/validation_standard.md) apply to it — per [Plugin Development Guide §10](../ADS/plugin_standard.md). Plugin *structure* (directory layout, registration, interface contract) is **not** covered here; see [plugin_standard.md](../ADS/plugin_standard.md).

Each feature section below corresponds to one profile in **`config/features.json`**, which is the authoritative source for every feature's verification status and expectation set. Where this chapter and that file disagree, the file is correct and this chapter is stale.

The fourteen feature profiles (`EM010_Screenshots` … `EM023_EmailMonitoring`) replace the six scaffold sections (`EM001`–`EM006`) that this chapter previously carried as pure TODO. That replacement **renumbers the sections**, contrary to the fixed-numbering note this chapter used to carry — see §1.1 for the inbound-link map that mitigates it.

### 1.1 Feature ID Migration Map (inbound links)

[HB-001 §4](HB-001_Product_Overview.md), [the implementation plan §7](../roadmap/implementation_plan.md) and [the Synchronization Monitor design §12](../design/Synchronization_Monitor.md) have been repointed to the new IDs and sections. Older references — external notes, review documents, anything written before 2026-07-31 — may still say "HB-006 §2" … "HB-006 §7" for the original six scaffold features. **Those section numbers no longer address those features.** Resolve such references through this table:

| Old ID / name | Old section (now stale) | New feature ID | New section |
|---|---|---|---|
| `EM001` — Login | §2 | **none — unprofiled** | — (see §1.2) |
| `EM002` — User Management | §3 | **none — unprofiled** | — |
| `EM003` — Attendance | §4 | `EM013_Attendance` | [§5](#5-em013_attendance--attendance) |
| `EM004` — Live Monitoring | §5 | `EM012_LiveMonitoring` | [§4](#4-em012_livemonitoring--live-monitoring) |
| `EM005` — Screenshots | §6 | `EM010_Screenshots` | [§2](#2-em010_screenshots--screenshots) |
| `EM006` — Screen Recording | §7 | `EM011_ScreenRecording` | [§3](#3-em011_screenrecording--screen-recording) |

**`EM001_Login` and `EM002_UserManagement` have no profile in `config/features.json` and remain unprofiled.** They are **dashboard-side concerns, not agent features**: authentication and user-account administration are exercised through the dashboard, and **the dashboard has never been observed** — no Layer 4 collector exists ([Evidence Catalog §3](../Evidence_Catalog.md), [Synchronization Architecture Report §8.3](../Synchronisation_Architecture_Report.md)). No agent-side artifact was attributed to either. They are therefore absent by design rather than by oversight, and nothing in this chapter specifies them.

> Note that the agent-side login *state* is not entirely invisible: the `[auth]` section of `empm.ini` was observed to be present while a user was signed in and absent afterwards ([RE-005](../../knowledge_base/RE-005_Configuration_Loading.md)). That is a configuration observation, not a Login feature specification, and it is recorded in RE-005 only.

### 1.2 Plugin Identifier Collision — `EM001`

The identifier **`EM001` was originally allocated to `EM001_Login`** in the original scaffold. It is **now held by the implemented `EM001_Synchronization` plugin**. Both directories currently exist under `plugins/`, so the identifier is genuinely double-booked.

To avoid compounding the collision, **feature plugins start at `EM010`**. `EM000`–`EM009` are treated as reserved for framework-level and cross-cutting plugins (environment validation, synchronization), not for feature areas. Resolution of the duplicate `EM001` directories is a plugin-catalog matter and is not decided here.

### 1.3 What Applies to Every Feature Section

Stated once here rather than repeated fourteen times:

- **Verification status** is copied verbatim from the profile's `verification_status` and carries the [README §6](../../knowledge_base/README.md) meaning: **Verified** — mechanism directly observed; **Partially Verified** — supporting artifacts observed but the feature's operation was not; **Hypothesis** — no artifact identified at all.
- **Expected validators** are identical across all fourteen profiles: `ConfigurationValidator`, `RuntimeValidator`, `FrequencyValidator`, `TimestampValidator`, `CorrelationValidator`. Deviations would be recorded per-section; there are none.
- **Four failure modes are common to every profile** and are listed per-section only when a feature adds to them: *captured but not persisted*, *persisted but not uploaded*, *uploaded but not surfaced*, *configured on but not capturing*. These are the four cross-layer break points the four-layer model exists to distinguish.
- **Every `expected_dashboard_pages` value is Hypothesis.** They reference [`docs/design/Dashboard_Navigation.md`](../design/Dashboard_Navigation.md), an unobserved model. **No dashboard page has been visited by anything**, and no L4 evidence source is cited by any profile. Dashboard pages are listed for traceability only and must not be read as a claim.
- **Expected evidence layers** below are derived from each profile's `expected_evidence` EV IDs and the layer each ID is registered under in the [Evidence Catalog](../Evidence_Catalog.md) (EV-001/EV-002 → L1; EV-003/EV-011/EV-013 → L2; EV-007/EV-017 → L3). They are *expectations for the plugin to confirm*, not findings.
- **Artifact expectations are expectations, not inventory.** Where an artifact was actually observed, the RE document for that artifact is authoritative: [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) for config keys, [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) for tables, [RE-008](../../knowledge_base/RE-008_Logging_System.md) for logs, [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) for processes.
- **An empty expectation list means nothing was profiled**, not that nothing exists. It is recorded as "none profiled" rather than omitted, so the gap is visible.

### 1.4 Caution — `settings/data\trackingMode` Key Escaping

The attendance config key is `data\trackingMode` in the `[settings]` section of `empm.ini`, i.e. `settings/data\trackingMode` — the backslash is literal, as in the `from_remote\` keys ([RE-005 §6.2](../../knowledge_base/RE-005_Configuration_Loading.md)). A single backslash inside a JSON string is an escape introducer, so this key must be written `"settings/data\\trackingMode"` in any JSON file. Plugin authors comparing a configured key name against an observed one should be alert to this.

## 2. EM010_Screenshots — Screenshots

**Purpose:** Capture of point-in-time screen images of the monitored endpoint, their local persistence, and their upload to the server.

**Verification Status:** **Partially Verified**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | Quality and interval keys present and readable |
| L2 — Runtime | EV-003, EV-011 | `empmonitor.exe` alive; `pending_screenshots6` present |
| L3 — Synchronization | EV-007 | Upload cycle triggered; `add-activity` outcome |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | `appSettings/screenshotQuality`, `appSettings/from_remote\screenshotPeriodSec` |
| Upload interval key | `appSettings/from_remote\screenshotPeriodSec` |
| Runtime components | `empmonitor.exe` |
| SQLite tables | `pending_screenshots6` |
| APIs | `add-activity` |
| Log patterns | `upload_cycle_trigger` |
| Dashboard pages (Hypothesis) | `screenshots` |

**Expected Failure Modes:** the four common modes (§1.3), plus **capture interval drifts from configuration**.

**Established vs. Inferred** — profile `note`, verbatim:

> Config keys and pending_screenshots6 table VERIFIED present (Phase 2/3). No screenshot capture or upload was observed.

**Cross References:** [RE-004 — Upload Pipeline](../../knowledge_base/RE-004_Upload_Pipeline.md) · [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [RE-010 — Folder Structure](../../knowledge_base/RE-010_Folder_Structure.md)

## 3. EM011_ScreenRecording — Screen Recording

**Purpose:** Capture of video-form recordings of endpoint screen activity, their persistence, and their upload.

**Verification Status:** **Partially Verified**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | Sources cited but **no key profiled** — a Layer 1 check has nothing to assert on |
| L2 — Runtime | EV-003, EV-011 | `esr.exe` alive |
| L3 — Synchronization | EV-007 | Upload of a recording |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | none profiled |
| Upload interval key | none profiled |
| Runtime components | `esr.exe` |
| SQLite tables | none profiled |
| APIs | none profiled |
| Log patterns | none profiled |
| Dashboard pages (Hypothesis) | `recordings` |

The empty table and API rows are themselves the notable result: **no table name suggests screen recordings** anywhere in the 28-table schema, and no on-disk capture folder was found — yet `esr.exe` runs. Where recordings are persisted is an open question in [RE-007 §16](../../knowledge_base/RE-007_SQLite_Database.md) and [RE-010](../../knowledge_base/RE-010_Folder_Structure.md).

**Expected Failure Modes:** the four common modes (§1.3); no feature-specific modes are profiled.

**Established vs. Inferred** — profile `note`, verbatim:

> esr.exe VERIFIED present and running, with ffmpeg DLLs. No recording or upload observed; no recording table identified.

**Cross References:** [RE-009 — Runtime Components](../../knowledge_base/RE-009_Runtime_Components.md) · [RE-004 — Upload Pipeline](../../knowledge_base/RE-004_Upload_Pipeline.md) · [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md)

## 4. EM012_LiveMonitoring — Live Monitoring

**Purpose:** Real-time or near-real-time observation of endpoint activity, including whatever streaming channel carries it.

**Verification Status:** **Partially Verified**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001 | The `wss` endpoint declared in `config.js` |
| L2 — Runtime | EV-011 | `esr.exe` and `empmonitor.exe` alive |
| L3 — Synchronization | EV-007, EV-017 | Stream/connection state — this is the only feature profiling EV-017 alongside a capture concern |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | none profiled |
| Upload interval key | none profiled (a stream has no upload interval) |
| Runtime components | `esr.exe`, `empmonitor.exe` |
| SQLite tables | none profiled |
| APIs | none profiled |
| Log patterns | none profiled |
| Dashboard pages (Hypothesis) | `live_monitoring` |

**Expected Failure Modes:** the four common modes (§1.3), plus **stream not established** and **stream established but not rendered**.

**Established vs. Inferred** — profile `note`, verbatim:

> A wss endpoint is VERIFIED configured in config.js and Qt5WebSockets ships with the agent; live streaming itself was never observed.

Note the observability limit recorded in [Synchronization Architecture Report §2.6](../Synchronisation_Architecture_Report.md): WebSocket traffic is indistinguishable from HTTPS at connection level, so EV-017 cannot by itself confirm a stream.

**Cross References:** [RE-006 — API Flow](../../knowledge_base/RE-006_API_Flow.md) · [RE-005 §6.4](../../knowledge_base/RE-005_Configuration_Loading.md) · [Synchronization Monitor Design](../design/Synchronization_Monitor.md)

## 5. EM013_Attendance — Attendance

**Purpose:** Recording of attendance-related activity — clock events and presence over time.

**Verification Status:** **Partially Verified**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | `settings/data\trackingMode` present (§1.4) |
| L2 — Runtime | EV-003, EV-011 | `empmonitor.exe` alive; `clock_data6` present |
| L3 — Synchronization | EV-007 | Upload of clock data — no API profiled |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | `settings/data\trackingMode` |
| Upload interval key | none profiled |
| Runtime components | `empmonitor.exe` |
| SQLite tables | `clock_data6` |
| APIs | none profiled |
| Log patterns | none profiled |
| Dashboard pages (Hypothesis) | `timesheet`, `reports` |

**Expected Failure Modes:** the four common modes (§1.3), plus **clock event recorded with wrong state**.

**Established vs. Inferred** — profile `note`, verbatim:

> clock_data6 VERIFIED present with columns type/mode/status/reason/startDate/endDate; settings/data\trackingMode VERIFIED present. Their relationship to attendance is inferred, not observed.

**Cross References:** [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [RE-005 — Configuration Loading](../../knowledge_base/RE-005_Configuration_Loading.md) · [RE-003 — Scheduler](../../knowledge_base/RE-003_Scheduler.md)

## 6. EM014_IdleTime — Idle Time

**Purpose:** Detection and accounting of idle/break periods on the endpoint.

**Verification Status:** **Partially Verified**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | `appSettings/todayRemainingBreakInSeconds` present |
| L2 — Runtime | EV-003, EV-011 | `clock_data6` present — **no runtime component is profiled**, so there is no process to attribute idle detection to |
| L3 — Synchronization | EV-007 | Upload of idle/break data |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | `appSettings/todayRemainingBreakInSeconds` |
| Upload interval key | none profiled |
| Runtime components | none profiled |
| SQLite tables | `clock_data6` (shared with EM013) |
| APIs | none profiled |
| Log patterns | none profiled |
| Dashboard pages (Hypothesis) | `timesheet` |

**Expected Failure Modes:** the four common modes (§1.3), plus **idle not detected** and **idle time misattributed**.

**Established vs. Inferred** — profile `note`, verbatim:

> appSettings/todayRemainingBreakInSeconds VERIFIED present, which evidences break/idle accounting. Idle detection itself unobserved.

Because `clock_data6` is shared with EM013, a row-count delta on it cannot on its own attribute activity to idle time rather than attendance.

**Cross References:** [RE-005 — Configuration Loading](../../knowledge_base/RE-005_Configuration_Loading.md) · [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [RE-013 — Agent State Machine](../../knowledge_base/RE-013_Agent_State_Machine.md)

## 7. EM015_Timesheet — Timesheet

**Purpose:** Presentation of worked-time records over a period.

**Verification Status:** **Hypothesis**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | No key profiled |
| L2 — Runtime | EV-003, EV-011 | `clock_data6`, `usagedata6` present |
| L3 — Synchronization | EV-007 | Upload of the underlying data |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) — and this feature is the one most likely to live here |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | none profiled |
| Upload interval key | none profiled |
| Runtime components | none profiled |
| SQLite tables | `clock_data6`, `usagedata6` (both shared with other features) |
| APIs | none profiled |
| Log patterns | none profiled |
| Dashboard pages (Hypothesis) | `timesheet` |

**Expected Failure Modes:** the four common modes (§1.3); no feature-specific modes are profiled.

**Established vs. Inferred** — profile `note`, verbatim:

> No timesheet-specific artifact identified. Most likely a dashboard-side aggregation of clock/usage data, which would make it primarily an L4 feature.

A plugin for this feature cannot reach a conclusion with the collectors that exist today, since L4 has no collector.

**Cross References:** [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [Validation Standard](../ADS/validation_standard.md)

## 8. EM016_Keystrokes — Keystrokes

**Purpose:** Capture of keyboard input activity on the endpoint.

**Verification Status:** **Hypothesis**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | No key profiled — none was found |
| L2 — Runtime | EV-003, EV-011 | No table or process profiled — none was found |
| L3 — Synchronization | EV-007 | No log pattern or API profiled |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:** **none profiled in any category** — no configuration key, runtime component, SQLite table, API, or log pattern. Dashboard page (Hypothesis): `reports`.

**Expected Failure Modes:** the four common modes (§1.3); no feature-specific modes are profiled.

**Established vs. Inferred** — profile `note`, verbatim:

> No keystroke table, config key, or log pattern was observed. clipboardData exists but is clipboard content, not keystrokes. Whether this feature is present in this build is unknown.

**Do not attribute `clipboardData` to keystrokes.** That mis-attribution is the specific error this profile exists to prevent — see [RE-007 §6.5 mapping subsection](../../knowledge_base/RE-007_SQLite_Database.md).

**Cross References:** [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md)

## 9. EM017_ApplicationUsage — Application Usage

**Purpose:** Recording of which applications are used on the endpoint and for how long.

**Verification Status:** **Partially Verified**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | No key profiled |
| L2 — Runtime | EV-003, EV-011 | `empmonitor.exe` alive; `usagedata6`, `pending_usagedata6` present |
| L3 — Synchronization | EV-007 | `config_refresh` log pattern; `add-activity` |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | none profiled |
| Upload interval key | none profiled |
| Runtime components | `empmonitor.exe` |
| SQLite tables | `usagedata6`, `pending_usagedata6` |
| APIs | `add-activity` |
| Log patterns | `config_refresh` |
| Dashboard pages (Hypothesis) | `reports` |

**Expected Failure Modes:** the four common modes (§1.3); no feature-specific modes are profiled.

**Established vs. Inferred** — profile `note`, verbatim:

> usagedata6 (populated) and pending_usagedata6 VERIFIED present; UploadBlock app block-list log lines VERIFIED. Attribution of usagedata6 to application usage is inferred.

Note that `usagedata6` is also profiled for EM018 and EM022, so a row-count delta on it does not attribute activity to any one of the three.

**Cross References:** [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [RE-008 — Logging System](../../knowledge_base/RE-008_Logging_System.md) · [RE-004 — Upload Pipeline](../../knowledge_base/RE-004_Upload_Pipeline.md)

## 10. EM018_WebsiteUsage — Website Usage

**Purpose:** Recording of websites visited on the endpoint, and of browser-mediated activity such as downloads.

**Verification Status:** **Partially Verified**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | No key profiled |
| L2 — Runtime | EV-003, EV-011 | `empmonitor.exe` and `emp_psa_service.exe` alive; `usagedata6`, `pending_usagedata6`, `download_history` present |
| L3 — Synchronization | EV-007 | `add-activity` |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | none profiled |
| Upload interval key | none profiled |
| Runtime components | `empmonitor.exe`, `emp_psa_service.exe` |
| SQLite tables | `usagedata6`, `pending_usagedata6`, `download_history` |
| APIs | `add-activity` |
| Log patterns | none profiled |
| Dashboard pages (Hypothesis) | `reports` |

**Expected Failure Modes:** the four common modes (§1.3), plus **browser traffic not intercepted**.

**Established vs. Inferred** — profile `note`, verbatim:

> BrowserHandlingService and WinDivert driver VERIFIED present, and website block-list log lines VERIFIED. Interception behaviour itself unobserved.

**Cross References:** [RE-009 — Runtime Components](../../knowledge_base/RE-009_Runtime_Components.md) · [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [RE-006 — API Flow](../../knowledge_base/RE-006_API_Flow.md)

## 11. EM019_UsbDetection — USB Detection

**Purpose:** Detection of USB device insertion/removal on the endpoint and recording of those events.

**Verification Status:** **Partially Verified**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | No key profiled |
| L2 — Runtime | EV-003, EV-011 | `usbdata6`, `pending_usbdata6` present — no runtime component profiled |
| L3 — Synchronization | EV-007 | Upload of USB events — no API profiled |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | none profiled |
| Upload interval key | none profiled |
| Runtime components | none profiled |
| SQLite tables | `usbdata6`, `pending_usbdata6` |
| APIs | none profiled |
| Log patterns | none profiled |
| Dashboard pages (Hypothesis) | `reports` |

**Expected Failure Modes:** the four common modes (§1.3), plus **device inserted but not detected**.

**Established vs. Inferred** — profile `note`, verbatim:

> usbdata6 and pending_usbdata6 VERIFIED present, both empty. No USB event was observed.

Both tables being empty is **not** a defect signal on its own ([RE-007 7-V21](../../knowledge_base/RE-007_SQLite_Database.md)); it is what "no USB device was used" looks like. This feature is, however, the cheapest of the fourteen to promote: it has a dedicated, currently-empty table pair, so a single deliberate insertion would produce an unambiguous row-count delta.

**Cross References:** [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md)

## 12. EM020_Webcam — Webcam

**Purpose:** Capture of webcam images or video from the endpoint.

**Verification Status:** **Hypothesis**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | No key profiled — none was found |
| L2 — Runtime | EV-003, EV-011 | No table or process profiled — none was found |
| L3 — Synchronization | EV-007 | No log pattern or API profiled |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:** **none profiled in any category.** Dashboard page (Hypothesis): `reports`.

**Expected Failure Modes:** the four common modes (§1.3); no feature-specific modes are profiled.

**Established vs. Inferred** — profile `note`, verbatim:

> No webcam table, config key, log pattern, or runtime component identified.

**Cross References:** [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [RE-009 — Runtime Components](../../knowledge_base/RE-009_Runtime_Components.md)

## 13. EM021_FaceDetection — Face Detection

**Purpose:** Detection of a face in captured imagery from the endpoint.

**Verification Status:** **Hypothesis**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | No key profiled — none was found |
| L2 — Runtime | EV-003, EV-011 | No table or process profiled — none was found |
| L3 — Synchronization | EV-007 | No log pattern or API profiled |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:** **none profiled in any category.** Dashboard page (Hypothesis): `reports`.

**Expected Failure Modes:** the four common modes (§1.3); no feature-specific modes are profiled.

**Established vs. Inferred** — profile `note`, verbatim:

> No face-detection artifact identified. Presumably depends on EM020_Webcam.

**Cross References:** [§12 — EM020_Webcam](#12-em020_webcam--webcam) · [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md)

## 14. EM022_Productivity — Productivity

**Purpose:** Classification of endpoint activity as productive or otherwise.

**Verification Status:** **Hypothesis**

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | EV-001, EV-002 | No key profiled |
| L2 — Runtime | EV-003, EV-011 | `usagedata6` present |
| L3 — Synchronization | EV-007 | Upload of the underlying usage data |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) — the likeliest home for the classification itself |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | none profiled |
| Upload interval key | none profiled |
| Runtime components | none profiled |
| SQLite tables | `usagedata6` (shared with EM017, EM018, EM015) |
| APIs | none profiled |
| Log patterns | none profiled |
| Dashboard pages (Hypothesis) | `reports` |

**Expected Failure Modes:** the four common modes (§1.3); no feature-specific modes are profiled.

**Established vs. Inferred** — profile `note`, verbatim:

> No productivity-specific artifact identified. Likely a dashboard-side classification of usage data rather than an agent-side capture.

**Cross References:** [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [§9 — EM017_ApplicationUsage](#9-em017_applicationusage--application-usage)

## 15. EM023_EmailMonitoring — Email Monitoring

**Purpose:** Interception and recording of inbound and outbound mail activity, including attachment metadata, and its upload to the server.

**Verification Status:** **Verified** — the only profile of the fourteen at this status, and the most strongly evidenced feature in the product.

**Expected Evidence Layers:**

| Layer | Evidence sources | What it should show |
|---|---|---|
| L1 — Configuration | — | **No L1 source is profiled** — no configuration key was attributed to this feature, so a Layer 1 check has nothing to assert on |
| L2 — Runtime | EV-003, EV-011, EV-013 | `EmailMonitorSvc.exe` alive (and its build metadata); four mail tables present |
| L3 — Synchronization | EV-007, EV-017 | `request_dump` / `upload_succeeded` log patterns; `save-email-monitoring-log`; mail-provider connection state |
| L4 — Dashboard | — | No source cited; Hypothesis (§1.3) |

**Expected Artifacts:**

| Kind | Expectation |
|---|---|
| Configuration keys | none profiled |
| Upload interval key | none profiled — uploads are **event-driven**, not periodic |
| Runtime components | `EmailMonitorSvc.exe` |
| SQLite tables | `inbound_emails`, `outbound_emails`, `mail_data`, `mail_attachment_data` |
| APIs | `save-email-monitoring-log` |
| Log patterns | `request_dump`, `upload_succeeded` |
| Dashboard pages (Hypothesis) | `reports` |

**Expected Failure Modes:** the four common modes (§1.3), plus **mail proxy not intercepting** and **attachment enrichment fails**.

**Established vs. Inferred** — profile `note`, verbatim:

> The most strongly evidenced feature. VERIFIED: EmailMonitorSvc.exe running with six mail-protocol listeners and established provider connections; four mail tables; multipart uploads to save-email-monitoring-log with per-item UPLOAD SUCCEEDED.

Two constraints bind any plugin here. First, mail content and metadata are among the most sensitive data the product handles: **row contents must never be read** ([RE-007 §6.0](../../knowledge_base/RE-007_SQLite_Database.md)) and no recipient, subject, or attachment name may enter an artifact. Second, this feature's Verified status rests substantially on **log-derived** evidence, which [RE-008 §6.5](../../knowledge_base/RE-008_Logging_System.md) records as non-durable — the strongest feature in the catalog has the most perishable evidence base.

**Cross References:** [RE-009 — Runtime Components](../../knowledge_base/RE-009_Runtime_Components.md) · [RE-006 — API Flow](../../knowledge_base/RE-006_API_Flow.md) · [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md) · [RE-008 — Logging System](../../knowledge_base/RE-008_Logging_System.md) · [Synchronization Architecture Report §2.2](../Synchronisation_Architecture_Report.md)

## 16. Evidence Sources

Every layer expectation above must be confirmed or corrected by the plugin author against the [Validation Standard](../ADS/validation_standard.md) §3–§4, and each cited `EV-NNN` must exist in the [Evidence Catalog](../Evidence_Catalog.md) — a source not registered there may not be cited. This chapter records *expectations about scope*, not evidence itself; the evidence lives in the RE documents and in run artifacts under `reports/`.

Three chapter-wide observations about the evidence available to these fourteen features:

- **Layer 4 is unavailable for all fourteen.** No profile cites an L4 source, and no L4 collector exists. Any feature whose only plausible home is the dashboard (EM015, EM022) therefore cannot be concluded today, and "uploaded but not surfaced" — one of the four common failure modes — is **undetectable for every feature**.
- **No configuration key is profiled for eleven of the fourteen.** Only EM010, EM013 and EM014 profile one; EM023 (the sole Verified feature) profiles none. A Configuration validator run against most of these features has nothing to assert on, and must report that rather than pass.
- **Log-derived evidence is not durable.** The agent was observed emptying its own log directory ([RE-008 §6.5](../../knowledge_base/RE-008_Logging_System.md)). Features whose expectations rest on `expected_log_patterns` — EM010, EM017, EM023 — can lose their evidence base mid-run. The correct outcome is `INCONCLUSIVE`, never an invented failure.

## 17. Version Notes

| Scope | Version | Date |
|---|---|---|
| Every artifact observation underlying the statuses above | EmpMonitor `gui` components **3.7.4** / `service` component **3.7.3**; host Windows 10 Pro build 10.0.19045 x64 | 2026-07-30 |

Single host, single installation, single tenant, single observation window. No status above is corroborated across hosts or versions, so all of them are provisional in the sense of [README §7](../../knowledge_base/README.md) step 6: on a version change, table names, configuration keys and log patterns must be re-checked, and any expectation that no longer matches must be demoted rather than repaired silently.

**Reviewer sign-off is outstanding** for every claim referenced by this chapter ([README §7](../../knowledge_base/README.md) step 4).

## 18. Cross References

- [HB-001 — Product Overview](HB-001_Product_Overview.md) — §4 carries the full fourteen-feature validation scope; §4.2 records the retired scaffold IDs mapped in §1.1
- [HB-002 — Product Architecture](HB-002_Product_Architecture.md)
- [HB-005 — Component Inventory](HB-005_Component_Inventory.md)
- [Plugin Development Guide](../ADS/plugin_standard.md)
- [Validation Standard](../ADS/validation_standard.md)
- [Evidence Catalog](../Evidence_Catalog.md)
- [Synchronization Architecture Report](../Synchronisation_Architecture_Report.md) — the Phase 3 observations several statuses rest on
- [Reverse Engineering Knowledge Base](../../knowledge_base/README.md)
- `config/features.json` — authoritative source for every status and expectation in this chapter

---
**Document Status:** Active — fourteen feature profiles (EM010–EM023) documented from `config/features.json`; one **Verified** (EM023), eight **Partially Verified**, five **Hypothesis**. Sections renumbered; known inbound links repointed 2026-07-31, and any remaining "HB-006 §2–§7" reference resolves via §1.1. `EM001_Login` and `EM002_UserManagement` remain unprofiled dashboard-side concerns. Layer 4 unavailable for all fourteen. Reviewer sign-off outstanding.
**Owner:** TODO
**Last Updated:** 2026-07-31
