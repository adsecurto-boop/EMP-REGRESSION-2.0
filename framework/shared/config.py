"""Configuration loading and access.

Implements ``docs/ADS/configuration_standard.md``: configuration is external to
logic, layered by environment, validated before a run proceeds, and reached only
through this module -- no other component reads configuration files directly.

Precedence, lowest to highest:

1. Base configuration (``config/framework.json``)
2. Environment overlay (``config/environments/<environment>.json``)
3. Environment variables prefixed ``EMPAF_``

Variable substitution supports ``${VAR}`` and ``${VAR:-default}`` against
process environment variables and previously resolved configuration keys.

YAML is supported when :mod:`PyYAML` is installed; JSON always works from the
standard library. YAML is an optional import so that a missing third-party
dependency cannot break ``import framework``.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Iterator, Mapping, MutableMapping

from framework.shared.constants import (
    CONFIG_DIR_NAME,
    DEFAULT_ENVIRONMENT,
    ENV_VAR_CONFIG_DIR,
    ENV_VAR_ENVIRONMENT,
    ENV_VAR_PREFIX,
    MIN_CORROBORATING_LAYERS,
)
from framework.shared.exceptions import ConfigurationError

__all__ = ["Configuration", "ConfigurationManager", "load_configuration"]

_SUBSTITUTION_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
_MISSING = object()


def _read_structured_file(path: Path) -> dict[str, Any]:
    """Read a JSON or YAML file into a dictionary.

    Args:
        path: File to read.

    Returns:
        Parsed mapping.

    Raises:
        ConfigurationError: If the file is unreadable, malformed, does not
            contain a mapping at the top level, or is YAML while PyYAML is not
            installed.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            "Configuration file could not be read", {"path": str(path)}
        ) from exc

    suffix = path.suffix.lower()
    try:
        if suffix in (".yaml", ".yml"):
            try:
                import yaml  # noqa: PLC0415 -- optional dependency, imported on demand
            except ModuleNotFoundError as exc:
                raise ConfigurationError(
                    "YAML configuration requires PyYAML to be installed; "
                    "use JSON or install PyYAML",
                    {"path": str(path)},
                ) from exc
            parsed = yaml.safe_load(text) or {}
        else:
            parsed = json.loads(text) if text.strip() else {}
    except ConfigurationError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise ConfigurationError(
            "Configuration file is malformed", {"path": str(path)}
        ) from exc

    if not isinstance(parsed, dict):
        raise ConfigurationError(
            "Configuration file must contain a mapping at the top level",
            {"path": str(path), "found": type(parsed).__name__},
        )
    return parsed


