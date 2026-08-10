"""Reusable, dependency-light utility helpers.

Each submodule owns one concern:

============================  ===============================================
:mod:`~.filesystem`           Path and file operations
:mod:`~.datetime_utils`       Timezone-aware UTC time handling
:mod:`~.version`              Version parsing and comparison
:mod:`~.hashing`              Artifact identity and integrity digests
:mod:`~.retry`                Bounded retry for the framework's own operations
:mod:`~.json_utils`           JSON serialisation of framework types
:mod:`~.ini_utils`            Generic INI parsing
:mod:`~.sqlite_utils`         Generic read-only SQLite inspection
:mod:`~.http_utils`           Generic HTTP transport
:mod:`~.windows`              Host OS inspection: services, processes, clock, registry
============================  ===============================================

Everything here is generic. No submodule contains EmpMonitor paths, schemas,
endpoints, or behaviour -- product knowledge belongs to collectors and plugins
built in later phases, reaching them through configuration.

Submodules are imported explicitly (``from framework.shared.utils import
hashing``) rather than re-exported symbol-by-symbol, so that call sites read
``hashing.hash_file(...)`` and the origin of a helper is obvious.
"""

from __future__ import annotations

from framework.shared.utils import (
    datetime_utils,
    filesystem,
    hashing,
    http_utils,
    ini_utils,
    json_utils,
    retry,
    sqlite_utils,
    version,
    windows,
)

__all__ = [
    "datetime_utils",
    "filesystem",
    "hashing",
    "http_utils",
    "ini_utils",
    "json_utils",
    "retry",
    "sqlite_utils",
    "version",
    "windows",
]
