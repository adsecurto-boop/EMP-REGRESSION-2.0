# framework/dashboard -- Dashboard Automation Layer (Layer 4)

Phase 5 scaffold: **folders and contracts only -- no code, no locators, no scripts.** The dashboard has never been observed (0 of 17 pages).

Binding standard: [Dashboard Automation Standard](../../docs/ADS/dashboard_automation_standard.md). Architecture: [Playwright Architecture](../../docs/design/Playwright_Architecture.md).

**The one rule:** this package is a *collector*, not a framework. It implements the frozen contract in [`framework/validators/dashboard.py`](../validators/dashboard.py) (`DashboardSnapshotCollector` -> `DashboardObservation` -> `Evidence` EV-006/EV-008) and nothing outside `plugins/` may depend on it.

**Dependency rule** ([Architecture Standard §3](../../docs/ADS/architecture.md)): `framework/dashboard/` imports from `framework/shared/` only. `plugins/` may import it. `framework/core|monitors|validators` must never import it. `playwright` is an optional dependency imported only inside this package.

| Package | Purpose |
|---|---|
| `playwright_manager/` | Browser/context lifecycle |
| `authentication/` | Credentials, sessions, supervised login |
| `navigation/` | The only component that navigates |
| `pages/` | 17 page objects (register identifiers) |
| `components/` | Shared page fragments |
| `locators/` | Central locator registries (empty until observed) |
| `helpers/` | Shared read/parse/artifact helpers |
| `recordings/raw/` | Codegen quarantine -- never imported, never executed |

Read-only, without exception. Real people are monitored by this product.
