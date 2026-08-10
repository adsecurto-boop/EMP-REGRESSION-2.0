# Dashboard Collector Design — the first Layer 4 collector

> Design only — no code this phase. The collector implements, without modification, the contract frozen in [`framework/validators/dashboard.py`](../../framework/validators/dashboard.py): `DashboardSnapshotCollector`, producing `DashboardObservation` and `Evidence`. Its acceptance test is the contract docstring's promise: *"Replace it with a real collector; nothing else needs to change."*

## 1. Identity

| Property | Value |
|---|---|
| Class | `PlaywrightDashboardCollector` (`framework/dashboard/`) |
| Contract | `DashboardSnapshotCollector` — unchanged |
| `name` | `dashboard.playwright` |
| `layer` | `EvidenceLayer.DASHBOARD` (inherited) |
| `evidence_ids` | `EV-006`, `EV-008` (inherited) — no new catalog rows needed |
| `pages` | The intersection of the 17-page register with pages a locator registry exists for — i.e., **only pages actually observed and refactored**; it grows page by page |
| Registration | Replaces `UnavailableDashboardCollector` when `dashboard.enabled=true`; otherwise the unavailable collector continues to serve, unchanged |

## 2. Responsibilities (and the reads behind the brief's list)

`observe(page, context)` navigates via the engine, reads via the page object, and normalises into `DashboardObservation`:

| Brief responsibility | What is actually read | Observation field |
|---|---|---|
| Read dashboard state | Page reached, readiness, empty-state vs data vs error | `reached`, `values` |
| Read timestamps | Displayed timestamps, **raw string + parse attempt** (§4) | `timestamps` |
| Read status | Per-user/per-feature status indicators as displayed | `values` |
| Read images | Screenshot-list **metadata**: count, per-item timestamp, thumbnail presence — never image content (§5) | `values` |
| Read recordings | Recording-list metadata: count, durations, timestamps — never playback (§5) | `values` |
| Read live monitoring state | Connection indicator state, stream-area presence | `values`, `visible_features` |

`collect(context)` iterates the requested page set (the plugin's profile `expected_dashboard_pages`, else `dashboard.pages` config) and wraps each observation:

- One `Evidence` per observed page: `evidence_id=EV-006`, `source=f"dashboard:{page}"`, `data=observation.to_dict()`, `collector="dashboard.playwright"`.
- `monitoring_control` (and `storage`/`localization`/`shift_management` settings reads) emit `EV-008` instead — dashboard-authored settings as L1 intent. **Per the independence rule ([Page Specifications §2.4](Dashboard_Page_Specifications.md)), one visit yields one evidence id**: a run configured to treat the settings read as L1 intent does not also count it as an L4 observation. The choice is a per-run configuration (`dashboard.settings_as`, default `EV-008`), recorded in the evidence.
- A page that could not be reached emits its `reached=False` observation as evidence — absence visible, exactly as `UnavailableDashboardCollector` established.
- Session acquisition failure ⇒ **one** evidence record for the whole cycle (`state: unavailable`, classified reason from the [Authentication design §2.2](Dashboard_Authentication.md)) — the same shape the existing `DashboardValidator` already consumes for its `INCONCLUSIVE` finding, which is why no validator change is needed.

## 3. What It Never Does

Never produces a verdict or `Finding` (Collector contract). Never navigates outside the engine, never holds locator strings, never enters credentials, never performs a write, never reads row-level personal content, never retries an honest absence into a presence, never raises for an unreachable page — `EvidenceError` is reserved for "the browser itself could not run" ([Architecture §5](Playwright_Architecture.md)).

## 4. Timestamp Normalisation — the honest version

Every displayed timestamp is captured as **raw displayed string** plus a parsed value flagged with the parse assumption (`assumed_tz`, `assumed_format`). Until the three questions of [Navigation §6](Dashboard_Navigation.md) (timezone, rounding, propagation delay) are answered by observation, downstream comparison via `TimestampValidator` must treat parsed values as `INCONCLUSIVE`-grade inputs. The collector records; it does not resolve the semantics question silently. Relative displays ("3 minutes ago") are captured raw with `observed_at` alongside — the pair is the datum.

## 5. Sensitivity at Collection Time

- Image/recording **content** is never downloaded, hashed, or embedded. Metadata only ([Standard §4](../ADS/dashboard_automation_standard.md)).
- `values` carries no free-text personal payloads (no email subjects, no window titles); where a page displays them, the collector records presence/count only — the L4 analogue of "EV-003 is count-only".
- Optional page screenshots (debug config) go through `ArtifactManager` into the run's `reports/` folder as sensitive artifacts referenced from evidence metadata — never inlined into `Evidence.data`.

## 6. Lifecycle in a Run

```
setup():    PlaywrightManager.setup() → SessionManager.acquire() (probe)
collect():  for page in requested: engine.open_<page>() → page object reads → observation → Evidence
teardown(): SessionManager.refresh() → PlaywrightManager.teardown()   (always, on any path)
```

Sequential, one context, per [Architecture §6](Playwright_Architecture.md). Existing pipeline stages (normalizers, correlation, validators, reporting) consume the output with **zero changes** — that is the measure that the dashboard layer stayed a collector.

## 7. Build Order

First implementation targets the four chain-closing pages, in the order the model already argues for ([Navigation §5](Dashboard_Navigation.md)): `monitoring_control`, `screenshots`, `timesheet`, `reports` — plus the session probe page, whichever proves cheapest. The other thirteen pages follow as observation reaches them; `pages` grows accordingly.

## 8. Cross References

- [`framework/validators/dashboard.py`](../../framework/validators/dashboard.py) — frozen contract this implements
- [Playwright Architecture](Playwright_Architecture.md) · [Navigation Engine](Dashboard_Navigation_Engine.md) · [Authentication](Dashboard_Authentication.md)
- [Dashboard Validators design](Dashboard_Validators.md) — what concludes from this collector's evidence
- [Evidence Catalog](../Evidence_Catalog.md) — EV-006 / EV-008 rows

---
**Document Status:** Design complete — no code; consumes only frozen contracts; dashboard remains unobserved
**Owner:** TODO
**Last Updated:** 2026-07-31
