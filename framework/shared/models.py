"""Framework data models -- the machine-readable form of the ratified contracts.

This module is the single source of truth in code for the contracts frozen in
``docs/ADS/validation_standard.md`` v1.0. In particular:

* :class:`EvidenceLayer` -- the four evidence layers (§3)
* :class:`Verdict` -- the verdict set and its precedence rules (§6)
* :class:`Confidence` -- the five confidence levels (§8.1)
* :class:`FailureClass` -- the failure taxonomy (§9)
* :class:`Evidence` / :class:`Finding` -- the finding structure (§10)

The rules encoded here are deliberately *mechanical*: confidence is computed
from evidence rather than asserted (§8.2), and a ``HEALTHY`` verdict cannot be
constructed without satisfying corroboration (§5.1). Making the contract hard
to violate in code is the point -- a standard that lives only in prose drifts.

Models are frozen dataclasses. Immutability matters because evidence is an
audit trail: a collected observation must not be editable after the fact by
whatever consumes it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping, Sequence

from framework.shared.constants import (
    EVIDENCE_ID_PATTERN,
    MIN_CORROBORATING_LAYERS,
    PLUGIN_ID_PATTERN,
)
from framework.shared.exceptions import ValidationError

__all__ = [
    "EvidenceLayer",
    "Verdict",
    "Confidence",
    "FailureClass",
    "SourceReliability",
    "EvidenceSourceSpec",
    "Evidence",
    "EvidenceConflict",
    "Finding",
    "ExecutionStatus",
    "ExecutionResult",
    "PluginMetadata",
    "ValidationContext",
    "EnvironmentInfo",
    "AgentInfo",
    "DashboardInfo",
    "utc_now",
]

_EVIDENCE_ID_RE = re.compile(EVIDENCE_ID_PATTERN)
_PLUGIN_ID_RE = re.compile(PLUGIN_ID_PATTERN)


def utc_now() -> datetime:
    """Return the current time as a timezone-aware UTC timestamp.

    Centralised so every model timestamps consistently. Naive datetimes are
    never used: a run may span hosts and timezones, and evidence correlation
    depends on unambiguous ordering.
    """
    return datetime.now(timezone.utc)


class EvidenceLayer(IntEnum):
    """The four evidence layers (``validation_standard.md`` §3).

    ``IntEnum`` because the layers are ordered and that order is meaningful:
    the layer at which evidence first diverges localises the fault (§3.1), and
    corroboration requires at least one layer at L2 or higher (§5.1).
    """

    CONFIGURATION = 1
    """L1 -- is the feature *supposed* to be doing this?"""

    RUNTIME = 2
    """L2 -- is the endpoint *actually* doing it?"""

    SYNCHRONIZATION = 3
    """L3 -- is the result *reaching* the server?"""

    DASHBOARD = 4
    """L4 -- is the result *visible and correct* to the user?"""

    @property
    def label(self) -> str:
        """Return the short display label, e.g. ``"L2"``."""
        return f"L{self.value}"


class Verdict(Enum):
    """Validation verdicts (``validation_standard.md`` §6).

    The framework never emits a bare pass/fail. Precedence between verdicts is
    implemented by :meth:`aggregate`.
    """

    HEALTHY = "HEALTHY"
    """Corroborated across the required layers."""

    DEGRADED = "DEGRADED"
    """Functioning, but with corroborated anomalies."""

    FAILED = "FAILED"
    """Divergence localised to a specific layer with supporting evidence."""

    INCONCLUSIVE = "INCONCLUSIVE"
    """Insufficient independent evidence -- neither a pass nor a failure."""

    BLOCKED = "BLOCKED"
    """Preconditions not met; validation did not run."""

    @property
    def is_conclusive(self) -> bool:
        """Whether this verdict represents a reached conclusion."""
        return self in (Verdict.HEALTHY, Verdict.DEGRADED, Verdict.FAILED)

    @classmethod
    def aggregate(cls, verdicts: Iterable["Verdict"]) -> "Verdict":
        """Combine verdicts according to the ratified precedence rules.

        Per §6: ``BLOCKED`` preempts everything (if validation could not run,
        nothing else may be claimed); ``FAILED`` preempts ``DEGRADED``; and an
        ``INCONCLUSIVE`` result may never be upgraded or downgraded away by
        aggregation -- a roll-up containing one must surface it.

        The ordering below encodes exactly that: ``BLOCKED`` first, then
        ``FAILED``, then ``INCONCLUSIVE`` (so it outranks the positive verdicts
        and cannot be masked by them), then ``DEGRADED``, then ``HEALTHY``.

        Args:
            verdicts: Verdicts to combine.

        Returns:
            The precedent verdict, or :attr:`INCONCLUSIVE` if none were given
            (no evidence of anything is not a pass).
        """
        collected = list(verdicts)
        if not collected:
            return cls.INCONCLUSIVE
        for candidate in (cls.BLOCKED, cls.FAILED, cls.INCONCLUSIVE, cls.DEGRADED):
            if candidate in collected:
                return candidate
        return cls.HEALTHY


class Confidence(IntEnum):
    """Confidence levels (``validation_standard.md`` §8.1).

    Ordered so that monotonicity rules are expressible as comparisons: more
    independent corroboration never lowers confidence, and a conflict never
    raises it. Confidence is computed by :meth:`Finding.compute_confidence`,
    never asserted by a plugin (§8.2).
    """

    UNKNOWN = 0
    """Evidence could not be collected at all."""

    LOW = 1
    """Single-source support, or an unresolved conflict is present."""

    MEDIUM = 2
    """Corroboration met, but a contributing source is weak or upstream
    soundness could not be evidenced."""

    HIGH = 3
    """Two independent layers corroborate; no conflicts; primary source strong."""

    VERY_HIGH = 4
    """Three or more independent layers corroborate; no conflicts; all sources
    strong."""


class FailureClass(Enum):
    """Failure taxonomy for the product under validation (§9).

    Derived from the first diverging layer. This classifies failures of
    *EmpMonitor*; failures of the framework itself are exceptions from
    :mod:`framework.shared.exceptions` and must not be conflated with these.
    """

    CONFIGURATION_DEFECT = "CONFIGURATION_DEFECT"
    """L1 -- intent is wrong, missing, or contradictory."""

    CAPTURE_RUNTIME_DEFECT = "CAPTURE_RUNTIME_DEFECT"
    """L2 -- endpoint not doing what configuration intends."""

    PERSISTENCE_DEFECT = "PERSISTENCE_DEFECT"
    """L2 storage surfaces -- captured but not correctly persisted locally."""

    SYNCHRONIZATION_DEFECT = "SYNCHRONIZATION_DEFECT"
    """L3 -- persisted but not correctly reaching the server."""

    SURFACING_DEFECT = "SURFACING_DEFECT"
    """L4 -- server has it, dashboard shows it wrong or not at all."""

    @classmethod
    def from_layer(
        cls, layer: EvidenceLayer, *, storage_surface: bool = False
    ) -> "FailureClass":
        """Classify a failure from the layer at which evidence first diverged.

        Args:
            layer: The first diverging layer.
            storage_surface: Set when an L2 divergence concerns a persistence
                surface (local database/file system) rather than capture
                behaviour, to distinguish the two L2 classes in §9.

        Returns:
            The corresponding failure class.
        """
        if layer is EvidenceLayer.CONFIGURATION:
            return cls.CONFIGURATION_DEFECT
        if layer is EvidenceLayer.RUNTIME:
            return cls.PERSISTENCE_DEFECT if storage_surface else cls.CAPTURE_RUNTIME_DEFECT
        if layer is EvidenceLayer.SYNCHRONIZATION:
            return cls.SYNCHRONIZATION_DEFECT
        return cls.SURFACING_DEFECT


class SourceReliability(IntEnum):
    """Inherent reliability of an evidence *source* (Evidence Catalog §2.1).

    Distinct from :class:`Confidence`, which describes a *finding*. A source's
    reliability is one input to computing a finding's confidence.
    """

    LOW = 1
    """Inferred or absence-based; admissible only as corroboration."""

    MEDIUM = 2
    """Subject to rendering, timing, or interpretation."""

    HIGH = 3
    """Direct observation of a durable, structured artifact."""


@dataclass(frozen=True, slots=True)
class EvidenceSourceSpec:
    """Registration record for an evidence source, mirroring the catalog.

    The authoritative registry is ``docs/Evidence_Catalog.md``; this is the
    machine-readable mirror supplied through configuration so that adding a
    source is a configuration change, not a code change.

    Args:
        evidence_id: Catalog identifier, e.g. ``EV-003``.
        name: Source name as registered in the catalog.
        layer: The primary evidence layer this source serves.
        reliability: Inherent source reliability from the catalog rubric.
        collector: Name of the component responsible for collecting it.
        implemented: Whether a collector implementation exists yet. Sources may
            be registered before their collector is built (e.g. EV-007, whose
            collector is designed but unimplemented).
    """

    evidence_id: str
    name: str
    layer: EvidenceLayer
    reliability: SourceReliability
    collector: str = ""
    implemented: bool = False

    def __post_init__(self) -> None:
        """Validate the identifier shape.

        Raises:
            ValidationError: If ``evidence_id`` is not of the form ``EV-NNN``.
        """
        if not _EVIDENCE_ID_RE.match(self.evidence_id):
            raise ValidationError(
                "Evidence source identifier does not match the required EV-NNN form",
                {"evidence_id": self.evidence_id},
            )


@dataclass(frozen=True, slots=True)
class Evidence:
    """A single collected observation.

    Evidence is the atomic unit the whole validation model rests on: findings
    cite it, confidence is computed from it, and reports must resolve it. It is
    immutable once collected.

    Args:
        evidence_id: Evidence Catalog identifier (``EV-NNN``).
        layer: The layer this observation contributes to. A single observation
            contributes to exactly one layer, per the independence rule (§4.1).
        source: Concrete artifact/signal observed, e.g. a file path or a
            service name. Never a secret value.
        summary: Short human-readable statement of what was observed.
        collected_at: Timestamp of collection.
        collector: Name of the collecting component.
        reliability: Inherent reliability of the source, from its catalog entry.
        artifact_path: Optional path to a retained artifact under ``reports/``
            or ``baselines/``.
        data: Optional structured detail. Must not contain secrets.
    """

    evidence_id: str
    layer: EvidenceLayer
    source: str
    summary: str
    collected_at: datetime = field(default_factory=utc_now)
    collector: str = ""
    reliability: SourceReliability = SourceReliability.MEDIUM
    artifact_path: Path | None = None
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the evidence identifier shape.

        Raises:
            ValidationError: If ``evidence_id`` is not of the form ``EV-NNN``.
        """
        if not _EVIDENCE_ID_RE.match(self.evidence_id):
            raise ValidationError(
                "Evidence identifier does not match the required EV-NNN form",
                {"evidence_id": self.evidence_id},
            )


