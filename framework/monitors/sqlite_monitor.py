"""Local SQLite database collection (EV-003).

Observes whether the product's local database exists, is readable, and carries a
plausible structure.

**Structure only, never contents.** The collector lists table names and row counts;
it does not read rows. The database holds captured monitoring data -- clipboard
contents, activity records, screenshots -- which is none of the framework's
business. Establishing that persistence *works* needs the shape of the store, not
the personal data inside it. Reads are opened read-only so the framework cannot
disturb what it observes.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Sequence

from framework.shared.interfaces import Collector
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    SourceReliability,
    ValidationContext,
)
from framework.shared.profile import ProductProfile
from framework.shared.utils import filesystem, sqlite_utils, windows

__all__ = ["SqliteCollector", "EV_SQLITE"]

_LOGGER = get_logger(__name__)

EV_SQLITE = "EV-003"


class SqliteCollector(Collector):
    """Collects local database presence and structure."""

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile describing where the database lives.
        """
        self._profile = profile

    @property
    def name(self) -> str:
        """Component name."""
        return "sqlite.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.RUNTIME

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_SQLITE,)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect database evidence.

        Args:
            context: Run context.

        Returns:
            Evidence describing the database, or an empty sequence when no
            database is configured -- nothing configured means nothing claimed.
        """
        expectation = self._profile.database()
        if expectation is None:
            return ()

        located, searched = self._profile.locate(expectation)
        data: dict[str, Any] = {
            "state": "present" if located else "absent",
            "patterns": list(expectation.names),
            "searched": [str(path) for path in searched],
            "required": expectation.required,
            "verified_name": expectation.verified,
            "path": str(located) if located else None,
        }

        if located is None:
            return (
                self._evidence(
                    "local database not found in any configured location", data
                ),
            )

        data.update(
            {
                "size_bytes": filesystem.file_size(located),
                "permissions": windows.path_permissions(located),
                "readable": sqlite_utils.database_is_readable(located),
            }
        )

        if not data["readable"]:
            data["state"] = "unreadable"
            return (
                self._evidence(
                    f"local database at {located} exists but could not be opened", data
                ),
            )

        try:
            with sqlite_utils.open_readonly(located) as connection:
                tables = sqlite_utils.list_tables(connection)
                # Row counts are structural: they establish that persistence is
                # happening without reading a single stored value.
                counts = {}
                for table in tables:
                    try:
                        counts[table] = sqlite_utils.row_count(connection, table)
                    except Exception:  # noqa: BLE001 -- one bad table must not stop the rest
                        counts[table] = None
        except Exception as exc:  # noqa: BLE001 -- normalised into an observation
            data["state"] = "unreadable"
            data["error"] = str(exc)
            return (
                self._evidence(f"local database at {located} could not be inspected", data),
            )

        populated = sum(1 for value in counts.values() if (value or 0) > 0)
        data.update(
            {
                "table_count": len(tables),
                "tables": list(tables),
                "row_counts": counts,
                "populated_table_count": populated,
                "total_rows": sum(value or 0 for value in counts.values()),
            }
        )
        return (
            self._evidence(
                f"local database at {located} readable with {len(tables)} table(s), "
                f"{populated} populated",
                data,
            ),
        )

    def _evidence(self, summary: str, data: dict[str, Any]) -> Evidence:
        """Build a database evidence record.

        Args:
            summary: Human-readable statement.
            data: Structured detail.

        Returns:
            The evidence.
        """
        return Evidence(
            evidence_id=EV_SQLITE,
            layer=EvidenceLayer.RUNTIME,
            source="local database",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data=data,
        )
