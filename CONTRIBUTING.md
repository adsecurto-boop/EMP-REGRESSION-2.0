# Contribution Guide

## 1. Purpose

This guide defines how to propose, review, and merge changes to the EmpMonitor Automation Framework so that contributions are consistent regardless of who makes them.

## 2. Before You Start

- Read the [Repository Guide](docs/Repository_Guide.md) to understand where your change belongs.
- Read the relevant [Automation Development Standard (ADS)](docs/ADS/README.md) document(s) for the area you're touching.
- Check the [Sprint Roadmap](docs/roadmap/SPRINT_ROADMAP.md) and backlog to confirm the work is planned/expected.

## 3. Types of Contributions

| Type | Guidance |
|---|---|
| Core framework change (`framework/`) | Must respect the dependency rules in the [Framework Architecture Standard](docs/ADS/architecture.md) |
| New or updated plugin (`plugins/`) | Must follow the [Plugin Development Guide](docs/ADS/plugin_standard.md) |
| Configuration change (`config/`) | Must follow the [Configuration Standard](docs/ADS/configuration_standard.md) |
| Documentation change (`docs/`) | Must keep cross-links and the [Repository Guide](docs/Repository_Guide.md) accurate |

## 4. Branching

> **TODO:** Define the branching model (e.g., trunk-based, feature branches, naming pattern) once the team's workflow is confirmed.

## 5. Commit Messages

> **TODO:** Define the commit message convention (e.g., required prefix/tag, reference to a tracked item) once confirmed.

## 6. Pull Request Process

> **TODO:** Define the required PR template fields, minimum number of reviewers, and required checks once confirmed. At minimum, a PR should state:
- What changed and why
- Which ADS standard(s) apply and how the change complies
- Which documentation was updated as a result

## 7. Review Checklist

A reviewer should confirm:
- [ ] Change respects the [Framework Architecture Standard](docs/ADS/architecture.md) dependency rules
- [ ] Naming follows the [Naming Convention](docs/ADS/naming_convention.md)
- [ ] Errors are handled per the [Error Handling Standard](docs/ADS/error_handling_standard.md)
- [ ] Logging follows the [Logging Standard](docs/ADS/logging_standard.md)
- [ ] New/changed configuration follows the [Configuration Standard](docs/ADS/configuration_standard.md)
- [ ] New/changed reporting output follows the [Reporting Standard](docs/ADS/reporting.md)
- [ ] If a component/process/file/API was added, changed, or verified: [HB-005 — Component Inventory](docs/handbook/HB-005_Component_Inventory.md) is updated in the same change — an out-of-date inventory is worse than no inventory
- [ ] If a plugin's expected behavior or evidence layers were confirmed: [HB-006 — Feature Specifications](docs/handbook/HB-006_Feature_Specifications.md) is updated to move the relevant claim from TODO/suggested to verified
- [ ] Relevant documentation was updated
- [ ] Relevant tests were added or updated

## 8. Definition of Done

> **TODO:** Define what "done" means for a contribution (e.g., merged, documented, covered by tests, reflected in the roadmap) once confirmed with the team.

## 9. Getting Help

> **TODO:** Add point of contact / escalation channel for contributors who are blocked.

---
**Document Status:** Draft — structure established, implementation details pending
**Owner:** TODO
**Last Updated:** 2026-07-30
