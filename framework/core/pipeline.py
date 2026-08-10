"""The evidence pipeline.

Implements the frozen pipeline shape::

    Collector -> Evidence -> Normalizer -> Validator -> Correlator -> Verdict

Each stage is a registered component satisfying an interface from
:mod:`framework.shared.interfaces`, so a pipeline accepts collectors, normalizers,
validators, and correlators the framework has never seen -- adding one requires no
change here.

Stage failures are isolated per component: one collector that cannot read its
source must not prevent the others from contributing. An isolated failure is
recorded as a pipeline error and surfaces in the result, so it is never silent --
and a pipeline that lost a stage cannot claim full coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from framework.core.hooks import HookPoint, HookRegistry
from framework.core.validation import CorrelationReport, ValidationEngine
from framework.shared.exceptions import EvidenceError, FrameworkError, ValidationError
from framework.shared.interfaces import Collector, Correlator, Normalizer, Validator
from framework.shared.logger import get_logger
from framework.shared.models import (
    Confidence,
    Evidence,
    EvidenceLayer,
    Finding,
    ValidationContext,
    Verdict,
)

__all__ = ["StageError", "PipelineResult", "EvidencePipeline"]

_LOGGER = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class StageError:
    """A failure isolated at one pipeline stage.

    Args:
        stage: Stage name (``"collect"``, ``"normalize"``, ``"validate"``,
            ``"correlate"``).
        component: Component that failed.
        message: Failure description.
    """

    stage: str
    component: str
    message: str


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """The outcome of running the pipeline.

    Args:
        evidence: Evidence after collection and normalization.
        findings: Findings after validation and correlation.
        correlation: The engine's correlated view of the evidence.
        verdict: Aggregate verdict across findings.
        confidence: Weakest confidence among findings.
        errors: Stage failures that were isolated.
        layers_covered: Layers with evidence.
    """

    evidence: Sequence[Evidence] = field(default_factory=tuple)
    findings: Sequence[Finding] = field(default_factory=tuple)
    correlation: CorrelationReport | None = None
    verdict: Verdict = Verdict.INCONCLUSIVE
    confidence: Confidence = Confidence.UNKNOWN
    errors: Sequence[StageError] = field(default_factory=tuple)
    layers_covered: Sequence[EvidenceLayer] = field(default_factory=tuple)

    @property
    def degraded_by_errors(self) -> bool:
        """Whether stage failures mean coverage was incomplete.

        A caller must not read a clean verdict as full coverage when a collector
        failed: the missing evidence might have changed the conclusion.
        """
        return bool(self.errors)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-native summary.

        Returns:
            A serialisable mapping.
        """
        return {
            "verdict": self.verdict.value,
            "confidence": self.confidence.name,
            "evidence_count": len(self.evidence),
            "finding_count": len(self.findings),
            "layers_covered": [layer.label for layer in self.layers_covered],
            "errors": [
                {"stage": error.stage, "component": error.component, "message": error.message}
                for error in self.errors
            ],
        }


