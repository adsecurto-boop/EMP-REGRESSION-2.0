"""Framework exception hierarchy.

Every failure raised by framework code or by a plugin must use a type from this
module, so that the orchestrator can catch, classify, and route failures
uniformly regardless of origin (see ``docs/ADS/error_handling_standard.md`` §4).

The hierarchy mirrors the error categories in that standard:

* :class:`ConfigurationError` -- invalid/missing configuration
* :class:`EnvironmentError_` -- prerequisite environment condition not met
* :class:`EvidenceError` -- evidence could not be captured or failed validation
* :class:`ValidationError` -- a validation could not be carried out
* :class:`PluginError` -- failure originating in a single plugin
* :class:`SynchronizationError` -- Layer 3 (synchronization) failure
* :class:`SchedulerError` -- failure in scheduling units of work
* :class:`ReportingError` -- failure producing or persisting a report

Note the distinction drawn by ``docs/ADS/validation_standard.md`` §9: these
exceptions describe failures **of the framework itself**. A failure of the
*product under validation* is not an exception -- it is a
:class:`~framework.shared.models.Finding` carrying a ``FAILED`` verdict. Raising
an exception because EmpMonitor is broken would be an architecture violation.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = [
    "FrameworkError",
    "ConfigurationError",
    "EnvironmentError_",
    "EvidenceError",
    "ValidationError",
    "PluginError",
    "PluginNotFoundError",
    "PluginDependencyError",
    "SynchronizationError",
    "SchedulerError",
    "ReportingError",
    "ExecutionError",
    "ExecutionTimeoutError",
    "ExecutionCancelledError",
    "ArtifactError",
    "HookError",
]


class FrameworkError(Exception):
    """Base class for every framework failure.

    Carries an optional structured ``context`` mapping so that a handler can
    report *why* a failure occurred without parsing the message string. Per the
    "no silent failure" principle, anything catching a ``FrameworkError`` must
    log it and reflect it in the run outcome.

    Args:
        message: Human-readable description of the failure.
        context: Optional structured detail (identifiers, paths, keys). Must not
            contain secrets -- see ``docs/ADS/logging_standard.md`` §8.
    """

    def __init__(self, message: str, context: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = dict(context) if context else {}

    def __str__(self) -> str:
        if not self.context:
            return self.message
        detail = ", ".join(f"{key}={value!r}" for key, value in sorted(self.context.items()))
        return f"{self.message} ({detail})"


class ConfigurationError(FrameworkError):
    """Configuration is missing, malformed, or fails validation.

    Per ``docs/ADS/configuration_standard.md`` §7 a run must fail fast on
    invalid configuration rather than proceed with undefined behaviour.
    """


class EnvironmentError_(FrameworkError):
    """A prerequisite environment condition is not met.

    Named with a trailing underscore to avoid shadowing the builtin
    ``EnvironmentError``. Raising this maps to the ``BLOCKED`` verdict: the
    validation did not run, so nothing may be concluded about the product.
    """


class EvidenceError(FrameworkError):
    """Evidence could not be collected, or failed evidence validation.

    Raised by collectors when a source is unreachable, and by evidence
    validation when a captured artifact does not meet requirements.
    """


class ValidationError(FrameworkError):
    """A validation could not be carried out.

    This means the framework failed to *reach* a conclusion. It does **not**
    mean the product failed -- that is a ``FAILED``
    :class:`~framework.shared.models.Finding`.
    """


class PluginError(FrameworkError):
    """Failure originating in a single plugin.

    The orchestrator isolates these so one plugin's failure does not block
    unrelated plugins (``docs/ADS/error_handling_standard.md`` §2).
    """


class PluginNotFoundError(PluginError):
    """A plugin was requested by identifier but is not registered."""


class PluginDependencyError(PluginError):
    """A plugin's declared dependencies cannot be satisfied or are cyclic."""


class SynchronizationError(FrameworkError):
    """A Layer 3 (synchronization) collection or observation failure.

    Reserved for the Synchronization Monitor designed in
    ``docs/design/Synchronization_Monitor.md``; no implementation exists in
    Phase 1.
    """


class SchedulerError(FrameworkError):
    """A unit of work could not be scheduled or dispatched."""


class ReportingError(FrameworkError):
    """A report could not be produced or persisted."""


class ExecutionError(FrameworkError):
    """A unit of work could not be executed to completion.

    Raised by the execution engine for failures in its own machinery. A failure
    *inside* a plugin surfaces as :class:`PluginError`; a failure of the engine to
    run that plugin at all surfaces as this.
    """


class ExecutionTimeoutError(ExecutionError):
    """A unit of work exceeded its allotted time.

    A timeout yields an ``INCONCLUSIVE`` verdict, never a failure of the product:
    the framework ran out of time, which says nothing about EmpMonitor's health.
    """


class ExecutionCancelledError(ExecutionError):
    """A unit of work was cancelled before completing.

    Cancellation is a framework decision (shutdown, upstream failure), so like a
    timeout it yields ``INCONCLUSIVE`` rather than a product verdict.
    """


class ArtifactError(FrameworkError):
    """An artifact could not be stored, read, or verified."""


class HookError(FrameworkError):
    """An extension hook failed.

    Hook failures are isolated by default so that a third-party hook cannot abort
    the run that invoked it; this is raised only when a hook is registered as
    required.
    """
