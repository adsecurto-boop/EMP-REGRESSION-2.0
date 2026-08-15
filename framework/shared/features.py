"""Feature profile access.

A typed reader over ``config/features.json``: what each monitored EmpMonitor feature
requires, where its evidence should come from, and how well its mechanism is
currently established.

Profiles are **configuration, not code**. A feature whose interval changes, or whose
table is renamed, is a configuration edit -- and a feature whose mechanism becomes
better understood is a status change, not a rewrite.

The ``verification_status`` field is load-bearing in the same way the product
profile's ``verified`` flag is: a plugin validating a `Hypothesis` feature must not
report `FAILED` when it finds nothing, because it does not yet know what "nothing"
means for that feature. :meth:`FeatureProfile.absence_verdict` encodes that.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from framework.shared.exceptions import ConfigurationError
from framework.shared.logger import get_logger
from framework.shared.models import EvidenceLayer, Verdict

__all__ = ["VerificationStatus", "FeatureProfile", "FeatureProfileRegistry"]

_LOGGER = get_logger(__name__)


class VerificationStatus:
    """How well a feature's mechanism is established.

    The same vocabulary the knowledge base uses, so a feature's status and its
    underlying claims cannot drift apart.
    """

    VERIFIED = "Verified"
    PARTIALLY_VERIFIED = "Partially Verified"
    HYPOTHESIS = "Hypothesis"
    DEPRECATED = "Deprecated"


@dataclass(frozen=True, slots=True)
class FeatureProfile:
    """What is expected of one monitored feature.

    Args:
        feature_id: Plugin identifier, e.g. ``EM010_Screenshots``.
        name: Human-readable feature name.
        verification_status: How well the mechanism is established.
        required_configuration: Configuration keys the feature depends on.
        expected_upload_interval_key: Configuration key holding its interval.
        expected_dashboard_pages: Pages where results should appear (all unobserved).
        expected_runtime_components: Processes or services that implement it.
        expected_log_patterns: Configured log-pattern names that evidence it.
        expected_sqlite_tables: Tables where its data should land.
        expected_apis: API names that should carry its data.
        expected_validators: Validators a plugin should run.
        expected_evidence: Catalog identifiers a plugin should collect.
        expected_failure_modes: Candidate failure modes to look for.
        note: Provenance -- what is actually established and what is inferred.
    """

    feature_id: str
    name: str
    verification_status: str = VerificationStatus.HYPOTHESIS
    required_configuration: Sequence[str] = field(default_factory=tuple)
    expected_upload_interval_key: str | None = None
    expected_dashboard_pages: Sequence[str] = field(default_factory=tuple)
    expected_runtime_components: Sequence[str] = field(default_factory=tuple)
    expected_log_patterns: Sequence[str] = field(default_factory=tuple)
    expected_sqlite_tables: Sequence[str] = field(default_factory=tuple)
    expected_apis: Sequence[str] = field(default_factory=tuple)
    expected_validators: Sequence[str] = field(default_factory=tuple)
    expected_evidence: Sequence[str] = field(default_factory=tuple)
    expected_failure_modes: Sequence[str] = field(default_factory=tuple)
    note: str = ""

    @property
    def is_verified(self) -> bool:
        """Whether the feature's mechanism has been directly observed."""
        return self.verification_status == VerificationStatus.VERIFIED

    @property
    def is_hypothesis(self) -> bool:
        """Whether nothing about the feature's mechanism has been observed."""
        return self.verification_status == VerificationStatus.HYPOTHESIS

    @property
    def absence_verdict(self) -> Verdict:
        """The verdict to report when the feature's expected artifacts are absent.

        Returns:
            ``FAILED`` only for a ``Verified`` feature -- there, absence of a mechanism
            we have seen working is a real defect. Otherwise ``INCONCLUSIVE``: for a
            feature whose mechanism is inferred or unknown, absence more likely means
            the framework is looking in the wrong place than that the product is
            broken.
        """
        return Verdict.FAILED if self.is_verified else Verdict.INCONCLUSIVE

    @property
    def required_layers(self) -> tuple[EvidenceLayer, ...]:
        """Layers this profile implies, derived from what it expects.

        Derived rather than declared so a profile cannot claim a layer it gives no
        way to observe.
        """
        layers: set[EvidenceLayer] = set()
        if self.required_configuration or self.expected_upload_interval_key:
            layers.add(EvidenceLayer.CONFIGURATION)
        if self.expected_runtime_components or self.expected_sqlite_tables:
            layers.add(EvidenceLayer.RUNTIME)
        if self.expected_log_patterns or self.expected_apis:
            layers.add(EvidenceLayer.SYNCHRONIZATION)
        if self.expected_dashboard_pages:
            layers.add(EvidenceLayer.DASHBOARD)
        return tuple(sorted(layers))

    @property
    def observable_layers(self) -> tuple[EvidenceLayer, ...]:
        """Layers that can actually be observed today.

        Includes Layer 4 for plugins with implemented collectors (e.g. EM010_Screenshots).
        """
        if self.feature_id == "EM010_Screenshots":
            return self.required_layers
        return tuple(
            layer for layer in self.required_layers if layer is not EvidenceLayer.DASHBOARD
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "feature_id": self.feature_id,
            "name": self.name,
            "verification_status": self.verification_status,
            "required_configuration": list(self.required_configuration),
            "expected_upload_interval_key": self.expected_upload_interval_key,
            "expected_dashboard_pages": list(self.expected_dashboard_pages),
            "expected_runtime_components": list(self.expected_runtime_components),
            "expected_log_patterns": list(self.expected_log_patterns),
            "expected_sqlite_tables": list(self.expected_sqlite_tables),
            "expected_apis": list(self.expected_apis),
            "expected_validators": list(self.expected_validators),
            "expected_evidence": list(self.expected_evidence),
            "expected_failure_modes": list(self.expected_failure_modes),
            "required_layers": [layer.label for layer in self.required_layers],
            "observable_layers": [layer.label for layer in self.observable_layers],
            "absence_verdict": self.absence_verdict.value,
            "note": self.note,
        }

    @classmethod
    def from_config(cls, entry: Mapping[str, Any]) -> "FeatureProfile":
        """Build a profile from a configuration entry.

        Args:
            entry: The configured mapping.

        Returns:
            The profile.

        Raises:
            ConfigurationError: If the entry has no feature identifier.
        """
        feature_id = str(entry.get("feature_id") or "").strip()
        if not feature_id:
            raise ConfigurationError(
                "Feature profile has no feature_id", {"entry": repr(entry)[:120]}
            )
        return cls(
            feature_id=feature_id,
            name=str(entry.get("name") or feature_id),
            verification_status=str(
                entry.get("verification_status") or VerificationStatus.HYPOTHESIS
            ),
            required_configuration=tuple(entry.get("required_configuration", ()) or ()),
            expected_upload_interval_key=entry.get("expected_upload_interval_key"),
            expected_dashboard_pages=tuple(entry.get("expected_dashboard_pages", ()) or ()),
            expected_runtime_components=tuple(
                entry.get("expected_runtime_components", ()) or ()
            ),
            expected_log_patterns=tuple(entry.get("expected_log_patterns", ()) or ()),
            expected_sqlite_tables=tuple(entry.get("expected_sqlite_tables", ()) or ()),
            expected_apis=tuple(entry.get("expected_apis", ()) or ()),
            expected_validators=tuple(entry.get("expected_validators", ()) or ()),
            expected_evidence=tuple(entry.get("expected_evidence", ()) or ()),
            expected_failure_modes=tuple(entry.get("expected_failure_modes", ()) or ()),
            note=str(entry.get("note") or ""),
        )