class EvidencePipeline:
    """Runs evidence from collection through to a verdict.

    Components are registered rather than hardcoded, and the pipeline holds no
    knowledge of what any of them observe. Registration order is preserved within a
    stage so that a deployment can make normalization order explicit.
    """

    __slots__ = ("_collectors", "_normalizers", "_validators", "_correlators", "_engine", "_hooks")

    def __init__(
        self,
        *,
        engine: ValidationEngine | None = None,
        hooks: HookRegistry | None = None,
    ) -> None:
        """Initialise an empty pipeline.

        Args:
            engine: Validation engine used for correlation and aggregation. A
                default engine is created when omitted.
            hooks: Hook registry for before/after extension points.
        """
        self._collectors: list[Collector] = []
        self._normalizers: list[Normalizer] = []
        self._validators: list[Validator] = []
        self._correlators: list[Correlator] = []
        self._engine = engine or ValidationEngine()
        self._hooks = hooks or HookRegistry()

    @property
    def engine(self) -> ValidationEngine:
        """The validation engine in use."""
        return self._engine

    @property
    def component_counts(self) -> Mapping[str, int]:
        """Counts of registered components by stage."""
        return {
            "collectors": len(self._collectors),
            "normalizers": len(self._normalizers),
            "validators": len(self._validators),
            "correlators": len(self._correlators),
        }

    def add_collector(self, collector: Collector) -> "EvidencePipeline":
        """Register a collector.

        Args:
            collector: Collector to add.

        Returns:
            This pipeline, for chaining.
        """
        self._collectors.append(collector)
        return self

    def add_normalizer(self, normalizer: Normalizer) -> "EvidencePipeline":
        """Register a normalizer.

        Args:
            normalizer: Normalizer to add.

        Returns:
            This pipeline, for chaining.
        """
        self._normalizers.append(normalizer)
        return self

    def add_validator(self, validator: Validator) -> "EvidencePipeline":
        """Register a validator.

        Args:
            validator: Validator to add.

        Returns:
            This pipeline, for chaining.
        """
        self._validators.append(validator)
        return self

    def add_correlator(self, correlator: Correlator) -> "EvidencePipeline":
        """Register a correlator.

        Args:
            correlator: Correlator to add.

        Returns:
            This pipeline, for chaining.
        """
        self._correlators.append(correlator)
        return self

    def _collect(
        self, context: ValidationContext, errors: list[StageError]
    ) -> list[Evidence]:
        """Run every collector, isolating failures.

        Args:
            context: Run context.
            errors: Accumulator for isolated failures.

        Returns:
            Collected evidence.
        """
        collected: list[Evidence] = []
        for collector in self._collectors:
            name = collector.name
            outcome = self._hooks.invoke(
                HookPoint.BEFORE_COLLECTOR, name, execution_id=context.execution_id
            )
            if outcome.vetoed:
                errors.append(
                    StageError("collect", name, f"vetoed by hook: {outcome.veto_reason}")
                )
                continue
            try:
                collector.setup()
                try:
                    produced = tuple(collector.collect(context))
                finally:
                    collector.teardown()
            except (EvidenceError, FrameworkError) as exc:
                errors.append(StageError("collect", name, str(exc)))
                _LOGGER.error("Collector %s failed: %s", name, exc)
                continue
            except Exception as exc:  # noqa: BLE001 -- isolation boundary
                errors.append(StageError("collect", name, f"unexpected error: {exc}"))
                _LOGGER.error("Collector %s raised unexpectedly: %s", name, exc, exc_info=True)
                continue
            collected.extend(produced)
            self._hooks.invoke(
                HookPoint.AFTER_COLLECTOR,
                name,
                execution_id=context.execution_id,
                evidence_count=len(produced),
            )
        return collected

    def _normalize(
        self,
        evidence: Sequence[Evidence],
        context: ValidationContext,
        errors: list[StageError],
    ) -> list[Evidence]:
        """Run every normalizer in registration order, isolating failures.

        A normalizer that fails leaves the evidence as it was, rather than dropping
        it: unnormalized evidence is still evidence.

        Args:
            evidence: Evidence to normalize.
            context: Run context.
            errors: Accumulator for isolated failures.

        Returns:
            Normalized evidence.
        """
        current = list(evidence)
        for normalizer in self._normalizers:
            name = normalizer.name
            outcome = self._hooks.invoke(
                HookPoint.BEFORE_NORMALIZER, name, execution_id=context.execution_id
            )
            if outcome.vetoed:
                errors.append(
                    StageError("normalize", name, f"vetoed by hook: {outcome.veto_reason}")
                )
                continue
            try:
                current = list(normalizer.normalize(current))
            except Exception as exc:  # noqa: BLE001 -- isolation boundary
                errors.append(StageError("normalize", name, str(exc)))
                _LOGGER.error("Normalizer %s failed: %s", name, exc, exc_info=True)
                continue
            self._hooks.invoke(
                HookPoint.AFTER_NORMALIZER,
                name,
                execution_id=context.execution_id,
                evidence_count=len(current),
            )
        return current

    def _validate(
        self, context: ValidationContext, errors: list[StageError]
    ) -> list[Finding]:
        """Run every validator, isolating failures.

        Args:
            context: Run context carrying the normalized evidence.
            errors: Accumulator for isolated failures.

        Returns:
            Findings produced.
        """
        findings: list[Finding] = []
        for validator in self._validators:
            name = validator.name
            outcome = self._hooks.invoke(
                HookPoint.BEFORE_VALIDATOR, name, execution_id=context.execution_id
            )
            if outcome.vetoed:
                errors.append(
                    StageError("validate", name, f"vetoed by hook: {outcome.veto_reason}")
                )
                continue
            try:
                validator.setup()
                try:
                    produced = tuple(validator.validate(context))
                finally:
                    validator.teardown()
            except (ValidationError, FrameworkError) as exc:
                errors.append(StageError("validate", name, str(exc)))
                _LOGGER.error("Validator %s failed: %s", name, exc)
                continue
            except Exception as exc:  # noqa: BLE001 -- isolation boundary
                errors.append(StageError("validate", name, f"unexpected error: {exc}"))
                _LOGGER.error("Validator %s raised unexpectedly: %s", name, exc, exc_info=True)
                continue
            findings.extend(produced)
            self._hooks.invoke(
                HookPoint.AFTER_VALIDATOR,
                name,
                execution_id=context.execution_id,
                finding_count=len(produced),
            )
        return findings

    def _correlate(
        self,
        findings: Sequence[Finding],
        context: ValidationContext,
        errors: list[StageError],
    ) -> list[Finding]:
        """Run every correlator, isolating failures.

        Args:
            findings: Findings to correlate.
            context: Run context.
            errors: Accumulator for isolated failures.

        Returns:
            Reconciled findings.
        """
        current = list(findings)
        for correlator in self._correlators:
            name = correlator.name
            outcome = self._hooks.invoke(
                HookPoint.BEFORE_CORRELATOR, name, execution_id=context.execution_id
            )
            if outcome.vetoed:
                errors.append(
                    StageError("correlate", name, f"vetoed by hook: {outcome.veto_reason}")
                )
                continue
            try:
                current = list(correlator.correlate(current, context))
            except Exception as exc:  # noqa: BLE001 -- isolation boundary
                errors.append(StageError("correlate", name, str(exc)))
                _LOGGER.error("Correlator %s failed: %s", name, exc, exc_info=True)
                continue
            self._hooks.invoke(
                HookPoint.AFTER_CORRELATOR,
                name,
                execution_id=context.execution_id,
                finding_count=len(current),
            )
        return current

    def run(self, context: ValidationContext) -> PipelineResult:
        """Run the full pipeline.

        Args:
            context: Run context. Evidence already present on the context is
                carried forward, so a pipeline can build on evidence collected
                earlier in the run.

        Returns:
            The pipeline result, including verdict, confidence, and any isolated
            stage failures.
        """
        errors: list[StageError] = []

        collected = self._collect(context, errors)
        combined = list(context.evidence) + collected
        normalized = self._normalize(combined, context, errors)

        # Rebuild the context so validators see exactly the normalized evidence.
        # Appending to the original would leave both pre- and post-normalization
        # copies visible, and a validator comparing the two would find spurious
        # disagreement between what is really one observation.
        validation_context = ValidationContext(
            execution_id=context.execution_id,
            environment=context.environment,
            agent=context.agent,
            dashboard=context.dashboard,
            evidence=tuple(normalized),
            minimum_layers=context.minimum_layers,
            plugin_id=context.plugin_id,
            metadata=context.metadata,
        )

        findings = self._validate(validation_context, errors)
        findings = self._correlate(findings, validation_context, errors)
        findings = list(self._engine.merge_duplicates(findings))

        correlation = self._engine.correlate(tuple(normalized))
        result = PipelineResult(
            evidence=tuple(normalized),
            findings=tuple(findings),
            correlation=correlation,
            verdict=self._engine.aggregate(findings),
            confidence=self._engine.aggregate_confidence(findings),
            errors=tuple(errors),
            layers_covered=correlation.layers_covered,
        )
        _LOGGER.info(
            "Pipeline complete: %d evidence, %d finding(s), verdict=%s, %d stage error(s)",
            len(result.evidence),
            len(result.findings),
            result.verdict.value,
            len(result.errors),
        )
        return result
