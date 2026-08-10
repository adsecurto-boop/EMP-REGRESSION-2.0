"""Product configuration collection and validation (EV-001, EV-002, EV-016).

Reads the product's own configuration -- ``empm.ini``, ``config.js``, and any
documented registry values -- as Layer 1 evidence of *intent*: what the product has
been told to do.

**Secrets are never recorded.** A configuration file for a monitoring agent holds
credentials: on the reference installation ``empm.ini`` carries an ``auth`` section
with an email address and a stored credential. This collector records that such a
key is **present and non-empty**, never its value, and never its length beyond a
coarse indication. Keys listed in the profile's ``secret_keys`` are redacted before
evidence is constructed, so no downstream component -- report, artifact, or log --
can leak what was never captured (``docs/ADS/logging_standard.md`` §8).

Layer 1 alone proves intent, not behaviour. Findings here are therefore paired with
Layer 2 reality by :mod:`framework.validators.runtime`; this module concludes only
about configuration's own integrity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from framework.shared.interfaces import Collector, Validator
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    Finding,
    SourceReliability,
    ValidationContext,
    Verdict,
)
from framework.shared.profile import Expectation, ProductProfile
from framework.shared.utils import filesystem, ini_utils, windows

__all__ = [
    "ConfigurationCollector",
    "ConfigurationValidator",
    "EV_AGENT_CONFIG",
    "EV_USER_CONFIG",
    "EV_REGISTRY",
]

_LOGGER = get_logger(__name__)

EV_AGENT_CONFIG = "EV-001"
EV_USER_CONFIG = "EV-002"
EV_REGISTRY = "EV-016"

_REDACTED = "<present, value not recorded>"
_URL_RE = re.compile(r"\b(?:https?|wss?)://[^\s\"',;)]+", re.IGNORECASE)
_ROLE_EVIDENCE = {
    "agent_configuration": EV_AGENT_CONFIG,
    "user_configuration": EV_USER_CONFIG,
}


def _redact(value: Any) -> str:
    """Reduce a value to a presence indicator.

    Args:
        value: The value observed.

    Returns:
        A redaction marker when the value is non-empty, or an explicit empty
        marker. The value itself never survives this function.
    """
    text = "" if value is None else str(value)
    return _REDACTED if text.strip() else "<present, empty>"


class ConfigurationCollector(Collector):
    """Collects product configuration as Layer 1 evidence."""

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile describing the configuration files.
        """
        self._profile = profile

    @property
    def name(self) -> str:
        """Component name."""
        return "configuration.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.CONFIGURATION

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_AGENT_CONFIG, EV_USER_CONFIG, EV_REGISTRY)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect configuration evidence.

        Args:
            context: Run context.

        Returns:
            Evidence for each configured file and registry value.
        """
        collected = [
            self._collect_file(expectation)
            for expectation in self._profile.configuration_files()
        ]
        collected.extend(self._collect_registry(entry) for entry in self._profile.registry_keys())
        return tuple(item for item in collected if item is not None)

    def _collect_file(self, expectation: Expectation) -> Evidence:
        """Read one configuration file.

        Args:
            expectation: The file expectation.

        Returns:
            Evidence describing the file's presence and key inventory.
        """
        evidence_id = _ROLE_EVIDENCE.get(expectation.role, EV_USER_CONFIG)
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
            "format": str(expectation.extra.get("format") or ""),
        }

        if located is None:
            return self._evidence(
                evidence_id,
                expectation,
                f"{expectation.display_names} not found",
                data,
            )

        data.update(
            {
                "size_bytes": filesystem.file_size(located),
                "permissions": windows.path_permissions(located),
            }
        )
        fmt = str(expectation.extra.get("format") or "").lower()
        if fmt == "ini":
            data.update(self._read_ini(located, expectation))
        else:
            data.update(self._read_text(located, expectation))

        return self._evidence(
            evidence_id,
            expectation,
            f"{located.name} present at {located} "
            f"({data.get('key_count', 0)} key(s) observed)",
            data,
        )

    def _read_ini(self, path: Path, expectation: Expectation) -> dict[str, Any]:
        """Read an INI configuration file, redacting secret values.

        Args:
            path: File to read.
            expectation: The expectation, naming secret and role keys.

        Returns:
            Structured detail: section/key inventory with redacted values, plus
            per-role key presence.
        """
        try:
            sections = ini_utils.read_ini_file(path)
        except Exception as exc:  # noqa: BLE001 -- unreadable file is an observation
            return {"parse_error": str(exc), "key_count": 0, "state": "unreadable"}

        secret_keys = {
            str(item).lower() for item in expectation.extra.get("secret_keys", ()) or ()
        }
        flat = ini_utils.flatten_ini(sections, separator="/")
        recorded: dict[str, str] = {}
        for key, value in flat.items():
            recorded[key] = (
                _redact(value)
                if key.lower() in secret_keys
                else str(value)[:200]
            )
        return {
            "sections": sorted(sections),
            "keys": sorted(flat),
            "key_count": len(flat),
            "values": recorded,
            "redacted_keys": sorted(key for key in flat if key.lower() in secret_keys),
            "roles": self._role_presence(expectation, flat),
        }

    def _read_text(self, path: Path, expectation: Expectation) -> dict[str, Any]:
        """Read a non-INI configuration file.

        ``config.js`` is JavaScript, not JSON, so it is not parsed as structured
        data. Endpoint URLs are extracted because they are the load-bearing fact for
        later Layer 3 work; nothing else is interpreted, and no attempt is made to
        guess at key semantics that have not been verified.

        Args:
            path: File to read.
            expectation: The file expectation.

        Returns:
            Structured detail about the file.
        """
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"parse_error": str(exc), "key_count": 0, "state": "unreadable"}

        urls = sorted(set(_URL_RE.findall(text)))
        return {
            "line_count": len(text.splitlines()),
            "endpoints": urls,
            "endpoint_count": len(urls),
            "schemes": sorted({url.split("://", 1)[0].lower() for url in urls}),
            "key_count": len(urls),
            "content_recorded": False,
            "roles": {},
        }

    @staticmethod
    def _role_presence(
        expectation: Expectation, flat: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Report which role-specific keys are present.

        Presence, not value: a validator needs to know that authentication *is*
        configured, never what the credential is.

        Args:
            expectation: The expectation, naming role key groups.
            flat: Flattened configuration keys.

        Returns:
            A mapping of role name to presence detail.
        """
        lowered = {key.lower(): value for key, value in flat.items()}
        roles: dict[str, Any] = {}
        for group in (
            "authentication_keys",
            "tracking_keys",
            "screenshot_keys",
            "recording_keys",
            "upload_interval_keys",
            "feature_flag_keys",
            "identifier_keys",
        ):
            configured = [str(item) for item in expectation.extra.get(group, ()) or ()]
            if not configured:
                roles[group] = {"configured": False, "present": None, "keys": []}
                continue
            present = [key for key in configured if key.lower() in lowered]
            non_empty = [
                key
                for key in present
                if str(lowered.get(key.lower(), "")).strip()
            ]
            roles[group] = {
                "configured": True,
                "expected": configured,
                "keys": present,
                "present": len(present) == len(configured),
                "non_empty": len(non_empty) == len(configured),
            }
        return roles

    def _collect_registry(self, entry: Mapping[str, Any]) -> Evidence | None:
        """Read one configured registry value.

        Args:
            entry: Configured registry expectation.

        Returns:
            Evidence describing the read, or ``None`` when the entry is malformed.
        """
        root = str(entry.get("root") or "")
        key_path = str(entry.get("key") or "")
        if not root or not key_path:
            return None
        outcome = windows.read_registry_value(root, key_path, entry.get("value_name"))
        secret = bool(entry.get("secret", False))
        recorded = dict(outcome)
        if secret and recorded.get("value") is not None:
            recorded["value"] = _redact(recorded["value"])
        return Evidence(
            evidence_id=EV_REGISTRY,
            layer=EvidenceLayer.CONFIGURATION,
            source=f"registry:{root}\\{key_path}",
            summary=(
                f"registry value {'found' if outcome.get('found') else 'not found'}: "
                f"{root}\\{key_path}"
            ),
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data={
                **recorded,
                "state": "present" if outcome.get("found") else "absent",
                "required": bool(entry.get("required", False)),
                "verified_name": bool(entry.get("verified", False)),
            },
        )

    def _evidence(
        self,
        evidence_id: str,
        expectation: Expectation,
        summary: str,
        data: dict[str, Any],
    ) -> Evidence:
        """Build a configuration evidence record.

        Args:
            evidence_id: Catalog identifier for this source.
            expectation: The expectation observed.
            summary: Human-readable statement.
            data: Structured detail, already redacted.

        Returns:
            The evidence.
        """
        return Evidence(
            evidence_id=evidence_id,
            layer=EvidenceLayer.CONFIGURATION,
            source=f"configuration:{expectation.role}",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data=data,
        )


