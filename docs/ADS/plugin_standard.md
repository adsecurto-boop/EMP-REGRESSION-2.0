# Plugin Development Guide

## 1. Purpose

This guide defines how a feature-area automation module ("plugin") must be structured, registered, and validated within the EmpMonitor Automation Framework, so that every plugin is consistent, discoverable, and maintainable regardless of who authors it.

## 2. What Is a Plugin

A plugin is a self-contained module under `plugins/` that automates coverage for one EmpMonitor capability. Plugins depend on the framework core (`framework/core/`, `framework/shared/`, `framework/monitors/`, `framework/validators/`) but the core must never depend on a plugin (see [Framework Architecture Standard](architecture.md)).

## 3. Current Plugin Catalog

| Plugin | Capability Area |
|---|---|
| `EM000_EnvironmentValidator` | **Environment & agent pre-check.** Implemented. Runs before every regression run; every other plugin declares it as a required dependency, and the gate in `plugins/EM000_EnvironmentValidator/gate.py` skips downstream plugins when it reports `FAILED` or `BLOCKED`. |
| `EM001_Login` | Login |
| `EM002_UserManagement` | User Management |
| `EM003_Attendance` | Attendance |
| `EM004_LiveMonitoring` | Live Monitoring |
| `EM005_Screenshots` | Screenshots |
| `EM006_ScreenRecording` | Screen Recording |

> These are the currently scaffolded plugin directories. Each is a placeholder pending implementation — this table should be kept in sync as plugins are built out or new ones are added.

## 4. Plugin Identifier Convention

Plugins are identified as `EM<3-digit-number>_<PascalCaseCapabilityName>` (e.g., `EM003_Attendance`). See the [Naming Convention](naming_convention.md) for the full rule set.

## 5. Required Structure

> **TODO:** Define the required internal structure of a plugin directory (e.g., entry file, config schema, evidence hooks, test location) once the first plugin is implemented as a reference.

## 6. Plugin Lifecycle

> **TODO:** Document how a plugin is discovered, registered with `framework/core/registry.py`, invoked by the orchestrator, and how it reports results back through `framework/core/reporting.py`.

## 7. Interface Contract

> **TODO:** Define the minimum interface every plugin must implement (e.g., setup, execution, teardown, evidence capture) so the orchestrator can treat all plugins uniformly.

## 8. Configuration

Plugin-specific configuration must live under `config/`, following the [Configuration Standard](configuration_standard.md). Plugins must not read configuration from ad hoc locations.

## 9. Logging and Error Handling

Plugins must use the shared logger (`framework/shared/logger.py`) per the [Logging Standard](logging_standard.md) and classify/handle failures per the [Error Handling Standard](error_handling_standard.md). Plugin-specific error types, if needed, should extend the shared error hierarchy rather than introduce a parallel one.

## 10. Reporting and Evidence

Every plugin run must produce results compatible with the [Reporting Standard](reporting.md), including any evidence captured via `framework/core/evidence.py`. A plugin must gather evidence across the layers defined in the [Validation Standard](validation_standard.md) §3 relevant to its feature — a plugin that only checks one layer (e.g., dashboard UI alone) does not conform to this standard.

Each plugin's feature specification — what the feature is expected to do, and which evidence layers apply to it — lives in [HB-006 — Feature Specifications](../handbook/HB-006_Feature_Specifications.md), not in this document. This document governs plugin *structure*; HB-006 governs plugin *behavioral scope*.

## 11. Adding a New Plugin — Checklist

> **TODO:** Finalize this checklist once the first reference plugin exists. Draft outline:
- [ ] Directory created under `plugins/` following the naming convention
- [ ] Plugin registered with the core registry
- [ ] Configuration keys added and documented
- [ ] Logging and error handling follow the shared standards
- [ ] Evidence/reporting hooks implemented
- [ ] Entry added to the plugin catalog table above
- [ ] Tests added
- [ ] Documentation updated

## 12. Related Documents

- [Framework Architecture Standard](architecture.md)
- [Naming Convention](naming_convention.md)
- [Reporting Standard](reporting.md)

---
**Document Status:** Draft — structure established, implementation details pending
**Owner:** TODO
**Last Updated:** 2026-07-30
