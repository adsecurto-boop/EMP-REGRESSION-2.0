# Reporting Standard

## 1. Purpose

This standard defines how the framework reports the outcome of a run, and how supporting evidence is captured, formatted, and retained. Consistent reporting is what makes automation runs trustworthy and auditable.

## 2. Reporting Components

| Component | Responsibility |
|---|---|
| `framework/core/evidence.py` | Captures evidence artifacts produced during execution |
| `framework/core/reporting.py` | Aggregates results and evidence into a run report |
| `framework/validators/evidence.py` | Validates that captured evidence meets requirements |
| `reports/` | Destination for generated reports and evidence output |

## 3. Report Contents

A run report must never reduce a validation to a bare PASS/FAIL. Per the [Validation Standard](validation_standard.md) §7, every reported finding must carry `what` / `where` / `why` / `evidence[]` / `verdict` / `corroboration`.

> **TODO:** Define the remaining required contents of a run report (run metadata, timestamps, environment/config summary) and the concrete serialization of the finding structure above.

## 4. Evidence Requirements

Evidence must be classifiable by the four layers defined in the [Validation Standard](validation_standard.md) §3, and a conclusion must be corroborated per §5 of that standard before it can be reported as `HEALTHY` or `FAILED`.

> **TODO:** Define what counts as valid evidence per plugin/capability (e.g., screenshots, logs, recordings — noting `EM005_Screenshots` and `EM006_ScreenRecording` are dedicated capability areas), and the minimum evidence required for a run to be considered verifiable.

## 5. Report Format

> **TODO:** Decide and document the output format(s) for reports (e.g., structured data file, human-readable summary, or both) and where the schema is defined.

## 6. Storage and Retention

- All generated reports are written under `reports/`.
- Baseline artifacts used for comparison live separately under `baselines/` and are not overwritten by run output.

> **TODO:** Define retention policy (how long reports/evidence are kept), naming convention for report files/folders (see [Naming Convention](naming_convention.md)), and whether reports are archived or shipped elsewhere.

## 7. Failure Reporting

Failures must be reported with enough detail to diagnose without re-running, per the [Error Handling Standard](error_handling_standard.md). A failed run must still produce a report — reporting must not depend on a successful run.

## 8. Related Documents

- [Plugin Development Guide](plugin_standard.md)
- [Error Handling Standard](error_handling_standard.md)
- [Framework Architecture Standard](architecture.md)

---
**Document Status:** Draft — structure established, implementation details pending
**Owner:** TODO
**Last Updated:** 2026-07-30
