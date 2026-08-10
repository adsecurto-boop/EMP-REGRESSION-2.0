"""Run orchestration.

The orchestrator wires the framework together and owns the run lifecycle at the
top level: bootstrap, delegate execution, aggregate, report.

It is deliberately thin. Since Phase 1.5 the real work belongs to dedicated
engines -- :mod:`framework.core.execution` for running units,
:mod:`framework.core.lifecycle` for stages, :mod:`framework.core.validation` for
verdicts, :mod:`framework.core.aggregator` for the final account. The orchestrator
composes them; it does not reimplement them, and it contains no validation logic
and no feature knowledge.

Failure handling follows ``docs/ADS/error_handling_standard.md`` §5: a unit failure
is isolated by the execution engine, a bootstrap failure is run-fatal, and a report
is produced even when the run fails (``reporting.md`` §7).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from framework.core.aggregator import AggregatedResult, ResultAggregator
from framework.core.artifacts import ArtifactManager
from framework.core.context import RuntimeContext, build_environment_info
from framework.core.event_bus import EventBus, EventType
from framework.core.evidence import EvidenceCatalog, EvidenceStore, build_catalog_from_config
from framework.core.execution import ExecutionEngine, ExecutionMode, ExecutionReport
from framework.core.hooks import HookRegistry
from framework.core.metrics import MetricsEngine
from framework.core.registry import PluginRegistry
from framework.core.reporting import Report, ReportMetadata
from framework.core.timeline import ExecutionTimeline
from framework.core.validation import ValidationEngine
from framework.shared.config import Configuration, ConfigurationManager
from framework.shared.exceptions import FrameworkError, PluginError
from framework.shared.logger import LogContext, configure_logging, get_logger
from framework.shared.models import ExecutionStatus, Verdict

__all__ = ["Orchestrator", "BootstrapResult", "bootstrap"]

_LOGGER = get_logger(__name__)
_SOURCE = "core.orchestrator"


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """The wired-up object graph for a run.

    Returned rather than stashed in globals so a caller (including a test) can hold
    and inspect the graph, and so nothing has to reach into module state to find its
    collaborators.

    Args:
        context: The runtime context.
        event_bus: The run's event bus.
        registry: The plugin registry.
        evidence_store: The evidence store.
        hooks: The hook registry.
        metrics: The metrics engine.
        timeline: The execution timeline, already attached to the bus.
        artifacts: The artifact manager.
        validation_engine: The verdict engine, configured with this run's
            corroboration minimum.
    """

    context: RuntimeContext
    event_bus: EventBus
    registry: PluginRegistry
    evidence_store: EvidenceStore
    hooks: HookRegistry
    metrics: MetricsEngine
    timeline: ExecutionTimeline
    artifacts: ArtifactManager
    validation_engine: ValidationEngine


def _build_catalog(configuration: Configuration) -> EvidenceCatalog:
    """Build the evidence catalog from configuration.

    Args:
        configuration: Resolved configuration.

    Returns:
        The catalog, empty when none is configured. An empty catalog disables strict
        source checking rather than rejecting all evidence, so the framework remains
        usable before the catalog mirror is populated.

    Raises:
        FrameworkError: If ``evidence.sources`` is not a list.
    """
    entries = configuration.get("evidence.sources", [])
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise FrameworkError(
            "'evidence.sources' must be a list of source entries",
            {"found": type(entries).__name__},
        )
    if not entries:
        _LOGGER.warning(
            "No evidence sources configured; evidence source validation is disabled"
        )
        return EvidenceCatalog()
    return build_catalog_from_config(list(entries))


def bootstrap(
    *,
    config_dir: Path | None = None,
    environment: str | None = None,
    keep_event_history: bool = False,
) -> BootstrapResult:
    """Start the framework and wire its components together.

    Order matters: configuration first (everything else is configured by it), then
    logging (so subsequent steps are observable), then the context and its
    collaborators.

    Args:
        config_dir: Configuration directory override.
        environment: Environment name override.
        keep_event_history: Retain events on the bus as well as in the timeline.
            Off by default -- the timeline already records every event, so bus
            history would be a second copy of the same data.

    Returns:
        The wired object graph.

    Raises:
        ConfigurationError: If configuration cannot be loaded or is invalid.
        FrameworkError: If another bootstrap step fails.
    """
    manager = ConfigurationManager(config_dir=config_dir, environment=environment)
    ConfigurationManager.set_instance(manager)
    configuration = manager.load()

    environment_info = build_environment_info(
        configuration.environment,
        organization=configuration.get("organization"),
    )
    context = RuntimeContext(
        configuration=configuration,
        environment=environment_info,
        build_number=configuration.get("build_number"),
    )
    LogContext.bind(execution_id=context.execution_id)

    output_root = context.resolve_output_root()
    logging_settings = configuration.get("logging", {})
    configure_logging(
        logging_settings if isinstance(logging_settings, Mapping) else {},
        output_root=output_root,
        force=True,
    )

    _LOGGER.info(
        "Framework starting: version=%s environment=%s execution_id=%s",
        context.framework_version,
        configuration.environment,
        context.execution_id,
    )

    event_bus = EventBus(keep_history=keep_event_history)
    timeline = ExecutionTimeline()
    timeline.attach(event_bus)

    evidence_store = EvidenceStore(
        _build_catalog(configuration),
        artifact_root=output_root,
        strict=bool(configuration.get("evidence.strict", True)),
    )
    registry = PluginRegistry()
    context.attach(evidence_store=evidence_store, plugin_registry=registry)

    hooks = HookRegistry()
    metrics = MetricsEngine(
        context.execution_id,
        trace_memory=bool(configuration.get("metrics.trace_memory", False)),
    )
    artifacts = ArtifactManager(output_root, context.execution_id)
    validation_engine = ValidationEngine(
        minimum_layers=context.minimum_corroborating_layers
    )

    package = configuration.get("plugins.package")
    if package:
        try:
            registry.discover(str(package))
        except PluginError as exc:
            # Discovery failure must not prevent a run: the run simply has no
            # plugins, which the report shows as an unanswered question.
            _LOGGER.error("Plugin discovery failed for package %s: %s", package, exc)

    _LOGGER.info(
        "Bootstrap complete: %d plugin(s) registered, %d evidence source(s) known",
        len(registry),
        len(evidence_store.catalog),
    )
    return BootstrapResult(
        context=context,
        event_bus=event_bus,
        registry=registry,
        evidence_store=evidence_store,
        hooks=hooks,
        metrics=metrics,
        timeline=timeline,
        artifacts=artifacts,
        validation_engine=validation_engine,
    )


class Orchestrator:
    """Coordinates a run from start to report.

    Collaborators are injected rather than constructed internally, so a caller can
    substitute any of them (composition over inheritance, dependency injection).
    """

    __slots__ = (
        "_context",
        "_event_bus",
        "_registry",
        "_hooks",
        "_metrics",
        "_timeline",
        "_artifacts",
        "_engine",
        "_aggregator",
    )

    def __init__(
        self,
        context: RuntimeContext,
        *,
        event_bus: EventBus,
        registry: PluginRegistry,
        hooks: HookRegistry | None = None,
        metrics: MetricsEngine | None = None,
        timeline: ExecutionTimeline | None = None,
        artifacts: ArtifactManager | None = None,
        validation_engine: ValidationEngine | None = None,
    ) -> None:
        """Initialise the orchestrator.

        Args:
            context: The run's context.
            event_bus: Bus to publish lifecycle events on.
            registry: Registry supplying plugins to execute.
            hooks: Hook registry.
            metrics: Metrics engine.
            timeline: Execution timeline. Attached to the bus if not already.
            artifacts: Artifact manager.
            validation_engine: Verdict engine used for aggregation.
        """
        self._context = context
        self._event_bus = event_bus
        self._registry = registry
        self._hooks = hooks or HookRegistry()
        self._metrics = metrics or MetricsEngine(context.execution_id)
        self._timeline = timeline or ExecutionTimeline()
        self._timeline.attach(event_bus)
        self._artifacts = artifacts
        self._engine = ExecutionEngine(
            registry,
            event_bus=event_bus,
            hooks=self._hooks,
            metrics=self._metrics,
        )
        self._aggregator = ResultAggregator(engine=validation_engine)

    @classmethod
    def from_bootstrap(cls, result: BootstrapResult) -> "Orchestrator":
        """Build an orchestrator from a bootstrap result.

        Args:
            result: Wired object graph from :func:`bootstrap`.

        Returns:
            The orchestrator.
        """
        return cls(
            result.context,
            event_bus=result.event_bus,
            registry=result.registry,
            hooks=result.hooks,
            metrics=result.metrics,
            timeline=result.timeline,
            artifacts=result.artifacts,
            validation_engine=result.validation_engine,
        )

    @property
    def context(self) -> RuntimeContext:
        """The run's context."""
        return self._context

    @property
    def execution_engine(self) -> ExecutionEngine:
        """The execution engine, for cancellation and shutdown."""
        return self._engine

    @property
    def timeline(self) -> ExecutionTimeline:
        """The run's timeline."""
        return self._timeline

    def run(
        self,
        plugin_ids: Sequence[str] | None = None,
        *,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        max_workers: int | None = None,
        completed: Mapping[str, ExecutionStatus] | None = None,
    ) -> Report:
        """Execute the run and assemble a report.

        A report is always produced, including when plugins fail or none are
        registered -- an absent report would hide the outcome entirely.

        Args:
            plugin_ids: Subset of plugins to execute; defaults to all enabled
                plugins in dependency order.
            mode: Sequential or parallel execution.
            max_workers: Worker limit for parallel execution.
            completed: Units already finished in a previous run, for resume.

        Returns:
            The assembled report.
        """
        self._event_bus.emit(
            EventType.RUN_STARTED,
            _SOURCE,
            execution_id=self._context.execution_id,
            environment=self._context.environment.name,
            mode=mode.value,
        )

        execution: ExecutionReport | None = None
        try:
            execution = self._engine.execute(
                self._context.to_validation_context(),
                plugin_ids,
                mode=mode,
                max_workers=max_workers,
                completed=completed,
            )
        except FrameworkError as exc:
            # A failure to execute at all is still reportable: the report will
            # carry the error and an INCONCLUSIVE verdict rather than nothing.
            _LOGGER.error("Execution could not be carried out: %s", exc)
            self._event_bus.emit(
                EventType.RUN_FAILED,
                _SOURCE,
                execution_id=self._context.execution_id,
                error=str(exc),
            )

        report = self._finalise(execution)
        event = (
            EventType.RUN_FAILED
            if report.summary.overall_verdict in (Verdict.FAILED, Verdict.BLOCKED)
            else EventType.RUN_COMPLETED
        )
        self._event_bus.emit(
            event,
            _SOURCE,
            execution_id=self._context.execution_id,
            verdict=report.summary.overall_verdict.value,
        )
        _LOGGER.info(
            "Run complete: verdict=%s confidence=%s findings=%d",
            report.summary.overall_verdict.value,
            report.summary.lowest_confidence.name,
            report.summary.total_findings,
        )
        return report

    def aggregate(self, execution: ExecutionReport | None) -> AggregatedResult:
        """Aggregate a run's outputs without building the report.

        Args:
            execution: The execution report, if execution ran.

        Returns:
            The aggregated result.
        """
        return self._aggregator.aggregate(
            execution=execution,
            evidence=self._context.evidence_store.all(),
            metrics=self._metrics.finish(),
            artifacts=self._artifacts,
            graph=execution.graph if execution is not None else None,
            extra_warnings=(
                () if execution is not None else ("execution did not run",)
            ),
        )

    def _finalise(self, execution: ExecutionReport | None) -> Report:
        """Aggregate results and assemble the report.

        Args:
            execution: The execution report, if execution ran.

        Returns:
            The assembled report.
        """
        self._event_bus.emit(
            EventType.REPORT_STARTED, _SOURCE, execution_id=self._context.execution_id
        )
        aggregated = self.aggregate(execution)
        environment = self._context.environment
        metadata = ReportMetadata(
            execution_id=self._context.execution_id,
            environment=environment.name,
            framework_version=self._context.framework_version,
            host=environment.host,
            organization=environment.organization,
            build_number=self._context.build_number,
            agent_version=self._context.agent_version,
            extra={
                "config_sources": [
                    str(path) for path in self._context.configuration.sources
                ]
            },
        )
        results = execution.ordered_results if execution is not None else ()
        report = self._aggregator.build_report(
            aggregated,
            metadata=metadata,
            results=results,
            timeline=self._timeline,
            duration_seconds=self._context.elapsed_seconds,
        )
        if self._artifacts is not None:
            try:
                self._artifacts.snapshot_configuration(
                    self._context.configuration.as_dict()
                )
                self._artifacts.write_manifest()
            except FrameworkError as exc:
                # Losing the manifest must not lose the report.
                _LOGGER.error("Artifact manifest could not be written: %s", exc)
        self._event_bus.emit(
            EventType.REPORT_COMPLETED,
            _SOURCE,
            execution_id=self._context.execution_id,
            findings=report.summary.total_findings,
        )
        return report
