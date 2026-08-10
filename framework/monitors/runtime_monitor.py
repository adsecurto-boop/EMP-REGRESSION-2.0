"""Windows service and process collection (EV-005, EV-011).

Observes the product's runtime footprint: whether its services are installed and
running, and whether its processes are alive and consuming resources normally.

Two distinct evidence sources live here because they answer different questions.
EV-005 asks "does the service exist and run"; EV-011 asks "does the process consume
resources normally". They share an underlying subject, so per the independence rule
(``docs/ADS/validation_standard.md`` §4.1) two readings of the same process do not
corroborate each other merely because they carry different identifiers.

Passive throughout: nothing here starts, stops, or reconfigures anything. An
anomaly is reported, never corrected (``docs/ADS/error_handling_standard.md`` §5).
"""

from __future__ import annotations

from typing import Any, Sequence

from framework.shared.interfaces import Collector
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    SourceReliability,
    ValidationContext,
)
from framework.shared.profile import Expectation, ProductProfile
from framework.shared.utils import windows

__all__ = ["ServiceCollector", "ProcessCollector", "EV_SERVICE", "EV_RESOURCE"]

_LOGGER = get_logger(__name__)

EV_SERVICE = "EV-005"
EV_RESOURCE = "EV-011"


class ServiceCollector(Collector):
    """Collects Windows service state for each expected service."""

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile naming the expected services.
        """
        self._profile = profile

    @property
    def name(self) -> str:
        """Component name."""
        return "service.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.RUNTIME

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_SERVICE,)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect service state.

        Args:
            context: Run context.

        Returns:
            One piece of evidence per expected service, including any not found.
        """
        timeout = float(self._profile.collection_setting("command_timeout_seconds", 20))
        return tuple(
            self._collect_one(expectation, timeout=timeout)
            for expectation in self._profile.services()
        )

    def _collect_one(self, expectation: Expectation, *, timeout: float) -> Evidence:
        """Query one expected service.

        Args:
            expectation: The service expectation.
            timeout: Seconds to allow per command.

        Returns:
            Evidence describing the service.
        """
        display = str(expectation.extra.get("display_name") or "")
        # Try the short name first, then the display name: sc.exe accepts only the
        # short name, and a profile may legitimately record either.
        names = [name for name in (*expectation.names, display) if name]
        info = None
        for candidate in names:
            info = windows.query_service(candidate, timeout=timeout)
            if info.found:
                break
        if info is None:
            info = windows.ServiceInfo(name=expectation.role)

        expected_state = str(expectation.extra.get("expected_state") or "RUNNING").upper()
        data: dict[str, Any] = {
            "state": (info.state or "absent").upper() if info.found else "absent",
            "role": expectation.role,
            "queried_names": names,
            "found": info.found,
            "service_name": info.name if info.found else None,
            "display_name": info.display_name,
            "reported_state": info.state,
            "start_type": info.start_type,
            "binary_path": info.binary_path,
            "process_id": info.process_id,
            "recovery": dict(info.recovery),
            "is_running": info.is_running,
            "expected_state": expected_state,
            "required": expectation.required,
            "verified_name": expectation.verified,
            "raw": info.raw[:2000],
        }
        summary = (
            f"service {info.name} is {info.state or 'in an unreported state'}"
            f" (start type {info.start_type or 'unknown'})"
            if info.found
            else f"service {' / '.join(names) or expectation.role} not installed"
        )
        return Evidence(
            evidence_id=EV_SERVICE,
            layer=EvidenceLayer.RUNTIME,
            source=f"service:{expectation.role}",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data=data,
        )


class ProcessCollector(Collector):
    """Collects process presence and resource usage for expected processes."""

    def __init__(self, profile: ProductProfile) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile naming the expected processes.
        """
        self._profile = profile

    @property
    def name(self) -> str:
        """Component name."""
        return "process.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.RUNTIME

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_RESOURCE,)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect process evidence.

        Args:
            context: Run context.

        Returns:
            One piece of evidence per expected process. The host process list is
            read once and shared, so every expectation is evaluated against the
            same snapshot rather than against a drifting sequence of snapshots.
        """
        observed = windows.list_processes(
            timeout=float(self._profile.collection_setting("command_timeout_seconds", 20))
        )
        return tuple(
            self._collect_one(expectation, observed)
            for expectation in self._profile.processes()
        )

    def _collect_one(
        self, expectation: Expectation, observed: Sequence[windows.ProcessInfo]
    ) -> Evidence:
        """Evaluate one process expectation against an observed snapshot.

        Args:
            expectation: The process expectation.
            observed: The shared process snapshot.

        Returns:
            Evidence describing the matching processes, or their absence.
        """
        grouped = windows.find_processes(expectation.names, processes=observed)
        matches = [item for group in grouped.values() for item in group]
        instances = [
            {
                "name": item.name,
                "pid": item.pid,
                "memory_bytes": item.memory_bytes,
                "cpu_seconds": item.cpu_seconds,
                "thread_count": item.thread_count,
                "handle_count": item.handle_count,
                "start_time": item.start_time.isoformat() if item.start_time else None,
                "parent_pid": item.parent_pid,
                "executable_path": item.executable_path,
            }
            for item in matches
        ]
        data: dict[str, Any] = {
            "state": "running" if matches else "not running",
            "role": expectation.role,
            "candidates": list(expectation.names),
            "required": expectation.required,
            "verified_name": expectation.verified,
            "note": expectation.note,
            "instance_count": len(matches),
            "instances": instances,
            "total_memory_bytes": sum(
                item.memory_bytes or 0 for item in matches
            ) or None,
            "host_process_count": len(observed),
        }
        summary = (
            f"{expectation.display_names} running "
            f"({len(matches)} instance(s), pid {', '.join(str(item.pid) for item in matches)})"
            if matches
            else f"{expectation.display_names} not running"
            + (" (host process list unavailable)" if not observed else "")
        )
        return Evidence(
            evidence_id=EV_RESOURCE,
            layer=EvidenceLayer.RUNTIME,
            source=f"process:{expectation.role}",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.MEDIUM,
            data=data,
        )
