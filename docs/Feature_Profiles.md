# Feature Profiles

The human-readable view of `config/features.json`, which is authoritative for the running framework. **Both must be updated together.**

A profile records what a feature *should* do and how well its mechanism is currently established. It is written before the plugin exists, so expectations are reviewable rather than buried in code.

**Status:** 1 Verified · 8 Partially Verified · 5 Hypothesis · 14 total

## 1. Why Status Governs Behaviour

`verification_status` is not documentation — it changes what a plugin may report. Per [Feature Validation Standard §4](ADS/feature_validation_standard.md):

| Status | Expected artifact absent → | Reasoning |
|---|---|---|
| **Verified** | `FAILED` | The mechanism was observed working; its absence is a real defect |
| **Partially Verified** | `INCONCLUSIVE` | Artifacts observed, mechanism not; absence may mean looking in the wrong place |
| **Hypothesis** | `INCONCLUSIVE` | Nothing known; the framework does not know what absence *means* here |

Encoded in `FeatureProfile.absence_verdict` so a plugin cannot get it wrong by forgetting.

## 2. Register

| Feature | Name | Status | SQLite tables | Runtime | Dashboard (unobserved) |
|---|---|---|---|---|---|
| `EM010_Screenshots` | Screenshots | **Partially Verified** | pending_screenshots6 | empmonitor.exe | screenshots |
| `EM011_ScreenRecording` | Screen Recording | **Partially Verified** | — | esr.exe | recordings |
| `EM012_LiveMonitoring` | Live Monitoring | **Partially Verified** | — | esr.exe, empmonitor.exe | live_monitoring |
| `EM013_Attendance` | Attendance | **Partially Verified** | clock_data6 | empmonitor.exe | timesheet, reports |
| `EM014_IdleTime` | Idle Time | **Partially Verified** | clock_data6 | — | timesheet |
| `EM015_Timesheet` | Timesheet | **Hypothesis** | clock_data6, usagedata6 | — | timesheet |
| `EM016_Keystrokes` | Keystrokes | **Hypothesis** | — | — | reports |
| `EM017_ApplicationUsage` | Application Usage | **Partially Verified** | usagedata6, pending_usagedata6 | empmonitor.exe | reports |
| `EM018_WebsiteUsage` | Website Usage | **Partially Verified** | usagedata6, pending_usagedata6, download_history | empmonitor.exe, emp_psa_service.exe | reports |
| `EM019_UsbDetection` | USB Detection | **Partially Verified** | usbdata6, pending_usbdata6 | — | reports |
| `EM020_Webcam` | Webcam | **Hypothesis** | — | — | reports |
| `EM021_FaceDetection` | Face Detection | **Hypothesis** | — | — | reports |
| `EM022_Productivity` | Productivity | **Hypothesis** | usagedata6 | — | reports |
| `EM023_EmailMonitoring` | Email Monitoring | **Verified** | inbound_emails, outbound_emails, mail_data, mail_attachment_data | EmailMonitorSvc.exe | reports |

## 3. What Is Actually Established

Every claim below rests on Phase 2–3 observation of a live agent (gui 3.7.4 / service 3.7.3). Dashboard pages are `Hypothesis` throughout — **the dashboard has never been observed**.

### `EM010_Screenshots` — Screenshots

**Status: Partially Verified**

Config keys and pending_screenshots6 table VERIFIED present (Phase 2/3). No screenshot capture or upload was observed.

- Configuration: appSettings/screenshotQuality, appSettings/from_remote\screenshotPeriodSec
- Interval key: `appSettings/from_remote\screenshotPeriodSec`

### `EM011_ScreenRecording` — Screen Recording

**Status: Partially Verified**

esr.exe VERIFIED present and running, with ffmpeg DLLs. No recording or upload observed; no recording table identified.

- Configuration: none identified

### `EM012_LiveMonitoring` — Live Monitoring

**Status: Partially Verified**

A wss endpoint is VERIFIED configured in config.js and Qt5WebSockets ships with the agent; live streaming itself was never observed.

- Configuration: none identified

### `EM013_Attendance` — Attendance

**Status: Partially Verified**

clock_data6 VERIFIED present with columns type/mode/status/reason/startDate/endDate; settings/data	rackingMode VERIFIED present. Their relationship to attendance is inferred, not observed.

