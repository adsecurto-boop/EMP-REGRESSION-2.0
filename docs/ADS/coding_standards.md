# Coding Standards

## 1. Purpose

This document defines the code quality and structure expectations for all code contributed to the EmpMonitor Automation Framework, regardless of which layer (core, monitor, validator, plugin, script) it belongs to.

## 2. General Principles

- **Single responsibility** — each module/function should do one clearly named thing.
- **No feature logic in the core** — feature-specific behavior belongs in `plugins/`, not `framework/` (see [Framework Architecture Standard](architecture.md)).
- **Fail loud, fail informative** — errors must be handled per the [Error Handling Standard](error_handling_standard.md), never silently swallowed.

The remaining expectations (configuration-driven, observable, logged, etc.) are consolidated once, below, rather than repeated here.

## 2.1 Component Quality Bar

Every component contributed to this framework — core, monitor, validator, or plugin — is expected to be:

| Quality | Meaning |
|---|---|
| Reusable | Not written for a single call site when a second is foreseeable |
| Modular | Replaceable/testable in isolation, per the boundaries in the [Framework Architecture Standard](architecture.md) |
| Configuration-driven | Behavior that varies by environment or run is externalized (see [Configuration Standard](configuration_standard.md)) |
| Observable | Emits enough log/evidence output to diagnose its own failure (see [Logging Standard](logging_standard.md), [Validation Standard](validation_standard.md)) |
| Documented | Purpose and non-obvious behavior are written down, not left to be inferred from the code |
| Strongly typed | > **TODO:** confirm typing discipline once the implementation language/toolchain is finalized |
| Well logged | Meaningful lifecycle events are logged per the [Logging Standard](logging_standard.md) |
| Production ready | No placeholder/demo-quality shortcuts left in place without a tracked TODO |

### 2.2 Anti-Patterns to Avoid

- **Magic numbers** — unexplained literals; use named, documented constants (see `framework/shared/constants.py`).
- **Hardcoded paths** — file system/network locations belong in configuration (see [Configuration Standard](configuration_standard.md)), never inline.
- **Duplicated code** — shared logic belongs in `framework/shared/` (see [Framework Architecture Standard](architecture.md)), not copy-pasted across plugins.
- **Hidden dependencies** — a module's dependencies must be explicit (constructor/parameter-level), never implicit global state or import-time side effects.

## 3. Structure and Organization

> **TODO:** Define file length/module size guidance, and rules for where shared logic should live (`framework/shared/` vs. plugin-local helpers).

## 4. Style

> **TODO:** Adopt and document a formatter/linter and style guide once the implementation language tooling is finalized. Record the chosen tool, its configuration file location, and how it is enforced (e.g., pre-commit, CI).

## 5. Naming

See the dedicated [Naming Convention](naming_convention.md) for file, module, and identifier naming rules.

## 6. Testing Expectations

> **TODO:** Define minimum test coverage expectations for core modules vs. plugins, and where tests are expected to live relative to the code they cover.

## 7. Documentation Expectations

- Every new plugin must be accompanied by an entry per the [Plugin Development Guide](plugin_standard.md).
- Every new configuration key must be documented per the [Configuration Standard](configuration_standard.md).
- Public modules/functions should carry a short docstring-equivalent explaining *why*, not *what*, when the behavior is non-obvious.

## 8. Code Review Expectations

See the [Contribution Guide](../../CONTRIBUTING.md) for the review and merge process. At minimum, a reviewer should confirm:
- The change respects the dependency rules in the [Framework Architecture Standard](architecture.md).
- Naming follows the [Naming Convention](naming_convention.md).
- Errors are handled per the [Error Handling Standard](error_handling_standard.md).
- Relevant documentation is updated alongside the code.

## 9. TODO — Language-Specific Rules

> **TODO:** Once the implementation language and toolchain are finalized, add language-specific rules (type usage, dependency management, packaging) to this document.

---
**Document Status:** Draft — structure established, implementation details pending
**Owner:** TODO
**Last Updated:** 2026-07-30
