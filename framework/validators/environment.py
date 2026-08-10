"""Host environment collection and validation.

Answers "is this machine itself fit to run a validation?" -- operating system
identity, outbound network reachability, and clock correctness. These are host
facts, not EmpMonitor facts, so nothing here depends on the product profile beyond
probe settings and thresholds.

**Layer assignment.** All three sources are Layer 2 (Runtime). Network reachability
in particular is *not* Layer 3: L3 means "is the result reaching the EmpMonitor
server", whereas this establishes only that the host has outbound access at all. A
generic TCP connect says nothing about EmpMonitor synchronization, and filing it as
L3 would let a host-level check masquerade as sync corroboration.

An unmet environment prerequisite produces a ``BLOCKED`` finding rather than
``FAILED``: if the machine is unfit, the validation did not run, and nothing may be
concluded about the product (``docs/ADS/validation_standard.md`` §6).
"""

from __future__ import annotations

from typing import Sequence

from framework.shared.interfaces import Collector, Validator
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    Finding,
    SourceReliability,
    ValidationContext,
    Verdict,
)
from framework.shared.profile import ProductProfile
from framework.shared.utils import windows

__all__ = ["EnvironmentCollector", "EnvironmentValidator", "EV_OS", "EV_NETWORK", "EV_CLOCK"]

_LOGGER = get_logger(__name__)

EV_OS = "EV-012"
EV_NETWORK = "EV-014"
EV_CLOCK = "EV-015"


class EnvironmentCollector(Collector):
    """Collects host operating system, network, and clock evidence."""

    def __init__(self, profile: ProductProfile | None = None) -> None:
        """Initialise the collector.

        Args:
            profile: Product profile, consulted only for network probe settings.
        """
        self._profile = profile or ProductProfile({})

    @property
    def name(self) -> str:
        """Component name."""
        return "environment.collector"

    @property
    def layer(self) -> EvidenceLayer:
        """The evidence layer this collector serves."""
        return EvidenceLayer.RUNTIME

    @property
    def evidence_ids(self) -> Sequence[str]:
        """Evidence Catalog identifiers this collector produces."""
        return (EV_OS, EV_NETWORK, EV_CLOCK)

    def collect(self, context: ValidationContext) -> Sequence[Evidence]:
        """Collect host environment evidence.

        Args:
            context: Run context.

        Returns:
            One piece of evidence per source. Each is emitted even when the
            underlying measurement failed, carrying the failure in its data --
            "could not measure" is an observation a validator needs to see, and is
            not the same as a measurement of absence.
        """
        collected: list[Evidence] = [self._collect_os()]
        if self._profile.network_setting("check_internet", True):
            collected.append(self._collect_network())
        collected.append(self._collect_clock())
        return tuple(collected)

    def _collect_os(self) -> Evidence:
        """Collect operating system identity.

        Returns:
            Evidence describing the host OS.
        """
        info = windows.os_information()
        data = {
            **info,
            "uptime_seconds": windows.uptime_seconds(),
            "time_zone": windows.time_zone_name(),
            "current_user": windows.current_user(),
            "state": "windows" if windows.is_windows() else str(info.get("system", "unknown")),
        }
        summary = (
            f"{info.get('system')} {info.get('release')} "
            f"build {info.get('build') or 'unknown'} ({info.get('architecture')})"
        )
        return Evidence(
            evidence_id=EV_OS,
            layer=EvidenceLayer.RUNTIME,
            source="operating system",
            summary=summary,
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data=data,
        )

    def _collect_network(self) -> Evidence:
        """Collect DNS and outbound connectivity evidence.

        Returns:
            Evidence describing network reachability.
        """
        hosts = tuple(
            str(item)
            for item in self._profile.network_setting(
                "dns_probe_hosts", ("www.microsoft.com",)
            )
            or ()
        ) or ("www.microsoft.com",)
        dns_results = [windows.resolve_host(host) for host in hosts]
        connectivity = windows.check_internet(hosts)
        resolved = all(item.get("resolved") for item in dns_results)
        available = bool(connectivity.get("available"))
        return Evidence(
            evidence_id=EV_NETWORK,
            layer=EvidenceLayer.RUNTIME,
            source="network reachability",
            summary=(
                f"DNS {'resolved' if resolved else 'unresolved'}, "
                f"outbound {'available' if available else 'unavailable'}"
            ),
            collector=self.name,
            reliability=SourceReliability.MEDIUM,
            data={
                "dns": dns_results,
                "connectivity": connectivity,
                "dns_resolved": resolved,
                "internet_available": available,
                "state": "available" if (resolved and available) else "unavailable",
            },
        )

    def _collect_clock(self) -> Evidence:
        """Collect system clock and drift evidence.

        Returns:
            Evidence describing the system clock.
        """
        clock = windows.clock_drift_seconds()
        drift = clock.get("drift_seconds")
        return Evidence(
            evidence_id=EV_CLOCK,
            layer=EvidenceLayer.RUNTIME,
            source="system clock",
            summary=(
                f"local time {clock.get('local_time_utc')} ({clock.get('time_zone')}), "
                f"drift {'unknown' if drift is None else format(float(drift), '+.3f') + 's'}"
            ),
            collector=self.name,
            reliability=SourceReliability.HIGH,
            data={**clock, "state": "measured" if drift is not None else "unmeasured"},
        )


