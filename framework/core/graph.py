"""Execution graph.

Represents a run as a directed acyclic graph of units, which is what makes
partial execution, failure propagation, and resume expressible rather than ad hoc.

Capabilities:

* **Failure propagation** -- when a unit fails, units that *require* it are blocked
  rather than run. Running a dependent whose prerequisite failed produces a
  meaningless result, and reporting that result as a failure would misattribute the
  fault.
* **Partial execution** -- a subgraph can be executed, with its prerequisites
  included automatically.
* **Resume** -- a graph can be seeded with units already completed in a previous
  run, so only outstanding work executes.
* **Visualization** -- renders to text, Mermaid, and DOT, with no rendering
  dependency.

Ordering comes from :mod:`framework.core.dependencies`; this module does not
implement its own sort.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from framework.core.dependencies import DependencyResolver, ResolutionResult
from framework.shared.exceptions import ExecutionError
from framework.shared.logger import get_logger
from framework.shared.models import ExecutionStatus, PluginMetadata

__all__ = ["NodeState", "GraphNode", "ExecutionGraph"]

_LOGGER = get_logger(__name__)


class NodeState(Enum):
    """State of a unit within the graph."""

    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """Whether the node will not transition again."""
        return self in (
            NodeState.SUCCEEDED,
            NodeState.FAILED,
            NodeState.BLOCKED,
            NodeState.SKIPPED,
            NodeState.CANCELLED,
        )

    @property
    def is_success(self) -> bool:
        """Whether the node completed successfully.

        Skipped counts as success for *dependency* purposes: a skipped unit did not
        fail, so a dependent is not blocked by it. Whether skipping was appropriate
        is a reporting question, not a scheduling one.
        """
        return self in (NodeState.SUCCEEDED, NodeState.SKIPPED)

    @classmethod
    def from_execution_status(cls, status: ExecutionStatus) -> "NodeState":
        """Map an execution status onto a node state.

        Args:
            status: Terminal execution status.

        Returns:
            The corresponding node state.
        """
        return {
            ExecutionStatus.PENDING: cls.PENDING,
            ExecutionStatus.RUNNING: cls.RUNNING,
            ExecutionStatus.COMPLETED: cls.SUCCEEDED,
            ExecutionStatus.ERRORED: cls.FAILED,
            ExecutionStatus.SKIPPED: cls.SKIPPED,
            ExecutionStatus.TIMED_OUT: cls.FAILED,
            ExecutionStatus.CANCELLED: cls.CANCELLED,
        }[status]


@dataclass(slots=True)
class GraphNode:
    """A unit of work in the graph.

    Args:
        unit_id: Unit identifier.
        requires: Required dependencies; a failure here blocks this node.
        optional: Optional dependencies; affect ordering only.
        state: Current state.
        level: Dependency level, for parallel scheduling and layout.
        reason: Why the node reached a non-success terminal state.
        metadata: Additional detail.
    """

    unit_id: str
    requires: frozenset[str] = field(default_factory=frozenset)
    optional: frozenset[str] = field(default_factory=frozenset)
    state: NodeState = NodeState.PENDING
    level: int = 0
    reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def dependencies(self) -> frozenset[str]:
        """Required and optional dependencies together."""
        return self.requires | self.optional


class ExecutionGraph:
    """A DAG of units with state tracking.

    Thread-safe: parallel execution updates node states concurrently.
    """

    __slots__ = ("_nodes", "_lock", "_resolution")

    def __init__(
        self,
        metadata: Iterable[PluginMetadata],
        *,
        resolution: ResolutionResult | None = None,
    ) -> None:
        """Build a graph from plugin metadata.

        Args:
            metadata: Metadata for the units in the graph.
            resolution: Precomputed resolution. When omitted, dependencies are
                resolved here. Units the resolver excluded start ``BLOCKED`` with
                the reason recorded, so an unsatisfiable dependency is visible in
                the graph rather than discovered at execution time.
        """
        items = list(metadata)
        resolver = DependencyResolver(items)
        resolved = resolution or resolver.analyse([item.plugin_id for item in items])
        level_of = {
            unit_id: index
            for index, level in enumerate(resolved.levels)
            for unit_id in level
        }
        self._nodes: dict[str, GraphNode] = {}
        for item in items:
            excluded_reason = resolved.excluded.get(item.plugin_id)
            self._nodes[item.plugin_id] = GraphNode(
                unit_id=item.plugin_id,
                requires=frozenset(item.depends_on),
                optional=frozenset(item.optional_depends_on),
                state=NodeState.BLOCKED if excluded_reason else NodeState.PENDING,
                level=level_of.get(item.plugin_id, 0),
                reason=excluded_reason,
                metadata={"version": item.version, "enabled": item.enabled},
            )
        self._resolution = resolved
        self._lock = threading.RLock()

    def __len__(self) -> int:
        return len(self._nodes)

    def __contains__(self, unit_id: object) -> bool:
        return isinstance(unit_id, str) and unit_id in self._nodes

    @property
    def resolution(self) -> ResolutionResult:
        """The dependency resolution this graph was built from."""
        return self._resolution

    def node(self, unit_id: str) -> GraphNode:
        """Return a node.

        Args:
            unit_id: Unit identifier.

        Returns:
            The node.

        Raises:
            ExecutionError: If the unit is not in the graph.
        """
        with self._lock:
            try:
                return self._nodes[unit_id]
            except KeyError as exc:
                raise ExecutionError(
                    "Unit is not present in the execution graph", {"unit_id": unit_id}
                ) from exc

    def nodes(self) -> tuple[GraphNode, ...]:
        """Return every node, ordered by level then identifier."""
        with self._lock:
            return tuple(
                sorted(self._nodes.values(), key=lambda item: (item.level, item.unit_id))
            )

    def levels(self) -> tuple[tuple[str, ...], ...]:
        """Return unit identifiers grouped into dependency levels.

        Members of a level have no dependency on one another and may run in
        parallel.

        Returns:
            The levels, in execution order.
        """
        grouped: dict[int, list[str]] = {}
        for node in self.nodes():
            grouped.setdefault(node.level, []).append(node.unit_id)
        return tuple(tuple(sorted(grouped[key])) for key in sorted(grouped))

    def ready(self) -> tuple[str, ...]:
        """Return units whose dependencies are satisfied and that can run now.

        Returns:
            Ready unit identifiers, sorted for determinism.
        """
        with self._lock:
            ready: list[str] = []
            for node in self._nodes.values():
                if node.state not in (NodeState.PENDING, NodeState.READY):
                    continue
                blocked = False
                for dependency in node.dependencies:
                    other = self._nodes.get(dependency)
                    if other is None:
                        continue
                    if not other.state.is_terminal or not other.state.is_success:
                        blocked = True
                        break
                if not blocked:
                    ready.append(node.unit_id)
            return tuple(sorted(ready))

    def mark(
        self, unit_id: str, state: NodeState, *, reason: str | None = None
    ) -> tuple[str, ...]:
        """Set a unit's state, propagating failure to its dependents.

        Args:
            unit_id: Unit to update.
            state: New state.
            reason: Why, for non-success terminal states.

        Returns:
            Units newly blocked as a consequence, sorted.
        """
        node = self.node(unit_id)
        with self._lock:
            node.state = state
            node.reason = reason
        if state in (NodeState.FAILED, NodeState.BLOCKED, NodeState.CANCELLED):
            return self._propagate(unit_id, state)
        return ()

    def _propagate(self, unit_id: str, state: NodeState) -> tuple[str, ...]:
        """Block units that require a unit which did not succeed.

        Propagation is transitive and the recorded reason names the *root* cause,
        so a report does not force the reader to trace a chain of blocked units back
        to the real failure.

        Args:
            unit_id: The unit that did not succeed.
            state: Its state.

        Returns:
            Newly blocked unit identifiers.
        """
        blocked: list[str] = []
        with self._lock:
            frontier = [unit_id]
            while frontier:
                current = frontier.pop()
                for node in self._nodes.values():
                    if current not in node.requires:
                        continue
                    if node.state.is_terminal:
                        continue
                    node.state = NodeState.BLOCKED
                    node.reason = (
                        f"required dependency {unit_id} "
                        f"{'failed' if state is NodeState.FAILED else state.value.lower()}"
                    )
                    blocked.append(node.unit_id)
                    frontier.append(node.unit_id)
        if blocked:
            _LOGGER.warning(
                "Failure of %s blocked %d dependent unit(s): %s",
                unit_id,
                len(blocked),
                ", ".join(sorted(blocked)),
            )
        return tuple(sorted(blocked))

    def seed_completed(self, completed: Mapping[str, ExecutionStatus]) -> tuple[str, ...]:
        """Mark units as already finished, for resuming a previous run.

        Args:
            completed: Unit identifiers mapped to the status they finished with.

        Returns:
            Units that were seeded, sorted. Unknown identifiers are ignored: a
            previous run may have contained units this graph does not.
        """
        seeded: list[str] = []
        for unit_id, status in completed.items():
            if unit_id not in self:
                continue
            state = NodeState.from_execution_status(status)
            self.mark(unit_id, state, reason="restored from a previous run")
            seeded.append(unit_id)
        if seeded:
            _LOGGER.info("Resumed with %d unit(s) already complete", len(seeded))
        return tuple(sorted(seeded))

    def subgraph_for(self, unit_ids: Iterable[str]) -> tuple[str, ...]:
        """Return the units needed to execute a subset, including prerequisites.

        Args:
            unit_ids: Units of interest.

        Returns:
            The closure over required and optional dependencies, sorted.

        Raises:
            ExecutionError: If a requested unit is not in the graph.
        """
        selected: set[str] = set()
        frontier = list(unit_ids)
        while frontier:
            current = frontier.pop()
            if current in selected:
                continue
            node = self.node(current)
            selected.add(current)
            frontier.extend(dep for dep in node.dependencies if dep in self)
        return tuple(sorted(selected))

    def outstanding(self) -> tuple[str, ...]:
        """Return units that have not reached a terminal state, sorted."""
        with self._lock:
            return tuple(
                sorted(
                    node.unit_id
                    for node in self._nodes.values()
                    if not node.state.is_terminal
                )
            )

    def state_counts(self) -> dict[str, int]:
        """Tally nodes by state.

        Returns:
            A mapping covering every state, so zeros are explicit.
        """
        counts = {state.value: 0 for state in NodeState}
        for node in self.nodes():
            counts[node.state.value] += 1
        return counts

    def is_complete(self) -> bool:
        """Whether every node has reached a terminal state."""
        return not self.outstanding()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping, sufficient to reconstruct the graph's shape and
            state for an external visualisation.
        """
        return {
            "node_count": len(self),
            "levels": [list(level) for level in self.levels()],
            "state_counts": self.state_counts(),
            "excluded": dict(self._resolution.excluded),
            "nodes": [
                {
                    "unit_id": node.unit_id,
                    "state": node.state.value,
                    "level": node.level,
                    "requires": sorted(node.requires),
                    "optional": sorted(node.optional),
                    "reason": node.reason,
                    "metadata": dict(node.metadata),
                }
                for node in self.nodes()
            ],
        }

    def render_text(self) -> str:
        """Render the graph as indented plain text, grouped by level.

        Returns:
            A human-readable rendering.
        """
        if not len(self):
            return "(execution graph empty)"
        lines: list[str] = []
        for index, level in enumerate(self.levels()):
            lines.append(f"level {index}:")
            for unit_id in level:
                node = self.node(unit_id)
                requires = ", ".join(sorted(node.requires)) or "-"
                suffix = f"  [{node.reason}]" if node.reason else ""
                lines.append(
                    f"  {unit_id:<28} {node.state.value:<10} requires: {requires}{suffix}"
                )
        return "\n".join(lines)

    def render_mermaid(self) -> str:
        """Render the graph as a Mermaid flowchart.

        Mermaid is text, so a graph can be visualised in documentation without the
        framework taking on a rendering dependency.

        Returns:
            Mermaid source. Required edges are solid, optional edges dotted.
        """
        lines = ["flowchart TD"]
        for node in self.nodes():
            label = f"{node.unit_id}<br/>{node.state.value}"
            lines.append(f'    {self._safe_id(node.unit_id)}["{label}"]')
        for node in self.nodes():
            target = self._safe_id(node.unit_id)
            for dependency in sorted(node.requires):
                if dependency in self:
                    lines.append(f"    {self._safe_id(dependency)} --> {target}")
            for dependency in sorted(node.optional):
                if dependency in self:
                    lines.append(f"    {self._safe_id(dependency)} -.-> {target}")
        return "\n".join(lines)

    def render_dot(self) -> str:
        """Render the graph in Graphviz DOT format.

        Returns:
            DOT source.
        """
        lines = ["digraph execution {", "    rankdir=TB;"]
        for node in self.nodes():
            lines.append(
                f'    "{node.unit_id}" [label="{node.unit_id}\\n{node.state.value}"];'
            )
        for node in self.nodes():
            for dependency in sorted(node.requires):
                if dependency in self:
                    lines.append(f'    "{dependency}" -> "{node.unit_id}";')
            for dependency in sorted(node.optional):
                if dependency in self:
                    lines.append(f'    "{dependency}" -> "{node.unit_id}" [style=dotted];')
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _safe_id(unit_id: str) -> str:
        """Convert a unit identifier into a diagram-safe node id.

        Args:
            unit_id: Identifier to convert.

        Returns:
            An identifier safe for Mermaid and DOT.
        """
        return "".join(char if char.isalnum() else "_" for char in unit_id)
