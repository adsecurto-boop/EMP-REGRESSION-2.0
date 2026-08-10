"""The environment gate.

The sprint brief requires that when the environment pre-check fails, later plugins
are *skipped or blocked* rather than run. This module implements that.

**Why a hook rather than a dependency.** Declaring
``depends_on=("EM000_EnvironmentValidator",)`` is necessary but not sufficient. The
execution graph blocks dependents when a unit *fails to execute*, but EM000 executing
correctly and concluding "the environment is broken" is a **successful** run producing
a negative result -- so the graph would let dependents proceed. Dependency ordering
answers "did it run?"; the gate answers "what did it conclude?".

Both are used together: the dependency guarantees EM000 runs first, and the gate
consults its verdict.

**Zero framework change.** This uses the ``BEFORE_PLUGIN`` hook veto already provided
by :mod:`framework.core.hooks`: a ``before`` hook that returns a string prevents the
bracketed work, and the lifecycle records the unit as ``SKIPPED`` with that reason.
A skipped unit's verdict is ``INCONCLUSIVE``, so a gated run can never read as a
pass -- which is the honest outcome when the environment was never fit to test.
"""

from __future__ import annotations

from typing import Iterable

from framework.core.event_bus import EventBus, EventType
from framework.core.hooks import HookContext, HookPoint, HookRegistry
from framework.shared.logger import get_logger
from framework.shared.models import Verdict

__all__ = ["EnvironmentGate", "register_environment_gate"]

_LOGGER = get_logger(__name__)

#: Verdicts from the pre-check that must stop the rest of the run.
BLOCKING_VERDICTS = frozenset({Verdict.FAILED.value, Verdict.BLOCKED.value})


class EnvironmentGate:
    """Prevents later plugins running when the environment pre-check is negative.

    Args:
        gate_plugin_id: The pre-check plugin whose verdict gates the run.
        blocking_verdicts: Verdict values that stop the run.
        exempt: Plugin identifiers that run regardless of the gate.
    """

    __slots__ = ("_gate_plugin_id", "_blocking", "_exempt", "_verdict", "_observed")

    def __init__(
        self,
        gate_plugin_id: str,
        *,
        blocking_verdicts: Iterable[str] = BLOCKING_VERDICTS,
        exempt: Iterable[str] = (),
    ) -> None:
        """Initialise the gate.

        Args:
            gate_plugin_id: The pre-check plugin identifier.
            blocking_verdicts: Verdict values that stop the run.
            exempt: Plugin identifiers exempt from gating.
        """
        self._gate_plugin_id = gate_plugin_id
        self._blocking = frozenset(blocking_verdicts)
        self._exempt = frozenset(exempt) | {gate_plugin_id}
        self._verdict: str | None = None
        self._observed = False

    @property
    def verdict(self) -> str | None:
        """The pre-check's verdict, once observed."""
        return self._verdict

    @property
    def is_closed(self) -> bool:
        """Whether the gate is currently stopping other plugins."""
        return self._verdict in self._blocking

    def record_verdict(self, event) -> None:  # noqa: ANN001 -- bus delivers Event
        """Record the pre-check's verdict from a plugin-completed event.

        Args:
            event: The published event. Ignored unless it concerns the gate plugin.
        """
        payload = event.payload or {}
        if payload.get("plugin_id") != self._gate_plugin_id:
            return
        verdict = payload.get("verdict")
        if verdict is None:
            return
        self._verdict = str(verdict)
        self._observed = True
        if self.is_closed:
            _LOGGER.warning(
                "Environment gate closed: %s reported %s; later plugins will be skipped",
                self._gate_plugin_id,
                self._verdict,
            )

    def veto(self, context: HookContext) -> str | None:
        """Veto a plugin when the gate is closed.

        Args:
            context: Hook context naming the plugin about to run.

        Returns:
            A reason string to skip the plugin, or ``None`` to let it proceed.
        """
        if context.target in self._exempt:
            return None
        if not self._observed:
            # The pre-check has not reported yet. Do not veto: ordering is the
            # dependency graph's job, and vetoing on an unobserved verdict would
            # skip plugins for a gate that never actually closed.
            return None
        if not self.is_closed:
            return None
        return (
            f"environment pre-check {self._gate_plugin_id} reported {self._verdict}; "
            "the machine is not prepared for regression execution"
        )

    def register(self, hooks: HookRegistry, event_bus: EventBus) -> None:
        """Wire the gate into a run.

        Args:
            hooks: Registry to register the veto with.
            event_bus: Bus to observe plugin completion on.
        """
        event_bus.subscribe(EventType.PLUGIN_COMPLETED, self.record_verdict)
        event_bus.subscribe(EventType.PLUGIN_FAILED, self._record_failure)
        hooks.register(
            HookPoint.BEFORE_PLUGIN,
            self.veto,
            name="environment_gate",
            priority=10,
        )
        _LOGGER.debug("Environment gate registered for %s", self._gate_plugin_id)

    def _record_failure(self, event) -> None:  # noqa: ANN001 -- bus delivers Event
        """Close the gate when the pre-check itself fails to execute.

        A pre-check that crashed has established nothing about the environment, so
        the rest of the run cannot be trusted either.

        Args:
            event: The published event.
        """
        if (event.payload or {}).get("plugin_id") != self._gate_plugin_id:
            return
        self._verdict = Verdict.BLOCKED.value
        self._observed = True
        _LOGGER.warning(
            "Environment gate closed: %s did not complete, so the environment is unverified",
            self._gate_plugin_id,
        )


def register_environment_gate(
    hooks: HookRegistry,
    event_bus: EventBus,
    *,
    gate_plugin_id: str = "EM000_EnvironmentValidator",
    exempt: Iterable[str] = (),
) -> EnvironmentGate:
    """Create and register an environment gate.

    Args:
        hooks: Hook registry for the run.
        event_bus: Event bus for the run.
        gate_plugin_id: The pre-check plugin identifier.
        exempt: Plugin identifiers exempt from gating.

    Returns:
        The registered gate, so a caller can inspect its verdict afterwards.
    """
    gate = EnvironmentGate(gate_plugin_id, exempt=exempt)
    gate.register(hooks, event_bus)
    return gate
