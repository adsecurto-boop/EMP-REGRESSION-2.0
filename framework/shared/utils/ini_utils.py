"""INI file reading helpers.

A thin, generic wrapper over :mod:`configparser`. It reads *any* INI file; it
carries no knowledge of any particular file's sections or keys.

That boundary is deliberate. Reading EmpMonitor's own configuration is Phase 2
work and its keys are still unverified (``knowledge_base/RE-005``). This module
is the reusable transport those later collectors will use, nothing more.
"""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Any, Mapping

from framework.shared.exceptions import FrameworkError

__all__ = ["read_ini_file", "parse_ini", "flatten_ini"]


def _new_parser() -> configparser.ConfigParser:
    """Create a permissive parser.

    Interpolation is disabled because arbitrary third-party INI content may
    contain ``%`` characters that are not interpolation syntax, and case is
    preserved because key case may be meaningful in files the framework does not
    own.

    Returns:
        A configured parser.
    """
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str  # type: ignore[method-assign]
    return parser


def parse_ini(text: str) -> dict[str, dict[str, str]]:
    """Parse INI text into nested dictionaries.

    Args:
        text: INI content.

    Returns:
        Mapping of section name to key/value pairs. Keys defined before any
        section header appear under ``"DEFAULT"``.

    Raises:
        FrameworkError: If the content cannot be parsed.
    """
    parser = _new_parser()
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise FrameworkError("INI content could not be parsed") from exc

    result: dict[str, dict[str, str]] = {}
    defaults = dict(parser.defaults())
    if defaults:
        result["DEFAULT"] = defaults
    for section in parser.sections():
        result[section] = dict(parser.items(section))
    return result


def read_ini_file(path: Path | str) -> dict[str, dict[str, str]]:
    """Read and parse an INI file.

    Args:
        path: File to read.

    Returns:
        Mapping of section name to key/value pairs.

    Raises:
        FrameworkError: If the file cannot be read or parsed.
    """
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise FrameworkError("INI file could not be read", {"path": str(target)}) from exc
    return parse_ini(text)


def flatten_ini(sections: Mapping[str, Mapping[str, Any]], *, separator: str = ".") -> dict[str, Any]:
    """Flatten parsed INI sections into dotted keys.

    Useful for comparing an INI file against a JSON/YAML representation of the
    same settings, which is the shape a configuration-divergence check needs.

    Args:
        sections: Parsed sections.
        separator: Separator between section and key.

    Returns:
        Flat mapping such as ``{"Section.Key": "value"}``.
    """
    flattened: dict[str, Any] = {}
    for section, values in sections.items():
        for key, value in values.items():
            flattened[f"{section}{separator}{key}"] = value
    return flattened
