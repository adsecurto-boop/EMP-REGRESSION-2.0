# Repository Guide

## 1. Purpose

This guide is a map of the repository: what every top-level directory (and its notable subdirectories) is for, so anyone can navigate the codebase without guessing.

## 2. Full Layout

```text
EMP_REGRESSION/
├── run.py                     Primary entry point for the framework
├── README.md                  Project entry point and documentation index
├── CONTRIBUTING.md             Contribution process and standards pointer
│
├── framework/                  Shared core engine — see ADS/architecture.md
│   ├── core/                   Execution + validation engine and orchestration
│   │   ├── context.py            Run state and identity
│   │   ├── event_bus.py          Publish/subscribe
│   │   ├── hooks.py              Before/after extension points
│   │   ├── evidence.py           Evidence catalog and store
│   │   ├── validation.py         The verdict engine
│   │   ├── pipeline.py           Collector → verdict pipeline
│   │   ├── dependencies.py       Ordering, cycles, version compatibility
│   │   ├── graph.py              Execution DAG, propagation, resume
│   │   ├── lifecycle.py          Per-unit lifecycle stages
│   │   ├── execution.py          Sequential/parallel execution engine
│   │   ├── scheduler.py          Scheduling contract and engine
│   │   ├── metrics.py            Timing, resource, counter metrics
│   │   ├── artifacts.py          Artifact storage and metadata
│   │   ├── timeline.py           Event-sourced timeline
│   │   ├── aggregator.py         Result aggregation
│   │   ├── registry.py           Plugin registration
│   │   ├── reporting.py          Report models (no rendering)
│   │   └── orchestrator.py       Run lifecycle and bootstrap
│   ├── monitors/                Observers of system/run state
│   │   ├── folder_monitor.py
│   │   ├── log_monitor.py
│   │   ├── runtime_monitor.py
│   │   ├── scheduler_monitor.py
│   │   └── sqlite_monitor.py
│   ├── validators/               State/output validators
│   │   ├── configuration.py
│   │   ├── dashboard.py
│   │   ├── environment.py
│   │   ├── evidence.py
│   │   └── runtime.py
│   └── shared/                   Contracts + cross-cutting utilities (bottom of the dependency graph)
│       ├── constants.py           Invariant values
│       ├── exceptions.py          Exception hierarchy
│       ├── models.py              Ratified contracts as data models
│       ├── interfaces.py          ABCs for all extension points
│       ├── config.py              Configuration loading
│       ├── logger.py              Logging setup
│       └── utils/                 Generic helpers (filesystem, datetime, version,
│                                  hashing, retry, json, ini, sqlite, http)
│
├── plugins/                     Feature-area automation modules
│   ├── EM001_Login/
│   ├── EM002_UserManagement/
│   ├── EM003_Attendance/
│   ├── EM004_LiveMonitoring/
│   ├── EM005_Screenshots/
│   └── EM006_ScreenRecording/
│
├── config/                      Run and environment configuration
│   ├── README.md                 Precedence rules and the Evidence Catalog mirror
│   ├── framework.json            Base configuration
│   └── environments/local.json   Per-environment overlay
├── knowledge_base/               Reverse-engineering knowledge base — EmpMonitor internal behavior
│   ├── README.md                 Index, provenance rules, document template
│   ├── RE-001_Agent_Startup.md
│   ├── RE-002_Watchdog_Behaviour.md
│   ├── RE-003_Scheduler.md
│   ├── RE-004_Upload_Pipeline.md
│   ├── RE-005_Configuration_Loading.md
│   ├── RE-006_API_Flow.md
│   ├── RE-007_SQLite_Database.md
│   ├── RE-008_Logging_System.md
│   ├── RE-009_Runtime_Components.md
│   ├── RE-010_Folder_Structure.md
│   ├── RE-011_Recovery_Behaviour.md
│   ├── RE-012_Offline_Synchronization.md
│   └── RE-013_Agent_State_Machine.md
├── prompts/                      Prompt/instruction assets
├── baselines/                    Reference artifacts used for comparison
├── reports/                      Generated run reports and evidence output
├── scripts/                      Supporting operational scripts
│
└── docs/                         Project documentation
    ├── FRAMEWORK_MANIFEST.md     The framework constitution — principles all decisions must comply with
    ├── Evidence_Catalog.md       Master registry of evidence sources (EV-NNN)
    ├── ARCHITECTURE_REVIEW.md    Prioritized findings on doc/architecture gaps (+ freeze addendum)
    ├── ARCHITECTURE_FREEZE_REPORT.md  Outcome of the architecture-freeze sprint
    ├── IMPLEMENTATION_REVIEW.md  Phase 1 implementation self-review
    ├── IMPLEMENTATION_REVIEW_PHASE_1_5.md  Phase 1.5 engine self-review
    ├── design/                    Framework component design documents
    │   └── Synchronization_Monitor.md  Layer 3 collector design
    ├── handbook/                  EmpMonitor product handbook (the target system, not this framework)
    │   ├── HB-001_Product_Overview.md
    │   ├── HB-002_Product_Architecture.md
    │   ├── HB-003_Agent_Architecture.md
    │   ├── HB-004_Agent_Ecosystem.md
    │   ├── HB-005_Component_Inventory.md
    │   └── HB-006_Feature_Specifications.md
    ├── ADS/                       Automation Development Standard suite (this framework's own standards)
    │   ├── README.md
    │   ├── validation_standard.md
    │   ├── architecture.md
    │   ├── coding_standards.md
    │   ├── plugin_standard.md
    │   ├── prompt_standard.md
    │   ├── naming_convention.md
    │   ├── configuration_standard.md
    │   ├── logging_standard.md
    │   ├── error_handling_standard.md
    │   └── reporting.md
    └── roadmap/                   Planning documents
        ├── SPRINT_ROADMAP.md
        ├── milestones.md
        ├── backlog.md
        └── implementation_plan.md
```

