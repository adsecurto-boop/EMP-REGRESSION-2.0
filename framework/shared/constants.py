"""Framework-wide constant values.

Only values that are genuinely invariant across every environment and run
belong here. Anything that varies by environment, endpoint, or run is
configuration, not a constant -- see ``docs/ADS/configuration_standard.md``.

This module deliberately contains **no EmpMonitor product paths, process
names, endpoints, or schema details**. Those are product facts: they live in
the reverse-engineering knowledge base as documentation and reach the code
through configuration, never as hardcoded constants.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "FRAMEWORK_NAME",
    "FRAMEWORK_VERSION",
    "VALIDATION_STANDARD_VERSION",
    "EVIDENCE_ID_PATTERN",
    "PLUGIN_ID_PATTERN",
    "DEFAULT_ENVIRONMENT",
    "ENV_VAR_PREFIX",
    "ENV_VAR_ENVIRONMENT",
    "ENV_VAR_CONFIG_DIR",
    "CONFIG_DIR_NAME",
    "REPORTS_DIR_NAME",
    "BASELINES_DIR_NAME",
    "LOG_DIR_NAME",
    "MIN_CORROBORATING_LAYERS",
    "CORRELATION_ID_LENGTH",
]

FRAMEWORK_NAME: Final[str] = "EmpMonitor Automation Framework"
"""Human-readable framework name, used in report metadata and log banners."""

FRAMEWORK_VERSION: Final[str] = "0.1.0"
"""Framework version. Phase 1 (Framework Foundation) baseline."""

VALIDATION_STANDARD_VERSION: Final[str] = "1.0"
"""Version of the ratified Validation Standard this code implements.

Recorded in reports so a report can be interpreted against the exact contract
in force when it was produced (``docs/ADS/validation_standard.md`` §13).
"""

EVIDENCE_ID_PATTERN: Final[str] = r"^EV-\d{3}$"
"""Regex for Evidence Catalog identifiers, e.g. ``EV-007``.

Format only. The authoritative list of *which* IDs exist is
``docs/Evidence_Catalog.md``, mirrored into configuration -- the framework
validates shape here and membership from configuration, so adding a catalog
entry never requires a code change (``docs/Evidence_Catalog.md`` §6).
"""

PLUGIN_ID_PATTERN: Final[str] = r"^EM\d{3}_[A-Za-z0-9]+$"
"""Regex for plugin identifiers, e.g. ``EM001_Login``.

See ``docs/ADS/naming_convention.md`` §2.
"""

DEFAULT_ENVIRONMENT: Final[str] = "local"
"""Environment assumed when none is specified."""

ENV_VAR_PREFIX: Final[str] = "EMPAF_"
"""Prefix for environment variables that override configuration values."""

ENV_VAR_ENVIRONMENT: Final[str] = f"{ENV_VAR_PREFIX}ENVIRONMENT"
"""Environment variable selecting the active environment."""

ENV_VAR_CONFIG_DIR: Final[str] = f"{ENV_VAR_PREFIX}CONFIG_DIR"
"""Environment variable overriding the configuration directory location."""

CONFIG_DIR_NAME: Final[str] = "config"
"""Repository-relative configuration directory name."""

REPORTS_DIR_NAME: Final[str] = "reports"
"""Repository-relative directory for generated run output."""

BASELINES_DIR_NAME: Final[str] = "baselines"
"""Repository-relative directory for canonical reference evidence.

Distinct from :data:`REPORTS_DIR_NAME` by design: baselines define what
"correct" looks like, reports record what happened
(``docs/FRAMEWORK_MANIFEST.md`` §9).
"""

LOG_DIR_NAME: Final[str] = "logs"
"""Log subdirectory name, resolved beneath the configured output root."""

MIN_CORROBORATING_LAYERS: Final[int] = 2
"""Absolute floor for corroboration.

``docs/ADS/validation_standard.md`` §5.1 makes the minimum configurable but
states it may **never** be below two. Configured values are clamped to this
floor rather than silently accepted.
"""

CORRELATION_ID_LENGTH: Final[int] = 12
"""Character length of generated short correlation identifiers."""
