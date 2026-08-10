# Dashboard Authentication Design

> Design only — no code this phase. Binding parent: [Dashboard Automation Standard](../ADS/dashboard_automation_standard.md).

## 1. The Constraint This Design Must Not Break

Two ratified rules predate this phase ([Dashboard Navigation §2](Dashboard_Navigation.md), [`framework/validators/dashboard.py`](../../framework/validators/dashboard.py) docstring):

> The collector must never enter credentials. A session must be supplied to it.

The sprint brief asks for `login()` / `logout()`. The resolution is a boundary, not an amendment: authentication lives in a **separate component** (`framework/dashboard/authentication/`), the only place a login may ever be performed, and the collector receives only a ready session. The constraint holds exactly as written at the collector boundary — and unattended runs never log in at all (§3).

## 2. Components

| Component | Sole responsibility |
|---|---|
| `CredentialProvider` | Resolve the credential *references* for the active environment. Nothing else in the framework reads secrets |
| `SessionManager` | Persist/load storage state, probe session validity, classify failures, decide reuse |
| `AuthenticationManager` | `login()` / `logout()` — supervised mode only |

### 2.1 CredentialProvider

- Reads from the existing configuration system (`framework/shared/config.py`): environment overlay names the *variable references*, values come from `EMPAF_`-prefixed process environment variables via the existing `${VAR}` substitution. Example shape (no values, ever):

  ```
  dashboard.credentials:
    username: "${EMPMON_DASH_USER}"
    password: "${EMPMON_DASH_PASSWORD}"   # resolved at use, never logged, never in Evidence
  ```

- A missing credential is a `ConfigurationError` naming the *variable name*, never echoing any resolved value.
- Provider is swappable (interface + env-var implementation) so a secret store can be added later without touching consumers — but no second implementation is built until needed.
- Repo-committed files (`config/framework.json`, `config/environments/*.json`) may contain **references only**. `empm.ini [auth]` handling already sets the precedent: assert on structure, never emit values ([RE-005 §6.0](../../knowledge_base/RE-005_Configuration_Loading.md)).

### 2.2 SessionManager

- **Storage state is the unit of session.** Path per environment from `dashboard.storage_state_path`; the file is secret-equivalent (outside the repo, never committed, never logged, not readable into any Evidence).
- `acquire()` → loads storage state → creates the context → **probes validity** before any observation: open the cheapest authenticated page and verify the session survives (not redirected to `login`). The probe result is itself evidence-relevant: it answers the `login` page-spec question *"Is an expired session distinguishable from a rejected one?"*
- Failure classification (recorded in the observation's reason, feeding `reached=False`):
  - `NO_STATE` — storage state file absent → bootstrap needed (§3)
  - `EXPIRED` — state present, probe redirected/challenged
  - `REJECTED` — probe actively refused (locked account, revoked user)
  - `UNREACHABLE` — dashboard host not reachable at all (corroborable against EV-014 network-reachability evidence)
- `refresh()` — after a successful run, re-save storage state so rolling cookies extend session life.
- Never chains into `login()` automatically. An invalid session **ends Layer 4 collection for the run**; it does not trigger an unattended login.

### 2.3 AuthenticationManager

- `login()` — permitted **only** in supervised mode: headed browser, human present, explicitly invoked (a bootstrap entry point, not part of any plugin run). Fills credentials from `CredentialProvider`, submits, verifies landing, saves storage state via `SessionManager`. Never screenshots, traces, or records while credentials are on screen — tracing is force-disabled during login regardless of `dashboard.tracing`.
- `logout()` — exists for one purpose: deliberately invalidating a session (e.g., before rotating accounts). Never called during collection: logging out would destroy the reusable session and double login-event noise in the tenant's audit trail. Default: unused.
- MFA/SSO: unknown until observed. If present, supervised bootstrap absorbs it (human completes the challenge; storage state captures the result). No automation of MFA challenges, ever.

## 3. Session Lifecycle (the storage-state-first flow)

```
[once per environment / on expiry]                      [every collection run]
Supervised bootstrap:                                   SessionManager.acquire()
  headed login() by human ──▶ storage_state.json ──▶      probe ──ok──▶ collector observes
                                                          probe ──fail──▶ L4 reported
                                                             unavailable (classified reason);
                                                             run continues, findings INCONCLUSIVE
```

Login events are visible to the monitored organisation's audit surface; a login per run would also make the framework itself the noisiest account in the tenant. Reuse-first keeps the observation footprint minimal — the same principle as read-only.

## 4. Environment Switching

Uses the existing configuration precedence (base → `config/environments/<env>.json` → `EMPAF_*` env vars) selected by the existing `EMPAF_ENVIRONMENT` mechanism — no new switching machinery.

| Environment | Overlay | Dashboard policy |
|---|---|---|
| `local` | exists today | `dashboard.enabled=false` (no dashboard on the endpoint host) |
| `dev` / `qa` | to be added when implementation lands | Collection permitted; recording sessions happen here (see [Recording Plan](Playwright_Recording_Plan.md)) |
| `production` | to be added when needed | `dashboard.enabled=false` by default; enabling requires explicit stakeholder sign-off recorded in the run config — production is a live tenant monitoring real people |

Each environment carries its own `base_url` reference, credential variable names, and storage-state path — switching environments can never cross-contaminate sessions.

**Open fact (TODO):** whether separate dev/QA EmpMonitor tenants *exist* for this engagement is unknown. If only the production tenant exists, `qa` collapses into a carefully-scoped production profile and the sign-off rule above applies to all collection. This must be resolved before the first recording session.

## 5. Rules Summary (binding)

1. Collector never sees credentials; it receives a context/session.
2. Unattended runs never log in; they reuse or report.
3. Credentials exist only as env-var references in committed files.
4. Storage state is a secret: per-environment, outside repo, never logged.
5. No tracing/video/screenshot during any supervised login.
6. `logout()` is never part of collection.
7. Failed auth is classified evidence (`NO_STATE`/`EXPIRED`/`REJECTED`/`UNREACHABLE`), not an exception that kills the run.

## 6. Cross References

- [Dashboard Automation Standard](../ADS/dashboard_automation_standard.md) §4–§6 · [Playwright Architecture](Playwright_Architecture.md) §2.3
- [Configuration Standard](../ADS/configuration_standard.md) — precedence and substitution this design reuses
- [RE-005 §6.0](../../knowledge_base/RE-005_Configuration_Loading.md) — secrets-handling precedent
- [Dashboard Page Specifications §3 `login` row](Dashboard_Page_Specifications.md) — the session questions the probe answers

---
**Document Status:** Design complete — no code; tenant/MFA/SSO facts unknown until first supervised session
**Owner:** TODO
**Last Updated:** 2026-07-31
