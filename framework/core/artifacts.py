"""Artifact storage and metadata.

An artifact is any file a run produces or retains: logs, JSON documents,
configuration snapshots, database copies, and -- in later phases -- screenshots and
recordings. Every artifact carries execution id, timestamp, module, source, and
checksum, so an artifact found on disk months later can still be attributed and
integrity-checked.

Artifacts are written beneath the run's output root and never outside it: a
component that could write anywhere could overwrite the reference evidence in
``baselines/`` that defines what "correct" looks like.

``HTML`` and ``PDF`` are declared as kinds but **not rendered** here. Phase 1.5
delivers the artifact system, not report renderers; a :class:`Reporter`
implementation produces those in a later phase.
"""

from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from framework.shared.exceptions import ArtifactError
from framework.shared.logger import get_logger
from framework.shared.models import utc_now
from framework.shared.utils import datetime_utils, filesystem, hashing, json_utils

__all__ = ["ArtifactKind", "ArtifactRecord", "ArtifactManager"]

_LOGGER = get_logger(__name__)


class ArtifactKind(Enum):
    """Categories of artifact the framework stores.

    ``HTML`` and ``PDF`` are placeholders: the kind exists so a renderer can
    register its output later without changing this enum, but nothing in the
    framework produces them yet.
    """

    LOG = "log"
    JSON = "json"
    TEXT = "text"
    HTML = "html"
    PDF = "pdf"
    SCREENSHOT = "screenshot"
    VIDEO = "video"
    DATABASE_COPY = "database_copy"
    CONFIG_SNAPSHOT = "config_snapshot"
    OTHER = "other"

    @property
    def is_placeholder(self) -> bool:
        """Whether the framework can produce this kind yet.

        ``True`` for kinds reserved for later phases. An artifact of a placeholder
        kind may still be *registered* by external code; the framework simply does
        not generate one itself.
        """
        return self in (
            ArtifactKind.HTML,
            ArtifactKind.PDF,
            ArtifactKind.SCREENSHOT,
            ArtifactKind.VIDEO,
        )

    @property
    def default_suffix(self) -> str:
        """Conventional file suffix for this kind."""
        return {
            ArtifactKind.LOG: ".log",
            ArtifactKind.JSON: ".json",
            ArtifactKind.TEXT: ".txt",
            ArtifactKind.HTML: ".html",
            ArtifactKind.PDF: ".pdf",
            ArtifactKind.SCREENSHOT: ".png",
            ArtifactKind.VIDEO: ".mp4",
            ArtifactKind.DATABASE_COPY: ".sqlite",
            ArtifactKind.CONFIG_SNAPSHOT: ".json",
            ArtifactKind.OTHER: "",
        }[self]


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    """Metadata describing a stored artifact.

    Args:
        artifact_id: Stable identifier, unique within a run.
        name: Display name.
        kind: Artifact category.
        path: Location on disk.
        execution_id: Run that produced it.
        created_at: Creation timestamp.
        module: Framework module or plugin that produced it.
        source: What it was derived from (a path, a component, a URL).
        checksum: Content digest.
        size_bytes: Size on disk.
        description: What the artifact shows.
        metadata: Additional detail.
    """

    artifact_id: str
    name: str
    kind: ArtifactKind
    path: Path
    execution_id: str
    created_at: Any = field(default_factory=utc_now)
    module: str = ""
    source: str = ""
    checksum: str = ""
    size_bytes: int = 0
    description: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "artifact_id": self.artifact_id,
            "name": self.name,
            "kind": self.kind.value,
            "path": str(self.path),
            "execution_id": self.execution_id,
            "created_at": datetime_utils.format_iso8601(self.created_at),
            "module": self.module,
            "source": self.source,
            "checksum": self.checksum,
            "size_bytes": self.size_bytes,
            "description": self.description,
            "metadata": dict(self.metadata),
        }

    def verify(self) -> bool:
        """Re-hash the file and compare against the recorded checksum.

        Returns:
            ``True`` if the file exists and its digest still matches.
        """
        if not self.path.is_file() or not self.checksum:
            return False
        try:
            return hashing.hash_file(self.path) == self.checksum
        except Exception:  # noqa: BLE001 -- unreadable means unverifiable
            return False


