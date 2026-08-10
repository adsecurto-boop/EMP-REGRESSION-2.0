# Logging Standard

## 1. Purpose

This standard defines how the framework and its plugins produce log output, so that runs are observable and diagnosable consistently across every component.

## 2. Logging Ownership

All logging must go through `framework/shared/logger.py`. No module should configure or instantiate its own independent logging mechanism — this keeps format, destination, and levels consistent across the entire framework.

## 3. Log Levels

> **TODO:** Define the level scheme and when each is used. Suggested baseline pending confirmation:

| Level | Intended Use |
|---|---|
| DEBUG | Fine-grained detail useful only during active troubleshooting |
| INFO | Normal lifecycle events (run start/end, plugin start/end, key decisions) |
| WARNING | Unexpected but non-fatal conditions the run recovered from |
| ERROR | A failure that affects the current unit of work (see [Error Handling Standard](error_handling_standard.md)) |
| CRITICAL | A failure that prevents the framework from continuing at all |

## 4. Log Format

> **TODO:** Define the required fields in each log line (e.g., timestamp, level, component/module, plugin ID, run/correlation ID, message) and the exact format/ordering.

## 5. Correlation Across a Run

> **TODO:** Define how a single run's log entries are correlated (e.g., a run ID generated at start via `framework/core/context.py` and threaded through every log call), so that logs from `framework/monitors/` and a plugin's own logging can be tied back to the same run.

## 6. Destinations

> **TODO:** Define where logs are written (console, file under a specific path, or both) and whether log output is also considered part of the evidence captured per the [Reporting Standard](reporting.md).

## 7. Retention and Rotation

> **TODO:** Define log retention/rotation policy, if any, and how it relates to report/evidence retention in the [Reporting Standard](reporting.md).

## 8. What Must Never Be Logged

- Secrets or credentials (see [Configuration Standard](configuration_standard.md))
- Any personally identifiable information beyond what is strictly required for diagnosing a run

## 9. Related Documents

- [Error Handling Standard](error_handling_standard.md)
- [Reporting Standard](reporting.md)
- [Framework Architecture Standard](architecture.md)

---
**Document Status:** Draft — structure established, implementation details pending
**Owner:** TODO
**Last Updated:** 2026-07-30
