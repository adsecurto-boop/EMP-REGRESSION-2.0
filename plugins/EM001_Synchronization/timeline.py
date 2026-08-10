"""Synchronization timeline and evidence graph.

Reconstructs the synchronization lifecycle as an ordered sequence of stages, each
one **referencing the evidence that establishes it**. A stage with no supporting
evidence is not omitted -- it is included and marked unobserved, because the gaps in
a reconstructed pipeline are as informative as the parts that were seen.

The evidence graph records which artifact supported which stage, so a reader can
see at a glance whether a conclusion rests on one source or several, and whether
two apparently independent supports actually share an artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from framework.shared.models import Evidence, EvidenceLayer, Finding, Verdict

__all__ = ["TimelineStage", "build_timeline", "build_evidence_graph"]

#: The synchronization lifecycle, in order, with the layer that can evidence each
#: stage and the configured log-pattern names that would demonstrate it. Stages are
#: declared up front so that an unobserved stage is reported as a gap rather than
#: silently missing from the timeline.
_STAGES: tuple[tuple[str, str, EvidenceLayer, tuple[str, ...]], ...] = (
    ("system_boot", "Host started", EvidenceLayer.RUNTIME, ()),
    ("service_started", "Browser Handling Service running", EvidenceLayer.RUNTIME, ()),
    ("agent_launched", "Agent process running", EvidenceLayer.RUNTIME, ()),
    ("configuration_loaded", "Configuration read", EvidenceLayer.CONFIGURATION, ("config_refresh",)),
    ("authentication", "Authentication performed", EvidenceLayer.SYNCHRONIZATION,
     ("auth_register", "auth_call")),
    ("scheduler_started", "Upload scheduler running on its interval",
     EvidenceLayer.SYNCHRONIZATION, ("upload_cycle_trigger",)),
    ("activity_collected", "Activity captured and queued", EvidenceLayer.SYNCHRONIZATION,
     ("session_enqueued",)),
    ("queue_persisted", "Queue persisted locally", EvidenceLayer.SYNCHRONIZATION, ()),
    ("upload_triggered", "Upload cycle triggered", EvidenceLayer.SYNCHRONIZATION,
     ("upload_cycle_trigger",)),
    ("request_issued", "Request issued to server", EvidenceLayer.SYNCHRONIZATION,
     ("request_dump",)),
    ("server_response", "Server accepted the data", EvidenceLayer.SYNCHRONIZATION,
     ("api_reply", "api_url_reply", "upload_succeeded")),
    ("queue_cleanup", "Queue retention sweep ran", EvidenceLayer.SYNCHRONIZATION,
     ("queue_cleanup", "queue_cleanup_result")),
    ("retry", "Retry after failure", EvidenceLayer.SYNCHRONIZATION, ("retry",)),
    ("offline_queue", "Offline queueing", EvidenceLayer.SYNCHRONIZATION, ()),
    ("recovery", "Reconnect and drain", EvidenceLayer.SYNCHRONIZATION, ()),
    ("dashboard_visibility", "Result visible on the dashboard", EvidenceLayer.DASHBOARD, ()),
)


@dataclass(frozen=True, slots=True)
class TimelineStage:
    """One stage of the reconstructed synchronization lifecycle.

    Args:
        key: Stable stage identifier.
        label: Human-readable stage name.
        layer: The evidence layer that can establish this stage.
        observed: Whether evidence for it was found.
        occurrences: How many times it was observed.
        first_seen: Earliest observation timestamp.
        last_seen: Latest observation timestamp.
        evidence_ids: Evidence Catalog identifiers supporting it.
        detail: Additional observed detail.
        gap_reason: Why the stage was not observed, when it was not.
    """

    key: str
    label: str
    layer: EvidenceLayer
    observed: bool = False
    occurrences: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    evidence_ids: Sequence[str] = field(default_factory=tuple)
    detail: Mapping[str, Any] = field(default_factory=dict)
    gap_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-native representation.

        Returns:
            A serialisable mapping.
        """
        return {
            "stage": self.key,
            "label": self.label,
            "layer": self.layer.label,
            "observed": self.observed,
            "occurrences": self.occurrences,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "evidence": list(self.evidence_ids),
            "detail": dict(self.detail),
            "gap_reason": self.gap_reason,
        }


def _log_summary(evidence: Sequence[Evidence]) -> Evidence | None:
    """Return the log collector's summary evidence.

    Args:
        evidence: All collected evidence.

    Returns:
        The summary evidence, or ``None``.
    """
    for item in evidence:
        if item.source == "synchronization:log" and "event_count" in item.data:
            return item
    return None


def _by_source(evidence: Sequence[Evidence], source: str) -> Evidence | None:
    """Return the last evidence for a source.

    Args:
        evidence: All collected evidence.
        source: Source name.

    Returns:
        The evidence, or ``None``.
    """
    matches = [item for item in evidence if item.source == source]
    return matches[-1] if matches else None


def _runtime_stage(
    evidence: Sequence[Evidence], key: str, label: str, prefix: str
) -> TimelineStage:
    """Build a Layer 2 stage from runtime evidence.

    Args:
        evidence: All collected evidence.
        key: Stage identifier.
        label: Stage label.
        prefix: Evidence source prefix identifying the runtime observation.

    Returns:
        The stage.
    """
    matches = [
        item
        for item in evidence
        if item.source.startswith(prefix) and item.data.get("state") in ("running", "RUNNING")
    ]
    if not matches:
        return TimelineStage(
            key=key,
            label=label,
            layer=EvidenceLayer.RUNTIME,
            gap_reason=f"no {prefix} evidence showed a running state in this run",
        )
    return TimelineStage(
        key=key,
        label=label,
        layer=EvidenceLayer.RUNTIME,
        observed=True,
        occurrences=len(matches),
        evidence_ids=tuple({item.evidence_id for item in matches}),
        detail={"sources": [item.source for item in matches]},
    )


