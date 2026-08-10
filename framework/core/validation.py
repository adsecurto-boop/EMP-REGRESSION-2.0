"""The verdict engine.

Mechanically applies the ratified Validation Standard v1.0 to evidence and
findings. This is the reusable heart of the framework: it decides verdicts,
computes confidence, resolves conflicts, and aggregates findings.

**It contains no EmpMonitor rules.** It consumes :class:`Evidence` and
:class:`Finding` objects and knows nothing about what they describe -- no product
paths, processes, schemas, or endpoints. A rule specific to EmpMonitor belongs in
a plugin or a product validator, never here. That is what makes the engine
reusable for evidence the framework has never seen.

Determinism is a requirement, not an aspiration: given the same evidence, this
engine must always produce the same verdict. Anything order-dependent is sorted
before it is used.

**Evidence reliability comes from the catalog, applied by the store.** This engine
reads the ``reliability`` already on each :class:`Evidence` and does not consult the
Evidence Catalog itself -- it has no product knowledge by design. Reliability is
filled in by :meth:`framework.core.evidence.EvidenceStore.add` from the registered
catalog entry, so evidence should be recorded through the store before it is
validated. Evidence built directly and passed straight here keeps the default
``MEDIUM`` reliability and therefore yields a lower computed confidence. That is the
safe direction to fail -- confidence is understated, never overstated -- but a plugin
wanting its evidence assessed at its registered strength must route it through the
store.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable, Mapping, Sequence

from framework.shared.constants import MIN_CORROBORATING_LAYERS
from framework.shared.exceptions import ValidationError
from framework.shared.logger import get_logger
from framework.shared.models import (
    Confidence,
    Evidence,
    EvidenceConflict,
    EvidenceLayer,
    FailureClass,
    Finding,
    SourceReliability,
    ValidationContext,
    Verdict,
)

__all__ = [
    "LayerAssessment",
    "CorrelationReport",
    "ValidationEngine",
]

_LOGGER = get_logger(__name__)

# Rule labels from Validation Standard §7, recorded on a resolved conflict so a
# report can state which rule settled a disagreement.
_RULE_PROXIMITY = "§7.2 proximity: layer-native evidence outranks external"
_RULE_DIRECTNESS = "§7.3 directness: direct observation outranks derived"


@dataclass(frozen=True, slots=True)
class LayerAssessment:
    """What the evidence says about one layer.

    Args:
        layer: The layer assessed.
        evidence_count: Pieces of evidence contributing.
        strongest: Highest source reliability present.
        weakest: Lowest source reliability present.
        diverged: Whether evidence at this layer departs from expectation.
    """

    layer: EvidenceLayer
    evidence_count: int
    strongest: SourceReliability | None = None
    weakest: SourceReliability | None = None
    diverged: bool = False

    @property
    def has_evidence(self) -> bool:
        """Whether any evidence covers this layer."""
        return self.evidence_count > 0


@dataclass(frozen=True, slots=True)
class CorrelationReport:
    """The engine's reconciled view across layers.

    Args:
        assessments: Per-layer assessments, in layer order.
        first_divergence: Earliest layer at which evidence diverged, if any.
        conflicts: Conflicts detected between sources.
        layers_covered: Layers with evidence.
    """

    assessments: Sequence[LayerAssessment] = field(default_factory=tuple)
    first_divergence: EvidenceLayer | None = None
    conflicts: Sequence[EvidenceConflict] = field(default_factory=tuple)
    layers_covered: Sequence[EvidenceLayer] = field(default_factory=tuple)

    @property
    def unresolved_conflicts(self) -> tuple[EvidenceConflict, ...]:
        """Conflicts no §7 rule could settle."""
        return tuple(item for item in self.conflicts if not item.is_resolved)

    @property
    def satisfies_corroboration(self) -> bool:
        """Whether coverage meets the positive-conclusion rule (§5.1)."""
        return len(self.layers_covered) >= MIN_CORROBORATING_LAYERS and any(
            layer >= EvidenceLayer.RUNTIME for layer in self.layers_covered
        )


class ValidationEngine:
    """Applies the Validation Standard to evidence and findings.

    Stateless with respect to any particular product: construct once per run and
    reuse for any evidence. The corroboration minimum is injected, honouring the
    standard's rule that the threshold is configurable but never below two.
    """

    __slots__ = ("_minimum_layers",)

    def __init__(self, *, minimum_layers: int = MIN_CORROBORATING_LAYERS) -> None:
        """Initialise the engine.

        Args:
            minimum_layers: Configured corroboration minimum. Values below the
                ratified floor of two are raised to it rather than honoured.
        """
        self._minimum_layers = max(int(minimum_layers), MIN_CORROBORATING_LAYERS)

    @property
    def minimum_layers(self) -> int:
        """The effective corroboration minimum in force."""
        return self._minimum_layers

    # -- Evidence ingestion and layer evaluation --------------------------------

    def assess_layers(
        self,
        evidence: Sequence[Evidence],
        *,
        diverged_layers: Iterable[EvidenceLayer] = (),
    ) -> tuple[LayerAssessment, ...]:
        """Assess the evidence available at each layer.

        Args:
            evidence: Evidence to assess.
            diverged_layers: Layers the caller has determined diverge from
                expectation. The engine cannot decide divergence itself -- that
                requires knowing what "expected" means, which is product knowledge
                and therefore a validator's job.

        Returns:
            One assessment per layer that has evidence, in layer order.
        """
        diverged = set(diverged_layers)
        grouped: dict[EvidenceLayer, list[Evidence]] = {}
        for item in evidence:
            grouped.setdefault(item.layer, []).append(item)
        assessments: list[LayerAssessment] = []
        for layer in sorted(grouped):
            items = grouped[layer]
            reliabilities = [item.reliability for item in items]
            assessments.append(
                LayerAssessment(
                    layer=layer,
                    evidence_count=len(items),
                    strongest=max(reliabilities),
                    weakest=min(reliabilities),
                    diverged=layer in diverged,
                )
            )
        return tuple(assessments)

    def first_diverging_layer(
        self, assessments: Sequence[LayerAssessment]
    ) -> EvidenceLayer | None:
        """Return the earliest diverging layer.

        The layer at which evidence first diverges *is* the fault localisation
        (§3.1), which is why this is computed rather than asserted.

        Args:
            assessments: Layer assessments.

        Returns:
            The earliest diverging layer, or ``None`` if none diverged.
        """
        for assessment in sorted(assessments, key=lambda item: item.layer):
            if assessment.diverged:
                return assessment.layer
        return None

    # -- Conflict detection and resolution (§7) --------------------------------

    def detect_conflicts(
        self, evidence: Sequence[Evidence], *, claim_layer: EvidenceLayer | None = None
    ) -> tuple[EvidenceConflict, ...]:
        """Detect and attempt to resolve disagreements between evidence sources.

        Detects pairs of evidence about the same subject whose recorded
        ``data["state"]`` values disagree. ``state`` is the engine's generic
        contract for "what this source says the subject is"; a collector that omits
        it simply cannot be automatically conflict-checked, which is safer than
        guessing at its semantics.

        Resolution applies the §7 rules in order and records which rule settled a
        conflict. Anything unresolved stays unresolved -- disagreement is
        information, never averaged away.

        Args:
            evidence: Evidence to check.
            claim_layer: Layer the overall claim concerns, used by the proximity
                rule to decide which side outranks the other.

        Returns:
            Detected conflicts, resolved where a rule applies.
        """
        by_subject: dict[str, list[Evidence]] = {}
        for item in evidence:
            state = item.data.get("state") if isinstance(item.data, Mapping) else None
            if state is None:
                continue
            by_subject.setdefault(item.source, []).append(item)

        conflicts: list[EvidenceConflict] = []
        for subject, items in sorted(by_subject.items()):
            if len(items) < 2:
                continue
            ordered = sorted(items, key=lambda entry: (entry.layer, entry.evidence_id))
            baseline = ordered[0]
            baseline_state = baseline.data.get("state")
            for other in ordered[1:]:
                if other.data.get("state") == baseline_state:
                    continue
                conflicts.append(
                    self._resolve_conflict(
                        baseline, other, subject=subject, claim_layer=claim_layer
                    )
                )
        return tuple(conflicts)

    def _resolve_conflict(
        self,
        left: Evidence,
        right: Evidence,
        *,
        subject: str,
        claim_layer: EvidenceLayer | None,
    ) -> EvidenceConflict:
        """Apply the §7 precedence rules to one disagreement.

        Args:
            left: One side.
            right: The other side.
            subject: What they disagree about.
            claim_layer: Layer the claim concerns.

        Returns:
            The conflict, with ``resolved_by`` set when a rule applies.
        """
        description = (
            f"sources disagree about {subject!r}: "
            f"{left.evidence_id}@{left.layer.label}={left.data.get('state')!r} vs "
            f"{right.evidence_id}@{right.layer.label}={right.data.get('state')!r}"
        )
        resolved_by: str | None = None

        # §7.2 proximity: for a question about a given layer, evidence native to
        # that layer outranks evidence about it from another layer.
        if claim_layer is not None and (left.layer is claim_layer) != (
            right.layer is claim_layer
        ):
            resolved_by = _RULE_PROXIMITY
        # §7.3 directness: a more reliable source outranks a less reliable one.
        elif left.reliability is not right.reliability:
            resolved_by = _RULE_DIRECTNESS

        return EvidenceConflict(
            description=description, left=left, right=right, resolved_by=resolved_by
        )

    # -- Verdict and confidence ------------------------------------------------

    def decide_verdict(
        self,
        *,
        correlation: CorrelationReport,
        blocked_reason: str | None = None,
        degraded: bool = False,
    ) -> Verdict:
        """Decide a verdict from correlated evidence.

        Implements §5 and §6 in order of precedence: a blocked precondition
        preempts everything; unresolved conflict about the claim forces
        ``INCONCLUSIVE``; divergence yields ``FAILED``; insufficient corroboration
        yields ``INCONCLUSIVE``; otherwise ``DEGRADED`` or ``HEALTHY``.

        Args:
            correlation: The correlated view of the evidence.
            blocked_reason: Set when a precondition was not met.
            degraded: Whether corroborated anomalies were observed.

        Returns:
            The decided verdict.
        """
        if blocked_reason is not None:
            return Verdict.BLOCKED
        if not correlation.layers_covered:
            return Verdict.INCONCLUSIVE
        if correlation.unresolved_conflicts:
            return Verdict.INCONCLUSIVE
        if correlation.first_divergence is not None:
            return Verdict.FAILED
        if not correlation.satisfies_corroboration:
            return Verdict.INCONCLUSIVE
        return Verdict.DEGRADED if degraded else Verdict.HEALTHY

    def build_finding(
        self,
        *,
        what: str,
        where_component: str,
        why: str,
        evidence: Sequence[Evidence],
        diverged_layers: Iterable[EvidenceLayer] = (),
        claim_layer: EvidenceLayer | None = None,
        blocked_reason: str | None = None,
        degraded: bool = False,
        storage_surface: bool = False,
        upstream_evidenced: bool = True,
        where_artifact: str | None = None,
        plugin_id: str | None = None,
    ) -> Finding:
        """Produce a fully reasoned finding from evidence.

        The engine's main entry point. It correlates the evidence, decides the
        verdict, classifies any failure, and lets :class:`Finding` compute
        confidence -- so a caller cannot accidentally assert a verdict the evidence
        does not support.

        Args:
            what: The observed defect or healthy behaviour.
            where_component: Component the finding concerns.
            why: Causal finding, or :attr:`Finding.UNDETERMINED`.
            evidence: Supporting evidence.
            diverged_layers: Layers the caller determined diverge from expectation.
            claim_layer: Layer the claim principally concerns. Defaults to the
                first diverging layer, or the highest layer with evidence.
            blocked_reason: Set when a precondition was not met.
            degraded: Whether corroborated anomalies were observed.
            storage_surface: Whether an L2 divergence concerns persistence rather
                than capture, distinguishing the two L2 failure classes.
            upstream_evidenced: Whether the layer upstream of a divergence was
                evidenced as sound (§5.2).
            where_artifact: Specific artifact, if applicable.
            plugin_id: Owning plugin.

        Returns:
            The finding, with computed confidence.

        Raises:
            ValidationError: If no evidence was supplied.
        """
        if not evidence:
            raise ValidationError(
                "The validation engine cannot build a finding without evidence",
                {"what": what},
            )
        correlation = self.correlate(
            evidence, diverged_layers=diverged_layers, claim_layer=claim_layer
        )
        resolved_claim_layer = (
            claim_layer
            or correlation.first_divergence
            or max(correlation.layers_covered)
        )
        verdict = self.decide_verdict(
            correlation=correlation, blocked_reason=blocked_reason, degraded=degraded
        )
        failure_class = (
            FailureClass.from_layer(
                correlation.first_divergence, storage_surface=storage_surface
            )
            if verdict is Verdict.FAILED and correlation.first_divergence is not None
            else None
        )
        # A FAILED verdict must carry a classification; if divergence was not
        # localised to a layer, the claim layer is the best-evidenced attribution.
        if verdict is Verdict.FAILED and failure_class is None:
            failure_class = FailureClass.from_layer(
                resolved_claim_layer, storage_surface=storage_surface
            )

        notes: list[str] = []
        if blocked_reason:
            notes.append(f"blocked: {blocked_reason}")
        for conflict in correlation.unresolved_conflicts:
            notes.append(f"unresolved conflict: {conflict.description}")

        return Finding.build(
            what=what,
            where_layer=resolved_claim_layer,
            where_component=where_component,
            why=why,
            evidence=tuple(evidence),
            verdict=verdict,
            minimum_layers=self._minimum_layers,
            conflicts=correlation.conflicts,
            failure_class=failure_class,
            upstream_evidenced=upstream_evidenced,
            where_artifact=where_artifact,
            plugin_id=plugin_id,
            notes=tuple(notes),
        )

    # -- Correlation and aggregation ------------------------------------------

    def correlate(
        self,
        evidence: Sequence[Evidence],
        *,
        diverged_layers: Iterable[EvidenceLayer] = (),
        claim_layer: EvidenceLayer | None = None,
    ) -> CorrelationReport:
        """Correlate evidence across layers.

        Args:
            evidence: Evidence to correlate.
            diverged_layers: Layers determined to diverge from expectation.
            claim_layer: Layer the claim concerns, for conflict precedence.

        Returns:
            The correlation report.
        """
        assessments = self.assess_layers(evidence, diverged_layers=diverged_layers)
        return CorrelationReport(
            assessments=assessments,
            first_divergence=self.first_diverging_layer(assessments),
            conflicts=self.detect_conflicts(evidence, claim_layer=claim_layer),
            layers_covered=tuple(item.layer for item in assessments),
        )

    def aggregate(self, findings: Sequence[Finding]) -> Verdict:
        """Aggregate findings into one verdict.

        Args:
            findings: Findings to aggregate.

        Returns:
            The precedent verdict per §6. With no findings the result is
            ``INCONCLUSIVE``: concluding nothing is not a pass.
        """
        return Verdict.aggregate(finding.verdict for finding in findings)

    def aggregate_confidence(self, findings: Sequence[Finding]) -> Confidence:
        """Return the weakest confidence among findings.

        An aggregate conclusion is only as trustworthy as its weakest support, so
        the minimum is reported rather than an average -- averaging would let one
        strong finding disguise a poorly evidenced one.

        Args:
            findings: Findings to consider.

        Returns:
            The lowest confidence present, or ``UNKNOWN`` when there are none.
        """
        return min(
            (finding.confidence for finding in findings), default=Confidence.UNKNOWN
        )

    def merge_duplicates(self, findings: Sequence[Finding]) -> tuple[Finding, ...]:
        """Merge findings that describe the same defect at the same place.

        Findings are considered duplicates when their ``what``, layer, and
        component match. The merged finding keeps the precedent verdict and the
        union of evidence, then has its confidence recomputed -- combining evidence
        can legitimately raise confidence, but only by recomputation, never by
        assertion.

        Args:
            findings: Findings to merge.

        Returns:
            The merged findings, in a deterministic order.

        Raises:
            ValidationError: If a merged finding cannot be reconstructed.
        """
        grouped: dict[tuple[str, int, str], list[Finding]] = {}
        for finding in findings:
            key = (finding.what, int(finding.where_layer), finding.where_component)
            grouped.setdefault(key, []).append(finding)

        merged: list[Finding] = []
        for key in sorted(grouped):
            group = grouped[key]
            if len(group) == 1:
                merged.append(group[0])
                continue
            combined_evidence: dict[tuple[str, str], Evidence] = {}
            for finding in group:
                for item in finding.evidence:
                    combined_evidence[(item.evidence_id, item.source)] = item
            conflicts = tuple(
                conflict for finding in group for conflict in finding.conflicts
            )
            verdict = Verdict.aggregate(item.verdict for item in group)
            primary = group[0]
            failure_class = next(
                (item.failure_class for item in group if item.failure_class is not None),
                None,
            )
            candidate = replace(
                primary,
                evidence=tuple(
                    combined_evidence[k] for k in sorted(combined_evidence)
                ),
                verdict=verdict,
                conflicts=conflicts,
                failure_class=failure_class if verdict is Verdict.FAILED else None,
                notes=tuple(
                    dict.fromkeys(note for item in group for note in item.notes)
                ),
            )
            merged.append(
                replace(
                    candidate,
                    confidence=candidate.compute_confidence(self._minimum_layers),
                )
            )
        _LOGGER.debug(
            "Finding aggregation: %d input, %d after merge", len(findings), len(merged)
        )
        return tuple(merged)

    def summarise(self, findings: Sequence[Finding]) -> dict[str, object]:
        """Produce a summary of findings.

        Every verdict is counted explicitly so that ``INCONCLUSIVE`` and
        ``BLOCKED`` have nowhere to hide (§10 rule 2).

        Args:
            findings: Findings to summarise.

        Returns:
            A serialisable summary.
        """
        counts = {verdict.value: 0 for verdict in Verdict}
        for finding in findings:
            counts[finding.verdict.value] += 1
        layers = sorted({layer for finding in findings for layer in finding.corroboration})
        return {
            "verdict": self.aggregate(findings).value,
            "confidence": self.aggregate_confidence(findings).name,
            "counts": counts,
            "layers_covered": [layer.label for layer in layers],
            "unresolved_conflicts": sum(
                1 for finding in findings if finding.has_unresolved_conflict
            ),
            "minimum_corroborating_layers": self._minimum_layers,
        }
