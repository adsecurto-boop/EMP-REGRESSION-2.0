"""Result aggregation.

Collapses everything a run produced -- evidence, findings, warnings, errors,
performance, execution statistics -- into one coherent account, and assembles the
final report.

Aggregation is where a run's honesty is either preserved or lost. Two rules are
enforced here rather than left to whoever reads the output:

* **Nothing is dropped.** Every finding, error, and warning is carried through, and
  ``INCONCLUSIVE`` and ``BLOCKED`` are counted in their own right rather than folded
  into a pass or a failure (``docs/ADS/validation_standard.md`` §10 rule 2).
* **The final verdict is derived, never chosen.** It comes from
  :meth:`ValidationEngine.aggregate` applying the ratified precedence rules, so a
  run cannot present a more flattering verdict than its evidence supports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from framework.core.artifacts import ArtifactManager, ArtifactRecord
from framework.core.execution import ExecutionReport
from framework.core.graph import ExecutionGraph
from framework.core.metrics import RunMetrics
from framework.core.pipeline import PipelineResult, StageError
from framework.core.reporting import (
    Attachment,
    Report,
    ReportMetadata,
    ReportSection,
    TimelineEntry,
)
from framework.core.timeline import ExecutionTimeline
from framework.core.validation import ValidationEngine
from framework.shared.logger import get_logger
from framework.shared.models import (
    Confidence,
    Evidence,
    ExecutionResult,
    ExecutionStatus,
    Finding,
    Verdict,
)

__all__ = ["AggregatedResult", "ResultAggregator"]

_LOGGER = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AggregatedResult:
    """The complete aggregated account of a run.

    Args:
        verdict: Final verdict, derived from every finding.
        confidence: Weakest confidence among findings.
        findings: Every finding, after duplicate merging.
        evidence: Every piece of evidence collected.
        warnings: Non-fatal conditions worth surfacing.
        errors: Failures recorded during the run.
        statistics: Execution statistics.
        metrics: Performance metrics, when collected.
        artifacts: Artifacts produced.
        unanswered: Count of findings that concluded nothing.
    """

    verdict: Verdict
    confidence: Confidence
    findings: Sequence[Finding] = field(default_factory=tuple)
    evidence: Sequence[Evidence] = field(default_factory=tuple)
    warnings: Sequence[str] = field(default_factory=tuple)
    errors: Sequence[str] = field(default_factory=tuple)
    statistics: Mapping[str, Any] = field(default_factory=dict)
    metrics: Mapping[str, Any] = field(default_factory=dict)
    artifacts: Sequence[ArtifactRecord] = field(default_factory=tuple)
    unanswered: int = 0

    @property
    def is_clean(self) -> bool:
        """Whether the run concluded positively with nothing left unanswered.

        A run with inconclusive findings is not clean even when nothing failed:
        unanswered questions are not evidence of health.
        """
        return (
            self.verdict in (Verdict.HEALTHY, Verdict.DEGRADED)
            and self.unanswered == 0
            and not self.errors
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native summary.

        Returns:
            A serialisable mapping.
        """
        return {
            "verdict": self.verdict.value,
            "confidence": self.confidence.name,
            "finding_count": len(self.findings),
            "evidence_count": len(self.evidence),
            "warning_count": len(self.warnings),
            "error_count": len(self.errors),
            "unanswered": self.unanswered,
            "is_clean": self.is_clean,
            "statistics": dict(self.statistics),
            "metrics": dict(self.metrics),
            "artifacts": [record.artifact_id for record in self.artifacts],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


class ResultAggregator:
    """Aggregates a run's outputs into a result and a report.

    Collaborators are injected; every one is optional, so a partially assembled run
    can still be aggregated. A run that crashed early must still be reportable --
    that is precisely when the report matters most.
    """

    __slots__ = ("_engine",)

    def __init__(self, *, engine: ValidationEngine | None = None) -> None:
        """Initialise the aggregator.

        Args:
            engine: Validation engine used for merging and verdict derivation.
        """
        self._engine = engine or ValidationEngine()

    def aggregate(
        self,
        *,
        execution: ExecutionReport | None = None,
        results: Sequence[ExecutionResult] = (),
        evidence: Sequence[Evidence] = (),
        pipeline_results: Sequence[PipelineResult] = (),
        metrics: RunMetrics | None = None,
        artifacts: ArtifactManager | None = None,
        graph: ExecutionGraph | None = None,
        extra_warnings: Sequence[str] = (),
    ) -> AggregatedResult:
        """Aggregate a run's outputs.

        Args:
            execution: Execution report, if the engine was used.
            results: Execution results, when not supplying an execution report.
            evidence: Evidence collected outside the pipeline.
            pipeline_results: Pipeline results, contributing evidence and findings.
            metrics: Performance metrics.
            artifacts: Artifact manager whose records are included.
            graph: Execution graph, contributing state statistics.
            extra_warnings: Additional warnings to surface.

        Returns:
            The aggregated result.
        """
        collected_results = list(results) or (
            list(execution.ordered_results) if execution is not None else []
        )

        findings: list[Finding] = []
        for result in collected_results:
            findings.extend(result.findings)
        for pipeline in pipeline_results:
            findings.extend(pipeline.findings)

        merged = list(self._engine.merge_duplicates(findings))

        # Harvest evidence from three places: what the caller supplied, what any
        # pipeline produced, and -- critically -- what the findings themselves cite.
        # A finding's evidence may have been collected inside a plugin that never
        # touched the run's evidence store, and a report whose findings cite
        # identifiers absent from its own evidence list violates the rule that
        # citations must resolve (``validation_standard.md`` §10 rule 5).
        all_evidence: dict[tuple[str, str, str], Evidence] = {}
        for item in (
            list(evidence)
            + [piece for pipeline in pipeline_results for piece in pipeline.evidence]
            + [piece for finding in merged for piece in finding.evidence]
        ):
            all_evidence[(item.evidence_id, item.source, item.summary)] = item

        warnings = list(extra_warnings)
        errors: list[str] = []

        for result in collected_results:
            if result.status is ExecutionStatus.ERRORED:
                errors.append(f"{result.unit_id}: {result.error or 'errored'}")
            elif result.status is ExecutionStatus.TIMED_OUT:
                errors.append(f"{result.unit_id}: timed out ({result.error or 'no detail'})")
            elif result.status is ExecutionStatus.CANCELLED:
                warnings.append(f"{result.unit_id}: cancelled ({result.error or 'no detail'})")
            elif result.status is ExecutionStatus.SKIPPED:
                warnings.append(f"{result.unit_id}: skipped ({result.error or 'no reason given'})")

        for pipeline in pipeline_results:
            for stage_error in pipeline.errors:
                errors.append(self._describe_stage_error(stage_error))

        if execution is not None and execution.cancelled:
            warnings.append(
                f"run cancelled: {execution.cancellation_reason or 'no reason given'}"
            )

        unanswered = sum(
            1
            for finding in merged
            if finding.verdict in (Verdict.INCONCLUSIVE, Verdict.BLOCKED)
        )
        if unanswered:
            warnings.append(
                f"{unanswered} finding(s) concluded nothing (inconclusive or blocked)"
            )

        result = AggregatedResult(
            verdict=self._engine.aggregate(merged),
            confidence=self._engine.aggregate_confidence(merged),
            findings=tuple(merged),
            evidence=tuple(all_evidence[key] for key in sorted(all_evidence)),
            warnings=tuple(dict.fromkeys(warnings)),
            errors=tuple(dict.fromkeys(errors)),
            statistics=self._statistics(collected_results, execution, graph),
            metrics=metrics.to_dict() if metrics is not None else {},
            artifacts=artifacts.all() if artifacts is not None else (),
            unanswered=unanswered,
        )
        _LOGGER.info(
            "Aggregated: verdict=%s confidence=%s findings=%d errors=%d warnings=%d",
            result.verdict.value,
            result.confidence.name,
            len(result.findings),
            len(result.errors),
            len(result.warnings),
        )
        return result

    @staticmethod
    def _describe_stage_error(error: StageError) -> str:
        """Render a pipeline stage error as a single line.

        Args:
            error: The stage error.

        Returns:
            A readable description.
        """
        return f"pipeline {error.stage} ({error.component}): {error.message}"

    @staticmethod
    def _statistics(
        results: Sequence[ExecutionResult],
        execution: ExecutionReport | None,
        graph: ExecutionGraph | None,
    ) -> dict[str, Any]:
        """Compute execution statistics.

        Args:
            results: Execution results.
            execution: Execution report, if available.
            graph: Execution graph, if available.

        Returns:
            A serialisable statistics mapping. Every status is present so a zero is
            explicit rather than a missing key.
        """
        by_status = {status.value: 0 for status in ExecutionStatus}
        for result in results:
            by_status[result.status.value] += 1
        durations = [
            result.duration_seconds
            for result in results
            if result.duration_seconds is not None
        ]
        statistics: dict[str, Any] = {
            "units": len(results),
            "by_status": by_status,
            "total_unit_seconds": round(sum(durations), 6) if durations else 0.0,
            "slowest_unit_seconds": round(max(durations), 6) if durations else None,
        }
        if execution is not None:
            statistics["mode"] = execution.plan.mode.value
            statistics["max_workers"] = execution.plan.max_workers
            statistics["excluded"] = dict(execution.plan.excluded)
            statistics["duration_seconds"] = execution.duration_seconds
        if graph is not None:
            statistics["graph_states"] = graph.state_counts()
            statistics["graph_levels"] = len(graph.levels())
        return statistics

    def build_report(
        self,
        aggregated: AggregatedResult,
        *,
        metadata: ReportMetadata,
        results: Sequence[ExecutionResult] = (),
        timeline: ExecutionTimeline | None = None,
        duration_seconds: float | None = None,
    ) -> Report:
        """Assemble the final report from an aggregated result.

        Args:
            aggregated: The aggregated result.
            metadata: Report provenance.
            results: Execution results, projected into report sections.
            timeline: Execution timeline, projected into report entries.
            duration_seconds: Total run duration.

        Returns:
            The assembled report, carrying aggregated warnings, errors, statistics,
            and metrics alongside the findings.
        """
        entries: tuple[TimelineEntry, ...] = (
            timeline.entries() if timeline is not None else ()
        )
        attachments = tuple(
            Attachment(
                name=record.name,
                path=record.path,
                media_type=record.kind.value,
                size_bytes=record.size_bytes,
                digest=record.checksum,
                description=record.description,
            )
            for record in aggregated.artifacts
        )
        enriched = ReportMetadata(
            execution_id=metadata.execution_id,
            generated_at=metadata.generated_at,
            environment=metadata.environment,
            framework_name=metadata.framework_name,
            framework_version=metadata.framework_version,
            validation_standard_version=metadata.validation_standard_version,
            host=metadata.host,
            organization=metadata.organization,
            build_number=metadata.build_number,
            agent_version=metadata.agent_version,
            extra={
                **dict(metadata.extra),
                "statistics": dict(aggregated.statistics),
                "metrics": dict(aggregated.metrics),
                "warnings": list(aggregated.warnings),
                "errors": list(aggregated.errors),
                "unanswered_findings": aggregated.unanswered,
            },
        )
        report = Report.build(
            metadata=enriched,
            results=results,
            evidence=aggregated.evidence,
            timeline=entries,
            attachments=attachments,
            duration_seconds=duration_seconds,
        )
        # The report's own summary is recomputed from its sections. Assert that it
        # agrees with the aggregate, so a divergence is caught here rather than
        # silently shipping two different verdicts for one run.
        if results and report.summary.overall_verdict is not aggregated.verdict:
            _LOGGER.warning(
                "Report verdict %s differs from aggregate verdict %s; "
                "sections may not cover every finding",
                report.summary.overall_verdict.value,
                aggregated.verdict.value,
            )
        return report
