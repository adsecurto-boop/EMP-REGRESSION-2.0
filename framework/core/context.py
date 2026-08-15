"""Runtime execution context.

The context is the single object carrying per-run state: identity, timing,
environment facts, configuration, the evidence store, and the plugin registry.
Threading it explicitly through components is the framework's dependency
injection mechanism -- it is why nothing here needs module-level globals beyond
the two approved singletons (configuration and logging).

The context holds *references to* collaborators; it is not a service locator and
must not grow behaviour of its own. Components receive what they need from it and
do their work themselves.
"""

from __future__ import annotations

import getpass
import platform
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from framework.shared.config import Configuration
from framework.shared.constants import (
    FRAMEWORK_VERSION,
    MIN_CORROBORATING_LAYERS,
    REPORTS_DIR_NAME,
)
from framework.shared.exceptions import FrameworkError
from framework.shared.logger import get_logger, new_execution_id
from framework.shared.models import (
    AgentInfo,
    DashboardInfo,
    EnvironmentInfo,
    ValidationContext,
    utc_now,
)
from framework.shared.utils import datetime_utils, filesystem

if TYPE_CHECKING:  # pragma: no cover -- import cycle avoidance for type checking only
    from framework.core.evidence import EvidenceStore
    from framework.core.registry import PluginRegistry

__all__ = ["RuntimeContext", "build_environment_info"]

_LOGGER = get_logger(__name__)


