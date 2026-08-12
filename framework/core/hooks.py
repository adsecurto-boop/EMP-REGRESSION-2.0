"""Extension hooks.

Provides before/after hook points around collectors, validators, monitors,
plugins, and reports, so behaviour can be added without editing the components
being extended. Registering a hook requires no change to any existing module,
which is the point (``docs/FRAMEWORK_MANIFEST.md`` §11).

Hooks are **isolated by default**: a hook that raises is logged and recorded, and
the work it wrapped proceeds. An observer must not be able to break the thing it
observes. A hook registered with ``required=True`` inverts this for the cases
where the hook genuinely is a precondition.

Hooks differ from the event bus deliberately. Events are *notifications* --
fire-and-forget, published after the fact. Hooks are *interception points* --
invoked synchronously at a defined boundary, able to signal that work should not
proceed. Using events for interception would make ordering and veto semantics
undefined.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Sequence

from framework.shared.exceptions import HookError
from framework.shared.logger import get_logger

__all__ = ["HookPoint", "HookContext", "HookOutcome", "Hook", "HookRegistry"]

_LOGGER = get_logger(__name__)


class HookPoint(Enum):
    """Points at which hooks may be invoked.

    Each extension point has a symmetric before/after pair so a hook can bracket
    the work (timing it, snapshotting state around it) without needing two
    unrelated registrations.
    """

    BEFORE_COLLECTOR = "before.collector"
    AFTER_COLLECTOR = "after.collector"
    BEFORE_NORMALIZER = "before.normalizer"
    AFTER_NORMALIZER = "after.normalizer"
    BEFORE_VALIDATOR = "before.validator"
    AFTER_VALIDATOR = "after.validator"
    BEFORE_CORRELATOR = "before.correlator"
    AFTER_CORRELATOR = "after.correlator"
    BEFORE_PLUGIN = "before.plugin"
    AFTER_PLUGIN = "after.plugin"
    BEFORE_RUN = "before.run"
    AFTER_RUN = "after.run"

    @property
    def is_before(self) -> bool:
        """Whether this point precedes the work it brackets."""
        return self.value.startswith("before.")

    @property
    def counterpart(self) -> "HookPoint":
        """The matching before/after point.

        Returns:
            The opposite half of this pair.
        """
        prefix, suffix = self.value.split(".", 1)
        target = f"{'after' if prefix == 'before' else 'before'}.{suffix}"
        return HookPoint(target)


@dataclass(frozen=True, slots=True)
class HookContext:
    """Information passed to a hook.

    Args:
        point: The hook point being invoked.
        target: Name of the component or unit the hook brackets.
        execution_id: Run identifier, for correlation.
        payload: Point-specific detail. For ``after`` points this typically
            includes the result or the error that occurred.
    """

    point: HookPoint
    target: str
    execution_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class HookOutcome:
    """The aggregate result of invoking the hooks at one point.

    Args:
        point: The point invoked.
        invoked: Number of hooks invoked.
        errors: Errors raised by non-required hooks, which were isolated.
        veto_reason: Reason a ``before`` hook asked to prevent the work, if any.
    """

    point: HookPoint
    invoked: int = 0
    errors: Sequence[Exception] = field(default_factory=tuple)
    veto_reason: str | None = None

    @property
    def vetoed(self) -> bool:
        """Whether a hook asked that the bracketed work not proceed."""
        return self.veto_reason is not None


HookCallable = Callable[[HookContext], Any]


@dataclass(frozen=True, slots=True)
class Hook:
    """A registered hook.

    Args:
        name: Identifying name, used in logs and error reporting.
        point: Where it is invoked.
        callback: The callable invoked with a :class:`HookContext`. Returning a
            string from a ``before`` hook vetoes the bracketed work, with the
            string as the reason.
        required: When ``True``, a failure propagates as :class:`HookError`
            instead of being isolated.
        priority: Lower values run first. Equal priorities run in registration
            order.
    """

    name: str
    point: HookPoint
    callback: HookCallable
    required: bool = False
    priority: int = 100


class HookRegistry:
    """Holds and invokes hooks.

    Instance-scoped rather than global so hooks registered for one run cannot
    leak into another.
    """

    __slots__ = ("_hooks", "_lock")

    def __init__(self) -> None:
        """Initialise an empty registry."""
        self._hooks: dict[HookPoint, list[Hook]] = {}
        self._lock = threading.RLock()

    def __len__(self) -> int:
        with self._lock:
            return sum(len(items) for items in self._hooks.values())

    def register(
        self,
        point: HookPoint,
        callback: HookCallable,
        *,
        name: str | None = None,
        required: bool = False,
        priority: int = 100,
    ) -> Hook:
        """Register a hook.

        Args:
            point: Where to invoke it.
            callback: Callable receiving a :class:`HookContext`.
            name: Identifying name; derived from the callable when omitted.
            required: Whether a failure should abort the bracketed work.
            priority: Lower runs first.

        Returns:
            The registered hook, for later removal.
        """
        hook = Hook(
            name=name or getattr(callback, "__name__", repr(callback)),
            point=point,
            callback=callback,
            required=required,
            priority=priority,
        )
        with self._lock:
            self._hooks.setdefault(point, []).append(hook)
            self._hooks[point].sort(key=lambda item: item.priority)
        _LOGGER.debug("Hook registered at %s: %s", point.value, hook.name)
        return hook

    def unregister(self, hook: Hook) -> bool:
        """Remove a registered hook.

        Args:
            hook: Hook returned by :meth:`register`.

        Returns:
            ``True`` if it was removed.
        """
        with self._lock:
            try:
                self._hooks.get(hook.point, []).remove(hook)
            except ValueError:
                return False
            return True

    def hooks_at(self, point: HookPoint) -> tuple[Hook, ...]:
        """Return the hooks registered at a point, in invocation order.

        Args:
            point: Point to inspect.

        Returns:
            The registered hooks.
        """
        with self._lock:
            return tuple(self._hooks.get(point, ()))

    def invoke(
        self,
        point: HookPoint,
        target: str,
        *,
        execution_id: str | None = None,
        **payload: Any,
    ) -> HookOutcome:
        """Invoke every hook at a point.

        Args:
            point: Point to invoke.
            target: Name of the component or unit being bracketed.
            execution_id: Run identifier.
            **payload: Point-specific detail passed to each hook.

        Returns:
            The aggregate outcome, including any veto and isolated errors.

        Raises:
            HookError: If a hook registered as ``required`` fails.
        """
        hooks = self.hooks_at(point)
        if not hooks:
            return HookOutcome(point=point)

        context = HookContext(
            point=point, target=target, execution_id=execution_id, payload=payload
        )
        errors: list[Exception] = []
        veto: str | None = None
        for hook in hooks:
            try:
                outcome = hook.callback(context)
            except Exception as exc:  # noqa: BLE001 -- isolation is the default
                if hook.required:
                    raise HookError(
                        "Required hook failed",
                        {"hook": hook.name, "point": point.value, "target": target},
                    ) from exc
                errors.append(exc)
                _LOGGER.error(
                    "Hook %s failed at %s for %s: %s",
                    hook.name,
                    point.value,
                    target,
                    exc,
                    exc_info=True,
                )
                continue
            if point.is_before and isinstance(outcome, str) and outcome:
                veto = outcome
                _LOGGER.info(
                    "Hook %s vetoed %s at %s: %s", hook.name, target, point.value, outcome
                )
                break
        return HookOutcome(
            point=point, invoked=len(hooks), errors=tuple(errors), veto_reason=veto
        )

    def clear(self) -> None:
        """Remove every registered hook."""
        with self._lock:
            self._hooks.clear()
