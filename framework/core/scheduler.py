"""Scheduling contract and engine.

The vocabulary (:class:`ScheduleKind`, :class:`ScheduleSpec`) defines *what* a
schedule is; :class:`SchedulerEngine` decides *when* an entry is due. The abstract
interface is :class:`framework.shared.interfaces.Scheduler`, which lives in
``shared`` so monitors and validators can reference it without importing ``core``.

One :class:`ScheduleSpec` type covers every kind, so adding a mechanism never
changes the :meth:`~framework.shared.interfaces.Scheduler.schedule` signature.

**The engine decides due-ness; it does not run anything.** It owns no threads and
no timers: a caller asks what is due and executes it. Keeping the clock and the
worker separate makes scheduling deterministically testable (inject a clock, assert
what fires) and leaves execution policy to the execution engine, which already owns
concurrency, timeouts, and cancellation. A scheduler that spawned its own threads
would duplicate that and compete with it.

No EmpMonitor task is scheduled here -- only the infrastructure exists.
"""

from __future__ import annotations

import itertools
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Iterable, Iterator, Mapping

from framework.shared.exceptions import SchedulerError
from framework.shared.interfaces import Scheduler
from framework.shared.logger import get_logger
from framework.shared.models import utc_now

__all__ = [
    "ScheduleKind",
    "ScheduleSpec",
    "CronExpression",
    "ScheduleEntry",
    "SchedulerEngine",
]

_LOGGER = get_logger(__name__)


class ScheduleKind(Enum):
    """Scheduling mechanisms the contract must accommodate."""

    ONCE = "once"
    """Run a single time, immediately or at :attr:`ScheduleSpec.run_at`."""

    INTERVAL = "interval"
    """Run repeatedly, separated by :attr:`ScheduleSpec.interval`."""

    CRON = "cron"
    """Run on a cron expression given in :attr:`ScheduleSpec.expression`."""

    EVENT = "event"
    """Run when the event named in :attr:`ScheduleSpec.expression` is published
    on the event bus."""

    CONTINUOUS = "continuous"
    """Run continuously for the duration of a monitoring session."""


