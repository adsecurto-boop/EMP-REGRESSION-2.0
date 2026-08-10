"""Plugin lifecycle engine.

Drives one unit of work through the lifecycle stages defined by
:class:`~framework.shared.models.LifecycleStage`::

    REGISTER -> INITIALIZE -> PRECHECK -> EXECUTE -> VALIDATE -> POSTCHECK
             -> REPORT -> CLEANUP        (with FAILED / SKIPPED as outcomes)

Every stage emits framework events, so the timeline records progress through the
lifecycle rather than only its outcome -- which is what makes a hang or a failure
attributable to a specific stage.

Two invariants the engine guarantees:

* **CLEANUP always runs.** Whatever happens in earlier stages, resources are
  released. A plugin that failed mid-execution must not leak handles into the rest
  of the run.
* **A unit that did not complete never reports success.** Failure, timeout,
  cancellation, and skipping each produce their own status, and only ``COMPLETED``
  carries findings forward as conclusions.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from framework.core.event_bus import EventBus, EventType
from framework.core.hooks import HookPoint, HookRegistry
from framework.core.metrics import MetricsEngine
from framework.shared.exceptions import (
    ExecutionCancelledError,
    ExecutionTimeoutError,
    FrameworkError,
    PluginError,
)
from framework.shared.interfaces import Plugin
from framework.shared.logger import correlation_scope, get_logger
from framework.shared.models import (
    ExecutionResult,
    ExecutionStatus,
    Finding,
    LifecycleStage,
    ValidationContext,
    Verdict,
    utc_now,
)

__all__ = ["StageRecord", "LifecycleOutcome", "LifecycleEngine"]

_LOGGER = get_logger(__name__)
_SOURCE = "core.lifecycle"


@dataclass(frozen=True, slots=True)
class StageRecord:
    """The outcome of one lifecycle stage.

    Args:
        stage: The stage.
        succeeded: Whether it completed without error.
        duration_seconds: How long it took.
        error: Error message when it failed.
        detail: Additional structured detail.
    """

    stage: LifecycleStage
    succeeded: bool
    duration_seconds: float = 0.0
    error: str | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LifecycleOutcome:
    """The result of running a unit through the lifecycle.

    Args:
        unit_id: The unit.
        result: The execution result, always present so a caller never has to
            reconstruct one for a failed unit.
        stages: Record of every stage attempted, in order.
        skipped_reason: Why the unit was skipped, if it was.
        blocked_reason: Why the unit was blocked by precheck, if it was.
    """

    unit_id: str
    result: ExecutionResult
    stages: Sequence[StageRecord] = field(default_factory=tuple)
    skipped_reason: str | None = None
    blocked_reason: str | None = None

    @property
    def stages_reached(self) -> tuple[LifecycleStage, ...]:
        """The stages that were attempted, in order."""
        return tuple(record.stage for record in self.stages)

    @property
    def failed_stage(self) -> LifecycleStage | None:
        """The first stage that failed, if any."""
        return next(
            (record.stage for record in self.stages if not record.succeeded), None
        )


class LifecycleEngine:
    """Runs a single unit through the lifecycle stages.

    Collaborators are injected so a caller can supply their own bus, hooks, or
    metrics -- or none, in which case inert defaults are used and the engine still
    works. That keeps a plugin testable without assembling the whole framework.
    """

    __slots__ = ("_event_bus", "_hooks", "_metrics")

    def __init__(
        self,
        *,
        event_bus: EventBus | None = None,
        hooks: HookRegistry | None = None,
        metrics: MetricsEngine | None = None,
    ) -> None:
        """Initialise the engine.

        Args:
            event_bus: Bus for stage events. A private bus is created when omitted.
            hooks: Hook registry for before/after plugin hooks.
            metrics: Metrics engine for timing and counters.
        """
        self._event_bus = event_bus or EventBus()
        self._hooks = hooks or HookRegistry()
        self._metrics = metrics

    def _emit_stage(
        self,
        event_type: EventType,
        stage: LifecycleStage,
        unit_id: str,
        execution_id: str | None,
        **payload: Any,
    ) -> None:
        """Publish a stage event.

        Args:
            event_type: Which stage event.
            stage: The stage concerned.
            unit_id: The unit.
            execution_id: Run identifier.
            **payload: Additional detail.
        """
        self._event_bus.emit(
            event_type,
            _SOURCE,
            execution_id=execution_id,
            stage=stage.value,
            unit_id=unit_id,
            **payload,
        )

    def _run_stage(
        self,
        stage: LifecycleStage,
        unit_id: str,
        execution_id: str | None,
        action: Any,
        records: list[StageRecord],
    ) -> tuple[bool, Any]:
        """Run one stage, recording timing, events, and any failure.

        Args:
            stage: The stage to run.
            unit_id: The unit.
            execution_id: Run identifier.
            action: Zero-argument callable performing the stage's work.
            records: Accumulator for stage records.

        Returns:
            Whether the stage succeeded, and the action's return value (``None`` on
            failure).

        Raises:
            ExecutionTimeoutError: Propagated unchanged -- a timeout is the
                execution engine's concern, not a stage failure to be swallowed.
            ExecutionCancelledError: Propagated unchanged, for the same reason.
        """
        self._emit_stage(EventType.STAGE_STARTED, stage, unit_id, execution_id)
        started = utc_now()
        try:
            value = action()
        except (ExecutionTimeoutError, ExecutionCancelledError):
            raise
        except Exception as exc:  # noqa: BLE001 -- stage isolation boundary
            duration = (utc_now() - started).total_seconds()
            records.append(
                StageRecord(
                    stage=stage,
                    succeeded=False,
                    duration_seconds=duration,
                    error=str(exc),
                )
            )
            self._emit_stage(
                EventType.STAGE_FAILED, stage, unit_id, execution_id, error=str(exc)
            )
            _LOGGER.error(
                "Stage %s failed for %s: %s", stage.value, unit_id, exc, exc_info=True
            )
            return False, None
        duration = (utc_now() - started).total_seconds()
        records.append(
            StageRecord(stage=stage, succeeded=True, duration_seconds=duration)
        )
        self._emit_stage(
            EventType.STAGE_COMPLETED,
            stage,
            unit_id,
            execution_id,
            duration_seconds=duration,
        )
        return True, value

    def run(
        self, plugin: Plugin, context: ValidationContext
    ) -> LifecycleOutcome:
        """Run a plugin through the full lifecycle.

        Args:
            plugin: The plugin to run.
            context: Run context passed to each stage.

        Returns:
            The lifecycle outcome, including an execution result in every case.

        Raises:
            ExecutionTimeoutError: If a stage exceeded its deadline.
            ExecutionCancelledError: If the run was cancelled mid-stage.
        """
        unit_id = plugin.metadata.plugin_id
        execution_id = context.execution_id
        records: list[StageRecord] = []
        started_at = utc_now()

        with correlation_scope(plugin_id=unit_id):
            hook_outcome = self._hooks.invoke(
                HookPoint.BEFORE_PLUGIN, unit_id, execution_id=execution_id
            )
            if hook_outcome.vetoed:
                return self._skipped(
                    unit_id,
                    execution_id,
                    started_at,
                    records,
                    f"vetoed by hook: {hook_outcome.veto_reason}",
                )

            self._event_bus.emit(
                EventType.PLUGIN_STARTED,
                _SOURCE,
                execution_id=execution_id,
                plugin_id=unit_id,
            )

            # Applicability gate. Deliberately not a lifecycle stage: it is asked
            # before any resource is acquired, and treating it as PRECHECK would
            # put two PRECHECK records in the timeline for one unit.
            try:
                applicable = plugin.should_execute(context)
            except Exception as exc:  # noqa: BLE001 -- gate failure is a unit failure
                _LOGGER.error(
                    "Applicability check failed for %s: %s", unit_id, exc, exc_info=True
                )
                return self._failed(
                    unit_id,
                    execution_id,
                    started_at,
                    records,
                    f"applicability check failed: {exc}",
                )
            if not applicable:
                return self._skipped(
                    unit_id,
                    execution_id,
                    started_at,
                    records,
                    "plugin reported it does not apply to this run",
                )

            # INITIALIZE
            initialised, _ = self._run_stage(
                LifecycleStage.INITIALIZE, unit_id, execution_id, plugin.setup, records
            )
            if not initialised:
                self._cleanup(plugin, unit_id, execution_id, records)
                return self._failed(
                    unit_id, execution_id, started_at, records, "initialisation failed"
                )

            try:
                # PRECHECK -- a BLOCKED finding here prevents execution, because
                # validating with unmet preconditions produces misleading results.
                precheck_ok, precheck_findings = self._run_stage(
                    LifecycleStage.PRECHECK,
                    unit_id,
                    execution_id,
                    lambda: tuple(plugin.precheck(context)),
                    records,
                )
                findings: list[Finding] = list(precheck_findings or ())
                if not precheck_ok:
                    return self._failed(
                        unit_id, execution_id, started_at, records, "precheck failed"
                    )
                blocking = [
                    item for item in findings if item.verdict is Verdict.BLOCKED
                ]
                if blocking:
                    reason = blocking[0].what
                    return self._blocked(
                        unit_id, execution_id, started_at, records, findings, reason
                    )

                # EXECUTE
                executed, result = self._run_stage(
                    LifecycleStage.EXECUTE,
                    unit_id,
                    execution_id,
                    lambda: plugin.execute(context),
                    records,
                )
                if not executed or result is None:
                    return self._failed(
                        unit_id,
                        execution_id,
                        started_at,
                        records,
                        "execution failed",
                        findings=findings,
                    )
                if not isinstance(result, ExecutionResult):
                    return self._failed(
                        unit_id,
                        execution_id,
                        started_at,
                        records,
                        "plugin returned a value that is not an ExecutionResult",
                        findings=findings,
                    )
                findings.extend(result.findings)

                # VALIDATE
                _, extra = self._run_stage(
                    LifecycleStage.VALIDATE,
                    unit_id,
                    execution_id,
                    lambda: tuple(plugin.validate(context, result)),
                    records,
                )
                findings.extend(extra or ())

                # POSTCHECK
                _, post = self._run_stage(
                    LifecycleStage.POSTCHECK,
                    unit_id,
                    execution_id,
                    lambda: tuple(plugin.postcheck(context, result)),
                    records,
                )
                findings.extend(post or ())

                # REPORT -- the unit's contribution is assembled; rendering happens
                # later, in a reporter.
                self._run_stage(
                    LifecycleStage.REPORT,
                    unit_id,
                    execution_id,
                    lambda: len(findings),
                    records,
                )

                final = replace(
                    result,
                    findings=tuple(findings),
                    status=ExecutionStatus.COMPLETED,
                    started_at=started_at,
                    finished_at=utc_now(),
                )
            finally:
                self._cleanup(plugin, unit_id, execution_id, records)

            if self._metrics is not None:
                self._metrics.record_status(unit_id, final.status)
                self._metrics.record_counts(unit_id, findings=len(final.findings))
            self._event_bus.emit(
                EventType.PLUGIN_COMPLETED,
                _SOURCE,
                execution_id=execution_id,
                plugin_id=unit_id,
                verdict=final.verdict.value,
            )
            self._hooks.invoke(
                HookPoint.AFTER_PLUGIN,
                unit_id,
                execution_id=execution_id,
                verdict=final.verdict.value,
            )
            return LifecycleOutcome(
                unit_id=unit_id, result=final, stages=tuple(records)
            )

    def _cleanup(
        self,
        plugin: Plugin,
        unit_id: str,
        execution_id: str | None,
        records: list[StageRecord],
    ) -> None:
        """Run the CLEANUP stage, which must never be skipped.

        Args:
            plugin: The plugin to tear down.
            unit_id: The unit.
            execution_id: Run identifier.
            records: Accumulator for stage records.
        """
        try:
            self._run_stage(
                LifecycleStage.CLEANUP, unit_id, execution_id, plugin.teardown, records
            )
        except (ExecutionTimeoutError, ExecutionCancelledError) as exc:
            # Cleanup must not be abandoned because the unit was cancelled or timed
            # out; record it and move on rather than leaking the resource.
            _LOGGER.error("Cleanup interrupted for %s: %s", unit_id, exc)
            records.append(
                StageRecord(
                    stage=LifecycleStage.CLEANUP, succeeded=False, error=str(exc)
                )
            )

    def _terminal(
        self,
        unit_id: str,
        execution_id: str | None,
        started_at: Any,
        records: list[StageRecord],
        *,
        status: ExecutionStatus,
        stage: LifecycleStage,
        event: EventType,
        reason: str,
        findings: Sequence[Finding] = (),
    ) -> LifecycleOutcome:
        """Build a terminal outcome and emit its event.

        Args:
            unit_id: The unit.
            execution_id: Run identifier.
            started_at: When the unit started.
            records: Stage records accumulated.
            status: Terminal execution status.
            stage: Terminal lifecycle stage.
            event: Event to publish.
            reason: Why the unit ended this way.
            findings: Findings gathered before termination.

        Returns:
            The terminal outcome.
        """
        records.append(StageRecord(stage=stage, succeeded=False, error=reason))
        # Terminal plugin events carry ``plugin_id`` as well as ``unit_id`` so every
        # ``plugin.*`` event has a consistent payload. Without it a subscriber cannot
        # tell which plugin failed, and anything gating on a plugin's outcome silently
        # never fires.
        self._emit_stage(
            event, stage, unit_id, execution_id, reason=reason, plugin_id=unit_id
        )
        if self._metrics is not None:
            self._metrics.record_status(unit_id, status)
            self._metrics.record_counts(
                unit_id,
                findings=len(findings),
                errors=1 if status is ExecutionStatus.ERRORED else 0,
            )
        result = ExecutionResult(
            unit_id=unit_id,
            status=status,
            findings=tuple(findings),
            started_at=started_at,
            finished_at=utc_now(),
            error=reason,
        )
        self._hooks.invoke(
            HookPoint.AFTER_PLUGIN,
            unit_id,
            execution_id=execution_id,
            verdict=result.verdict.value,
            status=status.value,
        )
        return LifecycleOutcome(
            unit_id=unit_id,
            result=result,
            stages=tuple(records),
            skipped_reason=reason if status is ExecutionStatus.SKIPPED else None,
        )

    def _skipped(
        self,
        unit_id: str,
        execution_id: str | None,
        started_at: Any,
        records: list[StageRecord],
        reason: str,
    ) -> LifecycleOutcome:
        """Build a SKIPPED outcome.

        Args:
            unit_id: The unit.
            execution_id: Run identifier.
            started_at: When the unit started.
            records: Stage records accumulated.
            reason: Why it was skipped.

        Returns:
            The outcome.
        """
        _LOGGER.info("Plugin %s skipped: %s", unit_id, reason)
        return self._terminal(
            unit_id,
            execution_id,
            started_at,
            records,
            status=ExecutionStatus.SKIPPED,
            stage=LifecycleStage.SKIPPED,
            event=EventType.PLUGIN_SKIPPED,
            reason=reason,
        )

    def _failed(
        self,
        unit_id: str,
        execution_id: str | None,
        started_at: Any,
        records: list[StageRecord],
        reason: str,
        *,
        findings: Sequence[Finding] = (),
    ) -> LifecycleOutcome:
        """Build a FAILED outcome.

        Args:
            unit_id: The unit.
            execution_id: Run identifier.
            started_at: When the unit started.
            records: Stage records accumulated.
            reason: Why it failed.
            findings: Findings gathered before failure.

        Returns:
            The outcome. Its verdict is ``INCONCLUSIVE``: the framework failed to
            complete, which says nothing about the product's health.
        """
        return self._terminal(
            unit_id,
            execution_id,
            started_at,
            records,
            status=ExecutionStatus.ERRORED,
            stage=LifecycleStage.FAILED,
            event=EventType.PLUGIN_FAILED,
            reason=reason,
            findings=findings,
        )

    def _blocked(
        self,
        unit_id: str,
        execution_id: str | None,
        started_at: Any,
        records: list[StageRecord],
        findings: Sequence[Finding],
        reason: str,
    ) -> LifecycleOutcome:
        """Build an outcome for a unit blocked by precheck.

        A blocked unit *ran correctly* -- it correctly determined it could not
        proceed -- so its status is ``COMPLETED`` while its findings carry the
        ``BLOCKED`` verdict. Marking the unit itself as errored would conflate a
        framework failure with a precondition the product did not meet.

        Args:
            unit_id: The unit.
            execution_id: Run identifier.
            started_at: When the unit started.
            records: Stage records accumulated.
            findings: Findings from precheck, including the blocking one.
            reason: Why it was blocked.

        Returns:
            The outcome.
        """
        _LOGGER.warning("Plugin %s blocked by precheck: %s", unit_id, reason)
        records.append(
            StageRecord(stage=LifecycleStage.PRECHECK, succeeded=True, error=reason)
        )
        self._emit_stage(
            EventType.STAGE_COMPLETED,
            LifecycleStage.PRECHECK,
            unit_id,
            execution_id,
            blocked=True,
            reason=reason,
        )
        if self._metrics is not None:
            self._metrics.record_status(unit_id, ExecutionStatus.COMPLETED)
            self._metrics.record_counts(unit_id, findings=len(findings), warnings=1)
        result = ExecutionResult(
            unit_id=unit_id,
            status=ExecutionStatus.COMPLETED,
            findings=tuple(findings),
            started_at=started_at,
            finished_at=utc_now(),
        )
        self._event_bus.emit(
            EventType.PLUGIN_COMPLETED,
            _SOURCE,
            execution_id=execution_id,
            plugin_id=unit_id,
            verdict=result.verdict.value,
            blocked=True,
        )
        self._hooks.invoke(
            HookPoint.AFTER_PLUGIN,
            unit_id,
            execution_id=execution_id,
            verdict=result.verdict.value,
        )
        return LifecycleOutcome(
            unit_id=unit_id,
            result=result,
            stages=tuple(records),
            blocked_reason=reason,
        )
