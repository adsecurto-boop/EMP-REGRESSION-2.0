# HB-005 — EmpMonitor Component Inventory

## 1. Purpose

This chapter is a **consolidated master inventory** — as tables — of every known or named component across the EmpMonitor product: processes, services, configuration files, folders, log files, database objects, and API endpoints. It pulls structure only (name, category, status, reference) from [HB-003](HB-003_Agent_Architecture.md), [HB-004](HB-004_Agent_Ecosystem.md), and the [RE knowledge base](../../knowledge_base/README.md). It does **not** restate their content, architecture, or behavior — for that, follow the Reference Document column.

## 2. Scope

**In scope:** a flat, categorized index of component names and their verification status.

**Out of scope:** architecture, behavior, failure modes, and recovery of any individual component — those live in [HB-002](HB-002_Product_Architecture.md), [HB-003](HB-003_Agent_Architecture.md), [HB-004](HB-004_Agent_Ecosystem.md), [HB-006](HB-006_Feature_Specifications.md), and the RE documents.

> **This inventory must be kept in sync as components are verified elsewhere.** When a claim is promoted from Known/TODO to Verified in an RE document or handbook chapter, its Status here must be updated in the same change. An out-of-date inventory is worse than an absent one — do not let this table drift from the documents it summarizes.

## 3. Architecture

Not applicable to this chapter's scope — this is an inventory, not an architectural description. See [HB-002](HB-002_Product_Architecture.md) (ecosystem), [HB-003](HB-003_Agent_Architecture.md) (Agent internals), and [HB-004](HB-004_Agent_Ecosystem.md) (Agent dependency graph).

> **Verification metadata for every Verified / Partially Verified row in this chapter.** All promotions below derive from a single observation pass; the six [knowledge_base README §6.1](../../knowledge_base/README.md) fields are stated once here rather than repeated in every table:
>
> | Field | Value |
> |---|---|
> | `Verified On` | 2026-07-30 |
> | `Verified Against Version` | EmpMonitor `gui` components **3.7.4** / `service` component **3.7.3**; host Windows 10 Pro build 10.0.19045 x64 |
> | `Evidence Source` | EV-001 (`config.js`), EV-002 (`empm.ini`), EV-003 (SQLite), EV-005 (service state), EV-010 (file system), EV-011 (process/resource), EV-012 (OS), EV-013 (executable metadata) — per-row IDs in each table |
> | `Verification Method` | Observed by `EM000_EnvironmentValidator` plugin run plus direct filesystem inspection |
> | `Reviewer` | TODO — reviewer sign-off ([README §7](../../knowledge_base/README.md) step 4) not yet performed |
> | `Last Review Date` | 2026-07-30 |
>
> **Scope limit on every row:** one host, one installation, one user profile, one point in time. No row is yet corroborated across hosts, users, Windows versions, or EmpMonitor versions.

## 4. Runtime — Windows Services

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **`BrowserHandlingService`** (display name `Browser Handling Service`) — hosts `emp_psa_service.exe`; observed RUNNING, start type AUTO_START (2) | Service | **Verified** | EV-005, EV-011 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| Windows failure/recovery actions on `BrowserHandlingService` — configured, readable via `sc qfailure`; **action content not recorded** | Service Configuration | **Verified** (that actions exist) | EV-005 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md), [RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md) |
| Watchdog service (if separate from main process) | Service | **Hypothesis** — no watchdog-named service observed; existence neither confirmed nor excluded | EV-005 | [RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md) |
| Any additional EmpMonitor service | Service | **Hypothesis** | — | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |

> The service name contains **no** "Emp" substring. Automation must query it by its exact short name `BrowserHandlingService`; name-substring discovery will not find it.