class ConfigurationValidator(Validator):
    """Concludes on the integrity of the product's own configuration."""

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the validator.

        Args:
            profile: Product profile describing the expectations.
        """
        self._profile = profile

    @property
    def name(self) -> str:
        """Component name."""
        return "configuration.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate configuration evidence.

        Args:
            context: Run context carrying collected evidence.

        Returns:
            Findings about configuration presence and integrity. Presence findings
            are Layer 1 only, so they never claim ``HEALTHY`` on their own --
            corroboration with Layer 2 is :mod:`framework.validators.runtime`'s job.
        """
        findings: list[Finding] = []
        for evidence in context.evidence:
            if evidence.layer is not EvidenceLayer.CONFIGURATION:
                continue
            if evidence.evidence_id == EV_REGISTRY:
                findings.extend(self._validate_registry(evidence, context))
                continue
            findings.extend(self._validate_file(evidence, context))
        return tuple(findings)

    def _validate_file(
        self, evidence: Evidence, context: ValidationContext
    ) -> Sequence[Finding]:
        """Check one configuration file's presence and integrity.

        Args:
            evidence: Configuration evidence.
            context: Run context.

        Returns:
            Findings about the file.
        """
        data = evidence.data
        role = str(data.get("role") or "configuration")
        required = bool(data.get("required", True))
        verified_name = bool(data.get("verified_name", False))

        if data.get("state") == "absent":
            if not required:
                return ()
            return (
                Finding.build(
                    what=f"{role} file not found",
                    where_layer=EvidenceLayer.CONFIGURATION,
                    where_component=f"configuration:{role}",
                    why=(
                        "the file is absent from every configured location"
                        if verified_name
                        else Finding.UNDETERMINED
                    ),
                    evidence=[evidence],
                    verdict=Verdict.FAILED if verified_name else Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    where_artifact=", ".join(str(item) for item in data.get("candidates", ())),
                    failure_class=None if not verified_name else _configuration_defect(),
                    upstream_evidenced=False,
                    notes=(
                        ()
                        if verified_name
                        else (
                            "Inconclusive rather than failed: this file's name and "
                            "location are unverified, so absence may mean the framework "
                            "looked in the wrong place.",
                        )
                    ),
                ),
            )

        if data.get("state") == "unreadable" or data.get("parse_error"):
            return (
                Finding.build(
                    what=f"{role} file could not be parsed",
                    where_layer=EvidenceLayer.CONFIGURATION,
                    where_component=f"configuration:{role}",
                    why=str(data.get("parse_error") or Finding.UNDETERMINED),
                    evidence=[evidence],
                    verdict=Verdict.FAILED,
                    failure_class=_configuration_defect(),
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    upstream_evidenced=False,
                ),
            )

        findings: list[Finding] = []
        roles = data.get("roles") or {}
        authentication = roles.get("authentication_keys") or {}
        if authentication.get("configured") and not authentication.get("non_empty"):
            findings.append(
                Finding.build(
                    what="authentication is not fully configured in the agent configuration",
                    where_layer=EvidenceLayer.CONFIGURATION,
                    where_component=f"configuration:{role}",
                    why="one or more expected authentication keys is missing or empty",
                    evidence=[evidence],
                    verdict=Verdict.FAILED,
                    failure_class=_configuration_defect(),
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    upstream_evidenced=False,
                    notes=(
                        "Key presence only; no credential value was read or recorded.",
                    ),
                )
            )
        return tuple(findings)

    def _validate_registry(
        self, evidence: Evidence, context: ValidationContext
    ) -> Sequence[Finding]:
        """Check one registry expectation.

        Args:
            evidence: Registry evidence.
            context: Run context.

        Returns:
            Findings about the registry value.
        """
        data = evidence.data
        if data.get("found") or not data.get("required"):
            return ()
        verified = bool(data.get("verified_name", False))
        return (
            Finding.build(
                what="expected registry value not found",
                where_layer=EvidenceLayer.CONFIGURATION,
                where_component="registry",
                why=str(data.get("error") or Finding.UNDETERMINED),
                evidence=[evidence],
                verdict=Verdict.FAILED if verified else Verdict.INCONCLUSIVE,
                failure_class=_configuration_defect() if verified else None,
                minimum_layers=context.minimum_layers,
                plugin_id=context.plugin_id,
                upstream_evidenced=False,
            ),
        )


def _configuration_defect() -> Any:
    """Return the configuration failure class.

    Imported lazily to keep this module's import list to the contracts it needs.

    Returns:
        The ``CONFIGURATION_DEFECT`` failure class.
    """
    from framework.shared.models import FailureClass  # noqa: PLC0415

    return FailureClass.CONFIGURATION_DEFECT
