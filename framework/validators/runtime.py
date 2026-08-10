"""Runtime state validation, corroborated against configured intent.

This is where the Validation Standard's central rule becomes concrete. A positive
conclusion needs at least two layers with one at Layer 2 or higher
(``docs/ADS/validation_standard.md`` §5.1), so every healthy finding here pairs
**Layer 1 intent** ("configuration says this feature is on") with **Layer 2
reality** ("the process that implements it is running").

That pairing is not a formality. "The service is running" alone cannot distinguish
a correctly-running agent from one running with tracking switched off, and
"configuration says tracking is on" alone proves only intent. Only together do they
support a conclusion -- which is exactly why the standard demands both.

Negative findings follow §5.2: the finding names the first diverging layer and, where
upstream state could be evidenced, records that it was sound. Where it could not,
``upstream_evidenced`` is ``False`` and the engine lowers confidence accordingly
rather than the validator overstating what it knows.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from framework.shared.interfaces import Validator
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    FailureClass,
    Finding,
    ValidationContext,
    Verdict,
)
from framework.shared.profile import ProductProfile

__all__ = ["RuntimeValidator"]

_LOGGER = get_logger(__name__)


class RuntimeValidator(Validator):
    """Concludes on installation and runtime state, corroborated with configuration."""

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the validator.

        Args:
            profile: Product profile describing expectations and thresholds.
        """
        self._profile = profile

    @property
    def name(self) -> str:
        """Component name."""
        return "runtime.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate runtime evidence against configured intent.

        Args:
            context: Run context carrying collected evidence.

        Returns:
            Findings about installation, executables, services, processes, storage,
            and disk space.
        """
        by_source: dict[str, Evidence] = {item.source: item for item in context.evidence}
        configuration = tuple(
            item for item in context.evidence if item.layer is EvidenceLayer.CONFIGURATION
        )

        findings: list[Finding] = []
        findings.extend(self._validate_installation(by_source, context))
        findings.extend(self._validate_executables(context))
        findings.extend(self._validate_services(context, configuration))
        findings.extend(self._validate_processes(context, configuration))
        findings.extend(self._validate_database(context, configuration))
        findings.extend(self._validate_folders(context))
        findings.extend(self._validate_disk(by_source, context))
        return tuple(findings)

    # -- installation ----------------------------------------------------------

    def _validate_installation(
        self, by_source: Mapping[str, Evidence], context: ValidationContext
    ) -> Sequence[Finding]:
        """Check that the product is installed at all.

        Args:
            by_source: Evidence indexed by source.
            context: Run context.

        Returns:
            A ``BLOCKED`` finding when no installation root exists, otherwise none.
            Absent installation blocks rather than fails: with nothing installed
            there is no product to conclude anything about.
        """
        evidence = by_source.get("installation root")
        if evidence is None or evidence.data.get("state") == "present":
            return ()
        verified = self._profile.install_roots_verified
        return (
            Finding.build(
                what="EmpMonitor installation root not found",
                where_layer=EvidenceLayer.RUNTIME,
                where_component="installation",
                why=(
                    "no configured installation root exists on this host"
                    if verified
                    else Finding.UNDETERMINED
                ),
                evidence=[evidence],
                verdict=Verdict.BLOCKED,
                minimum_layers=context.minimum_layers,
                plugin_id=context.plugin_id,
                where_artifact=", ".join(evidence.data.get("searched", ())[:4]),
                notes=(
                    "Blocked, not failed: nothing downstream can be validated without an "
                    "installation, so no product verdict is claimed.",
                ),
            ),
        )

    # -- executables -----------------------------------------------------------

    def _validate_executables(self, context: ValidationContext) -> Sequence[Finding]:
        """Check each expected executable is present.

        Args:
            context: Run context.

        Returns:
            Findings for missing required executables.
        """
        findings: list[Finding] = []
        for evidence in self._of_kind(context, "executable:"):
            data = evidence.data
            if data.get("state") == "present" or not data.get("required", True):
                continue
            verified = bool(data.get("verified_name", False))
            findings.append(
                Finding.build(
                    what=f"required executable not found: {self._names(data)}",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component=f"executable:{data.get('role')}",
                    why=(
                        "the file is absent from every searched location"
                        if verified
                        else Finding.UNDETERMINED
                    ),
                    evidence=[evidence],
                    verdict=Verdict.FAILED if verified else Verdict.INCONCLUSIVE,
                    failure_class=FailureClass.CAPTURE_RUNTIME_DEFECT if verified else None,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    upstream_evidenced=False,
                    notes=self._unverified_note(verified, str(data.get("note") or "")),
                )
            )
        return tuple(findings)

    # -- services --------------------------------------------------------------

    def _validate_services(
        self, context: ValidationContext, configuration: Sequence[Evidence]
    ) -> Sequence[Finding]:
        """Check each expected service is installed and in its expected state.

        Args:
            context: Run context.
            configuration: Layer 1 evidence, used to corroborate a healthy verdict.

        Returns:
            Findings for each service.
        """
        findings: list[Finding] = []
        for evidence in self._of_kind(context, "service:"):
            data = evidence.data
            role = str(data.get("role"))
            required = bool(data.get("required", True))
            verified = bool(data.get("verified_name", False))

            if not data.get("found"):
                if not required:
                    continue
                findings.append(
                    Finding.build(
                        what=f"required Windows service not installed: {self._names(data, 'queried_names')}",
                        where_layer=EvidenceLayer.RUNTIME,
                        where_component=f"service:{role}",
                        why=(
                            "the service is not registered with the service control manager"
                            if verified
                            else Finding.UNDETERMINED
                        ),
                        evidence=[evidence],
                        verdict=Verdict.FAILED if verified else Verdict.INCONCLUSIVE,
                        failure_class=FailureClass.CAPTURE_RUNTIME_DEFECT if verified else None,
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                        upstream_evidenced=False,
                        notes=self._unverified_note(verified, ""),
                    )
                )
                continue

            expected_state = str(data.get("expected_state") or "RUNNING").upper()
            actual = str(data.get("reported_state") or "").upper()
            if expected_state in actual:
                # Healthy needs corroboration: pair this L2 observation with L1
                # configuration evidence so the finding spans two layers.
                findings.append(
                    Finding.build(
                        what=f"Windows service {data.get('service_name')} is running as expected",
                        where_layer=EvidenceLayer.RUNTIME,
                        where_component=f"service:{role}",
                        why="service state matches the configured expectation",
                        evidence=self._corroborated([evidence], configuration),
                        verdict=Verdict.HEALTHY
                        if configuration
                        else Verdict.INCONCLUSIVE,
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                        notes=(
                            ()
                            if configuration
                            else (
                                "No Layer 1 evidence was available to corroborate this "
                                "observation, so it cannot support a positive verdict.",
                            )
                        ),
                    )
                )
                continue

            findings.append(
                Finding.build(
                    what=f"Windows service {data.get('service_name')} is not running",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component=f"service:{role}",
                    why=f"service reports state {actual or 'unknown'}, expected {expected_state}",
                    evidence=self._corroborated([evidence], configuration),
                    verdict=Verdict.FAILED,
                    failure_class=FailureClass.CAPTURE_RUNTIME_DEFECT,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    upstream_evidenced=bool(configuration),
                )
            )
        return tuple(findings)

    # -- processes -------------------------------------------------------------

    def _validate_processes(
        self, context: ValidationContext, configuration: Sequence[Evidence]
    ) -> Sequence[Finding]:
        """Check each expected process is running.

        Args:
            context: Run context.
            configuration: Layer 1 evidence, used to corroborate a healthy verdict.

        Returns:
            Findings for each process.
        """
        findings: list[Finding] = []
        for evidence in self._of_kind(context, "process:"):
            data = evidence.data
            role = str(data.get("role"))
            running = data.get("state") == "running"
            required = bool(data.get("required", True))
            verified = bool(data.get("verified_name", False))

            if running:
                findings.append(
                    Finding.build(
                        what=f"{self._names(data)} is running",
                        where_layer=EvidenceLayer.RUNTIME,
                        where_component=f"process:{role}",
                        why="process is present with the expected image name",
                        evidence=self._corroborated([evidence], configuration),
                        verdict=Verdict.HEALTHY if configuration else Verdict.INCONCLUSIVE,
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                        notes=(
                            ()
                            if configuration
                            else (
                                "Process presence alone is single-layer evidence and "
                                "cannot support a positive verdict.",
                            )
                        ),
                    )
                )
                continue

            if not required:
                # An optional process being idle is expected behaviour, not an
                # anomaly: the recorder runs only while recording.
                continue

            if not data.get("host_process_count"):
                findings.append(
                    Finding.build(
                        what=f"could not determine whether {self._names(data)} is running",
                        where_layer=EvidenceLayer.RUNTIME,
                        where_component=f"process:{role}",
                        why="the host process list could not be read",
                        evidence=[evidence],
                        verdict=Verdict.INCONCLUSIVE,
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                    )
                )
                continue

            findings.append(
                Finding.build(
                    what=f"required process is not running: {self._names(data)}",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component=f"process:{role}",
                    why=(
                        "no process with the expected image name was found among "
                        f"{data.get('host_process_count')} running processes"
                        if verified
                        else Finding.UNDETERMINED
                    ),
                    evidence=self._corroborated([evidence], configuration),
                    verdict=Verdict.FAILED if verified else Verdict.INCONCLUSIVE,
                    failure_class=FailureClass.CAPTURE_RUNTIME_DEFECT if verified else None,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    upstream_evidenced=bool(configuration),
                    notes=self._unverified_note(verified, str(data.get("note") or "")),
                )
            )
        return tuple(findings)

    # -- storage ---------------------------------------------------------------

    def _validate_database(
        self, context: ValidationContext, configuration: Sequence[Evidence]
    ) -> Sequence[Finding]:
        """Check the local database exists and is usable.

        Args:
            context: Run context.
            configuration: Layer 1 evidence for corroboration.

        Returns:
            Findings about the database.
        """
        findings: list[Finding] = []
        for evidence in self._of_kind(context, "local database"):
            data = evidence.data
            state = data.get("state")
            verified = bool(data.get("verified_name", False))

            if state == "present":
                minimum = int(
                    (self._profile.database().extra.get("min_expected_tables", 1))
                    if self._profile.database()
                    else 1
                )
                tables = int(data.get("table_count") or 0)
                if tables >= minimum:
                    findings.append(
                        Finding.build(
                            what="local database is present and readable",
                            where_layer=EvidenceLayer.RUNTIME,
                            where_component="storage:database",
                            why=f"database opened read-only with {tables} table(s)",
                            evidence=self._corroborated([evidence], configuration),
                            verdict=Verdict.HEALTHY if configuration else Verdict.INCONCLUSIVE,
                            minimum_layers=context.minimum_layers,
                            plugin_id=context.plugin_id,
                        )
                    )
                else:
                    findings.append(
                        Finding.build(
                            what="local database has fewer tables than expected",
                            where_layer=EvidenceLayer.RUNTIME,
                            where_component="storage:database",
                            why=f"observed {tables} table(s), expected at least {minimum}",
                            evidence=self._corroborated([evidence], configuration),
                            verdict=Verdict.DEGRADED,
                            minimum_layers=context.minimum_layers,
                            plugin_id=context.plugin_id,
                        )
                    )
                continue

            if state == "unreadable":
                findings.append(
                    Finding.build(
                        what="local database exists but could not be read",
                        where_layer=EvidenceLayer.RUNTIME,
                        where_component="storage:database",
                        why=str(data.get("error") or "the database could not be opened"),
                        evidence=self._corroborated([evidence], configuration),
                        verdict=Verdict.FAILED,
                        failure_class=FailureClass.PERSISTENCE_DEFECT,
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                        upstream_evidenced=bool(configuration),
                        notes=(
                            "A locked database may simply be in use by the agent; "
                            "re-observe before treating this as durable.",
                        ),
                    )
                )
                continue

            findings.append(
                Finding.build(
                    what="local database not found",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component="storage:database",
                    why=(
                        "no file matching the configured patterns exists"
                        if verified
                        else Finding.UNDETERMINED
                    ),
                    evidence=[evidence],
                    verdict=Verdict.FAILED if verified else Verdict.INCONCLUSIVE,
                    failure_class=FailureClass.PERSISTENCE_DEFECT if verified else None,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    upstream_evidenced=False,
                    notes=self._unverified_note(verified, ""),
                )
            )
        return tuple(findings)

    def _validate_folders(self, context: ValidationContext) -> Sequence[Finding]:
        """Check each expected storage folder.

        Args:
            context: Run context.

        Returns:
            Findings for missing required folders.
        """
        findings: list[Finding] = []
        for evidence in self._of_kind(context, "folder:"):
            data = evidence.data
            if data.get("state") == "present" or not data.get("required", True):
                continue
            verified = bool(data.get("verified_name", False))
            role = str(data.get("role"))
            configured = bool(data.get("candidates"))
            findings.append(
                Finding.build(
                    what=f"expected {role} folder not found",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component=f"storage:{role}",
                    why=(
                        "the folder is absent from every searched location"
                        if verified
                        else Finding.UNDETERMINED
                    ),
                    evidence=[evidence],
                    verdict=Verdict.FAILED if verified else Verdict.INCONCLUSIVE,
                    failure_class=FailureClass.PERSISTENCE_DEFECT if verified else None,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    upstream_evidenced=False,
                    notes=tuple(
                        note
                        for note in (
                            str(data.get("note") or ""),
                            ""
                            if configured
                            else "No candidate folder name is configured, so nothing "
                            "could be looked for; supply the name once it is verified.",
                            ""
                            if verified
                            else "Inconclusive rather than failed: the folder name is "
                            "unverified, and for a failure-holding folder absence may "
                            "simply mean nothing has failed.",
                        )
                        if note
                    ),
                )
            )
        return tuple(findings)

    def _validate_disk(
        self, by_source: Mapping[str, Evidence], context: ValidationContext
    ) -> Sequence[Finding]:
        """Check free disk space against the configured minimum.

        Args:
            by_source: Evidence indexed by source.
            context: Run context.

        Returns:
            Findings about disk space.
        """
        evidence = by_source.get("disk space")
        if evidence is None:
            return ()
        free_mb = evidence.data.get("free_mb")
        minimum = float(self._profile.threshold("min_free_disk_mb", 500))
        if free_mb is None:
            return (
                Finding.build(
                    what="free disk space could not be determined",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component="storage:disk",
                    why=Finding.UNDETERMINED,
                    evidence=[evidence],
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                ),
            )
        if float(free_mb) < minimum:
            return (
                Finding.build(
                    what="free disk space is below the configured minimum",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component="storage:disk",
                    why=f"{free_mb:.0f} MB free, minimum {minimum:.0f} MB",
                    evidence=[evidence],
                    verdict=Verdict.DEGRADED,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Degraded rather than failed: capture continues until the volume "
                        "actually fills, but persistence is at risk.",
                    ),
                ),
            )
        return ()

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _of_kind(context: ValidationContext, prefix: str) -> tuple[Evidence, ...]:
        """Return evidence whose source starts with a prefix.

        Args:
            context: Run context.
            prefix: Source prefix to match.

        Returns:
            Matching evidence, in collection order.
        """
        return tuple(item for item in context.evidence if item.source.startswith(prefix))

    @staticmethod
    def _corroborated(
        primary: Sequence[Evidence], configuration: Sequence[Evidence]
    ) -> tuple[Evidence, ...]:
        """Combine a Layer 2 observation with Layer 1 configuration evidence.

        Corroboration must be *independent*: the configuration evidence comes from a
        different collector reading a different artifact, which is what §4.1
        requires. Only one configuration item is attached -- adding more would inflate
        the apparent breadth of support without adding an independent layer.

        Args:
            primary: The Layer 2 observation.
            configuration: Available Layer 1 evidence.

        Returns:
            The combined evidence.
        """
        return tuple(primary) + (tuple(configuration[:1]) if configuration else ())

    @staticmethod
    def _names(data: Mapping[str, Any], key: str = "candidates") -> str:
        """Render an expectation's candidate names for a message.

        Args:
            data: Evidence data.
            key: Which key holds the names.

        Returns:
            A readable name list.
        """
        names = [str(item) for item in data.get(key, ()) or ()]
        return " or ".join(names) if names else str(data.get("role") or "component")

    @staticmethod
    def _unverified_note(verified: bool, note: str) -> tuple[str, ...]:
        """Build the explanatory notes for an unmet expectation.

        Args:
            verified: Whether the expectation's name was verified.
            note: A profile-supplied note, if any.

        Returns:
            The notes to attach to the finding.
        """
        notes = [note] if note else []
        if not verified:
            notes.append(
                "Inconclusive rather than failed: this expectation's name is unverified "
                "(Hypothesis status), so absence may mean the framework looked in the "
                "wrong place rather than that the component is missing."
            )
        return tuple(notes)
