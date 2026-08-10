"""Knowledge promotion.

Turns observations into candidate knowledge-base records, moving a claim along
``Hypothesis`` → ``Partially Verified`` → ``Verified`` per
``knowledge_base/README.md`` §6–§7.

**Promotion is proposed, never applied.** The workflow requires a reviewer other
than the author to confirm a promotion (§7 step 4), so this module emits records
carrying every mandatory metadata field and leaves ``reviewer`` unset. Writing
straight into the knowledge base would bypass the one control that keeps its
contents trustworthy -- and a framework that promotes its own findings unreviewed
would be marking its own homework.

The status a claim earns is decided mechanically:

* **Verified** -- directly observed, and corroborated by a second independent layer.
* **Partially Verified** -- observed once, from a single layer, or observed only
  indirectly.
* **Hypothesis** -- not observed; recorded so the open question is not lost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from framework.shared.logger import get_logger
from framework.shared.models import (
    Confidence,
    Evidence,
    EvidenceLayer,
    Finding,
    Verdict,
    utc_now,
)

__all__ = ["VerificationStatus", "PromotionRecord", "build_promotions"]

_LOGGER = get_logger(__name__)


class VerificationStatus:
    """The knowledge-base verification statuses.

    A plain container of constants rather than an enum: these values are the
    knowledge base's vocabulary, and they are written into documents as text.
    """

    VERIFIED = "Verified"
    PARTIALLY_VERIFIED = "Partially Verified"
    HYPOTHESIS = "Hypothesis"
    DEPRECATED = "Deprecated"


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    """A proposed knowledge-base claim.

    Args:
        claim: The behaviour being recorded.
        status: Proposed verification status.
        target_document: Which RE document the claim belongs in.
        evidence_ids: Evidence Catalog identifiers supporting it.
        collector: Component that observed it.
        observed_at: When it was observed.
        agent_version: Product version observed against.
        verification_method: How it was observed.
        supporting: Corroborating detail.
        layers: Evidence layers that contributed.
        reviewer: Left unset -- a human must confirm the promotion.
        notes: Why this status and not a higher one.
    """

    claim: str
    status: str
    target_document: str
    evidence_ids: Sequence[str] = field(default_factory=tuple)
    collector: str = ""
    observed_at: datetime = field(default_factory=utc_now)
    agent_version: str | None = None
    verification_method: str = ""
    supporting: Mapping[str, Any] = field(default_factory=dict)
    layers: Sequence[str] = field(default_factory=tuple)
    reviewer: str | None = None
    notes: Sequence[str] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping carrying every field the verification workflow
            requires, with ``reviewer`` explicitly ``None`` until a human signs off.
        """
        return {
            "claim": self.claim,
            "status": self.status,
            "target_document": self.target_document,
            "evidence_source": list(self.evidence_ids),
            "collector": self.collector,
            "verified_on": self.observed_at.date().isoformat(),
            "observed_at": self.observed_at.isoformat(),
            "verified_against_version": self.agent_version,
            "verification_method": self.verification_method,
            "supporting_evidence": dict(self.supporting),
            "layers": list(self.layers),
            "reviewer": self.reviewer,
            "last_review_date": self.observed_at.date().isoformat(),
            "notes": list(self.notes),
            "requires_review_before_promotion": True,
        }


def _status_for(finding: Finding) -> tuple[str, tuple[str, ...]]:
    """Decide the verification status a finding's claim has earned.

    Args:
        finding: The finding to assess.

    Returns:
        The status and the notes explaining why it is not higher.
    """
    layers = finding.corroboration
    if finding.verdict is Verdict.INCONCLUSIVE:
        return (
            VerificationStatus.HYPOTHESIS,
            (
                "Recorded as an open question: the observation could not settle it, so "
                "no behaviour is claimed.",
            ),
        )
    if len(layers) >= 2 and finding.confidence >= Confidence.HIGH:
        return VerificationStatus.VERIFIED, ()
    if len(layers) >= 2:
        return (
            VerificationStatus.PARTIALLY_VERIFIED,
            (
                f"Corroborated across {len(layers)} layer(s) but computed confidence is "
                f"{finding.confidence.name}; a contributing source is weak.",
            ),
        )
    return (
        VerificationStatus.PARTIALLY_VERIFIED,
        (
            "Observed from a single evidence layer. Promotion to Verified requires "
            "independent corroboration from another layer.",
        ),
    )


def _target_document(component: str) -> str:
    """Map a finding's component onto the RE document that owns it.

    Args:
        component: The finding's component, e.g. ``"synchronization:queue"``.

    Returns:
        The owning document identifier.
    """
    mapping = {
        "synchronization:scheduler": "RE-003_Scheduler",
        "synchronization:queue": "RE-012_Offline_Synchronization",
        "synchronization:authentication": "RE-006_API_Flow",
        "synchronization:upload": "RE-004_Upload_Pipeline",
        "synchronization:retry": "RE-004_Upload_Pipeline",
        "synchronization:recovery": "RE-011_Recovery_Behaviour",
        "synchronization:latency": "RE-004_Upload_Pipeline",
        "synchronization:pipeline": "RE-004_Upload_Pipeline",
        "synchronization:network": "RE-006_API_Flow",
    }
    return mapping.get(component, "RE-004_Upload_Pipeline")


def build_promotions(
    findings: Sequence[Finding],
    evidence: Sequence[Evidence],
    *,
    agent_version: str | None,
    method: str,
) -> tuple[PromotionRecord, ...]:
    """Build promotion records from a run's findings.

    Args:
        findings: Findings produced by the synchronization validators.
        evidence: Evidence collected, used to attach supporting detail.
        agent_version: Product version observed against.
        method: How the observation was made.

    Returns:
        One record per finding, in a deterministic order.
    """
    endpoints: list[str] = []
    api_names: list[str] = []
    for item in evidence:
        if item.source == "synchronization:log" and "observed_endpoints" in item.data:
            endpoints = [str(value) for value in item.data.get("observed_endpoints", ())]
            api_names = sorted(
                {
                    str(call.get("api", ""))
                    for call in item.data.get("api_calls", ()) or ()
                    if call.get("api") and not str(call["api"]).startswith("http")
                }
            )

    records: list[PromotionRecord] = []
    for finding in findings:
        status, notes = _status_for(finding)
        records.append(
            PromotionRecord(
                claim=finding.what,
                status=status,
                target_document=_target_document(finding.where_component),
                evidence_ids=tuple(item.evidence_id for item in finding.evidence),
                collector=", ".join(
                    sorted({item.collector for item in finding.evidence if item.collector})
                ),
                agent_version=agent_version,
                verification_method=method,
                supporting={
                    "why": finding.why,
                    "verdict": finding.verdict.value,
                    "confidence": finding.confidence.name,
                    "observed_api_names": api_names,
                    "observed_endpoint_count": len(endpoints),
                },
                layers=tuple(layer.label for layer in finding.corroboration),
                notes=tuple(notes) + tuple(finding.notes),
            )
        )
    _LOGGER.info(
        "Built %d promotion record(s): %s",
        len(records),
        ", ".join(
            f"{status}={sum(1 for record in records if record.status == status)}"
            for status in (
                VerificationStatus.VERIFIED,
                VerificationStatus.PARTIALLY_VERIFIED,
                VerificationStatus.HYPOTHESIS,
            )
        ),
    )
    return tuple(sorted(records, key=lambda record: (record.target_document, record.claim)))
