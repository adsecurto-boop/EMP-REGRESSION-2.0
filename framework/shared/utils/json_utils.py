"""JSON reading, writing, and serialisation helpers.

Handles the types the framework's own models use -- :class:`~pathlib.Path`,
:class:`~datetime.datetime`, :class:`~enum.Enum`, and dataclasses -- which the
standard library encoder rejects. Report and evidence serialisation depends on
this, so it lives in one place rather than being re-solved per call site.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from framework.shared.exceptions import FrameworkError

__all__ = [
    "default_encoder",
    "to_json",
    "from_json",
    "read_json_file",
    "write_json_file",
]


def default_encoder(value: Any) -> Any:
    """Convert framework types into JSON-native equivalents.

    Args:
        value: Object the standard encoder could not handle.

    Returns:
        A JSON-serialisable representation.

    Raises:
        TypeError: If the type is genuinely unsupported, so the caller learns
            about it rather than receiving a silently mangled document.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def to_json(value: Any, *, indent: int | None = 2, sort_keys: bool = False) -> str:
    """Serialise a value to JSON text.

    Args:
        value: Value to serialise.
        indent: Indentation; ``None`` produces compact output.
        sort_keys: Whether to sort mapping keys.

    Returns:
        JSON text.

    Raises:
        FrameworkError: If the value cannot be serialised.
    """
    try:
        return json.dumps(value, indent=indent, sort_keys=sort_keys, default=default_encoder)
    except (TypeError, ValueError) as exc:
        raise FrameworkError("Value could not be serialised to JSON") from exc


def from_json(text: str) -> Any:
    """Parse JSON text.

    Args:
        text: JSON text.

    Returns:
        The parsed value.

    Raises:
        FrameworkError: If the text is not valid JSON.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise FrameworkError("Text is not valid JSON") from exc


def read_json_file(path: Path | str) -> Any:
    """Read and parse a JSON file.

    Args:
        path: File to read.

    Returns:
        The parsed contents.

    Raises:
        FrameworkError: If the file cannot be read or is not valid JSON.
    """
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise FrameworkError("JSON file could not be read", {"path": str(target)}) from exc
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        raise FrameworkError("JSON file is malformed", {"path": str(target)}) from exc


def write_json_file(
    path: Path | str, value: Any, *, indent: int | None = 2, sort_keys: bool = False
) -> Path:
    """Write a value to a JSON file, creating parent directories.

    Args:
        path: Destination file.
        value: Value to serialise.
        indent: Indentation.
        sort_keys: Whether to sort mapping keys.

    Returns:
        The written path.

    Raises:
        FrameworkError: If serialisation or writing fails.
    """
    target = Path(path)
    payload = to_json(value, indent=indent, sort_keys=sort_keys)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    except OSError as exc:
        raise FrameworkError(
            "JSON file could not be written", {"path": str(target)}
        ) from exc
    return target
