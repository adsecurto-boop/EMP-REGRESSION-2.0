"""Dependency resolution and execution ordering.

Owns every question about *what order units run in and whether their declared
dependencies can be satisfied*: topological sorting, cycle detection, required
versus optional dependencies, and version compatibility.

This module is the single implementation of that logic. :mod:`framework.core.registry`
delegates to it rather than carrying its own sort, so ordering behaviour cannot
diverge between the two.

Depends on :mod:`framework.shared` only, so it can be used by anything in ``core``
without creating a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from framework.shared.exceptions import PluginDependencyError
from framework.shared.logger import get_logger
from framework.shared.models import PluginMetadata
from framework.shared.utils import version as version_utils

__all__ = ["DependencyIssue", "ResolutionResult", "DependencyResolver"]

_LOGGER = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DependencyIssue:
    """A problem found while resolving dependencies.

    Issues are *returned* rather than raised by :meth:`DependencyResolver.analyse`
    so that a caller can see every problem at once. A run blocked by three missing
    dependencies should report all three, not just the first.

    Args:
        plugin_id: The plugin the issue concerns.
        kind: Issue category -- ``"missing_required"``, ``"version_mismatch"``,
            ``"cycle"``, or ``"missing_optional"``.
        detail: Human-readable description.
        fatal: Whether this issue prevents execution. Missing *optional*
            dependencies are not fatal.
        related: Other plugin identifiers involved.
    """

    plugin_id: str
    kind: str
    detail: str
    fatal: bool = True
    related: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    """The outcome of resolving a set of plugins.

    Args:
        order: Execution order for the plugins that can run.
        excluded: Plugins that cannot run, mapped to the reason.
        issues: Every issue found, fatal or not.
        levels: Dependency levels. Each level's members have no dependencies on
            one another, so a level may be executed in parallel.
    """

    order: Sequence[str] = field(default_factory=tuple)
    excluded: Mapping[str, str] = field(default_factory=dict)
    issues: Sequence[DependencyIssue] = field(default_factory=tuple)
    levels: Sequence[Sequence[str]] = field(default_factory=tuple)

    @property
    def is_complete(self) -> bool:
        """Whether every requested plugin can run."""
        return not self.excluded

    @property
    def fatal_issues(self) -> tuple[DependencyIssue, ...]:
        """Issues that prevent one or more plugins from running."""
        return tuple(issue for issue in self.issues if issue.fatal)


class DependencyResolver:
    """Resolves execution order from declared plugin dependencies.

    Two modes, deliberately distinct:

    * :meth:`analyse` is tolerant -- it excludes what cannot run, reports why, and
      still returns an order for everything else. This is what an execution engine
      wants: one plugin with an unsatisfiable dependency should not cancel the
      whole run.
    * :meth:`resolve_order` is strict -- it raises on any fatal issue. This is what
      a caller wants when a complete, verified order is a precondition.
    """

    __slots__ = ("_metadata",)

    def __init__(self, metadata: Iterable[PluginMetadata]) -> None:
        """Initialise the resolver.

        Args:
            metadata: Metadata for all known plugins.

        Raises:
            PluginDependencyError: If two entries share a plugin identifier.
        """
        self._metadata: dict[str, PluginMetadata] = {}
        for item in metadata:
            if item.plugin_id in self._metadata:
                raise PluginDependencyError(
                    "Duplicate plugin metadata supplied to the resolver",
                    {"plugin_id": item.plugin_id},
                )
            self._metadata[item.plugin_id] = item

    @property
    def known_ids(self) -> tuple[str, ...]:
        """Identifiers known to the resolver, sorted."""
        return tuple(sorted(self._metadata))

    def _selection(self, plugin_ids: Iterable[str] | None) -> list[str]:
        """Resolve the requested subset, defaulting to enabled plugins.

        Args:
            plugin_ids: Requested subset, or ``None`` for all enabled plugins.

        Returns:
            The selected identifiers.

        Raises:
            PluginDependencyError: If a requested identifier is unknown.
        """
        if plugin_ids is None:
            return sorted(
                pid for pid, meta in self._metadata.items() if meta.enabled
            )
        selected = list(plugin_ids)
        unknown = [pid for pid in selected if pid not in self._metadata]
        if unknown:
            raise PluginDependencyError(
                "Requested plugins are not known to the resolver",
                {"unknown": sorted(unknown)},
            )
        return selected

    def _check_versions(self, plugin_id: str, available: set[str]) -> list[DependencyIssue]:
        """Check declared version constraints against available plugin versions.

        Args:
            plugin_id: Plugin whose constraints are checked.
            available: Identifiers present in the current selection.

        Returns:
            Version-mismatch issues, one per violated constraint.
        """
        issues: list[DependencyIssue] = []
        metadata = self._metadata[plugin_id]
        for target_id, constraint in metadata.requires.items():
            if target_id not in self._metadata:
                # A constraint on an absent plugin is reported by the dependency
                # checks; the constraint itself is simply unevaluable.
                continue
            target_version = self._metadata[target_id].version
            try:
                satisfied = version_utils.satisfies(target_version, constraint)
            except Exception as exc:  # noqa: BLE001 -- normalised to an issue
                issues.append(
                    DependencyIssue(
                        plugin_id=plugin_id,
                        kind="version_mismatch",
                        detail=(
                            f"constraint {constraint!r} on {target_id} could not be "
                            f"evaluated: {exc}"
                        ),
                        related=(target_id,),
                    )
                )
                continue
            if not satisfied:
                issues.append(
                    DependencyIssue(
                        plugin_id=plugin_id,
                        kind="version_mismatch",
                        detail=(
                            f"requires {target_id} {constraint}, but version "
                            f"{target_version} is registered"
                        ),
                        related=(target_id,),
                    )
                )
        return issues

    def analyse(self, plugin_ids: Iterable[str] | None = None) -> ResolutionResult:
        """Resolve as much as possible, reporting what cannot run and why.

        Exclusion is transitive: if A cannot run, anything requiring A cannot run
        either, and the reason names the root cause rather than just the immediate
        dependency.

        Args:
            plugin_ids: Subset to resolve; defaults to all enabled plugins.

        Returns:
            The resolution result, including order, exclusions, issues, and
            parallelisable levels.

        Raises:
            PluginDependencyError: If a requested identifier is unknown.
        """
        selected = self._selection(plugin_ids)
        selected_set = set(selected)
        issues: list[DependencyIssue] = []
        excluded: dict[str, str] = {}

        for plugin_id in selected:
            metadata = self._metadata[plugin_id]
            missing_required = [
                dep for dep in metadata.depends_on if dep not in selected_set
            ]
            for dep in missing_required:
                issues.append(
                    DependencyIssue(
                        plugin_id=plugin_id,
                        kind="missing_required",
                        detail=f"required dependency {dep} is not registered or not enabled",
                        related=(dep,),
                    )
                )
                excluded.setdefault(
                    plugin_id, f"missing required dependency {dep}"
                )
            for dep in metadata.optional_depends_on:
                if dep not in selected_set:
                    issues.append(
                        DependencyIssue(
                            plugin_id=plugin_id,
                            kind="missing_optional",
                            detail=f"optional dependency {dep} is absent; ordering unaffected",
                            fatal=False,
                            related=(dep,),
                        )
                    )
            for issue in self._check_versions(plugin_id, selected_set):
                issues.append(issue)
                excluded.setdefault(plugin_id, issue.detail)

        # Propagate exclusions transitively through required dependencies.
        changed = True
        while changed:
            changed = False
            for plugin_id in selected:
                if plugin_id in excluded:
                    continue
                for dep in self._metadata[plugin_id].depends_on:
                    if dep in excluded:
                        excluded[plugin_id] = f"depends on excluded plugin {dep}"
                        changed = True
                        break

        runnable = [pid for pid in selected if pid not in excluded]
        levels, cycle = self._level_sort(runnable)
        if cycle:
            for plugin_id in cycle:
                excluded[plugin_id] = "participates in a dependency cycle"
            issues.append(
                DependencyIssue(
                    plugin_id=sorted(cycle)[0],
                    kind="cycle",
                    detail=f"dependency cycle among {sorted(cycle)}",
                    related=tuple(sorted(cycle)),
                )
            )
            runnable = [pid for pid in runnable if pid not in cycle]
            levels, _ = self._level_sort(runnable)

        order = tuple(pid for level in levels for pid in level)
        if excluded:
            _LOGGER.warning(
                "%d plugin(s) excluded from execution: %s",
                len(excluded),
                ", ".join(f"{pid} ({reason})" for pid, reason in sorted(excluded.items())),
            )
        return ResolutionResult(
            order=order,
            excluded=dict(excluded),
            issues=tuple(issues),
            levels=tuple(tuple(level) for level in levels),
        )

    def _level_sort(
        self, plugin_ids: Sequence[str]
    ) -> tuple[list[list[str]], set[str]]:
        """Group plugins into dependency levels via Kahn's algorithm.

        Members of a level depend on nothing else in that level, so a level is
        safe to execute in parallel. Within a level, order is alphabetical, which
        keeps sequential execution reproducible -- a run whose order varies is not
        reproducible, and reproducibility is what makes a report trustworthy.

        Args:
            plugin_ids: Plugins to sort.

        Returns:
            The levels, and the set of plugins left unresolved (a cycle).
        """
        present = set(plugin_ids)
        pending = {
            pid: {
                dep
                for dep in self._metadata[pid].all_dependencies
                if dep in present
            }
            for pid in plugin_ids
        }
        levels: list[list[str]] = []
        settled: set[str] = set()
        while pending:
            ready = sorted(
                pid for pid, deps in pending.items() if not (deps - settled)
            )
            if not ready:
                return levels, set(pending)
            levels.append(ready)
            settled.update(ready)
            for pid in ready:
                pending.pop(pid)
        return levels, set()

    def resolve_order(self, plugin_ids: Iterable[str] | None = None) -> tuple[str, ...]:
        """Resolve a complete execution order, or fail.

        Args:
            plugin_ids: Subset to order; defaults to all enabled plugins.

        Returns:
            Every requested plugin in a safe execution order.

        Raises:
            PluginDependencyError: If any dependency is missing, any version
                constraint is violated, or the graph contains a cycle.
        """
        result = self.analyse(plugin_ids)
        if result.fatal_issues:
            first = result.fatal_issues[0]
            raise PluginDependencyError(
                f"Dependencies could not be resolved: {first.detail}",
                {
                    "plugin_id": first.plugin_id,
                    "kind": first.kind,
                    "issues": [issue.detail for issue in result.fatal_issues],
                },
            )
        return tuple(result.order)

    def dependents_of(self, plugin_id: str) -> tuple[str, ...]:
        """Return plugins that require the given plugin, directly or transitively.

        Used for failure propagation: when a plugin fails, its dependents cannot
        meaningfully run.

        Args:
            plugin_id: Plugin to trace.

        Returns:
            Dependent identifiers, sorted.
        """
        found: set[str] = set()
        frontier = {plugin_id}
        while frontier:
            current = frontier.pop()
            for candidate, metadata in self._metadata.items():
                if current in metadata.depends_on and candidate not in found:
                    found.add(candidate)
                    frontier.add(candidate)
        return tuple(sorted(found))
