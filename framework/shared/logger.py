"""Logging setup and access.

Implements ``docs/ADS/logging_standard.md``. All logging goes through this
module: a component that configured its own handlers would break the format,
destination, and correlation guarantees the standard requires.

Every record carries the correlation fields the standard mandates -- timestamp,
level, module, execution id, plugin id, and correlation id -- whether rendered
as human-readable text or as JSON lines. Correlation identifiers are held in
:class:`contextvars.ContextVar` so they follow execution without being passed
explicitly through every call, and remain correct across threads.

This module never imports :mod:`framework.shared.config`. Configuration is
passed in by the caller, which keeps the two lowest-level modules independent
and prevents an import cycle.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator, Mapping

from framework.shared.constants import (
    CORRELATION_ID_LENGTH,
    FRAMEWORK_NAME,
    LOG_DIR_NAME,
)
from framework.shared.exceptions import ConfigurationError

__all__ = [
    "LogContext",
    "configure_logging",
    "get_logger",
    "new_execution_id",
    "new_correlation_id",
    "correlation_scope",
    "current_execution_id",
    "current_correlation_id",
    "reset_logging",
    "JsonFormatter",
]

_ROOT_LOGGER_NAME = "empaf"
_DEFAULT_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(execution_id)s | %(correlation_id)s | "
    "%(plugin_id)s | %(name)s | %(message)s"
)
_CONFIGURED = False
_CONFIGURE_LOCK = threading.Lock()

_execution_id: ContextVar[str] = ContextVar("execution_id", default="-")
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")
_plugin_id: ContextVar[str] = ContextVar("plugin_id", default="-")


def new_execution_id() -> str:
    """Generate an execution identifier for a run.

    Returns:
        A UUID4 hex string identifying one run end to end.
    """
    return uuid.uuid4().hex


def new_correlation_id() -> str:
    """Generate a short correlation identifier for a unit of work.

    Returns:
        A short hex string, long enough to be unique within a run but short
        enough to stay readable in aligned log output.
    """
    return uuid.uuid4().hex[:CORRELATION_ID_LENGTH]


def current_execution_id() -> str:
    """Return the execution id bound to the current context."""
    return _execution_id.get()


def current_correlation_id() -> str:
    """Return the correlation id bound to the current context."""
    return _correlation_id.get()


class LogContext:
    """Binds correlation identifiers for the current execution context.

    Identifiers set here are attached to every subsequent log record, so a run's
    output can be reassembled from interleaved component logs.
    """

    @staticmethod
    def bind(
        *,
        execution_id: str | None = None,
        correlation_id: str | None = None,
        plugin_id: str | None = None,
    ) -> None:
        """Bind identifiers to the current context.

        Args:
            execution_id: Run identifier.
            correlation_id: Unit-of-work identifier.
            plugin_id: Owning plugin identifier.
        """
        if execution_id is not None:
            _execution_id.set(execution_id)
        if correlation_id is not None:
            _correlation_id.set(correlation_id)
        if plugin_id is not None:
            _plugin_id.set(plugin_id)

    @staticmethod
    def clear() -> None:
        """Reset all bound identifiers to their placeholder values."""
        _execution_id.set("-")
        _correlation_id.set("-")
        _plugin_id.set("-")


@contextmanager
def correlation_scope(
    *, correlation_id: str | None = None, plugin_id: str | None = None
) -> Iterator[str]:
    """Bind a correlation id for the duration of a block, then restore.

    Args:
        correlation_id: Identifier to bind; generated when omitted.
        plugin_id: Plugin identifier to bind for the block.

    Yields:
        The bound correlation id.
    """
    resolved = correlation_id or new_correlation_id()
    correlation_token = _correlation_id.set(resolved)
    plugin_token = _plugin_id.set(plugin_id) if plugin_id is not None else None
    try:
        yield resolved
    finally:
        _correlation_id.reset(correlation_token)
        if plugin_token is not None:
            _plugin_id.reset(plugin_token)


class _ContextFilter(logging.Filter):
    """Injects correlation identifiers into every record.

    Implemented as a filter rather than a custom adapter so identifiers are
    attached no matter which logger emitted the record, including loggers
    obtained before the identifiers were bound.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach context fields to ``record``.

        Args:
            record: Record being emitted.

        Returns:
            Always ``True`` -- this filter enriches rather than excludes.
        """
        record.execution_id = _execution_id.get()
        record.correlation_id = _correlation_id.get()
        record.plugin_id = _plugin_id.get()
        return True


class JsonFormatter(logging.Formatter):
    """Renders records as single-line JSON objects.

    Structured output is the default for file logs so that log content is
    machine-readable evidence rather than prose that must be re-parsed later.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Render ``record`` as a JSON line.

        Args:
            record: Record to render.

        Returns:
            A JSON string containing the standard's required fields plus any
            extras attached to the record.
        """
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "execution_id": getattr(record, "execution_id", "-"),
            "correlation_id": getattr(record, "correlation_id", "-"),
            "plugin_id": getattr(record, "plugin_id", "-"),
            "module": record.module,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, Mapping):
            payload.update(extra)
        return json.dumps(payload, default=str)


def _resolve_level(value: Any, *, key: str) -> int:
    """Resolve a configured level name or number to a logging level.

    Args:
        value: Level name (e.g. ``"INFO"``) or numeric level.
        key: Configuration key, for error context.

    Returns:
        The numeric logging level.

    Raises:
        ConfigurationError: If the value is not a recognised level.
    """
    if isinstance(value, bool):
        raise ConfigurationError("Log level must be a name or number", {"key": key})
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        resolved = logging.getLevelName(value.strip().upper())
        if isinstance(resolved, int):
            return resolved
    raise ConfigurationError(
        "Unrecognised log level", {"key": key, "value": repr(value)}
    )


def configure_logging(
    settings: Mapping[str, Any] | None = None,
    *,
    output_root: Path | None = None,
    force: bool = False,
) -> logging.Logger:
    """Configure the framework logger hierarchy.

    Safe to call once per process; subsequent calls are ignored unless ``force``
    is set, so a library-style import cannot silently reconfigure handlers.

    Recognised settings:

    ``level``
        Root level for framework loggers. Default ``"INFO"``.
    ``console.enabled`` / ``console.level`` / ``console.format``
        Console handler controls. ``format`` is ``"text"`` or ``"json"``.
    ``file.enabled`` / ``file.level`` / ``file.format``
        File handler controls; ``format`` defaults to ``"json"``.
    ``file.filename``
        Log filename. Default ``framework.log``.
    ``file.max_bytes`` / ``file.backup_count``
        Rotation controls.

    Args:
        settings: The ``logging`` configuration section.
        output_root: Directory beneath which the ``logs/`` directory is created.
        force: Reconfigure even if already configured.

    Returns:
        The configured root framework logger.

    Raises:
        ConfigurationError: If a level is unrecognised or the log directory
            cannot be created.
    """
    global _CONFIGURED
    with _CONFIGURE_LOCK:
        if _CONFIGURED and not force:
            return logging.getLogger(_ROOT_LOGGER_NAME)

        config: Mapping[str, Any] = settings or {}
        logger = logging.getLogger(_ROOT_LOGGER_NAME)
        logger.setLevel(_resolve_level(config.get("level", "INFO"), key="logging.level"))
        logger.propagate = False
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

        context_filter = _ContextFilter()

        console_config = config.get("console", {})
        if not isinstance(console_config, Mapping):
            raise ConfigurationError("'logging.console' must be a section")
        if console_config.get("enabled", True):
            console = logging.StreamHandler(stream=sys.stdout)
            console.setLevel(
                _resolve_level(
                    console_config.get("level", logger.level), key="logging.console.level"
                )
            )
            console.setFormatter(
                JsonFormatter()
                if str(console_config.get("format", "text")).lower() == "json"
                else logging.Formatter(_DEFAULT_FORMAT)
            )
            console.addFilter(context_filter)
            logger.addHandler(console)

        file_config = config.get("file", {})
        if not isinstance(file_config, Mapping):
            raise ConfigurationError("'logging.file' must be a section")
        if file_config.get("enabled", True):
            root = Path(output_root) if output_root is not None else Path.cwd()
            log_dir = root / LOG_DIR_NAME
            try:
                log_dir.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ConfigurationError(
                    "Log directory could not be created", {"path": str(log_dir)}
                ) from exc
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / str(file_config.get("filename", "framework.log")),
                maxBytes=int(file_config.get("max_bytes", 10 * 1024 * 1024)),
                backupCount=int(file_config.get("backup_count", 5)),
                encoding="utf-8",
            )
            file_handler.setLevel(
                _resolve_level(
                    file_config.get("level", logger.level), key="logging.file.level"
                )
            )
            file_handler.setFormatter(
                logging.Formatter(_DEFAULT_FORMAT)
                if str(file_config.get("format", "json")).lower() == "text"
                else JsonFormatter()
            )
            file_handler.addFilter(context_filter)
            logger.addHandler(file_handler)

        if not logger.handlers:
            logger.addHandler(logging.NullHandler())

        _CONFIGURED = True
        logger.debug("%s logging configured", FRAMEWORK_NAME)
        return logger


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced framework logger.

    Args:
        name: Component or module name, e.g. ``"core.orchestrator"``. A
            ``framework.``-prefixed module name is normalised so callers can
            pass ``__name__`` directly.

    Returns:
        A logger beneath the framework root, so one configuration governs all
        framework output.
    """
    normalised = name
    if normalised.startswith("framework."):
        normalised = normalised[len("framework.") :]
    elif normalised == "framework":
        normalised = "root"
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{normalised}")


def reset_logging() -> None:
    """Remove framework handlers and mark logging unconfigured.

    Intended for tests, which must be able to assert against a clean handler
    set.
    """
    global _CONFIGURED
    with _CONFIGURE_LOCK:
        logger = logging.getLogger(_ROOT_LOGGER_NAME)
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        _CONFIGURED = False
