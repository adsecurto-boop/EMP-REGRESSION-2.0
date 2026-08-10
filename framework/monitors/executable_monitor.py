"""Executable file metadata collection (EV-013).

Observes the identity of the product's executables: resolved path, size,
modification time, content hash, version resource, and Authenticode signature.

Hashing gives an executable a stable identity, which is what lets one run be
compared with another or with a retained baseline. Signature and version status are
read where the host will report them and recorded as ``None`` where it will not --
"unreadable" is distinct from "unsigned", and conflating the two would turn a
missing capability into a false accusation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from framework.shared.interfaces import Collector
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    SourceReliability,
    ValidationContext,
)
from framework.shared.profile import Expectation, ProductProfile
from framework.shared.utils import filesystem, hashing, windows

__all__ = ["ExecutableCollector", "EV_EXECUTABLE"]

_LOGGER = get_logger(__name__)

EV_EXECUTABLE = "EV-013"


class ExecutableCollector(Collector):
    """Collects metadata for each expected executable."""

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile describing which executables to look for.
        """
        self._profile = profile

    @property
    def name(self) -> str:
        """Component name."""
        return "executable.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.RUNTIME

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_EXECUTABLE,)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect executable metadata.

        Args:
            context: Run context.

        Returns:
            One piece of evidence per configured executable, including those that
            were not found.
        """
        hash_enabled = bool(self._profile.collection_setting("hash_executables", True))
        signatures_enabled = bool(self._profile.collection_setting("collect_signatures", True))
        timeout = float(self._profile.collection_setting("command_timeout_seconds", 20))
        return tuple(
            self._collect_one(
                expectation,
                hash_enabled=hash_enabled,
                signatures_enabled=signatures_enabled,
                timeout=timeout,
            )
            for expectation in self._profile.executables()
        )

    def _collect_one(
        self,
        expectation: Expectation,
        *,
        hash_enabled: bool,
        signatures_enabled: bool,
        timeout: float,
    ) -> Evidence:
        """Collect metadata for one executable.

        Args:
            expectation: What to look for.
            hash_enabled: Whether to compute a content hash.
            signatures_enabled: Whether to read the Authenticode signature.
            timeout: Seconds to allow per external command.

        Returns:
            Evidence describing the executable, or its absence.
        """
        located, searched = self._profile.locate(expectation)
        data: dict[str, Any] = {
            "state": "present" if located else "absent",
            "role": expectation.role,
            "candidates": list(expectation.names),
            "searched": [str(path) for path in searched],
            "required": expectation.required,
            "verified_name": expectation.verified,
            "note": expectation.note,
            "path": str(located) if located else None,
        }

        if located is None:
            return self._evidence(expectation, f"{expectation.display_names} not found", data)

        size = filesystem.file_size(located)
        data.update(
            {
                "name": located.name,
                "size_bytes": size,
                "modified_at": self._modified_at(located),
                "permissions": windows.path_permissions(located),
            }
        )
        if hash_enabled:
            try:
                data["sha256"] = hashing.hash_file(located)
            except Exception as exc:  # noqa: BLE001 -- unreadable file is an observation
                data["sha256"] = None
                data["hash_error"] = str(exc)
        version = windows.file_version_info(located, timeout=timeout)
        data["version"] = version
        if signatures_enabled:
            data["signature"] = windows.file_signature(located, timeout=timeout)

        summary = (
            f"{located.name} present at {located} "
            f"({size} bytes, version {version.get('file_version') or 'unknown'})"
        )
        return self._evidence(expectation, summary, data)

    @staticmethod
    def _modified_at(path: Path) -> str | None:
        """Return a file's modification time as an ISO 8601 UTC string.

        Args:
            path: File to inspect.

        Returns:
            The timestamp, or ``None`` if unreadable.
        """
        from datetime import datetime, timezone  # noqa: PLC0415 -- local to this helper

        try:
            return datetime.fromtimestamp(
                path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
        except OSError:
            return None

    def _evidence(
        self, expectation: Expectation, summary: str, data: dict[str, Any]
    ) -> Evidence:
        """Build an executable evidence record.

        Args:
            expectation: The expectation observed.
            summary: Human-readable statement.
            data: Structured detail.

        Returns:
            The evidence.
        """
        return Evidence(
            evidence_id=EV_EXECUTABLE,
            layer=EvidenceLayer.RUNTIME,
            source=f"executable:{expectation.role}",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data=data,
        )