def build_environment_info(
    name: str,
    *,
    organization: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> EnvironmentInfo:
    """Describe the machine the framework is running on.

    Records facts about the *host executing the framework*, which are always
    available. It deliberately records nothing about EmpMonitor -- agent and
    dashboard facts are product observations, and gathering them is a later
    phase's collector work.

    Args:
        name: Environment name.
        organization: Owning organization, if known.
        metadata: Additional detail to record.

    Returns:
        Populated environment information.
    """
    try:
        user: str | None = getpass.getuser()
    except (OSError, KeyError):  # pragma: no cover -- depends on host account setup
        user = None
    return EnvironmentInfo(
        name=name,
        host=socket.gethostname(),
        os_version=platform.platform(),
        organization=organization,
        user=user,
        metadata=dict(metadata or {}),
    )


@dataclass(slots=True)
class RuntimeContext:
    """State for one framework run.

    Mutable, unlike the framework's data models: a run genuinely progresses
    through states, and agent/dashboard facts are discovered partway through it.
    Its mutable fields are assigned by the orchestrator, never by arbitrary
    components reaching in.

    Args:
        configuration: Resolved configuration for this run.
        environment: Environment the run executes against.
        execution_id: Unique run identifier.
        started_at: Run start timestamp.
        agent: Agent facts, populated once observed.
        dashboard: Dashboard facts, populated once observed.
        build_number: Build identifier of the framework or pipeline, if any.
        output_root: Directory beneath which run output is written.
        metadata: Additional run-scoped detail.
    """

    configuration: Configuration
    environment: EnvironmentInfo
    execution_id: str = field(default_factory=new_execution_id)
    started_at: Any = field(default_factory=utc_now)
    agent: AgentInfo = field(default_factory=AgentInfo)
    dashboard: DashboardInfo = field(default_factory=DashboardInfo)
    build_number: str | None = None
    output_root: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    _evidence_store: "EvidenceStore | None" = field(default=None, repr=False)
    _plugin_registry: "PluginRegistry | None" = field(default=None, repr=False)

    @property
    def framework_version(self) -> str:
        """The framework version producing this run."""
        return FRAMEWORK_VERSION

    @property
    def organization(self) -> str | None:
        """Owning organization, as recorded on the environment."""
        return self.environment.organization

    @property
    def current_user(self) -> str | None:
        """The account the framework is running as."""
        return self.environment.user

    @property
    def agent_version(self) -> str | None:
        """Observed agent version, or ``None`` if not yet established."""
        return self.agent.version

    @property
    def minimum_corroborating_layers(self) -> int:
        """Configured corroboration minimum, clamped to the ratified floor.

        The Validation Standard permits tuning this but never below two, so a
        configured value lower than the floor is raised rather than honoured.
        """
        configured = self.configuration.get(
            "validation.minimum_corroborating_layers", MIN_CORROBORATING_LAYERS
        )
        try:
            return max(int(configured), MIN_CORROBORATING_LAYERS)
        except (TypeError, ValueError):
            return MIN_CORROBORATING_LAYERS

    @property
    def elapsed_seconds(self) -> float:
        """Seconds since the run started."""
        return (utc_now() - self.started_at).total_seconds()

    @property
    def evidence_store(self) -> "EvidenceStore":
        """The run's evidence store.

        Returns:
            The attached store.

        Raises:
            FrameworkError: If no store has been attached yet.
        """
        if self._evidence_store is None:
            from framework.shared.exceptions import FrameworkError  # noqa: PLC0415

            raise FrameworkError(
                "No evidence store attached to the runtime context",
                {"execution_id": self.execution_id},
            )
        return self._evidence_store

    @property
    def plugin_registry(self) -> "PluginRegistry":
        """The run's plugin registry.

        Returns:
            The attached registry.

        Raises:
            FrameworkError: If no registry has been attached yet.
        """
        if self._plugin_registry is None:
            from framework.shared.exceptions import FrameworkError  # noqa: PLC0415

            raise FrameworkError(
                "No plugin registry attached to the runtime context",
                {"execution_id": self.execution_id},
            )
        return self._plugin_registry

    def attach(
        self,
        *,
        evidence_store: "EvidenceStore | None" = None,
        plugin_registry: "PluginRegistry | None" = None,
    ) -> "RuntimeContext":
        """Attach collaborators to the context.

        Called by the orchestrator during bootstrap. Kept as an explicit step so
        that constructing a context in a test does not require building the whole
        object graph.

        Args:
            evidence_store: Store to attach.
            plugin_registry: Registry to attach.

        Returns:
            This context, to allow chaining.
        """
        if evidence_store is not None:
            self._evidence_store = evidence_store
        if plugin_registry is not None:
            self._plugin_registry = plugin_registry
        return self

    def resolve_output_root(self) -> Path:
        """Return the run's output directory, creating it if needed.

        The directory name embeds the start timestamp and execution id so runs
        sort chronologically and never collide.

        Returns:
            The run output directory.
        """
        if self.output_root is not None:
            return filesystem.ensure_directory(self.output_root)
        configured = self.configuration.get("output.root")
        base = (
            Path(configured)
            if configured
            else filesystem.repository_root() / REPORTS_DIR_NAME
        )
        stamp = datetime_utils.format_timestamp_for_filename(self.started_at)
        resolved = base / f"{stamp}_{self.execution_id[:8]}"
        try:
            self.output_root = filesystem.ensure_directory(resolved)
        except (FrameworkError, PermissionError, OSError):
            # Fallback for installed location (e.g., C:\Program Files) where standard user lacks write permissions
            fallback_base = Path.home() / ".empmonitor" / REPORTS_DIR_NAME
            resolved = fallback_base / f"{stamp}_{self.execution_id[:8]}"
            self.output_root = filesystem.ensure_directory(resolved)
        _LOGGER.debug("Run output root resolved to %s", self.output_root)
        return self.output_root

    def to_validation_context(self, *, plugin_id: str | None = None) -> ValidationContext:
        """Derive an immutable validation context for a validator or plugin.

        Converting rather than passing the runtime context directly keeps
        validators unable to mutate run state, and gives them a stable input
        shape.

        Args:
            plugin_id: Owning plugin identifier, when applicable.

        Returns:
            An immutable validation context carrying currently known facts and
            all evidence collected so far.
        """
        evidence = (
            self._evidence_store.all() if self._evidence_store is not None else ()
        )
        return ValidationContext(
            execution_id=self.execution_id,
            environment=self.environment,
            agent=self.agent,
            dashboard=self.dashboard,
            evidence=evidence,
            minimum_layers=self.minimum_corroborating_layers,
            plugin_id=plugin_id,
            metadata=dict(self.metadata),
        )

    def summary(self) -> dict[str, Any]:
        """Return a serialisable summary of the run context.

        Used in report metadata so a report records the conditions it was
        produced under.

        Returns:
            A JSON-friendly mapping.
        """
        return {
            "execution_id": self.execution_id,
            "started_at": datetime_utils.format_iso8601(self.started_at),
            "framework_version": self.framework_version,
            "environment": self.environment.name,
            "host": self.environment.host,
            "os_version": self.environment.os_version,
            "organization": self.organization,
            "current_user": self.current_user,
            "build_number": self.build_number,
            "agent_version": self.agent_version,
            "minimum_corroborating_layers": self.minimum_corroborating_layers,
        }
