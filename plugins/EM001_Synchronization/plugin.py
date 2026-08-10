"""EM001 -- Synchronization Validator.

Reverse-engineers the synchronization lifecycle from observable evidence, then
validates what it found. The order matters: the plugin does not set out to prove
synchronization works, it sets out to establish **how** it works, and reports only
what the evidence supports.

Layer coverage is L1 (configured intent), L2 (the process doing the work), and L3
(what actually crossed the wire, as far as passive observation reveals). Layer 4 is
deliberately absent: no dashboard collector exists, and asserting dashboard
visibility without one would invent behaviour.

Depends on ``EM000_EnvironmentValidator``: synchronization cannot be meaningfully
assessed on a machine whose agent is not installed and running, and the environment
gate skips this plugin entirely when the pre-check is negative.
"""

from __future__ import annotations

from typing import Any, Sequence

from framework.core.evidence import EvidenceStore
from framework.core.pipeline import EvidencePipeline
from framework.core.validation import ValidationEngine
from framework.monitors.executable_monitor import ExecutableCollector
from framework.monitors.runtime_monitor import ProcessCollector, ServiceCollector
from framework.monitors.sync_monitor import (
    AgentNetworkCollector,
    SyncLogCollector,
    SyncQueueCollector,
)
from framework.shared.config import ConfigurationManager
from framework.shared.interfaces import Plugin
from framework.shared.logger import get_logger
from framework.shared.models import (
    Evidence,
    EvidenceLayer,
    ExecutionResult,
    ExecutionStatus,
    Finding,
    PluginMetadata,
    SourceReliability,
    ValidationContext,
    Verdict,
    utc_now,
)
from framework.shared.profile import ProductProfile
from framework.validators.configuration import ConfigurationCollector
from framework.validators.environment import EnvironmentCollector
from framework.validators.synchronization import (
    AuthenticationValidator,
    LatencyValidator,
    QueueValidator,
    RecoveryValidator,
    RetryValidator,
    SchedulerValidator,
    SynchronizationValidator,
    UploadValidator,
)
from plugins.EM001_Synchronization.promotion import build_promotions
from plugins.EM001_Synchronization.summary import build_summary
from plugins.EM001_Synchronization.timeline import build_evidence_graph, build_timeline

__all__ = ["PLUGIN_ID", "SynchronizationPlugin"]

_LOGGER = get_logger(__name__)

PLUGIN_ID = "EM001_Synchronization"
_ENVIRONMENT_PLUGIN = "EM000_EnvironmentValidator"


