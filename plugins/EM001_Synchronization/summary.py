"""Report summaries for the synchronization validator.

Projects evidence and findings into the sections the sprint brief requires:
synchronization, scheduler, authentication, queue, retry, recovery, and latency
health; observed APIs and WebSocket configuration; the observed upload cycle; the
evidence timeline and graph; and per-layer plus overall verdicts.

Every value is a projection of recorded evidence. Where a health area could not be
observed, it is reported as ``not observed`` with the reason -- never as healthy by
omission, which would be the single easiest way for this report to mislead.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from framework.shared.models import (
    Confidence,
    Evidence,
    EvidenceLayer,
    Finding,
    Verdict,
)

__all__ = ["build_summary"]

#: Health areas, mapped to the finding component that reports on each.
_HEALTH_AREAS = (
    ("synchronization", "synchronization:pipeline"),
    ("scheduler", "synchronization:scheduler"),
    ("authentication", "synchronization:authentication"),
    ("queue", "synchronization:queue"),
    ("retry", "synchronization:retry"),
    ("recovery", "synchronization:recovery"),
    ("latency", "synchronization:latency"),
    ("upload", "synchronization:upload"),
)


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


def _health(findings: Sequence[Finding], component: str) -> dict[str, Any]:
    """Summarise one health area from its findings.

    Args:
        findings: All findings.
        component: The component that reports on this area.

    Returns:
        A serialisable health record. An area with no findings is reported as not
        observed, with an explicit note that this is not a pass.
    """
    relevant = [finding for finding in findings if finding.where_component == component]
    if not relevant:
        return {
            "verdict": "NOT_OBSERVED",
            "confidence": Confidence.UNKNOWN.name,
            "finding_count": 0,
            "note": "No validator reported on this area; absence of a finding is not a pass.",
        }
    verdict = Verdict.aggregate(finding.verdict for finding in relevant)
    return {
        "verdict": verdict.value,
        "confidence": min(finding.confidence for finding in relevant).name,
        "finding_count": len(relevant),
        "findings": [
            {
                "what": finding.what,
                "why": finding.why,
                "verdict": finding.verdict.value,
                "confidence": finding.confidence.name,
                "layers": [layer.label for layer in finding.corroboration],
                "evidence": [item.evidence_id for item in finding.evidence],
                "notes": list(finding.notes),
            }
            for finding in relevant
        ],
    }


def _layer_verdicts(
    findings: Sequence[Finding], evidence: Sequence[Evidence] = ()
) -> dict[str, Any]:
    """Compute a verdict per evidence layer.

    A layer's verdict aggregates every finding that **drew on** that layer, not only
    findings localized to it. Grouping by localization alone would report L1 and L2
    as unobserved on a synchronization run whose conclusions rest on exactly that
    corroboration -- true of the localization, but plainly misleading about coverage.

    ``localized_here`` is reported separately, because *which layer a fault sits in*
    and *which layers supported the conclusion* are different questions and the brief
    asks about both.

    Args:
        findings: All findings.
        evidence: All evidence, used to distinguish "no evidence collected at this
            layer" from "evidence collected but no finding drew on it".

    Returns:
        A mapping of layer label to verdict detail, covering every layer.
    """
    layers_with_evidence = {item.layer for item in evidence}
    result: dict[str, Any] = {}
    for layer in EvidenceLayer:
        contributing = [
            finding for finding in findings if layer in finding.corroboration
        ]
        localized = [finding for finding in findings if finding.where_layer is layer]
        if not contributing:
            result[layer.label] = {
                "verdict": "NOT_OBSERVED",
                "finding_count": 0,
                "localized_here": len(localized),
                "evidence_collected": layer in layers_with_evidence,
                "note": (
                    "Evidence was collected at this layer but no finding drew on it."
                    if layer in layers_with_evidence
                    else "No evidence was collected at this layer in this run."
                ),
            }
            continue
        result[layer.label] = {
            "verdict": Verdict.aggregate(finding.verdict for finding in contributing).value,
            "confidence": min(finding.confidence for finding in contributing).name,
            "finding_count": len(contributing),
            "localized_here": len(localized),
            "evidence_collected": layer in layers_with_evidence,
        }
    return result


def _observed_apis(evidence: Sequence[Evidence]) -> dict[str, Any]:
    """Summarise the API surface actually exercised.

    Args:
        evidence: All collected evidence.

    Returns:
        A serialisable record of observed endpoints, named APIs, and reply codes.
    """
    summary = _log_summary(evidence)
    if summary is None:
        return {"observed": False, "note": "no log evidence was collected"}
    calls = summary.data.get("api_calls") or []
    named = sorted(
        {
            str(call.get("api"))
            for call in calls
            if call.get("api") and not str(call["api"]).startswith("http")
        }
    )
    codes: dict[str, int] = {}
    for call in calls:
        code = str(call.get("code") or "unknown")
        codes[code] = codes.get(code, 0) + 1
    return {
        "observed": bool(calls),
        "endpoint_count": len(summary.data.get("observed_endpoints") or []),
        "endpoints": list(summary.data.get("observed_endpoints") or []),
        "named_apis": named,
        "call_count": len(calls),
        "reply_codes": codes,
        "note": (
            "Endpoints are recorded as observed, not as an approved contract. Request "
            "and response bodies are not observable and were not captured."
        ),
    }


def _observed_websockets(evidence: Sequence[Evidence]) -> dict[str, Any]:
    """Summarise WebSocket evidence.

    Args:
        evidence: All collected evidence.

    Returns:
        A serialisable record. WebSocket *use* is reported as unverified: a
        configured ``wss`` endpoint evidences a channel, not traffic on it.
    """
    configured: list[str] = []
    for item in evidence:
        if item.layer is EvidenceLayer.CONFIGURATION:
            configured.extend(
                str(url)
                for url in item.data.get("endpoints", ()) or ()
                if str(url).lower().startswith(("ws://", "wss://"))
            )
    summary = _log_summary(evidence)
    log_endpoints = [
        url
        for url in ((summary.data.get("observed_endpoints") if summary else ()) or ())
        if str(url).lower().startswith(("ws://", "wss://"))
    ]
    return {
        "configured_channel_count": len(set(configured)),
        "configured_schemes": sorted({url.split("://", 1)[0] for url in configured}),
        "observed_in_logs": len(log_endpoints),
        "status": (
            "configured, use not verified"
            if configured and not log_endpoints
            else "observed"
            if log_endpoints
            else "not configured"
        ),
        "note": (
            "A configured wss endpoint establishes that a WebSocket channel exists. "
            "Frames are not observable passively, so its use remains unverified."
        ),
    }


def _upload_cycle(evidence: Sequence[Evidence]) -> dict[str, Any]:
    """Summarise the observed upload cycle.

    Args:
        evidence: All collected evidence.

    Returns:
        A serialisable record of cycle timing and configured interval.
    """
    summary = _log_summary(evidence)
    if summary is None:
        return {"observed": False}
    intervals = [float(value) for value in summary.data.get("observed_intervals_seconds", ())]
    return {
        "observed": bool(summary.data.get("cycle_count")),
        "cycle_count": summary.data.get("cycle_count"),
        "cycle_timestamps": list(summary.data.get("cycle_timestamps") or []),
        "observed_intervals_seconds": intervals,
        "mean_interval_seconds": (
            round(sum(intervals) / len(intervals), 2) if intervals else None
        ),
        "interval_spread_seconds": (
            round(max(intervals) - min(intervals), 3) if intervals else None
        ),
        "events_by_pattern": dict(summary.data.get("events_by_pattern") or {}),
    }


def _queue_health(evidence: Sequence[Evidence]) -> dict[str, Any]:
    """Summarise observed queue state.

    Args:
        evidence: All collected evidence.

    Returns:
        A serialisable record of queue depth per discovered table.
    """
    queue = _by_source(evidence, "synchronization:queue")
    if queue is None:
        return {"observed": False}
    return {
        "observed": queue.data.get("state") == "observed",
        "discovered_tables": list(queue.data.get("discovered_pending_tables") or []),
        "depths": dict(queue.data.get("pending_depths") or {}),
        "total_depth": queue.data.get("total_queue_depth"),
        "non_empty": dict(queue.data.get("non_empty_queues") or {}),
        "shares_artifact_with": queue.data.get("shares_artifact_with"),
    }


def _network(evidence: Sequence[Evidence]) -> dict[str, Any]:
    """Summarise observed connection state.

    Args:
        evidence: All collected evidence.

    Returns:
        A serialisable record of the agent's connections.
    """
    network = _by_source(evidence, "synchronization:network")
    if network is None:
        return {"observed": False}
    established = network.data.get("established_server_connections") or []
    return {
        "observed": network.data.get("state") == "observed",
        "established_server_connections": len(established),
        "processes_with_server_connection": list(
            network.data.get("processes_with_server_connection") or []
        ),
        "listening_endpoint_count": len(network.data.get("listening_endpoints") or []),
        "loopback_connection_count": len(network.data.get("loopback_connections") or []),
        "payload_observable": network.data.get("payload_observable"),
        "payload_note": network.data.get("payload_note"),
    }


def build_summary(
    evidence: Sequence[Evidence],
    findings: Sequence[Finding],
    *,
    timeline: Sequence[Any],
    graph: Mapping[str, Any],
    promotions: Sequence[Any],
    verdict: Verdict,
    confidence: Confidence,
    agent_version: str | None,
) -> dict[str, Any]:
    """Build the synchronization report summary.

    Args:
        evidence: Evidence collected.
        findings: Findings produced.
        timeline: Reconstructed lifecycle stages.
        graph: The evidence graph.
        promotions: Proposed knowledge promotions.
        verdict: Aggregate verdict.
        confidence: Aggregate confidence.
        agent_version: Product version observed against.

    Returns:
        A serialisable summary carrying every section the brief requires.
    """
    observed_stages = [stage for stage in timeline if getattr(stage, "observed", False)]
    gaps = [
        {"stage": stage.key, "label": stage.label, "reason": stage.gap_reason}
        for stage in timeline
        if not getattr(stage, "observed", False)
    ]
    promotion_counts: dict[str, int] = {}
    for record in promotions:
        promotion_counts[record.status] = promotion_counts.get(record.status, 0) + 1

    return {
        "questions_answered": {
            "how_synchronization_works": (
                f"{len(observed_stages)} of {len(timeline)} lifecycle stages were observed; "
                "see synchronization_timeline"
            ),
            "where_it_failed": [
                f"{finding.where_layer.label}/{finding.where_component}: {finding.what}"
                for finding in findings
                if finding.verdict in (Verdict.FAILED, Verdict.BLOCKED)
            ]
            or "no failure was observed",
            "which_layer_failed": [
                layer
                for layer, detail in _layer_verdicts(findings, evidence).items()
                if detail.get("verdict") in ("FAILED", "BLOCKED")
            ]
            or "none",
            "failure_classification": sorted(
                {
                    finding.failure_class.value
                    for finding in findings
                    if finding.failure_class is not None
                }
            )
            or "none",
        },
        "overall_verdict": verdict.value,
        "confidence": confidence.name,
        "agent_version_observed": agent_version,
        "health": {name: _health(findings, component) for name, component in _HEALTH_AREAS},
        "layer_verdicts": _layer_verdicts(findings, evidence),
        "observed_apis": _observed_apis(evidence),
        "observed_websockets": _observed_websockets(evidence),
        "observed_upload_cycle": _upload_cycle(evidence),
        "queue": _queue_health(evidence),
        "network": _network(evidence),
        "synchronization_timeline": [stage.to_dict() for stage in timeline],
        "timeline_gaps": gaps,
        "evidence_graph": dict(graph),
        "knowledge_promotions": {
            "counts": promotion_counts,
            "records": [record.to_dict() for record in promotions],
            "note": (
                "Promotions are proposed, not applied: the verification workflow "
                "requires a reviewer other than the author to confirm each one."
            ),
        },
        "counts": {
            "evidence": len(evidence),
            "findings": len(findings),
            "stages_observed": len(observed_stages),
            "stages_total": len(timeline),
            "layers_covered": sorted({item.layer.label for item in evidence}),
        },
    }