@dataclass(frozen=True, slots=True)
class EvidenceConflict:
    """A recorded disagreement between evidence sources (§7).

    Conflicts are never averaged away. An unresolved conflict caps a finding's
    confidence at :attr:`Confidence.LOW`, and if it concerns the claim itself
    the verdict becomes ``INCONCLUSIVE``.

    Args:
        description: What disagrees with what.
        left: One side of the disagreement.
        right: The other side.
        resolved_by: The §7 rule that resolved it, or ``None`` if unresolved.
    """

    description: str
    left: Evidence
    right: Evidence
    resolved_by: str | None = None

    @property
    def is_resolved(self) -> bool:
        """Whether a §7 rule resolved this conflict."""
        return self.resolved_by is not None


@dataclass(frozen=True, slots=True)
class Finding:
    """A structured validation result (``validation_standard.md`` §10).

    Every field required by §10 is present and, where the standard says
    "always", non-optional in practice: construction validates that evidence is
    present and that a ``HEALTHY`` verdict actually satisfies corroboration.

    Args:
        what: The observed defect, or the observed healthy behaviour.
        where_layer: Layer the finding concerns.
        where_component: Component the finding concerns.
        where_artifact: Specific artifact, if applicable.
        why: Causal finding. Use :data:`UNDETERMINED` when the cause could not
            be established -- never a guess.
        evidence: Supporting evidence; at least one item is required.
        verdict: The verdict reached.
        confidence: Computed confidence. Prefer :meth:`build`, which computes
            it, over passing a value directly.
        conflicts: Recorded evidence disagreements, if any.
        failure_class: Failure classification, required when ``verdict`` is
            ``FAILED``.
        upstream_evidenced: Whether the layer upstream of a divergence was
            evidenced as sound (§5.2). Affects computed confidence.
        plugin_id: Owning plugin identifier, when raised by a plugin.
        created_at: Timestamp.
        notes: Optional free-form annotations, e.g. a reason for lowering
            confidence below the computed value.
    """

    UNDETERMINED: ClassVar[str] = "undetermined"
    """Sentinel for ``why`` when the cause could not be established.

    Explicitly marking a cause undetermined is required by §10; guessing a
    plausible cause is the anti-pattern the standard forbids.
    """

    what: str
    where_layer: EvidenceLayer
    where_component: str
    why: str
    evidence: Sequence[Evidence]
    verdict: Verdict
    confidence: Confidence = Confidence.UNKNOWN
    where_artifact: str | None = None
    conflicts: Sequence[EvidenceConflict] = field(default_factory=tuple)
    failure_class: FailureClass | None = None
    upstream_evidenced: bool = True
    plugin_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    notes: Sequence[str] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Enforce the §10 structural requirements.

        Raises:
            ValidationError: If evidence is missing, if a ``HEALTHY`` verdict
                does not satisfy corroboration (§5.1), or if a ``FAILED``
                verdict lacks a failure classification (§9).
        """
        if not self.evidence:
            raise ValidationError(
                "A finding must cite at least one piece of evidence",
                {"what": self.what},
            )
        # §5.4 sets the same minimum for DEGRADED as for HEALTHY -- DEGRADED is a
        # positive conclusion ("functioning, with anomalies"), so it needs the same
        # corroboration. Enforcing only HEALTHY would leave the easier positive
        # verdict as an unguarded way to make an under-corroborated claim.
        if self.verdict in (Verdict.HEALTHY, Verdict.DEGRADED) and not self.satisfies_corroboration():
            raise ValidationError(
                f"A {self.verdict.value} verdict requires corroboration across at least "
                f"{MIN_CORROBORATING_LAYERS} layers with at least one at L2 or higher",
                {"what": self.what, "layers": [layer.label for layer in self.corroboration]},
            )
        if self.verdict is Verdict.FAILED and self.failure_class is None:
            raise ValidationError(
                "A FAILED verdict must carry a failure classification",
                {"what": self.what},
            )

    @property
    def corroboration(self) -> tuple[EvidenceLayer, ...]:
        """The distinct layers that contributed evidence, in layer order."""
        return tuple(sorted({item.layer for item in self.evidence}))

    @property
    def has_unresolved_conflict(self) -> bool:
        """Whether any recorded conflict remains unresolved."""
        return any(not conflict.is_resolved for conflict in self.conflicts)

    def satisfies_corroboration(self, minimum_layers: int = MIN_CORROBORATING_LAYERS) -> bool:
        """Whether the evidence meets the positive-conclusion rule (§5.1).

        Args:
            minimum_layers: Configured minimum, clamped to the ratified floor of
                two -- the standard permits tuning but never below two.

        Returns:
            ``True`` if enough distinct layers corroborate and at least one is
            L2 or higher.
        """
        required = max(minimum_layers, MIN_CORROBORATING_LAYERS)
        layers = self.corroboration
        if len(layers) < required:
            return False
        return any(layer >= EvidenceLayer.RUNTIME for layer in layers)

    def compute_confidence(
        self, minimum_layers: int = MIN_CORROBORATING_LAYERS
    ) -> Confidence:
        """Compute confidence mechanically from the evidence (§8.2).

        Confidence is derived from the number of independent corroborating
        layers, the reliability of the contributing sources, and the presence
        of unresolved conflicts. It is never asserted.

        Args:
            minimum_layers: Configured corroboration minimum.

        Returns:
            The computed confidence level.
        """
        if not self.evidence:
            return Confidence.UNKNOWN
        if self.verdict is Verdict.BLOCKED:
            return Confidence.UNKNOWN
        if self.has_unresolved_conflict:
            return Confidence.LOW

        layer_count = len(self.corroboration)
        if layer_count < max(minimum_layers, MIN_CORROBORATING_LAYERS):
            return Confidence.LOW

        reliabilities = [item.reliability for item in self.evidence]
        all_high = all(value is SourceReliability.HIGH for value in reliabilities)
        weakest = min(reliabilities)

        if layer_count >= 3 and all_high and self.upstream_evidenced:
            return Confidence.VERY_HIGH
        if weakest <= SourceReliability.MEDIUM or not self.upstream_evidenced:
            return Confidence.MEDIUM
        return Confidence.HIGH

    def with_confidence(self, confidence: Confidence, reason: str) -> "Finding":
        """Return a copy with confidence lowered and the reason recorded.

        Per §8.2 a plugin may lower a computed confidence with a recorded
        reason, but may never raise one.

        Args:
            confidence: The lower confidence level to apply.
            reason: Why it is being lowered. Required -- an unexplained
                downgrade is as opaque as an asserted one.

        Returns:
            A new finding with the lowered confidence and an appended note.

        Raises:
            ValidationError: If ``confidence`` is higher than the current value
                or ``reason`` is empty.
        """
        if confidence > self.confidence:
            raise ValidationError(
                "Confidence may be lowered but never raised",
                {"current": self.confidence.name, "requested": confidence.name},
            )
        if not reason.strip():
            raise ValidationError("Lowering confidence requires a recorded reason")
        return replace(
            self,
            confidence=confidence,
            notes=tuple(self.notes) + (f"confidence lowered: {reason}",),
        )

    @classmethod
    def build(
        cls,
        *,
        what: str,
        where_layer: EvidenceLayer,
        where_component: str,
        why: str,
        evidence: Sequence[Evidence],
        verdict: Verdict,
        minimum_layers: int = MIN_CORROBORATING_LAYERS,
        **kwargs: Any,
    ) -> "Finding":
        """Construct a finding with confidence computed rather than supplied.

        This is the preferred constructor: it guarantees the §8.2 rule that
        confidence is computed from evidence.

        Args:
            what: The observed defect or healthy behaviour.
            where_layer: Layer the finding concerns.
            where_component: Component the finding concerns.
            why: Causal finding, or :data:`UNDETERMINED`.
            evidence: Supporting evidence, at least one item.
            verdict: The verdict reached.
            minimum_layers: Configured corroboration minimum.
            **kwargs: Any other :class:`Finding` field.

        Returns:
            A finding whose ``confidence`` is computed from its evidence.
        """
        draft = cls(
            what=what,
            where_layer=where_layer,
            where_component=where_component,
            why=why,
            evidence=tuple(evidence),
            verdict=verdict,
            **kwargs,
        )
        return replace(draft, confidence=draft.compute_confidence(minimum_layers))


class ExecutionStatus(Enum):
    """Lifecycle status of an execution unit (a plugin run, or the whole run).

    Describes whether *the framework ran the unit*, which is independent of what
    the unit concluded about the product. See :class:`ExecutionResult`.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERRORED = "ERRORED"
    SKIPPED = "SKIPPED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """Whether no further transition is expected from this status."""
        return self is not ExecutionStatus.PENDING and self is not ExecutionStatus.RUNNING

    @property
    def reached_conclusion(self) -> bool:
        """Whether the unit ran far enough for its findings to mean anything.

        ``False`` for every status where the framework did not complete the work:
        such a unit's verdict is ``INCONCLUSIVE`` regardless of partial findings.
        """
        return self is ExecutionStatus.COMPLETED


class LifecycleStage(Enum):
    """Stages a unit of work passes through.

    Part of the plugin contract rather than an engine detail: a plugin author
    needs to know which stage each of their methods is invoked in, and reports
    reference the stage a failure occurred in.

    ``REGISTER`` happens once per plugin at registration time; the remaining
    stages happen per execution. ``FAILED`` and ``SKIPPED`` are terminal outcomes
    rather than steps in the happy path.
    """

    REGISTER = "REGISTER"
    INITIALIZE = "INITIALIZE"
    PRECHECK = "PRECHECK"
    EXECUTE = "EXECUTE"
    VALIDATE = "VALIDATE"
    POSTCHECK = "POSTCHECK"
    REPORT = "REPORT"
    CLEANUP = "CLEANUP"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"

    @property
    def is_terminal_outcome(self) -> bool:
        """Whether this stage represents a terminal outcome rather than a step."""
        return self in (LifecycleStage.FAILED, LifecycleStage.SKIPPED)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Outcome of one execution unit.

    Distinguishes *whether the framework ran* (:attr:`status`) from *what it
    concluded about the product* (:attr:`verdict`). Conflating the two is the
    mistake that produces false-healthy results: a plugin that crashed has
    ``ERRORED`` status and an ``INCONCLUSIVE`` verdict, never a pass.

    Args:
        unit_id: Identifier of the unit executed (plugin id, or a run id).
        status: Whether the unit itself ran to completion.
        findings: Findings produced.
        started_at: Start timestamp.
        finished_at: Completion timestamp, if finished.
        error: Error message when ``status`` is ``ERRORED``.
        metadata: Optional structured detail.
    """

    unit_id: str
    status: ExecutionStatus
    findings: Sequence[Finding] = field(default_factory=tuple)
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime | None = None
    error: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def verdict(self) -> Verdict:
        """The aggregate verdict across findings, per §6 precedence.

        An errored unit is ``INCONCLUSIVE`` regardless of any partial findings:
        if execution did not complete, the absence of a failure is not evidence
        of health.
        """
        if self.status is ExecutionStatus.ERRORED:
            return Verdict.INCONCLUSIVE
        return Verdict.aggregate(finding.verdict for finding in self.findings)

    @property
    def duration_seconds(self) -> float | None:
        """Wall-clock duration, or ``None`` if not finished."""
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


