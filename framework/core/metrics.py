"""Execution metrics collection.

Records timing, resource usage, and execution counters so a run's cost and
behaviour are observable, not guessed at.

**On resource measurement.** The framework has no mandatory third-party
dependencies, and the standard library cannot portably report process RSS memory
(:mod:`resource` is POSIX-only). Rather than pretend otherwise:

* Wall-clock intervals use :func:`time.perf_counter`, **not**
  :func:`time.monotonic`. On Windows ``monotonic`` has a resolution of ~15.6 ms, so
  any unit finishing faster than that would measure as zero -- and short units are
  exactly what a validation run is full of. ``perf_counter`` resolves to ~100 ns on
  the same platform.
* CPU time uses :func:`time.process_time`, which is portable and accurate.
* Python-heap memory uses :mod:`tracemalloc`, opt-in because tracing carries real
  overhead.
* OS-level RSS is reported only when :mod:`psutil` happens to be installed, and is
  ``None`` otherwise.

A ``None`` metric means "not measured", which is honest. Reporting a fabricated
number would corrupt exactly the performance comparisons metrics exist to support.
"""

from __future__ import annotations

import threading
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping

from framework.shared.logger import get_logger
from framework.shared.models import ExecutionStatus, utc_now
from framework.shared.utils import datetime_utils

__all__ = ["Timing", "UnitMetrics", "RunMetrics", "MetricsEngine"]

_LOGGER = get_logger(__name__)


def _rss_bytes() -> int | None:
    """Return process resident memory, if it can be determined portably.

    Returns:
        Resident set size in bytes, or ``None`` when unavailable.
    """
    try:
        import psutil  # noqa: PLC0415 -- optional dependency, probed on demand

        return int(psutil.Process().memory_info().rss)
    except Exception:  # noqa: BLE001 -- absence is expected, never fatal
        return None


@dataclass(frozen=True, slots=True)
class Timing:
    """A wall-clock and CPU-time measurement.

    Args:
        wall_seconds: Elapsed wall-clock time.
        cpu_seconds: Process CPU time consumed.
        started_at: When measurement began.
        finished_at: When measurement ended.
    """

    wall_seconds: float
    cpu_seconds: float
    started_at: Any = None
    finished_at: Any = None

    @property
    def human(self) -> str:
        """Wall time in compact human-readable form."""
        return datetime_utils.humanize_duration(self.wall_seconds)


@dataclass(slots=True)
class UnitMetrics:
    """Metrics for one execution unit.

    Mutable because a unit accumulates counters as it runs; it is snapshotted
    into an immutable form for reporting.

    Args:
        unit_id: The unit measured.
        timing: Timing once complete.
        status: Terminal execution status.
        attempts: Execution attempts made.
        retries: Retries performed (``attempts - 1``).
        findings: Findings produced.
        warnings: Warnings recorded.
        errors: Errors recorded.
        peak_traced_memory_bytes: Peak Python-heap memory, when tracing was on.
        extra: Additional counters.
    """

    unit_id: str
    timing: Timing | None = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    attempts: int = 0
    findings: int = 0
    warnings: int = 0
    errors: int = 0
    peak_traced_memory_bytes: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def retries(self) -> int:
        """Number of retries, i.e. attempts beyond the first."""
        return max(0, self.attempts - 1)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "unit_id": self.unit_id,
            "status": self.status.value,
            "wall_seconds": self.timing.wall_seconds if self.timing else None,
            "cpu_seconds": self.timing.cpu_seconds if self.timing else None,
            "attempts": self.attempts,
            "retries": self.retries,
            "findings": self.findings,
            "warnings": self.warnings,
            "errors": self.errors,
            "peak_traced_memory_bytes": self.peak_traced_memory_bytes,
            **self.extra,
        }


@dataclass(slots=True)
class RunMetrics:
    """Metrics for a whole run.

    Args:
        execution_id: Run identifier.
        started_at: Run start.
        finished_at: Run end, once known.
        units: Per-unit metrics keyed by unit id.
        rss_bytes_at_start: Process RSS at start, when measurable.
        rss_bytes_at_end: Process RSS at end, when measurable.
        peak_traced_memory_bytes: Peak Python-heap memory across the run.
    """

    execution_id: str
    started_at: Any = field(default_factory=utc_now)
    finished_at: Any = None
    units: dict[str, UnitMetrics] = field(default_factory=dict)
    rss_bytes_at_start: int | None = None
    rss_bytes_at_end: int | None = None
    peak_traced_memory_bytes: int | None = None

    @property
    def total_wall_seconds(self) -> float | None:
        """Total run wall time, or ``None`` if the run has not finished."""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    def counts_by_status(self) -> dict[str, int]:
        """Tally units by terminal status.

        Returns:
            A mapping of status value to count, covering every status so that a
            zero is explicit rather than a missing key.
        """
        tally = {status.value: 0 for status in ExecutionStatus}
        for unit in self.units.values():
            tally[unit.status.value] += 1
        return tally

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        totals = self.counts_by_status()
        return {
            "execution_id": self.execution_id,
            "started_at": datetime_utils.format_iso8601(self.started_at),
            "finished_at": (
                datetime_utils.format_iso8601(self.finished_at)
                if self.finished_at is not None
                else None
            ),
            "total_wall_seconds": self.total_wall_seconds,
            "total_cpu_seconds": round(
                sum(
                    unit.timing.cpu_seconds
                    for unit in self.units.values()
                    if unit.timing is not None
                ),
                6,
            ),
            "units_executed": len(self.units),
            "status_counts": totals,
            "total_retries": sum(unit.retries for unit in self.units.values()),
            "total_findings": sum(unit.findings for unit in self.units.values()),
            "total_warnings": sum(unit.warnings for unit in self.units.values()),
            "total_errors": sum(unit.errors for unit in self.units.values()),
            "rss_bytes_at_start": self.rss_bytes_at_start,
            "rss_bytes_at_end": self.rss_bytes_at_end,
            "peak_traced_memory_bytes": self.peak_traced_memory_bytes,
            "units": [unit.to_dict() for unit in self.units.values()],
        }