def build_timeline(
    evidence: Sequence[Evidence], findings: Sequence[Finding]
) -> tuple[TimelineStage, ...]:
    """Reconstruct the synchronization lifecycle from evidence.

    Args:
        evidence: Evidence collected during the run.
        findings: Findings produced, used to attach gap reasons for stages a
            validator explicitly could not settle.

    Returns:
        Every declared stage, in lifecycle order, each marked observed or with the
        reason it was not.
    """
    summary = _log_summary(evidence)
    events = list(summary.data.get("events", ()) or ()) if summary else []
    by_pattern: dict[str, list[Mapping[str, Any]]] = {}
    for event in events:
        by_pattern.setdefault(str(event.get("pattern")), []).append(event)

    inconclusive_by_component = {
        finding.where_component.split(":", 1)[-1]: finding.why
        for finding in findings
        if finding.verdict is Verdict.INCONCLUSIVE
    }

    stages: list[TimelineStage] = []
    for key, label, layer, patterns in _STAGES:
        if key == "service_started":
            stages.append(_runtime_stage(evidence, key, label, "service:"))
            continue
        if key == "agent_launched":
            stages.append(_runtime_stage(evidence, key, label, "process:"))
            continue
        if key == "system_boot":
            os_evidence = _by_source(evidence, "operating system")
            uptime = (os_evidence.data.get("uptime_seconds") if os_evidence else None)
            stages.append(
                TimelineStage(
                    key=key,
                    label=label,
                    layer=layer,
                    observed=uptime is not None,
                    evidence_ids=(os_evidence.evidence_id,) if os_evidence else (),
                    detail={"uptime_seconds": uptime},
                    gap_reason=None if uptime is not None else "host uptime was not measured",
                )
            )
            continue
        if key == "queue_persisted":
            queue = _by_source(evidence, "synchronization:queue")
            observed = bool(queue and queue.data.get("state") == "observed")
            stages.append(
                TimelineStage(
                    key=key,
                    label=label,
                    layer=layer,
                    observed=observed,
                    evidence_ids=(queue.evidence_id,) if queue else (),
                    detail={
                        "queue_tables": (queue.data.get("discovered_pending_tables") if queue else []),
                        "depth": (queue.data.get("total_queue_depth") if queue else None),
                    },
                    gap_reason=None if observed else "queue state was not observable",
                )
            )
            continue
        if key == "dashboard_visibility":
            stages.append(
                TimelineStage(
                    key=key,
                    label=label,
                    layer=layer,
                    observed=False,
                    gap_reason=(
                        "Layer 4 is out of scope for this plugin: no dashboard collector "
                        "is implemented, and asserting visibility without one would be "
                        "inventing behaviour"
                    ),
                )
            )
            continue

        matched = [event for pattern in patterns for event in by_pattern.get(pattern, ())]
        timestamps = sorted(
            str(event.get("timestamp")) for event in matched if event.get("timestamp")
        )
        gap: str | None = None
        if not matched:
            gap = inconclusive_by_component.get(key) or (
                "no configured pattern for this stage matched in the observation window"
            )
        stages.append(
            TimelineStage(
                key=key,
                label=label,
                layer=layer,
                observed=bool(matched),
                occurrences=len(matched),
                first_seen=timestamps[0] if timestamps else None,
                last_seen=timestamps[-1] if timestamps else None,
                evidence_ids=(summary.evidence_id,) if summary and matched else (),
                detail={"patterns_matched": sorted({str(e.get("pattern")) for e in matched})},
                gap_reason=gap,
            )
        )
    return tuple(stages)


def build_evidence_graph(
    evidence: Sequence[Evidence], findings: Sequence[Finding]
) -> dict[str, Any]:
    """Build the evidence graph linking artifacts to conclusions.

    Args:
        evidence: Evidence collected.
        findings: Findings produced.

    Returns:
        A serialisable graph of sources, layers, findings, and the edges between
        them, plus a note of any shared artifact that must not be treated as
        independent corroboration.
    """
    nodes = [
        {
            "id": item.evidence_id,
            "source": item.source,
            "layer": item.layer.label,
            "collector": item.collector,
            "reliability": item.reliability.name,
            "shares_artifact_with": item.data.get("shares_artifact_with"),
        }
        for item in evidence
    ]
    edges = [
        {
            "finding": finding.what[:120],
            "verdict": finding.verdict.value,
            "confidence": finding.confidence.name,
            "supported_by": sorted({item.evidence_id for item in finding.evidence}),
            "layers": [layer.label for layer in finding.corroboration],
        }
        for finding in findings
    ]
    shared = [node for node in nodes if node.get("shares_artifact_with")]
    return {
        "sources": nodes,
        "conclusions": edges,
        "layers_present": sorted({item.layer.label for item in evidence}),
        "shared_artifacts": shared,
        "shared_artifact_note": (
            "Sources listed in shared_artifacts read the same underlying artifact as "
            "another source. Per Validation Standard 4.1 they do not independently "
            "corroborate each other, however different their identifiers."
        )
        if shared
        else None,
    }