@dataclass(frozen=True, slots=True)
class PluginMetadata:
    """Declarative description of a plugin.

    Metadata is separate from plugin behaviour so the registry can resolve
    dependencies and report inventory without importing or executing anything.

    Args:
        plugin_id: Identifier of the form ``EM001_Login``.
        name: Human-readable name.
        version: Plugin version string.
        description: What feature area the plugin validates.
        evidence_layers: Layers this plugin is expected to gather evidence
            across. A single-layer plugin is non-conformant per the Plugin
            Development Guide §10.
        depends_on: Plugin identifiers that **must** run first. A missing or
            failed required dependency prevents this plugin from running.
        optional_depends_on: Plugin identifiers that should run first *if
            present*. A missing optional dependency is not an error; it only
            affects ordering.
        requires: Version constraints on dependencies, keyed by plugin id, e.g.
            ``{"EM001_Login": ">=1.2"}``. Checked by the dependency resolver.
        feature_spec_ref: Pointer to the HB-006 section defining the feature's
            behavioural scope.
        enabled: Whether the plugin should be executed.
        timeout_seconds: Maximum wall-clock time for one execution, or ``None``
            for no limit.
        max_attempts: Total execution attempts including the first. Values above
            one opt the plugin into engine-level retry.
    """

    plugin_id: str
    name: str
    version: str
    description: str = ""
    evidence_layers: Sequence[EvidenceLayer] = field(default_factory=tuple)
    depends_on: Sequence[str] = field(default_factory=tuple)
    optional_depends_on: Sequence[str] = field(default_factory=tuple)
    requires: Mapping[str, str] = field(default_factory=dict)
    feature_spec_ref: str | None = None
    enabled: bool = True
    timeout_seconds: float | None = None
    max_attempts: int = 1

    def __post_init__(self) -> None:
        """Validate the plugin identifier shape.

        Raises:
            ValidationError: If ``plugin_id`` does not match ``EM<NNN>_<Name>``.
        """
        if not _PLUGIN_ID_RE.match(self.plugin_id):
            raise ValidationError(
                "Plugin identifier does not match the required EM<NNN>_<Name> form",
                {"plugin_id": self.plugin_id},
            )
        if self.max_attempts < 1:
            raise ValidationError(
                "max_attempts must be at least 1",
                {"plugin_id": self.plugin_id, "max_attempts": self.max_attempts},
            )
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValidationError(
                "timeout_seconds must be positive when set",
                {"plugin_id": self.plugin_id, "timeout_seconds": self.timeout_seconds},
            )
        overlap = set(self.depends_on) & set(self.optional_depends_on)
        if overlap:
            raise ValidationError(
                "A dependency cannot be both required and optional",
                {"plugin_id": self.plugin_id, "overlap": sorted(overlap)},
            )
        if self.plugin_id in set(self.depends_on) | set(self.optional_depends_on):
            raise ValidationError(
                "A plugin cannot depend on itself", {"plugin_id": self.plugin_id}
            )

    @property
    def is_multi_layer(self) -> bool:
        """Whether the plugin declares evidence across two or more layers."""
        return len(set(self.evidence_layers)) >= MIN_CORROBORATING_LAYERS

    @property
    def all_dependencies(self) -> tuple[str, ...]:
        """Required and optional dependencies together, for ordering purposes."""
        return tuple(self.depends_on) + tuple(self.optional_depends_on)