## 3. Directory Purpose Reference

| Directory | Purpose | Standard(s) Governing It |
|---|---|---|
| `framework/core/` | Shared orchestration engine | [Framework Architecture Standard](ADS/architecture.md) |
| `framework/monitors/` | Passive observation of system/run state | [Framework Architecture Standard](ADS/architecture.md) |
| `framework/validators/` | Assertion of expected state | [Framework Architecture Standard](ADS/architecture.md) |
| `framework/shared/` | Contracts (models, interfaces, exceptions) and cross-cutting utilities | [Validation Standard](ADS/validation_standard.md), [Configuration Standard](ADS/configuration_standard.md), [Logging Standard](ADS/logging_standard.md) |
| `plugins/` | Feature-area automation modules | [Plugin Development Guide](ADS/plugin_standard.md) |
| `config/` | Run/environment configuration | [Configuration Standard](ADS/configuration_standard.md) |
| `knowledge_base/` | Reverse-engineering knowledge base — verified/known internal EmpMonitor behavior (RE-001–RE-013) | [Knowledge Base Index](../knowledge_base/README.md) |
| `docs/design/` | Framework component designs authored before implementation | [Framework Manifest](FRAMEWORK_MANIFEST.md), [Naming Convention §10](ADS/naming_convention.md) |
| `prompts/` | Prompt/instruction assets | [`ADS/prompt_standard.md`](ADS/prompt_standard.md) |
| `baselines/` | Comparison reference artifacts | [Reporting Standard](ADS/reporting.md) |
| `reports/` | Generated run output and evidence | [Reporting Standard](ADS/reporting.md) |
| `scripts/` | Supporting operational scripts | [Coding Standards](ADS/coding_standards.md) |
| `docs/handbook/` | Product-facing documentation | — |
| `docs/ADS/` | Engineering standards | [ADS Overview](ADS/README.md) |
| `docs/roadmap/` | Planning and sequencing documents | [Sprint Roadmap](roadmap/SPRINT_ROADMAP.md) |

## 4. How to Navigate This Repository

- **New to the project?** Start at the root [README.md](../README.md), then read the [ADS Overview](ADS/README.md) for how this framework is engineered, and [HB-001](handbook/HB-001_Product_Overview.md)/[HB-002](handbook/HB-002_Product_Architecture.md) for what EmpMonitor (the target product) is.
- **Building or modifying a plugin?** Read the [Validation Standard](ADS/validation_standard.md), the [Plugin Development Guide](ADS/plugin_standard.md), and the [Framework Architecture Standard](ADS/architecture.md) first.
- **Adding configuration?** Read the [Configuration Standard](ADS/configuration_standard.md).
- **Contributing a change?** Read the [Contribution Guide](../CONTRIBUTING.md).

## 5. Keeping This Guide Current

This guide must be updated whenever a top-level directory is added, removed, or repurposed. Treat a structural change without a corresponding update to this guide as an incomplete change.

---
**Document Status:** Draft — structure established, implementation details pending
**Owner:** TODO
**Last Updated:** 2026-07-30