@dataclass(frozen=True, slots=True)
class ScheduleSpec:
    """A schedule specification.

    One type covers every :class:`ScheduleKind`; which fields are meaningful
    depends on ``kind``, and :meth:`validate` enforces that. Modelling all kinds
    in one immutable value keeps the scheduler interface stable as mechanisms are
    added.

    Args:
        kind: Scheduling mechanism.
        run_at: Absolute time for :attr:`ScheduleKind.ONCE`.
        interval: Period for :attr:`ScheduleKind.INTERVAL`.
        expression: Cron expression or event name, per ``kind``.
        max_runs: Optional cap on repetitions.
        jitter: Optional random spread applied to repeated runs, to avoid many
            units firing simultaneously.
        metadata: Implementation-specific detail.
    """

    kind: ScheduleKind
    run_at: datetime | None = None
    interval: timedelta | None = None
    expression: str | None = None
    max_runs: int | None = None
    jitter: timedelta | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the specification on construction.

        Raises:
            SchedulerError: If the specification is inconsistent with its kind.
        """
        self.validate()

    def validate(self) -> None:
        """Check that the fields required by :attr:`kind` are present.

        Validating here rather than inside a scheduler implementation means an
        unusable schedule is rejected at configuration time, not at fire time.

        Raises:
            SchedulerError: If a required field is missing or a value is invalid.
        """
        if self.kind is ScheduleKind.INTERVAL:
            if self.interval is None or self.interval.total_seconds() <= 0:
                raise SchedulerError(
                    "An interval schedule requires a positive interval",
                    {"interval": str(self.interval)},
                )
        if self.kind in (ScheduleKind.CRON, ScheduleKind.EVENT) and not self.expression:
            raise SchedulerError(
                "This schedule kind requires an expression",
                {"kind": self.kind.value},
            )
        if self.max_runs is not None and self.max_runs < 1:
            raise SchedulerError(
                "max_runs must be at least 1", {"max_runs": self.max_runs}
            )
        if self.jitter is not None and self.jitter.total_seconds() < 0:
            raise SchedulerError("jitter must not be negative")

    @property
    def is_recurring(self) -> bool:
        """Whether this schedule fires more than once."""
        return self.kind in (
            ScheduleKind.INTERVAL,
            ScheduleKind.CRON,
            ScheduleKind.EVENT,
            ScheduleKind.CONTINUOUS,
        )

    @classmethod
    def once(cls, *, run_at: datetime | None = None) -> "ScheduleSpec":
        """Build a one-shot schedule.

        Args:
            run_at: When to run; immediately when omitted.

        Returns:
            The specification.
        """
        return cls(kind=ScheduleKind.ONCE, run_at=run_at or utc_now())

    @classmethod
    def every(cls, interval: timedelta, *, max_runs: int | None = None) -> "ScheduleSpec":
        """Build a fixed-interval schedule.

        Args:
            interval: Period between runs.
            max_runs: Optional repetition cap.

        Returns:
            The specification.
        """
        return cls(kind=ScheduleKind.INTERVAL, interval=interval, max_runs=max_runs)

    @classmethod
    def on_event(cls, event_name: str) -> "ScheduleSpec":
        """Build an event-triggered schedule.

        Args:
            event_name: Event that triggers execution.

        Returns:
            The specification.
        """
        return cls(kind=ScheduleKind.EVENT, expression=event_name)

    @classmethod
    def cron(cls, expression: str) -> "ScheduleSpec":
        """Build a cron schedule.

        Args:
            expression: Standard five-field cron expression. Validated by
                :class:`CronExpression` when the entry is registered.

        Returns:
            The specification.
        """
        return cls(kind=ScheduleKind.CRON, expression=expression)

    @classmethod
    def continuous(cls) -> "ScheduleSpec":
        """Build a continuous-monitoring schedule.

        Returns:
            The specification.
        """
        return cls(kind=ScheduleKind.CONTINUOUS)


_FIELD_BOUNDS: tuple[tuple[str, int, int], ...] = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day", 1, 31),
    ("month", 1, 12),
    ("weekday", 0, 6),
)
_STEP_RE = re.compile(r"^(?P<range>[^/]+)(?:/(?P<step>\d+))?$")


class CronExpression:
    """A parsed five-field cron expression.

    Fields are ``minute hour day-of-month month day-of-week``, supporting ``*``,
    single values, ``a-b`` ranges, ``a,b,c`` lists, and ``*/n`` or ``a-b/n`` steps.
    Sunday is ``0``; ``7`` is accepted as an alias for Sunday.

    Unsupported deliberately: ``L``, ``W``, ``#``, ``?``, named months and weekdays,
    and seconds fields. These are non-standard extensions with inconsistent
    semantics between implementations, and accepting one silently would mean a
    schedule that fires at a different time than its author intended. They raise
    rather than being ignored.

    Day-of-month and day-of-week follow the standard's union rule: when both are
    restricted, a match on *either* fires.
    """

    __slots__ = ("_fields", "_raw", "_day_restricted", "_weekday_restricted")

    def __init__(self, expression: str) -> None:
        """Parse a cron expression.

        Args:
            expression: The expression to parse.

        Raises:
            SchedulerError: If the expression is malformed or uses unsupported
                syntax.
        """
        raw = (expression or "").strip()
        parts = raw.split()
        if len(parts) != 5:
            raise SchedulerError(
                "A cron expression must have exactly five fields "
                "(minute hour day month weekday)",
                {"expression": expression, "fields": len(parts)},
            )
        self._raw = raw
        self._fields: list[frozenset[int]] = []
        for part, (name, low, high) in zip(parts, _FIELD_BOUNDS, strict=True):
            self._fields.append(self._parse_field(part, name, low, high))
        self._day_restricted = parts[2] != "*"
        self._weekday_restricted = parts[4] != "*"

    @staticmethod
    def _parse_field(part: str, name: str, low: int, high: int) -> frozenset[int]:
        """Parse one cron field into the set of values it matches.

        Args:
            part: Field text.
            name: Field name, for error messages.
            low: Lowest legal value.
            high: Highest legal value.

        Returns:
            The matching values.

        Raises:
            SchedulerError: If the field is malformed or unsupported.
        """
        if any(char in part for char in "LW#?"):
            raise SchedulerError(
                "Unsupported cron syntax; L, W, # and ? are not implemented",
                {"field": name, "value": part},
            )
        values: set[int] = set()
        for chunk in part.split(","):
            match = _STEP_RE.match(chunk.strip())
            if not match:
                raise SchedulerError(
                    "Malformed cron field", {"field": name, "value": chunk}
                )
            body = match.group("range").strip()
            step = int(match.group("step") or 1)
            if step < 1:
                raise SchedulerError(
                    "Cron step must be positive", {"field": name, "value": chunk}
                )
            if body == "*":
                start, end = low, high
            elif "-" in body:
                start_text, _, end_text = body.partition("-")
                start, end = (
                    CronExpression._parse_int(start_text, name, low, high),
                    CronExpression._parse_int(end_text, name, low, high),
                )
                if start > end:
                    raise SchedulerError(
                        "Cron range start exceeds its end",
                        {"field": name, "value": body},
                    )
            else:
                start = end = CronExpression._parse_int(body, name, low, high)
            values.update(range(start, end + 1, step))
        if not values:
            raise SchedulerError(
                "Cron field matches no values", {"field": name, "value": part}
            )
        return frozenset(values)

    @staticmethod
    def _parse_int(text: str, name: str, low: int, high: int) -> int:
        """Parse and bounds-check a single cron value.

        Args:
            text: Value text.
            name: Field name, for error messages.
            low: Lowest legal value.
            high: Highest legal value.

        Returns:
            The parsed value, with weekday ``7`` normalised to ``0``.

        Raises:
            SchedulerError: If the value is not an integer in range.
        """
        try:
            value = int(text.strip())
        except (TypeError, ValueError) as exc:
            raise SchedulerError(
                "Cron field value is not an integer; names are not supported",
                {"field": name, "value": text},
            ) from exc
        if name == "weekday" and value == 7:
            return 0
        if not low <= value <= high:
            raise SchedulerError(
                "Cron field value out of range",
                {"field": name, "value": value, "min": low, "max": high},
            )
        return value

    @property
    def expression(self) -> str:
        """The original expression text."""
        return self._raw

    def matches(self, moment: datetime) -> bool:
        """Whether a moment matches this expression.

        Args:
            moment: The time to test, to minute precision.

        Returns:
            ``True`` if the expression fires at that minute.
        """
        minute, hour, day, month, weekday = self._fields
        if moment.minute not in minute or moment.hour not in hour:
            return False
        if moment.month not in month:
            return False
        # Python's weekday() is Monday=0; cron uses Sunday=0.
        cron_weekday = (moment.weekday() + 1) % 7
        day_ok = moment.day in day
        weekday_ok = cron_weekday in weekday
        if self._day_restricted and self._weekday_restricted:
            return day_ok or weekday_ok
        return day_ok and weekday_ok

    def next_after(self, moment: datetime, *, horizon_days: int = 366) -> datetime | None:
        """Return the next firing time strictly after a moment.

        Searches minute by minute, bounded by ``horizon_days`` so an expression that
        can never fire (for example 31 February) terminates instead of looping.

        Args:
            moment: The time to search after.
            horizon_days: How far ahead to search.

        Returns:
            The next firing time, or ``None`` if none within the horizon.
        """
        candidate = (moment + timedelta(minutes=1)).replace(second=0, microsecond=0)
        limit = moment + timedelta(days=horizon_days)
        while candidate <= limit:
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)
        return None


@dataclass(slots=True)
class ScheduleEntry:
    """A registered schedule.

    Mutable because an entry accumulates fire counts and advances its next-due time
    as the schedule progresses.

    Args:
        handle: Identifier returned by :meth:`SchedulerEngine.schedule`.
        unit_id: The unit to run when this entry fires.
        spec: The schedule specification.
        next_due: When it next fires, or ``None`` when exhausted.
        run_count: How many times it has fired.
        cancelled: Whether it has been cancelled.
        cron: Parsed cron expression, for cron entries.
        last_fired_at: When it last fired.
    """

    handle: str
    unit_id: str
    spec: ScheduleSpec
    next_due: datetime | None = None
    run_count: int = 0
    cancelled: bool = False
    cron: CronExpression | None = None
    last_fired_at: datetime | None = None

    @property
    def is_exhausted(self) -> bool:
        """Whether the entry has reached its run limit."""
        return self.spec.max_runs is not None and self.run_count >= self.spec.max_runs

    @property
    def is_active(self) -> bool:
        """Whether the entry can still fire."""
        return not self.cancelled and not self.is_exhausted and self.next_due is not None


class SchedulerEngine(Scheduler):
    """Decides when registered entries are due.

    Implements :class:`framework.shared.interfaces.Scheduler`. The clock is injected
    so behaviour is deterministic under test: a fake clock makes "what fires in the
    next hour" an assertion rather than a wait.

    Event-driven entries become due when :meth:`notify_event` is called with their
    event name, which lets the event bus drive scheduling without this module
    subscribing to it and inverting the dependency.
    """

    __slots__ = ("_entries", "_lock", "_clock", "_counter", "_pending_events")

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        """Initialise an empty scheduler.

        Args:
            clock: Callable returning the current time; defaults to UTC now.
        """
        self._entries: dict[str, ScheduleEntry] = {}
        self._lock = threading.RLock()
        self._clock = clock or utc_now
        self._counter = itertools.count(1)
        self._pending_events: set[str] = set()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    @property
    def entries(self) -> tuple[ScheduleEntry, ...]:
        """Every registered entry, ordered by handle."""
        with self._lock:
            return tuple(self._entries[key] for key in sorted(self._entries))

    def schedule(self, unit_id: str, spec: Any) -> str:
        """Register a unit to run on a schedule.

        Args:
            unit_id: Unit to run.
            spec: A :class:`ScheduleSpec`.

        Returns:
            A handle identifying the entry.

        Raises:
            SchedulerError: If ``spec`` is not a :class:`ScheduleSpec`, or a cron
                expression is invalid.
        """
        if not isinstance(spec, ScheduleSpec):
            raise SchedulerError(
                "schedule() requires a ScheduleSpec",
                {"unit_id": unit_id, "received": type(spec).__name__},
            )
        now = self._clock()
        cron = CronExpression(spec.expression or "") if spec.kind is ScheduleKind.CRON else None
        with self._lock:
            handle = f"sched-{next(self._counter):04d}"
            entry = ScheduleEntry(
                handle=handle,
                unit_id=unit_id,
                spec=spec,
                cron=cron,
                next_due=self._initial_due(spec, cron, now),
            )
            self._entries[handle] = entry
        _LOGGER.debug(
            "Scheduled %s as %s (%s), next due %s",
            unit_id,
            handle,
            spec.kind.value,
            entry.next_due,
        )
        return handle

    def _initial_due(
        self, spec: ScheduleSpec, cron: CronExpression | None, now: datetime
    ) -> datetime | None:
        """Compute an entry's first due time.

        Args:
            spec: The specification.
            cron: Parsed cron expression, for cron entries.
            now: Current time.

        Returns:
            The first due time, or ``None`` for event-driven entries, which become
            due only on notification.
        """
        if spec.kind is ScheduleKind.ONCE:
            return spec.run_at or now
        if spec.kind is ScheduleKind.INTERVAL:
            return now + (spec.interval or timedelta(0))
        if spec.kind is ScheduleKind.CONTINUOUS:
            return now
        if spec.kind is ScheduleKind.CRON and cron is not None:
            return cron.next_after(now)
        return None

    def cancel(self, handle: str) -> bool:
        """Cancel an entry.

        Args:
            handle: Handle returned by :meth:`schedule`.

        Returns:
            ``True`` if an active entry was cancelled.
        """
        with self._lock:
            entry = self._entries.get(handle)
            if entry is None or entry.cancelled:
                return False
            entry.cancelled = True
            entry.next_due = None
            return True

    def notify_event(self, event_name: str) -> tuple[str, ...]:
        """Mark event-driven entries for the named event as due.

        Args:
            event_name: The event that occurred.

        Returns:
            Handles of entries made due, sorted.
        """
        now = self._clock()
        triggered: list[str] = []
        with self._lock:
            self._pending_events.add(event_name)
            for entry in self._entries.values():
                if (
                    entry.spec.kind is ScheduleKind.EVENT
                    and entry.spec.expression == event_name
                    and not entry.cancelled
                    and not entry.is_exhausted
                ):
                    entry.next_due = now
                    triggered.append(entry.handle)
        return tuple(sorted(triggered))

    def due(self) -> Iterable[str]:
        """Return the handles of entries currently due.

        Returns:
            Due handles, sorted by their due time so the longest-waiting fires
            first.
        """
        now = self._clock()
        with self._lock:
            ready = [
                entry
                for entry in self._entries.values()
                if entry.is_active and entry.next_due is not None and entry.next_due <= now
            ]
        return tuple(
            entry.handle
            for entry in sorted(ready, key=lambda item: (item.next_due, item.handle))
        )

    def due_entries(self) -> tuple[ScheduleEntry, ...]:
        """Return the entries currently due.

        Returns:
            The due entries, in fire order.
        """
        handles = set(self.due())
        return tuple(entry for entry in self.entries if entry.handle in handles)

    def mark_fired(self, handle: str) -> ScheduleEntry:
        """Record that an entry fired and advance its schedule.

        Called by whatever executes the due work, so the engine never has to know
        how or whether execution succeeded -- only that the slot was consumed.

        Args:
            handle: Handle that fired.

        Returns:
            The updated entry.

        Raises:
            SchedulerError: If the handle is unknown.
        """
        now = self._clock()
        with self._lock:
            entry = self._entries.get(handle)
            if entry is None:
                raise SchedulerError("Unknown schedule handle", {"handle": handle})
            entry.run_count += 1
            entry.last_fired_at = now
            entry.next_due = self._advance(entry, now)
            if entry.next_due is None and entry.is_exhausted:
                _LOGGER.debug(
                    "Schedule %s exhausted after %d run(s)", handle, entry.run_count
                )
            return entry

    def _advance(self, entry: ScheduleEntry, now: datetime) -> datetime | None:
        """Compute an entry's next due time after firing.

        Args:
            entry: The entry that fired.
            now: Current time.

        Returns:
            The next due time, or ``None`` if the entry will not fire again.
        """
        if entry.is_exhausted:
            return None
        kind = entry.spec.kind
        if kind is ScheduleKind.ONCE:
            return None
        if kind is ScheduleKind.INTERVAL:
            base = now + (entry.spec.interval or timedelta(0))
            return base + (entry.spec.jitter or timedelta(0))
        if kind is ScheduleKind.CONTINUOUS:
            return now
        if kind is ScheduleKind.CRON and entry.cron is not None:
            return entry.cron.next_after(now)
        if kind is ScheduleKind.EVENT:
            # Event entries go dormant until the next notification.
            return None
        return None

    def next_due_at(self) -> datetime | None:
        """Return the earliest due time across all active entries.

        Lets a caller sleep until there is work instead of polling.

        Returns:
            The earliest due time, or ``None`` if nothing is scheduled.
        """
        with self._lock:
            times = [
                entry.next_due
                for entry in self._entries.values()
                if entry.is_active and entry.next_due is not None
            ]
        return min(times) if times else None

    def upcoming(self, count: int = 5) -> tuple[tuple[str, datetime], ...]:
        """Return the next entries due, for inspection and reporting.

        Args:
            count: Maximum entries to return.

        Returns:
            Handle and due-time pairs, earliest first.
        """
        with self._lock:
            pairs = [
                (entry.handle, entry.next_due)
                for entry in self._entries.values()
                if entry.is_active and entry.next_due is not None
            ]
        return tuple(sorted(pairs, key=lambda item: (item[1], item[0]))[:count])

    def clear(self) -> None:
        """Remove every entry."""
        with self._lock:
            self._entries.clear()
            self._pending_events.clear()
