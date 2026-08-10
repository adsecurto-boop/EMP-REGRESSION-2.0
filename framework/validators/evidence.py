"""Evidence sufficiency validation.

Validates the *evidence itself* rather than the product: did this run gather enough,
from enough independent layers, for its conclusions to mean anything?

This is the check that catches the framework deceiving itself. A run can produce a
page of confident findings while having observed only one layer, and every one of
those findings would be under-corroborated. Individual findings already guard their
own verdicts, but nothing until now asked the question at the level of the *run*:
was the coverage adequate for the claim being made?

It answers to the run, not to the product, so its findings are localised to the
weakest layer involved and never carry a product failure classification.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from framework.shared.constants import MIN_CORROBORATING_LAYERS
from framework.shared.interfaces import Validator
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    Finding,
    SourceReliability,
    ValidationContext,
    Verdict,
)

__all__ = ["EvidenceSufficiencyValidator"]

_LOGGER = get_logger(__name__)


class EvidenceSufficiencyValidator(Validator):
    """Concludes whether a run gathered adequate evidence for its own claims."""

    def __init__(
        self,
        *,
        required_layers: Sequence[EvidenceLayer] = (),
        required_evidence_ids: Sequence[str] = (),
        subject: str = "this run",
    ) -> None:
        """Initialise the validator.

        Args:
            required_layers: Layers the caller's profile says it needs. Empty means
                only the standard's own minimum applies.
            required_evidence_ids: Catalog identifiers the caller expected to collect.
            subject: What the sufficiency assessment concerns.
        """
        self._required_layers = tuple(required_layers)
        self._required_evidence_ids = tuple(required_evidence_ids)
        self._subject = subject

    @property
    def name(self) -> str:
        """Component name."""
        return "evidence.sufficiency.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Assess whether the evidence gathered is sufficient.

        Args:
            context: Run context.

        Returns:
            Findings about coverage gaps. Empty when coverage met every expectation --
            adequate evidence needs no finding of its own, since the findings it
            supports already carry their own confidence.
        """
        evidence = tuple(context.evidence)
        if not evidence:
            return ()

        findings: list[Finding] = []
        present_layers = {item.layer for item in evidence}
        present_ids = {item.evidence_id for item in evidence}

        missing_layers = [
            layer for layer in self._required_layers if layer not in present_layers
        ]
        if missing_layers:
            findings.append(
                Finding.build(
                    what=(
                        f"{self._subject} did not observe "
                        f"{', '.join(layer.label for layer in missing_layers)}"
                    ),
                    where_layer=min(missing_layers),
                    where_component="evidence coverage",
                    why=(
                        "the feature profile requires these layers, and no evidence was "
                        "collected at them"
                    ),
                    evidence=evidence[:2],
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Conclusions drawn without a required layer cannot be complete, "
                        "however confident the individual findings look.",
                    ),
                )
            )

        missing_ids = [
            identifier
            for identifier in self._required_evidence_ids
            if identifier not in present_ids
        ]
        if missing_ids:
            findings.append(
                Finding.build(
                    what=(
                        f"{self._subject} did not collect expected evidence: "
                        f"{', '.join(sorted(missing_ids))}"
                    ),
                    where_layer=min(present_layers),
                    where_component="evidence coverage",
                    why="a collector produced nothing, or none is assigned to these sources",
                    evidence=evidence[:2],
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                )
            )

        minimum = max(int(context.minimum_layers), MIN_CORROBORATING_LAYERS)
        if len(present_layers) < minimum:
            findings.append(
                Finding.build(
                    what=(
                        f"{self._subject} observed only "
                        f"{len(present_layers)} evidence layer(s)"
                    ),
                    where_layer=min(present_layers),
                    where_component="evidence coverage",
                    why=(
                        f"the corroboration minimum is {minimum} layers, so no positive "
                        "conclusion in this run can be fully supported"
                    ),
                    evidence=evidence[:2],
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                )
            )

        if weak := self._only_weak_sources(evidence):
            findings.append(
                Finding.build(
                    what=f"{self._subject} rests entirely on low-reliability evidence",
                    where_layer=min(present_layers),
                    where_component="evidence coverage",
                    why=(
                        "every source collected is rated low reliability, and the standard "
                        "admits such evidence only as corroboration, never as primary"
                    ),
                    evidence=evidence[:2],
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(f"sources: {', '.join(sorted(weak))}",),
                )
            )
        return tuple(findings)

    @staticmethod
    def _only_weak_sources(evidence: Sequence[Evidence]) -> set[str]:
        """Return the source identifiers when every source is low reliability.

        Args:
            evidence: Evidence to assess.

        Returns:
            The identifiers, or an empty set when at least one stronger source is
            present.
        """
        if any(item.reliability > SourceReliability.LOW for item in evidence):
            return set()
        return {item.evidence_id for item in evidence}