@dataclass(frozen=True, slots=True)
class EnvironmentInfo:
    """Description of the environment a run executes against.

    Fields are intentionally optional and free-form: the framework records what
    it is told, and populating these from real observation is the job of the
    environment collector built in a later phase.
    """

    name: str
    host: str | None = None
    os_version: str | None = None
    organization: str | None = None
    user: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentInfo:
    """Description of the EmpMonitor agent a run observes.

    Every field is optional because none of it is verified yet: the knowledge
    base records agent version, build, and process facts as Hypothesis status.
    This model is the shape those facts will occupy once a collector observes
    them -- the framework does not assume any of them here.
    """

    version: str | None = None
    build: str | None = None
    install_path: Path | None = None
    service_names: Sequence[str] = field(default_factory=tuple)
    process_names: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DashboardInfo:
    """Description of the dashboard surface a run observes (Layer 4).

    Holds no navigation logic and no selectors -- those belong to the dashboard
    collector built in a later phase.
    """

    base_url: str | None = None
    version: str | None = None
    organization: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Immutable input bundle handed to a validator.

    Bundling the inputs keeps validator signatures stable as the framework
    grows: adding a new input is a field here, not a signature change across
    every validator (composition over inheritance, dependency injection).

    Args:
        execution_id: Run identifier, for correlation.
        environment: Environment under test.
        agent: Agent facts, as far as they are known.
        dashboard: Dashboard facts, as far as they are known.
        evidence: Evidence available to the validator.
        minimum_layers: Configured corroboration minimum for this run.
        plugin_id: Owning plugin, when validation runs inside one.
        metadata: Optional structured detail.
    """

    execution_id: str
    environment: EnvironmentInfo
    agent: AgentInfo = field(default_factory=AgentInfo)
    dashboard: DashboardInfo = field(default_factory=DashboardInfo)
    evidence: Sequence[Evidence] = field(default_factory=tuple)
    minimum_layers: int = MIN_CORROBORATING_LAYERS
    plugin_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def evidence_for_layer(self, layer: EvidenceLayer) -> tuple[Evidence, ...]:
        """Return the available evidence belonging to one layer.

        Args:
            layer: Layer to filter by.

        Returns:
            Matching evidence, in collection order.
        """
        return tuple(item for item in self.evidence if item.layer is layer)

    def with_evidence(self, additional: Iterable[Evidence]) -> "ValidationContext":
        """Return a copy with more evidence appended.

        Args:
            additional: Evidence to add.

        Returns:
            A new context; the original is unchanged.
        """
        return replace(self, evidence=tuple(self.evidence) + tuple(additional))
