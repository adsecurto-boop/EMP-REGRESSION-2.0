"""EmpMonitor Automation Framework.

An enterprise automation platform that continuously validates the EmpMonitor
ecosystem. Its defining rule is that a conclusion must be supported by multiple
independent evidence sources across defined layers -- a bare pass/fail is not an
acceptable output (``docs/ADS/validation_standard.md``).

Package structure and dependency direction (``docs/ADS/architecture.md`` §3)::

    plugins/      ->  framework.core, framework.shared,
                      framework.monitors, framework.validators
    framework.core     ->  framework.shared
    framework.monitors ->  framework.shared
    framework.validators -> framework.shared
    framework.shared   ->  (nothing internal)

No module under ``framework`` may import from ``plugins``. The contracts
(models, interfaces, exceptions) live in :mod:`framework.shared` so that every
tier can implement them without inverting this direction.

Phase 1 delivers the reusable foundation only: configuration, logging, context,
event bus, plugin registry, models, exceptions, base interfaces, the scheduling
contract, utilities, and report models. It contains no EmpMonitor feature
behaviour -- ``framework.monitors`` and ``framework.validators`` remain
unimplemented scaffolds until later phases.

Typical entry point::

    from framework.core import Orchestrator, bootstrap

    result = bootstrap()
    report = Orchestrator.from_bootstrap(result).run()
"""

from __future__ import annotations

from framework.shared.constants import (
    FRAMEWORK_NAME,
    FRAMEWORK_VERSION,
    VALIDATION_STANDARD_VERSION,
)

__all__ = [
    "FRAMEWORK_NAME",
    "FRAMEWORK_VERSION",
    "VALIDATION_STANDARD_VERSION",
    "__version__",
]

__version__ = FRAMEWORK_VERSION
