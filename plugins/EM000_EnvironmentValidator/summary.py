"""Report summaries for the environment pre-check.

Turns collected evidence and findings into the report sections the sprint brief
requires: environment, installation, configuration, and runtime summaries, plus
warnings, failures, recommendations, and the overall verdict.

These are **projections of evidence, not new claims**. Every value shown here comes
from a recorded piece of evidence or a finding; nothing is inferred, and nothing is
smoothed over. Recommendations are derived from findings so a reader is never told to
fix something the run did not actually observe.
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

# Advice is keyed by the finding's full component so it names the actual problem.
# A coarser prefix key would, for example, blame the database for a folder whose
# name is simply unknown -- advice that sends a reader to investigate the wrong thing
# is worse than no advice.
_COMPONENT_ADVICE = {
    "installation": "Confirm EmpMonitor is installed and that config/framework.json "
    "names the correct installation root for this host.",
    "service": "Check the Windows service is installed and started, and review its "
    "recovery settings.",
    "process": "Start the agent, or investigate why its process exited.",
    "storage:database": "Verify the local database exists and is not locked by another "
    "tool; the agent may hold it open.",
    "storage:disk": "Free disk space on the volume holding the agent's data directory.",
    "storage:logs": "Verify the agent's log directory exists and is writable.",
    "network": "Restore outbound connectivity and DNS resolution before running "
    "synchronization coverage.",
    "system clock": "Correct the system clock; timestamp comparison against the server "
    "depends on it.",
    "framework configuration": "Populate the 'empmonitor' section of "
    "config/framework.json so the pre-check knows where to look.",
}
_CONFIGURATION_ADVICE = (
    "Review the agent configuration file; authentication and feature settings must be "
    "present before regression coverage is meaningful."
)


def _evidence_by_source(evidence: Sequence[Evidence]) -> dict[str, Evidence]:
    """Index evidence by its source.

    Args:
        evidence: Evidence to index.

    Returns:
        A mapping of source to the last evidence recorded for it.
    """
    return {item.source: item for item in evidence}


def _of_kind(evidence: Sequence[Evidence], prefix: str) -> tuple[Evidence, ...]:
    """Return evidence whose source starts with a prefix.

    Args:
        evidence: Evidence to filter.
        prefix: Source prefix.

    Returns:
        Matching evidence.
    """
    return tuple(item for item in evidence if item.source.startswith(prefix))


def _environment_summary(by_source: Mapping[str, Evidence]) -> dict[str, Any]:
    """Build the environment summary.

    Args:
        by_source: Evidence indexed by source.

    Returns:
        A serialisable summary of the host.
    """
    os_evidence = by_source.get("operating system")
    clock = by_source.get("system clock")
    network = by_source.get("network reachability")
    data = dict(os_evidence.data) if os_evidence else {}
    uptime = data.get("uptime_seconds")
    return {
        "windows_edition": data.get("edition"),
        "release": data.get("release"),
        "version": data.get("version"),
        "build": data.get("build"),
        "architecture": data.get("architecture"),
        "uptime_seconds": uptime,
        "uptime_hours": round(uptime / 3600, 2) if isinstance(uptime, (int, float)) else None,
        "time_zone": data.get("time_zone"),
        "current_user": data.get("current_user"),
        "host": data.get("node"),
        "clock_drift_seconds": (clock.data.get("drift_seconds") if clock else None),
        "clock_source": (clock.data.get("source") if clock else None),
        "dns_resolved": (network.data.get("dns_resolved") if network else None),
        "internet_available": (network.data.get("internet_available") if network else None),
    }


def _installation_summary(
    by_source: Mapping[str, Evidence], evidence: Sequence[Evidence]
) -> dict[str, Any]:
    """Build the installation summary.

    Args:
        by_source: Evidence indexed by source.
        evidence: All evidence, for executable enumeration.

    Returns:
        A serialisable summary of the installation.
    """
    root = by_source.get("installation root")
    executables = []
    for item in _of_kind(evidence, "executable:"):
        data = item.data
        version = data.get("version") or {}
        signature = data.get("signature") or {}
        executables.append(
            {
                "role": data.get("role"),
                "present": data.get("state") == "present",
                "name": data.get("name"),
                "path": data.get("path"),
                "size_bytes": data.get("size_bytes"),
                "modified_at": data.get("modified_at"),
                "sha256": data.get("sha256"),
                "file_version": version.get("file_version"),
                "product_version": version.get("product_version"),
                "build_part": version.get("file_build_part"),
                "company": version.get("company"),
                "signature_status": signature.get("status"),
                "signature_signer": signature.get("signer"),
                "required": data.get("required"),
            }
        )
    return {
        "install_root": (root.data.get("path") if root else None),
        "install_root_present": bool(root and root.data.get("state") == "present"),
        "searched_roots": list(root.data.get("searched", ())) if root else [],
        "executable_count": len(executables),
        "executables_present": sum(1 for item in executables if item["present"]),
        "executables": executables,
    }


def _configuration_summary(evidence: Sequence[Evidence]) -> dict[str, Any]:
    """Build the configuration summary.

    Values are never included -- only which keys are configured and whether they are
    populated. Credentials must not reach a report.

    Args:
        evidence: All evidence.

    Returns:
        A serialisable summary of configuration.
    """
    files = []
    for item in evidence:
        if item.layer is not EvidenceLayer.CONFIGURATION:
            continue
        data = item.data
        if not str(item.source).startswith("configuration:"):
            continue
        roles = data.get("roles") or {}
        files.append(
            {
                "role": data.get("role"),
                "present": data.get("state") == "present",
                "path": data.get("path"),
                "format": data.get("format"),
                "size_bytes": data.get("size_bytes"),
                "sections": list(data.get("sections", ()) or ()),
                "key_count": data.get("key_count"),
                "endpoints": list(data.get("endpoints", ()) or ()),
                "endpoint_schemes": list(data.get("schemes", ()) or ()),
                "redacted_keys": list(data.get("redacted_keys", ()) or ()),
                "authentication_configured": (roles.get("authentication_keys") or {}).get(
                    "non_empty"
                ),
                "upload_interval_configured": (roles.get("upload_interval_keys") or {}).get(
                    "present"
                ),
                "screenshot_settings_configured": (roles.get("screenshot_keys") or {}).get(
                    "present"
                ),
                "recording_settings_configured": (roles.get("recording_keys") or {}).get(
                    "present"
                ),
                "tracking_configured": (roles.get("tracking_keys") or {}).get("present"),
                "feature_flags_configured": (roles.get("feature_flag_keys") or {}).get(
                    "present"
                ),
            }
        )
    registry = [
        {
            "key": item.source,
            "found": item.data.get("found"),
            "required": item.data.get("required"),
        }
        for item in evidence
        if str(item.source).startswith("registry:")
    ]
    return {
        "files": files,
        "files_present": sum(1 for item in files if item["present"]),
        "registry_checked": len(registry),
        "registry": registry,
        "note": "Configuration values are not recorded; only key presence is reported.",
    }


def _runtime_summary(
    by_source: Mapping[str, Evidence], evidence: Sequence[Evidence]
) -> dict[str, Any]:
    """Build the runtime summary.

    Args:
        by_source: Evidence indexed by source.
        evidence: All evidence.

    Returns:
        A serialisable summary of runtime state.
    """
    services = [
        {
            "role": item.data.get("role"),
            "service_name": item.data.get("service_name"),
            "display_name": item.data.get("display_name"),
            "installed": item.data.get("found"),
            "state": item.data.get("reported_state"),
            "start_type": item.data.get("start_type"),
            "process_id": item.data.get("process_id"),
            "binary_path": item.data.get("binary_path"),
            "recovery_configured": bool(item.data.get("recovery")),
        }
        for item in _of_kind(evidence, "service:")
    ]
    processes = []
    for item in _of_kind(evidence, "process:"):
        for instance in item.data.get("instances", ()) or ():
            processes.append({"role": item.data.get("role"), **instance})
    database = by_source.get("local database")
    disk = by_source.get("disk space")
    folders = [
        {
            "role": item.data.get("role"),
            "present": item.data.get("state") == "present",
            "path": item.data.get("path"),
            "file_count": item.data.get("file_count"),
            "name_verified": item.data.get("verified_name"),
        }
        for item in _of_kind(evidence, "folder:")
    ]
    return {
        "services": services,
        "services_running": sum(1 for item in services if item["state"] == "RUNNING"),
        "processes": processes,
        "process_count": len(processes),
        "database": {
            "present": bool(database and database.data.get("state") == "present"),
            "path": database.data.get("path") if database else None,
            "readable": database.data.get("readable") if database else None,
            "table_count": database.data.get("table_count") if database else None,
            "populated_table_count": (
                database.data.get("populated_table_count") if database else None
            ),
        },
        "folders": folders,
        "free_disk_mb": disk.data.get("free_mb") if disk else None,
    }


def _recommendations(findings: Sequence[Finding]) -> list[str]:
    """Derive recommendations from findings.

    Args:
        findings: The run's findings.

    Returns:
        Distinct recommendations, in a stable order. Empty when nothing needs
        attention -- a run with nothing wrong should not manufacture advice.
    """
    advice: list[str] = []
    for finding in findings:
        if finding.verdict is Verdict.HEALTHY:
            continue
        component = finding.where_component
        # An unverified-name finding is a knowledge gap, not a component fault; the
        # consolidated note below covers it, so component advice would misdirect.
        if any("unverified" in note for note in finding.notes):
            continue
        text = _COMPONENT_ADVICE.get(component)
        if text is None and finding.where_layer is EvidenceLayer.CONFIGURATION:
            text = _CONFIGURATION_ADVICE
        if text is None:
            text = _COMPONENT_ADVICE.get(component.split(":", 1)[0])
        if text and text not in advice:
            advice.append(text)
    inconclusive = [
        finding
        for finding in findings
        if finding.verdict is Verdict.INCONCLUSIVE
        and any("unverified" in note for note in finding.notes)
    ]
    if inconclusive:
        advice.append(
            f"{len(inconclusive)} check(s) were inconclusive because the expected name or "
            "location is unverified. Supply the confirmed names in "
            "config/framework.json 'empmonitor' and set verified:true so absence becomes "
            "a real failure rather than an open question."
        )
    return advice


def build_summary(
    evidence: Sequence[Evidence],
    findings: Sequence[Finding],
    *,
    verdict: Verdict,
    confidence: Confidence,
) -> dict[str, Any]:
    """Build the complete environment pre-check summary.

    Args:
        evidence: Evidence collected during the run.
        findings: Findings produced.
        verdict: The aggregate verdict.
        confidence: The aggregate confidence.

    Returns:
        A serialisable summary carrying every section the brief requires.
    """
    by_source = _evidence_by_source(evidence)
    failures = [
        {
            "what": finding.what,
            "where": f"{finding.where_layer.label}/{finding.where_component}",
            "why": finding.why,
            "verdict": finding.verdict.value,
            "confidence": finding.confidence.name,
            "failure_class": (
                finding.failure_class.value if finding.failure_class else None
            ),
            "evidence": [item.evidence_id for item in finding.evidence],
        }
        for finding in findings
        if finding.verdict in (Verdict.FAILED, Verdict.BLOCKED)
    ]
    warnings = [
        {
            "what": finding.what,
            "where": f"{finding.where_layer.label}/{finding.where_component}",
            "why": finding.why,
            "verdict": finding.verdict.value,
            "confidence": finding.confidence.name,
            "notes": list(finding.notes),
        }
        for finding in findings
        if finding.verdict in (Verdict.DEGRADED, Verdict.INCONCLUSIVE)
    ]
    healthy = sum(1 for finding in findings if finding.verdict is Verdict.HEALTHY)
    return {
        "question": "Is this Windows machine correctly prepared to execute EmpMonitor "
        "regression testing?",
        "answer": _answer(verdict, healthy=healthy, failures=len(failures), open_questions=len(warnings)),
        "overall_verdict": verdict.value,
        "confidence": confidence.name,
        "environment": _environment_summary(by_source),
        "installation": _installation_summary(by_source, evidence),
        "configuration": _configuration_summary(evidence),
        "runtime": _runtime_summary(by_source, evidence),
        "failures": failures,
        "warnings": warnings,
        "recommendations": _recommendations(findings),
        "counts": {
            "evidence": len(evidence),
            "findings": len(findings),
            "failures": len(failures),
            "warnings": len(warnings),
            "layers_covered": sorted(
                {item.layer.label for item in evidence}
            ),
        },
    }


def _answer(
    verdict: Verdict, *, healthy: int = 0, failures: int = 0, open_questions: int = 0
) -> str:
    """Render the plain-language answer to the plugin's question.

    ``INCONCLUSIVE`` is never rendered as a yes -- an unanswered question is not a
    pass. But it is qualified with what *was* established, because "cannot tell" on
    its own is true and useless: a reader needs to know whether nothing could be
    checked or whether almost everything passed and two questions remain open.

    Args:
        verdict: The aggregate verdict.
        healthy: Count of healthy findings.
        failures: Count of failed or blocked findings.
        open_questions: Count of degraded or inconclusive findings.

    Returns:
        A sentence a human can act on.
    """
    base = {
        Verdict.HEALTHY: "Yes -- the environment is prepared.",
        Verdict.DEGRADED: "Yes, with reservations -- the environment works but has anomalies.",
        Verdict.FAILED: "No -- the environment is not correctly prepared.",
        Verdict.BLOCKED: "Cannot tell -- a precondition prevented validation from running.",
        Verdict.INCONCLUSIVE: "Cannot tell -- the evidence was insufficient to conclude.",
    }[verdict]
    if verdict is Verdict.INCONCLUSIVE and (healthy or open_questions):
        return (
            f"{base} {healthy} check(s) passed and {failures} failed, but "
            f"{open_questions} question(s) could not be answered, so the environment "
            "is not certified as prepared."
        )
    return base
