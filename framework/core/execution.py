"""Execution engine.

Runs units of work through the lifecycle, honouring dependency order, with support
for sequential and parallel execution, cancellation, timeouts, retries, and
graceful shutdown.

**Threads, not processes.** Validation work is I/O-bound -- reading files, querying
databases, waiting on the network, driving a browser -- so threads give real
concurrency without the cost of serialising context across process boundaries.

**On timeout enforcement.** Python cannot forcibly kill a thread. A unit that
exceeds its timeout is *abandoned*: it is recorded ``TIMED_OUT`` and the run moves
on, but the underlying thread may continue until it returns on its own. This is a
language limitation, not a design choice, and it is reported honestly rather than
papered over -- see the performance risks in the Implementation Review. Units are
therefore expected to cooperate with cancellation via :class:`CancellationToken`.

A ``TIMED_OUT`` or ``CANCELLED`` unit yields an ``INCONCLUSIVE`` verdict. The
framework ran out of time or was told to stop; neither says anything about whether
the product is healthy.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence

from framework.core.dependencies import DependencyResolver
from framework.core.event_bus import EventBus, EventType
from framework.core.graph import ExecutionGraph, NodeState
from framework.core.hooks import HookPoint, HookRegistry
from framework.core.lifecycle import LifecycleEngine, LifecycleOutcome
from framework.core.metrics import MetricsEngine
from framework.core.registry import PluginRegistry
from framework.shared.exceptions import ExecutionError
from framework.shared.logger import get_logger
from framework.shared.models import (
    ExecutionResult,
    ExecutionStatus,
    PluginMetadata,
    ValidationContext,
    Verdict,
    utc_now,
)
from framework.shared.utils import retry as retry_utils

__all__ = [
    "ExecutionMode",
    "CancellationToken",
    "ExecutionPlan",
    "ExecutionReport",
    "ExecutionEngine",
]

_LOGGER = get_logger(__name__)
_SOURCE = "core.execution"


class ExecutionMode(Enum):
    """How units are executed."""

    SEQUENTIAL = "sequential"
    """One unit at a time, in dependency order. Deterministic and easiest to
    debug; the default."""

    PARALLEL = "parallel"
    """Units within a dependency level run concurrently, levels in order."""


class CancellationToken:
    """A cooperative cancellation signal.

    Cooperative because Python cannot forcibly stop a thread. Long-running units
    should poll :meth:`is_cancelled` (or wait on :meth:`wait`) and return promptly
    when it is set. A unit that ignores the token cannot be stopped, only abandoned.
    """

    __slots__ = ("_event", "_reason", "_lock")

    def __init__(self) -> None:
        """Create an uncancelled token."""
        self._event = threading.Event()
        self._reason: str | None = None
        self._lock = threading.Lock()

    def cancel(self, reason: str = "cancelled") -> None:
        """Request cancellation.

        Args:
            reason: Why cancellation was requested. The first reason wins, so the
                original cause is not overwritten by later cascading cancellations.
        """
        with self._lock:
            if self._reason is None:
                self._reason = reason
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._event.is_set()

    @property
    def reason(self) -> str | None:
        """Why cancellation was requested, if it was."""
        with self._lock:
            return self._reason

    def wait(self, timeout: float | None = None) -> bool:
        """Block until cancelled or the timeout elapses.

        Args:
            timeout: Maximum seconds to wait, or ``None`` to wait indefinitely.

        Returns:
            ``True`` if cancellation was requested.
        """
        return self._event.wait(timeout)

    def raise_if_cancelled(self) -> None:
        """Raise if cancellation has been requested.

        Raises:
            ExecutionCancelledError: If cancelled.
        """
        if self.is_cancelled:
            from framework.shared.exceptions import (  # noqa: PLC0415 -- local to keep imports light
                ExecutionCancelledError,
            )

            raise ExecutionCancelledError(
                "Execution cancelled", {"reason": self.reason or "unspecified"}
            )


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """What the engine intends to execute.

    Produced before execution so a caller can inspect or record the plan without
    running it -- useful for dry runs and for reporting what a run *would* have done.

    Args:
        mode: Execution mode.
        order: Units in execution order.
        levels: Dependency levels; members of a level may run in parallel.
        excluded: Units that cannot run, mapped to the reason.
        max_workers: Worker limit for parallel execution.
    """

    mode: ExecutionMode
    order: Sequence[str] = field(default_factory=tuple)
    levels: Sequence[Sequence[str]] = field(default_factory=tuple)
    excluded: Mapping[str, str] = field(default_factory=dict)
    max_workers: int = 1

    @property
    def unit_count(self) -> int:
        """Number of units that will be executed."""
        return len(self.order)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "mode": self.mode.value,
            "unit_count": self.unit_count,
            "order": list(self.order),
            "levels": [list(level) for level in self.levels],
            "excluded": dict(self.excluded),
            "max_workers": self.max_workers,
        }


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    """The outcome of an execution.

    Args:
        plan: The plan that was executed.
        results: Execution results, keyed by unit id.
        outcomes: Full lifecycle outcomes, keyed by unit id.
        graph: The execution graph with final node states.
        cancelled: Whether the run was cancelled.
        cancellation_reason: Why, if it was.
        started_at: When execution began.
        finished_at: When execution ended.
    """

    plan: ExecutionPlan
    results: Mapping[str, ExecutionResult] = field(default_factory=dict)
    outcomes: Mapping[str, LifecycleOutcome] = field(default_factory=dict)
    graph: ExecutionGraph | None = None
    cancelled: bool = False
    cancellation_reason: str | None = None
    started_at: Any = None
    finished_at: Any = None

    @property
    def ordered_results(self) -> tuple[ExecutionResult, ...]:
        """Results in the plan's execution order, then any extras."""
        ordered = [self.results[key] for key in self.plan.order if key in self.results]
        extra = [
            value for key, value in sorted(self.results.items()) if key not in self.plan.order
        ]
        return tuple(ordered + extra)

    @property
    def verdict(self) -> Verdict:
        """Aggregate verdict across every unit."""
        return Verdict.aggregate(result.verdict for result in self.results.values())

    @property
    def duration_seconds(self) -> float | None:
        """Wall-clock duration, or ``None`` if not finished."""
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


