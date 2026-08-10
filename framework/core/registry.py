"""Plugin discovery, registration, and dependency resolution.

The registry is the framework's primary extension seam: new coverage arrives as
a new plugin, and nothing in the core changes
(``docs/FRAMEWORK_MANIFEST.md`` §11).

The registry stores plugin *factories*, not plugin instances. Constructing a
plugin can be expensive and can fail, and the registry needs to answer questions
about inventory and ordering without executing anything -- so instantiation is
deferred until execution.

**Dependency direction.** This module imports the ``Plugin`` interface from
``framework.shared``; it never imports from the ``plugins`` package. Discovery
works by importing a configured module path at runtime, so the static dependency
rule in ``docs/ADS/architecture.md`` §3 (no framework module imports plugins) is
preserved.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import threading
from typing import Callable, Iterable, Iterator, Sequence

from framework.core.dependencies import DependencyResolver
from framework.shared.exceptions import PluginError, PluginNotFoundError
from framework.shared.interfaces import Plugin
from framework.shared.logger import get_logger
from framework.shared.models import PluginMetadata

__all__ = ["PluginRegistry", "PluginFactory"]

_LOGGER = get_logger(__name__)

PluginFactory = Callable[[], Plugin]


class PluginRegistry:
    """Registers plugins and resolves their execution order.

    Thread-safe so that registration during bootstrap and queries during
    execution cannot race.
    """

    __slots__ = ("_factories", "_metadata", "_lock")

    def __init__(self) -> None:
        """Initialise an empty registry."""
        self._factories: dict[str, PluginFactory] = {}
        self._metadata: dict[str, PluginMetadata] = {}
        self._lock = threading.RLock()

    def __len__(self) -> int:
        return len(self._factories)

    def __contains__(self, plugin_id: object) -> bool:
        return isinstance(plugin_id, str) and plugin_id in self._factories

    def __iter__(self) -> Iterator[PluginMetadata]:
        return iter(self.all_metadata())

    def register(
        self, metadata: PluginMetadata, factory: PluginFactory, *, replace: bool = False
    ) -> None:
        """Register a plugin factory.

        Args:
            metadata: Declarative plugin metadata.
            factory: Zero-argument callable returning a plugin instance.
            replace: Permit replacing an existing registration.

        Raises:
            PluginError: If the identifier is already registered and ``replace``
                is not set. Silent replacement would make execution order depend
                on import order.
        """
        with self._lock:
            if metadata.plugin_id in self._factories and not replace:
                raise PluginError(
                    "Plugin identifier is already registered",
                    {"plugin_id": metadata.plugin_id},
                )
            self._factories[metadata.plugin_id] = factory
            self._metadata[metadata.plugin_id] = metadata
        _LOGGER.debug("Plugin registered: %s v%s", metadata.plugin_id, metadata.version)

    def register_class(self, plugin_class: type[Plugin], *, replace: bool = False) -> None:
        """Register a plugin class, deriving metadata from a temporary instance.

        Args:
            plugin_class: Concrete :class:`~framework.shared.interfaces.Plugin`
                subclass with a zero-argument constructor.
            replace: Permit replacing an existing registration.

        Raises:
            PluginError: If the class is abstract, cannot be instantiated without
                arguments, or fails to report metadata.
        """
        if inspect.isabstract(plugin_class):
            raise PluginError(
                "Cannot register an abstract plugin class",
                {"class": plugin_class.__name__},
            )
        try:
            probe = plugin_class()
            metadata = probe.metadata
        except Exception as exc:  # noqa: BLE001 -- normalised to a plugin failure
            raise PluginError(
                "Plugin class could not be instantiated for metadata discovery",
                {"class": plugin_class.__name__},
            ) from exc
        self.register(metadata, plugin_class, replace=replace)

    def unregister(self, plugin_id: str) -> bool:
        """Remove a registration.

        Args:
            plugin_id: Identifier to remove.

        Returns:
            ``True`` if a registration was removed.
        """
        with self._lock:
            existed = self._factories.pop(plugin_id, None) is not None
            self._metadata.pop(plugin_id, None)
        return existed

    def metadata_for(self, plugin_id: str) -> PluginMetadata:
        """Return a registered plugin's metadata.

        Args:
            plugin_id: Identifier to look up.

        Returns:
            The metadata.

        Raises:
            PluginNotFoundError: If the identifier is not registered.
        """
        with self._lock:
            try:
                return self._metadata[plugin_id]
            except KeyError as exc:
                raise PluginNotFoundError(
                    "Plugin is not registered", {"plugin_id": plugin_id}
                ) from exc

    def all_metadata(self) -> tuple[PluginMetadata, ...]:
        """Return metadata for every registered plugin, sorted by identifier."""
        with self._lock:
            return tuple(
                self._metadata[key] for key in sorted(self._metadata)
            )

    def create(self, plugin_id: str) -> Plugin:
        """Instantiate a registered plugin.

        Args:
            plugin_id: Identifier to instantiate.

        Returns:
            A new plugin instance.

        Raises:
            PluginNotFoundError: If the identifier is not registered.
            PluginError: If the factory raises.
        """
        with self._lock:
            factory = self._factories.get(plugin_id)
        if factory is None:
            raise PluginNotFoundError(
                "Plugin is not registered", {"plugin_id": plugin_id}
            )
        try:
            return factory()
        except Exception as exc:  # noqa: BLE001 -- normalised to a plugin failure
            raise PluginError(
                "Plugin could not be instantiated", {"plugin_id": plugin_id}
            ) from exc

    def enabled_metadata(self) -> tuple[PluginMetadata, ...]:
        """Return metadata for enabled plugins only."""
        return tuple(item for item in self.all_metadata() if item.enabled)

    def resolver(self) -> DependencyResolver:
        """Return a resolver over the currently registered plugins.

        Returns:
            A resolver snapshot. Built fresh on each call so it reflects the
            registry as it is now rather than as it was at construction.
        """
        return DependencyResolver(self.all_metadata())

    def resolve_order(self, plugin_ids: Iterable[str] | None = None) -> tuple[str, ...]:
        """Resolve execution order from declared dependencies.

        Delegates to :class:`framework.core.dependencies.DependencyResolver`, which
        owns the single implementation of ordering, cycle detection, and version
        compatibility. The registry deliberately keeps no sort of its own: two
        implementations of ordering would eventually disagree, and a run whose order
        depends on which code path resolved it is not reproducible.

        Args:
            plugin_ids: Subset to order; defaults to all enabled plugins.

        Returns:
            Plugin identifiers in a safe execution order.

        Raises:
            PluginNotFoundError: If a requested plugin is not registered.
            PluginDependencyError: If a dependency is missing, a version constraint
                is violated, or the dependency graph contains a cycle.
        """
        if plugin_ids is not None:
            requested = list(plugin_ids)
            with self._lock:
                unknown = [pid for pid in requested if pid not in self._metadata]
            if unknown:
                raise PluginNotFoundError(
                    "Plugin is not registered", {"plugin_id": unknown[0]}
                )
        else:
            requested = None
        return self.resolver().resolve_order(requested)

    def discover(self, package_name: str) -> tuple[str, ...]:
        """Discover and register plugins from a package.

        Imports each submodule of ``package_name`` and registers every concrete
        :class:`~framework.shared.interfaces.Plugin` subclass it defines. The
        package name is supplied by the caller (from configuration), so the
        framework never statically imports the ``plugins`` package.

        A submodule that fails to import is logged and skipped rather than
        aborting discovery: one broken plugin must not prevent every other plugin
        from running.

        Args:
            package_name: Importable package to scan, e.g. ``"plugins"``.

        Returns:
            Identifiers of the plugins registered by this call.

        Raises:
            PluginError: If the package itself cannot be imported.
        """
        try:
            package = importlib.import_module(package_name)
        except ImportError as exc:
            raise PluginError(
                "Plugin package could not be imported", {"package": package_name}
            ) from exc

        search_paths: Sequence[str] = getattr(package, "__path__", ())
        if not search_paths:
            _LOGGER.warning("Plugin package %s is not a package; nothing to discover", package_name)
            return ()

        registered: list[str] = []
        for module_info in pkgutil.iter_modules(list(search_paths)):
            module_name = f"{package_name}.{module_info.name}"
            try:
                module = importlib.import_module(module_name)
            except Exception as exc:  # noqa: BLE001 -- isolate one bad plugin module
                _LOGGER.error(
                    "Plugin module %s could not be imported: %s", module_name, exc,
                    exc_info=True,
                )
                continue
            for _, candidate in inspect.getmembers(module, inspect.isclass):
                # Accept classes defined in this module *or in one of its
                # submodules*. A plugin is normally a subpackage
                # (``plugins/EM000_Name/plugin.py``) that re-exports its class from
                # ``__init__``, so requiring an exact module match would discover
                # nothing in the repository's own canonical layout. The prefix test
                # still excludes classes merely imported from elsewhere, such as the
                # ``Plugin`` base itself.
                if (
                    issubclass(candidate, Plugin)
                    and candidate is not Plugin
                    and not inspect.isabstract(candidate)
                    and (
                        candidate.__module__ == module_name
                        or candidate.__module__.startswith(f"{module_name}.")
                    )
                ):
                    try:
                        self.register_class(candidate)
                    except PluginError as exc:
                        _LOGGER.error("Plugin class %s not registered: %s", candidate.__name__, exc)
                        continue
                    registered.append(candidate().metadata.plugin_id)
        _LOGGER.info("Discovered %d plugin(s) in %s", len(registered), package_name)
        return tuple(registered)

    def clear(self) -> None:
        """Remove every registration."""
        with self._lock:
            self._factories.clear()
            self._metadata.clear()
