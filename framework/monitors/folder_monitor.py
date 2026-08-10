"""File system artifact collection (EV-010).

Observes the product's on-disk footprint: installation root, expected folders,
process access rights, and free disk space. Locations come entirely from the
configured product profile -- no path is hardcoded.

Reports what it observed and where it looked. A "not found" result always carries
the searched locations, because absence is only meaningful alongside the places
that were checked (``docs/ADS/validation_standard.md`` §7 rule 4).
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
from framework.shared.profile import ProductProfile
from framework.shared.utils import windows

__all__ = ["FilesystemCollector", "EV_FILESYSTEM"]

_LOGGER = get_logger(__name__)

EV_FILESYSTEM = "EV-010"


class FilesystemCollector(Collector):
    """Collects installation, folder, permission, and disk evidence."""

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile describing where to look.
        """
        self._profile = profile

    @property
    def name(self) -> str:
        """Component name."""
        return "filesystem.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.RUNTIME

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_FILESYSTEM,)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect file system evidence.

        Args:
            context: Run context.

        Returns:
            Evidence for the installation root, the data root, each expected
            folder, and disk space.
        """
        collected: list[Evidence] = [
            self._collect_root("installation root", self._profile.install_roots()),
            self._collect_root("data root", self._profile.data_roots()),
        ]
        collected.extend(
            self._collect_folder(expectation)
            for expectation in self._profile.storage_folders()
        )
        if (disk := self._collect_disk()) is not None:
            collected.append(disk)
        return tuple(collected)

    def _evidence(
        self, source: str, summary: str, data: dict[str, Any]
    ) -> Evidence:
        """Build a filesystem evidence record.

        Args:
            source: What was observed.
            summary: Human-readable statement.
            data: Structured detail.

        Returns:
            The evidence.
        """
        return Evidence(
            evidence_id=EV_FILESYSTEM,
            layer=EvidenceLayer.RUNTIME,
            source=source,
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data=data,
        )

    def _collect_root(self, label: str, candidates: Sequence[Path]) -> Evidence:
        """Observe which of several candidate roots exists.

        Args:
            label: What the root is, for the evidence source.
            candidates: Candidate directories, in configured order.

        Returns:
            Evidence naming the located root, or recording that none existed.
        """
        located = next((path for path in candidates if path.is_dir()), None)
        permissions = windows.path_permissions(located) if located else {}
        entries: list[str] = []
        if located is not None:
            try:
                entries = sorted(item.name for item in located.iterdir())[:200]
            except OSError as exc:  # pragma: no cover -- unreadable directory
                _LOGGER.debug("Root not listable: %s (%s)", located, exc)
        return self._evidence(
            source=label,
            summary=(
                f"{label} located at {located}"
                if located
                else f"{label} not found in {len(candidates)} configured location(s)"
            ),
            data={
                "state": "present" if located else "absent",
                "path": str(located) if located else None,
                "searched": [str(path) for path in candidates],
                "permissions": permissions,
                "entry_count": len(entries),
                "entries": entries,
            },
        )

    def _collect_folder(self, expectation: Any) -> Evidence:
        """Observe an expected folder.

        Args:
            expectation: The folder expectation from the profile.

        Returns:
            Evidence naming the located folder, or recording that none matched,
            together with whether the expectation's name was verified.
        """
        located, searched = self._profile.locate(expectation)
        file_count: int | None = None
        if located is not None and located.is_dir():
            try:
                file_count = sum(1 for item in located.iterdir() if item.is_file())
            except OSError:  # pragma: no cover -- unreadable directory
                file_count = None
        return self._evidence(
            source=f"folder:{expectation.role}",
            summary=(
                f"{expectation.role} folder located at {located}"
                if located
                else f"{expectation.role} folder not found"
                + ("" if expectation.names else " (no candidate name configured)")
            ),
            data={
                "state": "present" if located else "absent",
                "role": expectation.role,
                "path": str(located) if located else None,
                "searched": [str(path) for path in searched],
                "candidates": list(expectation.names),
                "required": expectation.required,
                "verified_name": expectation.verified,
                "note": expectation.note,
                "file_count": file_count,
                "permissions": windows.path_permissions(located) if located else {},
            },
        )

    def _collect_disk(self) -> Evidence | None:
        """Observe free disk space on the volume holding the data root.

        Returns:
            Evidence describing free space, or ``None`` when no root exists to
            measure.
        """
        target = self._profile.existing_data_root() or self._profile.existing_install_root()
        if target is None:
            return None
        free = windows.disk_free_bytes(target)
        return self._evidence(
            source="disk space",
            summary=(
                f"{free / 1_048_576:.0f} MB free on the volume holding {target}"
                if free is not None
                else f"free space on {target} could not be determined"
            ),
            data={
                "state": "measured" if free is not None else "unmeasured",
                "path": str(target),
                "free_bytes": free,
                "free_mb": round(free / 1_048_576, 1) if free is not None else None,
            },
        )
