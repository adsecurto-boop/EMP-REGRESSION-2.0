"""Read-only SQLite access helpers.

Generic transport only. This module can open and inspect *any* SQLite file; it
carries no knowledge of any particular schema.

Two boundaries are deliberate and must be preserved:

1. **Read-only.** Connections are opened with ``mode=ro`` so the framework
   cannot mutate a database it is observing. The framework observes the product,
   it never modifies it (``docs/FRAMEWORK_MANIFEST.md`` §14).
2. **No product knowledge.** EmpMonitor's database location and schema are
   unverified (``knowledge_base/RE-007``) and reading them is Phase 3 work. The
   SQLite *monitor* built then will use these helpers; that monitor, not this
   module, owns any schema expectations.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from framework.shared.exceptions import FrameworkError

__all__ = [
    "open_readonly",
    "list_tables",
    "table_columns",
    "row_count",
    "fetch_all",
    "database_is_readable",
]


@contextmanager
def open_readonly(
    path: Path | str, *, timeout: float = 5.0
) -> Iterator[sqlite3.Connection]:
    """Open a SQLite database read-only.

    Uses SQLite URI mode so the read-only guarantee is enforced by the driver
    rather than by convention. A short timeout is applied because a database
    being actively written by the product may be briefly locked -- waiting
    forever would hang a run.

    Args:
        path: Database file.
        timeout: Seconds to wait for a lock.

    Yields:
        An open read-only connection with :class:`sqlite3.Row` rows.

    Raises:
        FrameworkError: If the file is missing or cannot be opened.
    """
    target = Path(path)
    if not target.is_file():
        raise FrameworkError("SQLite database not found", {"path": str(target)})
    uri = f"file:{target.as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=timeout)
    except sqlite3.Error as exc:
        raise FrameworkError(
            "SQLite database could not be opened read-only", {"path": str(target)}
        ) from exc
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def database_is_readable(path: Path | str) -> bool:
    """Whether a database exists and can be opened read-only.

    Args:
        path: Database file.

    Returns:
        ``True`` if it opened successfully. Returns ``False`` rather than raising
        because "not readable" is a normal observation for a collector to make
        and report, not a framework failure.
    """
    try:
        with open_readonly(path) as connection:
            connection.execute("SELECT 1").fetchone()
    except (FrameworkError, sqlite3.Error):
        return False
    return True


def list_tables(connection: sqlite3.Connection) -> tuple[str, ...]:
    """List user table names.

    Internal ``sqlite_%`` tables are excluded as they are engine implementation
    detail, not observable product state.

    Args:
        connection: An open connection.

    Returns:
        Table names in alphabetical order.

    Raises:
        FrameworkError: If the query fails.
    """
    try:
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    except sqlite3.Error as exc:
        raise FrameworkError("Table list could not be read") from exc
    return tuple(str(row["name"]) for row in rows)


def table_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    """List a table's column names.

    Args:
        connection: An open connection.
        table: Table name.

    Returns:
        Column names in declaration order.

    Raises:
        FrameworkError: If the table does not exist or cannot be inspected.
    """
    if table not in list_tables(connection):
        raise FrameworkError("Table does not exist", {"table": table})
    try:
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    except sqlite3.Error as exc:
        raise FrameworkError("Table columns could not be read", {"table": table}) from exc
    return tuple(str(row["name"]) for row in rows)


def row_count(connection: sqlite3.Connection, table: str) -> int:
    """Count rows in a table.

    Args:
        connection: An open connection.
        table: Table name.

    Returns:
        The row count.

    Raises:
        FrameworkError: If the table does not exist or cannot be counted.
    """
    if table not in list_tables(connection):
        raise FrameworkError("Table does not exist", {"table": table})
    try:
        row = connection.execute(f'SELECT COUNT(*) AS total FROM "{table}"').fetchone()
    except sqlite3.Error as exc:
        raise FrameworkError("Rows could not be counted", {"table": table}) from exc
    return int(row["total"])


def fetch_all(
    connection: sqlite3.Connection,
    query: str,
    parameters: Sequence[Any] = (),
    *,
    limit: int | None = None,
) -> tuple[dict[str, Any], ...]:
    """Run a read query and return rows as dictionaries.

    Args:
        connection: An open connection.
        query: SQL query. Parameterise values via ``parameters`` rather than
            string formatting.
        parameters: Query parameters.
        limit: Optional cap on returned rows, to bound memory when a table is
            unexpectedly large.

    Returns:
        Result rows as dictionaries.

    Raises:
        FrameworkError: If the query fails.
    """
    try:
        cursor = connection.execute(query, tuple(parameters))
        rows = cursor.fetchmany(limit) if limit is not None else cursor.fetchall()
    except sqlite3.Error as exc:
        raise FrameworkError("Query failed", {"query": query}) from exc
    return tuple(dict(row) for row in rows)
