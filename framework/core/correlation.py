"""Feature correlation engine.

Answers cross-layer questions of the form "does X agree with Y?" and returns
**correlation objects, never verdicts**. A correlation states whether two
observations agree; deciding what that *means* is a validator's job, and keeping
the two apart is what stops correlation quietly becoming judgement.

The five questions the engine answers:

* Does runtime match configuration?          (L1 ↔ L2)
* Does dashboard match runtime?              (L2 ↔ L4)
* Does synchronization match dashboard?      (L3 ↔ L4)
* Does SQLite match logs?                    (L2 ↔ L3)
* Does configuration explain runtime?        (L1 → L2, directional)

This module is also the **single home for cadence and freshness arithmetic**. Phase 3
computed cadence inside ``SchedulerValidator``; a second copy for feature intervals
would have been two implementations of one calculation, free to disagree. Both now
call :func:`analyse_cadence`.

Correlation is deliberately *not* the same thing as
:meth:`framework.core.validation.ValidationEngine.correlate`, which detects conflicts
between evidence about one subject. This engine relates observations across
*different* layers. Conflict detection is delegated, not duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Sequence

from framework.shared.logger import get_logger
from framework.shared.models import Evidence, EvidenceLayer, utc_now

__all__ = [
    "Agreement",
    "Correlation",
    "CadenceAnalysis",
    "FreshnessAnalysis",
    "analyse_cadence",
    "analyse_freshness",
    "FeatureCorrelationEngine",
]

_LOGGER = get_logger(__name__)


class Agreement(Enum):
    """Whether two observations agree.

    Deliberately **not** a verdict. ``DISAGREES`` does not mean "failed" -- two
    layers disagreeing might mean the product is broken, or that one observation was
    taken at the wrong moment, or that an expectation is wrong. Only a validator,
    applying the Validation Standard, may turn this into a verdict.
    """

    AGREES = "AGREES"
    DISAGREES = "DISAGREES"
    INDETERMINATE = "INDETERMINATE"
    """One or both sides could not be observed, so no comparison was possible."""

    @property
    def is_comparable(self) -> bool:
        """Whether a comparison was actually possible."""
        return self is not Agreement.INDETERMINATE


@dataclass(frozen=True, slots=True)
class Correlation:
    """The result of relating two observations.

    Args:
        question: What was asked, in plain language.
        agreement: Whether the two sides agree.
        left_layer: Layer of the first observation.
        right_layer: Layer of the second observation.
        left: What the first side showed.
        right: What the second side showed.
        detail: Structured supporting detail.
        evidence: Evidence backing both sides, for a validator to cite.
        reason: Why the sides disagree or could not be compared.
    """

    question: str
    agreement: Agreement
    left_layer: EvidenceLayer | None = None
    right_layer: EvidenceLayer | None = None
    left: str = ""
    right: str = ""
    detail: Mapping[str, Any] = field(default_factory=dict)
    evidence: Sequence[Evidence] = field(default_factory=tuple)
    reason: str = ""

    @property
    def layers(self) -> tuple[EvidenceLayer, ...]:
        """The distinct layers this correlation spans, in layer order."""
        return tuple(
            sorted({layer for layer in (self.left_layer, self.right_layer) if layer})
        )

    @property
    def spans_two_layers(self) -> bool:
        """Whether the correlation genuinely relates two different layers.

        A validator needs this: a "correlation" within one layer cannot supply the
        cross-layer corroboration a positive verdict requires.
        """
        return len(self.layers) >= 2

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "question": self.question,
            "agreement": self.agreement.value,
            "left_layer": self.left_layer.label if self.left_layer else None,
            "right_layer": self.right_layer.label if self.right_layer else None,
            "left": self.left,
            "right": self.right,
            "spans_two_layers": self.spans_two_layers,
            "reason": self.reason,
            "detail": dict(self.detail),
            "evidence": [item.evidence_id for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class CadenceAnalysis:
    """Measured cadence of a repeating event.

    Args:
        occurrences: How many events were seen.
        intervals: Measured gaps between consecutive events, in seconds.
        mean_seconds: Mean interval, or ``None`` when fewer than two events.
        spread_seconds: Difference between the longest and shortest interval.
        expected_seconds: Configured expectation, when one was supplied.
        drift_seconds: Mean minus expected, when both are known.
        within_tolerance: Whether drift is inside the supplied tolerance.
        reason: Why the analysis is incomplete, when it is.
    """

    occurrences: int
    intervals: Sequence[float] = field(default_factory=tuple)
    mean_seconds: float | None = None
    spread_seconds: float | None = None
    expected_seconds: float | None = None
    drift_seconds: float | None = None
    within_tolerance: bool | None = None
    reason: str = ""

    @property
    def is_measurable(self) -> bool:
        """Whether a cadence could be measured at all."""
        return self.mean_seconds is not None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "occurrences": self.occurrences,
            "intervals_seconds": list(self.intervals),
            "mean_seconds": self.mean_seconds,
            "spread_seconds": self.spread_seconds,
            "expected_seconds": self.expected_seconds,
            "drift_seconds": self.drift_seconds,
            "within_tolerance": self.within_tolerance,
            "reason": self.reason,
        }


def analyse_cadence(
    timestamps: Sequence[datetime],
    *,
    expected_seconds: float | None = None,
    tolerance_seconds: float = 30.0,
    minimum_occurrences: int = 2,
) -> CadenceAnalysis:
    """Measure the cadence of a repeating event.

    The single implementation of this calculation in the framework. Two events give
    one interval, so ``minimum_occurrences`` of two is the floor below which cadence
    is not a measurement but a guess.

    Args:
        timestamps: Event times, in any order.
        expected_seconds: Configured interval to compare against, if known.
        tolerance_seconds: Permitted drift from the expectation.
        minimum_occurrences: Fewest events needed to measure an interval.

    Returns:
        The analysis. When too few events were seen, ``mean_seconds`` is ``None`` and
        ``reason`` says so -- an unmeasurable cadence is reported, never estimated.
    """
    ordered = sorted(item for item in timestamps if item is not None)
    if len(ordered) < max(2, minimum_occurrences):
        return CadenceAnalysis(
            occurrences=len(ordered),
            expected_seconds=expected_seconds,
            reason=(
                f"{len(ordered)} occurrence(s) observed; at least "
                f"{max(2, minimum_occurrences)} are needed to measure an interval"
            ),
        )

    intervals = [
        (later - earlier).total_seconds()
        for earlier, later in zip(ordered, ordered[1:], strict=False)
    ]
    mean = sum(intervals) / len(intervals)
    spread = max(intervals) - min(intervals)
    drift = None if expected_seconds is None else mean - float(expected_seconds)
    return CadenceAnalysis(
        occurrences=len(ordered),
        intervals=tuple(intervals),
        mean_seconds=mean,
        spread_seconds=spread,
        expected_seconds=expected_seconds,
        drift_seconds=drift,
        within_tolerance=None if drift is None else abs(drift) <= float(tolerance_seconds),
    )


@dataclass(frozen=True, slots=True)
class FreshnessAnalysis:
    """How recent an observation is.

    Args:
        observed_at: The timestamp examined.
        age_seconds: How long ago it was, in seconds.
        tolerance_seconds: Permitted age.
        is_fresh: Whether it is within tolerance.
        reason: Why freshness could not be established, when it could not.
    """

    observed_at: datetime | None
    age_seconds: float | None = None
    tolerance_seconds: float | None = None
    is_fresh: bool | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "observed_at": self.observed_at.isoformat() if self.observed_at else None,
            "age_seconds": self.age_seconds,
            "tolerance_seconds": self.tolerance_seconds,
            "is_fresh": self.is_fresh,
            "reason": self.reason,
        }


def analyse_freshness(
    observed_at: datetime | None,
    *,
    tolerance_seconds: float,
    now: datetime | None = None,
) -> FreshnessAnalysis:
    """Measure how recent an observation is.

    Args:
        observed_at: Timestamp to examine. A naive value is treated as UTC, since
            every framework timestamp is UTC by contract.
        tolerance_seconds: Permitted age.
        now: Reference time; defaults to the current time.

    Returns:
        The analysis. A missing timestamp yields ``is_fresh=None`` -- unknown
        freshness is reported as unknown, not as stale.
    """
    if observed_at is None:
        return FreshnessAnalysis(
            observed_at=None,
            tolerance_seconds=tolerance_seconds,
            reason="no timestamp was observed",
        )
    stamped = (
        observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=timezone.utc)
    )
    reference = now or utc_now()
    age = (reference - stamped).total_seconds()
    return FreshnessAnalysis(
        observed_at=stamped,
        age_seconds=age,
        tolerance_seconds=tolerance_seconds,
        is_fresh=age <= float(tolerance_seconds),
    )


class FeatureCorrelationEngine:
    """Relates observations across evidence layers.

    Returns :class:`Correlation` objects only. It holds no thresholds of its own and
    no feature knowledge: every expectation is passed in by the caller, so the engine
    is reusable by any feature plugin without modification.
    """

    __slots__ = ()

    @staticmethod
    def _find(
        evidence: Sequence[Evidence], layer: EvidenceLayer, source_prefix: str = ""
    ) -> Evidence | None:
        """Return the last evidence matching a layer and optional source prefix.

        Args:
            evidence: Evidence to search.
            layer: Layer to match.
            source_prefix: Source prefix to match, or empty for any.

        Returns:
            The matching evidence, or ``None``.
        """
        matches = [
            item
            for item in evidence
            if item.layer is layer and item.source.startswith(source_prefix)
        ]
        return matches[-1] if matches else None

    def _indeterminate(
        self,
        question: str,
        *,
        reason: str,
        left_layer: EvidenceLayer | None = None,
        right_layer: EvidenceLayer | None = None,
        evidence: Sequence[Evidence] = (),
    ) -> Correlation:
        """Build an indeterminate correlation.

        Args:
            question: What was asked.
            reason: Why no comparison was possible.
            left_layer: Layer of the first side.
            right_layer: Layer of the second side.
            evidence: Whatever evidence was available.

        Returns:
            The correlation.
        """
        return Correlation(
            question=question,
            agreement=Agreement.INDETERMINATE,
            left_layer=left_layer,
            right_layer=right_layer,
            reason=reason,
            evidence=tuple(evidence),
        )

    def runtime_matches_configuration(
        self,
        evidence: Sequence[Evidence],
        *,
        expectation: str,
        configured: Any,
        observed: Any,
        configuration_evidence: Evidence | None = None,
        runtime_evidence: Evidence | None = None,
    ) -> Correlation:
        """Relate a configured intent to the runtime reality it should produce.

        This is the correlation that matters most: Layer 1 alone proves intent and
        Layer 2 alone proves activity, and only together do they support a positive
        conclusion (Validation Standard §5.1).

        Args:
            evidence: All available evidence, used to find the two sides when they
                are not supplied directly.
            expectation: What is being compared, in plain language.
            configured: The configured value or state.
            observed: The observed value or state.
            configuration_evidence: Layer 1 evidence, located automatically when
                omitted.
            runtime_evidence: Layer 2 evidence, located automatically when omitted.

        Returns:
            The correlation.
        """
        question = f"does runtime match configuration for {expectation}?"
        left = configuration_evidence or self._find(evidence, EvidenceLayer.CONFIGURATION)
        right = runtime_evidence or self._find(evidence, EvidenceLayer.RUNTIME)
        if configured is None or observed is None:
            return self._indeterminate(
                question,
                reason=(
                    "configuration did not state an expectation"
                    if configured is None
                    else "runtime state was not observed"
                ),
                left_layer=EvidenceLayer.CONFIGURATION,
                right_layer=EvidenceLayer.RUNTIME,
                evidence=[item for item in (left, right) if item],
            )
        agrees = self._values_agree(configured, observed)
        return Correlation(
            question=question,
            agreement=Agreement.AGREES if agrees else Agreement.DISAGREES,
            left_layer=EvidenceLayer.CONFIGURATION,
            right_layer=EvidenceLayer.RUNTIME,
            left=f"configured: {configured}",
            right=f"observed: {observed}",
            detail={"expectation": expectation, "configured": configured, "observed": observed},
            evidence=tuple(item for item in (left, right) if item),
            reason="" if agrees else f"configuration expects {configured}, runtime shows {observed}",
        )

    def configuration_explains_runtime(
        self,
        evidence: Sequence[Evidence],
        *,
        observation: str,
        candidate_explanations: Mapping[str, Any],
        configuration_evidence: Evidence | None = None,
        runtime_evidence: Evidence | None = None,
    ) -> Correlation:
        """Ask whether configuration accounts for an observed runtime state.

        Directional and deliberately distinct from
        :meth:`runtime_matches_configuration`: some runtime states are *explained* by
        configuration rather than *equal* to it. A queue holding one row is explained
        by a six-hourly send interval, and calling that a mismatch would be wrong.

        Args:
            evidence: All available evidence.
            observation: The runtime state needing explanation.
            candidate_explanations: Configured settings that could account for it,
                keyed by setting name. An empty mapping means nothing was found.
            configuration_evidence: Layer 1 evidence.
            runtime_evidence: Layer 2 evidence.

        Returns:
            The correlation. ``AGREES`` means configuration explains the observation.
        """
        question = f"does configuration explain {observation}?"
        left = configuration_evidence or self._find(evidence, EvidenceLayer.CONFIGURATION)
        right = runtime_evidence or self._find(evidence, EvidenceLayer.RUNTIME)
        if not candidate_explanations:
            return Correlation(
                question=question,
                agreement=Agreement.DISAGREES,
                left_layer=EvidenceLayer.CONFIGURATION,
                right_layer=EvidenceLayer.RUNTIME,
                left="no configured setting accounts for this",
                right=observation,
                evidence=tuple(item for item in (left, right) if item),
                reason="no configured setting was found that would produce this state",
            )
        return Correlation(
            question=question,
            agreement=Agreement.AGREES,
            left_layer=EvidenceLayer.CONFIGURATION,
            right_layer=EvidenceLayer.RUNTIME,
            left=", ".join(f"{key}={value}" for key, value in sorted(candidate_explanations.items())),
            right=observation,
            detail={"explanations": dict(candidate_explanations)},
            evidence=tuple(item for item in (left, right) if item),
        )

    def sqlite_matches_logs(
        self,
        evidence: Sequence[Evidence],
        *,
        subject: str,
        database_count: int | None,
        log_count: int | None,
        tolerance: int = 0,
    ) -> Correlation:
        """Relate a count observed in the database to one observed in logs.

        Args:
            evidence: All available evidence.
            subject: What is being counted.
            database_count: Count from the database, or ``None`` if unobserved.
            log_count: Count from logs, or ``None`` if unobserved.
            tolerance: Permitted difference. A non-zero tolerance is usually right:
                the two observations are taken at slightly different moments.

        Returns:
            The correlation.
        """
        question = f"does the database agree with the logs about {subject}?"
        database_evidence = self._find(evidence, EvidenceLayer.RUNTIME, "local database")
        log_evidence = self._find(evidence, EvidenceLayer.SYNCHRONIZATION, "synchronization:log")
        if database_count is None or log_count is None:
            return self._indeterminate(
                question,
                reason=(
                    "the database count was not observed"
                    if database_count is None
                    else "the log count was not observed"
                ),
                left_layer=EvidenceLayer.RUNTIME,
                right_layer=EvidenceLayer.SYNCHRONIZATION,
                evidence=[item for item in (database_evidence, log_evidence) if item],
            )
        difference = abs(int(database_count) - int(log_count))
        agrees = difference <= int(tolerance)
        return Correlation(
            question=question,
            agreement=Agreement.AGREES if agrees else Agreement.DISAGREES,
            left_layer=EvidenceLayer.RUNTIME,
            right_layer=EvidenceLayer.SYNCHRONIZATION,
            left=f"database: {database_count}",
            right=f"logs: {log_count}",
            detail={"difference": difference, "tolerance": tolerance},
            evidence=tuple(item for item in (database_evidence, log_evidence) if item),
            reason="" if agrees else f"counts differ by {difference}, tolerance {tolerance}",
        )

    def dashboard_matches_runtime(
        self,
        evidence: Sequence[Evidence],
        *,
        subject: str,
        runtime_state: Any = None,
        dashboard_state: Any = None,
    ) -> Correlation:
        """Relate dashboard state to runtime state.

        Returns ``INDETERMINATE`` whenever no dashboard observation exists -- which is
        every case until a dashboard collector is built. That is the honest answer:
        the framework has no Layer 4 evidence, so it cannot compare against it, and
        must not pretend the comparison succeeded.

        Args:
            evidence: All available evidence.
            subject: What is being compared.
            runtime_state: Observed runtime state.
            dashboard_state: Observed dashboard state.

        Returns:
            The correlation.
        """
        question = f"does the dashboard match runtime for {subject}?"
        dashboard_evidence = self._find(evidence, EvidenceLayer.DASHBOARD)
        runtime_evidence = self._find(evidence, EvidenceLayer.RUNTIME)
        if dashboard_state is None or dashboard_evidence is None:
            return self._indeterminate(
                question,
                reason=(
                    "no Layer 4 evidence exists: the dashboard collector is an interface "
                    "only, so dashboard state cannot be compared"
                ),
                left_layer=EvidenceLayer.RUNTIME,
                right_layer=EvidenceLayer.DASHBOARD,
                evidence=[item for item in (runtime_evidence,) if item],
            )
        agrees = self._values_agree(runtime_state, dashboard_state)
        return Correlation(
            question=question,
            agreement=Agreement.AGREES if agrees else Agreement.DISAGREES,
            left_layer=EvidenceLayer.RUNTIME,
            right_layer=EvidenceLayer.DASHBOARD,
            left=f"runtime: {runtime_state}",
            right=f"dashboard: {dashboard_state}",
            evidence=tuple(item for item in (runtime_evidence, dashboard_evidence) if item),
            reason="" if agrees else "runtime and dashboard disagree",
        )

    def synchronization_matches_dashboard(
        self,
        evidence: Sequence[Evidence],
        *,
        subject: str,
        uploaded: Any = None,
        displayed: Any = None,
    ) -> Correlation:
        """Relate what was uploaded to what the dashboard displays.

        The end-to-end correlation that separates a synchronization defect from a
        surfacing defect. Like :meth:`dashboard_matches_runtime`, it is
        ``INDETERMINATE`` until Layer 4 evidence exists.

        Args:
            evidence: All available evidence.
            subject: What is being compared.
            uploaded: What synchronization reported sending.
            displayed: What the dashboard shows.

        Returns:
            The correlation.
        """
        question = f"does the dashboard show what synchronization uploaded for {subject}?"
        sync_evidence = self._find(evidence, EvidenceLayer.SYNCHRONIZATION)
        dashboard_evidence = self._find(evidence, EvidenceLayer.DASHBOARD)
        if displayed is None or dashboard_evidence is None:
            return self._indeterminate(
                question,
                reason=(
                    "no Layer 4 evidence exists, so an upload cannot be traced to what "
                    "the dashboard displays"
                ),
                left_layer=EvidenceLayer.SYNCHRONIZATION,
                right_layer=EvidenceLayer.DASHBOARD,
                evidence=[item for item in (sync_evidence,) if item],
            )
        agrees = self._values_agree(uploaded, displayed)
        return Correlation(
            question=question,
            agreement=Agreement.AGREES if agrees else Agreement.DISAGREES,
            left_layer=EvidenceLayer.SYNCHRONIZATION,
            right_layer=EvidenceLayer.DASHBOARD,
            left=f"uploaded: {uploaded}",
            right=f"displayed: {displayed}",
            evidence=tuple(item for item in (sync_evidence, dashboard_evidence) if item),
            reason="" if agrees else "uploaded and displayed values differ",
        )

    def cadence_matches_expectation(
        self,
        evidence: Sequence[Evidence],
        *,
        subject: str,
        timestamps: Sequence[datetime],
        expected_seconds: float | None,
        tolerance_seconds: float = 30.0,
        minimum_occurrences: int = 2,
    ) -> Correlation:
        """Relate an observed cadence to a configured interval.

        Args:
            evidence: All available evidence.
            subject: What repeats.
            timestamps: Observed event times.
            expected_seconds: Configured interval, if known.
            tolerance_seconds: Permitted drift.
            minimum_occurrences: Fewest events needed to measure.

        Returns:
            The correlation, carrying the full :class:`CadenceAnalysis` in its detail.
        """
        question = f"does the observed cadence of {subject} match its configured interval?"
        analysis = analyse_cadence(
            timestamps,
            expected_seconds=expected_seconds,
            tolerance_seconds=tolerance_seconds,
            minimum_occurrences=minimum_occurrences,
        )
        configuration_evidence = self._find(evidence, EvidenceLayer.CONFIGURATION)
        observation_evidence = self._find(
            evidence, EvidenceLayer.SYNCHRONIZATION
        ) or self._find(evidence, EvidenceLayer.RUNTIME)
        supporting = tuple(
            item for item in (configuration_evidence, observation_evidence) if item
        )

        if not analysis.is_measurable or analysis.within_tolerance is None:
            return Correlation(
                question=question,
                agreement=Agreement.INDETERMINATE,
                left_layer=EvidenceLayer.CONFIGURATION,
                right_layer=(
                    observation_evidence.layer if observation_evidence else None
                ),
                detail={"cadence": analysis.to_dict()},
                evidence=supporting,
                reason=analysis.reason
                or "no configured interval was available to compare against",
            )
        return Correlation(
            question=question,
            agreement=Agreement.AGREES if analysis.within_tolerance else Agreement.DISAGREES,
            left_layer=EvidenceLayer.CONFIGURATION,
            right_layer=observation_evidence.layer if observation_evidence else None,
            left=f"configured: {analysis.expected_seconds}s",
            right=f"observed: {analysis.mean_seconds:.1f}s",
            detail={"cadence": analysis.to_dict()},
            evidence=supporting,
            reason=(
                ""
                if analysis.within_tolerance
                else f"drift {analysis.drift_seconds:+.1f}s exceeds tolerance "
                f"{tolerance_seconds:.0f}s"
            ),
        )

    @staticmethod
    def _values_agree(left: Any, right: Any) -> bool:
        """Compare two values tolerantly.

        Booleans, numbers, and strings arrive from different sources in different
        shapes -- ``"1"`` from an INI file and ``True`` from a process check describe
        the same state. Comparing them strictly would report disagreement where there
        is none.

        Args:
            left: First value.
            right: Second value.

        Returns:
            ``True`` when the two describe the same state.
        """
        if isinstance(left, bool) or isinstance(right, bool):
            return _as_bool(left) == _as_bool(right)
        try:
            return abs(float(left) - float(right)) < 1e-9
        except (TypeError, ValueError):
            return str(left).strip().casefold() == str(right).strip().casefold()

    def summarise(self, correlations: Sequence[Correlation]) -> dict[str, Any]:
        """Summarise a set of correlations.

        Args:
            correlations: Correlations to summarise.

        Returns:
            A serialisable summary. Indeterminate correlations are counted in their
            own right rather than folded into agreement or disagreement.
        """
        counts = {agreement.value: 0 for agreement in Agreement}
        for correlation in correlations:
            counts[correlation.agreement.value] += 1
        return {
            "total": len(correlations),
            "counts": counts,
            "cross_layer": sum(1 for item in correlations if item.spans_two_layers),
            "disagreements": [
                item.to_dict() for item in correlations if item.agreement is Agreement.DISAGREES
            ],
            "indeterminate": [
                item.question
                for item in correlations
                if item.agreement is Agreement.INDETERMINATE
            ],
        }


def _as_bool(value: Any) -> bool:
    """Interpret a value as a boolean.

    Args:
        value: Value to interpret.

    Returns:
        The boolean reading. Recognises the string forms configuration files use.
    """
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    return text in ("1", "true", "yes", "on", "enabled", "running", "present")
