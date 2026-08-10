"""Generic, feature-agnostic validators.

These turn :class:`~framework.core.correlation.Correlation` objects into findings.
They contain **no feature logic** -- no screenshot rules, no attendance rules -- so any
feature plugin can use them by supplying its own expectations from its profile.

The division of labour is deliberate and matches the Manifest: the correlation engine
*relates* observations and returns correlations; these validators *conclude* and return
findings. A validator that did its own correlating would be two components in one, and
the boundary that keeps correlation free of judgement would be gone.

Three validators fill genuine gaps left by Phases 2-3:

* :class:`TimestampValidator` -- is an observation recent enough to mean anything?
* :class:`FrequencyValidator` -- does a repeating event occur at its configured rate?
* :class:`CorrelationValidator` -- do the layers agree with each other?

Everything else a feature needs already exists: configuration, runtime, upload, and
queue validation were built in Phases 2 and 3 and are reused rather than reimplemented.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from framework.core.correlation import (
    Agreement,
    Correlation,
    analyse_cadence,
    analyse_freshness,
)
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

__all__ = ["TimestampValidator", "FrequencyValidator", "CorrelationValidator"]

_LOGGER = get_logger(__name__)


def _positive_or_inconclusive(
    evidence: Sequence[Evidence], intended: Verdict, minimum_layers: int
) -> tuple[Verdict, tuple[str, ...]]:
    """Downgrade a positive verdict the evidence cannot support.

    ``HEALTHY`` and ``DEGRADED`` both require corroboration across at least two
    layers with one at L2 or higher (Validation Standard §5.1, §5.4). A generic
    validator cannot know what its caller collected, so every positive verdict passes
    through here instead of being asserted -- otherwise a missing layer becomes a
    crash rather than an honest ``INCONCLUSIVE``.

    Args:
        evidence: Evidence backing the finding.
        intended: The verdict the validator would like to report.
        minimum_layers: Configured corroboration minimum.

    Returns:
        The verdict to use and any note explaining a downgrade.
    """
    layers = {item.layer for item in evidence}
    required = max(int(minimum_layers), 2)
    if len(layers) >= required and any(layer >= EvidenceLayer.RUNTIME for layer in layers):
        return intended, ()
    return (
        Verdict.INCONCLUSIVE,
        (
            f"Downgraded from {intended.value}: supported by "
            f"{sorted(layer.label for layer in layers)} only, which does not meet the "
            "corroboration minimum for a positive verdict.",
        ),
    )


class TimestampValidator(Validator):
    """Concludes whether observations are recent enough to be meaningful.

    Staleness matters independently of correctness: a screenshot record from three
    days ago says nothing about whether capture works *now*, and treating it as
    current would be the easiest way to report a dead feature as healthy.
    """

    def __init__(
        self,
        *,
        subject: str,
        observed_at: datetime | None,
        tolerance_seconds: float,
        component: str,
        layer: EvidenceLayer = EvidenceLayer.RUNTIME,
        evidence: Sequence[Evidence] = (),
    ) -> None:
        """Initialise the validator.

        Args:
            subject: What the timestamp describes.
            observed_at: The timestamp to assess.
            tolerance_seconds: How old it may be and still count as current.
            component: Component the finding concerns.
            layer: Layer the finding is localised to.
            evidence: Evidence supporting the observation.
        """
        self._subject = subject
        self._observed_at = observed_at
        self._tolerance = tolerance_seconds
        self._component = component
        self._layer = layer
        self._evidence = tuple(evidence)

    @property
    def name(self) -> str:
        """Component name."""
        return "generic.timestamp.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Assess freshness.

        Args:
            context: Run context.

        Returns:
            A finding about freshness, or none when no evidence was supplied.
        """
        if not self._evidence:
            return ()
        analysis = analyse_freshness(
            self._observed_at, tolerance_seconds=self._tolerance
        )
        if analysis.is_fresh is None:
            return (
                Finding.build(
                    what=f"could not establish how recent {self._subject} is",
                    where_layer=self._layer,
                    where_component=self._component,
                    why=analysis.reason or Finding.UNDETERMINED,
                    evidence=self._evidence,
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Unknown age is reported as unknown: an observation of unknown "
                        "age cannot support a claim about current behaviour.",
                    ),
                ),
            )
        if analysis.is_fresh:
            verdict, downgrade = _positive_or_inconclusive(
                self._evidence, Verdict.HEALTHY, context.minimum_layers
            )
            return (
                Finding.build(
                    what=f"{self._subject} is current ({analysis.age_seconds:.0f}s old)",
                    where_layer=self._layer,
                    where_component=self._component,
                    why=f"age is within the {self._tolerance:.0f}s tolerance",
                    evidence=self._evidence,
                    verdict=verdict,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=downgrade,
                ),
            )
        return (
            Finding.build(
                what=f"{self._subject} is stale ({analysis.age_seconds:.0f}s old)",
                where_layer=self._layer,
                where_component=self._component,
                why=f"age exceeds the {self._tolerance:.0f}s tolerance",
                evidence=self._evidence,
                verdict=Verdict.DEGRADED
                if _positive_or_inconclusive(
                    self._evidence, Verdict.DEGRADED, context.minimum_layers
                )[0]
                is Verdict.DEGRADED
                else Verdict.INCONCLUSIVE,
                minimum_layers=context.minimum_layers,
                plugin_id=context.plugin_id,
                notes=(
                    "Stale, not absent: the artifact exists but has not been updated "
                    "recently, so the feature may have stopped rather than never started.",
                ),
            ),
        )


