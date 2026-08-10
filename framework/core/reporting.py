"""Report models.

Models only. **No HTML, no PDF, no rendering** -- per the sprint brief, and
because the format a report is rendered into should be replaceable without
touching what a report *means*. A :class:`Reporter` implementation
(:class:`framework.shared.interfaces.Reporter`) renders these in a later phase.

The models enforce the reporting rules ratified in
``docs/ADS/validation_standard.md`` §10:

* every finding field is carried through aggregation, never dropped;
* ``INCONCLUSIVE`` and ``BLOCKED`` are surfaced as prominently as ``FAILED``,
  which is why :class:`ReportSummary` counts them explicitly rather than folding
  them into an "other" bucket;
* confidence always accompanies a verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from framework.shared.constants import (
    FRAMEWORK_NAME,
    FRAMEWORK_VERSION,
    VALIDATION_STANDARD_VERSION,
)
from framework.shared.models import (
    Confidence,
    Evidence,
    EvidenceLayer,
    ExecutionResult,
    FailureClass,
    Finding,
    Verdict,
    utc_now,
)

__all__ = [
    "Attachment",
    "TimelineEntry",
    "ReportMetadata",
    "ReportSummary",
    "FindingRecord",
    "ReportSection",
    "Report",
]


@dataclass(frozen=True, slots=True)
class Attachment:
    """A file attached to a report.

    Args:
        name: Display name.
        path: Location of the attachment.
        media_type: Media type, when known.
        size_bytes: Size in bytes, when known.
        digest: Content digest, for integrity.
        description: What the attachment shows.
    """

    name: str
    path: Path
    media_type: str | None = None
    size_bytes: int | None = None
    digest: str | None = None
    description: str = ""


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """One ordered event in a run's timeline.

    A timeline is what makes a report diagnosable rather than merely conclusive:
    it shows the sequence that produced the verdict.

    Args:
        occurred_at: When it happened.
        label: Short description.
        category: Grouping key, e.g. ``"plugin"`` or ``"evidence"``.
        detail: Structured detail.
    """

    occurred_at: datetime
    label: str
    category: str = "general"
    detail: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    """Provenance for a report.

    Records the conditions the report was produced under, including the
    Validation Standard version -- a report must be interpretable against the
    contract that was in force when it was written.

    Args:
        execution_id: Run identifier.
        generated_at: Report creation time.
        environment: Environment name.
        framework_name: Producing framework.
        framework_version: Framework version.
        validation_standard_version: Validation Standard version implemented.
        host: Host that produced the run.
        organization: Owning organization.
        build_number: Build identifier, if any.
        agent_version: Observed agent version, if established.
        extra: Additional provenance detail.
    """

    execution_id: str
    generated_at: datetime = field(default_factory=utc_now)
    environment: str = ""
    framework_name: str = FRAMEWORK_NAME
    framework_version: str = FRAMEWORK_VERSION
    validation_standard_version: str = VALIDATION_STANDARD_VERSION
    host: str | None = None
    organization: str | None = None
    build_number: str | None = None
    agent_version: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReportSummary:
    """Aggregate counts and the overall verdict for a run.

    Each verdict is counted separately and deliberately: collapsing
    ``INCONCLUSIVE`` into a pass or a failure is the anti-pattern the Validation
    Standard forbids (§11), so the model gives it nowhere to hide.

    Args:
        overall_verdict: Aggregate verdict across all findings.
        lowest_confidence: Weakest confidence among findings -- reported because
            an aggregate is only as trustworthy as its weakest support.
        total_findings: Number of findings.
        healthy: Count of ``HEALTHY`` findings.
        degraded: Count of ``DEGRADED`` findings.
        failed: Count of ``FAILED`` findings.
        inconclusive: Count of ``INCONCLUSIVE`` findings.
        blocked: Count of ``BLOCKED`` findings.
        layers_covered: Layers that contributed evidence.
        failure_classes: Count of findings per failure class.
        duration_seconds: Total run duration.
    """

    overall_verdict: Verdict
    lowest_confidence: Confidence
    total_findings: int = 0
    healthy: int = 0
    degraded: int = 0
    failed: int = 0
    inconclusive: int = 0
    blocked: int = 0
    layers_covered: Sequence[EvidenceLayer] = field(default_factory=tuple)
    failure_classes: Mapping[str, int] = field(default_factory=dict)
    duration_seconds: float | None = None

    @property
    def has_unanswered_questions(self) -> bool:
        """Whether any finding was inconclusive or blocked.

        A run with unanswered questions is not a clean run, even when nothing
        failed -- callers should surface this rather than reporting success.
        """
        return bool(self.inconclusive or self.blocked)

    @classmethod
    def from_findings(
        cls,
        findings: Sequence[Finding],
        *,
        duration_seconds: float | None = None,
    ) -> "ReportSummary":
        """Build a summary from findings.

        Args:
            findings: Findings to summarise.
            duration_seconds: Total run duration.

        Returns:
            The computed summary. With no findings the verdict is
            ``INCONCLUSIVE``: a run that concluded nothing has not passed.
        """
        counts = {verdict: 0 for verdict in Verdict}
        failure_classes: dict[str, int] = {}
        layers: set[EvidenceLayer] = set()
        for finding in findings:
            counts[finding.verdict] += 1
            layers.update(finding.corroboration)
            if finding.failure_class is not None:
                key = finding.failure_class.value
                failure_classes[key] = failure_classes.get(key, 0) + 1
        lowest = (
            min((finding.confidence for finding in findings), default=Confidence.UNKNOWN)
        )
        return cls(
            overall_verdict=Verdict.aggregate(finding.verdict for finding in findings),
            lowest_confidence=lowest,
            total_findings=len(findings),
            healthy=counts[Verdict.HEALTHY],
            degraded=counts[Verdict.DEGRADED],
            failed=counts[Verdict.FAILED],
            inconclusive=counts[Verdict.INCONCLUSIVE],
            blocked=counts[Verdict.BLOCKED],
            layers_covered=tuple(sorted(layers)),
            failure_classes=failure_classes,
            duration_seconds=duration_seconds,
        )


@dataclass(frozen=True, slots=True)
class FindingRecord:
    """A report-facing projection of a :class:`Finding`.

    Flattens a finding for serialisation while carrying every field §10 requires.
    Kept separate from :class:`Finding` so the report format can evolve without
    changing the validation contract.

    Args:
        what: Observed defect or healthy behaviour.
        where: Rendered location (layer, component, artifact).
        why: Causal finding, or ``"undetermined"``.
        verdict: The verdict.
        confidence: Computed confidence -- always present alongside the verdict.
        corroboration: Layers that contributed evidence.
        evidence_ids: Catalog identifiers of the citing evidence.
        failure_class: Failure classification, for failures.
        conflicts: Descriptions of recorded evidence conflicts.
        plugin_id: Owning plugin.
        notes: Annotations, such as a recorded confidence downgrade reason.
    """

    what: str
    where: str
    why: str
    verdict: Verdict
    confidence: Confidence
    corroboration: Sequence[str] = field(default_factory=tuple)
    evidence_ids: Sequence[str] = field(default_factory=tuple)
    failure_class: FailureClass | None = None
    conflicts: Sequence[str] = field(default_factory=tuple)
    plugin_id: str | None = None
    notes: Sequence[str] = field(default_factory=tuple)

    @classmethod
    def from_finding(cls, finding: Finding) -> "FindingRecord":
        """Project a finding into a report record.

        Args:
            finding: Finding to project.

        Returns:
            The record, preserving every required field.
        """
        location = f"{finding.where_layer.label}/{finding.where_component}"
        if finding.where_artifact:
            location = f"{location}/{finding.where_artifact}"
        return cls(
            what=finding.what,
            where=location,
            why=finding.why,
            verdict=finding.verdict,
            confidence=finding.confidence,
            corroboration=tuple(layer.label for layer in finding.corroboration),
            evidence_ids=tuple(item.evidence_id for item in finding.evidence),
            failure_class=finding.failure_class,
            conflicts=tuple(
                conflict.description
                for conflict in finding.conflicts
                if not conflict.is_resolved
            ),
            plugin_id=finding.plugin_id,
            notes=tuple(finding.notes),
        )


@dataclass(frozen=True, slots=True)
class ReportSection:
    """A grouped part of a report, typically one plugin's results.

    Args:
        title: Section heading.
        status: Execution status of the unit.
        verdict: Aggregate verdict for the section.
        findings: Finding records.
        attachments: Attachments belonging to this section.
        metadata: Section-scoped detail.
    """

    title: str
    status: str
    verdict: Verdict
    findings: Sequence[FindingRecord] = field(default_factory=tuple)
    attachments: Sequence[Attachment] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_execution_result(cls, result: ExecutionResult) -> "ReportSection":
        """Build a section from an execution result.

        Args:
            result: Result to project.

        Returns:
            The section.
        """
        return cls(
            title=result.unit_id,
            status=result.status.value,
            verdict=result.verdict,
            findings=tuple(FindingRecord.from_finding(item) for item in result.findings),
            metadata={
                "duration_seconds": result.duration_seconds,
                "error": result.error,
                **dict(result.metadata),
            },
        )


def _serialise_layers(layers: Sequence[EvidenceLayer]) -> list[str]:
    """Render layers as their standard labels, e.g. ``["L1", "L2"]``."""
    return [layer.label for layer in layers]


@dataclass(frozen=True, slots=True)
class Report:
    """A complete run report.

    The top-level model a :class:`~framework.shared.interfaces.Reporter` renders.
    It carries everything needed to interpret the run without consulting the
    framework: summary, per-unit sections, evidence, timeline, attachments, and
    provenance.

    Args:
        metadata: Report provenance.
        summary: Aggregate summary.
        sections: Per-unit sections.
        timeline: Ordered run events.
        evidence: Evidence collected during the run.
        attachments: Run-level attachments.
    """

    metadata: ReportMetadata
    summary: ReportSummary
    sections: Sequence[ReportSection] = field(default_factory=tuple)
    timeline: Sequence[TimelineEntry] = field(default_factory=tuple)
    evidence: Sequence[Evidence] = field(default_factory=tuple)
    attachments: Sequence[Attachment] = field(default_factory=tuple)

    @property
    def all_findings(self) -> tuple[FindingRecord, ...]:
        """Every finding record across all sections."""
        return tuple(
            record for section in self.sections for record in section.findings
        )

    def findings_with_verdict(self, verdict: Verdict) -> tuple[FindingRecord, ...]:
        """Return findings carrying a particular verdict.

        Args:
            verdict: Verdict to filter by.

        Returns:
            Matching finding records.
        """
        return tuple(record for record in self.all_findings if record.verdict is verdict)

    def to_dict(self) -> dict[str, Any]:
        """Render the report as a JSON-native mapping.

        Serialisation lives here rather than in a generic encoder because the
        display policy is a *reporting* decision: verdicts render as their
        values, confidence as its name, and layers as their ``L<n>`` labels.
        :class:`Confidence` and :class:`EvidenceLayer` are ``IntEnum`` members --
        chosen so ordering rules are expressible in code -- which a generic JSON
        encoder would emit as bare integers. ``"confidence": 0`` would not
        satisfy the §10 rule that confidence is always displayed alongside the
        verdict, so the mapping is built explicitly.

        Returns:
            A mapping safe to serialise with :mod:`json`.
        """
        return {
            "metadata": {
                "execution_id": self.metadata.execution_id,
                "generated_at": self.metadata.generated_at.isoformat(),
                "environment": self.metadata.environment,
                "framework_name": self.metadata.framework_name,
                "framework_version": self.metadata.framework_version,
                "validation_standard_version": self.metadata.validation_standard_version,
                "host": self.metadata.host,
                "organization": self.metadata.organization,
                "build_number": self.metadata.build_number,
                "agent_version": self.metadata.agent_version,
                "extra": dict(self.metadata.extra),
            },
            "summary": {
                "overall_verdict": self.summary.overall_verdict.value,
                "lowest_confidence": self.summary.lowest_confidence.name,
                "total_findings": self.summary.total_findings,
                "healthy": self.summary.healthy,
                "degraded": self.summary.degraded,
                "failed": self.summary.failed,
                "inconclusive": self.summary.inconclusive,
                "blocked": self.summary.blocked,
                "layers_covered": _serialise_layers(self.summary.layers_covered),
                "failure_classes": dict(self.summary.failure_classes),
                "duration_seconds": self.summary.duration_seconds,
                "has_unanswered_questions": self.summary.has_unanswered_questions,
            },
            "sections": [
                {
                    "title": section.title,
                    "status": section.status,
                    "verdict": section.verdict.value,
                    "findings": [
                        {
                            "what": record.what,
                            "where": record.where,
                            "why": record.why,
                            "verdict": record.verdict.value,
                            "confidence": record.confidence.name,
                            "corroboration": list(record.corroboration),
                            "evidence_ids": list(record.evidence_ids),
                            "failure_class": (
                                record.failure_class.value
                                if record.failure_class is not None
                                else None
                            ),
                            "conflicts": list(record.conflicts),
                            "plugin_id": record.plugin_id,
                            "notes": list(record.notes),
                        }
                        for record in section.findings
                    ],
                    "attachments": [
                        {
                            "name": attachment.name,
                            "path": str(attachment.path),
                            "media_type": attachment.media_type,
                            "size_bytes": attachment.size_bytes,
                            "digest": attachment.digest,
                            "description": attachment.description,
                        }
                        for attachment in section.attachments
                    ],
                    "metadata": dict(section.metadata),
                }
                for section in self.sections
            ],
            "timeline": [
                {
                    "occurred_at": entry.occurred_at.isoformat(),
                    "label": entry.label,
                    "category": entry.category,
                    "detail": dict(entry.detail),
                }
                for entry in self.timeline
            ],
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "layer": item.layer.label,
                    "source": item.source,
                    "summary": item.summary,
                    "collected_at": item.collected_at.isoformat(),
                    "collector": item.collector,
                    "reliability": item.reliability.name,
                    "artifact_path": (
                        str(item.artifact_path) if item.artifact_path is not None else None
                    ),
                    "data": dict(item.data),
                }
                for item in self.evidence
            ],
            "attachments": [
                {
                    "name": attachment.name,
                    "path": str(attachment.path),
                    "media_type": attachment.media_type,
                    "size_bytes": attachment.size_bytes,
                    "digest": attachment.digest,
                    "description": attachment.description,
                }
                for attachment in self.attachments
            ],
        }

    @classmethod
    def build(
        cls,
        *,
        metadata: ReportMetadata,
        results: Sequence[ExecutionResult],
        evidence: Sequence[Evidence] = (),
        timeline: Sequence[TimelineEntry] = (),
        attachments: Sequence[Attachment] = (),
        duration_seconds: float | None = None,
    ) -> "Report":
        """Assemble a report from execution results.

        Args:
            metadata: Report provenance.
            results: Execution results to include.
            evidence: Evidence collected during the run.
            timeline: Ordered run events.
            attachments: Run-level attachments.
            duration_seconds: Total run duration.

        Returns:
            The assembled report.
        """
        findings = [finding for result in results for finding in result.findings]
        return cls(
            metadata=metadata,
            summary=ReportSummary.from_findings(findings, duration_seconds=duration_seconds),
            sections=tuple(ReportSection.from_execution_result(item) for item in results),
            timeline=tuple(sorted(timeline, key=lambda entry: entry.occurred_at)),
            evidence=tuple(evidence),
            attachments=tuple(attachments),
        )
