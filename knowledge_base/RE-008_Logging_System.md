# RE-008 — Logging System

## 1. Purpose

This document records what is known and verified about the EmpMonitor Windows Agent's **own local log output** — for use by automation developers building Layer 2 (Runtime) validation and diagnosing agent-side failures.

## 2. Scope

Covers the agent's own local log files/streams produced on the endpoint as a byproduct of its operation. This is **distinct from the automation framework's own logging**, which is produced by this repository's test/validation runs and is governed by [`docs/ADS/logging_standard.md`](../docs/ADS/logging_standard.md) (framework logging goes through `framework/shared/logger.py`). This document is only about logs the *product under test* (EmpMonitor) writes on its own, independent of whether the framework is running at all. Does not cover dashboard-side or server-side logging (unaddressed in current handbook docs).

## 3. Architecture

**Logging is decentralised — there is no single log.** Log and status artifacts were found in **four distinct places across three media** (§6):

| # | Location | Medium | Scope |
|---|---|---|---|
| 1 | `%APPDATA%\screen\empm\logs\<date>.txt` | Date-named text file | Per user — the agent's general log |
| 2 | `<install root>\service\EMP_SERVICE.log`, `EMP_SERVICE2.txt`, `CurrentStatus.txt`, `UpdateProgress.txt` | Text files **inside Program Files** | Machine-wide — service side |
| 3 | `%APPDATA%\screen\empm\print_detection.log` (plus `.json`/`.jsonl` companions) | Feature-specific log **outside** the `logs\` folder | Per user |
| 4 | `tbl_exception_log2` in `local_db20.db` | **SQLite table**, not a file | Per user, per installation |

Three consequences follow, and each is a correction to how this document was previously framed:

- **"Where does the agent log?" has no single answer.** Reading only `%APPDATA%\screen\empm\logs\` gives an incomplete picture — it omits the service side entirely and the database-resident error log completely.
- **Some logs live in the install tree**, i.e. the product writes runtime state into Program Files (see [RE-010](RE-010_Folder_Structure.md)), which normally requires elevation. Log collection therefore has *two different permission profiles*.
- **At least one error log is not a file at all** — `tbl_exception_log2` ([RE-007](RE-007_SQLite_Database.md)) means file-based log collection alone cannot be a complete error picture.
- **Location 1 is not durable.** The agent was observed **emptying `%APPDATA%\screen\empm\logs\` itself** during a session (§6.5). Locating a log is therefore not the same as having it, and any evidence taken from that directory must be copied out at read time.

Whether logging is centralised in one code module is **Hypothesis**; the spread of naming conventions (`.log`, `.txt`, `.jsonl`, a database table) suggests it is not. Which process writes which artifact is **Hypothesis** — only co-location was observed (§6.4).

## 4. Sequence / Flow

> **TODO / Hypothesis:** nothing is established about *when* entries are written relative to the agent lifecycle. **No log file contents were read during the 2026-07-30 pass** — only the existence, names and locations of log artifacts were observed. A sequence diagram would therefore be pure invention and is deliberately omitted. The correlation of log entries with startup, capture, upload, shutdown or error events is the central open question in §16.

## 5. Known Behaviour (unverified)

- HB-001 and HB-002 identify "Local Logs" as a component of the EmpMonitor ecosystem, produced agent-side on the endpoint (stated by project charter, not independently confirmed). **Now confirmed to exist** (§6) — the charter statement was correct, though it understated the case: logs exist in four locations, not one.
- The Validation Standard ([validation_standard.md §4](../docs/ADS/validation_standard.md)) lists "Log content" as a Layer 2 evidence source, implying stakeholders expect log files to be inspectable as part of runtime validation. **Only partly confirmed:** log files were confirmed to *exist and be locatable*; their **content was not read**, so "log content" as an evidence source is not yet demonstrated to be usable. EV-004's Medium confidence rating remains untested in practice.

## 6. Verified Behaviour (with evidence + version)

All claims in this section derive from a single observation pass on **2026-07-30** against one real installation. The [README §6.1](README.md) metadata fields common to every claim are stated once here rather than repeated per row:

| Field | Value |
|---|---|
| `Verified On` | 2026-07-30 |
| `Verified Against Version` | EmpMonitor `gui` components **3.7.4** / `service` component **3.7.3**; host Windows 10 Pro build 10.0.19045 x64 |
| `Verification Method` | Observed by `EM000_EnvironmentValidator` plugin run plus direct filesystem inspection |
| `Reviewer` | TODO — reviewer sign-off ([README §7](README.md) step 4) not yet performed |
| `Last Review Date` | 2026-07-30 |

> **Scope limit — and it is a severe one for this document.** Every claim below concerns the **existence, name and location** of log artifacts. **No log file was opened and no log content, format, level, or entry was read.** Nothing here evidences what the agent logs, when, or in what format.

### 6.1 Agent Log Folder (Per User)

| # | Claim | Status | Evidence Source |
|---|---|---|---|
| 8-V1 | The agent log folder is `%APPDATA%\screen\empm\logs\` — per user, in the data tree, **not** under the install root. | **Verified** | EV-004, EV-010 |
| 8-V2 | It contained a **date-named** log file: **`2026-07-30.txt`** — i.e. a `<date>.txt` naming convention, and a `.txt` extension rather than `.log`. | **Verified** | EV-004, EV-010 |
| 8-V3 | The convention implies **one file per calendar day** (daily rotation by filename). | **Partially Verified** — the naming is unambiguous, but **only one day's file was present**, so rotation across days was not observed | EV-010 |
| 8-V4 | Retention: how many days are kept, and whether old files are deleted, compressed, or accumulate indefinitely. Only one file existed — which is equally consistent with same-day installation, aggressive purging, or a 1-day retention policy. | **Hypothesis** | — |
| 8-V5 | Log format, encoding, log levels, and what events are recorded. **Contents not read.** | **Hypothesis** | — |

### 6.2 Service-Side Logs and Status Files (Install Tree)

| # | Claim | Status | Evidence Source |
|---|---|---|---|
| 8-V6 | `<install root>\service\` contains **`EMP_SERVICE.log`** — the only artifact observed with a conventional `.log` extension. | **Verified** | EV-010 |
| 8-V7 | The same folder contains **`EMP_SERVICE2.txt`**. The `2` suffix suggests a second/rotated/secondary service log. | **Verified** (presence); the role of the `2` suffix **Hypothesis** | EV-010 |
| 8-V8 | The same folder contains **`CurrentStatus.txt`** — by name, a **status** file rather than an append-only log, i.e. likely a small current-state snapshot. | **Verified** (presence); role **Hypothesis** | EV-010 |
| 8-V9 | The same folder contains **`UpdateProgress.txt`** — by name, update/upgrade progress state. Plausibly written by `UpdateMgr_Emp.exe` ([RE-009](RE-009_Runtime_Components.md)), which was observed running continuously. | **Verified** (presence); writer and role **Hypothesis** | EV-010 |
| 8-V10 | These four artifacts reside **inside `C:\Program Files\`**, so reading them may require elevation, unlike the per-user logs in §6.1. | **Verified** (location) | EV-010 |
| 8-V11 | That `CurrentStatus.txt` is a machine-readable agent-state indicator usable for Layer 2 validation — potentially valuable for [RE-013](RE-013_Agent_State_Machine.md). | **Hypothesis** — contents not read; worth investigating early given its name | — |

### 6.3 Feature-Specific and Database-Resident Logs

| # | Claim | Status | Evidence Source |
|---|---|---|---|
| 8-V12 | **`%APPDATA%\screen\empm\print_detection.log`** exists — a feature-specific log sitting in `empm\` **beside** the `logs\` folder rather than inside it. Feature logs are therefore not confined to the log folder. | **Verified** | EV-010 |
| 8-V13 | Companion structured files exist in the same folder: `print_detection.json`, `print_detection.jsonl`, `print_block.json`, `print_block.jsonl`. The `.jsonl` (JSON Lines) extension conventionally denotes an **append-only event stream** — i.e. a structured log. | **Verified** (presence); the append-only semantics **Hypothesis** (contents not read) | EV-010 |
| 8-V14 | If 8-V13 holds, the product uses **both** unstructured (`.log`, `.txt`) and structured (`.jsonl`) logging, and structured output would be substantially easier for automation to parse reliably. | **Hypothesis** | — |
| 8-V15 | **`tbl_exception_log2`**, a table in `local_db20.db`, appears to be an **agent-side error/exception log held in the database rather than in a file**. See [RE-007](RE-007_SQLite_Database.md) 7-V11. | **Partially Verified** — the table name is explicit; contents not read and no error correlated with it | EV-003 |
| 8-V16 | Consequently, **agent error history spans at least two media** (files and the database), and file-only log collection is incomplete for error detection. Its **row count** is a privacy-safe internal-error indicator (no row contents may be read — see [RE-007 §6.0](RE-007_SQLite_Database.md)). | **Partially Verified** (follows from 8-V15) | EV-003 |

### 6.4 Log-to-Component Ownership

| # | Claim | Status | Evidence Source |
|---|---|---|---|
| 8-V17 | The `service\` log/status files are **co-located** with `emp_psa_service.exe`, and the `%APPDATA%\screen\empm\` logs are in the per-user data tree alongside the agent's other per-user state. | **Verified** (co-location) | EV-010 |
| 8-V18 | That `emp_psa_service.exe` writes the `service\` files and `empmonitor.exe` the per-user logs. | **Hypothesis** — co-location is suggestive, not evidence. No file handle, write event, or process-to-file association was observed | — |

### 6.5 The Agent Empties Its Own Log Directory — Log Evidence Is Not Durable

The single most consequential operational fact in this document, and it is not about log *content*.

| Field | Value |
|---|---|
| `Verified On` | 2026-07-30 |
| `Verified Against Version` | EmpMonitor `gui` **3.7.4** / `service` **3.7.3**, Windows 10 Pro 19045 |
| `Evidence Source` | **EV-007** (synchronization/log observation), corroborated by **EV-010** (filesystem) |
| `Verification Method` | Observed by `EM000`/`EM001` plugin runs plus direct inspection |
| `Reviewer` | TODO — sign-off outstanding |
| `Last Review Date` | 2026-07-30 |

| # | Claim | Status | Evidence Source |
|---|---|---|---|
| 8-V19 | The agent's log directory **`%APPDATA%\screen\empm\logs\`** was observed to be **emptied during a single session** on 2026-07-30 — log files that had been present and readable were subsequently gone. | **Verified** | EV-007, EV-010 |
| 8-V20 | **The agent emptied it itself.** No framework action, no operator action and no external process removed the files; the deletion occurred while the agent ran and nothing else touched the directory. | **Verified** | EV-007, EV-010 |
| 8-V21 | **Log-derived evidence is therefore not durable.** Any validation resting on log content can lose **its entire evidence base**, mid-run and without warning — not a degraded or truncated log, but no log at all. | **Verified** (follows directly from 8-V19 and 8-V20) | EV-007, EV-010 |
| 8-V22 | What triggers the purge — rotation policy, a size or age bound, a lifecycle event such as sign-out or restart, or an explicit cleanup routine. **Not established.** The removal was observed; its cause was not. | **Hypothesis** | — |
| 8-V23 | Whether the same behaviour applies to the service-side files in the install tree (§6.2), the feature logs beside `logs\` (§6.3), or `tbl_exception_log2`. **Only the per-user `logs\` directory was observed being emptied.** | **Hypothesis** | — |

This **supersedes 8-V4's framing.** 8-V4 offered three explanations for finding only one day's log file — same-day installation, aggressive purging, or a 1-day retention policy — and treated them as equally open. Purging is now **observed**, so it is no longer a candidate among three; what remains open is only what triggers it (8-V22).

#### Why this matters more than a retention detail

The [Synchronization Architecture Report §3](../docs/Synchronisation_Architecture_Report.md) adopted **log-derived observation as the primary Layer 3 strategy**, having measured its fidelity as High — richer than expected, and rich enough that payload interception was rejected as unnecessary. That decision stands. But it now carries a named structural risk: **the primary evidence source for Layer 3 is one the product may delete at any moment.**

Concretely, the features whose expectations rest on log patterns — `EM010_Screenshots`, `EM017_ApplicationUsage`, `EM023_EmailMonitoring` ([HB-006](../docs/handbook/HB-006_Feature_Specifications.md)) — can each lose their evidence base between one sample and the next. `EM023_EmailMonitoring` is the sharpest case: it is the **only feature profiled Verified**, and its status rests substantially on log evidence.

#### The framework handled this correctly

Worth recording precisely, because it is the design behaving as specified rather than luck. When the logs disappeared, the framework **degraded the affected finding to `INCONCLUSIVE`** and **invented no failure**. It did not report a broken feature, did not infer absence of activity from absence of evidence, and did not silently pass. That is exactly the behaviour [Synchronization Architecture Report §3](../docs/Synchronisation_Architecture_Report.md) commits to — "a pattern that stops matching degrades to `INCONCLUSIVE` — never to a false negative" — extended to the harsher case where the file itself is gone.

**The fragility is nonetheless inherent and cannot be engineered away by the framework.** Correct handling of a vanished evidence source is not the same as having the evidence. Consequences that bind all future work here:

1. **Collect logs eagerly and copy them out.** A log read at the moment of observation and persisted under `reports/` is durable; a path recorded for later reading is not. Never defer a log read to a later phase of a run.
2. **`INCONCLUSIVE` is the only correct verdict when logs are absent.** Absence of a log line is not evidence that the logged event did not occur — before this finding that was a defensible reading of a missing entry; it is now demonstrably wrong.
3. **Never treat log absence as a product defect**, and never treat it as a pass either.
4. **Do not build a validation whose *only* evidence source is a log**, where an alternative exists. `pending_*` row counts (EV-003) and connection state (EV-017) survive a log purge; log content does not.
5. **Distinguish "log absent" from "log unreadable" from "pattern not matched"** in findings. Three different diagnoses, and after this finding all three are live.

## 7. Configuration Inputs

**Partially Verified — negative result.** No configuration key governing logging was observed:

- The verified sections of the root `empm.ini` (`[General]`, `[appSettings]`, `[auth]` — see [RE-005](RE-005_Configuration_Loading.md)) contain **no** log-verbosity, log-path, or log-retention key.
- `config.js` is 324 bytes of endpoint configuration only, with no logging key recorded.
- **However**, the ~4.7 KB tenant-level `empm.ini` was **not** fully enumerated, so a logging key may exist there. This is the place to look.

Whether verbosity is configurable at all is therefore **Hypothesis**. The presence of `config_debug.js` alongside `config_release.js` ([RE-010](RE-010_Folder_Structure.md)) hints at build-level debug/release logging behaviour, but that is inference from filenames only.

## 8. Known Files

**Verified** locations (metadata block as §6). **Contents of every artifact below are unread**; the Format column records what the *extension* conventionally implies, not observed format.

### 8.1 Per-User — `%APPDATA%\screen\` (data tree, no elevation expected)

| Path | Format (by convention) | Notes |
|---|---|---|
| `empm\logs\<date>.txt` | Plain text | Agent log; observed instance `2026-07-30.txt`. One file per day (8-V3) |
| `empm\print_detection.log` | Plain text | Print-detection feature log, outside `logs\` |
| `empm\print_detection.jsonl` | JSON Lines | Structured print-detection event stream (**Hypothesis**) |
| `empm\print_detection.json` | JSON | Print-detection state (**Hypothesis**) |
| `empm\print_block.jsonl` | JSON Lines | Structured print-block event stream (**Hypothesis**) |
| `empm\print_block.json` | JSON | Print-block state (**Hypothesis**) |

### 8.2 Machine-Wide — `C:\Program Files\EmpMonitor\EmpMonitor\service\` (install tree, elevation may be required)

| Path | Format (by convention) | Notes |
|---|---|---|
| `EMP_SERVICE.log` | Plain text | Primary service log |
| `EMP_SERVICE2.txt` | Plain text | Secondary/rotated service log (role unverified) |
| `CurrentStatus.txt` | Plain text | Current-state snapshot (role unverified; see 8-V11) |
| `UpdateProgress.txt` | Plain text | Update progress state (writer unverified) |

### 8.3 Database-Resident

| Object | Location | Notes |
|---|---|---|
| `tbl_exception_log2` | `%APPDATA%\screen\<TENANT>\empm\local_db20.db` | Apparent agent-side error log **table** (8-V15). Row **counts** only — never row contents |

Note the install root is **double-nested** (`EmpMonitor\EmpMonitor`), correcting an earlier hypothesis — see [RE-010](RE-010_Folder_Structure.md).

## 9. Known APIs

Not applicable to this subject — agent logging is local file/stream output, not an API surface. See [RE-006](RE-006_API_Flow.md) for API contracts.

## 10. Storage / SQLite

**Now applicable — this section's former premise is superseded.** The agent appears to write at least some log data into SQLite as well as to flat files: **`tbl_exception_log2`** in `local_db20.db` is, by name, an agent-side exception log (8-V15, **Partially Verified**). See [RE-007](RE-007_SQLite_Database.md) 7-V11.

For automation this means error detection must query the database as well as read files, and that the table's **row count** is a usable internal-error signal. **Row contents must never be read** — that database holds captured monitoring data ([RE-007 §6.0](RE-007_SQLite_Database.md)).

## 11. Logs

Status of the five items this section previously listed as unknown:

| Item | Status | Detail |
|---|---|---|
| Log file name(s) and count | **Verified** | Four locations, three media — see §3 and §8. At least nine distinct artifacts including the database table. |
| Format (plain text, structured/JSON, binary) | **Hypothesis** | **No file was opened.** Extensions imply plain text (`.log`, `.txt`) and JSON Lines (`.jsonl`), but nothing was confirmed. |
| Log levels used, if any | **Hypothesis** | Not established. |
| What events are logged | **Hypothesis** | Not established. `tbl_exception_log2` and `print_detection.log` suggest errors and print events are among them (names only). |
| Rotation / retention | **Partially Verified** — with one **Verified** component | Date-based filename implies daily rotation (8-V3); retention depth unknown (8-V4). **Verified: the agent empties `%APPDATA%\screen\empm\logs\` itself, mid-session (8-V19, 8-V20)** — so log evidence is not durable (8-V21). The purge *trigger* is unknown (8-V22). Service-side `EMP_SERVICE2.txt` may be a rotation artifact (8-V7). |
| Human-readable vs. tool-required | **Hypothesis** | Extensions suggest human-readable; unconfirmed. |

**The gap is now sharply defined:** *where* the agent logs is verified; *what and how* it logs is entirely unverified. Closing it requires only reading files that are already located.

## 12. Failure Modes

**One is now observed** (the first item); every other item below remains **Hypothesis**. Items two and three are *framework* failure modes:

- **The agent empties its own log directory mid-session — OBSERVED, not hypothetical** (8-V19, 8-V20). Any check holding a log path for later reading loses its evidence entirely. The correct response is `INCONCLUSIVE`; the mitigation is to read and copy logs at the moment of observation (§6.5).


- **Collecting only `%APPDATA%\screen\empm\logs\`** and concluding the agent is silent, while the service-side files and `tbl_exception_log2` go unread. The most likely defect in any log check written from the pre-2026-07-30 picture.
- **Elevation failure on the install tree** (8-V10) reported as "log missing" rather than "log unreadable" — a materially different diagnosis.
- Date-named log file absent for the current date despite the agent running — **and note this is now known to be a normal state**, not a defect signal, since the agent purges the directory itself (8-V19). Report it as absence of evidence.
- Log file present but not growing while the agent is active.
- `EMP_SERVICE.log` or `EMP_SERVICE2.txt` growing unbounded — no retention behaviour is established for the service side at all (8-V7).
- Per-user logs accumulating one file per day without purge (8-V4).
- `CurrentStatus.txt` stale — its mtime not advancing would suggest the service is not updating state (**Hypothesis**: it is written periodically at all).
- `UpdateProgress.txt` stuck mid-update, indicating a failed or hung upgrade.
- `tbl_exception_log2` row count rising, indicating internal errors otherwise invisible in files (8-V16).
- Log path not writable, with unknown agent response (§13).
- Log format changing between versions and breaking parsers — an acute risk, since no format is yet pinned.

## 13. Recovery

> **TODO / Hypothesis:** unestablished and untested. No log file was deleted, truncated, or made unwritable during the 2026-07-30 pass, so whether the agent recreates a missing log file, fails silently, or fails loudly is unknown. The four-location layout (§3) makes this compound: behaviour may differ between the per-user log folder (agent-writable) and the install-tree service folder (elevation-gated). See [RE-011](RE-011_Recovery_Behaviour.md).

## 14. Troubleshooting

Log-collection recipe, now that locations are verified. **All of it is location guidance** — no step interprets log content, because no format is established.

> **Do this first, before any step below: read and copy logs at the moment of observation.** The agent empties `%APPDATA%\screen\empm\logs\` itself (§6.5, 8-V19). A recorded path is not evidence; a copy persisted under `reports/` is. If the files are gone, the verdict is `INCONCLUSIVE` — never a failure and never a pass.

1. **Collect from all four locations, not one** (§3). A log check that reads only the per-user `logs\` folder is incomplete by construction.
2. **Per-user log:** `%APPDATA%\screen\empm\logs\<today>.txt`, with `%APPDATA%` resolved for the *monitored user*. Expect the file to be named for the current date; its absence for today while the agent runs is a signal worth capturing.
3. **Service-side:** `C:\Program Files\EmpMonitor\EmpMonitor\service\` — `EMP_SERVICE.log`, `EMP_SERVICE2.txt`, `CurrentStatus.txt`, `UpdateProgress.txt`. Use the **double-nested** root. Expect to need elevation, and distinguish "unreadable" from "absent" in findings (8-V10).
4. **Feature log:** `%APPDATA%\screen\empm\print_detection.log` plus the `.json`/`.jsonl` companions. Note these sit *beside* `logs\`, not inside it.
5. **Database error log:** query the **row count** of `tbl_exception_log2` in `local_db20.db` (tenant path discovered at runtime). **Never read its rows.**
6. **Prefer mtime and size deltas over content parsing** for now. File-growth signals are available today; content assertions are not, and a parser written against an unread format will be wrong.
7. **Check `CurrentStatus.txt` early** when investigating agent state — its name suggests a state snapshot, which would be a cheap Layer 2 signal if confirmed (8-V11).
8. **Do not assert on log format, levels, or message text.** Nothing about format is verified; any such assertion today is guesswork.

## 15. Evidence Sources for Automation

| Source | Layer | Collector | Status |
|---|---|---|---|
| Log file presence | 2 | `framework/monitors/log_monitor.py` | Scaffolded, unimplemented (0 lines) |
| Log content | 2 | `framework/monitors/log_monitor.py` | Scaffolded, unimplemented (0 lines) |
| Log file presence/location (file system) | 2 | `framework/monitors/folder_monitor.py` | EV-010 — how the four locations in §3 were actually found |
| Database-resident error log (`tbl_exception_log2`) | 2 | `framework/monitors/sqlite_monitor.py` | EV-003 — row **count** only; see [RE-007 §6.0](RE-007_SQLite_Database.md) |

`framework/monitors/log_monitor.py` exists in the repository scaffold but currently contains no implementation. It is the intended observation point for this subject; no behaviour should be assumed from its name alone. The 2026-07-30 observations in §6 came from the `EM000_EnvironmentValidator` plugin plus direct filesystem inspection, not from `log_monitor.py`.

**Requirements this document places on `framework/monitors/log_monitor.py`:**

1. Collect from **all four locations** (§3), including the install tree and the SQLite table — not just the per-user `logs\` folder.
2. Resolve `%APPDATA%` for the monitored user and discover the tenant folder at runtime.
3. Distinguish **absent** from **unreadable** (elevation) for install-tree files (8-V10).
4. Report mtime/size deltas as first-class signals, since no log format is verified.
5. Treat log **content** as unparsed until §16's format question is closed; do not ship regex assertions against an unread format.
6. Never emit `tbl_exception_log2` row contents.
7. **Copy log content into run evidence at read time**, and treat a vanished log as `INCONCLUSIVE` (§6.5, 8-V21). Never hold a path for deferred reading — the directory may not exist by then.

## 16. Open Questions / TODO

**Answered by the 2026-07-30 pass** (see §6):

- ~~Where does the agent write its logs, and how many log files/streams exist?~~ → **Four locations, three media** (§3): per-user `%APPDATA%\screen\empm\logs\<date>.txt`; service-side files in `<install root>\service\`; feature logs in `%APPDATA%\screen\empm\`; and `tbl_exception_log2` in SQLite. **Verified** as to location and existence.
- ~~Does the agent rotate or purge old logs?~~ → **It purges — Verified.** The agent was observed **emptying `%APPDATA%\screen\empm\logs\` itself, mid-session** (8-V19, 8-V20), which makes log-derived evidence non-durable (8-V21). Date-based filenames still imply daily rotation (8-V3) and retention depth remains unknown (8-V4); no purge behaviour is established for the service-side files (8-V23).

**Newly open, and now the most operationally urgent question here:**

- **What triggers the log purge** (8-V22) — age, size, sign-out, restart, or an explicit cleanup routine? Knowing the trigger is the difference between scheduling collection around it and being unable to.
- **Does the purge extend to the service-side files, the feature logs, or `tbl_exception_log2`** (8-V23)? If the database table survives, it is the only durable agent-side error record.

**Still open — and note that all of it is now cheap to answer, since the files are located:**

- **What format are the logs in?** (8-V5.) Highest-value open question in this document; nothing can be asserted about log content until it is answered.
- What log levels does the agent use, and how do they map to severity?
- What events are logged — startup, capture, upload, error, watchdog activity? Do logs record enough to corroborate Layer 2/3 findings at all?
- **What is in `CurrentStatus.txt`?** (8-V11.) Potentially a direct agent-state signal for [RE-013](RE-013_Agent_State_Machine.md).
- What is in `UpdateProgress.txt`, and does `UpdateMgr_Emp.exe` write it (8-V9)?
- What distinguishes `EMP_SERVICE.log` from `EMP_SERVICE2.txt` — rotation, severity split, or two components (8-V7)?
- Are the `.jsonl` files genuinely append-only structured event streams (8-V13)? If so they are the most automation-friendly surface available.
- How many days of per-user logs are retained (8-V4)?
- **Which process writes which artifact** (8-V18)? Only co-location is known.
- Is log verbosity configurable — specifically, is there a logging key in the unenumerated ~4.7 KB tenant `empm.ini` (§7)?
- Do `config_debug.js` / `config_release.js` change logging behaviour?
- What does `tbl_exception_log2` contain, and does it duplicate or complement file-based errors (8-V15)?
- Do agent logs correlate with SQLite row changes or upload activity? This is the correlation that would make EV-004 useful for Layer 3 corroboration.
- Are logs written into Program Files at runtime, and how are the necessary rights obtained (8-V10)?

## 17. Future Expansion

The location pass is done; the content pass has not started, and that is the whole of the near-term work:

- **Read the per-user `<date>.txt` and `EMP_SERVICE.log`** and record format, encoding, timestamp convention and level vocabulary. This single step closes 8-V5 and unblocks every content assertion in the framework.
- Read `CurrentStatus.txt` (8-V11) — small, likely structured, and potentially the cheapest agent-state signal available.
- Inspect a `.jsonl` file's shape to confirm append-only structured logging (8-V13).
- Observe across a day boundary to confirm daily rotation and measure retention (8-V3, 8-V4).
- Correlate an induced event (agent restart, one capture, an offline period) with log entries in each location — this both establishes what is logged and identifies which component writes where (8-V18).
- Read `PRAGMA table_info` for `tbl_exception_log2` — column names, not values — to establish what it records.
- Once format is verified, document changes to log structure across EmpMonitor releases and demote broken claims to **Deprecated** with pointers.

## 18. Version Notes

| Version observed | Date | Notes |
|---|---|---|
| `gui` components **3.7.4**, `service` component **3.7.3** | 2026-07-30 | First version ever verified against for this subject. Host: Windows 10 Pro build 10.0.19045 x64, single user profile. Established four log locations across three media. **Log formats and contents remain unobserved at this version** — this document's §6 is a location inventory, not a logging-behaviour record, with one behavioural exception below. |
| `gui` components **3.7.4**, `service` component **3.7.3** | 2026-07-30 (same session) | **The agent was observed emptying its own log directory** (§6.5, 8-V19/8-V20). This is the first *behavioural* log finding on record and it makes log-derived evidence non-durable at this version. The purge trigger is unknown (8-V22), so it cannot be assumed to be version-specific — re-check on any version change, and do not assume a future version keeps logs longer. |

All §6 claims are scoped to the row above. Statements outside §6 remain unversioned. Per [README §7](README.md) step 6, log paths and (once known) formats must be re-checked on version change; log formats are among the least stable product facts and any future parser should be treated as version-pinned.

## 19. Cross References

- [Knowledge Base Index](README.md)
- [HB-001 — Product Overview](../docs/handbook/HB-001_Product_Overview.md)
- [HB-002 — Product Architecture](../docs/handbook/HB-002_Product_Architecture.md)
- [Validation Standard](../docs/ADS/validation_standard.md)
- [RE-005 — Configuration Loading](RE-005_Configuration_Loading.md)
- [RE-007 — SQLite Database](RE-007_SQLite_Database.md)
- [RE-009 — Runtime Components](RE-009_Runtime_Components.md)
- [RE-010 — Folder Structure](RE-010_Folder_Structure.md)
- [RE-011 — Recovery Behaviour](RE-011_Recovery_Behaviour.md)
- [RE-013 — Agent State Machine](RE-013_Agent_State_Machine.md) — `CurrentStatus.txt` as a candidate state signal
- [Synchronization Architecture Report](../docs/Synchronisation_Architecture_Report.md) — §3 adopts log-derived observation as the primary Layer 3 strategy; §6.5 here records the durability risk that choice carries
- [HB-006 — Feature Specifications](../docs/handbook/HB-006_Feature_Specifications.md) — the features whose expectations rest on log patterns
- [Evidence Catalog](../docs/Evidence_Catalog.md) — EV-003, EV-004, EV-007, EV-010
- [HB-005 — Component Inventory](../docs/handbook/HB-005_Component_Inventory.md) — log file inventory rows promoted from these findings

---
**Document Status:** Active — log **locations** first verified 2026-07-30 (gui 3.7.4 / service 3.7.3): four locations across three media, including service-side files inside Program Files and a database-resident `tbl_exception_log2`. **No log content, format, or level was read** — logging *behaviour* remains Hypothesis with one **Verified** exception: **the agent empties its own log directory mid-session (§6.5), so log-derived evidence is not durable.** The framework degraded to `INCONCLUSIVE` and invented no failure, but the fragility is inherent. Reviewer sign-off outstanding.
**Owner:** TODO
**Last Updated:** 2026-07-30
