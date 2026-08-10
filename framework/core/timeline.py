"""Execution timeline.

Builds a complete, ordered record of everything that happened during a run.

The timeline is **event-sourced**: it subscribes to the event bus and records every
event published, rather than components separately telling it what they did. That
single source is deliberate -- Phase 1 kept a parallel narrative list alongside
event history and produced two entries for every moment. Deriving the timeline from
the events that already exist removes that duplication and guarantees the brief's
requirement that *every* framework event appears.

Entries are ordered by occurrence and carry a monotonic sequence number, so events
sharing a timestamp still have a defined order. Clock resolution on Windows is
coarse enough that several events in one run routinely share a timestamp; without
the sequence number their relative order would be unrecoverable.
"""

from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from framework.core.event_bus import Event, EventBus, EventType
from framework.core.reporting import TimelineEntry
from framework.shared.logger import get_logger
from framework.shared.models import utc_now
from framework.shared.utils import datetime_utils

__all__ = ["TimelineRecord", "ExecutionTimeline"]

_LOGGER = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TimelineRecord:
    """One entry in the timeline.

    Args:
        sequence: Monotonic position in the run, breaking timestamp ties.
        occurred_at: When it happened.
        label: Event type value, or a caller-supplied label.
        category: Grouping key derived from the event type's namespace.
        source: Component that published it.
        execution_id: Run identifier.
        detail: Structured detail.
    """

    sequence: int
    occurred_at: Any
    label: str
    category: str
    source: str = ""
    execution_id: str | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "sequence": self.sequence,
            "occurred_at": datetime_utils.format_iso8601(self.occurred_at),
            "label": self.label,
            "category": self.category,
            "source": self.source,
            "detail": dict(self.detail),
        }

    def to_entry(self) -> TimelineEntry:
        """Project into the report's timeline model.

        Returns:
            The report-facing entry.
        """
        return TimelineEntry(
            occurred_at=self.occurred_at,
            label=self.label,
            category=self.category,
            detail={"sequence": self.sequence, "source": self.source, **dict(self.detail)},
        )


class ExecutionTimeline:
    """Records an ordered timeline of a run.

    Attach to an event bus with :meth:`attach` and every published event is
    recorded. Thread-safe, since events may be published from parallel units.
    """

    __slots__ = ("_records", "_lock", "_counter", "_subscription", "_bus")

    def __init__(self) -> None:
        """Initialise an empty timeline."""
        self._records: list[TimelineRecord] = []
        self._lock = threading.RLock()
        self._counter = itertools.count(1)
        self._subscription: Any = None
        self._bus: EventBus | None = None

    def attach(self, bus: EventBus) -> None:
        """Subscribe to every event published on a bus.

        Args:
            bus: Bus to observe. A wildcard subscription is used so that event
                types added later are recorded without changing this module.
        """
        with self._lock:
            if self._subscription is not None and self._bus is bus:
                return
            self._bus = bus
            self._subscription = bus.subscribe(None, self.record_event)
        _LOGGER.debug("Timeline attached to event bus")

    def detach(self) -> bool:
        """Stop observing the bus.

        Returns:
            ``True`` if a subscription was removed.
        """
        with self._lock:
            if self._bus is None or self._subscription is None:
                return False
            removed = self._bus.unsubscribe(self._subscription)
            self._subscription = None
            self._bus = None
            return removed

    def record_event(self, event: Event) -> None:
        """Record a published event.

        Args:
            event: The event to record.
        """
        category = event.event_type.value.split(".", 1)[0]
        self.record(
            label=event.event_type.value,
            category=category,
            source=event.source,
            occurred_at=event.occurred_at,
            execution_id=event.execution_id,
            **dict(event.payload),
        )

    def record(
        self,
        *,
        label: str,
        category: str = "general",
        source: str = "",
        occurred_at: Any = None,
        execution_id: str | None = None,
        **detail: Any,
    ) -> TimelineRecord:
        """Record an entry directly.

        Provided for moments that are not modelled as events. Prefer publishing an
        event where one exists, so the timeline stays a faithful projection of the
        event stream rather than a second, divergent account.

        Args:
            label: Short description.
            category: Grouping key.
            source: Component responsible.
            occurred_at: When it happened; defaults to now.
            execution_id: Run identifier.
            **detail: Structured detail.

        Returns:
            The recorded entry.
        """
        with self._lock:
            record = TimelineRecord(
                sequence=next(self._counter),
                occurred_at=occurred_at or utc_now(),
                label=label,
                category=category,
                source=source,
                execution_id=execution_id,
                detail=detail,
            )
            self._records.append(record)
            return record

    def records(self) -> tuple[TimelineRecord, ...]:
        """Return every entry, ordered by time then sequence.

        Returns:
            The ordered entries.
        """
        with self._lock:
            return tuple(
                sorted(self._records, key=lambda item: (item.occurred_at, item.sequence))
            )

    def entries(self) -> tuple[TimelineEntry, ...]:
        """Return the timeline as report-facing entries.

        Returns:
            The ordered report entries.
        """
        return tuple(record.to_entry() for record in self.records())

    def of_category(self, category: str) -> tuple[TimelineRecord, ...]:
        """Return entries in one category.

        Args:
            category: Category to filter by.

        Returns:
            Matching entries, in order.
        """
        return tuple(item for item in self.records() if item.category == category)

    def of_type(self, event_type: EventType) -> tuple[TimelineRecord, ...]:
        """Return entries recorded from one event type.

        Args:
            event_type: Event type to filter by.

        Returns:
            Matching entries, in order.
        """
        return tuple(item for item in self.records() if item.label == event_type.value)

    def categories(self) -> tuple[str, ...]:
        """Return the distinct categories present, sorted."""
        return tuple(sorted({item.category for item in self.records()}))

    def span_seconds(self) -> float | None:
        """Return the elapsed time between the first and last entry.

        Returns:
            Seconds spanned, or ``None`` with fewer than two entries.
        """
        ordered = self.records()
        if len(ordered) < 2:
            return None
        return (ordered[-1].occurred_at - ordered[0].occurred_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation of the whole timeline.

        Returns:
            A serialisable mapping, suitable for a future visualisation to consume.
        """
        ordered = self.records()
        return {
            "entry_count": len(ordered),
            "span_seconds": self.span_seconds(),
            "categories": list(self.categories()),
            "entries": [record.to_dict() for record in ordered],
        }

    def render_text(self, *, limit: int | None = None) -> str:
        """Render the timeline as aligned plain text.

        Args:
            limit: Maximum entries to render, most recent first when exceeded.

        Returns:
            A human-readable timeline.
        """
        ordered = self.records()
        selected = ordered[-limit:] if limit is not None else ordered
        if not selected:
            return "(timeline empty)"
        start = selected[0].occurred_at
        lines = []
        for record in selected:
            offset = (record.occurred_at - start).total_seconds()
            lines.append(
                f"[{offset:8.3f}s] {record.category:<10} {record.label:<28} "
                f"{record.source}"
            )
        return "\n".join(lines)

    def clear(self) -> None:
        """Remove every entry."""
        with self._lock:
            self._records.clear()