class SynchronizationPlugin(Plugin):
    """Reverse-engineers and validates the synchronization lifecycle."""

    def __init__(
        self,
        *,
        profile: ProductProfile | None = None,
        evidence_store: EvidenceStore | None = None,
    ) -> None:
        """Initialise the plugin.

        Args:
            profile: Product profile. Loaded from configuration when omitted so the
                plugin works under discovery while staying injectable for testing.
            evidence_store: Store used to record evidence and apply catalog
                reliability.
        """
        self._profile = profile if profile is not None else self._load_profile()
        self._store = evidence_store
        self._summary: dict[str, Any] = {}
        self._promotions: tuple[Any, ...] = ()

    @staticmethod
    def _load_profile() -> ProductProfile:
        """Load the product profile from configuration.

        Returns:
            The profile, empty when unconfigured -- which makes :meth:`precheck`
            block rather than guess.
        """
        try:
            configuration = ConfigurationManager.instance().load()
        except Exception as exc:  # noqa: BLE001 -- surfaced by precheck, not raised
            _LOGGER.error("Product profile could not be loaded: %s", exc)
            return ProductProfile({})
        section = configuration.get("empmonitor", {})
        return ProductProfile(section if isinstance(section, dict) else {})

    @property
    def metadata(self) -> PluginMetadata:
        """Declarative plugin metadata."""
        return PluginMetadata(
            plugin_id=PLUGIN_ID,
            name="Synchronization Validator",
            version="1.0.0",
            description=(
                "Reverse-engineers the EmpMonitor synchronization lifecycle from "
                "configuration, runtime, log, queue, and connection evidence, then "
                "validates the scheduler, queue, authentication, upload, retry, "
                "recovery, and latency behaviour it observed."
            ),
            evidence_layers=(
                EvidenceLayer.CONFIGURATION,
                EvidenceLayer.RUNTIME,
                EvidenceLayer.SYNCHRONIZATION,
            ),
            depends_on=(_ENVIRONMENT_PLUGIN,),
            feature_spec_ref="HB-006 (synchronization)",
            timeout_seconds=300.0,
            max_attempts=1,
        )

    @property
    def summary(self) -> dict[str, Any]:
        """The report summary from the most recent execution."""
        return dict(self._summary)

    def precheck(self, context: ValidationContext) -> Sequence[Finding]:
        """Confirm the plugin can observe anything at all.

        Args:
            context: Run context.

        Returns:
            A ``BLOCKED`` finding when the synchronization profile is missing --
            without configured log patterns and locations there is nothing to observe,
            and reporting "no synchronization" would be a false accusation.
        """
        if not self._profile.is_configured:
            return (self._blocked(context, "the EmpMonitor product profile is not configured"),)
        if not self._profile.raw.get("synchronization"):
            return (
                self._blocked(
                    context,
                    "config/framework.json has no 'empmonitor.synchronization' block, so no "
                    "log source or pattern is known",
                ),
            )
        return ()

    def _blocked(self, context: ValidationContext, why: str) -> Finding:
        """Build a ``BLOCKED`` precondition finding.

        Args:
            context: Run context.
            why: Why the plugin cannot proceed.

        Returns:
            The finding.
        """
        evidence = Evidence(
            evidence_id="EV-007",
            layer=EvidenceLayer.SYNCHRONIZATION,
            source="synchronization:log",
            summary="synchronization observation is not configured",
            collector=PLUGIN_ID,
            reliability=SourceReliability.HIGH,
            data={"state": "unconfigured"},
        )
        return Finding.build(
            what="synchronization cannot be observed",
            where_layer=EvidenceLayer.SYNCHRONIZATION,
            where_component="framework configuration",
            why=why,
            evidence=[evidence],
            verdict=Verdict.BLOCKED,
            minimum_layers=context.minimum_layers,
            plugin_id=PLUGIN_ID,
            notes=(
                "Blocked, not failed: this is a framework configuration gap and no claim "
                "about EmpMonitor may be drawn from it.",
            ),
        )

    def _build_pipeline(self, context: ValidationContext) -> EvidencePipeline:
        """Compose the synchronization pipeline.

        Collector order runs L1 and L2 before L3 so that when validators execute,
        configured intent and runtime state are already available to corroborate
        Layer 3 observations. The configuration and process collectors are **reused**
        from the framework rather than reimplemented, which keeps one artifact to one
        collector.

        Args:
            context: Run context supplying the corroboration minimum.

        Returns:
            The composed pipeline.
        """
        engine = ValidationEngine(minimum_layers=context.minimum_layers)
        pipeline = EvidencePipeline(engine=engine)
        # Layer 1 -- configured intent (interval, auth, feature settings).
        pipeline.add_collector(ConfigurationCollector(self._profile))
        # Layer 2 -- is the thing that uploads actually alive, and which build is it?
        # The executable collector is included specifically so every knowledge
        # promotion can record the agent version it was verified against, which the
        # verification workflow requires (knowledge_base/README.md §6.1). A claim
        # without a version is not reviewable: nobody can tell what it applies to.
        pipeline.add_collector(ProcessCollector(self._profile))
        pipeline.add_collector(ServiceCollector(self._profile))
        pipeline.add_collector(ExecutableCollector(self._profile))
        pipeline.add_collector(EnvironmentCollector(self._profile))
        # Layer 3 -- the three passive strategies adopted by the design spike.
        pipeline.add_collector(SyncLogCollector(self._profile))
        pipeline.add_collector(SyncQueueCollector(self._profile))
        pipeline.add_collector(AgentNetworkCollector(self._profile))

        pipeline.add_validator(SchedulerValidator(self._profile))
        pipeline.add_validator(QueueValidator(self._profile))
        pipeline.add_validator(AuthenticationValidator(self._profile))
        pipeline.add_validator(UploadValidator(self._profile))
        pipeline.add_validator(RetryValidator(self._profile))
        pipeline.add_validator(RecoveryValidator(self._profile))
        pipeline.add_validator(LatencyValidator(self._profile))
        pipeline.add_validator(SynchronizationValidator(self._profile))
        return pipeline

    def execute(self, context: ValidationContext) -> ExecutionResult:
        """Reverse-engineer and validate synchronization.

        Args:
            context: Run context.

        Returns:
            The execution result carrying findings, the reconstructed timeline, the
            evidence graph, and proposed knowledge promotions.
        """
        started = utc_now()
        pipeline = self._build_pipeline(context)
        result = pipeline.run(context)

        recorded = result.evidence
        if self._store is not None:
            try:
                recorded = self._store.extend(result.evidence)
            except Exception as exc:  # noqa: BLE001 -- evidence must still be reported
                _LOGGER.error("Evidence could not be recorded in the store: %s", exc)

        findings = tuple(result.findings)
        verdict = pipeline.engine.aggregate(findings)
        confidence = pipeline.engine.aggregate_confidence(findings)

        timeline = build_timeline(recorded, findings)
        graph = build_evidence_graph(recorded, findings)
        agent_version = self._observed_agent_version(recorded)
        self._promotions = build_promotions(
            findings,
            recorded,
            agent_version=agent_version,
            method=(
                "Passive observation by EM001_Synchronization: agent log patterns, "
                "local queue state, and host connection table"
            ),
        )
        self._summary = build_summary(
            recorded,
            findings,
            timeline=timeline,
            graph=graph,
            promotions=self._promotions,
            verdict=verdict,
            confidence=confidence,
            agent_version=agent_version,
        )

        for error in result.errors:
            _LOGGER.error(
                "Sync stage error in %s (%s): %s", error.stage, error.component, error.message
            )

        observed_stages = sum(1 for stage in timeline if stage.observed)
        _LOGGER.info(
            "Synchronization: %s (%s) -- %d evidence, %d finding(s), "
            "%d/%d lifecycle stage(s) observed across %s",
            verdict.value,
            confidence.name,
            len(recorded),
            len(findings),
            observed_stages,
            len(timeline),
            ", ".join(layer.label for layer in result.layers_covered) or "no layers",
        )
        return ExecutionResult(
            unit_id=PLUGIN_ID,
            status=ExecutionStatus.COMPLETED,
            findings=findings,
            started_at=started,
            finished_at=utc_now(),
            metadata={
                "summary": self._summary,
                "timeline": [stage.to_dict() for stage in timeline],
                "evidence_graph": graph,
                "promotions": [record.to_dict() for record in self._promotions],
                "pipeline": result.to_dict(),
                "stage_errors": [
                    {
                        "stage": error.stage,
                        "component": error.component,
                        "message": error.message,
                    }
                    for error in result.errors
                ],
            },
        )

    @staticmethod
    def _observed_agent_version(evidence: Sequence[Evidence]) -> str | None:
        """Read the agent version from executable evidence, if present.

        Args:
            evidence: Collected evidence.

        Returns:
            The observed agent version, or ``None``. Recorded on every promotion so a
            future reader knows which build a claim was verified against.
        """
        for item in evidence:
            if item.source == "executable:agent":
                version = item.data.get("version") or {}
                if isinstance(version, dict) and version.get("file_version"):
                    return str(version["file_version"])
        return None

    def postcheck(
        self, context: ValidationContext, result: ExecutionResult
    ) -> Sequence[Finding]:
        """Confirm the reverse engineering produced a usable picture.

        Args:
            context: Run context.
            result: The execution result.

        Returns:
            An ``INCONCLUSIVE`` finding when no lifecycle stage could be observed --
            a pipeline reconstruction with nothing in it must not read as success.
        """
        timeline = result.metadata.get("timeline") or []
        observed = [stage for stage in timeline if stage.get("observed")]
        if observed:
            return ()
        evidence = Evidence(
            evidence_id="EV-007",
            layer=EvidenceLayer.SYNCHRONIZATION,
            source="synchronization:log",
            summary="no lifecycle stage was observed",
            collector=PLUGIN_ID,
            reliability=SourceReliability.HIGH,
            data={"state": "no observation"},
        )
        return (
            Finding.build(
                what="no synchronization lifecycle stage could be observed",
                where_layer=EvidenceLayer.SYNCHRONIZATION,
                where_component="synchronization:pipeline",
                why=Finding.UNDETERMINED,
                evidence=[evidence],
                verdict=Verdict.INCONCLUSIVE,
                minimum_layers=context.minimum_layers,
                plugin_id=PLUGIN_ID,
                notes=(
                    "Treat synchronization as unverified rather than broken: the "
                    "observation produced nothing, which is a gap in observation.",
                ),
            ),
        )