class FrequencyValidator(Validator):
    """Concludes whether a repeating event occurs at its configured rate.

    Uses :func:`framework.core.correlation.analyse_cadence`, the single
    implementation of cadence arithmetic in the framework, so a feature's interval
    check and the synchronization scheduler check can never disagree about what
    "every 180 seconds" means.
    """

    def __init__(
        self,
        *,
        subject: str,
        timestamps: Sequence[datetime],
        expected_seconds: float | None,
        component: str,
        tolerance_seconds: float = 30.0,
        minimum_occurrences: int = 2,
        layer: EvidenceLayer = EvidenceLayer.SYNCHRONIZATION,
        evidence: Sequence[Evidence] = (),
    ) -> None:
        """Initialise the validator.

        Args:
            subject: What repeats.
            timestamps: Observed event times.
            expected_seconds: Configured interval, if known.
            component: Component the finding concerns.
            tolerance_seconds: Permitted drift.
            minimum_occurrences: Fewest events needed to measure.
            layer: Layer the finding is localised to.
            evidence: Evidence supporting the observation.
        """
        self._subject = subject
        self._timestamps = tuple(timestamps)
        self._expected = expected_seconds
        self._component = component
        self._tolerance = tolerance_seconds
        self._minimum = minimum_occurrences
        self._layer = layer
        self._evidence = tuple(evidence)

    @property
    def name(self) -> str:
        """Component name."""
        return "generic.frequency.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Assess cadence against the configured interval.

        Args:
            context: Run context.

        Returns:
            A finding about cadence, or none when no evidence was supplied.
        """
        if not self._evidence:
            return ()
        analysis = analyse_cadence(
            self._timestamps,
            expected_seconds=self._expected,
            tolerance_seconds=self._tolerance,
            minimum_occurrences=self._minimum,
        )
        if not analysis.is_measurable:
            return (
                Finding.build(
                    what=f"cadence of {self._subject} could not be measured",
                    where_layer=self._layer,
                    where_component=self._component,
                    why=analysis.reason,
                    evidence=self._evidence,
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "A limit of the observation window, not a defect in the product.",
                    ),
                ),
            )
        if analysis.within_tolerance is None:
            return (
                Finding.build(
                    what=(
                        f"{self._subject} occurs every {analysis.mean_seconds:.1f}s, but "
                        "no configured interval was available to compare against"
                    ),
                    where_layer=self._layer,
                    where_component=self._component,
                    why="the feature profile does not state an expected interval",
                    evidence=self._evidence,
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Regularity alone is not correctness: without the configured "
                        "interval there is nothing to be correct against.",
                    ),
                ),
            )
        if analysis.within_tolerance:
            verdict, downgrade = _positive_or_inconclusive(
                self._evidence, Verdict.HEALTHY, context.minimum_layers
            )
            return (
                Finding.build(
                    what=(
                        f"{self._subject} occurs at its configured "
                        f"{analysis.expected_seconds:.0f}s interval "
                        f"(observed {analysis.mean_seconds:.1f}s)"
                    ),
                    where_layer=self._layer,
                    where_component=self._component,
                    why=(
                        f"drift {analysis.drift_seconds:+.1f}s is within the "
                        f"{self._tolerance:.0f}s tolerance"
                    ),
                    evidence=self._evidence,
                    verdict=verdict,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=downgrade,
                ),
            )
        verdict, downgrade = _positive_or_inconclusive(
            self._evidence, Verdict.DEGRADED, context.minimum_layers
        )
        return (
            Finding.build(
                what=f"{self._subject} does not occur at its configured interval",
                where_layer=self._layer,
                where_component=self._component,
                why=(
                    f"configured {analysis.expected_seconds:.0f}s, observed "
                    f"{analysis.mean_seconds:.1f}s, drift {analysis.drift_seconds:+.1f}s"
                ),
                evidence=self._evidence,
                verdict=verdict,
                minimum_layers=context.minimum_layers,
                plugin_id=context.plugin_id,
                notes=downgrade,
            ),
        )


class CorrelationValidator(Validator):
    """Concludes from a set of cross-layer correlations.

    This is where the framework's central claim becomes a finding: a feature is
    healthy when the layers *agree*, and a disagreement localises the fault to the
    boundary where the layers part company.

    Indeterminate correlations are never treated as agreement. A comparison that
    could not be made is an open question, and rolling it into a pass is exactly the
    failure mode the Validation Standard's ``INCONCLUSIVE`` verdict exists to prevent.
    """

    def __init__(
        self,
        *,
        subject: str,
        correlations: Sequence[Correlation],
        component: str,
        layer: EvidenceLayer = EvidenceLayer.RUNTIME,
        failure_class: FailureClass | None = None,
    ) -> None:
        """Initialise the validator.

        Args:
            subject: What the correlations concern.
            correlations: Correlations to conclude from.
            component: Component the finding concerns.
            layer: Layer the finding is localised to.
            failure_class: Classification to apply when reporting a failure.
        """
        self._subject = subject
        self._correlations = tuple(correlations)
        self._component = component
        self._layer = layer
        self._failure_class = failure_class

    @property
    def name(self) -> str:
        """Component name."""
        return "generic.correlation.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Conclude from the supplied correlations.

        Args:
            context: Run context.

        Returns:
            One finding per outcome class present: a failure for disagreements, an
            open question for indeterminate comparisons, and a positive finding only
            when every comparison agreed.
        """
        if not self._correlations:
            return ()

        disagreements = [
            item for item in self._correlations if item.agreement is Agreement.DISAGREES
        ]
        indeterminate = [
            item for item in self._correlations if item.agreement is Agreement.INDETERMINATE
        ]
        agreements = [
            item for item in self._correlations if item.agreement is Agreement.AGREES
        ]
        findings: list[Finding] = []

        if disagreements:
            evidence = self._evidence_for(disagreements)
            if evidence:
                first = disagreements[0]
                findings.append(
                    Finding.build(
                        what=f"layers disagree about {self._subject}",
                        where_layer=first.layers[0] if first.layers else self._layer,
                        where_component=self._component,
                        why="; ".join(
                            item.reason or item.question for item in disagreements[:3]
                        ),
                        evidence=evidence,
                        verdict=Verdict.FAILED,
                        failure_class=self._failure_class
                        or FailureClass.from_layer(
                            first.layers[0] if first.layers else self._layer
                        ),
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                        notes=tuple(item.question for item in disagreements),
                    )
                )

        if indeterminate:
            evidence = self._evidence_for(indeterminate)
            if evidence:
                findings.append(
                    Finding.build(
                        what=(
                            f"{len(indeterminate)} comparison(s) about {self._subject} "
                            "could not be made"
                        ),
                        where_layer=self._layer,
                        where_component=self._component,
                        why="; ".join(
                            item.reason or item.question for item in indeterminate[:3]
                        ),
                        evidence=evidence,
                        verdict=Verdict.INCONCLUSIVE,
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                        notes=tuple(item.question for item in indeterminate),
                    )
                )

        if agreements and not disagreements:
            evidence = self._evidence_for(agreements)
            cross_layer = [item for item in agreements if item.spans_two_layers]
            if evidence and cross_layer:
                verdict, downgrade = _positive_or_inconclusive(
                    evidence, Verdict.HEALTHY, context.minimum_layers
                )
                findings.append(
                    Finding.build(
                        what=(
                            f"layers agree about {self._subject} "
                            f"({len(cross_layer)} cross-layer comparison(s))"
                        ),
                        where_layer=self._layer,
                        where_component=self._component,
                        why="; ".join(item.question for item in cross_layer[:3]),
                        evidence=evidence,
                        verdict=verdict,
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                        notes=downgrade
                        + (
                            (
                                f"{len(indeterminate)} comparison(s) remain open and are "
                                "reported separately; this finding covers only what was "
                                "actually compared.",
                            )
                            if indeterminate
                            else ()
                        ),
                    )
                )
        return tuple(findings)

    @staticmethod
    def _evidence_for(correlations: Sequence[Correlation]) -> tuple[Evidence, ...]:
        """Collect the distinct evidence backing a set of correlations.

        Args:
            correlations: Correlations to gather evidence from.

        Returns:
            The distinct evidence, in a deterministic order.
        """
        seen: dict[tuple[str, str], Evidence] = {}
        for correlation in correlations:
            for item in correlation.evidence:
                seen[(item.evidence_id, item.source)] = item
        return tuple(seen[key] for key in sorted(seen))
