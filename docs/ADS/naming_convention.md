# Naming Convention

## 1. Purpose

This document defines naming rules across the repository so that files, directories, plugins, and identifiers are predictable and self-describing.

## 2. Plugin Naming

Plugins under `plugins/` follow: `EM<3-digit-number>_<PascalCaseCapabilityName>`

Examples observed in the current catalog:
- `EM000_EnvironmentValidator` — `EM000` is reserved for the environment pre-check that must run before every other plugin; the zero denotes "runs first, depends on nothing"
- `EM001_Login`
- `EM002_UserManagement`
- `EM003_Attendance`
- `EM004_LiveMonitoring`
- `EM005_Screenshots`
- `EM006_ScreenRecording`

Rules:
- The numeric prefix is zero-padded to 3 digits and assigned sequentially — it is never reused, even if a plugin is retired.
- The capability name is PascalCase, no spaces or underscores within the name itself.
- The capability name should name the *feature area*, not the test type or technique.

> **TODO:** Confirm the numbering authority (who assigns the next `EM0XX` number) and whether retired plugin numbers are documented anywhere.

## 3. Handbook Document Naming

Documents under `docs/handbook/` follow: `HB-<3-digit-number>_<Title_In_Underscored_Case>.md`, e.g. `HB-001_Product_Overview.md`.

## 4. Reverse Engineering Document Naming

Documents under `knowledge_base/` follow: `RE-<3-digit-number>_<Title_In_Underscored_Case>.md`, e.g. `RE-001_Agent_Startup.md`. The numeric prefix is assigned sequentially and never reused. See [knowledge_base/README.md](../../knowledge_base/README.md) for the full index and document template.

## 5. Framework Module Naming

Modules under `framework/` use lowercase `snake_case.py` filenames that name the responsibility, not the implementation detail (e.g., `folder_monitor.py`, not `watch_dir_impl.py`).

## 6. Configuration File and Key Naming

See the [Configuration Standard](configuration_standard.md) for configuration-specific naming rules.

> **TODO:** Define the naming convention for configuration files under `config/` (e.g., per-environment file naming) and for configuration keys (casing, nesting convention).

## 7. Report and Evidence Naming

> **TODO:** Define the naming convention for generated artifacts under `reports/` (e.g., inclusion of timestamp, plugin ID, run ID) so that outputs sort and correlate predictably. Coordinate with the [Reporting Standard](reporting.md).

## 8. Branch and Commit Naming

See the [Contribution Guide](../../CONTRIBUTING.md).

## 9. Evidence Source Naming

Evidence sources in the [Evidence Catalog](../Evidence_Catalog.md) follow: `EV-<3-digit-number>` (e.g., `EV-007`). The numeric prefix is assigned sequentially and never reused, even if a source is retired. The Evidence Catalog is the sole registry; an `EV` ID not present there is invalid.

## 10. Design Document Naming

Framework component design documents live under `docs/design/` and are named `<Component_Name_In_Underscored_Case>.md` (e.g., `Synchronization_Monitor.md`). A design document describes a framework component before/independent of implementation; it is neither a standard (ADS) nor product documentation (handbook/knowledge base).

## 11. Architecture Decision / Reference Naming

> **TODO:** Define naming for any future decision records or reference documents, if the project adopts them (e.g., an ADR-style series).

## 12. General Rules

- Prefer full words over abbreviations unless the abbreviation is already an accepted term in this document set (e.g., `ADS`, `HB`).
- Directory names are lowercase; file names within `framework/` and `plugins/` follow the case convention of their category as defined above.
- Names must not encode a date, author, or version — use version control and document control footers for that instead.

---
**Document Status:** Draft — structure established, implementation details pending
**Owner:** TODO
**Last Updated:** 2026-07-30
