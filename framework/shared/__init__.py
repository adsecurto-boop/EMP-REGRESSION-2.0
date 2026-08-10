"""Cross-cutting foundations shared by every framework tier.

This package is the bottom of the dependency graph defined in
``docs/ADS/architecture.md`` §3. It may not import from
:mod:`framework.core`, :mod:`framework.monitors`, :mod:`framework.validators`,
or ``plugins``.

The contracts -- :mod:`~framework.shared.models`,
:mod:`~framework.shared.interfaces`, :mod:`~framework.shared.exceptions` -- live
here rather than in :mod:`framework.core` precisely because of that rule:
monitors and validators must be able to implement the interfaces and produce the
models without depending on ``core``.

Contents:

==============================  =============================================
:mod:`~framework.shared.constants`   Invariant values
:mod:`~framework.shared.exceptions`  Exception hierarchy
:mod:`~framework.shared.models`      Ratified contracts as data models
:mod:`~framework.shared.interfaces`  Abstract base classes for extension points
:mod:`~framework.shared.config`      Configuration loading and access
:mod:`~framework.shared.logger`      Logging configuration and access
:mod:`~framework.shared.utils`       Generic helper submodules
==============================  =============================================
"""

from __future__ import annotations

from framework.shared.config import Configuration, ConfigurationManager, load_configuration
from framework.shared.exceptions import (
    ConfigurationError,
    EnvironmentError_,
    EvidenceError,
    FrameworkError,
    PluginDependencyError,
    PluginError,
    PluginNotFoundError,
    ReportingError,
    SchedulerError,
    SynchronizationError,
    ValidationError,
)
from framework.shared.interfaces import (
    Collector,
    Component,
    Monitor,
    Plugin,
    Reporter,
    Scheduler,
    Validator,
)
from framework.shared.logger import (
    LogContext,
    configure_logging,
    get_logger,
    new_correlation_id,
    new_execution_id,
)
from framework.shared.models import (
    AgentInfo,
    Confidence,
    DashboardInfo,
    EnvironmentInfo,
    Evidence,
    EvidenceConflict,
    EvidenceLayer,
    EvidenceSourceSpec,
    ExecutionResult,
    ExecutionStatus,
    FailureClass,
    Finding,
    PluginMetadata,
    SourceReliability,
    ValidationContext,
    Verdict,
)

__all__ = [
    # Configuration
    "Configuration",
    "ConfigurationManager",
    "load_configuration",
    # Exceptions
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
    # Interfaces
    "Component",
    "Collector",
    "Validator",
    "Monitor",
    "Plugin",
    "Reporter",
    "Scheduler",
    # Logging
    "LogContext",
    "configure_logging",
    "get_logger",
    "new_execution_id",
    "new_correlation_id",
    # Models
    "EvidenceLayer",
    "Verdict",
    "Confidence",
    "FailureClass",
    "SourceReliability",
    "EvidenceSourceSpec",
    "Evidence",
    "EvidenceConflict",
    "Finding",
    "ExecutionStatus",
    "ExecutionResult",
    "PluginMetadata",
    "ValidationContext",
    "EnvironmentInfo",
    "AgentInfo",
    "DashboardInfo",
]