class FeatureProfileRegistry:
    """Loads and provides access to the feature profiles."""

    __slots__ = ("_profiles", "_source")

    def __init__(self, profiles: Sequence[FeatureProfile] = (), *, source: str = "") -> None:
        """Initialise the registry.

        Args:
            profiles: Profiles to register.
            source: Where they were loaded from, for reporting.

        Raises:
            ConfigurationError: If two profiles share a feature identifier.
        """
        self._profiles: dict[str, FeatureProfile] = {}
        for profile in profiles:
            if profile.feature_id in self._profiles:
                raise ConfigurationError(
                    "Duplicate feature profile", {"feature_id": profile.feature_id}
                )
            self._profiles[profile.feature_id] = profile
        self._source = source

    def __len__(self) -> int:
        return len(self._profiles)

    def __contains__(self, feature_id: object) -> bool:
        return isinstance(feature_id, str) and feature_id in self._profiles

    @property
    def source(self) -> str:
        """Where the profiles were loaded from."""
        return self._source

    @classmethod
    def load(cls, path: Path | str | None = None) -> "FeatureProfileRegistry":
        """Load profiles from disk.

        Args:
            path: Profile file. Defaults to ``config/features.json`` relative to the
                repository root, derived from this module's location so behaviour does
                not depend on the working directory.

        Returns:
            The registry. A missing file yields an empty registry with a warning
            rather than an error: a deployment with no feature profiles yet is not
            broken, it is just early.

        Raises:
            ConfigurationError: If the file exists but is malformed.
        """
        target = (
            Path(path)
            if path is not None
            else Path(__file__).resolve().parents[2] / "config" / "features.json"
        )
        if not target.is_file():
            _LOGGER.warning("No feature profile file found at %s", target)
            return cls(source=str(target))
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigurationError(
                "Feature profile file could not be read", {"path": str(target)}
            ) from exc
        entries = payload.get("profiles") if isinstance(payload, Mapping) else None
        if not isinstance(entries, Sequence):
            raise ConfigurationError(
                "Feature profile file must contain a 'profiles' list",
                {"path": str(target)},
            )
        profiles = [
            FeatureProfile.from_config(entry)
            for entry in entries
            if isinstance(entry, Mapping)
        ]
        _LOGGER.debug("Loaded %d feature profile(s) from %s", len(profiles), target)
        return cls(profiles, source=str(target))

    def get(self, feature_id: str) -> FeatureProfile:
        """Return one profile.

        Args:
            feature_id: Identifier to look up.

        Returns:
            The profile.

        Raises:
            ConfigurationError: If no profile is registered for the identifier.
        """
        try:
            return self._profiles[feature_id]
        except KeyError as exc:
            raise ConfigurationError(
                "No feature profile is registered for this feature",
                {"feature_id": feature_id, "known": sorted(self._profiles)},
            ) from exc

    def all(self) -> tuple[FeatureProfile, ...]:
        """Return every profile, ordered by feature identifier."""
        return tuple(self._profiles[key] for key in sorted(self._profiles))

    def by_status(self, status: str) -> tuple[FeatureProfile, ...]:
        """Return profiles with a given verification status.

        Args:
            status: Status to filter by.

        Returns:
            Matching profiles.
        """
        return tuple(
            profile for profile in self.all() if profile.verification_status == status
        )

    def status_counts(self) -> dict[str, int]:
        """Tally profiles by verification status.

        Returns:
            A mapping covering every status, so a zero is explicit.
        """
        counts = {
            status: 0
            for status in (
                VerificationStatus.VERIFIED,
                VerificationStatus.PARTIALLY_VERIFIED,
                VerificationStatus.HYPOTHESIS,
                VerificationStatus.DEPRECATED,
            )
        }
        for profile in self.all():
            counts[profile.verification_status] = (
                counts.get(profile.verification_status, 0) + 1
            )
        return counts
