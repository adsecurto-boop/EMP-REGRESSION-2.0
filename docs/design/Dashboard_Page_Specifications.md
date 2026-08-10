# Dashboard Page Specifications

> ## ⚠ Every element on this page is unobserved
>
> **No page below has been opened.** Element names are *descriptions of what a validator would need to find*, not selectors, not confirmed labels, and not evidence that the element exists.
>
> Each page is therefore a **checklist for the engineer who first opens it**, not a specification of the product. Assertions are written as questions the page should be able to answer.
>
> Deliberately absent: selectors, XPaths, CSS, waits, and any automation code. Committing invented selectors would be worse than committing nothing — they would look authoritative, fail mysteriously, and take longer to disprove than to write.

**Status:** all pages `Hypothesis` · **0 of 17 observed** · Companion to [Dashboard Navigation](Dashboard_Navigation.md)

## 1. How to Read a Page Specification

| Section | Meaning |
|---|---|
| **Expected Elements** | What a validator must locate. Described by *role*, never by selector — the selector is discovered when the page is first observed. |
| **Expected Actions** | Read-only interactions needed to reach the data. Filtering and paging are reads; anything that changes state is forbidden. |
| **Expected Assertions** | What could be checked *once the page is observed*. Written as questions, because none can be answered yet. |
| **Expected Evidence** | Which catalog identifier the observation would be recorded under, and which layer it serves. |
| **Corroborates** | The lower-layer evidence this page would close the chain against — the reason the page is worth automating at all. |

Only `EV-006` (dashboard UI state, L4) and `EV-008` (dashboard-authored settings, treated as L1 intent) are available. A page needing a new evidence source must have it registered in the [Evidence Catalog](../Evidence_Catalog.md) *before* a collector cites it.

## 2. Priority Pages

These four close the end-to-end chain. Build them first; the rest are supporting.

### 2.1 `screenshots`

**Corroborates:** EM010 — `pending_screenshots6` draining (L3) → a screenshot visible (L4).

| Category | Detail |
|---|---|
| **Elements** | employee selector · date-range control · screenshot list or grid · per-item timestamp · per-item image thumbnail · empty-state indicator · paging control |
| **Actions** | select employee (read) · set date range (read) · page through results (read) |
| **Assertions** | Does a screenshot appear for a period when the queue was observed draining? · Is its displayed timestamp within tolerance of the locally observed capture time? · Does the displayed count agree with rows observed leaving `pending_screenshots6`? · Is the empty state shown when nothing was captured, rather than an error? |
| **Evidence** | `EV-006` (L4) |

**The distinction this page exists to make:** without it, a screenshot that was captured, persisted, and uploaded but never displayed is indistinguishable from one that was never captured. Both look like "no screenshot".

**Blocked on:** the timestamp semantics in [Navigation §6](Dashboard_Navigation.md). Until timezone, rounding, and propagation delay are known, the second assertion cannot be trusted.

### 2.2 `timesheet`

**Corroborates:** EM013, EM014 — `clock_data6` rows and `todayRemainingBreakInSeconds` (L1/L2) → displayed worked, idle, and break totals (L4).

| Category | Detail |
|---|---|
| **Elements** | employee selector · date-range control · worked-time total · idle-time total · break-time total · per-day breakdown · shift indicator |
| **Actions** | select employee (read) · set date range (read) |
| **Assertions** | Do displayed totals agree with `clock_data6` start/end pairs? · Does displayed break time agree with the locally configured remaining-break value? · Do the parts sum to the whole? · Is the date range interpreted in the organisation's timezone or the viewer's? |
| **Evidence** | `EV-006` (L4) |

**Note on the internal-consistency assertion.** "Do the parts sum to the whole" is checkable *without* knowing the timezone, so it is the one assertion here that could be verified on first observation. Worth doing first for that reason.

### 2.3 `reports`

**Corroborates:** EM017, EM018, EM019, EM023 — `usagedata6`, `usbdata6`, and the four mail tables (L2) → displayed activity (L4).

| Category | Detail |
|---|---|
| **Elements** | report-type selector · scope selector (organisation / team / employee) · date range · result table · export control · aggregate totals |
| **Actions** | select report type (read) · set scope and range (read) · read results (read). **Export must not be used** — it writes a file and may queue server-side work. |
| **Assertions** | Does application-usage data appear for rows observed in `usagedata6`? · Do USB events appear for rows in `usbdata6`? · Do email records appear for items whose upload was observed succeeding? · Does an empty report render as empty rather than as an error? |
| **Evidence** | `EV-006` (L4) |

**Email monitoring is the best first target for any dashboard assertion**, because it is the only feature whose *upload* has been directly observed succeeding, per-item, with server acknowledgement. If an observed successful upload does not appear here, that is a surfacing defect with an unusually solid evidential basis behind it.

### 2.4 `monitoring_control`

**Corroborates:** every feature — this is the likely *origin* of Layer 1 intent.