class MetricsEngine:
    """Collects metrics for a run and its units.

    Thread-safe, since units may execute in parallel.
    """

    __slots__ = ("_metrics", "_lock", "_trace_memory", "_owns_tracing")

    def __init__(self, execution_id: str, *, trace_memory: bool = False) -> None:
        """Initialise the engine.

        Args:
            execution_id: Run identifier.
            trace_memory: Enable :mod:`tracemalloc`. Off by default because
                tracing measurably slows execution, which would distort the very
                timings being measured.
        """
        self._metrics = RunMetrics(
            execution_id=execution_id, rss_bytes_at_start=_rss_bytes()
        )
        self._lock = threading.RLock()
        self._trace_memory = trace_memory
        self._owns_tracing = False
        if trace_memory and not tracemalloc.is_tracing():
            tracemalloc.start()
            self._owns_tracing = True

    @property
    def metrics(self) -> RunMetrics:
        """The metrics collected so far."""
        return self._metrics

    def unit(self, unit_id: str) -> UnitMetrics:
        """Return (creating if needed) the metrics record for a unit.

        Args:
            unit_id: Unit identifier.

        Returns:
            The unit's metrics record.
        """
        with self._lock:
            return self._metrics.units.setdefault(unit_id, UnitMetrics(unit_id=unit_id))

    @contextmanager
    def measure(self, unit_id: str) -> Iterator[UnitMetrics]:
        """Measure a unit's execution.

        Timing is recorded even when the body raises, because a failed unit's cost
        is as interesting as a successful one's -- often more so.

        Args:
            unit_id: Unit identifier.

        Yields:
            The unit's metrics record, for the caller to annotate.
        """
        record = self.unit(unit_id)
        started_wall = time.perf_counter()
        started_cpu = time.process_time()
        started_at = utc_now()
        with self._lock:
            record.attempts += 1
        try:
            yield record
        finally:
            wall = time.perf_counter() - started_wall
            cpu = time.process_time() - started_cpu
            with self._lock:
                record.timing = Timing(
                    wall_seconds=wall,
                    cpu_seconds=cpu,
                    started_at=started_at,
                    finished_at=utc_now(),
                )
                if self._trace_memory and tracemalloc.is_tracing():
                    _, peak = tracemalloc.get_traced_memory()
                    record.peak_traced_memory_bytes = peak

    def record_status(self, unit_id: str, status: ExecutionStatus) -> None:
        """Record a unit's terminal status.

        Args:
            unit_id: Unit identifier.
            status: Terminal status.
        """
        with self._lock:
            self.unit(unit_id).status = status

    def record_counts(
        self,
        unit_id: str,
        *,
        findings: int = 0,
        warnings: int = 0,
        errors: int = 0,
    ) -> None:
        """Add to a unit's counters.

        Args:
            unit_id: Unit identifier.
            findings: Findings to add.
            warnings: Warnings to add.
            errors: Errors to add.
        """
        with self._lock:
            record = self.unit(unit_id)
            record.findings += findings
            record.warnings += warnings
            record.errors += errors

    def finish(self) -> RunMetrics:
        """Close out the run's metrics.

        Stops :mod:`tracemalloc` only if this engine started it, so a caller that
        was already tracing keeps their tracing intact.

        Returns:
            The completed run metrics.
        """
        with self._lock:
            self._metrics.finished_at = utc_now()
            self._metrics.rss_bytes_at_end = _rss_bytes()
            if self._trace_memory and tracemalloc.is_tracing():
                _, peak = tracemalloc.get_traced_memory()
                self._metrics.peak_traced_memory_bytes = peak
            if self._owns_tracing:
                tracemalloc.stop()
                self._owns_tracing = False
        _LOGGER.debug(
            "Run metrics finalised: %d unit(s), %.3fs wall",
            len(self._metrics.units),
            self._metrics.total_wall_seconds or 0.0,
        )
        return self._metrics