def _deep_merge(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` onto ``base`` without mutating either.

    Nested mappings merge key-by-key; every other type is replaced outright.
    Replacing rather than merging lists is deliberate: a partially overridden
    list is ambiguous, and an environment overlay should be able to state a list
    definitively.

    Args:
        base: Lower-precedence mapping.
        overlay: Higher-precedence mapping.

    Returns:
        The merged mapping.
    """
    merged: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _coerce(raw: str) -> Any:
    """Coerce an environment-variable string into a JSON-native value.

    Environment variables are always strings, but configuration consumers expect
    real types (a port should be an int, a flag a bool).

    Args:
        raw: Raw string value.

    Returns:
        The coerced value, or the original string when it is not JSON-like.
    """
    lowered = raw.strip().lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "none", ""):
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


class Configuration(Mapping[str, Any]):
    """Immutable, dotted-path view over resolved configuration values.

    Read-only by design: configuration is resolved once at startup, and a
    component mutating shared configuration mid-run would make behaviour
    unreproducible.
    """

    __slots__ = ("_values", "_environment", "_sources")

    def __init__(
        self,
        values: Mapping[str, Any],
        *,
        environment: str,
        sources: tuple[Path, ...] = (),
    ) -> None:
        """Initialise a configuration view.

        Args:
            values: Fully resolved configuration values.
            environment: Active environment name.
            sources: Files that contributed, in precedence order, for auditing.
        """
        self._values: dict[str, Any] = dict(values)
        self._environment = environment
        self._sources = sources

    @property
    def environment(self) -> str:
        """The active environment name."""
        return self._environment

    @property
    def sources(self) -> tuple[Path, ...]:
        """Files that contributed to this configuration, lowest precedence first."""
        return self._sources

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise KeyError(key)
        return value

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a value by dotted path.

        Args:
            key: Dotted path, e.g. ``"logging.level"``.
            default: Returned when the path is absent.

        Returns:
            The resolved value, or ``default``.
        """
        current: Any = self._values
        for part in key.split("."):
            if not isinstance(current, Mapping) or part not in current:
                return default
            current = current[part]
        return current

    def require(self, key: str) -> Any:
        """Return a value by dotted path, failing fast when absent.

        Args:
            key: Dotted path.

        Returns:
            The resolved value.

        Raises:
            ConfigurationError: If the key is not present. Per the Configuration
                Standard a run must fail fast rather than proceed on a silent
                default.
        """
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise ConfigurationError(
                "Required configuration key is missing",
                {"key": key, "environment": self._environment},
            )
        return value

    def section(self, key: str) -> "Configuration":
        """Return a nested section as its own :class:`Configuration`.

        Lets a component be injected with just its own subtree rather than the
        whole configuration.

        Args:
            key: Dotted path to a mapping.

        Returns:
            A configuration view over that subtree.

        Raises:
            ConfigurationError: If the path is absent or is not a mapping.
        """
        value = self.get(key, _MISSING)
        if value is _MISSING:
            raise ConfigurationError(
                "Configuration section is missing", {"key": key}
            )
        if not isinstance(value, Mapping):
            raise ConfigurationError(
                "Configuration key is not a section",
                {"key": key, "found": type(value).__name__},
            )
        return Configuration(value, environment=self._environment, sources=self._sources)

    def as_dict(self) -> dict[str, Any]:
        """Return a deep-enough copy of the underlying values."""
        return json.loads(json.dumps(self._values, default=str))


class ConfigurationManager:
    """Loads, validates, and provides singleton access to configuration.

    The singleton is one of the framework's two approved pieces of global state
    (the other being the logging registry): configuration is resolved once per
    process and read everywhere, and threading it through every constructor
    would add noise without adding isolation. :meth:`reset` exists so tests can
    still get a clean slate.
    """

    _instance: "ConfigurationManager | None" = None
    _lock = threading.Lock()

    def __init__(
        self,
        *,
        config_dir: Path | None = None,
        environment: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Initialise a manager without loading anything yet.

        Args:
            config_dir: Configuration directory. Defaults to the repository's
                ``config/`` directory, overridable via ``EMPAF_CONFIG_DIR``.
            environment: Environment name. Defaults to ``EMPAF_ENVIRONMENT`` or
                ``local``.
            env: Environment mapping to read overrides from. Injected rather
                than read from :data:`os.environ` directly so behaviour is
                testable.
        """
        self._env: Mapping[str, str] = env if env is not None else os.environ
        self._config_dir = self._resolve_config_dir(config_dir)
        self._environment = (
            environment
            or self._env.get(ENV_VAR_ENVIRONMENT)
            or DEFAULT_ENVIRONMENT
        )
        self._configuration: Configuration | None = None

    def _resolve_config_dir(self, explicit: Path | None) -> Path:
        """Resolve the configuration directory.

        Args:
            explicit: Explicit directory, if given.

        Returns:
            The directory to load configuration from. Derived from this file's
            location rather than the process working directory, so behaviour
            does not depend on where the framework was launched from.
        """
        if explicit is not None:
            return Path(explicit)
        override = self._env.get(ENV_VAR_CONFIG_DIR)
        if override:
            return Path(override)
        repository_root = Path(__file__).resolve().parents[2]
        return repository_root / CONFIG_DIR_NAME

    @property
    def config_dir(self) -> Path:
        """The directory configuration is loaded from."""
        return self._config_dir

    @property
    def environment(self) -> str:
        """The active environment name."""
        return self._environment

    def load(self, *, force: bool = False) -> Configuration:
        """Load, merge, substitute, and validate configuration.

        Args:
            force: Reload even if configuration was already loaded.

        Returns:
            The resolved configuration.

        Raises:
            ConfigurationError: If the base file is missing or any layer is
                malformed or fails validation.
        """
        if self._configuration is not None and not force:
            return self._configuration

        sources: list[Path] = []
        base_path = self._find_file(self._config_dir, "framework")
        if base_path is None:
            raise ConfigurationError(
                "Base configuration file not found",
                {"config_dir": str(self._config_dir), "expected": "framework.json|.yaml"},
            )
        values = _read_structured_file(base_path)
        sources.append(base_path)

        overlay_path = self._find_file(
            self._config_dir / "environments", self._environment
        )
        if overlay_path is not None:
            values = _deep_merge(values, _read_structured_file(overlay_path))
            sources.append(overlay_path)

        values = _deep_merge(values, self._environment_overrides())
        values = self._substitute(values)
        self._validate(values)

        self._configuration = Configuration(
            values, environment=self._environment, sources=tuple(sources)
        )
        return self._configuration

    @staticmethod
    def _find_file(directory: Path, stem: str) -> Path | None:
        """Find a configuration file by stem, preferring JSON then YAML.

        Args:
            directory: Directory to search.
            stem: Filename without extension.

        Returns:
            The first matching path, or ``None``.
        """
        for suffix in (".json", ".yaml", ".yml"):
            candidate = directory / f"{stem}{suffix}"
            if candidate.is_file():
                return candidate
        return None

    def _environment_overrides(self) -> dict[str, Any]:
        """Build a nested override mapping from ``EMPAF_``-prefixed variables.

        ``EMPAF_LOGGING__LEVEL=DEBUG`` overrides ``logging.level``. A double
        underscore separates path segments, since single underscores appear
        inside key names.

        Returns:
            Nested overrides; empty when no relevant variables are set.
        """
        overrides: dict[str, Any] = {}
        reserved = {ENV_VAR_ENVIRONMENT, ENV_VAR_CONFIG_DIR}
        for name, raw in self._env.items():
            if not name.startswith(ENV_VAR_PREFIX) or name in reserved:
                continue
            path = name[len(ENV_VAR_PREFIX) :].lower().split("__")
            cursor: MutableMapping[str, Any] = overrides
            for part in path[:-1]:
                nested = cursor.setdefault(part, {})
                if not isinstance(nested, dict):
                    nested = {}
                    cursor[part] = nested
                cursor = nested
            cursor[path[-1]] = _coerce(raw)
        return overrides

    def _substitute(self, values: Mapping[str, Any]) -> dict[str, Any]:
        """Resolve ``${VAR}`` and ``${VAR:-default}`` references in string values.

        Args:
            values: Configuration values to process.

        Returns:
            Values with substitutions applied.

        Raises:
            ConfigurationError: If a referenced variable is undefined and no
                default was supplied.
        """

        def resolve(text: str) -> str:
            def replacement(match: re.Match[str]) -> str:
                name, default = match.group(1), match.group(2)
                if name in self._env:
                    return self._env[name]
                if default is not None:
                    return default
                raise ConfigurationError(
                    "Configuration references an undefined variable",
                    {"variable": name},
                )

            return _SUBSTITUTION_RE.sub(replacement, text)

        def walk(node: Any) -> Any:
            if isinstance(node, Mapping):
                return {key: walk(value) for key, value in node.items()}
            if isinstance(node, list):
                return [walk(item) for item in node]
            if isinstance(node, str):
                return resolve(node)
            return node

        return walk(values)

    @staticmethod
    def _validate(values: Mapping[str, Any]) -> None:
        """Validate structural requirements before a run proceeds.

        Checks only what the framework itself cannot function without. Per
        ``docs/ADS/configuration_standard.md`` §7 this is the fail-fast gate;
        richer semantic validation belongs to the configuration validator built
        in a later phase.

        Args:
            values: Resolved configuration values.

        Raises:
            ConfigurationError: If a required key is missing or invalid.
        """
        logging_section = values.get("logging")
        if logging_section is not None and not isinstance(logging_section, Mapping):
            raise ConfigurationError(
                "'logging' must be a section", {"found": type(logging_section).__name__}
            )

        validation_section = values.get("validation")
        if validation_section is not None:
            if not isinstance(validation_section, Mapping):
                raise ConfigurationError(
                    "'validation' must be a section",
                    {"found": type(validation_section).__name__},
                )
            minimum = validation_section.get("minimum_corroborating_layers")
            if minimum is not None:
                if not isinstance(minimum, int) or isinstance(minimum, bool):
                    raise ConfigurationError(
                        "'validation.minimum_corroborating_layers' must be an integer",
                        {"found": repr(minimum)},
                    )
                if minimum < MIN_CORROBORATING_LAYERS:
                    raise ConfigurationError(
                        "'validation.minimum_corroborating_layers' may not be below the "
                        "ratified floor",
                        {"configured": minimum, "floor": MIN_CORROBORATING_LAYERS},
                    )

    @classmethod
    def instance(cls) -> "ConfigurationManager":
        """Return the process-wide manager, creating it on first use.

        Returns:
            The singleton manager.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def set_instance(cls, manager: "ConfigurationManager") -> None:
        """Install a specific manager as the singleton.

        Provided for tests and for entry points that construct a manager with
        explicit arguments.

        Args:
            manager: Manager to install.
        """
        with cls._lock:
            cls._instance = manager

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton so the next access reloads from disk."""
        with cls._lock:
            cls._instance = None


def load_configuration(
    *,
    config_dir: Path | None = None,
    environment: str | None = None,
) -> Configuration:
    """Convenience helper returning resolved configuration.

    Args:
        config_dir: Optional configuration directory override.
        environment: Optional environment override.

    Returns:
        The resolved configuration.
    """
    if config_dir is None and environment is None:
        return ConfigurationManager.instance().load()
    manager = ConfigurationManager(config_dir=config_dir, environment=environment)
    ConfigurationManager.set_instance(manager)
    return manager.load()