- Configuration: settings/data	rackingMode

### `EM014_IdleTime` — Idle Time

**Status: Partially Verified**

appSettings/todayRemainingBreakInSeconds VERIFIED present, which evidences break/idle accounting. Idle detection itself unobserved.

- Configuration: appSettings/todayRemainingBreakInSeconds

### `EM015_Timesheet` — Timesheet

**Status: Hypothesis**

No timesheet-specific artifact identified. Most likely a dashboard-side aggregation of clock/usage data, which would make it primarily an L4 feature.

- Configuration: none identified

### `EM016_Keystrokes` — Keystrokes

**Status: Hypothesis**

No keystroke table, config key, or log pattern was observed. clipboardData exists but is clipboard content, not keystrokes. Whether this feature is present in this build is unknown.

- Configuration: none identified

### `EM017_ApplicationUsage` — Application Usage

**Status: Partially Verified**

usagedata6 (populated) and pending_usagedata6 VERIFIED present; UploadBlock app block-list log lines VERIFIED. Attribution of usagedata6 to application usage is inferred.

- Configuration: none identified

### `EM018_WebsiteUsage` — Website Usage

**Status: Partially Verified**

BrowserHandlingService and WinDivert driver VERIFIED present, and website block-list log lines VERIFIED. Interception behaviour itself unobserved.

- Configuration: none identified

### `EM019_UsbDetection` — USB Detection

**Status: Partially Verified**

usbdata6 and pending_usbdata6 VERIFIED present, both empty. No USB event was observed.

- Configuration: none identified

### `EM020_Webcam` — Webcam

**Status: Hypothesis**

No webcam table, config key, log pattern, or runtime component identified.

- Configuration: none identified

### `EM021_FaceDetection` — Face Detection

**Status: Hypothesis**

No face-detection artifact identified. Presumably depends on EM020_Webcam.

- Configuration: none identified

### `EM022_Productivity` — Productivity

**Status: Hypothesis**

No productivity-specific artifact identified. Likely a dashboard-side classification of usage data rather than an agent-side capture.

- Configuration: none identified

### `EM023_EmailMonitoring` — Email Monitoring

**Status: Verified**

The most strongly evidenced feature. VERIFIED: EmailMonitorSvc.exe running with six mail-protocol listeners and established provider connections; four mail tables; multipart uploads to save-email-monitoring-log with per-item UPLOAD SUCCEEDED.

- Configuration: none identified


## 4. The Five Unknown Features

`EM015_Timesheet`, `EM016_Keystrokes`, `EM020_Webcam`, `EM021_FaceDetection`, and `EM022_Productivity` have **no identified artifact at all** — no table, config key, log pattern, or runtime component.

Two possibilities, and the framework cannot yet distinguish them: the feature is absent from this build, or its mechanism simply has not been found. Either way, a plugin for one of these must **reverse-engineer before validating**, and must report absence as `INCONCLUSIVE`.

`EM016_Keystrokes` deserves a specific note: `clipboardData` exists and is populated, but clipboard capture is not keystroke capture. Treating one as the other would be exactly the kind of plausible inference this framework exists to avoid.

## 5. Maintenance

- Adding a feature: profile first, then `python scripts/new_feature_plugin.py <FEATURE_ID>`.
- Promoting a status: requires the six verification-metadata fields and a reviewer ([knowledge_base/README.md §7](../knowledge_base/README.md)). **The reviewer role is still unassigned, so no promotion can currently complete.**
- Referenced dashboard pages must exist in [Dashboard Navigation](design/Dashboard_Navigation.md). Unlike the Evidence Catalog, this has **no automated drift check** — see [Architecture Review §8](ARCHITECTURE_REVIEW_PHASE_4.md).

## 6. Cross References

- [Feature Validation Standard](ADS/feature_validation_standard.md) · [Evidence Catalog](Evidence_Catalog.md)
- [HB-006 Feature Specifications](handbook/HB-006_Feature_Specifications.md)
- [Dashboard Navigation](design/Dashboard_Navigation.md) · [Dashboard Page Specifications](design/Dashboard_Page_Specifications.md)

---
**Document Status:** Active — mirrors `config/features.json`
**Owner:** TODO
**Last Updated:** 2026-07-30
