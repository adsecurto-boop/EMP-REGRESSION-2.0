"""In-process publish/subscribe event bus.

Decouples components that must react to each other without importing each other
-- a monitor reports an observed anomaly, and reporting or logging reacts,
without either knowing the other exists
(``docs/ADS/error_handling_standard.md`` §5).

Two deliberate design choices:

* **A subscriber exception never propagates to the publisher.** A logging
  subscriber that throws must not abort the monitor that published. Errors are
  logged and collected instead, so they are never silent but also never
  cascading.
* **Delivery is synchronous and ordered.** Evidence timing matters; an
  asynchronous bus would make event ordering non-deterministic and therefore
  unusable as a correlation aid.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from framework.shared.logger import get_logger
from framework.shared.models import utc_now

__all__ = ["EventType", "Event", "EventBus", "Subscription"]

_LOGGER = get_logger(__name__)


class EventType(Enum):
    """Event kinds the framework publishes.

    Grouped by the lifecycle stage they belong to. Values are strings so they
    serialise directly into reports and logs.
    """

    # Execution lifecycle
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"

    # Plugin lifecycle
    PLUGIN_REGISTERED = "plugin.registered"
    PLUGIN_STARTED = "plugin.started"
    PLUGIN_COMPLETED = "plugin.completed"
    PLUGIN_FAILED = "plugin.failed"
    PLUGIN_SKIPPED = "plugin.skipped"
    PLUGIN_TIMED_OUT = "plugin.timed_out"
    PLUGIN_CANCELLED = "plugin.cancelled"
    PLUGIN_RETRYING = "plugin.retrying"

    # Lifecycle stages. One event per stage entry and exit, so the timeline
    # records progress through the lifecycle, not just its outcome.
    STAGE_STARTED = "stage.started"
    STAGE_COMPLETED = "stage.completed"
    STAGE_FAILED = "stage.failed"

    # Evidence and validation
    EVIDENCE_COLLECTED = "evidence.collected"
    VALIDATION_STARTED = "validation.started"
    VALIDATION_COMPLETED = "validation.completed"
    FINDING_RAISED = "finding.raised"

    # Monitoring
    MONITOR_STARTED = "monitor.started"
    MONITOR_SAMPLED = "monitor.sampled"
    MONITOR_STOPPED = "monitor.stopped"
    ANOMALY_OBSERVED = "monitor.anomaly"

    # Reporting
    REPORT_STARTED = "report.started"
    REPORT_COMPLETED = "report.completed"

    # Scheduling
    SCHEDULE_REGISTERED = "schedule.registered"
    SCHEDULE_FIRED = "schedule.fired"
    SCHEDULE_CANCELLED = "schedule.cancelled"
    SCHEDULE_EXHAUSTED = "schedule.exhausted"

    # Artifacts
    ARTIFACT_STORED = "artifact.stored"


@dataclass(frozen=True, slots=True)
class Event:
    """A published event.

    Args:
        event_type: What happened.
        source: Component that published it.
        payload: Structured detail. Must not contain secrets.
        execution_id: Run the event belongs to, for correlation.
        occurred_at: Publication timestamp.
    """

    event_type: EventType
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)
    execution_id: str | None = None
    occurred_at: Any = field(default_factory=utc_now)


Handler = Callable[[Event], None]


@dataclass(frozen=True, slots=True)
class Subscription:
    """A handle for removing a subscription.

    Args:
        event_type: Subscribed event type, or ``None`` for all events.
        handler: The subscribed callable.
    """

    event_type: EventType | None
    handler: Handler


class EventBus:
    """Synchronous in-process event bus.

    Instance-scoped rather than global: one bus belongs to one run, so events
    from concurrent runs cannot bleed into each other.
    """

    __slots__ = ("_handlers", "_wildcard", "_lock", "_history", "_keep_history")

    def __init__(self, *, keep_history: bool = False) -> None:
        """Initialise an empty bus.

        Args:
            keep_history: Retain published events in memory. Useful for tests and
                for building a run timeline; off by default so long runs do not
                accumulate unbounded history.
        """
        self._handlers: dict[EventType, list[Handler]] = {}
        self._wildcard: list[Handler] = []
        self._lock = threading.RLock()
        self._history: list[Event] = []
        self._keep_history = keep_history

    def subscribe(self, event_type: EventType | None, handler: Handler) -> Subscription:
        """Register a handler.

        Args:
            event_type: Event type to listen for, or ``None`` for every event.
            handler: Callable invoked with the event.

        Returns:
            A subscription handle for :meth:`unsubscribe`.
        """
        with self._lock:
            if event_type is None:
                self._wildcard.append(handler)
            else:
                self._handlers.setdefault(event_type, []).append(handler)
        return Subscription(event_type=event_type, handler=handler)

    def unsubscribe(self, subscription: Subscription) -> bool:
        """Remove a previously registered handler.

        Args:
            subscription: Handle returned by :meth:`subscribe`.

        Returns:
            ``True`` if a handler was removed.
        """
        with self._lock:
            target = (
                self._wildcard
                if subscription.event_type is None
                else self._handlers.get(subscription.event_type, [])
            )
            try:
                target.remove(subscription.handler)
            except ValueError:
                return False
            return True

    def publish(self, event: Event) -> list[Exception]:
        """Deliver an event to all matching handlers.

        Handlers are invoked in registration order: specific handlers first,
        then wildcard handlers.

        Args:
            event: Event to publish.

        Returns:
            Exceptions raised by handlers. Empty when all handlers succeeded.
            Returned rather than raised so one bad subscriber cannot break the
            publisher, while still surfacing the failure to the caller.
        """
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, ())) + list(self._wildcard)
            if self._keep_history:
                self._history.append(event)

        errors: list[Exception] = []
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001 -- isolation is the point
                errors.append(exc)
                _LOGGER.error(
                    "Event handler failed for %s: %s",
                    event.event_type.value,
                    exc,
                    exc_info=True,
                )
        return errors

    def emit(
        self,
        event_type: EventType,
        source: str,
        *,
        execution_id: str | None = None,
        **payload: Any,
    ) -> list[Exception]:
        """Construct and publish an event in one call.

        Args:
            event_type: What happened.
            source: Publishing component.
            execution_id: Run identifier.
            **payload: Structured detail.

        Returns:
            Exceptions raised by handlers, as per :meth:`publish`.
        """
        return self.publish(
            Event(
                event_type=event_type,
                source=source,
                payload=payload,
                execution_id=execution_id,
            )
        )

    @property
    def history(self) -> tuple[Event, ...]:
        """Published events, when history retention is enabled."""
        with self._lock:
            return tuple(self._history)

    def clear(self) -> None:
        """Remove all handlers and history."""
        with self._lock:
            self._handlers.clear()
            self._wildcard.clear()
            self._history.clear()