class ExecutionEngine:
    """Executes units of work through the lifecycle.

    Every collaborator is injected, so the engine can be exercised with any subset
    of the framework assembled. Nothing here knows what a unit validates -- which is
    what allows it to run plugins the framework has never seen.
    """

    __slots__ = (
        "_registry",
        "_event_bus",
        "_hooks",
        "_metrics",
        "_lifecycle",
        "_token",
        "_shutdown_grace",
    )

    def __init__(
        self,
        registry: PluginRegistry,
        *,
        event_bus: EventBus | None = None,
        hooks: HookRegistry | None = None,
        metrics: MetricsEngine | None = None,
        lifecycle: LifecycleEngine | None = None,
        cancellation_token: CancellationToken | None = None,
        shutdown_grace_seconds: float = 10.0,
    ) -> None:
        """Initialise the engine.

        Args:
            registry: Registry supplying units to execute.
            event_bus: Bus for execution events.
            hooks: Hook registry.
            metrics: Metrics engine.
            lifecycle: Lifecycle engine. One is built from the other collaborators
                when omitted, so they stay consistent.
            cancellation_token: Token for cooperative cancellation.
            shutdown_grace_seconds: How long a graceful shutdown waits for in-flight
                units before giving up on them.
        """
        self._registry = registry
        self._event_bus = event_bus or EventBus()
        self._hooks = hooks or HookRegistry()
        self._metrics = metrics
        self._lifecycle = lifecycle or LifecycleEngine(
            event_bus=self._event_bus, hooks=self._hooks, metrics=metrics
        )
        self._token = cancellation_token or CancellationToken()
        self._shutdown_grace = shutdown_grace_seconds

    @property
    def cancellation_token(self) -> CancellationToken:
        """The token used to request cancellation."""
        return self._token

    def request_shutdown(self, reason: str = "shutdown requested") -> None:
        """Request a graceful shutdown.

        Args:
            reason: Why shutdown was requested.
        """
        self._token.cancel(reason)

    def plan(
        self,
        unit_ids: Iterable[str] | None = None,
        *,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        max_workers: int | None = None,
    ) -> tuple[ExecutionPlan, ExecutionGraph]:
        """Build an execution plan and graph without executing anything.

        Args:
            unit_ids: Units to execute; defaults to all enabled units.
            mode: Execution mode.
            max_workers: Worker limit for parallel mode. Defaults to the widest
                dependency level, since more workers than that cannot help.

        Returns:
            The plan and the graph it was derived from.

        Raises:
            ExecutionError: If a requested unit is not registered.
        """
        metadata = list(self._registry.all_metadata())
        resolver = DependencyResolver(metadata)
        try:
            requested = (
                None if unit_ids is None else list(unit_ids)
            )
            resolution = resolver.analyse(requested)
        except Exception as exc:  # noqa: BLE001 -- normalised to an execution failure
            raise ExecutionError(
                "Execution plan could not be resolved",
                {"requested": sorted(unit_ids) if unit_ids else None},
            ) from exc

        selected = set(resolution.order) | set(resolution.excluded)
        graph = ExecutionGraph(
            [item for item in metadata if item.plugin_id in selected],
            resolution=resolution,
        )
        widest = max((len(level) for level in resolution.levels), default=1)
        workers = (
            1
            if mode is ExecutionMode.SEQUENTIAL
            else max(1, max_workers if max_workers is not None else widest)
        )
        plan = ExecutionPlan(
            mode=mode,
            order=tuple(resolution.order),
            levels=tuple(tuple(level) for level in resolution.levels),
            excluded=dict(resolution.excluded),
            max_workers=workers,
        )
        _LOGGER.info(
            "Execution plan: %d unit(s), %d level(s), mode=%s, workers=%d, %d excluded",
            plan.unit_count,
            len(plan.levels),
            plan.mode.value,
            plan.max_workers,
            len(plan.excluded),
        )
        return plan, graph

    def execute(
        self,
        context: ValidationContext,
        unit_ids: Iterable[str] | None = None,
        *,
        mode: ExecutionMode = ExecutionMode.SEQUENTIAL,
        max_workers: int | None = None,
        completed: Mapping[str, ExecutionStatus] | None = None,
    ) -> ExecutionReport:
        """Execute units and return a report.

        Args:
            context: Run context passed to each unit.
            unit_ids: Units to execute; defaults to all enabled units.
            mode: Sequential or parallel.
            max_workers: Worker limit for parallel mode.
            completed: Units already finished in a previous run, for resume. These
                are not re-executed.

        Returns:
            The execution report, including results, outcomes, and final graph state.

        Raises:
            ExecutionError: If the plan cannot be built.
        """
        plan, graph = self.plan(unit_ids, mode=mode, max_workers=max_workers)
        started_at = utc_now()
        self._hooks.invoke(
            HookPoint.BEFORE_RUN, "execution", execution_id=context.execution_id
        )

        if completed:
            graph.seed_completed(completed)

        results: dict[str, ExecutionResult] = {}
        outcomes: dict[str, LifecycleOutcome] = {}

        for unit_id, reason in sorted(plan.excluded.items()):
            results[unit_id] = self._excluded_result(unit_id, reason, context)

        if mode is ExecutionMode.SEQUENTIAL:
            self._run_sequential(plan, graph, context, results, outcomes)
        else:
            self._run_parallel(plan, graph, context, results, outcomes)

        finished_at = utc_now()
        self._hooks.invoke(
            HookPoint.AFTER_RUN,
            "execution",
            execution_id=context.execution_id,
            unit_count=len(results),
        )
        report = ExecutionReport(
            plan=plan,
            results=results,
            outcomes=outcomes,
            graph=graph,
            cancelled=self._token.is_cancelled,
            cancellation_reason=self._token.reason,
            started_at=started_at,
            finished_at=finished_at,
        )
        _LOGGER.info(
            "Execution finished: %d unit(s), verdict=%s%s",
            len(results),
            report.verdict.value,
            f", cancelled ({self._token.reason})" if self._token.is_cancelled else "",
        )
        return report

    def _excluded_result(
        self, unit_id: str, reason: str, context: ValidationContext
    ) -> ExecutionResult:
        """Build a result for a unit that could not run at all.

        Args:
            unit_id: The unit.
            reason: Why it was excluded.
            context: Run context.

        Returns:
            A ``SKIPPED`` result. Its verdict is ``INCONCLUSIVE``, so an
            unsatisfiable dependency can never read as a pass.
        """
        _LOGGER.warning("Unit %s excluded: %s", unit_id, reason)
        self._event_bus.emit(
            EventType.PLUGIN_SKIPPED,
            _SOURCE,
            execution_id=context.execution_id,
            plugin_id=unit_id,
            reason=reason,
        )
        if self._metrics is not None:
            self._metrics.record_status(unit_id, ExecutionStatus.SKIPPED)
        return ExecutionResult(
            unit_id=unit_id,
            status=ExecutionStatus.SKIPPED,
            started_at=utc_now(),
            finished_at=utc_now(),
            error=reason,
            metadata={"excluded": True, "reason": reason},
        )

    def _run_sequential(
        self,
        plan: ExecutionPlan,
        graph: ExecutionGraph,
        context: ValidationContext,
        results: dict[str, ExecutionResult],
        outcomes: dict[str, LifecycleOutcome],
    ) -> None:
        """Execute units one at a time, in dependency order.

        Args:
            plan: The plan.
            graph: The graph to update.
            context: Run context.
            results: Accumulator for results.
            outcomes: Accumulator for lifecycle outcomes.
        """
        for unit_id in plan.order:
            if self._should_stop(unit_id, graph, context, results):
                continue
            self._execute_one(unit_id, graph, context, results, outcomes)

    def _run_parallel(
        self,
        plan: ExecutionPlan,
        graph: ExecutionGraph,
        context: ValidationContext,
        results: dict[str, ExecutionResult],
        outcomes: dict[str, LifecycleOutcome],
    ) -> None:
        """Execute each dependency level concurrently, levels in order.

        A level barrier is used rather than a free-running work queue because a
        unit must not start until every dependency has *finished* -- and the level
        boundary is exactly that guarantee. The cost is that a slow unit holds up
        its level; the benefit is that dependency correctness is structural rather
        than something the scheduler has to police.

        Args:
            plan: The plan.
            graph: The graph to update.
            context: Run context.
            results: Accumulator for results.
            outcomes: Accumulator for lifecycle outcomes.
        """
        lock = threading.Lock()
        with ThreadPoolExecutor(
            max_workers=plan.max_workers, thread_name_prefix="empaf-exec"
        ) as pool:
            for level in plan.levels:
                runnable = [
                    unit_id
                    for unit_id in level
                    if not self._should_stop(unit_id, graph, context, results)
                ]
                if not runnable:
                    continue
                futures: dict[Future[None], str] = {}
                for unit_id in runnable:
                    graph.mark(unit_id, NodeState.RUNNING)
                    futures[
                        pool.submit(
                            self._execute_one,
                            unit_id,
                            graph,
                            context,
                            results,
                            outcomes,
                            lock,
                        )
                    ] = unit_id
                for future, unit_id in futures.items():
                    try:
                        future.result()
                    except Exception as exc:  # noqa: BLE001 -- already recorded
                        _LOGGER.error(
                            "Parallel unit %s raised past its handler: %s",
                            unit_id,
                            exc,
                            exc_info=True,
                        )

    def _should_stop(
        self,
        unit_id: str,
        graph: ExecutionGraph,
        context: ValidationContext,
        results: dict[str, ExecutionResult],
    ) -> bool:
        """Decide whether a unit should be skipped before it starts.

        Args:
            unit_id: The unit.
            graph: The graph.
            context: Run context.
            results: Accumulator for results.

        Returns:
            ``True`` if the unit must not run, having recorded why.
        """
        node = graph.node(unit_id)
        if node.state.is_terminal:
            # Already settled: blocked by a failed dependency, or restored on resume.
            if unit_id not in results and node.state is not NodeState.SUCCEEDED:
                results[unit_id] = ExecutionResult(
                    unit_id=unit_id,
                    status=(
                        ExecutionStatus.CANCELLED
                        if node.state is NodeState.CANCELLED
                        else ExecutionStatus.SKIPPED
                    ),
                    started_at=utc_now(),
                    finished_at=utc_now(),
                    error=node.reason,
                    metadata={"node_state": node.state.value, "reason": node.reason},
                )
            return True
        if self._token.is_cancelled:
            reason = self._token.reason or "cancelled"
            graph.mark(unit_id, NodeState.CANCELLED, reason=reason)
            results[unit_id] = ExecutionResult(
                unit_id=unit_id,
                status=ExecutionStatus.CANCELLED,
                started_at=utc_now(),
                finished_at=utc_now(),
                error=reason,
            )
            self._event_bus.emit(
                EventType.PLUGIN_CANCELLED,
                _SOURCE,
                execution_id=context.execution_id,
                plugin_id=unit_id,
                reason=reason,
            )
            if self._metrics is not None:
                self._metrics.record_status(unit_id, ExecutionStatus.CANCELLED)
            return True
        return False

    def _execute_one(
        self,
        unit_id: str,
        graph: ExecutionGraph,
        context: ValidationContext,
        results: dict[str, ExecutionResult],
        outcomes: dict[str, LifecycleOutcome],
        lock: threading.Lock | None = None,
    ) -> None:
        """Execute one unit, applying retry and timeout, and update the graph.

        Args:
            unit_id: The unit.
            graph: The graph to update.
            context: Run context.
            results: Accumulator for results.
            outcomes: Accumulator for lifecycle outcomes.
            lock: Lock guarding the accumulators when running in parallel.
        """
        metadata = self._registry.metadata_for(unit_id)
        graph.mark(unit_id, NodeState.RUNNING)
        outcome = self._attempt_with_retry(unit_id, metadata, context)

        def record() -> None:
            results[unit_id] = outcome.result
            outcomes[unit_id] = outcome

        if lock is not None:
            with lock:
                record()
        else:
            record()

        status = outcome.result.status
        if status is ExecutionStatus.COMPLETED:
            graph.mark(unit_id, NodeState.SUCCEEDED)
        elif status is ExecutionStatus.SKIPPED:
            graph.mark(unit_id, NodeState.SKIPPED, reason=outcome.skipped_reason)
        else:
            blocked = graph.mark(
                unit_id,
                NodeState.from_execution_status(status),
                reason=outcome.result.error,
            )
            for dependent in blocked:
                node = graph.node(dependent)
                blocked_result = ExecutionResult(
                    unit_id=dependent,
                    status=ExecutionStatus.SKIPPED,
                    started_at=utc_now(),
                    finished_at=utc_now(),
                    error=node.reason,
                    metadata={"blocked_by": unit_id, "reason": node.reason},
                )
                if lock is not None:
                    with lock:
                        results.setdefault(dependent, blocked_result)
                else:
                    results.setdefault(dependent, blocked_result)

    def _attempt_with_retry(
        self, unit_id: str, metadata: PluginMetadata, context: ValidationContext
    ) -> LifecycleOutcome:
        """Run a unit, retrying per its declared policy.

        Only *framework-level* failures are retried, and only when the unit opted in
        via ``max_attempts``. A unit that ran correctly and reported a product
        failure is never retried: retrying until the product looks healthy would
        manufacture a false positive.

        Args:
            unit_id: The unit.
            metadata: Its metadata, carrying timeout and attempt policy.
            context: Run context.

        Returns:
            The outcome of the final attempt.
        """
        attempts = max(1, metadata.max_attempts)
        outcome: LifecycleOutcome | None = None
        for attempt in range(1, attempts + 1):
            if self._token.is_cancelled:
                break
            outcome = self._attempt_once(unit_id, metadata, context, attempt)
            if outcome.result.status is not ExecutionStatus.ERRORED:
                return outcome
            if attempt < attempts:
                _LOGGER.warning(
                    "Retrying %s after failure (attempt %d of %d)",
                    unit_id,
                    attempt + 1,
                    attempts,
                )
                self._event_bus.emit(
                    EventType.PLUGIN_RETRYING,
                    _SOURCE,
                    execution_id=context.execution_id,
                    plugin_id=unit_id,
                    attempt=attempt + 1,
                    of=attempts,
                )
        return outcome or self._timed_out_outcome(unit_id, context, "not attempted")

    def _attempt_once(
        self,
        unit_id: str,
        metadata: PluginMetadata,
        context: ValidationContext,
        attempt: int,
    ) -> LifecycleOutcome:
        """Make one attempt at a unit, enforcing its timeout.

        The timeout is enforced by waiting on a worker future. If it elapses the
        unit is abandoned rather than killed, because Python cannot terminate a
        thread; the abandoned thread is left as a daemon so it cannot prevent
        interpreter exit.

        Args:
            unit_id: The unit.
            metadata: Its metadata.
            context: Run context.
            attempt: Attempt number, for logging.

        Returns:
            The lifecycle outcome, or a synthesised timeout/failure outcome.
        """
        timeout = metadata.timeout_seconds

        def invoke() -> LifecycleOutcome:
            plugin = self._registry.create(unit_id)
            if self._metrics is not None:
                with self._metrics.measure(unit_id):
                    return self._lifecycle.run(plugin, context)
            return self._lifecycle.run(plugin, context)

        if timeout is None:
            try:
                return invoke()
            except Exception as exc:  # noqa: BLE001 -- isolation boundary
                return self._failed_outcome(unit_id, context, str(exc))

        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"empaf-{unit_id}")
        future = pool.submit(invoke)
        try:
            return future.result(timeout=timeout)
        except FutureTimeout:
            _LOGGER.error(
                "Unit %s exceeded its %.1fs timeout on attempt %d and was abandoned",
                unit_id,
                timeout,
                attempt,
            )
            future.cancel()
            self._token.cancel(f"unit {unit_id} timed out")
            self._event_bus.emit(
                EventType.PLUGIN_TIMED_OUT,
                _SOURCE,
                execution_id=context.execution_id,
                plugin_id=unit_id,
                timeout_seconds=timeout,
            )
            return self._timed_out_outcome(
                unit_id, context, f"exceeded timeout of {timeout}s"
            )
        except Exception as exc:  # noqa: BLE001 -- isolation boundary
            return self._failed_outcome(unit_id, context, str(exc))
        finally:
            # Do not block on an abandoned worker: shutting down without waiting
            # lets the run proceed, and the thread cannot hold up interpreter exit.
            pool.shutdown(wait=False)

    def _synthetic_outcome(
        self,
        unit_id: str,
        context: ValidationContext,
        status: ExecutionStatus,
        reason: str,
    ) -> LifecycleOutcome:
        """Build an outcome for a unit the lifecycle could not report on itself.

        Args:
            unit_id: The unit.
            context: Run context.
            status: Terminal status.
            reason: Why.

        Returns:
            The synthesised outcome.
        """
        if self._metrics is not None:
            self._metrics.record_status(unit_id, status)
            self._metrics.record_counts(unit_id, errors=1)
        return LifecycleOutcome(
            unit_id=unit_id,
            result=ExecutionResult(
                unit_id=unit_id,
                status=status,
                started_at=utc_now(),
                finished_at=utc_now(),
                error=reason,
            ),
        )

    def _timed_out_outcome(
        self, unit_id: str, context: ValidationContext, reason: str
    ) -> LifecycleOutcome:
        """Build a ``TIMED_OUT`` outcome.

        Args:
            unit_id: The unit.
            context: Run context.
            reason: Why.

        Returns:
            The outcome.
        """
        return self._synthetic_outcome(
            unit_id, context, ExecutionStatus.TIMED_OUT, reason
        )

    def _failed_outcome(
        self, unit_id: str, context: ValidationContext, reason: str
    ) -> LifecycleOutcome:
        """Build an ``ERRORED`` outcome.

        Args:
            unit_id: The unit.
            context: Run context.
            reason: Why.

        Returns:
            The outcome.
        """
        _LOGGER.error("Unit %s failed outside the lifecycle: %s", unit_id, reason)
        return self._synthetic_outcome(
            unit_id, context, ExecutionStatus.ERRORED, reason
        )

    def shutdown(self, reason: str = "graceful shutdown") -> bool:
        """Request shutdown and wait for in-flight work within the grace period.

        Args:
            reason: Why shutdown was requested.

        Returns:
            ``True`` if the grace period elapsed without the token being observed;
            in-flight units are cooperative, so a caller may still need to abandon
            them.
        """
        _LOGGER.info("Graceful shutdown requested: %s", reason)
        self._token.cancel(reason)
        return self._token.wait(self._shutdown_grace)
