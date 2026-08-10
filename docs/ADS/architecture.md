# Framework Architecture Standard

## 1. Purpose

This standard defines the technical architecture of `framework/`: the responsibility of each module, the dependency rules between them, and the extension points plugins are allowed to use.

> **Scope note:** This document is about the *automation framework's own* architecture (this codebase). It does not describe EmpMonitor's architecture as a product — that is [HB-002 — EmpMonitor Product Architecture](../handbook/HB-002_Product_Architecture.md). Do not duplicate content between the two; cross-reference instead.

## 2. Module Responsibilities

### 2.1 `framework/core/`

Since Phase 1.5 this package contains the execution and validation engine as well as the original orchestration primitives. Its 18 modules are internally tiered to keep the package acyclic — a module imports only from tiers above it. The authoritative tier list is in the `framework/core/__init__.py` docstring.

| Module | Responsibility |
|---|---|
| `context.py` | Holds shared run context/state passed through a run |
| `event_bus.py` | Publish/subscribe mechanism for decoupled communication between components |
| `hooks.py` | Before/after extension points around every stage; isolated by default |
| `evidence.py` | Captures evidence artifacts produced during a run |
| `validation.py` | The verdict engine: layer evaluation, correlation, conflict resolution, confidence, aggregation. Contains no product rules |
| `pipeline.py` | Collector → Normalizer → Validator → Correlator → Verdict |
| `dependencies.py` | Sole implementation of ordering, cycle detection, optional/required deps, version compatibility |
| `graph.py` | Execution DAG: failure propagation, partial execution, resume, visualization |
| `lifecycle.py` | Per-unit lifecycle stages, each emitting framework events |
| `execution.py` | Sequential/parallel execution, cancellation, timeout, retry, graceful shutdown |
| `metrics.py` | Timing, CPU, memory, and execution counters |
| `artifacts.py` | Artifact storage with execution id, timestamp, module, source, checksum |
| `timeline.py` | Event-sourced execution timeline |
| `aggregator.py` | Aggregates evidence, findings, warnings, errors, performance, statistics, verdict |
| `orchestrator.py` | Coordinates the overall run lifecycle and dispatches work to plugins |
| `registry.py` | Registers and resolves available plugins/monitors/validators |
| `reporting.py` | Produces run reports from collected results and evidence |
| `scheduler.py` | Sequences/schedules units of work within a run |

> **TODO:** Confirm each module's exact responsibility and public interface once implemented; update this table to match.

### 2.2 `framework/monitors/`
Monitors observe system or application state during a run without altering it.

| Module | Responsibility |
|---|---|
| `folder_monitor.py` | Observes filesystem/folder state |
| `log_monitor.py` | Observes log output |
| `runtime_monitor.py` | Observes runtime/process state |
| `scheduler_monitor.py` | Observes scheduled-task state |
| `sqlite_monitor.py` | Observes SQLite-backed state |

### 2.3 `framework/validators/`
Validators assert expected conditions and report pass/fail outcomes.

| Module | Responsibility |
|---|---|
| `configuration.py` | Validates configuration correctness |
| `dashboard.py` | Validates dashboard-related state |
| `environment.py` | Validates environment prerequisites |
| `evidence.py` | Validates captured evidence meets requirements |
| `runtime.py` | Validates runtime behavior/state |

### 2.4 `framework/shared/`
| Module | Responsibility |
|---|---|
| `constants.py` | Invariant values. No product paths, names, or endpoints — those are configuration |
| `exceptions.py` | Framework exception hierarchy, per [Error Handling Standard](error_handling_standard.md) |
| `models.py` | The ratified contracts as data models, per [Validation Standard](validation_standard.md) |
| `interfaces.py` | Abstract base classes for every extension point (Collector, Normalizer, Validator, Correlator, Monitor, Plugin, Reporter, Scheduler) |
| `config.py` | Configuration loading, per [Configuration Standard](configuration_standard.md) |
| `logger.py` | Logging setup, per [Logging Standard](logging_standard.md) |
| `utils/` | Generic helper package: filesystem, datetime, version, hashing, retry, json, ini, sqlite, http |

**Why the contracts live in `shared/` and not `core/`.** The dependency rules in §3 permit `monitors/` and `validators/` to depend on `shared/` but not on `core/`. Since those tiers must implement the interfaces and produce the models, the contracts have to sit below them in the graph — placing them in `core/` would invert the rule. This was settled during Phase 1 implementation and is recorded in the [Implementation Review](../IMPLEMENTATION_REVIEW.md).

### 2.5 `framework/dashboard/` (added Phase 5 — scaffold only)

The Dashboard Automation Layer: Playwright-based Layer 4 evidence collection, implementing the collector contract in `framework/validators/dashboard.py`. Governed by the [Dashboard Automation Standard](dashboard_automation_standard.md); package map in [`framework/dashboard/README.md`](../../framework/dashboard/README.md). It is a collector, not a framework tier: nothing outside `plugins/` may depend on it, and `playwright` is an optional dependency imported only inside it.

## 3. Dependency Rules

- `plugins/` may depend on `framework/core/`, `framework/shared/`, `framework/monitors/`, `framework/validators/`, and `framework/dashboard/`.
- `framework/core/` may depend on `framework/shared/`.
- `framework/monitors/` and `framework/validators/` may depend on `framework/shared/` but must not depend on `plugins/`.
- `framework/dashboard/` may depend on `framework/shared/` **only**; no module under `framework/core/`, `framework/monitors/`, or `framework/validators/` may import from `framework/dashboard/`.
- No module under `framework/` may import from `plugins/`.

> **TODO:** Confirm these rules against actual implementation and add enforcement notes (e.g., lint rule, import-boundary check) once tooling is decided.

## 4. Extension Points

- New plugins register through `framework/core/registry.py` — see the [Plugin Development Guide](plugin_standard.md).
- New monitors/validators are added as new modules under their respective directories and registered with the core; they must not require changes to `orchestrator.py`'s control flow.

> **TODO:** Document the exact registration mechanism once implemented.

## 5. Related Documents

- [Architecture Overview](../handbook/HB-002_Product_Architecture.md)
- [Plugin Development Guide](plugin_standard.md)
- [Coding Standards](coding_standards.md)

---
**Document Status:** Draft — structure established, implementation details pending. §2.5/§3 extended for `framework/dashboard/` (Phase 5); no existing rule changed.
**Owner:** TODO
**Last Updated:** 2026-07-31
