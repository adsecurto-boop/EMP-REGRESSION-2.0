# Automation Development Standard (ADS)

## 1. Purpose

The Automation Development Standard (ADS) is the authoritative set of engineering standards for building and maintaining the EmpMonitor Automation Framework. Where the [handbook](../handbook/) explains *what* the project is and *why* it exists, the ADS defines *how* it must be built: structure, naming, configuration, logging, error handling, plugin construction, and reporting.

Any code, configuration, or plugin contributed to this repository is expected to conform to the standards in this suite. Deviations should be raised for discussion before being merged (see the [Contribution Guide](../../CONTRIBUTING.md)).

## 2. Scope

The ADS applies to everything under `framework/`, `plugins/`, `config/`, and `scripts/`. It does not govern product/business documentation, which lives in the [handbook](../handbook/).

## 3. Standards in This Suite

| Standard | Covers |
|---|---|
| [Validation Standard](validation_standard.md) | The multi-source evidence model every validation must satisfy — read this first |
| [Framework Architecture Standard](architecture.md) | Module boundaries and responsibilities within `framework/` |
| [Coding Standards](coding_standards.md) | General code quality, structure, and review expectations |
| [Plugin Development Guide](plugin_standard.md) | How a plugin is structured, registered, and validated |
| [Naming Convention](naming_convention.md) | Naming rules for files, directories, plugins, and identifiers |
| [Configuration Standard](configuration_standard.md) | How configuration is authored, scoped, and loaded |
| [Logging Standard](logging_standard.md) | Log levels, format, and destinations |
| [Error Handling Standard](error_handling_standard.md) | Failure classification, handling, and escalation |
| [Reporting Standard](reporting.md) | Run report and evidence format and retention |

> Note: [`prompt_standard.md`](prompt_standard.md) also exists in this directory, governing prompt/instruction assets under `prompts/`. It is maintained separately and referenced here for completeness.

## 4. Precedence

Where a standard in this suite conflicts with general practice elsewhere in the codebase, the ADS takes precedence. Where two ADS documents appear to conflict, raise it for resolution rather than resolving it unilaterally — see [Contribution Guide](../../CONTRIBUTING.md).

## 5. Maintaining the ADS

> **TODO:** Define the review/approval process for changing an ADS document (e.g., who must sign off, whether a changelog is kept per document).

## 6. Change Log

| Date | Change | Author |
|---|---|---|
| 2026-07-30 | Initial ADS structure established | TODO |

---
**Document Status:** Draft — structure established, implementation details pending
**Owner:** TODO
**Last Updated:** 2026-07-30