class ArtifactManager:
    """Stores artifacts and their metadata for one run.

    Thread-safe; artifacts may be produced concurrently by parallel units.
    """

    __slots__ = ("_root", "_execution_id", "_records", "_lock", "_counter")

    def __init__(self, root: Path | str, execution_id: str) -> None:
        """Initialise the manager.

        Args:
            root: Directory beneath which artifacts are stored. Created if absent.
            execution_id: Run identifier stamped onto every artifact.

        Raises:
            ArtifactError: If the root cannot be created.
        """
        try:
            self._root = filesystem.ensure_directory(Path(root) / "artifacts")
        except Exception as exc:  # noqa: BLE001 -- normalised to an artifact failure
            raise ArtifactError(
                "Artifact root could not be created", {"root": str(root)}
            ) from exc
        self._execution_id = execution_id
        self._records: dict[str, ArtifactRecord] = {}
        self._lock = threading.RLock()
        self._counter = 0

    @property
    def root(self) -> Path:
        """The directory artifacts are stored beneath."""
        return self._root

    def _next_id(self, kind: ArtifactKind) -> str:
        """Generate the next artifact identifier.

        Args:
            kind: Artifact category, included in the identifier for readability.

        Returns:
            An identifier such as ``"json-0003"``.
        """
        with self._lock:
            self._counter += 1
            return f"{kind.value}-{self._counter:04d}"

    def _destination(self, kind: ArtifactKind, name: str) -> Path:
        """Resolve a safe destination path for an artifact.

        Args:
            kind: Artifact category, used as a subdirectory.
            name: Proposed filename.

        Returns:
            The destination path, with the filename sanitised.
        """
        safe = filesystem.safe_filename(name)
        if not Path(safe).suffix and kind.default_suffix:
            safe = f"{safe}{kind.default_suffix}"
        return filesystem.ensure_directory(self._root / kind.value) / safe

    def _register(
        self,
        *,
        path: Path,
        name: str,
        kind: ArtifactKind,
        module: str,
        source: str,
        description: str,
        metadata: Mapping[str, Any] | None,
    ) -> ArtifactRecord:
        """Create and store the metadata record for a written file.

        Args:
            path: The written file.
            name: Display name.
            kind: Artifact category.
            module: Producing module or plugin.
            source: What it derives from.
            description: What it shows.
            metadata: Additional detail.

        Returns:
            The stored record.

        Raises:
            ArtifactError: If the file cannot be hashed or measured.
        """
        if not filesystem.is_within(path, self._root):
            raise ArtifactError(
                "Refusing to register an artifact outside the artifact root",
                {"path": str(path), "root": str(self._root)},
            )
        try:
            checksum = hashing.hash_file(path)
        except Exception as exc:  # noqa: BLE001 -- normalised to an artifact failure
            raise ArtifactError(
                "Artifact could not be checksummed", {"path": str(path)}
            ) from exc
        record = ArtifactRecord(
            artifact_id=self._next_id(kind),
            name=name,
            kind=kind,
            path=path,
            execution_id=self._execution_id,
            module=module,
            source=source,
            checksum=checksum,
            size_bytes=filesystem.file_size(path),
            description=description,
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._records[record.artifact_id] = record
        _LOGGER.debug(
            "Artifact stored: %s (%s, %d bytes)",
            record.artifact_id,
            record.path.name,
            record.size_bytes,
        )
        return record

    def store_text(
        self,
        name: str,
        content: str,
        *,
        kind: ArtifactKind = ArtifactKind.TEXT,
        module: str = "",
        source: str = "",
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRecord:
        """Write text content as an artifact.

        Args:
            name: Filename.
            content: Text to write.
            kind: Artifact category.
            module: Producing module or plugin.
            source: What it derives from.
            description: What it shows.
            metadata: Additional detail.

        Returns:
            The stored record.

        Raises:
            ArtifactError: If writing fails.
        """
        destination = self._destination(kind, name)
        try:
            destination.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise ArtifactError(
                "Artifact could not be written", {"path": str(destination)}
            ) from exc
        return self._register(
            path=destination,
            name=name,
            kind=kind,
            module=module,
            source=source,
            description=description,
            metadata=metadata,
        )

    def store_json(
        self,
        name: str,
        payload: Any,
        *,
        module: str = "",
        source: str = "",
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRecord:
        """Write a value as a JSON artifact.

        Args:
            name: Filename.
            payload: Value to serialise.
            module: Producing module or plugin.
            source: What it derives from.
            description: What it shows.
            metadata: Additional detail.

        Returns:
            The stored record.

        Raises:
            ArtifactError: If serialisation or writing fails.
        """
        destination = self._destination(ArtifactKind.JSON, name)
        try:
            json_utils.write_json_file(destination, payload)
        except Exception as exc:  # noqa: BLE001 -- normalised to an artifact failure
            raise ArtifactError(
                "JSON artifact could not be written", {"path": str(destination)}
            ) from exc
        return self._register(
            path=destination,
            name=name,
            kind=ArtifactKind.JSON,
            module=module,
            source=source,
            description=description,
            metadata=metadata,
        )

    def store_file(
        self,
        source_path: Path | str,
        *,
        name: str | None = None,
        kind: ArtifactKind = ArtifactKind.OTHER,
        module: str = "",
        description: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> ArtifactRecord:
        """Copy an existing file in as an artifact.

        The original is copied, never moved: the framework must not disturb what it
        observes.

        Args:
            source_path: File to copy.
            name: Destination filename; the source's name when omitted.
            kind: Artifact category.
            module: Producing module or plugin.
            description: What it shows.
            metadata: Additional detail.

        Returns:
            The stored record.

        Raises:
            ArtifactError: If the source is missing or the copy fails.
        """
        origin = Path(source_path)
        if not origin.is_file():
            raise ArtifactError(
                "Artifact source file does not exist", {"path": str(origin)}
            )
        destination = self._destination(kind, name or origin.name)
        try:
            shutil.copy2(origin, destination)
        except OSError as exc:
            raise ArtifactError(
                "Artifact could not be copied",
                {"source": str(origin), "destination": str(destination)},
            ) from exc
        return self._register(
            path=destination,
            name=name or origin.name,
            kind=kind,
            module=module,
            source=str(origin),
            description=description,
            metadata=metadata,
        )

    def snapshot_configuration(
        self, configuration: Mapping[str, Any], *, module: str = "core.config"
    ) -> ArtifactRecord:
        """Store a configuration snapshot.

        A run's configuration determines its behaviour, so retaining it is what
        makes the run reproducible after the fact.

        Args:
            configuration: Resolved configuration values.
            module: Producing module.

        Returns:
            The stored record.

        Raises:
            ArtifactError: If the snapshot cannot be written.
        """
        return self.store_json(
            "configuration-snapshot",
            dict(configuration),
            module=module,
            source="resolved configuration",
            description="Configuration in force for this run",
            metadata={"kind_detail": ArtifactKind.CONFIG_SNAPSHOT.value},
        )

    def get(self, artifact_id: str) -> ArtifactRecord:
        """Return a stored record.

        Args:
            artifact_id: Identifier to look up.

        Returns:
            The record.

        Raises:
            ArtifactError: If the identifier is unknown.
        """
        with self._lock:
            try:
                return self._records[artifact_id]
            except KeyError as exc:
                raise ArtifactError(
                    "Unknown artifact identifier", {"artifact_id": artifact_id}
                ) from exc

    def all(self) -> tuple[ArtifactRecord, ...]:
        """Return every stored record, in creation order."""
        with self._lock:
            return tuple(self._records.values())

    def of_kind(self, kind: ArtifactKind) -> tuple[ArtifactRecord, ...]:
        """Return stored records of one kind.

        Args:
            kind: Category to filter by.

        Returns:
            Matching records.
        """
        return tuple(record for record in self.all() if record.kind is kind)

    def verify_all(self) -> dict[str, bool]:
        """Re-verify every artifact's checksum.

        Returns:
            A mapping of artifact id to whether it still verifies.
        """
        return {record.artifact_id: record.verify() for record in self.all()}

    def write_manifest(self) -> Path:
        """Write an index of every artifact.

        The manifest makes a run's output self-describing: a reader can enumerate
        and integrity-check the artifacts without the framework.

        Returns:
            Path to the written manifest.

        Raises:
            ArtifactError: If the manifest cannot be written.
        """
        payload = {
            "execution_id": self._execution_id,
            "generated_at": datetime_utils.format_iso8601(utc_now()),
            "artifact_count": len(self._records),
            "artifacts": [record.to_dict() for record in self.all()],
        }
        target = self._root / "manifest.json"
        try:
            return json_utils.write_json_file(target, payload)
        except Exception as exc:  # noqa: BLE001 -- normalised to an artifact failure
            raise ArtifactError(
                "Artifact manifest could not be written", {"path": str(target)}
            ) from exc