## 5. Configuration — Configuration Files

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **`config.js`** — `<install root>\gui\configs\config.js`; 324 B / 9 lines; **4 endpoint URLs** over `https` + `wss`. **URLs not recorded (deployment-specific)** | Configuration File | **Verified** (location, size, endpoint count/schemes) | EV-001, EV-010 | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md), [RE-006](../../knowledge_base/RE-006_API_Flow.md) |
| **`config_debug.js`**, **`config_release.js`** — same folder | Configuration File | **Verified** (presence); role **Hypothesis** | EV-010 | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) |
| **`empm.ini` (root)** — `%APPDATA%\screen\empm.ini`, **~357 B**, per user. Sections `[General]`, `[appSettings]`, `[auth]` | Configuration File | **Verified** (location + sections/keys) | EV-002, EV-010 | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) |
| **`empm.ini` (tenant)** — `%APPDATA%\screen\<TENANT>\empm.ini`, **~4.7 KB**. **Two `empm.ini` files exist, not one** | Configuration File | **Verified** (existence); "is the remote/synced config" **Partially Verified** | EV-002, EV-010 | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) |
| `[General] identifier` | Configuration Key | **Verified** (key exists) | EV-002 | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) |
| `[appSettings] dataSendingPeriodSec`, `from_remote\screenshotPeriodSec`, `from_remote\ADUserInfoSendPerSec`, `screenshotQuality` | Configuration Keys | **Verified** (keys exist); semantics **Hypothesis** | EV-002 | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) |
| `[auth] crypto_password`, `email` — **CREDENTIALS. Keys exist; values were never read and must never be recorded** | Configuration Keys | **Verified** (keys exist only) | EV-002 | [RE-005 §6.0](../../knowledge_base/RE-005_Configuration_Loading.md) |
| Dashboard settings (synced to endpoint) | Configuration Source | **Hypothesis** — delivery mechanism unobserved; the `from_remote\` key prefix and the `wss` endpoint are the first on-disk traces | EV-002 | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md), [HB-002 §6](HB-002_Product_Architecture.md) |
| Precedence between the two `empm.ini` files, and between local and dashboard config | Configuration Behaviour | **Hypothesis** — entirely unestablished | — | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) |

## 6. Components — Inventory Index

This section is a meta-index rather than a table of its own; it lists the categories inventoried below and where each is sourced from.

| Category | Table Location | Primary Source(s) |
|---|---|---|
| Windows Services | §4 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| Configuration Files | §5 | [RE-005](../../knowledge_base/RE-005_Configuration_Loading.md) |
| Processes | §7 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| API Endpoints | §8 | [RE-006](../../knowledge_base/RE-006_API_Flow.md) |
| Folders | §9 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| Scheduled Task Entries | §10 | [RE-003](../../knowledge_base/RE-003_Scheduler.md) |
| Database Objects | §12 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| Log Files | §13 | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |

### 6.1 Status Counts

First promotion event in this chapter's history: the 2026-07-30 observation pass (see §3 metadata block).

Counts are of **inventory rows**, not of distinct product artifacts — where one row covers several artifacts (the 28 database tables, the Qt5 DLL set, the ffmpeg DLL set) it is counted once. A row's status is that of its **primary claim**; several Verified rows carry a Partially Verified or Hypothesis sub-claim about the artifact's *role*, noted inline rather than counted separately.

| Status | Count | Breakdown by section |
|---|---|---|
| **Verified** | **48** | §4 (2), §5 (7), §7 (6), §8 (2), §9 (15), §12 (8), §13 (8) |
| **Partially Verified** | **5** | §5 (1) tenant `empm.ini` as remote config; §8 (1) WebSocket channel; §12 (3) incl. the `pending_*` tables as the upload queue |
| **Hypothesis** | **22** | §4 (2), §5 (2), §7 (3), §8 (4), §9 (3), §10 (2), §12 (4), §13 (4) — incl. watchdog process/service, capture-output and failed-capture folders, all scheduled tasks, all API endpoint roles and auth, and all log formats/content |
| **Deprecated** | **2** | Both corrections below |

**Two previously-assumed facts are now Deprecated:**

1. **Install root `C:\Program Files\EmpMonitor`** → superseded by the **double-nested** `C:\Program Files\EmpMonitor\EmpMonitor` (§9). Path construction from the single-level assumption fails for every file.
2. **`ffmpeg.exe` as a candidate recorder binary** → **it does not exist.** ffmpeg ships as DLLs only; `esr.exe` is the sole recorder executable (§7, §9).

Previously this section read "Total components currently Verified: 0. Total Known (unverified): 3." The old "Known (unverified)" label maps to **Hypothesis** under the ratified four-status model ([knowledge_base README §6](../../knowledge_base/README.md)), which this chapter now uses throughout.

## 7. Processes — Process Inventory

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **`empmonitor.exe`** — `gui\`, **v3.7.4**, signature Valid. Observed running: ~56 MB WS, 20 threads, 581 handles, high accumulated CPU. Agent GUI / main process | Process | **Verified** (presence, version, signature, running); role **Partially Verified** | EV-010, EV-011, EV-013 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| **`emp_psa_service.exe`** — `service\`, **v3.7.3**, signature Valid. Observed running: ~12 MB WS, 15 threads, 304 handles. Hosted by `BrowserHandlingService` | Process | **Verified** | EV-005, EV-010, EV-011, EV-013 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| **`esr.exe`** — `gui\executables\`, **version resource unreadable**, signature Valid. Observed running: **~424 MB WS**, 14 threads. Screen recorder | Process | **Verified** (presence, signature, running); role **Partially Verified** | EV-010, EV-011, EV-013 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| **`UpdateMgr_Emp.exe`** — `gui\`, **v3.7.4**, signature Valid. Observed running continuously (~16 MB WS, 2 threads) with no update in progress. **Not previously documented** | Process | **Verified** (presence, version, signature, running); role **Partially Verified** | EV-010, EV-011, EV-013 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md), [RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md) |
| **`EmailMonitorSvc.exe`** — `gui\`, **v3.7.4**, signature Valid. **On disk but NOT running**, and **not** registered as a Windows service despite the name. **Not previously documented** | Process / Executable | **Verified** (presence, version, signature; not running) | EV-010, EV-013 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| **`Uninstaller.exe`**, **`compress_decompress_test.exe`** — `gui\` | Executables | **Verified** (presence only; version/signature not recorded) | EV-010 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| Watchdog process (if separate) | Process | **Hypothesis** — no watchdog-named process observed; embedded logic would be invisible to enumeration | EV-011 | [RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md) |
| Inter-process communication mechanism between the four running processes | Runtime Relationship | **Hypothesis** — no parent/child or control relationship established | — | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| Resource-usage baseline ("normal" CPU/RAM) | Runtime Metric | **Hypothesis** — figures above are a **single sample**, not a baseline; must not be used as thresholds | EV-011 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| ~~`ffmpeg.exe`~~ | Executable | **Deprecated** — **does not exist.** ffmpeg ships as DLLs (`avcodec-61`, `avformat-61`, `avfilter-10`, `avutil-59`, `swscale-8`, `libx264-164`, `libx265-215`); `esr.exe` is the only recorder executable | EV-010 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md), [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |

> **Version skew within one installation:** `gui` binaries are at **3.7.4**, the `service` binary at **3.7.3** (**Verified**). Whether this is intentional or a partial-update artifact is **Hypothesis**.

## 8. Known APIs — API Endpoint Inventory

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **4 endpoint URLs configured in `config.js`**, over the **`https`** and **`wss`** schemes. **URLs deliberately not recorded — deployment-specific** | API Endpoints | **Verified** (count + schemes) | EV-001 | [RE-006](../../knowledge_base/RE-006_API_Flow.md) |
| Endpoints are **configuration-driven, not hardcoded** | API Property | **Verified** | EV-001 | [RE-006](../../knowledge_base/RE-006_API_Flow.md) |
| **WebSocket channel exists** — evidenced by a `wss`-scheme endpoint plus `Qt5WebSockets.dll` in the install tree | Transport | **Partially Verified** — configured; **no connection or traffic observed** | EV-001, EV-010 | [RE-006](../../knowledge_base/RE-006_API_Flow.md), [Sync Monitor Design](../design/Synchronization_Monitor.md) |
| Which endpoint serves upload / config delivery / authentication / real-time signalling | API Endpoint Roles | **Hypothesis** — no endpoint role determined | — | [RE-006](../../knowledge_base/RE-006_API_Flow.md), [RE-004](../../knowledge_base/RE-004_Upload_Pipeline.md) |
| Authentication scheme | API Property | **Hypothesis** — unobserved. Local credential material exists (`[auth]`, §5) but its presentation to the server is unknown | — | [RE-006](../../knowledge_base/RE-006_API_Flow.md) |
| Request/response payloads, methods, status conventions, API version | API Contract | **Hypothesis** — entirely unobserved | — | [RE-006](../../knowledge_base/RE-006_API_Flow.md) |
| Dashboard↔server contract (same surface as agent's?) | API Endpoint | **Hypothesis** | — | [RE-006](../../knowledge_base/RE-006_API_Flow.md) |

> Note: the [Validation Standard](../ADS/validation_standard.md) §12 records that the Layer 3 collector is designed (see [Synchronization Monitor Design](../design/Synchronization_Monitor.md)) but not yet implemented. **All rows above come from reading a configuration file, not from traffic** — no API *contract* can yet be independently evidenced. The design's conditional "WebSocket lifecycle (if confirmed)" should now be planned for, as the channel's existence is confirmed in configuration.

## 9. Known Files — Folder Inventory

### 9.1 Install Tree — `C:\Program Files\EmpMonitor\EmpMonitor` (machine-wide)

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **`C:\Program Files\EmpMonitor\EmpMonitor`** — install root, **DOUBLE-NESTED** | Folder | **Verified** | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| ~~`C:\Program Files\EmpMonitor`~~ as install root | Folder | **Deprecated** — superseded by the double-nested path above; it is only the outer container | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `gui\` | Folder | **Verified** | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `gui\configs\` — holds `config.js`, `config_debug.js`, `config_release.js` | Folder | **Verified** | EV-001, EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `gui\executables\` — holds `esr.exe` + ffmpeg/x264/x265 DLLs | Folder | **Verified** | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `gui\translations\` | Folder | **Verified** (existence; contents not enumerated) | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `gui\plugins\` — **product** plugins; unrelated to this repo's `plugins/` | Folder | **Verified** (existence; contents not enumerated) | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `service\` — holds `emp_psa_service.exe` + service log/status files | Folder | **Verified** | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `WinDivert.dll` + `WinDivert64.sys` in `gui\` — network-packet interception library + kernel driver | Driver / Library | **Verified** (presence); active use **Hypothesis** | EV-010 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |
| Qt5 DLLs (`Qt5Core`, `Qt5Gui`, `Qt5Network`, `Qt5Sql`, `Qt5WebSockets`, others) distributed throughout the tree — the agent is a **Qt application** | Libraries | **Verified** | EV-010 | [RE-009](../../knowledge_base/RE-009_Runtime_Components.md) |

### 9.2 Data Tree — `%APPDATA%\screen` (per user)

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **`%APPDATA%\screen`** — data root, **per user**. Note the name contains no product identifier | Folder | **Verified**; per-user scope **Partially Verified** (one profile inspected) | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `%APPDATA%\screen\empm\` — holds `print_block.json`/`.jsonl`, `print_detection.json`/`.jsonl`/`.log` | Folder | **Verified** | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| **`%APPDATA%\screen\empm\logs\`** — agent log folder | Folder | **Verified** | EV-004, EV-010 | [RE-008](../../knowledge_base/RE-008_Logging_System.md), [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| **`%APPDATA%\screen\<TENANT>\`** — 7-character per-installation tenant folder. **Token must be discovered at runtime, never hardcoded**; the observed value is deliberately not recorded | Folder | **Verified** (that such a folder exists, per installation) | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `%APPDATA%\screen\<TENANT>\empm\` — holds `local_db20.db` and `userProfile.png` | Folder | **Verified** | EV-003, EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| `%APPDATA%\screen\<TENANT>\empm\userProfile.png` | File | **Verified** (presence) | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| Capture output folder(s) | Folder | **Hypothesis** — **none found.** No on-disk capture-output folder was located anywhere | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| "Failed screenshots" / "failed recordings" folders | Folder | **Hypothesis** — **did not exist** at observation time; their names remain **UNVERIFIED** and must not be used | EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md) |
| Upload queue / staging folder | Folder | **Hypothesis** — **none found.** Queue state appears to live in SQLite instead (§12) | EV-003, EV-010 | [RE-010](../../knowledge_base/RE-010_Folder_Structure.md), [RE-012](../../knowledge_base/RE-012_Offline_Synchronization.md) |

## 10. Scheduler — Scheduled Task Entries

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| Agent startup/restart task (if any) | Scheduled Task | **Hypothesis** | — | [RE-003](../../knowledge_base/RE-003_Scheduler.md) |
| Feature-driven scheduled task(s) | Scheduled Task | **Hypothesis** | — | [RE-003](../../knowledge_base/RE-003_Scheduler.md) |

> **Scheduled tasks were not enumerated during the 2026-07-30 pass.** This category is therefore unchanged and remains wholly Hypothesis. Note this is the last unexamined candidate implementation for a watchdog ([RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md)) and is cheap to check. The service `BrowserHandlingService` is AUTO_START (§4), so at least the service does not depend on a scheduled task to launch.

## 11. Storage

Not applicable as a separate table — storage locations are captured under Folders (§9) and Database Objects (§12). See also [HB-004 §11](HB-004_Agent_Ecosystem.md) for the dependency-level discussion of where sync/queue state lives.

> **That dependency-level question now has a partial answer:** upload-queue state appears to live in the six `pending_*` SQLite tables (§12), **not** in a file system staging folder — no such folder exists (§9.2). **Partially Verified.**

## 12. SQLite — Database Object Inventory

### 12.1 Database File

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **`local_db20.db`** — `%APPDATA%\screen\<TENANT>\empm\local_db20.db`, **~1.18 MB**. Per user and per installation; tenant token discovered at runtime | Database File | **Verified** | EV-003, EV-010 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| Sole database (no other `.db` found) | Database File | **Partially Verified** — no exhaustive filesystem-wide search performed | EV-010 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| Container not encrypted — schema readable while the agent ran | Database Property | **Partially Verified** — column-level encryption not ruled out | EV-003 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| **28 tables total; 9 populated, 19 empty** | Schema | **Verified** | EV-003 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| Columns, types, keys, indices | Schema | **Hypothesis** — **never read**; schema verified at table-name granularity only | — | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |

> **Privacy constraint.** Only **table names and row counts** were read. **No row contents were read and none may be recorded** — this database holds captured employee monitoring data. Automation may assert on schema shape and counts only. See [RE-007 §6.0](../../knowledge_base/RE-007_SQLite_Database.md).

### 12.2 Tables — All 28 Verified to Exist

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **`pending_screenshots6`**, **`pending_usagedata6`**, **`pending_usbdata6`**, **`pending_clipboardata`**, **`pending_aduserproperties6`**, **`pending_bluetoothdata`** | Database Tables | **Verified** (exist) | EV-003 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| **The six `pending_*` tables ARE the upload queue** — resolving where queue state lives, an open question in RE-004, RE-012, HB-001 §6 and Validation Standard §4 | Database Behaviour | **Partially Verified** — tables exist and are named `pending`; that they *function* as the queue is a strong inference corroborated by the absence of any file system queue, but **no row was observed enqueued or drained** | EV-003, EV-010 | [RE-012](../../knowledge_base/RE-012_Offline_Synchronization.md), [RE-007 §6.3](../../knowledge_base/RE-007_SQLite_Database.md) |
| Row lifecycle — delete on success, move to counterpart, or status flag | Database Behaviour | **Hypothesis** — no columns read, no upload observed | — | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| `event_data`, `sent_event_data` — apparent **sent/unsent split** | Database Tables | **Verified** (exist); the split **Partially Verified** (from naming) | EV-003 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| `tbl_exception_log2` — apparent **agent-side error/exception log table**, i.e. error history is not file-only | Database Table | **Verified** (exists); role **Partially Verified** | EV-003 | [RE-008](../../knowledge_base/RE-008_Logging_System.md), [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| `PrintBlocking`, `PrintDetection`, `UploadBlocking`, `UploadDetection`, `UploadDetectionImage` — blocking/detection **features**, **not** the agent's own upload pipeline | Database Tables | **Verified** (exist); feature attribution **Partially Verified** | EV-003 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| `usagedata6`, `clipboardData`, `usbdata6`, `bluetoothdata`, `clock_data6`, `download_history`, `data_consumption`, `PrivateIp`, `PublicIp`, `user_details` | Database Tables | **Verified** (exist); feature mapping **Hypothesis** | EV-003 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| `inbound_emails`, `outbound_emails`, `mail_data`, `mail_attachment_data` | Database Tables | **Verified** (exist); feature mapping **Hypothesis** | EV-003 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md) |
| Screen-recording storage table | Database Object | **Hypothesis** — **no table name suggests recordings**, and no on-disk capture folder exists either; the recording persistence path is unaccounted for | EV-003, EV-010 | [RE-007](../../knowledge_base/RE-007_SQLite_Database.md), [RE-012](../../knowledge_base/RE-012_Offline_Synchronization.md) |
| Settings/configuration table | Database Object | **Hypothesis** — **none observed**; configuration appears to live in the INI/JS files instead (negative inference from table names only) | EV-003 | [RE-005 §10](../../knowledge_base/RE-005_Configuration_Loading.md) |

> **Which 9 tables held rows, and their counts, are deliberately not fixed here** — they reflect one endpoint's usage history, not product behaviour, and would mislead if read as expected values. **An empty table is not a defect:** 19 of 28 were empty on a healthy endpoint.

## 13. Logs — Log File Inventory

**Logging is decentralised: four locations across three media.** Every row below is **Verified as to existence and location**; **no log file was opened**, so format, levels and content are **Hypothesis** throughout.

| Name | Category | Status | Evidence | Reference Document |
|---|---|---|---|---|
| **`%APPDATA%\screen\empm\logs\<date>.txt`** — main agent log, **date-named** (observed: `2026-07-30.txt`), per user | Log File | **Verified** (location + naming); daily rotation **Partially Verified** (only one day's file present); retention **Hypothesis** | EV-004, EV-010 | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |
| **`<install root>\service\EMP_SERVICE.log`** — service log. **Inside Program Files**; elevation may be required | Log File | **Verified** (presence) | EV-010 | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |
| **`<install root>\service\EMP_SERVICE2.txt`** — secondary/rotated service log | Log File | **Verified** (presence); role **Hypothesis** | EV-010 | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |
| **`<install root>\service\CurrentStatus.txt`** — apparent current-state snapshot; candidate agent-state signal | Status File | **Verified** (presence); role **Hypothesis** | EV-010 | [RE-008](../../knowledge_base/RE-008_Logging_System.md), [RE-013](../../knowledge_base/RE-013_Agent_State_Machine.md) |
| **`<install root>\service\UpdateProgress.txt`** — update-progress state; plausibly written by `UpdateMgr_Emp.exe` | Status File | **Verified** (presence); writer **Hypothesis** | EV-010 | [RE-008](../../knowledge_base/RE-008_Logging_System.md), [RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md) |
| **`%APPDATA%\screen\empm\print_detection.log`** — feature log, sitting **beside** `logs\` rather than inside it | Log File | **Verified** (presence) | EV-010 | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |
| `%APPDATA%\screen\empm\print_detection.json`/`.jsonl`, `print_block.json`/`.jsonl` — apparent state + append-only structured event streams | Structured Logs | **Verified** (presence); append-only semantics **Hypothesis** | EV-010 | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |
| **`tbl_exception_log2`** in `local_db20.db` — **database-resident** error log; file-only collection is an incomplete error picture | Log Object | **Verified** (exists); role **Partially Verified** | EV-003 | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |
| Log format, levels, entry content, verbosity configuration | Log Property | **Hypothesis** — **no log contents were read** | — | [RE-008](../../knowledge_base/RE-008_Logging_System.md) |
| Watchdog/recovery log (if separate) | Log File | **Hypothesis** — none identified | — | [RE-008](../../knowledge_base/RE-008_Logging_System.md), [RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md) |
| Upload/sync log (if separate) | Log File | **Hypothesis** — none identified | — | [RE-008](../../knowledge_base/RE-008_Logging_System.md), [RE-004](../../knowledge_base/RE-004_Upload_Pipeline.md) |
| Windows System event log | External Log | **Hypothesis** — not examined; **no collector assigned** and not registered in the [Evidence Catalog](../Evidence_Catalog.md) | — | [RE-002](../../knowledge_base/RE-002_Watchdog_Behaviour.md) |

## 14. Failure Modes

Not applicable to this chapter's scope — this is a static inventory, not a behavioral document. See [HB-003 §14](HB-003_Agent_Architecture.md) (Agent-internal) and [HB-004 §14](HB-004_Agent_Ecosystem.md) (dependency-level) for failure modes of the components listed above.

## 15. Recovery

Not applicable to this chapter's scope. See [HB-003 §15](HB-003_Agent_Architecture.md) and [HB-004 §15](HB-004_Agent_Ecosystem.md).

## 16. Troubleshooting

Not applicable to this chapter's scope. See the per-component chapters and RE documents referenced in each table above.

## 17. Evidence Sources

This inventory is itself not evidence — it is an index pointing at where evidence-backed claims live. Evidence sources for each category are named in the [Validation Standard](../ADS/validation_standard.md) §4 evidence source catalog and registered in the [Evidence Catalog](../Evidence_Catalog.md); the Evidence and Reference Document columns above link each row to the source and the document responsible for it.

Sources that substantiated the 2026-07-30 promotions: **EV-001** (`config.js`), **EV-002** (`empm.ini`), **EV-003** (local SQLite), **EV-004** (agent logs — location only), **EV-005** (Windows service state), **EV-010** (file system artifacts), **EV-011** (process/resource usage), **EV-012** (host OS identification), **EV-013** (executable file metadata).

Two constraints govern how these sources may be re-read, and both come from what was found rather than from policy preference:

1. **EV-003 is count-only.** `local_db20.db` holds captured monitoring data; table names and row counts are readable, row contents are not ([RE-007 §6.0](../../knowledge_base/RE-007_SQLite_Database.md)).
2. **EV-001 and EV-002 carry secrets.** `config.js` holds deployment endpoint URLs; `empm.ini` `[auth]` holds `crypto_password` and `email`. Assert on structure; never emit values.

## 18. Version Notes

| Version | Date | Notes |
|---|---|---|
| EmpMonitor **`gui` components 3.7.4** / **`service` component 3.7.3**; host Windows 10 Pro build 10.0.19045 x64 | 2026-07-30 | **First version this inventory reflects.** Single host, single installation, single user profile, single point in time. Promoted 48 rows to Verified and 5 to Partially Verified; recorded 2 Deprecated corrections (double-nested install root; `ffmpeg.exe` does not exist). `esr.exe` has no readable version resource, so no version is attributable to it even on this build. |

**Intra-install version skew is expected:** `gui` at 3.7.4, `service` at 3.7.3 (§7). Whether that is by design is unestablished.

Per the [verification workflow](../../knowledge_base/README.md) §7 step 6, every Verified row must be re-checked when a new EmpMonitor version is encountered, and demoted to **Deprecated** with a pointer to its replacement if broken. The rows most likely to break on update are the folder paths (§9), the table set and its numeric suffixes (§12), and the service name (§4).

## 19. Cross References

- [HB-001 — Product Overview](HB-001_Product_Overview.md)
- [HB-002 — Product Architecture](HB-002_Product_Architecture.md)
- [HB-003 — Agent Architecture](HB-003_Agent_Architecture.md)
- [HB-004 — Agent Ecosystem](HB-004_Agent_Ecosystem.md)
- [Reverse Engineering Knowledge Base](../../knowledge_base/README.md) — verification status model (§6) and workflow (§7)
- [Validation Standard](../ADS/validation_standard.md)
- [Evidence Catalog](../Evidence_Catalog.md)
- [RE-002 — Watchdog Behaviour](../../knowledge_base/RE-002_Watchdog_Behaviour.md)
- [RE-005 — Configuration Loading](../../knowledge_base/RE-005_Configuration_Loading.md)
- [RE-006 — API Flow](../../knowledge_base/RE-006_API_Flow.md)
- [RE-007 — SQLite Database](../../knowledge_base/RE-007_SQLite_Database.md)
- [RE-008 — Logging System](../../knowledge_base/RE-008_Logging_System.md)
- [RE-009 — Runtime Components](../../knowledge_base/RE-009_Runtime_Components.md)
- [RE-010 — Folder Structure](../../knowledge_base/RE-010_Folder_Structure.md)
- [RE-012 — Offline Synchronization](../../knowledge_base/RE-012_Offline_Synchronization.md)

---
**Document Status:** Active — first promotion event 2026-07-30 against EmpMonitor gui 3.7.4 / service 3.7.3. **48 rows Verified, 5 Partially Verified, 22 Hypothesis, 2 Deprecated** (was: 0 Verified, 3 Known). Corrections recorded: install root is double-nested `EmpMonitor\EmpMonitor`; `ffmpeg.exe` does not exist. Scheduled tasks (§10) still unenumerated. Reviewer sign-off outstanding on all promotions.
**Owner:** TODO
**Last Updated:** 2026-07-30