| Category | Detail |
|---|---|
| **Elements** | per-feature enable/disable state · per-feature interval or schedule · organisation-wide policy · save control |
| **Actions** | **read only.** No toggle may be operated: changing monitoring configuration would alter the product's behaviour, invalidate every other layer's evidence, and affect real monitored people. |
| **Assertions** | Does each feature's dashboard-side state match the corresponding local `from_remote\` key? · Does each interval match the locally configured interval? · Is any feature enabled here but absent from local configuration, or the reverse? |
| **Evidence** | `EV-008` (dashboard-authored settings, **treated as L1**) |

**Why this page is the most valuable of the four.** Local keys carrying a `from_remote\` prefix suggest the dashboard authors configuration and the local file caches it. If so, **divergence between dashboard intent and local configuration is a defect class the framework cannot currently see at all** — it only ever reads the cache. This page would make that class detectable.

**Independence caution.** `EV-008` is L1 and `EV-006` is L4, but a single reading of one page cannot serve as both ([Validation Standard §4.1](../ADS/validation_standard.md)). Reading `monitoring_control` yields *either* L1 intent *or* an L4 observation of the settings page — not both from one visit.

## 3. Supporting Pages

Specified more briefly: each closes a narrower gap, and none is required for an end-to-end chain.

| Page | Elements (assumed) | Actions | Key assertions (all unanswerable today) | Evidence |
|---|---|---|---|---|
| `login` | username field · password field · submit · error area | **none by the framework** — a session is supplied; credentials are never entered by automation | Is a session valid? Is an expired session distinguishable from a rejected one? | none |
| `organization` | organisation selector · name · member count | select (read) | Does the observed organisation match the locally configured tenant? | `EV-006` |
| `users` | search · user list · per-user status · paging | search, page (read) | Does the monitored user appear? Does their status match the locally observed agent state? | `EV-006` |
| `employee` | identity header · activity summary · feature tabs · last-seen timestamp | select (read) | Is last-seen within tolerance of the last observed sync cycle? Are tabs present only for enabled features? | `EV-006` |
| `live_monitoring` | live view area · connection indicator · employee selector | select, observe (read) | Does a stream establish while `esr.exe` runs? Does the indicator agree with the observed `wss` connection? | `EV-006` |
| `recordings` | recording list · duration · timestamp · playback control | select, page (read). **Playback may trigger server work — treat as a write until proven otherwise.** | Does a recording appear for an observed capture period? Does duration agree with what was captured? | `EV-006` |
| `dashboard_home` | organisation summary · active-user count · alert area | none (read) | Does the active-user count agree with observed running agents? | `EV-006` |
| `settings` | settings navigation · section list | navigate (read) | Are the sections this model assumes actually present? | `EV-006` |
| `roles` | role list · capability matrix | read | Does the observing account hold only the read capabilities it should? | `EV-006` |
| `permissions` | role selector · effective-permission list | read | Do effective permissions explain any page that could not be reached? | `EV-006` |
| `storage` | usage figures · retention policy | read | Does the dashboard retention policy agree with local retention behaviour? **See §4.** | `EV-008` |
| `localization` | locale selector · timezone · format options | read | Which timezone renders timestamps? *(Prerequisite for every timestamp assertion.)* | `EV-008` |
| `shift_management` | shift list · assignment · schedule | read | Do shift definitions explain the timesheet boundaries observed? | `EV-008` |

## 4. The `storage` Page Has a Specific Job

Phase 3 found, with two corroborating signals, that the agent's local retention sweep **never deletes anything**: it logs an unsubstituted placeholder where a retention period should be, and reports `-1` records deleted, every cycle ([Synchronization Architecture Report §7.1](../Synchronisation_Architecture_Report.md)).

The `storage` page would show what retention the organisation *believes* it has. Comparing that against the observed local behaviour would turn a `DEGRADED` local anomaly into an evidenced end-to-end contradiction: policy says data is retained for N days, and the mechanism that enforces that locally is inert.

That comparison is currently impossible. It is the single most concrete reason to build a dashboard collector.

## 5. Rules for Whoever Builds These

1. **Read-only, without exception.** Navigate, filter, page, read. Never save, toggle, export, delete, or play back until proven side-effect-free. Real people are monitored by this product; changing its configuration is not a test action.
2. **Never enter credentials.** A session is supplied.
3. **Never invent a selector in this document.** Observe first, then record — with the six verification-metadata fields.
4. **A page you cannot reach is `reached=False` with a reason**, never an empty successful observation. `DashboardObservation` is shaped for this.
5. **Do not assert a timestamp until §6 of the Navigation spec is answered.** A comparison in the wrong timezone fails plausibly, which is the worst way to fail.
6. **Promote page by page.** Fourteen pages at `Hypothesis` and three at `Verified` is a more useful document than seventeen at "probably fine".

## 6. Cross References

- [Dashboard Navigation](Dashboard_Navigation.md) — hierarchy, paths, permissions, timestamp questions
- [`framework/validators/dashboard.py`](../../framework/validators/dashboard.py) — `DashboardObservation`, collector and validator contracts
- [Feature Validation Standard](../ADS/feature_validation_standard.md) · [Evidence Catalog](../Evidence_Catalog.md)
- [Synchronization Architecture Report](../Synchronisation_Architecture_Report.md) — the L3 findings these pages would close

---
**Document Status:** Hypothesis throughout — 0 of 17 pages observed, 0 elements confirmed
**Owner:** TODO
**Last Updated:** 2026-07-30
