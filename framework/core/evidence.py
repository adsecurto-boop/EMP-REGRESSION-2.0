"""Evidence collection and retention.

The store is the run's audit trail. Every finding cites evidence, and a report
must be able to resolve those citations to retained artifacts
(``docs/ADS/validation_standard.md`` §10 rule 5).

Two rules from the frozen architecture are enforced here rather than left to
convention:

1. **Only registered sources are admissible.** Evidence citing an ``EV-NNN`` not
   present in the configured catalog mirror is rejected
   (``docs/Evidence_Catalog.md`` §1). This is what stops ad-hoc, untraceable
   evidence entering a report.
2. **Artifacts are retained under the run's output root**, keeping run output
   (``reports/``) distinct from canonical reference evidence (``baselines/``).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from framework.shared.exceptions import EvidenceError
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    EvidenceSourceSpec,
    SourceReliability,
)
from framework.shared.utils import filesystem, hashing

__all__ = ["EvidenceStore", "EvidenceCatalog", "build_catalog_from_config"]

_LOGGER = get_logger(__name__)


class EvidenceCatalog:
    """The registered evidence sources available to a run.

    A machine-readable mirror of ``docs/Evidence_Catalog.md``, supplied through
    configuration. Because it is configuration rather than code, registering a
    new source never requires a code change (``Evidence_Catalog.md`` §6).

    The document remains authoritative for humans; this mirror is authoritative
    for the running framework. Keeping the two in step is a review obligation.
    """

    __slots__ = ("_sources",)

    def __init__(self, sources: Iterable[EvidenceSourceSpec] = ()) -> None:
        """Initialise the catalog.

        Args:
            sources: Source specifications to register.

        Raises:
            EvidenceError: If two specifications share an identifier.
        """
        self._sources: dict[str, EvidenceSourceSpec] = {}
        for spec in sources:
            if spec.evidence_id in self._sources:
                raise EvidenceError(
                    "Duplicate evidence source identifier",
                    {"evidence_id": spec.evidence_id},
                )
            self._sources[spec.evidence_id] = spec

    def __contains__(self, evidence_id: object) -> bool:
        return isinstance(evidence_id, str) and evidence_id in self._sources

    def __len__(self) -> int:
        return len(self._sources)

    @property
    def source_ids(self) -> tuple[str, ...]:
        """Registered identifiers, in sorted order."""
        return tuple(sorted(self._sources))

    def get(self, evidence_id: str) -> EvidenceSourceSpec:
        """Return a registered source specification.

        Args:
            evidence_id: Catalog identifier.

        Returns:
            The specification.

        Raises:
            EvidenceError: If the identifier is not registered.
        """
        try:
            return self._sources[evidence_id]
        except KeyError as exc:
            raise EvidenceError(
                "Evidence source is not registered in the catalog",
                {"evidence_id": evidence_id, "registered": len(self._sources)},
            ) from exc

    def for_layer(self, layer: EvidenceLayer) -> tuple[EvidenceSourceSpec, ...]:
        """Return registered sources serving one layer.

        Args:
            layer: Layer to filter by.

        Returns:
            Matching specifications, sorted by identifier.
        """
        return tuple(
            spec for spec in sorted(self._sources.values(), key=lambda item: item.evidence_id)
            if spec.layer is layer
        )

    def implemented_layers(self) -> tuple[EvidenceLayer, ...]:
        """Return layers that have at least one implemented collector.

        Layers registered but not yet collectable (notably L3, whose collector is
        designed but unimplemented) are excluded, so coverage reporting reflects
        reality rather than intent.

        Returns:
            Layers with a working collector, in layer order.
        """
        return tuple(
            sorted({spec.layer for spec in self._sources.values() if spec.implemented})
        )


def build_catalog_from_config(entries: Sequence[Mapping[str, Any]]) -> EvidenceCatalog:
    """Build a catalog from configuration entries.

    Args:
        entries: Sequence of mappings with ``id``, ``name``, ``layer``,
            ``reliability``, and optional ``collector``/``implemented`` keys.

    Returns:
        The populated catalog.

    Raises:
        EvidenceError: If an entry is malformed or names an unknown layer or
            reliability.
    """
    specs: list[EvidenceSourceSpec] = []
    for entry in entries:
        try:
            layer = EvidenceLayer(int(entry["layer"]))
            reliability = SourceReliability[str(entry["reliability"]).upper()]
            specs.append(
                EvidenceSourceSpec(
                    evidence_id=str(entry["id"]),
                    name=str(entry["name"]),
                    layer=layer,
                    reliability=reliability,
                    collector=str(entry.get("collector", "")),
                    implemented=bool(entry.get("implemented", False)),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise EvidenceError(
                "Evidence catalog entry is malformed", {"entry": repr(entry)}
            ) from exc
    return EvidenceCatalog(specs)


class EvidenceStore:
    """Collects, validates, and retains evidence for one run.

    Thread-safe, because monitors may sample concurrently with plugin execution.
    """

    __slots__ = ("_catalog", "_evidence", "_artifact_root", "_lock", "_strict")

    def __init__(
        self,
        catalog: EvidenceCatalog | None = None,
        *,
        artifact_root: Path | None = None,
        strict: bool = True,
    ) -> None:
        """Initialise the store.

        Args:
            catalog: Registered sources. An empty catalog with ``strict`` set
                would reject everything, so ``strict`` is ignored when no
                catalog is supplied.
            artifact_root: Directory beneath which artifacts are retained.
            strict: Reject evidence whose source is not registered.
        """
        self._catalog = catalog or EvidenceCatalog()
        self._evidence: list[Evidence] = []
        self._artifact_root = artifact_root
        self._lock = threading.RLock()
        self._strict = strict and len(self._catalog) > 0

    @property
    def catalog(self) -> EvidenceCatalog:
        """The catalog this store validates against."""
        return self._catalog

    def add(self, evidence: Evidence) -> Evidence:
        """Record one piece of evidence.

        Args:
            evidence: Evidence to record.

        Returns:
            The recorded evidence, with source reliability filled in from the
            catalog when the caller left it at the default. Reliability is a
            property of the *source*, so taking it from the catalog rather than
            from the caller prevents a collector from overstating its own
            evidence.

        Raises:
            EvidenceError: If strict mode is on and the source is unregistered,
                or if the declared layer contradicts the catalog.
        """
        resolved = evidence
        if self._strict or evidence.evidence_id in self._catalog:
            spec = self._catalog.get(evidence.evidence_id)
            if spec.layer is not evidence.layer:
                raise EvidenceError(
                    "Evidence layer contradicts the registered source layer",
                    {
                        "evidence_id": evidence.evidence_id,
                        "declared": evidence.layer.label,
                        "registered": spec.layer.label,
                    },
                )
            if evidence.reliability is SourceReliability.MEDIUM:
                resolved = Evidence(
                    evidence_id=evidence.evidence_id,
                    layer=evidence.layer,
                    source=evidence.source,
                    summary=evidence.summary,
                    collected_at=evidence.collected_at,
                    collector=evidence.collector or spec.collector,
                    reliability=spec.reliability,
                    artifact_path=evidence.artifact_path,
                    data=evidence.data,
                )
        with self._lock:
            self._evidence.append(resolved)
        _LOGGER.debug(
            "Evidence recorded: %s (%s) from %s",
            resolved.evidence_id,
            resolved.layer.label,
            resolved.collector or "unattributed",
        )
        return resolved

    def extend(self, evidence: Iterable[Evidence]) -> tuple[Evidence, ...]:
        """Record several pieces of evidence.

        Args:
            evidence: Evidence to record.

        Returns:
            The recorded evidence.

        Raises:
            EvidenceError: If any item is rejected. Recording is not atomic:
                earlier items remain, since partial evidence is still evidence.
        """
        return tuple(self.add(item) for item in evidence)

    def all(self) -> tuple[Evidence, ...]:
        """Return all recorded evidence in collection order."""
        with self._lock:
            return tuple(self._evidence)

    def for_layer(self, layer: EvidenceLayer) -> tuple[Evidence, ...]:
        """Return recorded evidence for one layer.

        Args:
            layer: Layer to filter by.

        Returns:
            Matching evidence.
        """
        return tuple(item for item in self.all() if item.layer is layer)

    def layers_covered(self) -> tuple[EvidenceLayer, ...]:
        """Return the distinct layers with recorded evidence, in layer order."""
        return tuple(sorted({item.layer for item in self.all()}))

    def retain_artifact(
        self, source_path: Path | str, *, subdirectory: str = "evidence"
    ) -> Path:
        """Copy an artifact into the run's output directory.

        Args:
            source_path: File to retain.
            subdirectory: Subdirectory beneath the artifact root.

        Returns:
            The retained artifact's path.

        Raises:
            EvidenceError: If no artifact root is configured, or the copy fails.
        """
        if self._artifact_root is None:
            raise EvidenceError(
                "No artifact root configured; cannot retain evidence artifacts"
            )
        destination = self._artifact_root / subdirectory
        try:
            return filesystem.copy_into(source_path, destination)
        except Exception as exc:  # noqa: BLE001 -- normalised to an evidence failure
            raise EvidenceError(
                "Evidence artifact could not be retained",
                {"source": str(source_path), "destination": str(destination)},
            ) from exc

    def fingerprint(self) -> str:
        """Return a stable digest of the recorded evidence.

        Lets two runs be compared for "did we observe the same thing" without
        diffing every artifact.

        Returns:
            A hex digest over the recorded evidence identities and summaries.
        """
        material = [
            {
                "id": item.evidence_id,
                "layer": int(item.layer),
                "source": item.source,
                "summary": item.summary,
            }
            for item in self.all()
        ]
        return hashing.hash_mapping({"evidence": material})
