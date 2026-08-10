# framework/dashboard/navigation

Folder scaffold only (Phase 5).

The navigation engine -- the ONLY component that navigates. One open_<identifier>() per page-register identifier; returns a page object or a classified NavigationFailure, never raises for an unreachable page. Design: [Dashboard Navigation Engine](../../../docs/design/Dashboard_Navigation_Engine.md).