class EnvironmentValidator(Validator):
    """Concludes whether the host is fit to run a validation."""

    def __init__(self, profile: ProductProfile | None = None) -> None:
        """Initialise the validator.

        Args:
            profile: Product profile, consulted for thresholds.
        """
        self._profile = profile or ProductProfile({})

    @property
    def name(self) -> str:
        """Component name."""
        return "environment.validator"

    def validate(self, context: ValidationContext) -> Sequence[Finding]:
        """Evaluate host environment evidence.

        Args:
            context: Run context carrying collected evidence.

        Returns:
            Findings about host fitness. Empty when every prerequisite is met --
            a met prerequisite is recorded as evidence and reported in the summary
            rather than inflated into a single-layer HEALTHY finding it could not
            corroborate.
        """
        findings: list[Finding] = []
        by_id = {item.evidence_id: item for item in context.evidence}

        if (os_evidence := by_id.get(EV_OS)) is not None:
            findings.extend(self._validate_os(os_evidence, context))
        if (clock_evidence := by_id.get(EV_CLOCK)) is not None:
            findings.extend(self._validate_clock(clock_evidence, context))
        if (network_evidence := by_id.get(EV_NETWORK)) is not None:
            findings.extend(self._validate_network(network_evidence, context))
        return tuple(findings)

    def _validate_os(
        self, evidence: Evidence, context: ValidationContext
    ) -> Sequence[Finding]:
        """Check the host operating system meets prerequisites.

        Args:
            evidence: OS evidence.
            context: Run context.

        Returns:
            Findings, empty when prerequisites are met.
        """
        data = evidence.data
        if not windows.is_windows():
            return (
                Finding.build(
                    what="host is not Windows; EmpMonitor validation cannot run here",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component="operating system",
                    why=f"observed platform is {data.get('system')!r}",
                    evidence=[evidence],
                    verdict=Verdict.BLOCKED,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                ),
            )

        minimum_build = self._profile.threshold("min_windows_build")
        build = str(data.get("build") or "")
        if minimum_build and build:
            from framework.shared.utils import version as version_utils  # noqa: PLC0415

            try:
                acceptable = version_utils.is_at_least(build, str(minimum_build))
            except Exception:  # noqa: BLE001 -- an unparsable build is not a product defect
                acceptable = True
            if not acceptable:
                return (
                    Finding.build(
                        what="Windows build is below the configured minimum",
                        where_layer=EvidenceLayer.RUNTIME,
                        where_component="operating system",
                        why=f"observed build {build}, minimum {minimum_build}",
                        evidence=[evidence],
                        verdict=Verdict.BLOCKED,
                        minimum_layers=context.minimum_layers,
                        plugin_id=context.plugin_id,
                    ),
                )
        return ()

    def _validate_clock(
        self, evidence: Evidence, context: ValidationContext
    ) -> Sequence[Finding]:
        """Check system clock drift against the configured tolerance.

        Args:
            evidence: Clock evidence.
            context: Run context.

        Returns:
            Findings about the clock.
        """
        drift = evidence.data.get("drift_seconds")
        tolerance = float(self._profile.threshold("max_clock_drift_seconds", 120))
        if drift is None:
            return (
                Finding.build(
                    what="system clock drift could not be measured",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component="system clock",
                    why=str(evidence.data.get("error") or Finding.UNDETERMINED),
                    evidence=[evidence],
                    verdict=Verdict.INCONCLUSIVE,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "Unmeasured drift is inconclusive, never a pass: timestamp "
                        "comparison at later layers depends on it.",
                    ),
                ),
            )
        if abs(float(drift)) > tolerance:
            return (
                Finding.build(
                    what="system clock drift exceeds the configured tolerance",
                    where_layer=EvidenceLayer.RUNTIME,
                    where_component="system clock",
                    why=f"drift {float(drift):+.3f}s exceeds tolerance {tolerance:.0f}s",
                    evidence=[evidence],
                    verdict=Verdict.DEGRADED,
                    minimum_layers=context.minimum_layers,
                    plugin_id=context.plugin_id,
                    notes=(
                        "DEGRADED rather than FAILED: the host functions, but timestamp "
                        "correlation against the server may be unreliable.",
                    ),
                ),
            )
        return ()

    def _validate_network(
        self, evidence: Evidence, context: ValidationContext
    ) -> Sequence[Finding]:
        """Check outbound network availability.

        Args:
            evidence: Network evidence.
            context: Run context.

        Returns:
            Findings about connectivity.
        """
        if evidence.data.get("dns_resolved") and evidence.data.get("internet_available"):
            return ()
        return (
            Finding.build(
                what="host has no usable outbound network connectivity",
                where_layer=EvidenceLayer.RUNTIME,
                where_component="network",
                why=(
                    "DNS resolution failed"
                    if not evidence.data.get("dns_resolved")
                    else "outbound TCP connection failed"
                ),
                evidence=[evidence],
                verdict=Verdict.BLOCKED,
                minimum_layers=context.minimum_layers,
                plugin_id=context.plugin_id,
                notes=(
                    "Blocking rather than failing: without connectivity the agent cannot "
                    "be expected to synchronize, so a sync verdict would be meaningless.",
                ),
            ),
        )
